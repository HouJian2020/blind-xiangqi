"""配置管理

管理应用配置。
"""

import json
from pathlib import Path
from typing import Optional, Any
from dataclasses import dataclass, asdict


@dataclass
class Config:
    """应用配置"""

    default_level: int = 5
    default_color: str = "red"
    engine_path: str = ""  # 默认 ~/.blind-xiangqi/engines/pikafish
    image_theme: str = "clean_alpha"
    image_output_dir: str = ""  # 默认 ~/.blind-xiangqi/images


def get_config_path() -> Path:
    """获取配置文件路径"""
    return Path.home() / ".blind-xiangqi" / "config.json"


def get_default_engine_path() -> Path:
    """获取默认引擎路径"""
    return Path.home() / ".blind-xiangqi" / "engines" / "pikafish"


def get_default_image_dir() -> Path:
    """获取默认图片输出目录"""
    return Path.home() / ".blind-xiangqi" / "images"


class ConfigManager:
    """配置管理器"""

    def __init__(self):
        """初始化配置管理器"""
        self.config_path = get_config_path()
        self._config: Optional[Config] = None

    def load(self) -> Config:
        """加载配置"""
        if self._config:
            return self._config

        if self.config_path.exists():
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self._config = Config(**data)
            except Exception:
                self._config = Config()
        else:
            self._config = Config()

        # 设置默认值
        if not self._config.engine_path:
            self._config.engine_path = str(get_default_engine_path())
        if not self._config.image_output_dir:
            self._config.image_output_dir = str(get_default_image_dir())

        return self._config

    def save(self, config: Config) -> None:
        """保存配置"""
        # 确保目录存在
        self.config_path.parent.mkdir(parents=True, exist_ok=True)

        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump(asdict(config), f, ensure_ascii=False, indent=2)

        self._config = config

    def get(self, key: str) -> Any:
        """获取配置项"""
        config = self.load()
        return getattr(config, key, None)

    def set(self, key: str, value: Any) -> None:
        """设置配置项"""
        config = self.load()
        if hasattr(config, key):
            setattr(config, key, value)
            self.save(config)

    def reset(self) -> Config:
        """重置为默认配置"""
        self._config = Config()
        self.save(self._config)
        return self._config