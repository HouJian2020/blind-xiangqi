"""测试招法转换器"""

import pytest
from xiangqi_engine.notation.converter import MoveConverter
from xiangqi_engine.engine.pikafish import map_level_to_depth, map_level_to_time


def test_map_level_to_depth():
    """测试深度映射"""
    assert map_level_to_depth(1) == 1
    assert map_level_to_depth(5) == 5
    assert map_level_to_depth(10) == 15


def test_map_level_to_time():
    """测试时间映射"""
    assert map_level_to_time(1) == 0.1
    assert map_level_to_time(5) == 0.3
    assert map_level_to_time(10) == 1.0


def test_converter_initialization():
    """测试转换器初始化"""
    converter = MoveConverter()
    # cchess 内部状态，不再暴露 _board_state
    assert converter._board is None


def test_set_board_state():
    """测试设置棋盘状态"""
    converter = MoveConverter()
    fen = "rnbakabnr/9/1c5c1/p1p1p1p1p/9/9/P1P1P1P1P/1C5C1/9/RNBAKABNR w - - 0 1"
    converter.set_board_state(fen)

    # 检查棋盘状态已设置
    assert converter._board is not None


def test_chinese_to_uci_basic():
    """测试中文到 UCI 基本转换"""
    converter = MoveConverter()
    fen = "rnbakabnr/9/1c5c1/p1p1p1p1p/9/9/P1P1P1P1P/1C5C1/9/RNBAKABNR w - - 0 1"
    converter.set_board_state(fen)

    # 简单测试转换功能
    result = converter.chinese_to_uci("炮二平五", "red")
    assert isinstance(result, str)
    assert len(result) == 4
    assert result == "h2e2"


def test_uci_to_chinese_basic():
    """测试 UCI 到中文基本转换"""
    converter = MoveConverter()
    fen = "rnbakabnr/9/1c5c1/p1p1p1p1p/9/9/P1P1P1P1P/1C5C1/9/RNBAKABNR w - - 0 1"
    converter.set_board_state(fen)

    result = converter.uci_to_chinese("h2e2", "red")
    assert isinstance(result, str)
    assert len(result) >= 3
    assert result == "炮二平五"


def test_chinese_to_uci_flexible_input():
    """测试双向兼容输入 - 红方黑方都可以用中文数字或阿拉伯数字"""
    converter = MoveConverter()

    # 红方局面
    fen = "rnbakabnr/9/1c5c1/p1p1p1p1p/9/9/P1P1P1P1P/1C5C1/9/RNBAKABNR w - - 0 1"
    converter.set_board_state(fen)

    # 红方用中文数字
    assert converter.chinese_to_uci("炮二平五", "red") == "h2e2"
    # 红方用阿拉伯数字（也能解析）
    assert converter.chinese_to_uci("炮2平5", "red") == "h2e2"

    # 黑方局面
    fen = "rnbakabnr/9/1c5c1/p1p1p1p1p/9/9/P1P1P1P1P/4C2C1/9/RNBAKABNR b - - 1 1"
    converter.set_board_state(fen)

    # 黑方用中文数字
    assert converter.chinese_to_uci("炮二平五", "black") == "b7e7"
    # 黑方用阿拉伯数字
    assert converter.chinese_to_uci("炮2平5", "black") == "b7e7"


def test_uci_to_chinese_black_side():
    """测试黑方 UCI 转中文输出"""
    converter = MoveConverter()
    fen = "rnbakabnr/9/1c5c1/p1p1p1p1p/9/9/P1P1P1P1P/4C2C1/9/RNBAKABNR b - - 1 1"
    converter.set_board_state(fen)

    # 黑方招法，输出应转换为中文数字（统一显示）
    result = converter.uci_to_chinese("b7e7", "black")
    assert isinstance(result, str)
    assert result == "炮二平五"