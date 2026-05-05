"""消息处理

处理用户发送的消息，解析招法。
"""

import re
from datetime import datetime, timedelta
from typing import Optional
from dataclasses import dataclass


# 招法错字映射
TYPO_MAP = {
    # 棋子
    "琪": "七", "骐": "七", "吴": "五", "无": "五", "宾": "兵", "冰": "兵",
    "跑": "炮", "泡": "炮", "居": "车", "拘": "车", "率": "帅", "师": "帅",
    # 列号（中文）
    "壹": "一", "乙": "一", "贰": "二", "两": "二", "叁": "三", "散": "三",
    "肆": "四", "死": "四", "伍": "五", "陆": "六", "留": "六",
    "柒": "七", "气": "七", "妻": "七", "捌": "八", "吧": "八", "玖": "九", "久": "九",
    # 动作
    "屏": "平", "评": "平", "近": "进", "金": "进", "腿": "退", "推": "退",
}


@dataclass
class MoveCommand:
    """招法命令"""
    original: str          # 用户原始输入
    corrected: str         # 纠错后的招法
    is_valid: bool         # 是否有效


@dataclass
class UserIntent:
    """用户意图"""
    action: str            # 动作类型：new_game, move, status, help, resign, history, switch_game, delete, undo
    move: Optional[MoveCommand] = None
    level: Optional[int] = None
    color: Optional[str] = None
    game_index: Optional[int] = None      # 切换对局编号
    undo_steps: Optional[int] = None      # 悔棋步数
    time_range: Optional[dict] = None     # 时间范围参数
    confirm_delete: bool = False          # 确认清空


def correct_move_typo(move_text: str) -> str:
    """纠错招法中的错字"""
    result = move_text
    for typo, correct in TYPO_MAP.items():
        result = result.replace(typo, correct)
    return result


def parse_time_range(text: str) -> Optional[dict]:
    """解析时间范围参数

    Args:
        text: 用户输入的时间范围描述

    Returns:
        解析结果字典，包含 date, start_date, date_prefix, limit 等参数
        不匹配时返回 None
    """
    text = text.strip().lower()

    # 数字：最近N局
    if text.isdigit():
        return {"limit": int(text)}

    # 今天
    if text in ["今天", "今日", "today"]:
        return {"date": datetime.now().strftime("%Y-%m-%d")}

    # 昨天
    if text in ["昨天", "昨日", "yesterday"]:
        yesterday = datetime.now() - timedelta(days=1)
        return {"date": yesterday.strftime("%Y-%m-%d")}

    # 最近N天（支持中文数字）
    chinese_num_map = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9, "十": 10}
    recent_match = re.match(r"最近(\d+|[一二三四五六七八九十])天", text)
    if recent_match:
        num_str = recent_match.group(1)
        if num_str.isdigit():
            days = int(num_str)
        else:
            days = chinese_num_map.get(num_str, 1)
        start = datetime.now() - timedelta(days=days - 1)
        return {"start_date": start.strftime("%Y-%m-%d")}

    # 本周
    if text in ["这一周", "本周", "this week"]:
        today = datetime.now()
        start = today - timedelta(days=today.weekday())
        return {"start_date": start.strftime("%Y-%m-%d")}

    # 本月
    if text in ["这个月", "本月", "this month"]:
        return {"date_prefix": datetime.now().strftime("%Y-%m")}

    # 上月
    if text in ["上个月", "上月", "last month"]:
        last_month = datetime.now().replace(day=1) - timedelta(days=1)
        return {"date_prefix": last_month.strftime("%Y-%m")}

    return None  # 不匹配


def parse_move(move_text: str) -> Optional[MoveCommand]:
    """
    解析招法

    支持格式：
    - 炮二平五 / 炮2平5 (红方)
    - 炮8平5 (黑方)
    """
    original = move_text.strip()
    corrected = correct_move_typo(original)

    # 中文招法正则：棋子 + 列号 + 动作 + 目标
    # 支持中文数字和阿拉伯数字
    # 红方：车马炮兵仕相帅，黑方：车马炮卒士象将
    pattern = r'^([车马炮兵仕相帅卒士象将])([一二三四五六七八九一二三四五六七八九\d])([平进退])([一二三四五六七八九一二三四五六七八九\d])$'

    match = re.match(pattern, corrected)
    if match:
        return MoveCommand(
            original=original,
            corrected=corrected,
            is_valid=True,
        )

    return MoveCommand(
        original=original,
        corrected=corrected,
        is_valid=False,
    )


def parse_user_message(text: str) -> UserIntent:
    """
    解析用户消息意图

    Args:
        text: 用户发送的文本

    Returns:
        UserIntent: 用户意图
    """
    text = text.strip()

    # 新游戏
    if text in ["开始下棋", "下棋", "开始", "新游戏", "new"]:
        return UserIntent(action="new_game")

    # 查看状态
    if text in ["查看棋谱", "棋谱", "状态", "status"]:
        return UserIntent(action="status")

    # 查看棋盘图片
    if text in ["看棋盘", "棋盘", "查看棋盘", "board"]:
        return UserIntent(action="board")

    # 认输
    if text in ["认输", "resign", "投降"]:
        return UserIntent(action="resign")

    # 帮助
    if text in ["帮助", "help", "怎么玩"]:
        return UserIntent(action="help")

    # 悔棋
    undo_match = re.match(r"^(悔棋|undo)(?:\s*(\d+))?$", text)
    if undo_match:
        steps = int(undo_match.group(2) or 1)
        return UserIntent(action="undo", undo_steps=steps)

    # 查看历史对局
    history_match = re.match(r"^(历史|历史对局|history)(?:\s+(.+))?$", text)
    if history_match:
        time_param = history_match.group(2)
        if time_param:
            time_range = parse_time_range(time_param)
            if time_range is None:
                return UserIntent(action="error", move=MoveCommand(
                    original=text, corrected=text, is_valid=False
                ))
            return UserIntent(action="history", time_range=time_range)
        return UserIntent(action="history")

    # 简单时间查询（今天/昨天等）
    time_range = parse_time_range(text)
    if time_range:
        return UserIntent(action="history", time_range=time_range)

    # 切换对局
    switch_match = re.match(r"^(切换|switch)\s*(\d+)$", text)
    if switch_match:
        return UserIntent(action="switch_game", game_index=int(switch_match.group(2)))

    # 删除对局（全部需要确认）
    delete_match = re.match(r"^(删除|delete)\s+(.+)$", text)
    if delete_match:
        target = delete_match.group(2)
        # 数字编号
        if target.isdigit():
            return UserIntent(action="delete_request", game_index=int(target))
        # 时间范围
        time_range = parse_time_range(target)
        if time_range:
            return UserIntent(action="delete_request", time_range=time_range)
        # 不匹配
        return UserIntent(action="error", move=MoveCommand(
            original=text, corrected=text, is_valid=False
        ))

    # 清空历史
    if text in ["清空", "清空历史", "清空对局", "clear all"]:
        return UserIntent(action="delete_request", time_range={"clear_all": True})

    # 确认删除
    if text in ["确认删除", "确认", "confirm"]:
        return UserIntent(action="delete_confirm", confirm_delete=True)

    # 解析招法
    move = parse_move(text)
    if move.is_valid:
        return UserIntent(action="move", move=move)

    # 尝试解析新游戏参数（如 "红方难度5"）
    color_match = re.search(r"(红方|红|black|黑方|黑)", text)
    level_match = re.search(r"难度(\d)|难度\s*(\d)|lv(\d)|level\s*(\d)", text)

    if color_match or level_match:
        color = "red" if color_match and "红" in color_match.group(0) else "black"
        level = int(level_match.group(1) or level_match.group(2) or level_match.group(3) or 5) if level_match else 5
        return UserIntent(action="new_game", color=color, level=level)

    # 默认当作招法尝试
    return UserIntent(action="move", move=move)


def get_help_text() -> str:
    """获取帮助文本"""
    return """【盲棋对弈帮助】

▶ 开始游戏
  下棋 - 新对局（红方 Lv5）
  红方难度3 - 指定执方和难度

▶ 走棋招法
  炮二平五 / 炮2平5 - 红方中文，黑方数字

▶ 查看状态
  棋谱 - 招法记录
  棋盘 - 棋盘图片

▶ 历史对局
  历史 - 最近10局
  历史 5 - 最近5局
  今天 / 昨天 / 最近三天 / 这个月

▶ 删除对局（需确认）
  删除 1 - 删除编号#1
  删除 今天 - 删除今日对局
  清空 - 删除全部
  确认删除 - 执行删除

▶ 对局控制
  悔棋 - 悔一步
  悔棋2 - 悔两步
  切换1 - 继续对局#1
  认输 - 结束对局

▶ 难度等级
  1-3: 初学者 | 4-6: 中等 | 7-10: 高手"""