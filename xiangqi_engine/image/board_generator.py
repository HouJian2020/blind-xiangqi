"""棋盘图片生成"""

import subprocess
import tempfile
from pathlib import Path
from typing import Optional


def generate_board_image(
    fen: str,
    output_path: Optional[str] = None,
    theme: str = "clean_alpha",
) -> str:
    """从 FEN 生成棋盘图片"""
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