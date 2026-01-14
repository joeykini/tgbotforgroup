#!/bin/bash
# 检查是否存在虚拟环境
if [ -d "venv" ]; then
    PYTHON_EXEC="venv/bin/python3"
else
    PYTHON_EXEC="python3"
fi

# 检查是否已经在运行
if pgrep -f main.py > /dev/null; then
    echo "Bot 已经在运行中。"
    exit 1
fi

nohup $PYTHON_EXEC main.py > bot.log 2>&1 &
echo "Bot 已在后台启动 (使用 $PYTHON_EXEC)，日志请查看 bot.log"
