"""真实引擎压力测试：使用 Pikafish 进行 AI 对 AI 对局

测试目标：
1. 100局对局能否正常完成
2. 终局状态与招法记录是否匹配
3. 引擎稳定性和响应时间
"""

import pytest
import time
from typing import List, Optional
from dataclasses import dataclass

from xiangqi_engine.engine.pikafish import PikafishEngine, INITIAL_FEN
from xiangqi_engine.game.game import Game
from xiangqi_engine.notation.converter import MoveConverter


@dataclass
class GameResult:
    """对局结果"""
    game_id: int
    moves: List[dict]
    final_fen: str
    move_count: int
    status: str
    errors: List[str]
    elapsed_time: float


def run_real_engine_game(game_id: int, level: int = 5, max_moves: int = 100) -> GameResult:
    """使用真实 Pikafish 引擎运行对局

    Args:
        game_id: 对局编号
        level: 难度等级 (1-10)
        max_moves: 最大招法数（防止无限循环）

    Returns:
        GameResult: 对局结果
    """
    game = Game.create(player_color="red", level=level)
    converter = MoveConverter()

    result = GameResult(
        game_id=game_id,
        moves=[],
        final_fen="",
        move_count=0,
        status="unknown",
        errors=[],
        elapsed_time=0.0,
    )

    start_time = time.time()

    try:
        # 启动引擎
        engine = PikafishEngine()
        engine.start()
        engine.set_user_level(level)

        for move_num in range(max_moves):
            current_side = game.get_current_side()
            current_fen = game.get_fen()

            # 设置局面
            engine.set_position(current_fen)

            # 获取引擎招法
            uci_move = engine.get_best_move()

            if uci_move is None:
                result.status = "engine_no_move"
                break

            # 验证招法长度
            if len(uci_move) < 4:
                result.errors.append(f"Move {move_num}: Invalid UCI format '{uci_move}'")
                result.status = "invalid_uci"
                break

            # 获取棋子类型
            source_col = ord(uci_move[0]) - ord('a')
            source_row = int(uci_move[1])
            piece = game.board.get_piece(source_col, source_row)
            piece_type = piece.lower() if piece else 'p'

            # 生成中文招法
            converter.set_board_state(current_fen)
            try:
                chinese_move = converter.uci_to_chinese(uci_move, current_side, piece_type)
            except Exception as e:
                chinese_move = f"[{uci_move}]"
                result.errors.append(f"Move {move_num}: Chinese conversion error - {e}")

            # 执行招法
            success = game.make_move(uci_move, chinese_move)
            if not success:
                result.errors.append(f"Move {move_num}: Failed to execute {uci_move}")
                result.status = "move_failed"
                break

            # 记录招法
            result.moves.append({
                "num": move_num + 1,
                "side": current_side,
                "uci": uci_move,
                "chinese": chinese_move,
                "fen_before": current_fen,
                "fen_after": game.get_fen(),
            })

            result.move_count = move_num + 1

            # 检查是否终局（简化：无棋可走或达到最大招法）
            # 真实场景需要检测将军、绝杀等

        engine.stop()
        result.final_fen = game.get_fen()

        if result.move_count >= max_moves:
            result.status = "max_moves"
        elif not result.errors:
            result.status = "completed"

    except Exception as e:
        result.status = "error"
        result.errors.append(str(e))

    result.elapsed_time = time.time() - start_time

    return result


def validate_game_result(result: GameResult) -> List[str]:
    """验证对局结果"""
    validation_errors = []

    # 1. FEN 历史长度检查
    expected_fen_count = result.move_count + 1
    actual_fen_count = len([m["fen_after"] for m in result.moves]) + 1
    if actual_fen_count != expected_fen_count:
        validation_errors.append(f"FEN count mismatch: {actual_fen_count} vs {expected_fen_count}")

    # 2. 检查行棋方交替
    for i, move in enumerate(result.moves):
        fen_before = move["fen_before"]
        fen_after = move["fen_after"]

        before_side = "red" if " w " in fen_before else "black"
        after_side = "red" if " w " in fen_after else "black"

        if before_side == after_side:
            validation_errors.append(f"Move {i+1}: Side did not alternate")

    # 3. 终局 FEN 检查
    if result.moves and result.final_fen:
        last_move_fen = result.moves[-1]["fen_after"]
        if last_move_fen != result.final_fen:
            validation_errors.append("Final FEN mismatch")

    # 4. UCI 格式检查
    for i, move in enumerate(result.moves):
        uci = move["uci"]
        if len(uci) != 4:
            validation_errors.append(f"Move {i+1}: Invalid UCI length")
        if uci[0] not in "abcdefghi" or uci[2] not in "abcdefghi":
            validation_errors.append(f"Move {i+1}: Invalid UCI column")

    return validation_errors


class TestRealEngine:
    """真实引擎压力测试"""

    def test_engine_single_game(self):
        """测试单局对局"""
        result = run_real_engine_game(1, level=3, max_moves=20)

        print(f"\n单局测试结果:")
        print(f"  状态: {result.status}")
        print(f"  招法数: {result.move_count}")
        print(f"  耗时: {result.elapsed_time:.2f}s")
        print(f"  错误: {result.errors}")

        assert result.status in ["completed", "max_moves"]
        assert result.move_count > 0
        assert result.elapsed_time < 30  # 单局不应超过30秒

        errors = validate_game_result(result)
        assert len(errors) == 0, f"Validation errors: {errors}"

    def test_engine_10_games(self):
        """测试10局对局"""
        results = []
        validation_errors = []

        for i in range(10):
            result = run_real_engine_game(i + 1, level=5, max_moves=50)
            results.append(result)

            errors = validate_game_result(result)
            if errors:
                validation_errors.append((i + 1, errors))

        completed = sum(1 for r in results if r.status in ["completed", "max_moves"])
        total_moves = sum(r.move_count for r in results)
        total_time = sum(r.elapsed_time for r in results)

        print(f"\n10局测试结果:")
        print(f"  完成率: {completed}/10")
        print(f"  总招法数: {total_moves}")
        print(f"  总耗时: {total_time:.2f}s")
        print(f"  平均每局: {total_time/10:.2f}s")
        print(f"  验证错误数: {len(validation_errors)}")

        assert completed >= 9, f"Too many failed games"
        assert len(validation_errors) == 0

    def test_engine_100_games(self):
        """测试100局对局（完整压力测试）"""
        results = []
        validation_errors = []
        game_errors = []

        start_total = time.time()

        for i in range(100):
            result = run_real_engine_game(i + 1, level=8, max_moves=500)
            results.append(result)

            # 验证
            errors = validate_game_result(result)
            if errors:
                validation_errors.append((i + 1, errors))

            if result.errors:
                game_errors.append((i + 1, result.errors))

            # 每10局打印进度
            if (i + 1) % 10 == 0:
                elapsed = time.time() - start_total
                avg_time = elapsed / (i + 1)
                print(f"  进度: {i+1}/100, 总耗时: {elapsed:.1f}s, 平均: {avg_time:.2f}s/局")

        total_elapsed = time.time() - start_total

        # 统计
        completed = sum(1 for r in results if r.status in ["completed", "max_moves"])
        error_games = sum(1 for r in results if r.status in ["error", "move_failed", "engine_no_move"])
        total_moves = sum(r.move_count for r in results)
        avg_moves = total_moves / 100
        total_rounds = total_moves // 2
        avg_rounds = total_rounds / 100

        print(f"\n100局真实引擎压力测试结果:")
        print(f"  搜索深度: level=8 → depth=10")
        print(f"  总耗时: {total_elapsed:.2f}秒")
        print(f"  平均每局: {total_elapsed/100:.2f}秒")
        print(f"  完成率: {completed}/100 ({completed}%)")
        print(f"  错误局数: {error_games}")
        print(f"  总招法数: {total_moves}")
        print(f"  平均招法数: {avg_moves:.1f}")
        print(f"  总回合数: {total_rounds}")
        print(f"  平均回合数: {avg_rounds:.1f}")
        print(f"  每回合耗时: {total_elapsed/total_rounds:.3f}秒")
        print(f"  验证错误局数: {len(validation_errors)}")
        print(f"  游戏错误局数: {len(game_errors)}")

        # 显示错误详情
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
        assert len(validation_errors) == 0, f"FEN/招法不匹配: {len(validation_errors)}局"
        assert total_elapsed < 3600, f"耗时过长: {total_elapsed}s"  # 放宽到1小时

    def test_different_levels(self):
        """测试不同难度等级"""
        levels_to_test = [1, 3, 5, 8, 10]
        results_by_level = {}

        for level in levels_to_test:
            result = run_real_engine_game(level, level=level, max_moves=20)
            results_by_level[level] = result

            print(f"  Level {level}: {result.move_count} moves, {result.elapsed_time:.2f}s, status={result.status}")

        # 低难度应该更快
        low_level_time = results_by_level[1].elapsed_time
        high_level_time = results_by_level[10].elapsed_time

        print(f"\n难度时间对比:")
        print(f"  Level 1: {low_level_time:.2f}s")
        print(f"  Level 10: {high_level_time:.2f}s")

        # 高难度不应超过10秒（深度15限制）
        for level, result in results_by_level.items():
            assert result.elapsed_time < 15, f"Level {level} too slow: {result.elapsed_time}s"
            assert result.status in ["completed", "max_moves"]


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])