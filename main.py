import asyncio
import logging
from aiogram import executor
from loader import dp, db, bot
import handlers
from scheduler import scheduled_ad_task, scheduled_channel_sync_task
from channel_sync import sync_channel_to_db

log = logging.getLogger("main")


async def on_startup(dispatcher):
    me = await bot.get_me()
    wh = await bot.get_webhook_info()
    print(f"Bot 启动: @{me.username} id={me.id}", flush=True)
    print(f"Webhook: url={wh.url or '(无)'} pending={wh.pending_update_count}", flush=True)
    if wh.url:
        await bot.delete_webhook(drop_pending_updates=False)
        print("已清除 webhook，改用 polling 收消息", flush=True)
    print("提示: 群内发任意消息时 bot.log 应出现 [TG] 行；若无则是 Bot 未收到群消息", flush=True)

    try:
        stats = sync_channel_to_db(db)
        print(f"频道同步完成: {stats['count']} 位老师", flush=True)
    except Exception as e:
        log.error("启动同步失败: %s", e)
    asyncio.create_task(scheduled_ad_task())
    asyncio.create_task(scheduled_channel_sync_task())

async def on_shutdown(dispatcher):
    print("Bot is shutting down...")

if __name__ == '__main__':
    # 注册所有 handlers
    handlers.setup_handlers()
    
    # 启动轮询
    executor.start_polling(
        dp,
        on_startup=on_startup,
        on_shutdown=on_shutdown,
        skip_updates=True,
        allowed_updates=[
            "message",
            "callback_query",
            "chat_member",
            "my_chat_member",
            "inline_query",
        ],
    )
