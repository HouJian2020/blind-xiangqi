"""盲棋 webhook service 启动入口。

不再直接连飞书 WebSocket——由 FeishuGateway 统一管理连接。
本服务只暴露 HTTP 端点，接收 gateway 转发的消息。
"""

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import uvicorn
from feishu_bot.bot import app
from feishu_bot.config import FeishuConfig

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler('/tmp/feishu_bot.log'),
        logging.StreamHandler(sys.stdout),
    ]
)

log = logging.getLogger("blind_chess_service")


def main():
    FeishuConfig.load_from_env_file()
    FeishuConfig.ensure_dirs()

    log.info("=" * 50)
    log.info("BlindChess webhook service 启动")
    log.info(f"  GATEWAY_URL: {FeishuConfig.GATEWAY_URL}")
    log.info(f"  SERVICE_NAME: {FeishuConfig.SERVICE_NAME}")
    log.info(f"  DEFAULT_LEVEL: {FeishuConfig.DEFAULT_LEVEL}")
    log.info(f"  DEFAULT_COLOR: {FeishuConfig.DEFAULT_COLOR}")
    log.info("=" * 50)

    uvicorn.run(app, host="0.0.0.0", port=8010, log_level="info")


if __name__ == "__main__":
    main()
