"""配置管理"""

import os
from pathlib import Path
from typing import Optional


class FeishuConfig:
    """飞书配置"""

    # 从环境变量读取
    APP_ID: str = os.getenv("FEISHU_APP_ID", "")
    APP_SECRET: str = os.getenv("FEISHU_APP_SECRET", "")
    ENCRYPT_KEY: str = os.getenv("FEISHU_ENCRYPT_KEY", "")
    VERIFICATION_TOKEN: str = os.getenv("FEISHU_VERIFICATION_TOKEN", "")

    # 游戏配置
    DEFAULT_LEVEL: int = int(os.getenv("DEFAULT_LEVEL", "5"))
    DEFAULT_COLOR: str = os.getenv("DEFAULT_COLOR", "red")
    BOARD_IMAGE_METHOD: str = os.getenv("BOARD_IMAGE_METHOD", "pil")  # svg 或 pil

    # 存储路径
    GAME_STORAGE_DIR: Path = Path.home() / ".blind-xiangqi" / "feishu_games"
    IMAGE_STORAGE_DIR: Path = Path.home() / ".blind-xiangqi" / "feishu_images"

    @classmethod
    def load_from_env_file(cls, filepath: str = "config/feishu.env") -> None:
        """从 .env 文件加载配置"""
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

            # 重新加载
            cls.APP_ID = os.getenv("FEISHU_APP_ID", "")
            cls.APP_SECRET = os.getenv("FEISHU_APP_SECRET", "")
            cls.ENCRYPT_KEY = os.getenv("FEISHU_ENCRYPT_KEY", "")
            cls.VERIFICATION_TOKEN = os.getenv("FEISHU_VERIFICATION_TOKEN", "")
            cls.DEFAULT_LEVEL = int(os.getenv("DEFAULT_LEVEL", "5"))
            cls.DEFAULT_COLOR = os.getenv("DEFAULT_COLOR", "red")

    @classmethod
    def ensure_dirs(cls) -> None:
        """确保存储目录存在"""
        cls.GAME_STORAGE_DIR.mkdir(parents=True, exist_ok=True)
        cls.IMAGE_STORAGE_DIR.mkdir(parents=True, exist_ok=True)

    @classmethod
    def validate(cls) -> bool:
        """验证配置是否完整"""
        return bool(cls.APP_ID and cls.APP_SECRET)