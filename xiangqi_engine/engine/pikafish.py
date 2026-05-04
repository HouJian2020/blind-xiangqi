"""Pikafish 象棋引擎封装

Pikafish 是 Stockfish 的中国象棋衍生版本，支持 UCI 协议。
注意：Pikafish 不支持 Skill Level 选项，使用搜索深度控制难度。
"""

import logging
import re
from typing import Optional
from pathlib import Path

from .uci_client import UCIClient

logger = logging.getLogger(__name__)


# 初始局面 FEN (中国象棋)
INITIAL_FEN = "rnbakabnr/9/1c5c1/p1p1p1p1p/9/9/P1P1P1P1P/1C5C1/9/RNBAKABNR w - - 0 1"


def map_level_to_depth(user_level: int) -> int:
    """用户等级 1-10 → 搜索深度 1-15

    Pikafish 不支持 Skill Level，使用深度限制控制难度：
    - Level 1-2: depth 1-2 (初学者)
    - Level 3-5: depth 3-5 (入门到中等)
    - Level 6-8: depth 6-10 (较强)
    - Level 9-10: depth 12-15 (最强)
    """
    if user_level <= 2:
        return user_level
    elif user_level <= 5:
        return user_level
    elif user_level <= 8:
        return user_level + 2
    else:
        return min(15, user_level + 5)


def map_level_to_time(user_level: int) -> float:
    """用户等级 1-10 → 思考时间（秒）

    低难度快速返回，高难度给予更多思考时间。
    """
    if user_level <= 3:
        return 0.1
    elif user_level <= 6:
        return 0.3
    elif user_level <= 8:
        return 0.5
    else:
        return 1.0


class PikafishEngine:
    """Pikafish 引擎封装"""

    def __init__(self, engine_path: Optional[str] = None):
        """
        初始化 Pikafish 引擎

        Args:
            engine_path: 引擎路径，默认为 ~/.blind-xiangqi/engines/pikafish
        """
        if engine_path:
            self.engine_path = engine_path
        else:
            self.engine_path = str(
                Path.home() / ".blind-xiangqi" / "engines" / "pikafish"
            )

        self.client = UCIClient(self.engine_path)
        self._user_level = 5  # 默认中等难度
        self._current_fen = INITIAL_FEN
        self._depth_limit: Optional[int] = None
        self._time_limit: Optional[float] = None

    def start(self) -> None:
        """启动引擎"""
        self.client.start()
        # Pikafish 不支持 Skill Level，跳过该选项
        # 设置 Hash 大小（可选优化）
        self.client.set_option("Hash", 64)
        self.client.is_ready()

    def stop(self) -> None:
        """停止引擎"""
        self.client.stop()

    def set_user_level(self, user_level: int) -> None:
        """
        设置用户等级 (1-10)

        Args:
            user_level: 用户等级 1-10
        """
        self._user_level = max(1, min(10, user_level))
        self._depth_limit = map_level_to_depth(self._user_level)
        self._time_limit = map_level_to_time(self._user_level)

    def set_depth_limit(self, depth: int) -> None:
        """直接设置搜索深度"""
        self._depth_limit = depth

    def set_time_limit(self, seconds: float) -> None:
        """直接设置思考时间"""
        self._time_limit = seconds

    def set_position(self, fen: str = INITIAL_FEN) -> None:
        """设置当前局面"""
        logger.debug(f"set_position: {fen}")
        self._current_fen = fen
        self.client.send_command(f"position fen {fen}")

    def make_move(self, move_uci: str) -> None:
        """
        执行招法

        Args:
            move_uci: UCI 格式招法，如 "b2e5"
        """
        self.client.send_command(f"position fen {self._current_fen} moves {move_uci}")

    def get_best_move(self, time_limit: Optional[float] = None) -> Optional[str]:
        """
        获取最佳招法

        Args:
            time_limit: 思考时间（秒），可选，默认使用等级对应时间

        Returns:
            UCI 格式招法，如 "b2e5"
        """
        logger.debug(f"get_best_move 开始, depth_limit={self._depth_limit}, time_limit={self._time_limit}")

        # 根据设置选择搜索方式
        if self._depth_limit:
            cmd = f"go depth {self._depth_limit}"
            timeout = 10.0
        elif time_limit:
            cmd = f"go movetime {int(time_limit * 1000)}"
            timeout = time_limit + 5
        elif self._time_limit:
            cmd = f"go movetime {int(self._time_limit * 1000)}"
            timeout = self._time_limit + 5
        else:
            cmd = "go movetime 500"
            timeout = 10

        logger.debug(f"发送命令: {cmd}, timeout={timeout}")
        self.client.send_command(cmd)

        try:
            lines = self.client.wait_for_response("bestmove", timeout=timeout)
            logger.debug(f"收到响应: {len(lines)} 行")

            for line in lines:
                logger.debug(f"响应行: {line}")
                if line.startswith("bestmove"):
                    match = re.match(r"bestmove\s+(\w+)", line)
                    if match:
                        result = match.group(1)
                        logger.debug(f"解析到招法: {result}")
                        return result

            logger.warning("未找到 bestmove")
            return None

        except TimeoutError as e:
            logger.error(f"等待 bestmove 超时: {e}")
            return None

    def get_current_fen(self) -> str:
        """获取当前局面 FEN"""
        return self._current_fen

    def is_running(self) -> bool:
        """检查引擎是否运行"""
        return self.client.is_running()

    def __enter__(self):
        """上下文管理器入口"""
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器退出"""
        self.stop()
        return False