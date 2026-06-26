import asyncio
import time
from aiogram import types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ChatPermissions

from loader import dp, db, bot
from config import DefaultConfig
from utils import delete_later, check_group_admin

# ================= 群组管理逻辑 =================

# 1. 入群处理：踢出 Bot，可选简短欢迎
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
                    "请授予管理员权限，以便自动拦截 Bot 和维护群秩序。"
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
            f"或私聊 @{bot_username} 浏览完整列表"
        )
        kb = InlineKeyboardMarkup().add(
            InlineKeyboardButton("😘 立即启动", url=f"https://t.me/{bot_username}?start=v")
        )
        sent_msg = await message.reply(text, parse_mode="Markdown", reply_markup=kb, disable_web_page_preview=True)
        await delete_later(sent_msg, 120)

    await delete_later(message, 120)


# 另外处理退群消息
@dp.message_handler(content_types=types.ContentType.LEFT_CHAT_MEMBER)
async def goodbye_member(message: types.Message):
    # 2分钟后删除退群消息
    await delete_later(message, 120)


# 2. 禁言 (Reply模式)
@dp.message_handler(commands=['mute'], is_chat_admin=True)
async def cmd_mute(message: types.Message):
    if not message.reply_to_message:
        await message.reply("⚠️ 请回复要禁言的用户消息。")
        return
    
    args = message.get_args().split()
    duration = 60 # 默认60秒
    if args and args[0].isdigit():
        duration = int(args[0]) * 60 # 输入分钟
    
    try:
        until_date = int(time.time()) + duration
        await bot.restrict_chat_member(
            chat_id=message.chat.id,
            user_id=message.reply_to_message.from_user.id,
            permissions=ChatPermissions(can_send_messages=False),
            until_date=until_date
        )
        await message.reply(f"🔇 用户已被禁言 {duration // 60} 分钟。")
    except Exception as e:
        await message.reply(f"❌ 操作失败: {e}")

# 3. 解除禁言
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
                can_send_other_messages=True
            )
        )
        await message.reply("🔊 用户已解除禁言。")
    except Exception as e:
        await message.reply(f"❌ 操作失败: {e}")

# 4. 踢出成员
@dp.message_handler(commands=['kick', 'ban'], is_chat_admin=True)
async def cmd_kick(message: types.Message):
    if not message.reply_to_message:
        await message.reply("⚠️ 请回复要踢出的用户消息。")
        return
    try:
        await bot.kick_chat_member(
            chat_id=message.chat.id,
            user_id=message.reply_to_message.from_user.id
        )
        await message.reply("👋 用户已被踢出群组。")
    except Exception as e:
        await message.reply(f"❌ 操作失败: {e}")

# 6. 关键词「麻辣鹅」→ 使用同步后的关键词回复
@dp.message_handler(text_contains="麻辣鹅", chat_type=[types.ChatType.GROUP, types.ChatType.SUPERGROUP])
async def group_keyword_handler(message: types.Message):
    db.add_group(message.chat.id, message.chat.title)

    reply_content = db.get_keyword_reply(message.text)
    if not reply_content:
        bot_username = (await bot.get_me()).username
        reply_content = (
            "🦢 发送 **麻辣鹅** 获取淮安榜资源\n"
            f"私聊 @{bot_username} 浏览完整列表"
        )

    bot_username = (await bot.get_me()).username
    kb = InlineKeyboardMarkup().add(
        InlineKeyboardButton("😘 立即启动", url=f"https://t.me/{bot_username}?start=v")
    )
    sent_msg = await message.reply(
        reply_content, parse_mode="Markdown", reply_markup=kb, disable_web_page_preview=True
    )
    await delete_later(sent_msg, 300)

@dp.message_handler(lambda m: m.text and m.text.startswith("报告"), chat_type=[types.ChatType.GROUP, types.ChatType.SUPERGROUP])
async def group_report_trigger(message: types.Message):
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        return # 忽略只有 "报告" 的消息，或者提示
    
    mascot_name = parts[1].strip()
    bot_info = await bot.get_me()
    # 构造深层链接跳转私聊并自动带出报告指令
    # start 参数限制：[a-zA-Z0-9_-]，负号用 n 代替
    chat_id_str = str(message.chat.id).replace("-", "n")
    deep_link = f"https://t.me/{bot_info.username}?start=report_{mascot_name}_{chat_id_str}"
    
    kb = InlineKeyboardMarkup().add(InlineKeyboardButton("📝 点击此处私聊提交报告", url=deep_link))
    sent_msg = await message.reply(f"🔍 收到您的反馈请求：`#{mascot_name}`\n请点击下方按钮进入私聊获取模版。", 
                                   parse_mode="Markdown", reply_markup=kb)
    await delete_later(sent_msg, 60)
    await delete_later(message, 60)

@dp.message_handler(lambda m: m.text and m.text.startswith("看报告"), chat_type=[types.ChatType.GROUP, types.ChatType.SUPERGROUP])
async def group_view_reports_trigger(message: types.Message):
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2: return
    
    mascot_name = parts[1].strip()
    bot_info = await bot.get_me()
    # 构造深层链接跳转私聊并查看报告
    deep_link = f"https://t.me/{bot_info.username}?start=view_report_{mascot_name}"
    
    kb = InlineKeyboardMarkup().add(InlineKeyboardButton("📚 点击此处私聊查看报告", url=deep_link))
    sent_msg = await message.reply(f"🔍 正在查询 `#{mascot_name}` 的实操报告...\n请点击下方按钮进入私聊查看。", 
                                   parse_mode="Markdown", reply_markup=kb)
    await delete_later(sent_msg, 60)
    await delete_later(message, 60)

# 5. 用户记录 & 防链接监控
@dp.message_handler(content_types=types.ContentType.ANY, chat_type=[types.ChatType.GROUP, types.ChatType.SUPERGROUP])
async def group_message_logger(message: types.Message):
    # 记录用户信息和统计消息
    username = message.from_user.username or message.from_user.full_name
    db.log_user(message.from_user.id, username, is_group=True)
    
    # 记录该群组
    db.add_group(message.chat.id, message.chat.title)

    if not db.get_setting("ANTI_LINK_ENABLED", DefaultConfig.ANTI_LINK_ENABLED): return
    
    # 忽略管理员
    if await check_group_admin(message): return
    
    # 简单检测 http/https/t.me
    if not message.text:
        return
        
    text = message.text.lower()
    if 'http://' in text or 'https://' in text or 't.me/' in text:
        try:
            await message.delete()
            # 发送警告消息，5秒后自动删除
            warning = await message.answer(f"⚠️ {message.from_user.get_mention(as_html=True)} 本群禁止发送外部链接！", parse_mode="HTML")
            await asyncio.sleep(5)
            await warning.delete()
        except:
            pass # 可能没有删除权限
            return

    if message.text and "麻辣鹅" not in message.text:
        reply_content = db.get_keyword_reply(message.text)
        if reply_content:
            sent_msg = await message.reply(
                reply_content, parse_mode="Markdown", disable_web_page_preview=True
            )
            await delete_later(sent_msg, 300)
            return
