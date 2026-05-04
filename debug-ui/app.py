"""盲棋 Debug UI

简易 Gradio 前端，实时显示 CLI 对局的棋盘和历史招法。
"""

import gradio as gr
import json
from pathlib import Path
from datetime import datetime

# 导入 xiangqi_engine
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from xiangqi_engine.image.board_generator import generate_board_image

# 对局文件目录
GAME_DIR = Path.home() / ".blind-xiangqi" / "games"
INITIAL_FEN = "rnbakabnr/9/1c5c1/p1p1p1p1p/9/9/P1P1P1P1P/1C5C1/9/RNBAKABNR w - - 0 1"

# 缓存上次的结果，避免重复生成
_last_result = None
_last_file = None
_last_mtime = None


def load_latest_game():
    """加载最新对局文件"""
    global _last_result, _last_file, _last_mtime

    if not GAME_DIR.exists():
        return [{"role": "assistant", "content": "提示：暂无对局记录，请先在 CLI 中开始对局"}], None

    # 找到最新的对局文件
    files = sorted(
        GAME_DIR.glob("**/*.xqi"),
        key=lambda f: f.stat().st_mtime,
        reverse=True
    )

    if not files:
        return [{"role": "assistant", "content": "提示：暂无对局记录"}], None

    # 检查是否有变化（避免重复处理）
    latest_file = files[0]
    current_mtime = latest_file.stat().st_mtime

    if _last_file == latest_file and _last_mtime == current_mtime and _last_result:
        return _last_result

    # 加载文件
    try:
        with open(latest_file, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        return [{"role": "assistant", "content": f"读取失败: {e}"}], None

    # 构建招法历史
    moves = data.get("moves", [])
    history = []

    player_color = data.get("meta", {}).get("player_color", "unknown")
    level = data.get("meta", {}).get("level", "?")
    start_time = data.get("meta", {}).get("date", "?")

    history.append({"role": "assistant", "content": "=== 对局信息 ==="})
    history.append({"role": "assistant", "content": f"执方: {player_color} | 难度: Lv{level} | 时间: {start_time}"})
    history.append({"role": "assistant", "content": f"文件: {latest_file.name}"})
    history.append({"role": "assistant", "content": ""})

    for move in moves:
        num = move.get("num", "?")
        player = move.get("player", "?")
        chinese = move.get("chinese", "?")
        uci = move.get("uci", "?")

        side_name = "红" if player == "red" else "黑"
        history.append({"role": "assistant", "content": f"第{num}回合 {side_name}方: {chinese} ({uci})"})

    total_moves = len(moves)
    history.append({"role": "assistant", "content": ""})
    history.append({"role": "assistant", "content": f"共 {total_moves} 招法"})

    # 生成棋盘图片
    fen_history = data.get("fen_history", [])
    current_fen = fen_history[-1] if fen_history else INITIAL_FEN

    try:
        board_image = generate_board_image(current_fen)
    except Exception as e:
        board_image = None
        history.append({"role": "assistant", "content": f"棋盘生成失败: {e}"})

    # 缓存结果
    _last_result = (history, board_image)
    _last_file = latest_file
    _last_mtime = current_mtime

    return history, board_image


def create_ui():
    """创建 Gradio UI"""

    with gr.Blocks(title="盲棋 Debug UI") as demo:
        gr.Markdown("""
        ## 盲棋对局实时监控

        CLI 对局时，此处自动同步显示棋盘和招法记录。
        每2秒自动刷新。
        """)

        with gr.Row():
            with gr.Column(scale=1):
                chatbot = gr.Chatbot(
                    label="招法记录",
                    height=500,
                    show_label=True,
                )

            with gr.Column(scale=1):
                board = gr.Image(
                    label="当前棋盘",
                    type="filepath",
                    height=500,
                )

        with gr.Row():
            refresh_btn = gr.Button("手动刷新", variant="primary")
            status_text = gr.Textbox(label="状态", value="等待对局...", interactive=False)

        # 刷新按钮
        def refresh():
            history, image = load_latest_game()
            status = f"更新时间: {datetime.now().strftime('%H:%M:%S')}"
            return history, image, status

        refresh_btn.click(refresh, outputs=[chatbot, board, status_text])

        # 定时自动刷新（每3秒）
        timer = gr.Timer(3, active=True)
        timer.tick(refresh, outputs=[chatbot, board, status_text])

    return demo


if __name__ == "__main__":
    demo = create_ui()
    print("=" * 50)
    print("盲棋 Debug UI 启动")
    print("=" * 50)
    print()
    print("使用方法:")
    print("  1. 在终端运行: blind-xiangqi play -c black -l 5")
    print("  2. 此页面自动同步显示棋局")
    print()
    print("局域网访问: http://192.168.1.97:7860")
    print()
    print("启动 Gradio...")
    demo.launch(server_name="0.0.0.0", server_port=7860, share=False)