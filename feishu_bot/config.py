"""配置管理 — webhook service 模式

飞书连接由 FeishuGateway 统一管理，这里只保留游戏配置。
"""

import os
from pathlib import Path


class FeishuConfig:
    """游戏配置（飞书凭证已移到 gateway）"""

    # Gateway 连接
    GATEWAY_URL: str = os.getenv("GATEWAY_URL", "http://localhost:9000")
    SERVICE_NAME: str = os.getenv("SERVICE_NAME", "blind_chess")

    # 游戏配置
    DEFAULT_LEVEL: int = int(os.getenv("DEFAULT_LEVEL", "5"))
    DEFAULT_COLOR: str = os.getenv("DEFAULT_COLOR", "red")
    BOARD_IMAGE_METHOD: str = os.getenv("BOARD_IMAGE_METHOD", "pil")  # svg 或 pil

    # 存储路径
    GAME_STORAGE_DIR: Path = Path.home() / ".blind-xiangqi" / "feishu_games"
    IMAGE_STORAGE_DIR: Path = Path.home() / ".blind-xiangqi" / "feishu_images"

    @classmethod
    def load_from_env_file(cls, filepath: str = "config/feishu.env") -> None:
        """从 .env 文件加载配置（保持兼容，可选）"""
        env_path = Path(filepath)
        if env_path.exists():
            with open(env_path, "r") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        key, value = line.split("=", 1)
                        key = key.strip()
                        value = value.strip()
                        os.environ[key] = value

            cls.GATEWAY_URL = os.getenv("GATEWAY_URL", "http://localhost:9000")
            cls.SERVICE_NAME = os.getenv("SERVICE_NAME", "blind_chess")
            cls.DEFAULT_LEVEL = int(os.getenv("DEFAULT_LEVEL", "5"))
            cls.DEFAULT_COLOR = os.getenv("DEFAULT_COLOR", "red")
            cls.BOARD_IMAGE_METHOD = os.getenv("BOARD_IMAGE_METHOD", "pil")

    @classmethod
    def ensure_dirs(cls) -> None:
        """确保存储目录存在"""
        cls.GAME_STORAGE_DIR.mkdir(parents=True, exist_ok=True)
        cls.IMAGE_STORAGE_DIR.mkdir(parents=True, exist_ok=True)

    @classmethod
    def validate(cls) -> bool:
        """验证配置是否完整"""
        return bool(cls.GATEWAY_URL)
