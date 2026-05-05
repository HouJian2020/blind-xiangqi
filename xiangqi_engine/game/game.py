"""对局管理

管理整局对局的流程，包括开始、招法记录、结束等。
"""

import json
from datetime import datetime
from pathlib import Path
from typing import List
from dataclasses import dataclass, field, asdict

from .board import BoardState, create_initial_board, INITIAL_FEN
from .move import MoveRecord


@dataclass
class GameMeta:
    """对局元数据"""

    date: str                           # 对局开始时间
    player_color: str                   # 玩家执方 (red/black)
    level: int                          # 难度等级 (1-10)
    updated_at: str = ""                # 最后更新时间
    result: str = "ongoing"             # 结果 (ongoing/win/loss/draw)
    total_moves: int = 0                # 总招法数

@dataclass
class Game:
    """对局管理类"""

    meta: GameMeta
    board: BoardState = field(default_factory=create_initial_board)
    moves: List[MoveRecord] = field(default_factory=list)
    fen_history: List[str] = field(default_factory=list)
    _current_side: str = "red"

    def __post_init__(self):
        """初始化后记录初始 FEN"""
        if not self.fen_history:
            self.fen_history.append(self.board.get_fen())

    @classmethod
    def create(cls, player_color: str = "red", level: int = 5) -> "Game":
        """
        创建新对局

        Args:
            player_color: 玩家执方
            level: 难度等级

        Returns:
            新对局实例
        """
        now = datetime.now()
        date_str = now.strftime("%Y-%m-%dT%H:%M:%S")
        meta = GameMeta(
            date=date_str,
            updated_at=date_str,
            player_color=player_color,
            level=level,
        )

        game = cls(meta=meta)
        game._current_side = "red"  # 红方先行

        return game

    def _update_timestamp(self) -> None:
        """更新时间戳"""
        self.meta.updated_at = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")

    def get_current_side(self) -> str:
        """获取当前行棋方"""
        return self._current_side

    def make_move(self, uci_move: str, chinese_move: str) -> bool:
        """
        执行招法

        Args:
            uci_move: UCI 格式招法
            chinese_move: 中文招法描述

        Returns:
            是否成功执行
        """
        # 执行招法
        success = self.board.make_move_uci(uci_move)
        if not success:
            return False

        # 记录招法
        num = len(self.moves) // 2 + 1
        record = MoveRecord(
            num=num,
            player=self._current_side,
            chinese=chinese_move,
            uci=uci_move,
        )
        self.moves.append(record)

        # 记录 FEN 历史
        self.fen_history.append(self.board.get_fen())

        # 更新行棋方
        self._current_side = "black" if self._current_side == "red" else "red"

        # 更新元数据
        self.meta.total_moves = len(self.moves)
        self._update_timestamp()

        return True

    def get_move_count(self) -> int:
        """获取招法数"""
        return len(self.moves)

    def get_fen(self) -> str:
        """获取当前 FEN"""
        return self.board.get_fen()

    def get_fen_at_move(self, move_index: int) -> str:
        """获取指定招法后的 FEN"""
        if move_index < 0 or move_index >= len(self.fen_history):
            return self.fen_history[-1]
        return self.fen_history[move_index]

    def set_result(self, result: str) -> None:
        """设置对局结果"""
        self.meta.result = result
        self._update_timestamp()

    def is_player_turn(self) -> bool:
        """检查是否玩家回合"""
        return self._current_side == self.meta.player_color

    def undo_to_move(self, move_index: int) -> bool:
        """
        回退到指定回合

        Args:
            move_index: 目标回合索引（0=初始局面，1=第1步后，...）

        Returns:
            是否成功回退
        """
        if move_index < 0 or move_index >= len(self.fen_history):
            return False

        # 回退招法记录
        self.moves = self.moves[:move_index]

        # 回退 FEN 历史
        self.fen_history = self.fen_history[:move_index + 1]

        # 恢复棋盘状态
        target_fen = self.fen_history[-1]
        self.board = BoardState(fen=target_fen)

        # 更新当前行棋方
        if move_index % 2 == 0:
            self._current_side = "red"
        else:
            self._current_side = "black"

        # 更新元数据
        self.meta.total_moves = len(self.moves)
        self.meta.result = "ongoing"  # 重置结果为进行中
        self._update_timestamp()

        return True

    def get_move_list(self) -> list[dict]:
        """获取招法列表（用于显示）"""
        result = []
        for i, move in enumerate(self.moves):
            result.append({
                "index": i + 1,
                "player": move.player,
                "chinese": move.chinese,
                "uci": move.uci,
            })
        return result

    def to_dict(self) -> dict:
        """转换为字典（用于保存）"""
        return {
            "meta": asdict(self.meta),
            "moves": [m.to_dict() for m in self.moves],
            "fen_history": self.fen_history,
            "final_fen": self.board.get_fen(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Game":
        """从字典创建（用于加载）"""
        meta = GameMeta(**data["meta"])
        moves = [MoveRecord.from_dict(m) for m in data["moves"]]
        fen_history = data.get("fen_history", [])

        # 从最后一个 FEN 创建棋盘
        final_fen = data.get("final_fen", INITIAL_FEN)
        board = BoardState(fen=final_fen)

        game = cls(meta=meta, board=board, moves=moves, fen_history=fen_history)

        # 根据招法数确定当前行棋方
        if len(moves) % 2 == 0:
            game._current_side = "red"
        else:
            game._current_side = "black"

        return game

    def save(self, filepath: str) -> None:
        """保存对局"""
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)

    @classmethod
    def load(cls, filepath: str) -> "Game":
        """加载对局"""
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        return cls.from_dict(data)

    def get_moves_text(self) -> str:
        """获取招法记录文本"""
        lines = []
        for i, move in enumerate(self.moves):
            if move.player == "red":
                lines.append(f"{move.num}. {move.chinese}")
            else:
                # 黑方招法追加到同一行
                if i > 0 and self.moves[i-1].player == "red":
                    lines[-1] += f"  {move.chinese}"
                else:
                    lines.append(f"{move.num}. ... {move.chinese}")

        return "\n".join(lines)


def get_game_save_dir() -> Path:
    """获取对局保存目录"""
    base_dir = Path.home() / ".blind-xiangqi" / "games"
    base_dir.mkdir(parents=True, exist_ok=True)
    return base_dir


def generate_game_filename(game: Game) -> str:
    """生成对局文件名"""
    date_part = game.meta.date.split("T")[0]
    time_part = game.meta.date.split("T")[1].replace(":", "-")[:5]
    color = game.meta.player_color
    level = game.meta.level

    return f"{date_part}_{time_part}_{color}_lv{level}.xqi"