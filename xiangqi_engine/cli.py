"""盲棋 CLI 命令接口"""

import argparse
import sys
import logging
import cchess

from .game.game import Game
from .game.validator import MoveValidator
from .storage.config import ConfigManager
from .storage.recorder import GameRecorder
from .notation.converter import MoveConverter
from .image.board_generator import generate_board_image
from .engine.pikafish import PikafishEngine

# 配置日志：DEBUG写入文件，INFO及以上显示在终端
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/tmp/blind-xiangqi.log'),
    ]
)
# 终端只显示WARNING及以上
console_handler = logging.StreamHandler(sys.stderr)
console_handler.setLevel(logging.WARNING)
console_handler.setFormatter(logging.Formatter('%(levelname)s: %(message)s'))
logging.getLogger().addHandler(console_handler)

logger = logging.getLogger(__name__)


def _is_being_checked(fen: str) -> bool:
    """
    检查当前行棋方是否被将军

    使用 cchess 的 is_checking() 方法（需切换到对手视角）
    """
    board = cchess.ChessBoard(fen)
    current_color = board.get_move_color()
    opponent_color = cchess.BLACK if current_color == cchess.RED else cchess.RED

    # 切换到对手视角，检查对手是否在将军当前方
    board.set_move_color(opponent_color)
    return board.is_checking()


def _is_checking_opponent(fen: str) -> bool:
    """
    检查当前行棋方是否在将军对手

    直接使用 cchess 的 is_checking() 方法
    """
    board = cchess.ChessBoard(fen)
    return board.is_checking()


def _check_game_state(fen: str) -> tuple[str, bool]:
    """
    检查游戏状态

    Returns:
        (状态描述, 是否结束)
        - ("", False) - 正常继续
        - ("将死", True) - 被将死
        - ("困毙", True) - 无棋可走但未被将军
    """
    board = cchess.ChessBoard(fen)

    # 使用 cchess 的 no_moves() 判断是否有合法招法
    if board.no_moves():
        if _is_being_checked(fen):
            return "将死", True
        else:
            return "困毙", True

    return "", False


def _get_checkmate_message(game: Game, losing_side: str) -> str:
    """获取绝杀提示消息"""
    import random

    if losing_side != game.meta.player_color:
        # AI 无棋可走 → 玩家获胜
        return random.choice(["绝杀吴姐！", "一招毙命！"])
    else:
        # 玩家无棋可走 → AI获胜
        return "哦哦，你噶了"


def _game_loop(
    game: Game,
    engine: PikafishEngine,
    converter: MoveConverter,
    validator: MoveValidator,
    recorder: GameRecorder,
) -> None:
    """
    公共游戏循环逻辑

    处理玩家和 AI 的交互循环，包括特殊命令和招法处理。
    """
    config = ConfigManager().load()

    while True:
        try:
            side = game.get_current_side()
            side_name = "红方" if side == "red" else "黑方"

            # AI 回合
            if not game.is_player_turn():
                print(f"\n[{side_name}回合] AI 思考中...")
                ai_move = _ai_move(game, engine, converter)
                if ai_move:
                    check_status = "【将军】" if _is_checking_opponent(game.get_fen()) else ""
                    print(f"AI: {ai_move}{check_status}\nFEN: {game.get_fen()}")
                    recorder.save_game(game)

                    status, ended = _check_game_state(game.get_fen())
                    if ended:
                        losing_side = game.get_current_side()
                        msg = _get_checkmate_message(game, losing_side)
                        game.set_result("loss" if losing_side == game.meta.player_color else "win")
                        print(msg)
                        _save_and_exit(game, recorder, engine, validator)
                        return
                    continue
                else:
                    losing_side = side
                    msg = _get_checkmate_message(game, losing_side)
                    game.set_result("win" if side == game.meta.player_color else "loss")
                    print(msg)
                    _save_and_exit(game, recorder, engine, validator)
                    return

            # 玩家回合 - 检查是否已被将死/困毙
            status, ended = _check_game_state(game.get_fen())
            if ended:
                losing_side = side
                msg = _get_checkmate_message(game, losing_side)
                game.set_result("loss")
                print(f"\n[{side_name}回合] {msg}")
                _save_and_exit(game, recorder, engine, validator)
                return

            # 玩家回合开始时，检查是否被将军
            check_status = "【将军】" if _is_being_checked(game.get_fen()) else ""
            print(f"\n[{side_name}回合]{check_status} FEN: {game.get_fen()}")

            # 读取用户输入
            user_input = ""
            try:
                raw_bytes = sys.stdin.buffer.readline()
                if raw_bytes:
                    user_input = raw_bytes.decode('utf-8', errors='replace').strip()
            except Exception as e:
                logger.warning(f"输入读取异常: {e}")

            if not user_input:
                continue

            logger.debug(f"用户输入: 「{user_input}」")

            # 特殊命令处理
            cmd = user_input.lower()

            if cmd in ("quit", "exit"):
                _save_and_exit(game, recorder, engine, validator)
                return

            if cmd in ("认输", "resign"):
                winner = _get_winner(game, side)
                game.set_result("loss")
                print(f"{side_name}认输！{winner}")
                _save_and_exit(game, recorder, engine, validator)
                return

            if cmd == "help":
                print("命令: <招法> | back N(悔棋) | 认输(resign) | history | show | quit")
                continue

            if cmd == "history":
                print(game.get_moves_text())
                print(f"\n当前第 {game.get_move_count()} 步，可回退到 0-{game.get_move_count()} 步")
                continue

            if cmd.startswith("back") or cmd.startswith("undo"):
                _handle_undo(game, engine, converter, recorder, user_input)
                continue

            if cmd == "show":
                try:
                    path = generate_board_image(game.get_fen(), theme=config.image_theme)
                    print(f"棋盘图片: {path}")
                except Exception as e:
                    print(f"生成失败: {e}")
                continue

            # 处理招法
            try:
                logger.debug(f"开始处理招法: {user_input}")
                converter.set_board_state(game.get_fen())
                uci = converter.chinese_to_uci(user_input, side)
                logger.debug(f"转换UCI: {uci}")

                is_legal, error = validator.is_legal(game.get_fen(), uci)
                logger.debug(f"验证结果: 合法={is_legal}, 错误={error}")
                if not is_legal:
                    print(f"非法招法: {error}")
                    continue

                logger.debug(f"执行招法: {uci}")
                game.make_move(uci, user_input)
                check_status = "【将军】" if _is_checking_opponent(game.get_fen()) else ""
                print(f"玩家: {user_input}{check_status}\nFEN: {game.get_fen()}")
                recorder.save_game(game)

                # 检查 AI 是否被将死/困毙
                status, ended = _check_game_state(game.get_fen())
                if ended:
                    losing_side = game.get_current_side()
                    msg = _get_checkmate_message(game, losing_side)
                    game.set_result("win" if losing_side == game.meta.player_color else "loss")
                    print(msg)
                    _save_and_exit(game, recorder, engine, validator)
                    return

                # 立即触发 AI
                if not game.is_player_turn():
                    side = game.get_current_side()
                    side_name = "红方" if side == "red" else "黑方"
                    print(f"\n[{side_name}回合] AI 思考中...")
                    ai_move = _ai_move(game, engine, converter)
                    if ai_move:
                        check_status = "【将军】" if _is_checking_opponent(game.get_fen()) else ""
                        print(f"AI: {ai_move}{check_status}\nFEN: {game.get_fen()}")
                        recorder.save_game(game)

                        status, ended = _check_game_state(game.get_fen())
                        if ended:
                            losing_side = game.get_current_side()
                            msg = _get_checkmate_message(game, losing_side)
                            game.set_result("loss" if losing_side == game.meta.player_color else "win")
                            print(msg)
                            _save_and_exit(game, recorder, engine, validator)
                            return
                    else:
                        losing_side = side
                        msg = _get_checkmate_message(game, losing_side)
                        game.set_result("win" if side == game.meta.player_color else "loss")
                        print(msg)
                        _save_and_exit(game, recorder, engine, validator)
                        return

            except ValueError as e:
                print(f"无效招法: {e}")

        except KeyboardInterrupt:
            print("\n对局中断")
            _save_and_exit(game, recorder, engine, validator)
            return


def _handle_undo(
    game: Game,
    engine: PikafishEngine,
    converter: MoveConverter,
    recorder: GameRecorder,
    user_input: str,
) -> None:
    """处理悔棋命令"""
    try:
        parts = user_input.lower().split()
        steps = int(parts[1]) if len(parts) > 1 else 1

        current_moves = game.get_move_count()
        target_move = current_moves - steps

        if target_move < 0:
            print(f"无法回退 {steps} 步，当前只有 {current_moves} 步")
            return

        if game.undo_to_move(target_move):
            print(f"已回退到第 {target_move} 步")
            print(game.get_moves_text())
            print(f"\nFEN: {game.get_fen()}")
            recorder.save_game(game)

            # 如果回退后是 AI 回合，需要重新走棋
            if not game.is_player_turn():
                side = game.get_current_side()
                side_name = "红方" if side == "red" else "黑方"
                print(f"\n[{side_name}回合] AI 思考中...")
                ai_move = _ai_move(game, engine, converter)
                if ai_move:
                    check_status = "【将军】" if _is_checking_opponent(game.get_fen()) else ""
                    print(f"AI: {ai_move}{check_status}\nFEN: {game.get_fen()}")
                    recorder.save_game(game)
        else:
            print("回退失败")
    except ValueError:
        print("用法: back N (回退N步) 或 back (回退1步)")


def _get_winner(game: Game, losing_side: str) -> str:
    """获取胜利方名称"""
    if losing_side == "red":
        winner = "黑方"
    else:
        winner = "红方"

    # 判断是玩家还是 AI
    if losing_side == game.meta.player_color:
        return f"{winner}(AI) 获胜"
    else:
        return f"{winner}(玩家) 获胜"


def create_parser() -> argparse.ArgumentParser:
    """创建命令行解析器"""
    parser = argparse.ArgumentParser(
        prog="blind-xiangqi",
        description="盲棋游戏 CLI - 自然语言交互的中国象棋",
    )

    subparsers = parser.add_subparsers(dest="command", help="子命令")

    # play 命令
    play_parser = subparsers.add_parser("play", help="开始新对局")
    play_parser.add_argument("-c", "--color", choices=["red", "black"], default="red")
    play_parser.add_argument("-l", "--level", type=int, choices=range(1, 11), default=5)

    # history 命令
    history_parser = subparsers.add_parser("history", help="查看历史对局")
    history_parser.add_argument("--date", type=str)
    history_parser.add_argument("--limit", type=int, default=10)

    # resume 命令
    resume_parser = subparsers.add_parser("resume", help="继续历史对局")
    resume_parser.add_argument("game_file", type=str, help="对局文件路径")
    resume_parser.add_argument("-m", "--move", type=int, help="从指定回合继续（默认从最后一步）")

    # show 命令
    show_parser = subparsers.add_parser("show", help="显示棋盘图片")
    show_parser.add_argument("game_file", type=str, nargs="?")
    show_parser.add_argument("-m", "--move", type=int)
    show_parser.add_argument("-o", "--output", type=str)

    # config 命令
    config_parser = subparsers.add_parser("config", help="配置默认设置")
    config_parser.add_argument("--default-level", type=int, choices=range(1, 11))
    config_parser.add_argument("--default-color", choices=["red", "black"])

    return parser


def cmd_play(args: argparse.Namespace) -> None:
    """执行 play 命令"""
    game = Game.create(player_color=args.color, level=args.level)

    print(f"执{args.color}方，难度{args.level}，开始对局\n")

    # 棋子名称提示
    if args.color == "black":
        print("提示：黑方棋子为「卒、将、士、象、马、车、炮」")
    print("输入中文招法（如「炮二平五」），或输入 help 查看帮助")
    print("特殊命令: 认输(resign) | quit | show\n")

    # 启动引擎
    engine = PikafishEngine()
    engine.start()
    engine.set_user_level(args.level)

    converter = MoveConverter()
    recorder = GameRecorder()
    validator = MoveValidator()

    # AI 先走（玩家执黑方时）
    if args.color == "black":
        print("[红方回合] AI 思考中...")
        ai_move = _ai_move(game, engine, converter)
        if ai_move:
            check_status = "【将军】" if _is_being_checked(game.get_fen()) else ""
            print(f"AI: {ai_move}{check_status}\nFEN: {game.get_fen()}\n")
            recorder.save_game(game)
        else:
            # AI 无法走棋，红方输棋
            status, _ = _check_game_state(game.get_fen())
            winner = _get_winner(game, "red")
            game.set_result("loss" if game.meta.player_color == "black" else "win")
            print(f"红方{status}！{winner}")
            _save_and_exit(game, recorder, engine, validator)
            return

    # 运行游戏循环
    _game_loop(game, engine, converter, validator, recorder)


def _ai_move(game: Game, engine: PikafishEngine, converter: MoveConverter) -> str:
    """AI 走棋"""
    logger.debug(f"_ai_move 开始, FEN: {game.get_fen()}")

    try:
        engine.set_position(game.get_fen())
        logger.debug("引擎位置已设置")

        uci = engine.get_best_move()
        logger.debug(f"引擎返回招法: {uci}")

        if not uci:
            logger.warning("引擎返回空招法")
            return None

        side = game.get_current_side()

        logger.debug(f"转换招法: uci={uci}, side={side}")
        converter.set_board_state(game.get_fen())
        chinese = converter.uci_to_chinese(uci, side)
        logger.debug(f"中文招法: {chinese}")

        game.make_move(uci, chinese)
        logger.debug(f"_ai_move 完成: {chinese}")
        return chinese

    except Exception as e:
        logger.error(f"_ai_move 异常: {e}", exc_info=True)
        return None


def _save_and_exit(game: Game, recorder: GameRecorder, engine: PikafishEngine, validator: MoveValidator):
    """保存并退出"""
    path = recorder.save_game(game)
    print(f"对局已保存: {path}")
    engine.stop()
    validator.close()


def cmd_resume(args: argparse.Namespace) -> None:
    """执行 resume 命令 - 继续历史对局"""
    from pathlib import Path

    recorder = GameRecorder()

    # 处理文件路径
    filepath = Path(args.game_file)
    if not filepath.exists():
        filepath = Path.home() / ".blind-xiangqi" / "games" / args.game_file
    if not filepath.exists():
        print(f"对局文件不存在: {args.game_file}")
        return

    # 加载对局
    try:
        game = recorder.load_game(str(filepath))
    except Exception as e:
        print(f"加载对局失败: {e}")
        return

    # 如果指定了回合，先回退
    if args.move is not None:
        target_move = args.move
        if target_move < 0 or target_move > game.get_move_count():
            print(f"无效回合: {target_move}，有效范围 0-{game.get_move_count()}")
            return
        if game.undo_to_move(target_move):
            print(f"已回退到第 {target_move} 步")
        else:
            print("回退失败")
            return

    # 显示对局信息
    print(f"继续对局: {filepath}")
    print(f"执{game.meta.player_color}方，难度{game.meta.level}")
    print(f"当前第 {game.meta.total_moves} 步")
    print(game.get_moves_text())
    print(f"\n当前局面 FEN: {game.get_fen()}\n")

    # 启动引擎
    engine = PikafishEngine()
    engine.start()
    engine.set_user_level(game.meta.level)

    converter = MoveConverter()
    validator = MoveValidator()

    # 如果是 AI 回合，先让 AI 走棋
    if not game.is_player_turn():
        side = game.get_current_side()
        side_name = "红方" if side == "red" else "黑方"
        print(f"[{side_name}回合] AI 思考中...")
        ai_move = _ai_move(game, engine, converter)
        if ai_move:
            check_status = "【将军】" if _is_checking_opponent(game.get_fen()) else ""
            print(f"AI: {ai_move}{check_status}\nFEN: {game.get_fen()}\n")
            recorder.save_game(game)

            status, ended = _check_game_state(game.get_fen())
            if ended:
                losing_side = game.get_current_side()
                msg = _get_checkmate_message(game, losing_side)
                game.set_result("loss" if losing_side == game.meta.player_color else "win")
                print(msg)
                _save_and_exit(game, recorder, engine, validator)
                return
        else:
            losing_side = side
            msg = _get_checkmate_message(game, losing_side)
            game.set_result("win" if side == game.meta.player_color else "loss")
            print(msg)
            _save_and_exit(game, recorder, engine, validator)
            return

    print("特殊命令: 认输(resign) | quit | show\n")

    # 运行游戏循环
    _game_loop(game, engine, converter, validator, recorder)


def cmd_history(args: argparse.Namespace) -> None:
    """执行 history 命令"""
    recorder = GameRecorder()
    games = recorder.list_games(date=args.date, limit=args.limit)

    if not games:
        print("没有找到对局记录")
        return

    print("对局历史:")
    for i, g in enumerate(games, 1):
        print(f"  {i}. {g['file']} | {g['player_color']} | Lv{g['level']} | {g['result']}")


def cmd_show(args: argparse.Namespace) -> None:
    """执行 show 命令"""
    config = ConfigManager().load()
    fen = "rnbakabnr/9/1c5c1/p1p1p1p1p/9/9/P1P1P1P1P/1C5C1/9/RNBAKABNR w - - 0 1"

    if args.game_file:
        recorder = GameRecorder()
        game = recorder.load_game(args.game_file)
        idx = args.move if args.move else len(game.fen_history) - 1
        fen = game.get_fen_at_move(idx)

    try:
        path = generate_board_image(fen, args.output, config.image_theme)
        print(f"棋盘图片: {path}")
    except Exception as e:
        print(f"生成失败: {e}")


def cmd_config(args: argparse.Namespace) -> None:
    """执行 config 命令"""
    manager = ConfigManager()

    if args.default_level or args.default_color:
        cfg = manager.load()
        if args.default_level:
            cfg.default_level = args.default_level
        if args.default_color:
            cfg.default_color = args.default_color
        manager.save(cfg)
        print("配置已更新")
    else:
        cfg = manager.load()
        print(f"默认难度: {cfg.default_level}")
        print(f"默认执方: {cfg.default_color}")
        print(f"引擎路径: {cfg.engine_path}")


def main() -> None:
    """CLI 主入口"""
    parser = create_parser()
    args = parser.parse_args()

    if args.command == "play":
        cmd_play(args)
    elif args.command == "resume":
        cmd_resume(args)
    elif args.command == "history":
        cmd_history(args)
    elif args.command == "show":
        cmd_show(args)
    elif args.command == "config":
        cmd_config(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()