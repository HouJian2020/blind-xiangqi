"""棋盘状态管理

管理中国象棋棋盘状态，包括局面更新、合法性检查等。
"""

import copy
from typing import Optional, List, Dict, Tuple
from dataclasses import dataclass, field


# 初始局面 FEN
INITIAL_FEN = "rnbakabnr/9/1c5c1/p1p1p1p1p/9/9/P1P1P1P1P/1C5C1/9/RNBAKABNR w - - 0 1"


@dataclass
class BoardState:
    """棋盘状态"""

    fen: str = INITIAL_FEN
    turn: str = "red"  # 当前行棋方
    move_count: int = 0
    half_move_count: int = 0  # 半回合数（用于 FEN）

    # 棋盘状态缓存
    _pieces: Dict[Tuple[int, int], str] = field(default_factory=dict)

    def __post_init__(self):
        """初始化后解析 FEN"""
        self._parse_fen()

    def _parse_fen(self) -> None:
        """解析 FEN 字符串"""
        self._pieces.clear()

        parts = self.fen.split()
        if len(parts) < 1:
            return

        board_part = parts[0]
        rows = board_part.split("/")

        # FEN 行顺序：从黑方底线(第9行)到红方底线(第0行)
        for row_idx, row_str in enumerate(rows):
            actual_row = 9 - row_idx
            col_idx = 0

            for char in row_str:
                if char.isdigit():
                    col_idx += int(char)
                else:
                    self._pieces[(col_idx, actual_row)] = char
                    col_idx += 1

        # 解析行棋方
        if len(parts) >= 2:
            self.turn = "red" if parts[1] == "w" else "black"

    def get_piece(self, col: int, row: int) -> Optional[str]:
        """获取指定位置的棋子"""
        return self._pieces.get((col, row))

    def get_piece_type(self, col: int, row: int) -> Optional[str]:
        """获取棋子类型（小写字母）"""
        piece = self.get_piece(col, row)
        if piece:
            return piece.lower()
        return None

    def get_piece_side(self, col: int, row: int) -> Optional[str]:
        """获取棋子所属方"""
        piece = self.get_piece(col, row)
        if piece:
            return "red" if piece.isupper() else "black"
        return None

    def make_move(self, source_col: int, source_row: int, target_col: int, target_row: int) -> bool:
        """
        执行招法

        Args:
            source_col, source_row: 起点坐标
            target_col, target_row: 终点坐标

        Returns:
            是否成功执行
        """
        piece = self.get_piece(source_col, source_row)
        if piece is None:
            return False

        # 移除起点棋子
        del self._pieces[(source_col, source_row)]

        # 在终点放置棋子（可能吃子）
        self._pieces[(target_col, target_row)] = piece

        # 先更新行棋方，再更新 FEN
        self.turn = "black" if self.turn == "red" else "red"
        self.half_move_count += 1

        # 更新 FEN
        self._update_fen()

        return True

    def make_move_uci(self, uci_move: str) -> bool:
        """
        使用 UCI 格式执行招法

        Args:
            uci_move: UCI 格式招法，如 "b2e5"

        Returns:
            是否成功执行
        """
        source_col = ord(uci_move[0]) - ord("a")
        source_row = int(uci_move[1])
        target_col = ord(uci_move[2]) - ord("a")
        target_row = int(uci_move[3])

        return self.make_move(source_col, source_row, target_col, target_row)

    def _update_fen(self) -> None:
        """从棋盘状态更新 FEN"""
        rows = []
        for row in range(9, -1, -1):  # 从第9行到第0行
            row_str = ""
            empty_count = 0

            for col in range(9):
                piece = self.get_piece(col, row)
                if piece:
                    if empty_count > 0:
                        row_str += str(empty_count)
                        empty_count = 0
                    row_str += piece
                else:
                    empty_count += 1

            if empty_count > 0:
                row_str += str(empty_count)

            rows.append(row_str)

        board_part = "/".join(rows)
        turn_char = "w" if self.turn == "red" else "b"
        self.fen = f"{board_part} {turn_char} - - {self.half_move_count} {self.move_count + 1}"

    def get_fen(self) -> str:
        """获取当前 FEN"""
        return self.fen

    def copy(self) -> "BoardState":
        """复制棋盘状态"""
        new_state = BoardState()
        new_state.fen = self.fen
        new_state.turn = self.turn
        new_state.move_count = self.move_count
        new_state.half_move_count = self.half_move_count
        new_state._pieces = copy.deepcopy(self._pieces)
        return new_state

    def is_valid_position(self, col: int, row: int) -> bool:
        """检查位置是否有效"""
        return 0 <= col <= 8 and 0 <= row <= 9

    def get_all_pieces(self, side: str) -> List[Tuple[int, int, str]]:
        """获取指定方的所有棋子"""
        pieces = []
        for (col, row), piece in self._pieces.items():
            if side == "red" and piece.isupper():
                pieces.append((col, row, piece))
            elif side == "black" and piece.islower():
                pieces.append((col, row, piece))
        return pieces


def create_initial_board() -> BoardState:
    """创建初始棋盘"""
    return BoardState(fen=INITIAL_FEN)