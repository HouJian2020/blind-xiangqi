"""测试对局管理"""

import pytest
import tempfile
from pathlib import Path

from xiangqi_engine.game.game import Game, GameMeta, get_game_save_dir


def test_game_create():
    """测试创建对局"""
    game = Game.create(player_color="red", level=5)

    assert game.meta.player_color == "red"
    assert game.meta.level == 5
    assert game.meta.result == "ongoing"
    assert game.get_current_side() == "red"


def test_game_make_move():
    """测试执行招法"""
    game = Game.create()

    success = game.make_move("b2e5", "炮二平五")
    assert success
    assert game.get_move_count() == 1
    assert game.get_current_side() == "black"


def test_game_multiple_moves():
    """测试多步招法"""
    game = Game.create()

    moves = [
        ("b2e5", "炮二平五"),
        ("h9g7", "马8进7"),
        ("h0g2", "马二进三"),
    ]

    for uci, chinese in moves:
        success = game.make_move(uci, chinese)
        assert success

    assert game.get_move_count() == 3


def test_game_save_load():
    """测试保存和加载"""
    game = Game.create(player_color="black", level=7)
    game.make_move("h9g7", "马8进7")

    # 保存到临时文件
    with tempfile.NamedTemporaryFile(suffix=".xqi", delete=False) as f:
        filepath = f.name

    try:
        game.save(filepath)

        # 加载
        loaded = Game.load(filepath)

        assert loaded.meta.player_color == "black"
        assert loaded.meta.level == 7
        assert loaded.get_move_count() == 1
    finally:
        Path(filepath).unlink()


def test_game_get_moves_text():
    """测试获取招法文本"""
    game = Game.create()

    game.make_move("b2e5", "炮二平五")
    game.make_move("h9g7", "马8进7")

    text = game.get_moves_text()
    assert "炮二平五" in text
    assert "马8进7" in text


def test_game_result():
    """测试设置对局结果"""
    game = Game.create()
    game.set_result("win")

    assert game.meta.result == "win"


def test_game_fen_history():
    """测试 FEN 历史"""
    game = Game.create()

    initial_fen = game.get_fen()
    game.make_move("b2e5", "炮二平五")

    # FEN 历史应包含初始和更新后的 FEN
    assert len(game.fen_history) == 2
    assert game.fen_history[0] == initial_fen


def test_get_game_save_dir():
    """测试获取保存目录"""
    dir_path = get_game_save_dir()
    assert dir_path.exists()
    assert str(dir_path).endswith("games")


def test_is_player_turn():
    """测试玩家回合判断"""
    # 红方玩家
    game = Game.create(player_color="red")
    assert game.is_player_turn()  # 红方先行

    game.make_move("b2e5", "炮二平五")
    assert not game.is_player_turn()  # 黑方回合

    # 黑方玩家
    game2 = Game.create(player_color="black")
    assert not game2.is_player_turn()  # 红方先行，不是玩家回合