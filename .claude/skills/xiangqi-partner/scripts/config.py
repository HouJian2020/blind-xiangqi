"""Skill 配置 - 从 xiangqi.env 读取

配置文件 xiangqi.env 由 Shell 和 Python 共用。
"""

from pathlib import Path
import re

# ============================================================================
# 配置文件路径
# ============================================================================

ENV_FILE = Path(__file__).parent / "xiangqi.env"

# ============================================================================
# 配置读取函数
# ============================================================================

def _load_env():
    """从 .env 文件加载配置"""
    config = {}
    if ENV_FILE.exists():
        content = ENV_FILE.read_text(encoding="utf-8")
        for line in content.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip()
                # 展开 ~ 为 HOME
                if value.startswith("~"):
                    value = str(Path.home()) + value[1:]
                config[key] = value
    return config

def _get_config_value(key: str, default=None):
    """获取配置值"""
    config = _load_env()
    value = config.get(key, default)
    # 类型转换
    if key == "DEFAULT_LEVEL" and value is not None:
        return int(value)
    if key in ("GAME_STORAGE_DIR", "IMAGE_OUTPUT_DIR") and value:
        return Path(value)
    return value

# ============================================================================
# 配置变量（动态读取）
# ============================================================================

def get_python_interpreter():
    return _get_config_value("PYTHON_INTERPRETER", "~/miniconda3/envs/auto-dev/bin/python")

def get_game_storage_dir():
    return _get_config_value("GAME_STORAGE_DIR", Path.home() / ".blind-xiangqi" / "games")

def get_image_output_dir():
    return _get_config_value("IMAGE_OUTPUT_DIR", Path.home() / ".blind-xiangqi" / "images")

def get_default_player_color():
    return _get_config_value("DEFAULT_PLAYER_COLOR", "red")

def get_default_level():
    return _get_config_value("DEFAULT_LEVEL", 3)

# 模块级变量（初始化时加载）
PYTHON_INTERPRETER = get_python_interpreter()
GAME_STORAGE_DIR = get_game_storage_dir()
IMAGE_OUTPUT_DIR = get_image_output_dir()
DEFAULT_PLAYER_COLOR = get_default_player_color()
DEFAULT_LEVEL = get_default_level()

# ============================================================================
# 配置管理函数
# ============================================================================

def update_config(key: str, value) -> dict:
    """更新配置并持久化到 xiangqi.env

    Args:
        key: 配置键名
        value: 新值

    Returns:
        {"success": bool, "message": str}
    """
    persistable_keys = ["DEFAULT_PLAYER_COLOR", "DEFAULT_LEVEL", "PYTHON_INTERPRETER"]

    valid_keys = [
        "PYTHON_INTERPRETER",
        "GAME_STORAGE_DIR",
        "IMAGE_OUTPUT_DIR",
        "DEFAULT_PLAYER_COLOR",
        "DEFAULT_LEVEL",
    ]

    if key not in valid_keys:
        return {
            "success": False,
            "error": f"无效配置键: {key}，有效键: {valid_keys}"
        }

    # 更新模块变量
    globals()[key] = value

    # 持久化到文件
    if key in persistable_keys:
        try:
            _persist_env(key, value)
            return {
                "success": True,
                "key": key,
                "value": value,
                "message": f"已更新并保存 {key} = {value}"
            }
        except Exception as e:
            return {
                "success": True,
                "key": key,
                "value": value,
                "message": f"已更新 {key} = {value}（但保存失败: {e}）"
            }

    return {
        "success": True,
        "key": key,
        "value": value,
        "message": f"已更新 {key} = {value}"
    }


def _persist_env(key: str, value):
    """持久化配置到 xiangqi.env"""
    content = ENV_FILE.read_text(encoding="utf-8")

    # 构建新行
    if isinstance(value, int):
        new_line = f"{key}={value}"
    else:
        new_line = f"{key}={value}"

    # 替换现有行
    pattern = rf"^{key}=.*$"
    new_content = re.sub(pattern, new_line, content, flags=re.MULTILINE)

    ENV_FILE.write_text(new_content, encoding="utf-8")


def get_config(key: str = None) -> dict:
    """获取配置值

    Args:
        key: 配置键名，可选

    Returns:
        {"success": bool, "config": dict}
    """
    config_keys = [
        "PYTHON_INTERPRETER",
        "GAME_STORAGE_DIR",
        "IMAGE_OUTPUT_DIR",
        "DEFAULT_PLAYER_COLOR",
        "DEFAULT_LEVEL",
    ]

    if key is None:
        # 重新加载配置
        config = _load_env()
        return {
            "success": True,
            "config": {k: str(config.get(k, globals().get(k, ""))) for k in config_keys}
        }

    if key not in config_keys:
        return {
            "success": False,
            "error": f"无效配置键: {key}"
        }

    return {
        "success": True,
        "key": key,
        "value": globals().get(key)
    }