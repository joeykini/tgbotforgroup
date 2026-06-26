import asyncio
import logging
import random
from aiogram import types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from loader import bot, db
from config import DefaultConfig


async def scheduled_ad_task():
    while True:
        interval = db.get_setting("AD_INTERVAL", DefaultConfig.AD_INTERVAL)
        await asyncio.sleep(interval)

        ads = db.get_all_ads()
        if not ads:
            continue

        ad = random.choice(ads)
        content = ad['content']
        images = ad['images']
        buttons = ad.get('buttons', [])

        kb = None
        if buttons:
            kb = InlineKeyboardMarkup(row_width=1)
            for btn in buttons:
                kb.add(InlineKeyboardButton(btn['text'], url=btn['url']))

        groups = db.get_all_groups()

        for chat_id in groups:
            try:
                if images:
                    if len(images) == 1:
                        await bot.send_photo(chat_id, images[0], caption=content, reply_markup=kb)
                    else:
                        media = types.MediaGroup()
                        for i, img_id in enumerate(images):
                            if i == 0:
                                media.attach_photo(img_id, caption=content)
                            else:
                                media.attach_photo(img_id)
                        await bot.send_media_group(chat_id, media=media)
                        if kb:
                            await bot.send_message(chat_id, "👇 点击下方按钮了解更多：", reply_markup=kb)
                else:
                    if content:
                        await bot.send_message(chat_id, content, reply_markup=kb)
            except Exception:
                pass

            await asyncio.sleep(0.5)


async def scheduled_channel_sync_task():
    """每 N 小时从淮安榜频道同步老师资源。"""
    from channel_sync import sync_channel_to_db
    while True:
        interval = db.get_setting("SYNC_INTERVAL", DefaultConfig.SYNC_INTERVAL)
        await asyncio.sleep(interval)
        try:
            sync_channel_to_db(db)
        except Exception as e:
            logging.error("频道同步失败: %s", e)
