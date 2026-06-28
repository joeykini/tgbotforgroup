import asyncio
import logging
from aiogram import executor
from loader import dp, db
import handlers
from scheduler import scheduled_ad_task, scheduled_channel_sync_task
from channel_sync import sync_channel_to_db

async def on_startup(dispatcher):
    print("Bot is starting...")
    print("提示: 群内关键词需关闭 BotFather → Group Privacy，否则 Bot 收不到普通群消息")
    # 启动时立即同步一次，再进入定时轮询
    try:
        stats = sync_channel_to_db(db)
        print(f"频道同步完成: {stats['count']} 位老师")
    except Exception as e:
        logging.error("启动同步失败: %s", e)
    asyncio.create_task(scheduled_ad_task())
    asyncio.create_task(scheduled_channel_sync_task())

async def on_shutdown(dispatcher):
    print("Bot is shutting down...")

if __name__ == '__main__':
    # 注册所有 handlers
    handlers.setup_handlers()
    
    # 启动轮询
    executor.start_polling(dp, on_startup=on_startup, on_shutdown=on_shutdown, skip_updates=True, 
                           allowed_updates=["message", "callback_query", "chat_member", "inline_query"])
