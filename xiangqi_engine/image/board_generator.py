"""棋盘图片生成 - 使用 xiangqi-setup CLI 生成 SVG（原始稳定版本）"""

import subprocess
import tempfile
from pathlib import Path
from typing import Optional


def generate_board_image_svg(
    fen: str,
    output_path: Optional[str] = None,
    theme: str = "clean_alpha",
) -> str:
    """从 FEN 生成棋盘 SVG 图片（xiangqi-setup 方案）

    Args:
        fen: 棋局 FEN 字符串
        output_path: 输出路径，None 则使用临时文件
        theme: 主题名称

    Returns:
        生成的 SVG 图片路径
    """
    # 创建临时 FEN 文件
    with tempfile.NamedTemporaryFile(mode="w", suffix=".fen", delete=False) as f:
        f.write(fen)
        fen_file = f.name

    # 创建输出路径
    if output_path:
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
    else:
        output = Path(tempfile.mktemp(suffix=".svg"))

    try:
        # xiangqi-setup INPUT_FILE OUTPUT_FILE
        cmd = [
            "xiangqi-setup",
            fen_file,
            str(output),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode != 0:
            raise RuntimeError(f"xiangqi-setup failed: {result.stderr}")
        return str(output)
    finally:
        Path(fen_file).unlink(missing_ok=True)