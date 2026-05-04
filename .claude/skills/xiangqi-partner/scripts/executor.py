"""盲棋命令行执行器

提供简洁的命令行接口，供 SKILL.md 调用。

用法:
    python executor.py create --color red --level 3
    python executor.py move "炮二平五" --game-id latest
    python executor.py undo --game-id latest --steps 1
    python executor.py status --game-id latest
    python executor.py list --limit 10
    python executor.py board --game-id latest
    python executor.py config --key DEFAULT_LEVEL --value 5
    python executor.py resign --game-id latest
    python executor.py load --game-id #1 --move-index 10
"""

import sys
import argparse
import json
from pathlib import Path

# 确保路径
SCRIPT_DIR = Path(__file__).parent
PROJECT_PATH = "/mnt/z/PythonWork/blind-xiangqi"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))
if PROJECT_PATH not in sys.path:
    sys.path.insert(0, PROJECT_PATH)

from xiangqi_api import get_api


def main():
    parser = argparse.ArgumentParser(description="盲棋对弈命令行工具")
    subparsers = parser.add_subparsers(dest="command", help="命令")

    # ========== create ==========
    create_parser = subparsers.add_parser("create", help="创建新棋局")
    create_parser.add_argument("--color", "-c", choices=["red", "black"],
                               help="执方 (red/black)")
    create_parser.add_argument("--level", "-l", type=int,
                               help="难度等级 (1-10)")

    # ========== move ==========
    move_parser = subparsers.add_parser("move", help="走棋")
    move_parser.add_argument("move", help="中文招法，如 '炮二平五'")
    move_parser.add_argument("--game-id", "-g", default="latest",
                             help="对局ID (latest/#N/路径)")

    # ========== undo ==========
    undo_parser = subparsers.add_parser("undo", help="悔棋")
    undo_parser.add_argument("--game-id", "-g", default="latest",
                             help="对局ID")
    undo_parser.add_argument("--steps", "-s", type=int, default=1,
                             help="回退回合数")

    # ========== status ==========
    status_parser = subparsers.add_parser("status", help="查看对局状态")
    status_parser.add_argument("--game-id", "-g", default="latest",
                               help="对局ID")

    # ========== list ==========
    list_parser = subparsers.add_parser("list", help="列出历史对局")
    list_parser.add_argument("--limit", "-n", type=int, default=10,
                             help="显示数量")
    list_parser.add_argument("--days", "-d", type=int, default=0,
                             help="查看最近N天的对局，默认0表示今天")

    # ========== board ==========
    board_parser = subparsers.add_parser("board", help="生成棋盘图片")
    board_parser.add_argument("--game-id", "-g", default="latest",
                              help="对局ID")
    board_parser.add_argument("--output", "-o", help="输出路径")

    # ========== config ==========
    config_parser = subparsers.add_parser("config", help="配置管理")
    config_parser.add_argument("--key", "-k", help="配置键名")
    config_parser.add_argument("--value", "-v", help="配置值")
    config_parser.add_argument("--show", "-s", action="store_true",
                               help="显示所有配置")

    # ========== resign ==========
    resign_parser = subparsers.add_parser("resign", help="认输")
    resign_parser.add_argument("--game-id", "-g", default="latest",
                               help="对局ID")

    # ========== load ==========
    load_parser = subparsers.add_parser("load", help="加载对局")
    load_parser.add_argument("--game-id", "-g", default="latest",
                             help="对局ID")
    load_parser.add_argument("--move-index", "-m", type=int,
                             help="从指定回合开始")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    api = get_api()

    # 执行命令
    result = dispatch_command(api, args)

    # 输出结果
    if result.get("success"):
        # 特殊处理各命令的输出格式
        if args.command == "create":
            print(result.get("message", "创建成功"))
            print(f"GAME_ID:{result['game_id']}")
        elif args.command == "board":
            print(result.get("message", "生成成功"))
            print(f"BOARD_PATH:{result['path']}")
        elif args.command == "config":
            if args.show or (args.key is None and args.value is None):
                # 显示所有配置
                config = result.get("config", {})
                print("当前配置:")
                for k, v in config.items():
                    print(f"  {k} = {v}")
            elif args.key and args.value:
                print(result.get("message", "配置已更新"))
                print(f"CONFIG_UPDATED:{args.key}={args.value}")
            elif args.key:
                print(f"{args.key} = {result.get('value')}")
            else:
                print("操作成功")
        elif args.command == "list":
            print(result.get("message", "没有对局"))
        else:
            print(result.get("message", "操作成功"))
    else:
        print(f"错误: {result.get('error', '未知错误')}")


def dispatch_command(api, args):
    """分发命令到对应的 API 方法"""
    cmd = args.command

    if cmd == "create":
        return api.create_game(
            player_color=args.color,
            level=args.level
        )

    elif cmd == "move":
        return api.make_move(
            game_id=args.game_id,
            chinese_move=args.move
        )

    elif cmd == "undo":
        return api.undo(
            game_id=args.game_id,
            steps=args.steps
        )

    elif cmd == "status":
        return api.get_status(
            game_id=args.game_id
        )

    elif cmd == "list":
        return api.list_games(
            limit=args.limit,
            days=args.days
        )

    elif cmd == "board":
        return api.get_board_image(
            game_id=args.game_id,
            output_path=args.output
        )

    elif cmd == "config":
        if args.show or (args.key is None and args.value is None):
            return api.get_config_info()
        elif args.key and args.value:
            # 类型转换
            value = args.value
            if args.key == "DEFAULT_LEVEL":
                value = int(value)
            return api.update_defaults(args.key, value)
        elif args.key:
            return api.get_config_info(args.key)
        else:
            return {"success": False, "error": "请指定 --key 和 --value"}

    elif cmd == "resign":
        return api.resign(
            game_id=args.game_id
        )

    elif cmd == "load":
        return api.load_game(
            game_id=args.game_id,
            move_index=args.move_index
        )

    else:
        return {"success": False, "error": f"未知命令: {cmd}"}


if __name__ == "__main__":
    main()