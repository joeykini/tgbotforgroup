import asyncio
import time
from aiogram import types
from aiogram.dispatcher import FSMContext
from aiogram.types import ChatPermissions

from loader import dp, db, bot
from config import DefaultConfig
from utils import delete_later, check_group_admin
from states import ReportStates
from report_utils import REPORT_TEMPLATE, get_report_kb

# ================= 群组管理逻辑 =================


def _is_other_bot(message: types.Message) -> bool:
    return message.from_user and message.from_user.is_bot and message.from_user.id != bot.id


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

        name_link = "这位鹅友" if member.id == 1087968824 else f"[{member.full_name}](tg://user?id={member.id})"
        text = (
            f"👋 {name_link} 欢迎加入！\n"
            f"发送 **麻辣鹅** 获取 [淮安榜](https://t.me/huaianbendi) 实时资源\n"
            f"发送区县名（如 `清江浦`）按地区查看"
        )
        sent_msg = await message.reply(text, parse_mode="Markdown", disable_web_page_preview=True)
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


# 关键词「麻辣鹅」
@dp.message_handler(text_contains="麻辣鹅", chat_type=[types.ChatType.GROUP, types.ChatType.SUPERGROUP])
async def group_keyword_handler(message: types.Message):
    if _is_other_bot(message):
        return

    db.add_group(message.chat.id, message.chat.title)
    reply_content = db.get_keyword_reply(message.text)
    if not reply_content:
        reply_content = "🦢 发送 **麻辣鹅** 获取淮安榜资源\n发送区县名（如 `清江浦`）按地区查看"

    sent_msg = await message.reply(
        reply_content, parse_mode="Markdown", disable_web_page_preview=True
    )
    await delete_later(sent_msg, 300)


@dp.message_handler(
    lambda m: m.text and m.text.startswith("报告"),
    chat_type=[types.ChatType.GROUP, types.ChatType.SUPERGROUP],
    state="*",
)
async def group_report_start(message: types.Message, state: FSMContext):
    if _is_other_bot(message):
        return

    if state:
        await state.finish()
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.reply("📝 请输入：`报告 小鹅名字`", parse_mode="Markdown")
        return

    mascot_name = parts[1].strip()
    await state.update_data(report_mascot=mascot_name, target_chat=str(message.chat.id))
    await ReportStates.WAITING_FOR_REPORT_CONTENT.set()

    text = (
        f"麻辣鹅「报告模版」· #{mascot_name}\n"
        f"请 **直接在本群** 发送填好的报告（可附图/视频）\n"
        f"如需匿名，内容中加 **我要匿名**\n\n"
        f"`{REPORT_TEMPLATE.format(mascot_name=mascot_name)}`"
    )
    sent_msg = await message.reply(text, parse_mode="Markdown")
    await delete_later(sent_msg, 300)
    await delete_later(message, 60)


@dp.message_handler(
    lambda m: m.text and m.text.startswith("看报告"),
    chat_type=[types.ChatType.GROUP, types.ChatType.SUPERGROUP],
    state="*",
)
async def group_view_reports(message: types.Message, state: FSMContext = None):
    if _is_other_bot(message):
        return

    if state:
        await state.finish()
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.reply("📝 请输入：`看报告 小鹅名字`")
        return

    mascot_name = parts[1].strip()
    reports = db.get_reports_by_mascot(mascot_name)
    if not reports:
        sent = await message.reply(f"🔍 暂无 `#{mascot_name}` 的实操报告", parse_mode="Markdown")
        await delete_later(sent, 120)
        return

    await message.reply(f"📚 `#{mascot_name}` 的实操报告：", parse_mode="Markdown")
    for r in reports:
        likes = len(r["likes"])
        dislikes = len(r["dislikes"])
        text = f"👤 报告人ID: {r['user_id']} (👍{likes} 👎{dislikes})\n\n{r['content']}"
        kb = get_report_kb(r["id"], likes, dislikes)
        try:
            if r["media_type"] == "photo":
                await message.answer_photo(r["media_id"], caption=text, reply_markup=kb, parse_mode="Markdown")
            elif r["media_type"] == "video":
                await message.answer_video(r["media_id"], caption=text, reply_markup=kb, parse_mode="Markdown")
            else:
                await message.answer(text, reply_markup=kb, parse_mode="Markdown")
        except Exception:
            pass
    await delete_later(message, 60)


# 用户记录 & 防链接（跳过所有 Bot 消息，不影响定时广告 Bot）
@dp.message_handler(content_types=types.ContentType.ANY, chat_type=[types.ChatType.GROUP, types.ChatType.SUPERGROUP])
async def group_message_logger(message: types.Message):
    if _is_other_bot(message):
        return

    username = message.from_user.username or message.from_user.full_name
    db.log_user(message.from_user.id, username, is_group=True)
    db.add_group(message.chat.id, message.chat.title)

    if not db.get_setting("ANTI_LINK_ENABLED", DefaultConfig.ANTI_LINK_ENABLED):
        pass
    elif not await check_group_admin(message) and message.text:
        text = message.text.lower()
        if "http://" in text or "https://" in text or "t.me/" in text:
            try:
                await message.delete()
                warning = await message.answer(
                    f"⚠️ {message.from_user.get_mention(as_html=True)} 本群禁止发送外部链接！",
                    parse_mode="HTML",
                )
                await asyncio.sleep(5)
                await warning.delete()
            except Exception:
                return

    if message.text and "麻辣鹅" not in message.text:
        reply_content = db.get_keyword_reply(message.text)
        if reply_content:
            sent_msg = await message.reply(
                reply_content, parse_mode="Markdown", disable_web_page_preview=True
            )
            await delete_later(sent_msg, 300)
