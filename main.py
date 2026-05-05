"""飞书机器人服务入口 - 长连接模式

不需要公网IP，服务器主动连接飞书。
"""

import logging
import sys
import signal
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent))

from feishu_bot.bot import create_bot
from feishu_bot.config import FeishuConfig

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

# 全局机器人实例
bot = None


def signal_handler(sig, frame):
    """处理 Ctrl+C 信号"""
    global bot
    if bot:
        bot.stop()
    print("\n机器人已停止")
    sys.exit(0)


def main():
    """主函数"""
    global bot

    # 注册信号处理
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        bot = create_bot()
        bot.start()
    except ValueError as e:
        print(f"配置错误: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"启动失败: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()