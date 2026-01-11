import asyncio
import random
from aiogram import types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from loader import bot, db
from config import DefaultConfig

async def scheduled_ad_task():
    while True:
        # 动态获取间隔
        interval = db.get_setting("AD_INTERVAL", DefaultConfig.AD_INTERVAL)
        await asyncio.sleep(interval)
        
        # 获取所有广告并随机取一条
        ads = db.get_all_ads()
        if not ads:
            continue
            
        ad = random.choice(ads)
        content = ad['content']
        images = ad['images']
        buttons = ad.get('buttons', [])
        
        # 构造按钮
        kb = None
        if buttons:
            kb = InlineKeyboardMarkup(row_width=1)
            for btn in buttons:
                kb.add(InlineKeyboardButton(btn['text'], url=btn['url']))

        # 获取活跃群组
        groups = db.get_all_groups()
        
        for chat_id in groups:
            try:
                if images:
                    if len(images) == 1:
                        # 单张图片
                        await bot.send_photo(chat_id, images[0], caption=content, reply_markup=kb)
                    else:
                        # 多张图片 (MediaGroup)
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
                    # 纯文本
                    if content:
                        await bot.send_message(chat_id, content, reply_markup=kb)
            except Exception as e:
                # print(f"Error sending ad to {chat_id}: {e}")
                pass
            
            await asyncio.sleep(0.5)
