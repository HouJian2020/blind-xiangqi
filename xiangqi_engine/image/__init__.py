"""棋盘图片生成模块

提供两种生成方式：
- svg: 使用 xiangqi-setup CLI（稳定版本）
- pil: 使用 PIL 直接绘制（新增版本，支持 player_color 参数）
"""

from typing import Optional

# 默认使用 SVG 方案
DEFAULT_METHOD = "svg"


def generate_board_image(
    fen: str,
    player_color: str = "red",
    output_path: Optional[str] = None,
    method: str = DEFAULT_METHOD,
) -> str:
    """生成棋盘图片

    Args:
        fen: 棋局 FEN 字符串
        player_color: 玩家执方（仅 PIL 方案支持）
        output_path: 输出路径
        method: 生成方式，'svg' 或 'pil'

    Returns:
        图片路径（SVG 或 PNG）
    """
    if method == "pil":
        from .board_generator_pil import generate_board_image_pil
        return generate_board_image_pil(fen, player_color, output_path)
    else:
        from .board_generator import generate_board_image_svg
        return generate_board_image_svg(fen, output_path)