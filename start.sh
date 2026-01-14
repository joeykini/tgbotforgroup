#!/bin/bash
# 检查是否已经在运行
if pgrep -f main.py > /dev/null; then
    echo "Bot 已经在运行中。"
    exit 1
fi

nohup python3 main.py > bot.log 2>&1 &
echo "Bot 已在后台启动，日志请查看 bot.log"
