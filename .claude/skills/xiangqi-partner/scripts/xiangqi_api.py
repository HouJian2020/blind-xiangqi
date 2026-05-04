"""盲棋 API - 直接调用 xiangqi_engine 模块

作为 skill 与 xiangqi_engine 之间的薄包装层，不实现复杂逻辑。
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta

# 确保项目路径
PROJECT_PATH = Path(__file__).parent.parent.parent.parent
if str(PROJECT_PATH) not in sys.path:
    sys.path.insert(0, str(PROJECT_PATH))

# 直接导入 xiangqi_engine 模块
from xiangqi_engine.game.game import Game
from xiangqi_engine.game.validator import MoveValidator
from xiangqi_engine.storage.config import ConfigManager
from xiangqi_engine.storage.recorder import GameRecorder
from xiangqi_engine.notation.converter import MoveConverter
from xiangqi_engine.image.board_generator import generate_board_image
from xiangqi_engine.engine.pikafish import PikafishEngine
import cchess

# 导入配置
from config import (
    GAME_STORAGE_DIR,
    DEFAULT_PLAYER_COLOR,
    DEFAULT_LEVEL,
    update_config,
    get_config,
)


class XiangqiAPI:
    """盲棋 API - 薄包装层"""

    def __init__(self):
        self._recorder = GameRecorder()
        self._config = ConfigManager().load()
        # 每次操作使用独立的引擎实例
        self._engine = None
        self._converter = MoveConverter()
        self._validator = MoveValidator()

    def _ensure_engine(self, level: int):
        """确保引擎启动并设置难度"""
        if self._engine is None:
            self._engine = PikafishEngine()
            self._engine.start()
        self._engine.set_user_level(level)

    def _stop_engine(self):
        """停止引擎"""
        if self._engine:
            self._engine.stop()
            self._engine = None

    # ========================================================================
    # 游戏 ID 解析（使用 GameRecorder）
    # ========================================================================

    def _resolve_game_id(self, game_id: str) -> Path:
        """解析游戏 ID 为文件路径"""
        if game_id == "latest":
            games = self._recorder.list_games(limit=1)
            if not games:
                raise FileNotFoundError("没有历史对局")
            return Path(games[0]["path"])

        if game_id.startswith("#"):
            try:
                index = int(game_id[1:])
                games = self._recorder.list_games(limit=10)
                if index < 1 or index > len(games):
                    raise ValueError(f"序号 {index} 超出范围")
                return Path(games[index - 1]["path"])
            except ValueError:
                raise ValueError(f"无效序号: {game_id}")

        # 直接路径
        path = Path(game_id)
        if not path.exists():
            path = GAME_STORAGE_DIR / game_id
        if not path.exists():
            raise FileNotFoundError(f"对局不存在: {game_id}")
        return path

    # ========================================================================
    # API 方法
    # ========================================================================

    def create_game(self, player_color: str = None, level: int = None) -> dict:
        """创建新棋局 - 使用 Game.create()"""
        player_color = player_color or DEFAULT_PLAYER_COLOR
        level = level or DEFAULT_LEVEL

        # 使用 Game.create 创建对局
        game = Game.create(player_color=player_color, level=level)

        # 启动引擎
        self._ensure_engine(level)

        # AI 先走（玩家执黑）
        ai_first_move = None
        if player_color == "black":
            ai_first_move = self._ai_move(game)
            if ai_first_move:
                self._recorder.save_game(game)

        # 保存并获取 game_id
        save_path = self._recorder.save_game(game)
        game_id = str(save_path.relative_to(GAME_STORAGE_DIR))

        side_text = "红方" if player_color == "red" else "黑方"
        msg = f"执{side_text}，难度{level}级，开始对局"
        if ai_first_move:
            msg += f"\n🤖 AI（红方）先行：{ai_first_move}"

        return {
            "success": True,
            "game_id": game_id,
            "fen": game.get_fen(),
            "player_color": player_color,
            "level": level,
            "message": msg,
        }

    def make_move(self, game_id: str, chinese_move: str) -> dict:
        """走棋 - 使用 MoveConverter 和 Game"""
        # 加载对局
        filepath = self._resolve_game_id(game_id)
        game = Game.load(str(filepath))

        # 设置引擎难度（从对局读取）
        self._ensure_engine(game.meta.level)

        side = game.get_current_side()

        # 检查是否玩家回合
        if not game.is_player_turn():
            return {"success": False, "error": "当前是 AI 回合"}

        # 转换招法（使用 MoveConverter）
        try:
            self._converter.set_board_state(game.get_fen())
            uci = self._converter.chinese_to_uci(chinese_move, side)
        except ValueError as e:
            return {"success": False, "error": f"招法解析失败: {e}"}

        # 验证招法（使用 MoveValidator）
        is_legal, error_msg = self._validator.is_legal(game.get_fen(), uci)
        if not is_legal:
            return {"success": False, "error": f"非法招法: {error_msg}"}

        # 执行招法
        game.make_move(uci, chinese_move)
        user_checking = self._is_checking(game.get_fen())

        # 检查游戏状态
        status, ended = self._check_game_state(game.get_fen())
        if ended:
            msg = self._get_checkmate_msg(game)
            game.set_result("win" if game.get_current_side() != game.meta.player_color else "loss")
            self._recorder.save_game(game)
            self._stop_engine()
            return {
                "success": True,
                "user_move": chinese_move,
                "game_over": True,
                "result": game.meta.result,
                "message": f"🎯 用户：{chinese_move}\n{msg}"
            }

        # AI 回应
        ai_move = self._ai_move(game)
        if ai_move:
            ai_checking = self._is_checking(game.get_fen())

            # 检查用户是否被将死
            status, ended = self._check_game_state(game.get_fen())
            if ended:
                msg = self._get_checkmate_msg(game)
                game.set_result("loss" if game.get_current_side() == game.meta.player_color else "win")
                self._recorder.save_game(game)
                self._stop_engine()
                return {
                    "success": True,
                    "user_move": chinese_move,
                    "ai_move": ai_move,
                    "game_over": True,
                    "message": f"🎯 用户：{chinese_move}\n🤖 AI：{ai_move}\n{msg}"
                }

            # 正常继续
            self._recorder.save_game(game)

            user_msg = f"🎯 用户：{chinese_move}"
            if user_checking:
                user_msg += " 【将军】"
            ai_msg = f"🤖 AI：{ai_move}"
            if ai_checking:
                ai_msg += " 【被将军】"

            return {
                "success": True,
                "user_move": chinese_move,
                "ai_move": ai_move,
                "message": f"{user_msg}\n{ai_msg}"
            }
        else:
            # AI 无棋可走
            msg = self._get_checkmate_msg(game)
            game.set_result("win" if game.get_current_side() != game.meta.player_color else "loss")
            self._recorder.save_game(game)
            self._stop_engine()
            return {
                "success": True,
                "user_move": chinese_move,
                "game_over": True,
                "message": f"🎯 用户：{chinese_move}\nAI 无棋可走\n{msg}"
            }

    def _ai_move(self, game: Game) -> str:
        """AI 走棋 - 使用 PikafishEngine"""
        self._engine.set_position(game.get_fen())
        uci = self._engine.get_best_move()
        if not uci:
            return None

        side = game.get_current_side()
        self._converter.set_board_state(game.get_fen())
        chinese = self._converter.uci_to_chinese(uci, side)
        game.make_move(uci, chinese)
        return chinese

    def undo(self, game_id: str, steps: int = 1) -> dict:
        """悔棋 - 使用 Game.undo_to_move"""
        filepath = self._resolve_game_id(game_id)
        game = Game.load(str(filepath))

        # steps 是回合数，转换为招法数
        target_move = game.get_move_count() - steps * 2
        if target_move < 0:
            return {"success": False, "error": f"无法回退 {steps} 回合"}

        if game.undo_to_move(target_move):
            self._recorder.save_game(game)

            # 回退后如果是 AI 回合，重新走棋
            ai_move = None
            if not game.is_player_turn():
                self._ensure_engine(game.meta.level)
                ai_move = self._ai_move(game)
                if ai_move:
                    self._recorder.save_game(game)

            msg = f"已回退到第 {target_move // 2} 回合"
            if ai_move:
                msg += f"\n🤖 AI 重新走棋：{ai_move}"

            return {"success": True, "message": msg}
        else:
            return {"success": False, "error": "回退失败"}

    def get_status(self, game_id: str) -> dict:
        """获取状态 - 使用 Game 方法"""
        filepath = self._resolve_game_id(game_id)
        game = Game.load(str(filepath))

        side = game.get_current_side()
        side_text = "红方" if side == "red" else "黑方"
        being_checked = self._is_being_checked(game.get_fen())
        check_msg = "【被将军】" if being_checked else ""

        return {
            "success": True,
            "fen": game.get_fen(),
            "move_count": game.get_move_count(),
            "current_side": side,
            "is_player_turn": game.is_player_turn(),
            "moves_text": game.get_moves_text(),
            "being_checked": being_checked,
            "game_result": game.meta.result,
            "message": f"📍 当前：{side_text}行棋 {check_msg}\n回合数：{game.get_move_count() // 2}\n招法记录：\n{game.get_moves_text()}"
        }

    def list_games(self, limit: int = 10, days: int = 0) -> dict:
        """列出对局 - 使用 GameRecorder"""
        # 计算日期
        date_str = None
        if days == 0:
            date_str = datetime.now().strftime("%Y-%m-%d")
        elif days > 0:
            # 最近 days 天，不过滤具体日期
            date_str = None

        games = self._recorder.list_games(limit=limit, date=date_str)

        if not games:
            msg = "没有历史对局" if days < 0 else (f"今天没有对局" if days == 0 else f"最近{days}天没有对局")
            return {"success": True, "games": [], "message": msg}

        # 格式化输出
        lines = ["序号 | 对局ID | 执方 | 难度 | 结果 | 步数"]
        lines.append("-" * 50)
        for i, g in enumerate(games, 1):
            game_id = Path(g["path"]).relative_to(GAME_STORAGE_DIR)
            side_text = "红" if g["player_color"] == "red" else "黑"
            result_text = {"ongoing": "进行中", "win": "胜", "loss": "负", "draw": "和"}.get(g["result"], g["result"])
            moves = g["total_moves"] // 2
            lines.append(f"#{i}  | {game_id} | {side_text} | Lv{g['level']} | {result_text} | {moves}回合")

        return {"success": True, "games": games, "message": "\n".join(lines)}

    def get_board_image(self, game_id: str = None, output_path: str = None) -> dict:
        """生成棋盘图片 - 使用 generate_board_image"""
        if game_id:
            filepath = self._resolve_game_id(game_id)
            game = Game.load(str(filepath))
            fen = game.get_fen()
        else:
            fen = "rnbakabnr/9/1c5c1/p1p1p1p1p/9/9/P1P1P1P1P/1C5C1/9/RNBAKABNR w - - 0 1"

        try:
            theme = self._config.image_theme if self._config else "default"
            path = generate_board_image(fen, output_path, theme)
            return {
                "success": True,
                "path": str(path),
                "message": f"棋盘图片已生成: {path}"
            }
        except Exception as e:
            return {"success": False, "error": f"生成失败: {e}"}

    def resign(self, game_id: str) -> dict:
        """认输"""
        filepath = self._resolve_game_id(game_id)
        game = Game.load(str(filepath))

        side = game.get_current_side()
        side_name = "红方" if side == "red" else "黑方"
        game.set_result("loss")
        self._recorder.save_game(game)
        self._stop_engine()

        winner = "黑方" if side == "red" else "红方"
        winner_role = "(AI)" if side == game.meta.player_color else "(玩家)"

        return {"success": True, "message": f"{side_name}认输！{winner}{winner_role}获胜"}

    def load_game(self, game_id: str, move_index: int = None) -> dict:
        """加载对局 - 使用 Game.load"""
        filepath = self._resolve_game_id(game_id)
        game = Game.load(str(filepath))

        # 回退到指定回合
        if move_index is not None:
            target_move = move_index * 2
            if target_move < 0 or target_move > game.get_move_count():
                return {"success": False, "error": f"无效回合: {move_index}"}
            game.undo_to_move(target_move)

        self._ensure_engine(game.meta.level)

        # AI 回合时先走
        ai_move = None
        if not game.is_player_turn():
            ai_move = self._ai_move(game)
            if ai_move:
                self._recorder.save_game(game)

        side_text = "红方" if game.meta.player_color == "red" else "黑方"
        msg = f"加载对局: {filepath}\n执{side_text}，难度{game.meta.level}级\n当前第 {game.meta.total_moves // 2} 回合\n招法记录：\n{game.get_moves_text()}"
        if ai_move:
            msg += f"\n🤖 AI 先走：{ai_move}"

        return {"success": True, "fen": game.get_fen(), "message": msg}

    def get_config_info(self, key: str = None) -> dict:
        """获取配置"""
        return get_config(key)

    def update_defaults(self, key: str, value) -> dict:
        """更新配置"""
        return update_config(key, value)

    # ========================================================================
    # 辅助方法（直接使用 cchess）
    # ========================================================================

    def _is_checking(self, fen: str) -> bool:
        """是否将军对手"""
        board = cchess.ChessBoard(fen)
        return board.is_checking()

    def _is_being_checked(self, fen: str) -> bool:
        """是否被将军"""
        board = cchess.ChessBoard(fen)
        current_color = board.get_move_color()
        opponent_color = cchess.BLACK if current_color == cchess.RED else cchess.RED
        board.set_move_color(opponent_color)
        return board.is_checking()

    def _check_game_state(self, fen: str) -> tuple:
        """检查游戏状态"""
        board = cchess.ChessBoard(fen)
        if board.no_moves():
            if self._is_being_checked(fen):
                return "将死", True
            else:
                return "困毙", True
        return "", False

    def _get_checkmate_msg(self, game: Game) -> str:
        """绝杀消息"""
        import random
        losing_side = game.get_current_side()
        if losing_side != game.meta.player_color:
            return random.choice(["绝杀吴姐！", "一招毙命！", "绝杀！小瘪三，给我擦皮鞋", "绝杀！窝要烟牌！"])
        else:
            return "哦哦，你噶了"

    def close(self):
        """清理资源"""
        self._stop_engine()
        if self._validator:
            self._validator.close()


def get_api() -> XiangqiAPI:
    """获取 API 实例"""
    return XiangqiAPI()