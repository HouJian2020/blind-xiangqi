"""测试 UCI 客户端"""

import pytest
from unittest.mock import Mock, patch
from xiangqi_engine.engine.uci_client import UCIClient


def test_uci_client_init():
    """测试 UCI 客户端初始化"""
    client = UCIClient("/path/to/engine")
    assert client.engine_path == "/path/to/engine"
    assert not client.is_running()


def test_uci_client_mock_start():
    """测试启动（模拟）"""
    client = UCIClient("/path/to/engine")

    # 使用模拟进程
    with patch("subprocess.Popen") as mock_popen:
        mock_process = Mock()
        mock_process.stdin = Mock()
        mock_process.stdout = Mock()
        mock_popen.return_value = mock_process

        # 模拟 readline 返回
        mock_process.stdout.readline = Mock(return_value="uciok\n")

        client.start()
        assert client.is_running()


def test_uci_client_send_command():
    """测试发送命令"""
    client = UCIClient("/path/to/engine")

    with patch("subprocess.Popen") as mock_popen:
        mock_process = Mock()
        mock_process.stdin = Mock()
        mock_process.stdout = Mock()
        mock_popen.return_value = mock_process

        mock_process.stdout.readline = Mock(return_value="uciok\n")
        client.start()

        client.send_command("isready")
        mock_process.stdin.write.assert_called()


def test_map_level():
    """测试难度映射"""
    from xiangqi_engine.engine.pikafish import map_level_to_depth, map_level_to_time

    assert map_level_to_depth(1) == 1
    assert map_level_to_depth(5) == 5
    assert map_level_to_depth(10) == 15
    assert map_level_to_time(1) == 0.1
    assert map_level_to_time(10) == 1.0