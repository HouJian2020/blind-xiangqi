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

logger = logging.getLogger(__name__)

# 待确认删除的用户列表（存储删除参数）
_pending_delete: Dict[str, dict] = {}


class GameSession:
    """用户对局会话"""

    def __init__(self, user_id: str):
        self.user_id = user_id
        self.game: Optional[Game] = None
        self.engine: Optional[PikafishEngine] = None
        self.converter: MoveConverter = MoveConverter()

    def start_game(self, color: str = "red", level: int = 5) -> str:
        """开始新对局"""
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
                return f"对局已开始！\n执方：{color_text}\n难度：Lv{level}\nAI先手：{chinese}\n请走棋"

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

        self.game.make_move(uci_move, move_text)
        self.engine.set_position(self.game.get_fen())

        ai_move = self.engine.get_best_move()
        if ai_move:
            ai_fen = self.game.get_fen()
            self.converter.set_board_state(ai_fen)
            ai_side = self.game.get_current_side()
            ai_chinese = self.converter.uci_to_chinese(ai_move, ai_side)
            self.game.make_move(ai_move, ai_chinese)
            self.engine.set_position(self.game.get_fen())
            return f"你：{move_text}\nAI：{ai_chinese}", True

        self.game.set_result("win")
        return "绝杀！你赢了！", True

    def get_status(self) -> str:
        """获取对局状态"""
        if not self.game:
            return "没有进行中的对局"

        moves_text = self.game.get_moves_text()
        current_side = self.game.get_current_side()
        side_text = "红方" if current_side == "red" else "黑方"

        return f"当前：{side_text}行棋\n回合数：{self.game.get_move_count() // 2}\n招法记录：\n{moves_text}"

    def resign(self) -> str:
        """认输"""
        if self.game:
            self.game.set_result("loss")
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

    def list_history(self, time_range: Optional[dict] = None) -> str:
        """查看历史对局"""
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
            return "暂无历史对局记录"

        lines = ["历史对局列表："]
        for i, g in enumerate(games, 1):
            color = "红方" if g["player_color"] == "red" else "黑方"
            result_map = {"ongoing": "进行中", "win": "胜", "loss": "负", "draw": "和"}
            result = result_map.get(g["result"], g["result"])
            lines.append(f"#{i} {g['date'][:10]} {color} Lv{g['level']} {result} {g['total_moves']}步")

        lines.append("\n发送「切换1」继续某个对局")
        lines.append("发送「删除1」删除某个对局")
        return "\n".join(lines)

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
        self.engine.set_position(self.game.get_fen())

        color_text = "红方" if self.game.meta.player_color == "red" else "黑方"
        return f"已切换到对局 #{game_index}\n执方：{color_text}\n难度：Lv{self.game.meta.level}\n回合：{self.game.get_move_count()//2 + 1}\n请走棋"

    def undo_moves(self, steps: int = 1) -> str:
        """悔棋"""
        if not self.game or not self.engine:
            return "没有进行中的对局"

        current_moves = self.game.get_move_count()
        # 每次完整回合 = 玩家招法 + AI招法 = 2步
        target_index = current_moves - steps * 2

        if target_index < 0:
            return f"无法悔棋 {steps} 步，最多可悔 {current_moves // 2} 步"

        self.game.undo_to_move(target_index)
        self.engine.set_position(self.game.get_fen())

        remaining_moves = self.game.get_move_count() // 2
        return f"已悔棋 {steps} 步\n当前回合：{remaining_moves + 1}\n请走棋"


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

            if isinstance(reply, tuple) and reply[0] == "board":
                self._send_board_image(chat_id, reply[1], reply[2])
            else:
                self._send_text_reply(chat_id, reply)

        except Exception as e:
            logger.error(f"处理消息失败: {e}")

    def _process_intent(self, user_id: str, intent: UserIntent) -> str:
        """处理用户意图"""
        session = self.sessions.get(user_id)

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
            return session.list_history(intent.time_range)

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

    def _send_board_image(self, chat_id: str, fen: str, player_color: str = 'red') -> None:
        """发送棋盘图片"""
        try:
            logger.info(f"发送棋盘图片: chat={chat_id}, player_color={player_color}")

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