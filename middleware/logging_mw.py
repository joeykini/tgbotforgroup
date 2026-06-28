"""记录所有进入 Bot 的消息，便于排查群消息是否送达。"""
import logging

from aiogram import types
from aiogram.dispatcher.middlewares import BaseMiddleware

log = logging.getLogger("tg-updates")


class IncomingLogMiddleware(BaseMiddleware):
    async def on_pre_process_message(self, message: types.Message, data: dict):
        text = (message.text or message.caption or "")[:120]
        uid = message.from_user.id if message.from_user else "-"
        line = (
            f"[TG] chat={message.chat.id} ({message.chat.type}) "
            f"user={uid} text={text!r}"
        )
        log.info(line)
        print(line, flush=True)
