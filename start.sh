#!/bin/bash
# 检查是否存在虚拟环境
if [ -d "venv" ]; then
    PYTHON_EXEC="venv/bin/python3"
else
    PYTHON_EXEC="python3"
fi

# 加载 .env（若存在）
if [ -f ".env" ]; then
    set -a
    # shellcheck disable=SC1091
    source ./.env
    set +a
fi

# 检查是否已经在运行
if pgrep -f main.py > /dev/null; then
    echo "Bot 已经在运行中。"
    exit 1
fi

if [ -z "$BOT_API_TOKEN" ] || [ -z "$BOT_ADMIN_ID" ]; then
    echo "错误: 请先配置 .env（参考 .env.example）"
    exit 1
fi

nohup $PYTHON_EXEC main.py >> bot.log 2>&1 &
sleep 2
if ! pgrep -f main.py > /dev/null; then
    echo "错误: Bot 启动后立即退出，请查看 bot.log："
    tail -20 bot.log
    exit 1
fi
echo "Bot 已在后台启动 (使用 $PYTHON_EXEC)，日志请查看 bot.log"
tail -3 bot.log 2>/dev/null || true
