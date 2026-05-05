"""棋盘图片生成 - 使用 PIL 直接绘制"""

from PIL import Image, ImageDraw, ImageFont
import tempfile
from pathlib import Path
from typing import Optional

# 棋子映射：小写=黑方，大写=红方
PIECE_CHARS = {
    'r': '车', 'n': '马', 'b': '象', 'a': '士', 'k': '将', 'c': '炮', 'p': '卒',
    'R': '车', 'N': '马', 'B': '相', 'A': '仕', 'K': '帅', 'C': '炮', 'P': '兵',
}

RED_PIECES = {'R', 'N', 'B', 'A', 'K', 'C', 'P'}

# 棋盘尺寸
BOARD_WIDTH = 450
BOARD_HEIGHT = 500
CELL_SIZE = 50
MARGIN = 25


def get_font(size: int) -> ImageFont.FreeTypeFont:
    """获取字体"""
    font_paths = [
        "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for path in font_paths:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def draw_cannon_soldier_marker(draw: ImageDraw.ImageDraw, x: int, y: int, offset: int = 4, length: int = 8):
    """绘制炮和兵卒位置的特殊标记（四个L组成的花纹）

    类似于传统象棋棋盘的标记，四个角各有一个L形短线
    """
    # 左上角 L
    draw.line([(x - offset - length, y - offset), (x - offset, y - offset)], fill='black', width=1)
    draw.line([(x - offset, y - offset), (x - offset, y - offset - length)], fill='black', width=1)

    # 右上角 L
    draw.line([(x + offset, y - offset), (x + offset + length, y - offset)], fill='black', width=1)
    draw.line([(x + offset, y - offset), (x + offset, y - offset - length)], fill='black', width=1)

    # 左下角 L
    draw.line([(x - offset - length, y + offset), (x - offset, y + offset)], fill='black', width=1)
    draw.line([(x - offset, y + offset), (x - offset, y + offset + length)], fill='black', width=1)

    # 右下角 L
    draw.line([(x + offset, y + offset), (x + offset + length, y + offset)], fill='black', width=1)
    draw.line([(x + offset, y + offset), (x + offset, y + offset + length)], fill='black', width=1)


def generate_board_image_pil(
    fen: str,
    player_color: str = 'red',
    output_path: Optional[str] = None,
) -> str:
    """从 FEN 生成棋盘 PNG 图片（PIL 方案）

    Args:
        fen: 棋局 FEN 字符串
        player_color: 玩家执方，'red' 或 'black'。
                      'red' 时棋盘黑上红下（标准方向）
                      'black' 时棋盘红上黑下（翻转显示）
        output_path: 输出路径，None 则使用临时文件

    Returns:
        生成的 PNG 图片路径
    """
    # 创建棋盘图片 (米色背景)
    img = Image.new('RGB', (BOARD_WIDTH, BOARD_HEIGHT), '#f5deb3')
    draw = ImageDraw.Draw(img)

    # 绘制棋盘线条
    for i in range(10):
        y = MARGIN + i * CELL_SIZE
        draw.line([(MARGIN, y), (MARGIN + 8 * CELL_SIZE, y)], fill='black', width=1)

    for i in range(9):
        x = MARGIN + i * CELL_SIZE
        if i == 0 or i == 8:  # 边线
            draw.line([(x, MARGIN), (x, MARGIN + 9 * CELL_SIZE)], fill='black', width=1)
        else:  # 中间竖线，分上下半部分
            draw.line([(x, MARGIN), (x, MARGIN + 4 * CELL_SIZE)], fill='black', width=1)
            draw.line([(x, MARGIN + 5 * CELL_SIZE), (x, MARGIN + 9 * CELL_SIZE)], fill='black', width=1)

    # 绘制九宫斜线
    # 上方九宫（第0-2行，第3-5列）
    palace_x3 = MARGIN + 3 * CELL_SIZE
    palace_x5 = MARGIN + 5 * CELL_SIZE
    palace_y0 = MARGIN + 0 * CELL_SIZE
    palace_y2 = MARGIN + 2 * CELL_SIZE
    draw.line([(palace_x3, palace_y0), (palace_x5, palace_y2)], fill='black', width=1)
    draw.line([(palace_x5, palace_y0), (palace_x3, palace_y2)], fill='black', width=1)

    # 下方九宫（第7-9行，第3-5列）
    palace_y7 = MARGIN + 7 * CELL_SIZE
    palace_y9 = MARGIN + 9 * CELL_SIZE
    draw.line([(palace_x3, palace_y7), (palace_x5, palace_y9)], fill='black', width=1)
    draw.line([(palace_x5, palace_y7), (palace_x3, palace_y9)], fill='black', width=1)

    # 绘制炮和兵卒位置的特殊标记（四个L花纹）
    # 炮位：第2行和第7行，第1列和第7列
    cannon_y2 = MARGIN + 2 * CELL_SIZE
    cannon_y7 = MARGIN + 7 * CELL_SIZE
    cannon_col1 = MARGIN + 1 * CELL_SIZE
    cannon_col7 = MARGIN + 7 * CELL_SIZE
    draw_cannon_soldier_marker(draw, cannon_col1, cannon_y2)
    draw_cannon_soldier_marker(draw, cannon_col7, cannon_y2)
    draw_cannon_soldier_marker(draw, cannon_col1, cannon_y7)
    draw_cannon_soldier_marker(draw, cannon_col7, cannon_y7)

    # 兵卒位：第3行和第6行，第0,2,4,6,8列
    soldier_y3 = MARGIN + 3 * CELL_SIZE
    soldier_y6 = MARGIN + 6 * CELL_SIZE
    for col in [0, 2, 4, 6, 8]:
        x_pos = MARGIN + col * CELL_SIZE
        draw_cannon_soldier_marker(draw, x_pos, soldier_y3)
        draw_cannon_soldier_marker(draw, x_pos, soldier_y6)

    # 添加河界文字（根据玩家颜色调整）
    font = get_font(16)
    # 河界位置：左半边中心在第2列，右半边中心在第6列
    left_center = MARGIN + 2 * CELL_SIZE   # 第2列中心
    right_center = MARGIN + 6 * CELL_SIZE  # 第6列中心
    river_y = MARGIN + 4.5 * CELL_SIZE     # 河界中心线

    if player_color == 'red':
        # 玩家执红，标准方向：楚河在左边，汉界在右边
        draw.text((left_center, river_y), "楚 河", fill='black', font=font, anchor='mm')
        draw.text((right_center, river_y), "汉 界", fill='black', font=font, anchor='mm')
    else:
        # 玩家执黑，翻转方向：汉界在左边，楚河在右边
        draw.text((left_center, river_y), "汉 界", fill='black', font=font, anchor='mm')
        draw.text((right_center, river_y), "楚 河", fill='black', font=font, anchor='mm')

    # 解析 FEN 并放置棋子
    piece_font = get_font(26)  # 棋子字体 26px
    board_str = fen.split()[0]
    rows = board_str.split('/')

    for row_idx, row in enumerate(rows):
        col_idx = 0
        for char in row:
            if char.isdigit():
                col_idx += int(char)
            elif char in PIECE_CHARS:
                # 根据玩家颜色决定棋盘方向
                # FEN row_idx=0 是黑方底线，row_idx=9 是红方底线
                if player_color == 'red':
                    # 玩家执红：红方在下（玩家视角）
                    # FEN row_idx=0（黑方底线）显示在顶部
                    y_pos = MARGIN + row_idx * CELL_SIZE
                else:
                    # 玩家执黑：黑方在下（玩家视角）
                    # FEN row_idx=0（黑方底线）显示在底部
                    y_pos = MARGIN + (9 - row_idx) * CELL_SIZE

                x_pos = MARGIN + col_idx * CELL_SIZE

                # 棋子字符和颜色
                piece_char = PIECE_CHARS[char]
                # 红方棋子用红色，黑方棋子用黑色
                color = 'red' if char in RED_PIECES else 'black'

                # 绘制棋子圆形背景
                radius = 22
                draw.ellipse([
                    x_pos - radius, y_pos - radius,
                    x_pos + radius, y_pos + radius
                ], fill='#f5deb3', outline=color, width=2)

                # 绘制棋子文字（使用 anchor='mm' 居中）
                draw.text((x_pos, y_pos), piece_char, fill=color, font=piece_font, anchor='mm')

                col_idx += 1

    # 保存图片
    if output_path:
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        img.save(output)
        return str(output)
    else:
        output = tempfile.mktemp(suffix=".png")
        img.save(output)
        return output