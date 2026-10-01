"""飞书盲棋 webhook service — 接收 gateway 转发的消息，处理游戏逻辑。

改造自原 bot.py：删除 lark SDK 直连，改为 FastAPI webhook service。
- 入站：POST /on_message（gateway 转发用户文本）
- 入站：POST /on_card_action（gateway 转发按钮点击）
- 出站：调 gateway /send_message /send_card /send_image 发消息

依赖 FeishuGateway（cta_service）统一管理飞书连接。
"""

import json
import logging
import os
import tempfile
from typing import Dict, Optional, Any

import httpx
from fastapi import FastAPI
from pydantic import BaseModel

from .config import FeishuConfig
from .message import parse_user_message, UserIntent, get_help_text
from xiangqi_engine.engine.pikafish import PikafishEngine, INITIAL_FEN
from xiangqi_engine.game.game import Game
from xiangqi_engine.notation.converter import MoveConverter
from xiangqi_engine.storage.recorder import GameRecorder
from xiangqi_engine.game.validator import MoveValidator

logger = logging.getLogger(__name__)

# ===== Gateway 配置 =====
GATEWAY_URL = os.getenv("GATEWAY_URL", "http://localhost:9000")
SERVICE_NAME = os.getenv("SERVICE_NAME", "blind_chess")

# 待确认删除的用户列表（存储删除参数）
_pending_delete: Dict[str, dict] = {}


# ===== 绝杀/趣味消息 =====

CHECKMATE_WIN_MSGS = [
    "绝杀吴姐！",
    "一招毙命！",
    "绝杀！小瘪三，给我擦皮鞋",
    "绝杀！窝要烟牌！",
    "绝杀！我二弟天下无敌！"
]

CHECKMATE_LOSS_MSGS = [
    "哦哦，你噶了",
    "很抱歉，你输了",
    "再来一局吧",
]

AI_RESPONSE_MSGS = [
    "少侠好身手",
    "佩服佩服，愿赌服输",
    "高手高手，下次再来",
    "今日败在你手下，老夫无话可说",
]

PLAYER_LOSS_HARD_MSGS = [
    "哼！三十年河东三十年河西，莫欺少年穷！",
    "今日虽败，但我必东山再起！",
    "胜败乃兵家常事，大侠请重新来过！",
    "我还会回来的！！！",
    "不服！再来一局！",
    "这局不算！刚才手滑了！",
    "等我练好神功，再来取你首级！",
    "大胆！竟敢赢我，下次让你输得心服口服！",
    "且慢！容我回去修炼三年！",
    "可恶！居然被你套路了！",
]


import cchess


def _is_being_checked(fen: str) -> bool:
    try:
        board = cchess.ChessBoard(fen)
        current_color = board.get_move_color()
        opponent_color = cchess.BLACK if current_color == cchess.RED else cchess.RED
        board.set_move_color(opponent_color)
        return board.is_checking()
    except Exception as e:
        logger.error(f"被将军检测异常: {e}")
        return False


def _is_checking_opponent(fen: str) -> bool:
    try:
        board = cchess.ChessBoard(fen)
        current_color = board.get_move_color()
        opponent_color = cchess.BLACK if current_color == cchess.RED else cchess.RED
        board.set_move_color(opponent_color)
        result = board.is_checking()
        logger.info(f"将军检测: FEN={fen[:50]}..., result={result}")
        return result
    except Exception as e:
        logger.error(f"将军检测异常: {e}")
        return False


def _check_game_state(fen: str) -> tuple[str, bool]:
    try:
        board = cchess.ChessBoard(fen)
        if board.no_moves():
            if _is_being_checked(fen):
                return "将死", True
            else:
                return "困毙", True
        return "", False
    except Exception as e:
        logger.error(f"游戏状态检测异常: {e}")
        return "", False


def _get_checkmate_msg(player_won: bool) -> str:
    import random
    msg = random.choice(CHECKMATE_WIN_MSGS)
    ai_response = random.choice(AI_RESPONSE_MSGS)
    return f"{msg}\nAI：{ai_response}"


def _get_loss_msg() -> tuple[str, str]:
    import random
    loss_msg = random.choice(CHECKMATE_LOSS_MSGS)
    hard_msg = random.choice(PLAYER_LOSS_HARD_MSGS)
    return loss_msg, hard_msg


# ===== Gateway 出站客户端 =====

def _send_text(text: str) -> None:
    """通过 gateway 发文本消息"""
    try:
        httpx.post(
            f"{GATEWAY_URL}/send_message",
            json={
                "msg_type": "text",
                "content": json.dumps({"text": text}, ensure_ascii=False),
                "service_name": SERVICE_NAME,
            },
            timeout=5,
        )
    except Exception as e:
        logger.error(f"发文本失败: {e}")


def _send_card(card: dict) -> Optional[str]:
    """通过 gateway 发卡片消息，返回 message_id（失败返回 None）

    调用方可存 message_id 以便后续 update_card 更新此卡片。
    """
    try:
        resp = httpx.post(
            f"{GATEWAY_URL}/send_card",
            json={"card": card, "service_name": SERVICE_NAME},
            timeout=5,
        )
        if resp.status_code == 200:
            data = resp.json()
            if data.get("ok"):
                return data.get("message_id")
            logger.error(f"发卡片失败: {data.get('error')}")
        else:
            logger.error(f"发卡片 HTTP {resp.status_code}: {resp.text}")
    except Exception as e:
        logger.error(f"发卡片失败: {e}")
    return None


def _update_card(message_id: str, card: dict) -> bool:
    """通过 gateway 更新已发送的卡片（全量替换），返回 True/False"""
    if not message_id:
        logger.warning("update_card 缺 message_id")
        return False
    try:
        resp = httpx.post(
            f"{GATEWAY_URL}/update_card",
            json={
                "message_id": message_id,
                "card": card,
                "service_name": SERVICE_NAME,
            },
            timeout=5,
        )
        if resp.status_code == 200:
            data = resp.json()
            if data.get("ok"):
                return True
            logger.error(f"更新卡片失败: {data.get('error')}")
        else:
            logger.error(f"更新卡片 HTTP {resp.status_code}: {resp.text}")
    except Exception as e:
        logger.error(f"更新卡片失败: {e}")
    return False


def _send_image(image_bytes: bytes, text: str = "", title: str = "") -> None:
    """通过 gateway 上传图片 + 发消息（一条请求搞定）"""
    try:
        httpx.post(
            f"{GATEWAY_URL}/send_image",
            data={
                "service_name": SERVICE_NAME,
                "text": text,
                "title": title,
            },
            files={"image": ("board.png", image_bytes, "image/png")},
            timeout=30,
        )
    except Exception as e:
        logger.error(f"发图片失败: {e}")


# ===== GameSession（原样保留，不依赖飞书 SDK）=====

class GameSession:
    """用户对局会话"""

    def __init__(self, user_id: str = "default"):
        self.user_id = user_id
        self.game: Optional[Game] = None
        self.engine: Optional[PikafishEngine] = None
        self.converter: MoveConverter = MoveConverter()
        self.validator: MoveValidator = MoveValidator()
        self.recorder: GameRecorder = GameRecorder()
        self.game_path: Optional[str] = None

    def _save_game(self) -> None:
        if self.game:
            if self.game_path:
                self.game.save(self.game_path)
                logger.info(f"对局已更新: {self.game_path}")
            else:
                path = self.recorder.save_game(self.game)
                self.game_path = str(path)
                logger.info(f"对局已保存: {path}")

    def get_turn_start_status(self) -> tuple[str, bool]:
        if not self.game:
            return "", False
        fen = self.game.get_fen()
        status, ended = _check_game_state(fen)
        if ended:
            self.game.set_result("loss")
            self._save_game()
            loss_msg, hard_msg = _get_loss_msg()
            msg = f"{loss_msg}\n你：{hard_msg}"
            return msg, True
        being_checked = _is_being_checked(fen)
        check_msg = "\n⚔️ **被将军**，请解将！" if being_checked else ""
        return check_msg, False

    def start_game(self, color: str = "red", level: int = 5) -> str:
        self.game_path = None
        self.engine = PikafishEngine()
        self.engine.start()
        self.engine.set_user_level(level)
        self.game = Game.create(player_color=color, level=level)

        if color == "black":
            ai_move = self.engine.get_best_move()
            if ai_move:
                self.converter.set_board_state(INITIAL_FEN)
                chinese = self.converter.uci_to_chinese(ai_move, "red")
                self.game.make_move(ai_move, chinese)
                self.engine.set_position(self.game.get_fen())
                color_text = "黑方"
                turn_msg, ended = self.get_turn_start_status()
                if ended:
                    return f"对局已开始！\n执方：{color_text}\n难度：Lv{level}\nAI先手：{chinese}\n{turn_msg}"
                return f"对局已开始！\n执方：{color_text}\n难度：Lv{level}\nAI先手：{chinese}{turn_msg}\n请走棋"
            else:
                color_text = "黑方"
                return f"对局已开始！\n执方：{color_text}\n难度：Lv{level}\nAI无棋可走，你赢了！"

        color_text = "红方" if color == "red" else "黑方"
        return f"对局已开始！\n执方：{color_text}\n难度：Lv{level}\n请走棋"

    def make_move(self, move_text: str) -> tuple[str, bool]:
        if not self.game or not self.engine:
            return "没有进行中的对局", False

        current_fen = self.game.get_fen()
        current_side = self.game.get_current_side()
        self.converter.set_board_state(current_fen)

        try:
            uci_move = self.converter.chinese_to_uci(move_text, current_side)
        except Exception as e:
            logger.error(f"招法解析失败: {e}")
            return f"招法解析失败: {move_text}", False

        is_legal, error = self.validator.is_legal(current_fen, uci_move)
        if not is_legal:
            return f"非法招法: {error}", False

        self.game.make_move(uci_move, move_text)
        fen_after_player_move = self.game.get_fen()
        self.engine.set_position(fen_after_player_move)

        player_checking = _is_checking_opponent(fen_after_player_move)
        logger.info(f"玩家走棋后将军检测: player_checking={player_checking}")

        status, ended = _check_game_state(self.game.get_fen())
        if ended:
            self.game.set_result("win")
            self._save_game()
            checkmate_msg = _get_checkmate_msg(player_won=True)
            result_msg = f"你：{move_text}，{checkmate_msg}"
            card = {
                "config": {"wide_screen_mode": True},
                "elements": [{"tag": "markdown", "content": result_msg}]
            }
            return ("card", result_msg, card), True

        ai_move = self.engine.get_best_move()
        if ai_move:
            ai_fen = self.game.get_fen()
            self.converter.set_board_state(ai_fen)
            ai_side = self.game.get_current_side()
            ai_chinese = self.converter.uci_to_chinese(ai_move, ai_side)
            self.game.make_move(ai_move, ai_chinese)
            self.engine.set_position(self.game.get_fen())

            ai_checking = _is_checking_opponent(self.game.get_fen())
            self._save_game()

            status, ended = _check_game_state(self.game.get_fen())
            if ended:
                self.game.set_result("loss")
                self._save_game()
                loss_msg, hard_msg = _get_loss_msg()
                result_msg = f"你：{move_text}\nAI：{ai_chinese}，{loss_msg}\n你：{hard_msg}"
                card = {
                    "config": {"wide_screen_mode": True},
                    "elements": [{"tag": "markdown", "content": result_msg}]
                }
                return ("card", result_msg, card), True

            if player_checking or ai_checking:
                content = f"你：**{move_text}**"
                if player_checking:
                    content += " ⚔️ **将军**"
                content += f"\nAI：**{ai_chinese}**"
                if ai_checking:
                    content += " ⚔️ **将军**"
                next_turn_msg, next_ended = self.get_turn_start_status()
                if next_turn_msg:
                    content += next_turn_msg
                card = {
                    "config": {"wide_screen_mode": True},
                    "elements": [{"tag": "markdown", "content": content}]
                }
                return ("card", content, card), True

            next_turn_msg, next_ended = self.get_turn_start_status()
            return f"你：{move_text}\nAI：{ai_chinese}{next_turn_msg}", True

        self.game.set_result("win")
        self._save_game()
        checkmate_msg = _get_checkmate_msg(player_won=True)
        result_msg = f"你：{move_text}，{checkmate_msg}"
        card = {
            "config": {"wide_screen_mode": True},
            "elements": [{"tag": "markdown", "content": result_msg}]
        }
        return ("card", result_msg, card), True

    def get_status(self) -> str:
        if not self.game:
            return "没有进行中的对局"
        fen = self.game.get_fen()
        moves_text = self.game.get_moves_text()
        current_side = self.game.get_current_side()
        side_text = "红方" if current_side == "red" else "黑方"
        return f"当前：{side_text}行棋\n回合数：{self.game.get_move_count() // 2}\n招法记录：\n{moves_text}"

    def resign(self) -> str:
        if self.game:
            self.game.set_result("loss")
            self._save_game()
            if self.engine:
                self.engine.stop()
            self.game = None
            self.engine = None
            return "你认输了！AI获胜"
        return "没有进行中的对局"

    def end(self) -> None:
        if self.engine:
            self.engine.stop()
            self.engine = None
        self.game = None

    def list_history(self, time_range: Optional[dict] = None) -> tuple[str, dict]:
        recorder = GameRecorder()
        params = time_range or {"limit": 10}
        games = recorder.list_games(
            date=params.get("date"),
            start_date=params.get("start_date"),
            date_prefix=params.get("date_prefix"),
            limit=params.get("limit", 10)
        )
        if not games:
            return ("暂无历史对局记录", None)

        elements = [
            {"tag": "div", "text": {"tag": "lark_md", "content": "**历史对局列表**"}}
        ]
        for i, g in enumerate(games, 1):
            color = "红方" if g["player_color"] == "red" else "黑方"
            result_map = {"ongoing": "进行中", "win": "胜", "loss": "负", "draw": "和"}
            result = result_map.get(g["result"], g["result"])
            start_time = g["date"][5:16].replace("T", " ")
            update_time = g.get("updated_at", g["date"])
            if update_time:
                update_time = update_time[5:16].replace("T", " ")
            else:
                update_time = start_time
            content = f"**#{i}** {start_time} → {update_time} | {color} Lv{g['level']} | {result} | {g['total_moves']}步"
            elements.append({"tag": "div", "text": {"tag": "lark_md", "content": content}})

        elements.append({"tag": "hr"})
        elements.append({
            "tag": "div",
            "text": {"tag": "lark_md", "content": "发送「切换1」继续某个对局\n发送「删除1」删除某个对局"}
        })
        interactive_content = {"config": {"wide_screen_mode": True}, "elements": elements}

        fallback_lines = ["历史对局列表："]
        for i, g in enumerate(games, 1):
            color = "红方" if g["player_color"] == "red" else "黑方"
            result = {"ongoing": "进行中", "win": "胜", "loss": "负", "draw": "和"}.get(g["result"], g["result"])
            fallback_lines.append(f"{i}. {g['date'][:10]} {color} Lv{g['level']} {result} {g['total_moves']}步")
        fallback_text = "\n".join(fallback_lines)
        return (fallback_text, interactive_content)

    def switch_to_game(self, game_index: int) -> str:
        recorder = GameRecorder()
        games = recorder.list_games(limit=10)
        if game_index < 1 or game_index > len(games):
            return f"无效编号，当前有 {len(games)} 个对局"
        game_data = games[game_index - 1]
        if self.engine:
            self.engine.stop()
        self.engine = PikafishEngine()
        self.engine.start()
        self.game = recorder.load_game(game_data["path"])
        self.game_path = game_data["path"]
        self.engine.set_position(self.game.get_fen())
        color_text = "红方" if self.game.meta.player_color == "red" else "黑方"
        return f"已切换到对局 #{game_index}\n执方：{color_text}\n难度：Lv{self.game.meta.level}\n回合：{self.game.get_move_count()//2 + 1}\n请走棋"

    def undo_moves(self, steps: int = 1) -> str:
        if not self.game or not self.engine:
            return "没有进行中的对局"
        current_moves = self.game.get_move_count()
        target_index = current_moves - steps * 2
        if target_index < 0:
            max_rounds = current_moves // 2
            return f"无法悔棋 {steps} 回，最多可悔 {max_rounds} 回"
        self.game.undo_to_move(target_index)
        self.engine.set_position(self.game.get_fen())
        remaining_rounds = self.game.get_move_count() // 2
        if not self.game.is_player_turn():
            ai_move = self.engine.get_best_move()
            if ai_move:
                current_fen = self.game.get_fen()
                self.converter.set_board_state(current_fen)
                ai_side = self.game.get_current_side()
                ai_chinese = self.converter.uci_to_chinese(ai_move, ai_side)
                self.game.make_move(ai_move, ai_chinese)
                self.engine.set_position(self.game.get_fen())
                self._save_game()
                turn_msg, ended = self.get_turn_start_status()
                if ended:
                    return f"已悔棋 {steps} 回\nAI：{ai_chinese}\n{turn_msg}"
                return f"已悔棋 {steps} 回\nAI：{ai_chinese}{turn_msg}\n请走棋"
            else:
                self.game.set_result("win")
                self._save_game()
                return f"已悔棋 {steps} 回\nAI无棋可走，绝杀！你赢了！"
        turn_msg, ended = self.get_turn_start_status()
        if ended:
            return f"已悔棋 {steps} 回\n{turn_msg}"
        self._save_game()
        return f"已悔棋 {steps} 回{turn_msg}\n当前回合：{remaining_rounds + 1}\n请走棋"


# ===== 意图处理（从 BlindChessBot._process_intent 改造）=====

# 全局会话（单用户场景，在 GameSession 定义之后）
_sessions: Dict[str, GameSession] = {}


def _process_intent(user_id: str, intent: UserIntent) -> Any:
    """处理用户意图，返回 str / ("card", fallback, card) / ("board", fen, color)"""
    session = _sessions.get(user_id)
    if session:
        logger.info(f"session.game={session.game is not None}, engine={session.engine is not None}")

    if intent.action == "new_game":
        if session:
            session.end()
        else:
            session = GameSession(user_id)
            _sessions[user_id] = session
        color = intent.color or FeishuConfig.DEFAULT_COLOR
        level = intent.level or FeishuConfig.DEFAULT_LEVEL
        return session.start_game(color, level)

    elif intent.action == "move":
        if not session:
            return "没有进行中的对局，发送「下棋」开始新对局"
        if not intent.move or not intent.move.is_valid:
            original = intent.move.original if intent.move else ""
            return f"招法格式错误: {original}\n\n正确格式:\n- 炮二平五 (炮平移)\n- 马二进三 (马跳跃)\n- 相三进五 (相斜走田字)\n\n发送「帮助」查看完整说明"
        result, success = session.make_move(intent.move.corrected)
        if not success:
            return f"招法执行失败: {result}\n\n发送「棋谱」查看当前状态"
        if isinstance(result, tuple) and result[0] == "card":
            return result
        return result

    elif intent.action == "status":
        if session:
            return session.get_status()
        return "没有进行中的对局"

    elif intent.action == "board":
        if not session:
            return "没有进行中的对局，发送「下棋」开始新对局"
        return ("board", session.game.get_fen(), session.game.meta.player_color)

    elif intent.action == "resign":
        if session:
            return session.resign()
        return "没有进行中的对局"

    elif intent.action == "help":
        return get_help_text()

    elif intent.action == "history":
        if not session:
            session = GameSession(user_id)
            _sessions[user_id] = session
        fallback, card = session.list_history(intent.time_range)
        if card:
            return ("card", fallback, card)
        return fallback

    elif intent.action == "switch_game":
        if not session:
            session = GameSession(user_id)
            _sessions[user_id] = session
        return session.switch_to_game(intent.game_index)

    elif intent.action == "undo":
        if not session:
            return "没有进行中的对局，发送「下棋」开始新对局"
        return session.undo_moves(intent.undo_steps or 1)

    elif intent.action == "delete_request":
        recorder = GameRecorder()
        delete_params = {"game_index": intent.game_index, "time_range": intent.time_range}
        if intent.game_index:
            games = recorder.list_games(limit=10)
            if intent.game_index < 1 or intent.game_index > len(games):
                return f"无效编号，当前有 {len(games)} 个对局"
            game = games[intent.game_index - 1]
            color = "红方" if game["player_color"] == "red" else "黑方"
            _pending_delete[user_id] = delete_params
            return f"即将删除对局 #{intent.game_index}\n{game['date'][:10]} {color} Lv{game['level']} {game['total_moves']}步\n发送「确认删除」执行"
        elif intent.time_range:
            if intent.time_range.get("clear_all"):
                total = len(recorder.list_games(limit=1000))
                _pending_delete[user_id] = delete_params
                return f"即将删除所有历史对局（共 {total} 个）\n发送「确认删除」执行"
            else:
                games = recorder.list_games(
                    date=intent.time_range.get("date"),
                    start_date=intent.time_range.get("start_date"),
                    date_prefix=intent.time_range.get("date_prefix"),
                    limit=100
                )
                if not games:
                    return "该范围内没有对局"
                range_desc = ""
                if intent.time_range.get("date"):
                    range_desc = intent.time_range.get("date")
                elif intent.time_range.get("start_date"):
                    range_desc = f"{intent.time_range.get('start_date')} 至今"
                elif intent.time_range.get("date_prefix"):
                    range_desc = intent.time_range.get("date_prefix") + " 月"
                _pending_delete[user_id] = delete_params
                return f"即将删除 {range_desc} 的对局（共 {len(games)} 个）\n发送「确认删除」执行"
        return "删除参数错误"

    elif intent.action == "delete_confirm":
        if user_id not in _pending_delete:
            return "请先发送删除命令"
        delete_params = _pending_delete[user_id]
        del _pending_delete[user_id]
        recorder = GameRecorder()
        if delete_params.get("game_index"):
            games = recorder.list_games(limit=10)
            if recorder.delete_game(games[delete_params["game_index"] - 1]["path"]):
                return f"已删除对局 #{delete_params['game_index']}"
            return "删除失败"
        elif delete_params.get("time_range"):
            time_range = delete_params["time_range"]
            if time_range.get("clear_all"):
                deleted = recorder.delete_all_games()
                return f"已清空所有历史对局，共删除 {deleted} 个"
            else:
                deleted = recorder.delete_games_by_range(
                    date=time_range.get("date"),
                    start_date=time_range.get("start_date"),
                    date_prefix=time_range.get("date_prefix")
                )
                return f"已删除 {deleted} 个对局"
        return "删除参数错误"

    elif intent.action == "error":
        return f"参数解析失败: {intent.move.original if intent.move else '未知'}\n\n发送「帮助」查看可用命令"

    return "未知命令"


def _dispatch_reply(reply: Any) -> None:
    """根据 reply 类型调对应的 gateway 出站 API"""
    if isinstance(reply, str):
        _send_text(reply)
    elif isinstance(reply, tuple):
        if reply[0] == "board":
            _, fen, player_color = reply
            _send_board_image(fen, player_color)
        elif reply[0] == "card":
            _, _, card = reply
            _send_card(card)
    else:
        logger.warning(f"未知 reply 类型: {type(reply)}")


def _send_board_image(fen: str, player_color: str = 'red') -> None:
    """生成棋盘图片并通过 gateway 发送"""
    try:
        from xiangqi_engine.image import generate_board_image
        method = FeishuConfig.BOARD_IMAGE_METHOD
        png_file = generate_board_image(fen, player_color=player_color, method=method)

        with open(png_file, 'rb') as f:
            image_bytes = f.read()

        _send_image(image_bytes)

        os.unlink(png_file)
    except Exception as e:
        logger.error(f"发送棋盘图片失败: {e}", exc_info=True)
        _send_text(f"棋盘图片生成失败: {e}")


# ===== FastAPI app =====

app = FastAPI(title="BlindChess Webhook Service")


class OnMessageRequest(BaseModel):
    text: str = ""
    user_id: str = ""
    chat_id: str = ""


class OnCardActionRequest(BaseModel):
    action: str = ""
    value: dict = {}
    message_id: str = ""  # 触发点击的卡片 ID（可用它调 update_card）
    user_id: str = ""
    chat_id: str = ""


@app.post("/on_message")
async def on_message(req: OnMessageRequest):
    """处理 gateway 转发的用户文本消息"""
    text = req.text.strip()
    if not text:
        return {"ok": True}

    # gateway 透传 user_id（ou_xxx）/ chat_id（oc_xxx），单用户场景兜底 "default"
    user_id = req.user_id or "default"

    # 取消待确认的删除操作（除非是确认删除）
    if user_id in _pending_delete and text not in ["确认删除", "确认", "confirm"]:
        del _pending_delete[user_id]

    intent = parse_user_message(text)
    reply = _process_intent(user_id, intent)
    _dispatch_reply(reply)

    return {"ok": True}


@app.post("/on_card_action")
async def on_card_action(req: OnCardActionRequest):
    """处理 gateway 转发的卡片按钮点击"""
    value = req.value or {}
    # gateway 已把 action 提取到顶层（从 value.action 取的），优先用顶层
    action = req.action or value.get("action", "")

    user_id = req.user_id or "default"
    session = _sessions.get(user_id)

    if action == "status":
        if session:
            _send_text(session.get_status())
            return {"toast": {"type": "success", "content": "棋谱已发送"}}
        return {"toast": {"type": "info", "content": "没有进行中的对局"}}

    elif action == "resign":
        if session:
            result = session.resign()
            _send_text(result)
            return {"toast": {"type": "success", "content": "已认输"}}
        return {"toast": {"type": "info", "content": "没有进行中的对局"}}

    elif action == "help":
        _send_text(get_help_text())
        return {"toast": {"type": "success", "content": "帮助已发送"}}

    elif action == "new_game":
        if session:
            session.end()
        else:
            session = GameSession(user_id)
            _sessions[user_id] = session
        color = FeishuConfig.DEFAULT_COLOR
        level = FeishuConfig.DEFAULT_LEVEL
        result = session.start_game(color, level)
        _send_text(result)
        return {"toast": {"type": "success", "content": "新对局已开始"}}

    return {"toast": {"type": "info", "content": f"未知操作: {action}"}}


@app.post("/help")
async def help():
    """gateway /help 调用，返回动态帮助文本"""
    return {"text": get_help_text()}


@app.get("/health")
async def health():
    return {"status": "ok"}
