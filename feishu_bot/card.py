"""消息卡片生成

生成飞书消息卡片，显示棋盘图片和对局信息。
"""

import json
import tempfile
from typing import Optional
from pathlib import Path

from lark_oapi import Client

from .config import FeishuConfig
from xiangqi_engine.image.board_generator import generate_board_image


def upload_image_to_feishu(client: Client, image_path: str) -> Optional[str]:
    """
    上传图片到飞书，获取 image_key

    Args:
        client: 飞书 Client 实例
        image_path: 图片文件路径

    Returns:
        image_key 或 None
    """
    try:
        # 使用飞书 API 上传图片
        # TODO: 实现具体的上传逻辑
        # 参考：https://open.feishu.cn/document/server-docs/im-v1/image/create
        return None
    except Exception as e:
        print(f"上传图片失败: {e}")
        return None


def generate_board_image_and_upload(
    client: Optional[Client],
    fen: str,
) -> Optional[str]:
    """
    生成棋盘图片并上传到飞书

    Args:
        client: 飞书 Client 实例
        fen: 当前局面 FEN

    Returns:
        image_key 或 None
    """
    try:
        # 生成棋盘图片
        image_path = generate_board_image(fen)

        if client and image_path:
            return upload_image_to_feishu(client, image_path)

        return None
    except Exception as e:
        print(f"生成棋盘图片失败: {e}")
        return None


def generate_board_card(
    fen: str,
    moves_text: str = "",
    current_side: str = "red",
    message: str = "",
    image_path: Optional[str] = None,
) -> dict:
    """
    生成棋盘消息卡片

    Args:
        fen: 当前局面 FEN
        moves_text: 招法记录文本
        current_side: 当前行棋方
        message: 附加消息（如将军提示）
        image_path: 棋盘图片路径（如果已生成）

    Returns:
        卡片 JSON 结构
    """
    side_text = "红方行棋" if current_side == "red" else "黑方行棋"

    # 卡片结构
    card = {
        "config": {
            "wide_screen_mode": True
        },
        "header": {
            "template": "blue" if current_side == "red" else "purple",
            "title": {
                "tag": "plain_text",
                "content": f"📍 {side_text}"
            }
        },
        "elements": []
    }

    # 如果有棋盘图片，显示图片
    if image_path:
        card["elements"].append({
            "tag": "img",
            "img_key": image_path,
            "alt": {
                "tag": "plain_text",
                "content": "棋盘"
            }
        })
    else:
        # 没有图片，显示 FEN
        card["elements"].append({
            "tag": "div",
            "text": {
                "tag": "lark_md",
                "content": f"**当前局面**\nFEN: `{fen}`"
            }
        })

    # 招法记录
    if moves_text:
        card["elements"].append({
            "tag": "div",
            "text": {
                "tag": "lark_md",
                "content": f"**招法记录**\n{moves_text}"
            }
        })

    # 附加消息
    if message:
        card["elements"].append({
            "tag": "div",
            "text": {
                "tag": "lark_md",
                "content": message
            }
        })

    # 操作按钮
    card["elements"].append({
        "tag": "action",
        "actions": [
            {
                "tag": "button",
                "text": {
                    "tag": "plain_text",
                    "content": "查看棋谱"
                },
                "type": "default",
                "value": {"action": "status"}
            },
            {
                "tag": "button",
                "text": {
                    "tag": "plain_text",
                    "content": "认输"
                },
                "type": "danger",
                "value": {"action": "resign"}
            }
        ]
    })

    return card


def generate_welcome_card(level: int, color: str) -> dict:
    """生成欢迎卡片"""
    color_text = "红方" if color == "red" else "黑方"

    return {
        "config": {"wide_screen_mode": True},
        "header": {
            "template": "turquoise",
            "title": {
                "tag": "plain_text",
                "content": "🎮 盲棋对弈"
            }
        },
        "elements": [
            {
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": f"**对局已开始**\n\n执方：{color_text}\n难度：Lv{level}\n\n请发送招法开始对弈，例如：\n- 红方：「炮二平五」\n- 黑方：「炮8平5」"
                }
            },
            {
                "tag": "action",
                "actions": [
                    {
                        "tag": "button",
                        "text": {
                            "tag": "plain_text",
                            "content": "帮助"
                        },
                        "type": "primary",
                        "value": {"action": "help"}
                    }
                ]
            }
        ]
    }


def generate_result_card(result: str, moves_text: str = "") -> dict:
    """生成结果卡片"""
    result_text = "🎉 你赢了！" if result == "win" else "😢 你输了" if result == "loss" else "⚖️ 和棋"

    return {
        "config": {"wide_screen_mode": True},
        "header": {
            "template": "green" if result == "win" else "red" if result == "loss" else "grey",
            "title": {
                "tag": "plain_text",
                "content": result_text
            }
        },
        "elements": [
            {
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": f"**对局结束**\n\n{moves_text}\n\n发送「下棋」开始新对局"
                }
            },
            {
                "tag": "action",
                "actions": [
                    {
                        "tag": "button",
                        "text": {
                            "tag": "plain_text",
                            "content": "新对局"
                        },
                        "type": "primary",
                        "value": {"action": "new_game"}
                    }
                ]
            }
        ]
    }


def generate_error_card(error_msg: str) -> dict:
    """生成错误卡片"""
    return {
        "config": {"wide_screen_mode": True},
        "header": {
            "template": "red",
            "title": {
                "tag": "plain_text",
                "content": "⚠️ 错误"
            }
        },
        "elements": [
            {
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": error_msg
                }
            }
        ]
    }


def card_to_content(card: dict) -> str:
    """将卡片转换为消息 content"""
    return json.dumps(card, ensure_ascii=False)