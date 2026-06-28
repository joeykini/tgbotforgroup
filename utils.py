import asyncio
import logging
from aiogram import types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from loader import bot, db
from config import DefaultConfig

# ================= 辅助函数 =================

# ================= 消息计时管理 =================

class MessageTimerManager:
    def __init__(self):
        self.timers = {} # {(chat_id, message_id): asyncio.Task}

    async def start_timer(self, message: types.Message, delay: int = 120):
        key = (message.chat.id, message.message_id)
        # 如果已经有计时器在运行，先取消它
        self.cancel_timer(message.chat.id, message.message_id)
        
        task = asyncio.create_task(self._delete_task(message, delay))
        self.timers[key] = task

    def cancel_timer(self, chat_id: int, message_id: int):
        key = (chat_id, message_id)
        if key in self.timers:
            self.timers[key].cancel()
            del self.timers[key]

    async def _delete_task(self, message: types.Message, delay: int):
        try:
            await asyncio.sleep(delay)
            await message.delete()
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logging.debug(f"Failed to delete message {message.message_id} in chat {message.chat.id}: {e}")
        finally:
            key = (message.chat.id, message.message_id)
            if self.timers.get(key) == asyncio.current_task():
                self.timers.pop(key, None)

timer_manager = MessageTimerManager()

async def delete_later(message: types.Message, delay: int = 120):
    """延迟删除消息，并记录到计时管理器"""
    if not message: return
    await timer_manager.start_timer(message, delay)

async def reset_message_timer(message: types.Message, delay: int = 120):
    """重置消息的删除计时"""
    if not message: return
    await timer_manager.start_timer(message, delay)

def is_admin(user_id):
    """同步快捷判断：仅超级管理员。完整权限请用 check_bot_admin。"""
    return user_id == DefaultConfig.ADMIN_ID

async def is_bot_admin(user_id):
    from filters import check_bot_admin
    return await check_bot_admin(user_id)

async def check_group_admin(message: types.Message):
    """检查命令发送者是否为群管理员或 Bot 后台管理员。"""
    if message.chat.type == 'private':
        if not message.from_user:
            return False
        return await is_bot_admin(message.from_user.id)
    # 匿名管理员以群名义发言
    if not message.from_user and message.sender_chat and message.sender_chat.id == message.chat.id:
        return True
    if not message.from_user:
        return False
    if await is_bot_admin(message.from_user.id):
        return True
    member = await bot.get_chat_member(message.chat.id, message.from_user.id)
    return member.is_chat_admin()

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
