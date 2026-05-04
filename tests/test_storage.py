"""测试存储模块"""

import pytest
import tempfile
from pathlib import Path
from datetime import datetime

from xiangqi_engine.storage.config import ConfigManager, Config, get_config_path
from xiangqi_engine.storage.recorder import GameRecorder


def test_config_default():
    """测试默认配置"""
    manager = ConfigManager()
    config = manager.load()

    # 配置应该有有效的默认值
    assert config.default_level in range(1, 11)
    assert config.default_color in ["red", "black"]


def test_config_save_load():
    """测试配置保存和加载"""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "config.json"
        manager = ConfigManager()
        manager.config_path = config_path

        # 保存新配置
        config = Config(default_level=8, default_color="black")
        manager.save(config)

        # 加载
        loaded = manager.load()
        assert loaded.default_level == 8
        assert loaded.default_color == "black"


def test_config_get_set():
    """测试配置获取和设置"""
    manager = ConfigManager()

    # 获取当前配置
    current_level = manager.get("default_level")
    assert current_level in range(1, 11)

    # 设置新值
    manager.set("default_level", 8)
    assert manager.get("default_level") == 8


def test_game_recorder_save():
    """测试对局保存"""
    from xiangqi_engine.game.game import Game

    with tempfile.TemporaryDirectory() as tmpdir:
        recorder = GameRecorder(base_dir=Path(tmpdir))
        game = Game.create()

        filepath = recorder.save_game(game)
        assert filepath.exists()
        assert filepath.suffix == ".xqi"


def test_game_recorder_list():
    """测试对局列表"""
    from xiangqi_engine.game.game import Game

    with tempfile.TemporaryDirectory() as tmpdir:
        recorder = GameRecorder(base_dir=Path(tmpdir))

        # 创建多个对局
        game1 = Game.create()
        game2 = Game.create(player_color="black", level=3)

        recorder.save_game(game1)
        recorder.save_game(game2)

        games = recorder.list_games()
        assert len(games) == 2