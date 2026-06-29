import asyncio
import logging
import time
from aiogram import types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ChatPermissions

from loader import dp, db, bot
from config import DefaultConfig
from channel_sync import PRICE_KEYWORDS, REGIONS
from utils import delete_later, check_group_admin

log = logging.getLogger(__name__)
GROUP_CHAT_TYPES = [types.ChatType.GROUP, types.ChatType.SUPERGROUP]

# ================= 群组管理逻辑 =================


def _is_other_bot(message: types.Message) -> bool:
    return message.from_user and message.from_user.is_bot and message.from_user.id != bot.id


def _is_anonymous_group_admin(message: types.Message) -> bool:
    """Telegram 匿名管理员：消息以群名义发出，from_user 为空。"""
    if message.from_user:
        return False
    sc = message.sender_chat
    return bool(sc and sc.id == message.chat.id)


def _should_ignore_group_message(message: types.Message) -> bool:
    """忽略其他 Bot；忽略频道代发等非匿名管理员的 sender_chat 消息。"""
    if _is_other_bot(message):
        return True
    if message.from_user:
        return False
    # 匿名管理员可继续处理；其他无 from_user 的消息跳过
    return not _is_anonymous_group_admin(message)


def _log_group_message(message: types.Message) -> None:
    db.add_group(message.chat.id, message.chat.title)
    if message.from_user:
        username = message.from_user.username or message.from_user.full_name
        db.log_user(message.from_user.id, username, is_group=True)
    elif _is_anonymous_group_admin(message):
        log.info("匿名管理员群消息 chat=%s text=%r", message.chat.id, (message.text or "")[:40])


async def _private_start_kb():
    bot_username = (await bot.get_me()).username
    return InlineKeyboardMarkup().add(
        InlineKeyboardButton("😘 立即启动", url=f"https://t.me/{bot_username}?start=v")
    )


def _mala_fallback_text(bot_username: str) -> str:
    regions = " · ".join(f"`{r}`" for r in REGIONS[:4]) + " …"
    tiers = " · ".join(f"`{t}`" for t in PRICE_KEYWORDS)
    return (
        "🦢 **麻辣鹅 · 淮安榜资源**\n\n"
        f"发送地区名查看在榜老师，例如：{regions}\n"
        f"按价格档：{tiers}\n\n"
        f"私聊 @{bot_username} 浏览完整按钮列表"
    )


def _is_group_chat(message: types.Message) -> bool:
    return message.chat.type in (types.ChatType.GROUP, types.ChatType.SUPERGROUP, "group", "supergroup")


async def _send_keyword_reply(message: types.Message) -> bool:
    """统一关键词回复：含 Markdown 失败降级为纯文本。"""
    if not message.text:
        return False

    reply_content = db.get_keyword_reply(message.text)
    if not reply_content and "麻辣鹅" in message.text:
        bot_username = (await bot.get_me()).username
        reply_content = _mala_fallback_text(bot_username)

    if not reply_content:
        return False

    log.info("群关键词命中 chat=%s text=%r", message.chat.id, message.text[:40])

    kb = await _private_start_kb()
    attempts = [
        {"parse_mode": "Markdown", "reply_markup": kb},
        {"reply_markup": kb},
        {},  # 纯文本，无按钮（最后兜底）
    ]
    last_err = None
    for opts in attempts:
        try:
            sent_msg = await message.reply(
                reply_content,
                disable_web_page_preview=True,
                **opts,
            )
            await delete_later(sent_msg, 300)
            return True
        except Exception as e:
            last_err = e
            log.warning("关键词回复尝试失败 (%s): %s", opts or "plain", e)
    log.error("关键词回复全部失败: %s", last_err)
    return False


# 1. 入群处理：默认不自动踢 Bot，仅欢迎真人
@dp.message_handler(content_types=types.ContentType.NEW_CHAT_MEMBERS)
async def welcome_new_member(message: types.Message):
    if message.chat.type in [types.ChatType.GROUP, types.ChatType.SUPERGROUP]:
        db.add_group(message.chat.id, message.chat.title)

    anti_bot = db.get_setting("ANTI_BOT_ENABLED", DefaultConfig.ANTI_BOT_ENABLED)
    welcome_on = db.get_setting("WELCOME_ENABLED", DefaultConfig.WELCOME_ENABLED)

    for member in message.new_chat_members:
        if member.is_bot:
            if member.id == bot.id:
                await message.reply(
                    "👋 大家好！我是群管机器人。\n"
                    "请授予管理员权限，以便维护群秩序。\n"
                    "管理员可用 /kickbot 移除广告 Bot，/del 删除消息。"
                )
            elif anti_bot:
                try:
                    await bot.kick_chat_member(message.chat.id, member.id)
                    notice = await message.reply(f"🚫 已移除非授权 Bot：{member.full_name}")
                    await delete_later(notice, 30)
                except Exception:
                    pass
            continue

        if not welcome_on:
            continue

        bot_username = (await bot.get_me()).username
        name_link = "这位鹅友" if member.id == 1087968824 else f"[{member.full_name}](tg://user?id={member.id})"
        text = (
            f"👋 {name_link} 欢迎加入！\n"
            f"发送 **麻辣鹅** 获取 [淮安榜](https://t.me/huaianbendi) 实时资源\n"
            f"发送区县名（如 `清江浦`）按地区查看\n"
            f"或私聊 @{bot_username} 浏览完整列表"
        )
        kb = await _private_start_kb()
        sent_msg = await message.reply(
            text, parse_mode="Markdown", reply_markup=kb, disable_web_page_preview=True
        )
        await delete_later(sent_msg, 120)

    await delete_later(message, 120)


@dp.message_handler(content_types=types.ContentType.LEFT_CHAT_MEMBER)
async def goodbye_member(message: types.Message):
    await delete_later(message, 120)


# 2. 禁言 (Reply模式)
@dp.message_handler(commands=['mute'], is_chat_admin=True)
async def cmd_mute(message: types.Message):
    if not message.reply_to_message:
        await message.reply("⚠️ 请回复要禁言的用户消息。")
        return

    args = message.get_args().split()
    duration = 60
    if args and args[0].isdigit():
        duration = int(args[0]) * 60

    try:
        until_date = int(time.time()) + duration
        await bot.restrict_chat_member(
            chat_id=message.chat.id,
            user_id=message.reply_to_message.from_user.id,
            permissions=ChatPermissions(can_send_messages=False),
            until_date=until_date,
        )
        await message.reply(f"🔇 用户已被禁言 {duration // 60} 分钟。")
    except Exception as e:
        await message.reply(f"❌ 操作失败: {e}")


@dp.message_handler(commands=['unmute'], is_chat_admin=True)
async def cmd_unmute(message: types.Message):
    if not message.reply_to_message:
        await message.reply("⚠️ 请回复要解除禁言的用户消息。")
        return
    try:
        await bot.restrict_chat_member(
            chat_id=message.chat.id,
            user_id=message.reply_to_message.from_user.id,
            permissions=ChatPermissions(
                can_send_messages=True,
                can_send_media_messages=True,
                can_send_other_messages=True,
            ),
        )
        await message.reply("🔊 用户已解除禁言。")
    except Exception as e:
        await message.reply(f"❌ 操作失败: {e}")


@dp.message_handler(commands=['kick', 'ban'], is_chat_admin=True)
async def cmd_kick(message: types.Message):
    if not message.reply_to_message:
        await message.reply("⚠️ 请回复要踢出的用户消息。")
        return
    try:
        await bot.kick_chat_member(
            chat_id=message.chat.id,
            user_id=message.reply_to_message.from_user.id,
        )
        await message.reply("👋 用户已被踢出群组。")
    except Exception as e:
        await message.reply(f"❌ 操作失败: {e}")


@dp.message_handler(commands=['kickbot'], is_chat_admin=True)
async def cmd_kickbot(message: types.Message):
    """回复某条 Bot 消息，将其移出群组。"""
    if not message.reply_to_message:
        await message.reply("⚠️ 请回复要移除的 Bot 消息。")
        return
    target = message.reply_to_message.from_user
    if not target or not target.is_bot:
        await message.reply("⚠️ 目标不是 Bot。")
        return
    if target.id == bot.id:
        await message.reply("⚠️ 不能移除本群管 Bot。")
        return
    try:
        await bot.kick_chat_member(message.chat.id, target.id)
        try:
            await message.reply_to_message.delete()
        except Exception:
            pass
        notice = await message.reply(f"🚫 已移除 Bot：{target.full_name}")
        await delete_later(notice, 30)
        await delete_later(message, 30)
    except Exception as e:
        await message.reply(f"❌ 操作失败: {e}")


@dp.message_handler(commands=['grptest'])
async def cmd_grptest(message: types.Message):
    """群内自检：确认 Bot 能收到群消息。"""
    if not _is_group_chat(message):
        await message.reply("此命令请在群组里使用。")
        return
    me = await bot.get_me()
    await message.reply(
        f"✅ 群消息已收到（Bot @{me.username} id={me.id}）。\n"
        "请再发「麻辣鹅」测试关键词；多 Bot 同群时命令需写成 "
        f"/grptest@{me.username}"
    )


@dp.my_chat_member_handler()
async def on_bot_chat_member(event: types.ChatMemberUpdated):
    me = await bot.get_me()
    if event.new_chat_member.user.id != me.id:
        return
    status = event.new_chat_member.status
    print(
        f"[BOT] 成员状态变更 chat={event.chat.id} ({event.chat.title}) status={status}",
        flush=True,
    )


@dp.message_handler(commands=['del'], is_chat_admin=True)
async def cmd_del(message: types.Message):
    """回复任意消息并删除（含其他 Bot 的定时广告）。"""
    if not message.reply_to_message:
        await message.reply("⚠️ 请回复要删除的消息。")
        return
    try:
        await message.reply_to_message.delete()
        await delete_later(message, 10)
    except Exception as e:
        await message.reply(f"❌ 删除失败: {e}")


@dp.message_handler(lambda m: _is_group_chat(m) and m.text and m.text.startswith("报告"))
async def group_report_trigger(message: types.Message):
    if _is_other_bot(message):
        return

    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        return

    mascot_name = parts[1].strip()
    bot_info = await bot.get_me()
    chat_id_str = str(message.chat.id).replace("-", "n")
    deep_link = f"https://t.me/{bot_info.username}?start=report_{mascot_name}_{chat_id_str}"

    kb = InlineKeyboardMarkup().add(
        InlineKeyboardButton("📝 点击此处私聊提交报告", url=deep_link)
    )
    sent_msg = await message.reply(
        f"🔍 收到您的反馈请求：`#{mascot_name}`\n请点击下方按钮进入私聊获取模版。",
        parse_mode="Markdown",
        reply_markup=kb,
    )
    await delete_later(sent_msg, 60)
    await delete_later(message, 60)


@dp.message_handler(lambda m: _is_group_chat(m) and m.text and m.text.startswith("看报告"))
async def group_view_reports_trigger(message: types.Message):
    if _is_other_bot(message):
        return

    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        return

    mascot_name = parts[1].strip()
    bot_info = await bot.get_me()
    deep_link = f"https://t.me/{bot_info.username}?start=view_report_{mascot_name}"

    kb = InlineKeyboardMarkup().add(
        InlineKeyboardButton("📚 点击此处私聊查看报告", url=deep_link)
    )
    sent_msg = await message.reply(
        f"🔍 正在查询 `#{mascot_name}` 的实操报告...\n请点击下方按钮进入私聊查看。",
        parse_mode="Markdown",
        reply_markup=kb,
    )
    await delete_later(sent_msg, 60)
    await delete_later(message, 60)


# 群文本：统计 + 防外链 + 关键词（过滤条件写在装饰器里，避免吞掉私聊消息）
@dp.message_handler(
    lambda m: _is_group_chat(m) and bool(m.text) and not m.text.startswith("/"),
    content_types=types.ContentType.TEXT,
)
async def group_text_handler(message: types.Message):
    if _should_ignore_group_message(message):
        return

    _log_group_message(message)

    if db.get_setting("ANTI_LINK_ENABLED", DefaultConfig.ANTI_LINK_ENABLED):
        if not await check_group_admin(message):
            text = message.text.lower()
            if "http://" in text or "https://" in text or "t.me/" in text:
                try:
                    await message.delete()
                    if message.from_user:
                        warn_text = f"⚠️ {message.from_user.get_mention(as_html=True)} 本群禁止发送外部链接！"
                    else:
                        warn_text = "⚠️ 本群禁止发送外部链接！"
                    warning = await message.answer(warn_text, parse_mode="HTML")
                    await asyncio.sleep(5)
                    await warning.delete()
                except Exception as e:
                    log.debug("防外链处理失败: %s", e)
                return

    await _send_keyword_reply(message)


@dp.message_handler(
    lambda m: _is_group_chat(m),
    content_types=[
        types.ContentType.PHOTO,
        types.ContentType.VIDEO,
        types.ContentType.DOCUMENT,
        types.ContentType.STICKER,
        types.ContentType.VOICE,
        types.ContentType.AUDIO,
    ],
)
async def group_media_logger(message: types.Message):
    if _should_ignore_group_message(message):
        return
    _log_group_message(message)
