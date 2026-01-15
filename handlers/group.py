import asyncio
import time
from aiogram import types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ChatPermissions

from loader import dp, db, bot
from config import DefaultConfig
from utils import delete_later, check_group_admin

# ================= 群组管理逻辑 =================

# 1. 欢迎新成员
@dp.message_handler(content_types=types.ContentType.NEW_CHAT_MEMBERS)
async def welcome_new_member(message: types.Message):
    # 记录该群组
    if message.chat.type in [types.ChatType.GROUP, types.ChatType.SUPERGROUP]:
        db.add_group(message.chat.id, message.chat.title)

    if not db.get_setting("WELCOME_ENABLED", DefaultConfig.WELCOME_ENABLED): return

    # 如果是管理员/群主拉人进来，不需要欢迎
    if await check_group_admin(message):
        # 仍然可以删除进群服务消息（可选，通常群组会比较整洁）
        await delete_later(message, 120)
        return

    for member in message.new_chat_members:
        # 跳过所有机器人
        if member.is_bot:
            # 如果是本机器人被拉入，发送一个简单的招呼
            if member.id == bot.id:
                await message.reply("👋 大家好！我是群管机器人。如果是管理员，请给我管理员权限以便我正常工作。")
            continue
            
        # 强制硬编码链接
        link_newbie = "https://t.me/huaianbendi/6"
        
        link_rules = db.get_setting("LINK_RULES", DefaultConfig.LINK_RULES) or DefaultConfig.LINK_RULES
        link_safety = db.get_setting("LINK_SAFETY", DefaultConfig.LINK_SAFETY) or DefaultConfig.LINK_SAFETY
        link_terms = db.get_setting("LINK_TERMS", DefaultConfig.LINK_TERMS) or DefaultConfig.LINK_TERMS
        link_group = db.get_setting("LINK_GROUP", DefaultConfig.LINK_GROUP) or DefaultConfig.LINK_GROUP
        link_service = db.get_setting("LINK_SERVICE", DefaultConfig.LINK_SERVICE) or DefaultConfig.LINK_SERVICE

        # 匿名管理员处理
        if member.id == 1087968824: # GroupAnonymousBot ID
            name_link = "这位鹅友"
        else:
            name_link = f"[{member.full_name}](tg://user?id={member.id})"
        
        text = (
            "欢迎使用麻辣鹅系统\n"
            f"    {name_link} ，鹅友，您好!\n"
            f"🤗欢迎来到[麻辣鹅圈子]({link_group})，立即开始你的麻辣探索之旅吧；\n"
            f"    小鹅均为已验证资源!对眼有感即可冲，放心\"旅途\"，勿需多虑!\n"
            f"旅前须知:联系方式无条件获取，及时验证，请勿鸽人，素质诚信出击;[联系鹅神]({link_service})。\n"
            f"温馨提示:切勿相信任何非管理私聊，如有请避免踩雷[踩雷反馈]({link_service})\n"
            "雅俗共赏:行九浅而一深，待十侯而方毕\n"
            "小鹅状态: ♥️可约     😈 月休\n"
            f"安全须知1、[新人说明]({link_newbie}) 2、[群规及操作]({link_rules})\n\n"
            "小鹅，期待与您相约;祝\"旅途\"愉快!感谢支持"
        )
        bot_username = (await bot.get_me()).username
        kb = InlineKeyboardMarkup().add(InlineKeyboardButton("👊 😘立即启动😘 👊", url=f"https://t.me/{bot_username}?start=v"))
        sent_msg = await message.reply(text, parse_mode="Markdown", reply_markup=kb, disable_web_page_preview=True)
        await delete_later(sent_msg, 120)
            
    # 2分钟后删除进群服务消息
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

# 6. 群组关键词 "麻辣鹅"
@dp.message_handler(text_contains="麻辣鹅", chat_type=[types.ChatType.GROUP, types.ChatType.SUPERGROUP])
async def group_keyword_handler(message: types.Message):
    # 记录活跃群组
    db.add_group(message.chat.id, message.chat.title)
    
    if not db.get_setting("WELCOME_ENABLED", DefaultConfig.WELCOME_ENABLED): return
    
    # 匿名管理员处理
    if message.from_user.id == 1087968824 or message.sender_chat:
        name_link = "这位鹅友"
    else:
        name_link = f"[{message.from_user.full_name}](tg://user?id={message.from_user.id})"
        
    link_newbie = "https://t.me/huaianbendi/6" 
    link_rules = db.get_setting("LINK_RULES", DefaultConfig.LINK_RULES) or DefaultConfig.LINK_RULES
    link_safety = db.get_setting("LINK_SAFETY", DefaultConfig.LINK_SAFETY) or DefaultConfig.LINK_SAFETY
    link_group = db.get_setting("LINK_GROUP", DefaultConfig.LINK_GROUP) or DefaultConfig.LINK_GROUP
    link_service = db.get_setting("LINK_SERVICE", DefaultConfig.LINK_SERVICE) or DefaultConfig.LINK_SERVICE
        
    text = (
        "欢迎使用麻辣鹅系统\n"
        f"    {name_link} ，鹅友，您好!\n"
        f"🤗欢迎来到[麻辣鹅圈子]({link_group})，立即开始你的麻辣探索之旅吧；\n"
        f"    小鹅均为已验证资源!对眼有感即可冲，放心\"旅途\"，勿需多虑!\n"
        f"旅前须知:联系方式无条件获取，及时验证，请勿鸽人，素质诚信出击;[联系鹅神]({link_service})。\n"
        f"温馨提示:切勿相信任何非管理私聊，如有请避免踩雷[踩雷反馈]({link_service})\n"
        "雅俗共赏:行九浅而一深，待十侯而方毕\n"
        "小鹅状态: ♥️可约     😈 月休\n"
        f"安全须知1、[新人说明]({link_newbie}) 2、[群规及操作]({link_rules})\n\n"
        "小鹅，期待与您相约;祝\"旅途\"愉快!感谢支持"
    )
    
    bot_username = (await bot.get_me()).username
    kb = InlineKeyboardMarkup().add(InlineKeyboardButton("👊 😘立即启动😘 👊", url=f"https://t.me/{bot_username}?start=v"))
    
    sent_msg = await message.reply(text, parse_mode="Markdown", reply_markup=kb, disable_web_page_preview=True)
    await delete_later(sent_msg, 120)

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

    # 关键词回复检测 (只有主要没有违规链接才检测)
    if message.text:
        reply_content = db.get_keyword_reply(message.text)
        if reply_content:
            # 发送回复并5分钟(300秒)后删除
            sent_msg = await message.reply(reply_content)
            await delete_later(sent_msg, 300)
