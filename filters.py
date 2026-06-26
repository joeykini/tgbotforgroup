import logging
import time

from aiogram import types
from aiogram.dispatcher.filters import BoundFilter

from loader import bot, db
from config import DefaultConfig

_admin_cache = {}


async def check_bot_admin(user_id: int) -> bool:
    """超级管理员，或淮安榜频道 / 麻辣鹅群组的管理员。"""
    if user_id == DefaultConfig.ADMIN_ID:
        return True

    now = time.time()
    cached = _admin_cache.get(user_id)
    if cached and cached[1] > now:
        return cached[0]

    admin_chats = db.get_setting("ADMIN_CHATS", DefaultConfig.ADMIN_CHATS)
    for chat_id in admin_chats:
        try:
            member = await bot.get_chat_member(chat_id=chat_id, user_id=user_id)
            if member.status in ("creator", "administrator"):
                _admin_cache[user_id] = (True, now + 300)
                return True
        except Exception as e:
            logging.debug("Admin check failed for %s in %s: %s", user_id, chat_id, e)

    _admin_cache[user_id] = (False, now + 60)
    return False


class AdminAccessFilter(BoundFilter):
    key = "admin_access"

    def __init__(self, admin_access=None):
        self.admin_access = admin_access

    async def check(self, event):
        user = getattr(event, "from_user", None)
        if not user:
            return False
        return await check_bot_admin(user.id)


def register_admin_filter(dispatcher):
    dispatcher.filters_factory.bind(
        AdminAccessFilter,
        event_handlers=[
            dispatcher.message_handlers,
            dispatcher.callback_query_handlers,
        ],
    )
