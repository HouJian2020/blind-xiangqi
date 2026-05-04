"""招法转换器 - 基于 cchess 库"""

from typing import Dict, Tuple, Optional, List
import cchess

# 中文数字到阿拉伯数字映射
CHINESE_TO_DIGIT = {
    "一": "1", "二": "2", "三": "3", "四": "4", "五": "5",
    "六": "6", "七": "7", "八": "8", "九": "9",
}

# 阿拉伯数字到中文数字映射（包括全角数字）
DIGIT_TO_CHINESE = {
    "1": "一", "2": "二", "3": "三", "4": "四", "5": "五",
    "6": "六", "7": "七", "8": "八", "9": "九",
    # 全角数字（cchess 输出）
    "１": "一", "２": "二", "３": "三", "４": "四", "５": "五",
    "６": "六", "７": "七", "８": "八", "９": "九",
}


class MoveConverter:
    """招法转换器（使用 cchess 库）"""

    def __init__(self):
        self._board: Optional[cchess.ChessBoard] = None

    def set_board_state(self, fen: str) -> None:
        """从 FEN 设置棋盘状态"""
        self._board = cchess.ChessBoard(fen)

    def chinese_to_uci(
        self,
        chinese_move: str,
        side: str,
        board_state: Optional[Dict[Tuple[int, int], str]] = None
    ) -> str:
        """
        将中文招法转换为 UCI/ICCS 格式

        Args:
            chinese_move: 中文招法，如 "炮二平五" 或 "炮2平5"
            side: 当前行棋方 ("red" 或 "black")
            board_state: 可选的棋盘状态（已弃用，现在使用 FEN）

        Returns:
            UCI/ICCS 格式招法，如 "h2e2"

        Raises:
            ValueError: 招法解析失败
        """
        if self._board is None:
            raise ValueError("棋盘状态未设置，请先调用 set_board_state()")

        # 保存当前 FEN（因为 cchess 异常后会污染 board 状态）
        fen = self._board.to_full_fen()

        def try_parse(move_text: str) -> Optional[str]:
            """尝试解析招法，返回 ICCS 或 None（使用新鲜 board）"""
            try:
                fresh_board = cchess.ChessBoard(fen)
                move = fresh_board.move_text(move_text)
                if move:
                    return move.to_iccs()
            except Exception:
                pass
            return None

        # 先尝试原始输入
        result = try_parse(chinese_move)
        if result:
            return result

        # 尝试转换格式后解析（中文数字 → 阿拉伯数字）
        converted = chinese_move
        for cn, digit in CHINESE_TO_DIGIT.items():
            converted = converted.replace(cn, digit)
        result = try_parse(converted)
        if result:
            return result

        # 尝试反向转换（阿拉伯数字 → 中文数字）
        converted = chinese_move
        for digit, cn in DIGIT_TO_CHINESE.items():
            converted = converted.replace(digit, cn)
        result = try_parse(converted)
        if result:
            return result

        raise ValueError(f"无法解析招法: 「{chinese_move}」")

    def uci_to_chinese(self, uci_move: str, side: str, piece_type: Optional[str] = None) -> str:
        """
        将 UCI/ICCS 招法转换为中文

        Args:
            uci_move: UCI/ICCS 格式招法，如 "h2e2"
            side: 当前行棋方 ("red" 或 "black")
            piece_type: 可选的棋子类型（已弃用，cchess 自动识别）

        Returns:
            中文招法，如 "炮二平五"

        Raises:
            ValueError: 招法转换失败
        """
        if self._board is None:
            raise ValueError("棋盘状态未设置，请先调用 set_board_state()")

        if not uci_move or len(uci_move) < 4:
            raise ValueError(f"无效 UCI: {uci_move}")

        try:
            move = self._board.move_iccs(uci_move)
            if move is None:
                raise ValueError(f"无法解析 UCI: {uci_move}")
            chinese = move.to_text()

            # 黑方输出时将阿拉伯数字转换为中文数字（统一显示）
            if side == "black":
                for digit, cn in DIGIT_TO_CHINESE.items():
                    chinese = chinese.replace(digit, cn)

            return chinese
        except Exception as e:
            raise ValueError(f"UCI 转换失败: {uci_move} - {type(e).__name__}: {e}")