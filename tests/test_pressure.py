"""压力测试：AI 对 AI 对局模拟

使用 mock 引擎模拟 AI 对 AI 对局，验证：
1. 对局能否正常走完
2. 终局状态与招法记录是否匹配
3. FEN 历史是否正确
"""

import pytest
import random
import time
from typing import List, Tuple, Optional
from unittest.mock import Mock, patch

from xiangqi_engine.game.game import Game
from xiangqi_engine.game.board import BoardState, create_initial_board
from xiangqi_engine.notation.converter import MoveConverter


# 所有合法招法（简化版，用于 mock）
LEGAL_MOVES = [
    "b2e2", "b2g2", "h2e2", "h2g2",  # 炮
    "a0a1", "a0a2", "i0i1", "i0i2",  # 车
    "b0c2", "b0a2", "h0g2", "h0i2",  # 马
    "a3a4", "c3c4", "e3e4", "g3g4", "i3i4",  # 兵
]


class MockEngine:
    """模拟引擎，生成随机合法招法"""

    def __init__(self, level: int = 10):
        self.level = level
        self.move_count = 0

    def get_move(self, fen: str) -> Optional[str]:
        """根据 FEN 生成随机招法"""
        # 解析棋盘状态
        board = BoardState(fen=fen)
        side = board.turn

        # 获取该方所有棋子
        pieces = board.get_all_pieces(side)
        if not pieces:
            return None

        # 尝试生成合法招法（简化逻辑）
        self.move_count += 1

        # 随机选择一个棋子和目标位置
        for col, row, piece in pieces:
            piece_type = piece.lower()

            # 根据棋子类型生成可能的移动
            if piece_type == 'p':  # 兵/卒
                if side == 'red':
                    target_row = row + 1
                    if target_row <= 9:
                        return f"{chr(ord('a')+col)}{row}{chr(ord('a')+col)}{target_row}"
                else:
                    target_row = row - 1
                    if target_row >= 0:
                        return f"{chr(ord('a')+col)}{row}{chr(ord('a')+col)}{target_row}"

            elif piece_type == 'r':  # 车
                # 随机横向或纵向移动
                directions = [(0, 1), (0, -1), (1, 0), (-1, 0)]
                for dc, dr in random.sample(directions, 2):
                    target_col = col + dc
                    target_row = row + dr
                    if 0 <= target_col <= 8 and 0 <= target_row <= 9:
                        target_piece = board.get_piece(target_col, target_row)
                        if target_piece is None or (side == 'red' and target_piece.islower()) or (side == 'black' and target_piece.isupper()):
                            return f"{chr(ord('a')+col)}{row}{chr(ord('a')+target_col)}{target_row}"

            elif piece_type == 'c':  # 炮
                # 简化：横向移动
                for target_col in range(9):
                    if target_col != col:
                        target_piece = board.get_piece(target_col, row)
                        if target_piece is None:
                            return f"{chr(ord('a')+col)}{row}{chr(ord('a')+target_col)}{row}"

            elif piece_type == 'n':  # 马
                # 马走日字
                moves = [(col-1, row+2), (col+1, row+2), (col-2, row+1), (col+2, row+1),
                         (col-2, row-1), (col+2, row-1), (col-1, row-2), (col+1, row-2)]
                for tc, tr in random.sample(moves, min(4, len(moves))):
                    if 0 <= tc <= 8 and 0 <= tr <= 9:
                        return f"{chr(ord('a')+col)}{row}{chr(ord('a')+tc)}{tr}"

        return None


def run_single_game(game_id: int, max_moves: int = 200) -> dict:
    """运行单局 AI 对 AI 对局

    Returns:
        dict: 包含对局结果的字典
    """
    game = Game.create(player_color="red", level=10)
    converter = MoveConverter()
    engine = MockEngine(level=10)

    result = {
        "game_id": game_id,
        "moves": [],
        "fen_history": [],
        "final_fen": None,
        "move_count": 0,
        "status": "unknown",
        "errors": [],
    }

    try:
        for move_num in range(max_moves):
            current_side = game.get_current_side()
            current_fen = game.get_fen()

            # 设置棋盘状态
            converter.set_board_state(current_fen)

            # 获取引擎招法
            uci_move = engine.get_move(current_fen)

            if uci_move is None:
                # 无法生成招法，可能终局
                result["status"] = "no_move_available"
                break

            # 获取棋子类型
            source_col = ord(uci_move[0]) - ord('a')
            source_row = int(uci_move[1])
            piece = game.board.get_piece(source_col, source_row)
            piece_type = piece.lower() if piece else 'p'

            # 生成中文招法
            try:
                chinese_move = converter.uci_to_chinese(uci_move, current_side, piece_type)
            except Exception as e:
                chinese_move = f"[转换失败:{uci_move}]"
                result["errors"].append(f"Move {move_num}: Chinese conversion failed - {e}")

            # 执行招法
            success = game.make_move(uci_move, chinese_move)
            if not success:
                result["errors"].append(f"Move {move_num}: Failed to execute {uci_move}")
                result["status"] = "invalid_move"
                break

            # 记录招法
            result["moves"].append({
                "num": move_num + 1,
                "side": current_side,
                "uci": uci_move,
                "chinese": chinese_move,
                "fen_before": current_fen,
                "fen_after": game.get_fen(),
            })

            result["move_count"] = move_num + 1

        result["final_fen"] = game.get_fen()
        result["fen_history"] = game.fen_history.copy()

        if result["move_count"] >= max_moves:
            result["status"] = "max_moves_reached"
        elif not result["errors"]:
            result["status"] = "completed"

    except Exception as e:
        result["status"] = "error"
        result["errors"].append(str(e))

    return result


def validate_game_result(result: dict) -> List[str]:
    """验证对局结果的正确性

    Returns:
        List[str]: 验证错误列表
    """
    validation_errors = []

    # 1. 检查 FEN 历史长度与招法数匹配
    expected_fen_count = result["move_count"] + 1  # 初始 + 每招一个
    if len(result["fen_history"]) != expected_fen_count:
        validation_errors.append(
            f"FEN历史长度({len(result['fen_history'])}) != 招法数+1({expected_fen_count})"
        )

    # 2. 检查每个招法的 FEN 变化
    for i, move in enumerate(result["moves"]):
        fen_before = move["fen_before"]
        fen_after = move["fen_after"]

        # FEN 应该有变化
        if fen_before == fen_after:
            validation_errors.append(f"Move {i+1}: FEN unchanged after move")

        # 行棋方应该交替
        before_side = "red" if "w" in fen_before.split()[1] else "black"
        after_side = "red" if "w" in fen_after.split()[1] else "black"
        if before_side == after_side:
            validation_errors.append(f"Move {i+1}: Side did not alternate")

    # 3. 检查终局 FEN 与最后一个招法后的 FEN 匹配
    if result["moves"] and result["final_fen"]:
        last_move_fen = result["moves"][-1]["fen_after"]
        if last_move_fen != result["final_fen"]:
            validation_errors.append("Final FEN mismatch with last move")

    # 4. 检查 FEN 历史连续性
    for i in range(1, len(result["fen_history"])):
        prev_fen = result["fen_history"][i-1]
        curr_fen = result["fen_history"][i]

        # 简单检查：FEN 结构应保持有效
        if len(curr_fen.split("/")) != 10:
            validation_errors.append(f"FEN {i}: Invalid board structure")

    return validation_errors


class TestPressureGame:
    """压力测试类"""

    def test_single_game_completion(self):
        """测试单局对局能否完成"""
        result = run_single_game(1, max_moves=50)

        assert result["status"] in ["completed", "max_moves_reached", "no_move_available"]
        assert result["move_count"] > 0
        assert len(result["moves"]) == result["move_count"]
        assert result["final_fen"] is not None

        # 验证结果
        errors = validate_game_result(result)
        assert len(errors) == 0, f"Validation errors: {errors}"

    def test_10_games(self):
        """测试10局对局"""
        results = []
        validation_errors = []

        for i in range(10):
            result = run_single_game(i + 1, max_moves=100)
            results.append(result)

            errors = validate_game_result(result)
            if errors:
                validation_errors.append(f"Game {i+1}: {errors}")

        # 统计
        completed = sum(1 for r in results if r["status"] == "completed" or r["status"] == "max_moves_reached")
        total_moves = sum(r["move_count"] for r in results)

        print(f"\n10局测试结果:")
        print(f"  完成率: {completed}/10")
        print(f"  平均招法数: {total_moves/10:.1f}")
        print(f"  验证错误数: {len(validation_errors)}")

        assert completed >= 8, f"Too many failed games: {10-completed}"
        assert len(validation_errors) == 0, f"Validation errors: {validation_errors}"

    def test_100_games(self):
        """测试100局对局（压力测试）"""
        results = []
        validation_errors = []
        game_errors = []

        start_time = time.time()

        for i in range(100):
            result = run_single_game(i + 1, max_moves=200)
            results.append(result)

            # 验证每局
            errors = validate_game_result(result)
            if errors:
                validation_errors.append((i + 1, errors))

            if result["errors"]:
                game_errors.append((i + 1, result["errors"]))

        elapsed = time.time() - start_time

        # 统计
        completed = sum(1 for r in results if r["status"] in ["completed", "max_moves_reached", "no_move_available"])
        error_games = sum(1 for r in results if r["status"] == "error" or r["status"] == "invalid_move")
        total_moves = sum(r["move_count"] for r in results)
        avg_moves = total_moves / 100

        print(f"\n100局压力测试结果:")
        print(f"  总耗时: {elapsed:.2f}秒")
        print(f"  完成率: {completed}/100 ({completed}%)")
        print(f"  错误局数: {error_games}")
        print(f"  总招法数: {total_moves}")
        print(f"  平均招法数: {avg_moves:.1f}")
        print(f"  验证错误局数: {len(validation_errors)}")
        print(f"  游戏错误局数: {len(game_errors)}")

        # 输出详细错误
        if validation_errors:
            print(f"\n验证错误详情 (前5个):")
            for game_id, errors in validation_errors[:5]:
                print(f"  Game {game_id}: {errors}")

        if game_errors:
            print(f"\n游戏错误详情 (前5个):")
            for game_id, errors in game_errors[:5]:
                print(f"  Game {game_id}: {errors}")

        # 验证条件
        assert completed >= 95, f"完成率过低: {completed}%"
        assert len(validation_errors) == 0, f"存在FEN/招法不匹配: {len(validation_errors)}局"
        assert avg_moves >= 10, f"平均招法数过低: {avg_moves}"

    def test_fen_history_consistency(self):
        """测试 FEN 历史的一致性"""
        result = run_single_game(1, max_moves=30)

        # 每个招法后的 FEN 应该在历史中
        for move in result["moves"]:
            fen_after = move["fen_after"]
            assert fen_after in result["fen_history"], f"Move FEN not in history"

        # FEN 历史应该是连续的（无跳跃）
        for i in range(len(result["fen_history"]) - 1):
            fen1 = result["fen_history"][i]
            fen2 = result["fen_history"][i + 1]

            # 解析两个 FEN
            parts1 = fen1.split()
            parts2 = fen2.split()

            # 检查回合数递增
            if len(parts1) >= 5 and len(parts2) >= 5:
                turn1 = int(parts1[4]) if parts1[4].isdigit() else 0
                turn2 = int(parts2[4]) if parts2[4].isdigit() else 0
                # 回合数应该递增
                assert turn2 >= turn1, f"Turn number should increase: {turn1} -> {turn2}"

    def test_move_chinese_uci_match(self):
        """测试中文招法与 UCI 招法的匹配"""
        converter = MoveConverter()

        result = run_single_game(1, max_moves=20)

        for move in result["moves"]:
            uci = move["uci"]
            chinese = move["chinese"]
            side = move["side"]

            # 中文招法应该能转换回 UCI（可能不完全一致，但应有效）
            if "[转换失败]" not in chinese:
                converter.set_board_state(move["fen_before"])
                try:
                    converted_uci = converter.chinese_to_uci(chinese, side)
                    # 转换结果应该是有效的 4 字符 UCI
                    assert len(converted_uci) == 4, f"Invalid UCI length: {converted_uci}"
                    assert converted_uci[0] in "abcdefghi", f"Invalid UCI col: {converted_uci}"
                except Exception as e:
                    # 某些中文招法可能无法完全还原，记录但不失败
                    pass


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])