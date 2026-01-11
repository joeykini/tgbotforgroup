import asyncio
from aiogram import executor
from loader import dp
import handlers

async def on_startup(dispatcher):
    print("Bot is starting...")

async def on_shutdown(dispatcher):
    print("Bot is shutting down...")

if __name__ == '__main__':
    # 注册所有 handlers
    handlers.setup_handlers()
    
    # 启动轮询
    executor.start_polling(dp, on_startup=on_startup, on_shutdown=on_shutdown, skip_updates=True)
