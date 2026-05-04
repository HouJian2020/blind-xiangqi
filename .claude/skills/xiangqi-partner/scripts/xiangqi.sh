#!/bin/bash
# 盲棋对弈启动脚本 (Linux/Mac)
# 从 xiangqi.env 读取配置

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="$SCRIPT_DIR/xiangqi.env"
EXECUTOR="$SCRIPT_DIR/executor.py"

# 加载环境变量（处理 ~ 展开）
while IFS='=' read -r key value; do
    # 跳过空行和注释
    [[ -z "$key" || "$key" =~ ^# ]] && continue
    # 展开 ~ 为 HOME
    value="${value//\~/$HOME}"
    export "$key"="$value"
done < "$ENV_FILE"

# 执行
exec "$PYTHON_INTERPRETER" "$EXECUTOR" "$@"