"""测试棋盘状态"""

import pytest
from xiangqi_engine.game.board import BoardState, create_initial_board, INITIAL_FEN


def test_create_initial_board():
    """测试创建初始棋盘"""
    board = create_initial_board()
    assert board.fen == INITIAL_FEN
    assert board.turn == "red"


def test_board_state_parse_fen():
    """测试解析 FEN"""
    board = BoardState(fen=INITIAL_FEN)

    # 检查棋子位置
    # 红帅在 (4, 0)
    piece = board.get_piece(4, 0)
    assert piece == "K"  # 红帅

    # 黑将在 (4, 9)
    piece = board.get_piece(4, 9)
    assert piece == "k"  # 黑将


def test_get_piece_type():
    """测试获取棋子类型"""
    board = create_initial_board()

    # 红帅类型
    piece_type = board.get_piece_type(4, 0)
    assert piece_type == "k"

    # 空位置
    piece_type = board.get_piece_type(5, 5)
    assert piece_type is None


def test_get_piece_side():
    """测试获取棋子所属方"""
    board = create_initial_board()

    # 红方棋子
    side = board.get_piece_side(4, 0)
    assert side == "red"

    # 黑方棋子
    side = board.get_piece_side(4, 9)
    assert side == "black"


def test_make_move_uci():
    """测试执行 UCI 招法"""
    board = create_initial_board()

    # 红炮平移
    success = board.make_move_uci("b2e5")
    assert success

    # 检查棋子已移动
    piece = board.get_piece(1, 2)  # 原位置应该空
    assert piece is None

    piece = board.get_piece(4, 5)  # 新位置有炮
    assert piece == "C"


def test_board_copy():
    """测试复制棋盘"""
    board = create_initial_board()
    board.make_move_uci("b2e5")

    copied = board.copy()
    assert copied.fen == board.fen

    # 修改原棋盘不影响复制
    board.make_move_uci("h9g7")
    assert copied.get_fen() != board.get_fen()


def test_valid_position():
    """测试位置有效性"""
    board = create_initial_board()

    assert board.is_valid_position(0, 0)
    assert board.is_valid_position(8, 9)
    assert not board.is_valid_position(-1, 0)
    assert not board.is_valid_position(9, 0)
    assert not board.is_valid_position(0, 10)


def test_get_all_pieces():
    """测试获取所有棋子"""
    board = create_initial_board()

    red_pieces = board.get_all_pieces("red")
    assert len(red_pieces) == 16

    black_pieces = board.get_all_pieces("black")
    assert len(black_pieces) == 16


def test_turn_update():
    """测试行棋方更新"""
    board = create_initial_board()
    assert board.turn == "red"

    board.make_move_uci("b2e5")
    assert board.turn == "black"