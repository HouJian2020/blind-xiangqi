"""招法合法性验证器

使用 cchess 库验证招法是否合法：
1. 基本规则检查（棋子移动规则）
2. 被将军检查（不能走导致自己被将军的招法）
"""

from typing import Optional
import cchess
from cchess.common import iccs2pos


class MoveValidator:
    """招法合法性验证器"""

    def __init__(self):
        self._board: Optional[cchess.ChessBoard] = None

    def set_position(self, fen: str) -> None:
        """设置当前局面"""
        self._board = cchess.ChessBoard(fen)

    def is_legal(self, fen: str, uci_move: str) -> tuple[bool, str]:
        """
        验证招法是否合法

        使用 cchess 的两个方法：
        - is_valid_iccs_move(): 检查基本规则
        - is_checked_move(): 检查走完后是否被将军

        Args:
            fen: 当前局面 FEN
            uci_move: UCI/ICCS 格式招法，如 "h2e2"

        Returns:
            (is_legal, error_message)
        """
        # 设置棋盘状态
        self.set_position(fen)

        if self._board is None:
            return False, "棋盘状态未设置"

        # 检查招法格式
        if not uci_move or len(uci_move) < 4:
            return False, f"无效招法格式: {uci_move}"

        # 使用 cchess 验证
        try:
            # 1. 检查基本规则（棋子移动规则）
            if not self._board.is_valid_iccs_move(uci_move):
                return False, f"非法招法"

            # 2. 检查是否会导致被将军
            pos_from, pos_to = iccs2pos(uci_move)
            if self._board.is_checked_move(pos_from, pos_to):
                return False, "此招法会导致被将军"

            return True, ""

        except ValueError:
            return False, f"招法格式错误: {uci_move}"
        except Exception as e:
            return False, f"验证失败: {type(e).__name__}"

    def get_legal_moves(self, fen: str) -> list[str]:
        """
        获取所有合法招法

        Args:
            fen: 当前局面 FEN

        Returns:
            UCI/ICCS 格式招法列表
        """
        self.set_position(fen)

        if self._board is None:
            return []

        try:
            # create_moves 返回生成器，每个元素是 (from_pos, to_pos) 元组
            moves_gen = self._board.create_moves()
            # 转换为 ICCS 格式
            legal_moves = []
            for move_tuple in moves_gen:
                # move_tuple 是 ((col_from, row_from), (col_to, row_to))
                pos_from, pos_to = move_tuple
                iccs = self._pos_to_iccs(pos_from, pos_to)
                legal_moves.append(iccs)
            return legal_moves
        except Exception as e:
            return []

    def _pos_to_iccs(self, pos_from: tuple, pos_to: tuple) -> str:
        """将位置元组转换为 ICCS 格式"""
        col_from, row_from = pos_from
        col_to, row_to = pos_to
        # ICCS 格式: a-i 对应列 0-8, 0-9 对应行
        return f"{chr(ord('a') + col_from)}{row_from}{chr(ord('a') + col_to)}{row_to}"

    def close(self):
        """清理资源"""
        self._board = None


def validate_move(fen: str, uci_move: str) -> tuple[bool, str]:
    """
    快捷验证函数

    Args:
        fen: 当前局面 FEN
        uci_move: UCI 格式招法

    Returns:
        (is_legal, error_message)
    """
    validator = MoveValidator()
    result = validator.is_legal(fen, uci_move)
    validator.close()
    return result