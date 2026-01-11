import asyncio
import logging
from aiogram import types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from loader import bot, db
from config import DefaultConfig

# ================= 辅助函数 =================

async def delete_later(message: types.Message, delay: int):
    """延迟删除消息"""
    await asyncio.sleep(delay)
    try:
        await message.delete()
    except:
        pass

def is_admin(user_id):
    return user_id == DefaultConfig.ADMIN_ID

async def check_group_admin(message: types.Message):
    """检查命令发送者是否为群管理员"""
    if message.chat.type == 'private':
        return False
    member = await bot.get_chat_member(message.chat.id, message.from_user.id)
    return member.is_chat_admin() or is_admin(message.from_user.id)

async def check_subscription(user_id):
    """检查用户是否关注了所有必选频道"""
    required_channels = db.get_setting("REQUIRED_CHANNELS", DefaultConfig.REQUIRED_CHANNELS)
    if not required_channels:
        return []
    
    not_joined = []
    for channel in required_channels:
        try:
            member = await bot.get_chat_member(chat_id=channel["id"], user_id=user_id)
            if member.status not in ['creator', 'administrator', 'member']:
                not_joined.append(channel)
        except Exception as e:
            # 如果机器人不是管理员或者频道不存在，可能会报错，默认视为未加入或忽略
            logging.error(f"Error checking sub for {channel['id']}: {e}")
            not_joined.append(channel) # 安全起见，报错也算未加入，提示用户检查
    return not_joined

def get_subscription_keyboard(not_joined_channels):
    """生成强制关注的键盘"""
    keyboard = InlineKeyboardMarkup(row_width=1)
    for channel in not_joined_channels:
        keyboard.add(InlineKeyboardButton(f"👉 加入 {channel['name']}", url=channel["url"]))
    
    keyboard.add(InlineKeyboardButton("✅ 我已加入 (点击验证)", callback_data="check_sub"))
    return keyboard
