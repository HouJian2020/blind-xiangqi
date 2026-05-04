#!/bin/bash
# 启动 Debug UI

cd "$(dirname "$0")"

# 激活 conda 环境
source ~/miniconda3/etc/profile.d/conda.sh
conda activate auto-dev

# 安装依赖
pip install gradio -q

# 启动
python app.py