"""飞书机器人主逻辑 - 长连接模式

使用飞书 WebSocket 长连接，服务器主动连接飞书，不需要公网IP。
"""

import json
import logging
from typing import Dict, Optional

from lark_oapi import Client, LogLevel
from lark_oapi.ws import Client as WSClient
from lark_oapi.event.dispatcher_handler import EventDispatcherHandler

from .config import FeishuConfig
from .message import parse_user_message, UserIntent, get_help_text
from xiangqi_engine.engine.pikafish import PikafishEngine, INITIAL_FEN
from xiangqi_engine.game.game import Game
from xiangqi_engine.notation.converter import MoveConverter
from xiangqi_engine.storage.recorder import GameRecorder
from xiangqi_engine.game.validator import MoveValidator

logger = logging.getLogger(__name__)

# 待确认删除的用户列表（存储删除参数）
_pending_delete: Dict[str, dict] = {}

# 绝杀趣味消息
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

# AI回应趣味消息
AI_RESPONSE_MSGS = [
    "少侠好身手",
    "佩服佩服，愿赌服输",
    "高手高手，下次再来",
    "今日败在你手下，老夫无话可说",
]

# 玩家输棋狠话
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
    """
    检查当前行棋方是否被将军

    需要切换到对手视角，让对手视角下行棋方检查是否将军。
    """
    try:
        board = cchess.ChessBoard(fen)
        current_color = board.get_move_color()
        opponent_color = cchess.BLACK if current_color == cchess.RED else cchess.RED

        # 切换到对手视角，检查对手是否在将军当前方
        board.set_move_color(opponent_color)
        return board.is_checking()
    except Exception as e:
        logger.error(f"被将军检测异常: {e}")
        return False


def _is_checking_opponent(fen: str) -> bool:
    """
    检查当前行棋方是否被将军（即对手刚才那步是否将军了当前方）

    重要理解：
    - 玩家走棋后，FEN 行棋方变成 AI（对手）
    - `is_checking()` 检测当前行棋方是否将军对手
    - 所以直接调用会检测 AI 是否将军玩家（反了！）
    - 正确做法：检测当前行棋方是否**被将军**（即对手是否将军了当前方）

    Returns:
        True 表示对手将军了当前行棋方
    """
    try:
        board = cchess.ChessBoard(fen)
        current_color = board.get_move_color()
        opponent_color = cchess.BLACK if current_color == cchess.RED else cchess.RED

        # 切换到对手视角，检测对手是否在将军当前方
        board.set_move_color(opponent_color)
        result = board.is_checking()
        logger.info(f"将军检测: FEN={fen[:50]}..., result={result}")
        return result
    except Exception as e:
        logger.error(f"将军检测异常: {e}")
        return False


def _check_game_state(fen: str) -> tuple[str, bool]:
    """
    检查游戏状态

    Returns:
        (状态描述, 是否结束)
        - ("", False) - 正常继续
        - ("将死", True) - 被将死
        - ("困毙", True) - 无棋可走但未被将军
    """
    try:
        board = cchess.ChessBoard(fen)

        # 使用 cchess 的 no_moves() 判断是否有合法招法
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
    """绝杀趣味消息（玩家赢时使用）"""
    import random
    msg = random.choice(CHECKMATE_WIN_MSGS)
    ai_response = random.choice(AI_RESPONSE_MSGS)
    return f"{msg}\nAI：{ai_response}"


def _get_loss_msg() -> tuple[str, str]:
    """玩家输时的消息（AI绝杀信息和玩家狠话）"""
    import random
    loss_msg = random.choice(CHECKMATE_LOSS_MSGS)
    hard_msg = random.choice(PLAYER_LOSS_HARD_MSGS)
    return loss_msg, hard_msg


class GameSession:
    """用户对局会话"""

    def __init__(self, user_id: str):
        self.user_id = user_id
        self.game: Optional[Game] = None
        self.engine: Optional[PikafishEngine] = None
        self.converter: MoveConverter = MoveConverter()
        self.validator: MoveValidator = MoveValidator()
        self.recorder: GameRecorder = GameRecorder()
        self.game_path: Optional[str] = None  # 当前对局保存路径

    def _save_game(self) -> None:
        """保存当前对局"""
        if self.game:
            if self.game_path:
                # 覆盖现有对局文件
                self.game.save(self.game_path)
                logger.info(f"对局已更新: {self.game_path}")
            else:
                # 新建对局文件
                path = self.recorder.save_game(self.game)
                self.game_path = str(path)
                logger.info(f"对局已保存: {path}")

    def get_turn_start_status(self) -> tuple[str, bool]:
        """获取回合开始时的状态提示（玩家回合开始时调用）

        参考 CLI 版本逻辑：
        1. 检测绝杀/困毙 - 如果玩家无棋可走，自动结束游戏
        2. 检测被将军 - 提示玩家需要解将

        Returns:
            (提示消息, 是否游戏结束)
        """
        if not self.game:
            return "", False

        fen = self.game.get_fen()
        logger.info(f"回合开始状态检测: FEN={fen[:60]}...")

        # 检测绝杀/困毙
        status, ended = _check_game_state(fen)
        logger.info(f"绝杀/困毙检测: status={status}, ended={ended}")
        if ended:
            # 玩家无棋可走，游戏结束
            self.game.set_result("loss")
            self._save_game()
            loss_msg, hard_msg = _get_loss_msg()
            msg = f"{loss_msg}\n你：{hard_msg}"
            return msg, True

        # 检测玩家是否被将军
        being_checked = _is_being_checked(fen)
        logger.info(f"被将军检测: being_checked={being_checked}")
        check_msg = "\n⚔️ **被将军**，请解将！" if being_checked else ""

        return check_msg, False

    def start_game(self, color: str = "red", level: int = 5) -> str:
        """开始新对局"""
        self.game_path = None  # 新对局，清空路径
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

                # 检查回合开始状态（玩家是否被将军或绝杀）
                turn_msg, ended = self.get_turn_start_status()
                if ended:
                    # 极罕见情况：AI第一步绝杀玩家
                    return f"对局已开始！\n执方：{color_text}\n难度：Lv{level}\nAI先手：{chinese}\n{turn_msg}"

                return f"对局已开始！\n执方：{color_text}\n难度：Lv{level}\nAI先手：{chinese}{turn_msg}\n请走棋"
            else:
                # AI 无法走棋（极罕见）
                color_text = "黑方"
                return f"对局已开始！\n执方：{color_text}\n难度：Lv{level}\nAI无棋可走，你赢了！"

        color_text = "红方" if color == "red" else "黑方"
        return f"对局已开始！\n执方：{color_text}\n难度：Lv{level}\n请走棋"

    def make_move(self, move_text: str) -> tuple[str, bool]:
        """执行玩家招法"""
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

        # 验证招法合法性（包括是否会导致被将军）
        is_legal, error = self.validator.is_legal(current_fen, uci_move)
        if not is_legal:
            return f"非法招法: {error}", False

        # 执行招法
        self.game.make_move(uci_move, move_text)
        fen_after_player_move = self.game.get_fen()
        self.engine.set_position(fen_after_player_move)

        # 检查玩家是否将军对手
        # 注意：走棋后，FEN的行棋方已切换到AI
        # is_checking() 检测当前行棋方(AI)是否被将军 = 玩家将军了AI
        player_checking = _is_checking_opponent(fen_after_player_move)
        logger.info(f"玩家走棋后将军检测: FEN={fen_after_player_move[:50]}..., player_checking={player_checking}")

        # 检查 AI 是否被绝杀/困毙
        status, ended = _check_game_state(self.game.get_fen())
        if ended:
            # AI 无棋可走，玩家获胜
            self.game.set_result("win")
            self._save_game()
            checkmate_msg = _get_checkmate_msg(player_won=True)
            # 招法和绝杀提示在同一行
            result_msg = f"你：{move_text}，{checkmate_msg}"
            card = {
                "config": {"wide_screen_mode": True},
                "elements": [{"tag": "markdown", "content": result_msg}]
            }
            return ("card", result_msg, card), True

        # AI 走棋
        ai_move = self.engine.get_best_move()
        if ai_move:
            ai_fen = self.game.get_fen()
            self.converter.set_board_state(ai_fen)
            ai_side = self.game.get_current_side()
            ai_chinese = self.converter.uci_to_chinese(ai_move, ai_side)
            self.game.make_move(ai_move, ai_chinese)
            self.engine.set_position(self.game.get_fen())

            # 检查 AI 是否将军玩家
            ai_checking = _is_checking_opponent(self.game.get_fen())

            self._save_game()  # 保存对局

            # 检查玩家是否被绝杀/困毙
            status, ended = _check_game_state(self.game.get_fen())
            if ended:
                # 玩家无棋可走，AI获胜 - 三行格式
                self.game.set_result("loss")
                self._save_game()
                loss_msg, hard_msg = _get_loss_msg()
                # 第一行：玩家招法，第二行：AI招法+绝杀信息，第三行：玩家狠话
                result_msg = f"你：{move_text}\nAI：{ai_chinese}，{loss_msg}\n你：{hard_msg}"
                card = {
                    "config": {"wide_screen_mode": True},
                    "elements": [{"tag": "markdown", "content": result_msg}]
                }
                return ("card", result_msg, card), True

            # 正常走棋，构建消息
            if player_checking or ai_checking:
                # 返回卡片消息来突出将军提示
                content = f"你：**{move_text}**"
                if player_checking:
                    content += " ⚔️ **将军**"
                content += f"\nAI：**{ai_chinese}**"
                if ai_checking:
                    content += " ⚔️ **将军**"

                # 添加下一回合状态提示（玩家是否被将军）
                next_turn_msg, next_ended = self.get_turn_start_status()
                if next_turn_msg:
                    content += next_turn_msg

                card = {
                    "config": {"wide_screen_mode": True},
                    "elements": [{"tag": "markdown", "content": content}]
                }
                return ("card", content, card), True

            # 普通消息，也检查下一回合状态
            next_turn_msg, next_ended = self.get_turn_start_status()
            return f"你：{move_text}\nAI：{ai_chinese}{next_turn_msg}", True

        # AI 无法走棋（理论上不应该走到这里，因为前面已检查）
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
        """获取对局状态"""
        if not self.game:
            return "没有进行中的对局"

        fen = self.game.get_fen()
        logger.info(f"获取棋谱状态: FEN={fen[:60]}...")
        moves_text = self.game.get_moves_text()
        current_side = self.game.get_current_side()
        side_text = "红方" if current_side == "red" else "黑方"

        return f"当前：{side_text}行棋\n回合数：{self.game.get_move_count() // 2}\n招法记录：\n{moves_text}"

    def resign(self) -> str:
        """认输"""
        if self.game:
            self.game.set_result("loss")
            self._save_game()  # 保存认输结果
            if self.engine:
                self.engine.stop()
            self.game = None
            self.engine = None
            return "你认输了！AI获胜"
        return "没有进行中的对局"

    def end(self) -> None:
        """结束会话"""
        if self.engine:
            self.engine.stop()
            self.engine = None
        self.game = None

    def list_history(self, time_range: Optional[dict] = None) -> tuple[str, dict]:
        """查看历史对局，返回 (fallback_text, card_json)"""
        recorder = GameRecorder()

        # 默认参数
        params = time_range or {"limit": 10}

        games = recorder.list_games(
            date=params.get("date"),
            start_date=params.get("start_date"),
            date_prefix=params.get("date_prefix"),
            limit=params.get("limit", 10)
        )

        if not games:
            return ("暂无历史对局记录", None)

        # 构建飞书卡片（使用 div 元素显示列表）
        elements = [
            {
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": "**历史对局列表**"
                }
            }
        ]

        for i, g in enumerate(games, 1):
            color = "红方" if g["player_color"] == "red" else "黑方"
            result_map = {"ongoing": "进行中", "win": "胜", "loss": "负", "draw": "和"}
            result = result_map.get(g["result"], g["result"])

            # 时间格式化
            start_time = g["date"][5:16].replace("T", " ")
            update_time = g.get("updated_at", g["date"])
            if update_time:
                update_time = update_time[5:16].replace("T", " ")
            else:
                update_time = start_time

            # 每行显示一个对局
            content = f"**#{i}** {start_time} → {update_time} | {color} Lv{g['level']} | {result} | {g['total_moves']}步"
            elements.append({
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": content
                }
            })

        elements.append({
            "tag": "hr"
        })
        elements.append({
            "tag": "div",
            "text": {
                "tag": "lark_md",
                "content": "发送「切换1」继续某个对局\n发送「删除1」删除某个对局"
            }
        })

        # 飞书卡片 JSON 结构
        interactive_content = {
            "config": {
                "wide_screen_mode": True
            },
            "elements": elements
        }

        # 纯文本备用
        fallback_lines = ["历史对局列表："]
        for i, g in enumerate(games, 1):
            color = "红方" if g["player_color"] == "red" else "黑方"
            result = {"ongoing": "进行中", "win": "胜", "loss": "负", "draw": "和"}.get(g["result"], g["result"])
            fallback_lines.append(f"{i}. {g['date'][:10]} {color} Lv{g['level']} {result} {g['total_moves']}步")
        fallback_text = "\n".join(fallback_lines)

        return (fallback_text, interactive_content)

    def switch_to_game(self, game_index: int) -> str:
        """切换到历史对局"""
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
        self.game_path = game_data["path"]  # 记录当前对局路径
        self.engine.set_position(self.game.get_fen())

        color_text = "红方" if self.game.meta.player_color == "red" else "黑方"
        return f"已切换到对局 #{game_index}\n执方：{color_text}\n难度：Lv{self.game.meta.level}\n回合：{self.game.get_move_count()//2 + 1}\n请走棋"

    def undo_moves(self, steps: int = 1) -> str:
        """悔棋（按回合数计算）

        与 CLI 版本语义不同：
        - CLI: 按招法步数（悔棋1 = 悔一步招法）
        - 飞书: 按回合数（悔棋1 = 悔一个完整回合，即玩家+AI各一步）

        Args:
            steps: 回悔数，默认1（悔一个完整回合）

        Returns:
            悔棋结果消息
        """
        if not self.game or not self.engine:
            return "没有进行中的对局"

        current_moves = self.game.get_move_count()
        # 每次完整回合 = 玩家招法 + AI招法 = 2步
        target_index = current_moves - steps * 2

        if target_index < 0:
            max_rounds = current_moves // 2
            return f"无法悔棋 {steps} 回，最多可悔 {max_rounds} 回"

        self.game.undo_to_move(target_index)
        self.engine.set_position(self.game.get_fen())

        remaining_rounds = self.game.get_move_count() // 2

        # 检查是否轮到AI走棋（悔棋后可能轮到AI）
        if not self.game.is_player_turn():
            # AI回合，让AI走棋
            ai_move = self.engine.get_best_move()
            if ai_move:
                current_fen = self.game.get_fen()
                self.converter.set_board_state(current_fen)
                ai_side = self.game.get_current_side()
                ai_chinese = self.converter.uci_to_chinese(ai_move, ai_side)
                self.game.make_move(ai_move, ai_chinese)
                self.engine.set_position(self.game.get_fen())

                self._save_game()  # 保存悔棋后的对局

                # 检查回合开始状态（玩家是否被将军或绝杀）
                turn_msg, ended = self.get_turn_start_status()
                if ended:
                    return f"已悔棋 {steps} 回\nAI：{ai_chinese}\n{turn_msg}"

                return f"已悔棋 {steps} 回\nAI：{ai_chinese}{turn_msg}\n请走棋"
            else:
                # AI无棋可走（被绝杀）
                self.game.set_result("win")
                self._save_game()
                return f"已悔棋 {steps} 回\nAI无棋可走，绝杀！你赢了！"

        # 玩家回合，检查回合开始状态
        turn_msg, ended = self.get_turn_start_status()
        if ended:
            return f"已悔棋 {steps} 回\n{turn_msg}"

        self._save_game()  # 保存悔棋后的对局
        return f"已悔棋 {steps} 回{turn_msg}\n当前回合：{remaining_rounds + 1}\n请走棋"


class BlindChessBot:
    """盲棋飞书机器人 - 长连接模式"""

    def __init__(self):
        self.sessions: Dict[str, GameSession] = {}
        self.app_id = FeishuConfig.APP_ID
        self.app_secret = FeishuConfig.APP_SECRET

        self.api_client = Client.builder() \
            .app_id(self.app_id) \
            .app_secret(self.app_secret) \
            .log_level(LogLevel.INFO) \
            .build()

        self.event_handler = self._create_event_handler()

        self.ws_client = WSClient(
            app_id=self.app_id,
            app_secret=self.app_secret,
            log_level=LogLevel.INFO,
            event_handler=self.event_handler,
            auto_reconnect=True,
        )

    def _create_event_handler(self) -> EventDispatcherHandler:
        """创建事件处理器"""
        handler = EventDispatcherHandler.builder(
            encrypt_key=FeishuConfig.ENCRYPT_KEY,
            verification_token=FeishuConfig.VERIFICATION_TOKEN,
        )
        handler.register_p2_im_message_receive_v1(self._on_message_receive)
        return handler.build()

    def _on_message_receive(self, event):
        """处理接收到的消息事件"""
        try:
            event_data = event.event
            message = event_data.message
            sender = event_data.sender.sender_id

            user_id = sender.open_id or sender.user_id
            chat_id = message.chat_id
            message_type = message.message_type

            if message_type != "text":
                return

            content = json.loads(message.content)
            text = content.get("text", "").strip()

            if not text:
                return

            logger.info(f"收到消息: user={user_id}, chat={chat_id}, text={text}")

            # 取消待确认的删除操作（除非是确认删除）
            if user_id in _pending_delete and text not in ["确认删除", "确认", "confirm"]:
                del _pending_delete[user_id]

            intent = parse_user_message(text)
            reply = self._process_intent(user_id, intent)

            if isinstance(reply, tuple):
                if reply[0] == "board":
                    self._send_board_image(chat_id, reply[1], reply[2])
                elif reply[0] == "card":
                    # 卡片消息（历史对局列表或将军提示）
                    self._send_card_reply(chat_id, reply[2])
            else:
                self._send_text_reply(chat_id, reply)

        except Exception as e:
            logger.error(f"处理消息失败: {e}")

    def _process_intent(self, user_id: str, intent: UserIntent) -> str:
        """处理用户意图"""
        session = self.sessions.get(user_id)
        logger.info(f"处理意图: user={user_id}, action={intent.action}, session存在={session is not None}")
        if session:
            logger.info(f"session.game存在={session.game is not None}, session.engine存在={session.engine is not None}")

        if intent.action == "new_game":
            if session:
                session.end()
            else:
                session = GameSession(user_id)
                self.sessions[user_id] = session

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

            # 处理将军提示（返回卡片消息）
            if isinstance(result, tuple) and result[0] == "card":
                return result  # 返回 ("card", content, card)

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
                self.sessions[user_id] = session
            fallback, card = session.list_history(intent.time_range)
            if card:
                return ("card", fallback, card)
            return fallback

        elif intent.action == "switch_game":
            if not session:
                session = GameSession(user_id)
                self.sessions[user_id] = session
            return session.switch_to_game(intent.game_index)

        elif intent.action == "undo":
            if not session:
                return "没有进行中的对局，发送「下棋」开始新对局"
            return session.undo_moves(intent.undo_steps or 1)

        elif intent.action == "delete_request":
            recorder = GameRecorder()
            delete_params = {
                "game_index": intent.game_index,
                "time_range": intent.time_range
            }

            # 生成确认提示信息
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
                    # 清空所有
                    total = len(recorder.list_games(limit=1000))
                    _pending_delete[user_id] = delete_params
                    return f"即将删除所有历史对局（共 {total} 个）\n发送「确认删除」执行"
                else:
                    # 按时间范围
                    games = recorder.list_games(
                        date=intent.time_range.get("date"),
                        start_date=intent.time_range.get("start_date"),
                        date_prefix=intent.time_range.get("date_prefix"),
                        limit=100
                    )
                    if not games:
                        return "该范围内没有对局"

                    # 描述范围
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

            # 执行删除
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

    def _send_text_reply(self, chat_id: str, text: str) -> None:
        """发送文本消息"""
        try:
            logger.info(f"发送文本: chat={chat_id}, text={text[:30]}...")
            content = json.dumps({"text": text})

            from lark_oapi.api.im.v1 import CreateMessageRequest, CreateMessageRequestBody

            request = CreateMessageRequest.builder() \
                .receive_id_type("chat_id") \
                .request_body(CreateMessageRequestBody.builder()
                    .receive_id(chat_id)
                    .msg_type("text")
                    .content(content)
                    .build()) \
                .build()

            response = self.api_client.im.v1.message.create(request)

            if response.success():
                logger.info("文本消息发送成功")
            else:
                logger.error(f"发送失败: code={response.code}, msg={response.msg}")

        except Exception as e:
            logger.error(f"发送文本异常: {e}")

    def _send_card_reply(self, chat_id: str, card_content: dict) -> None:
        """发送卡片消息"""
        try:
            logger.info(f"发送卡片消息: chat={chat_id}")
            content = json.dumps(card_content)

            from lark_oapi.api.im.v1 import CreateMessageRequest, CreateMessageRequestBody

            request = CreateMessageRequest.builder() \
                .receive_id_type("chat_id") \
                .request_body(CreateMessageRequestBody.builder()
                    .receive_id(chat_id)
                    .msg_type("interactive")
                    .content(content)
                    .build()) \
                .build()

            response = self.api_client.im.v1.message.create(request)

            if response.success():
                logger.info("卡片消息发送成功")
            else:
                logger.error(f"发送失败: code={response.code}, msg={response.msg}")

        except Exception as e:
            logger.error(f"发送卡片异常: {e}")

            if response.success():
                logger.info("文本消息发送成功")
            else:
                logger.error(f"发送失败: code={response.code}, msg={response.msg}")

        except Exception as e:
            logger.error(f"发送文本异常: {e}")

    def _send_board_image(self, chat_id: str, fen: str, player_color: str = 'red') -> None:
        """发送棋盘图片"""
        try:
            logger.info(f"发送棋盘图片: chat={chat_id}, player_color={player_color}, FEN={fen[:60]}...")

            # 使用统一接口生成图片，根据配置选择 svg 或 pil
            from xiangqi_engine.image import generate_board_image
            method = FeishuConfig.BOARD_IMAGE_METHOD
            logger.info(f"使用图片生成方式: {method}")
            png_file = generate_board_image(fen, player_color=player_color, method=method)
            logger.info(f"图片已生成: {png_file}")

            # 获取 tenant_access_token (直接调用HTTP API)
            import requests as requests_lib
            token_url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
            token_data = {
                "app_id": self.app_id,
                "app_secret": self.app_secret
            }
            logger.info("开始获取token...")
            token_resp = requests_lib.post(token_url, json=token_data, timeout=10)
            token_result = token_resp.json()
            logger.info(f"Token响应: code={token_result.get('code')}")

            if token_result.get('code') != 0:
                logger.error(f"获取token失败: {token_result}")
                self._send_text_reply(chat_id, f"获取token失败")
                return

            token = token_result['tenant_access_token']
            logger.info("获取token成功")

            # 使用 requests 上传图片（官方推荐方式）
            from requests_toolbelt import MultipartEncoder

            url = "https://open.feishu.cn/open-apis/im/v1/images"

            # 先读取文件内容，再创建 MultipartEncoder
            logger.info("读取图片文件...")
            with open(png_file, 'rb') as f:
                file_content = f.read()
            logger.info(f"图片大小: {len(file_content)} bytes")

            form = MultipartEncoder({
                'image_type': 'message',
                'image': ('board.png', file_content, 'image/png')
            })

            headers = {
                'Authorization': f'Bearer {token}',
                'Content-Type': form.content_type
            }

            logger.info("开始上传图片...")
            response = requests_lib.post(url, headers=headers, data=form, timeout=30)
            result = response.json()
            logger.info(f"上传响应: code={result.get('code')}")

            if result.get('code') != 0:
                logger.error(f"上传图片失败: {result}")
                self._send_text_reply(chat_id, f"棋盘图片上传失败")
                return

            image_key = result['data']['image_key']
            logger.info(f"图片上传成功: image_key={image_key}")

            # 发送图片消息
            content = json.dumps({"image_key": image_key})

            from lark_oapi.api.im.v1 import CreateMessageRequest, CreateMessageRequestBody

            logger.info("发送图片消息...")
            request = CreateMessageRequest.builder() \
                .receive_id_type("chat_id") \
                .request_body(CreateMessageRequestBody.builder()
                    .receive_id(chat_id)
                    .msg_type("image")
                    .content(content)
                    .build()) \
                .build()

            response = self.api_client.im.v1.message.create(request)

            if response.success():
                logger.info("棋盘图片发送成功")
            else:
                logger.error(f"发送图片失败: code={response.code}, msg={response.msg}")

            # 清理临时文件
            import os
            os.unlink(png_file)
            logger.info("临时文件已清理")

        except Exception as e:
            logger.error(f"发送棋盘图片异常: {e}", exc_info=True)
            self._send_text_reply(chat_id, f"棋盘图片生成失败: {str(e)}")

    def start(self) -> None:
        """启动机器人"""
        FeishuConfig.ensure_dirs()
        logger.info("启动飞书机器人（长连接模式）...")
        logger.info(f"App ID: {self.app_id}")
        self.ws_client.start()
        logger.info("机器人已启动，等待消息...")

    def stop(self) -> None:
        """停止机器人"""
        logger.info("停止机器人...")
        for session in self.sessions.values():
            session.end()
        self.sessions.clear()


def create_bot() -> BlindChessBot:
    """创建机器人实例"""
    FeishuConfig.load_from_env_file()
    if not FeishuConfig.validate():
        raise ValueError("飞书配置不完整")
    return BlindChessBot()