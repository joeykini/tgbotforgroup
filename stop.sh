#!/bin/bash
if pkill -f main.py; then
    echo "Bot 已停止运行"
else
    echo "未发现正在运行的 Bot 进程"
fi
