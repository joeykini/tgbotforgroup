import asyncio
from aiogram import types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.dispatcher import FSMContext

from loader import dp, db, bot
from config import DefaultConfig
from states import ReportStates
from utils import delete_later, check_subscription, get_subscription_keyboard

# ================= 私聊/菜单逻辑 =================

# 1. /start 命令 (带强制关注检测)
@dp.message_handler(commands=['start'], chat_type=types.ChatType.PRIVATE)
async def cmd_start(message: types.Message):
    # 检测关注状态
    not_joined = await check_subscription(message.from_user.id)
    contact_user = db.get_setting("CONTACT_USER", DefaultConfig.CONTACT_USER)
    contact_url = db.get_setting("CONTACT_URL", DefaultConfig.CONTACT_URL)
    link_huaian = db.get_setting("LINK_HUAIAN", DefaultConfig.LINK_HUAIAN)

    if not_joined:
        text = (
            "麻辣鹅「淮安榜提示」\n\n"
            f"鹅友，你好！请先加入 [淮安榜]({link_huaian}) !\n\n"
            "因telegram官方升级,内链机器人无法加载小鹅资料\n\n"
            "出于安全、隐私，淮安榜也将升级私有频道\n\n"
            "如有打扰，深感抱歉；\n\n"
            "👇 未完成关注列表：\n"
        )
        for channel in not_joined:
            text += f"{channel['name']} 状态: left\n"
        
        # 发送消息并设置2分钟(120秒)后删除
        sent_msg = await message.answer(text, reply_markup=get_subscription_keyboard(not_joined), parse_mode="Markdown", disable_web_page_preview=True)
        asyncio.create_task(delete_later(sent_msg, 120))
        return

    name_link = f"[{message.from_user.full_name}](tg://user?id={message.from_user.id})"
    
    # 强制硬编码链接，避免数据库问题
    link_newbie = "https://t.me/huaianbendi/6"
    
    # 其他链接继续使用配置
    link_service = db.get_setting("LINK_SERVICE", DefaultConfig.LINK_SERVICE) or DefaultConfig.LINK_SERVICE
    link_rules = db.get_setting("LINK_RULES", DefaultConfig.LINK_RULES) or DefaultConfig.LINK_RULES
    link_safety = db.get_setting("LINK_SAFETY", DefaultConfig.LINK_SAFETY) or DefaultConfig.LINK_SAFETY
    link_group = db.get_setting("LINK_GROUP", DefaultConfig.LINK_GROUP) or DefaultConfig.LINK_GROUP

    success_text = (
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
    
    # --- Dynamic Start Menu Buttons ---
    start_items = db.get_start_menu_items()
    kb = InlineKeyboardMarkup(row_width=2)
    for item in start_items:
        kb.insert(InlineKeyboardButton(item['text'], callback_data=f"start_menu_{item['id']}"))
    
    # Send Welcome Message
    sent_msg = await message.answer(success_text, parse_mode="Markdown", reply_markup=kb, disable_web_page_preview=True)
    
    # 2分钟后自动删除
    asyncio.create_task(delete_later(sent_msg, 120))
    asyncio.create_task(delete_later(message, 120))

# ================= Start Menu Callback Handler (Auto-Delete & Refresh) =================
@dp.callback_query_handler(text_startswith="start_menu_")
async def start_menu_item_handler(call: types.CallbackQuery):
    item_id = int(call.data.split("_")[-1])
    item = db.get_start_menu_item(item_id)
    
    if not item:
        await call.answer("该菜单项已不存在", show_alert=True)
        return

    # 1. 删除旧消息 (User Interaction Reset)
    try:
        await call.message.delete()
    except: pass
    
    # 2. 准备新消息内容
    # 为了保持导航，我们在新消息下方再次挂载主菜单
    start_items = db.get_start_menu_items()
    kb = InlineKeyboardMarkup(row_width=2)
    for si in start_items:
        kb.insert(InlineKeyboardButton(si['text'], callback_data=f"start_menu_{si['id']}"))
        
    sent_msg = None
    
    # 3. 处理不同类型
    if item['type'] == 'report':
        text = "📝 **投诉/反馈**\n\n请直接在此发送您的反馈内容（文字或图片），我会转发给管理员。"
        await ReportStates.WAITING_FOR_CONTENT.set()
        sent_msg = await call.message.answer(text, parse_mode="Markdown", reply_markup=kb)
        
    elif item['type'] == 'link':
        # 链接类型：显示链接或者直接提供跳转按钮
        text = f"🔗 **{item['text']}**\n\n点击下方按钮跳转："
        # 在主菜单上方插入跳转按钮
        link_kb = InlineKeyboardMarkup(row_width=1)
        link_kb.add(InlineKeyboardButton("👉 点击跳转", url=item['value']))
        for si in start_items:
            link_kb.insert(InlineKeyboardButton(si['text'], callback_data=f"start_menu_{si['id']}"))
            
        sent_msg = await call.message.answer(text, parse_mode="Markdown", reply_markup=link_kb)
        
    elif item['type'] == 'reply':
        content = item['value'] or ""
        if item['media']:
            # 发送图片
            sent_msg = await call.message.answer_photo(item['media'], caption=content, reply_markup=kb)
        else:
            # 发送文字
            sent_msg = await call.message.answer(content, reply_markup=kb)

    await call.answer()
    
    # 4. 2分钟后自动删除新消息 (Reset Timer)
    if sent_msg:
        asyncio.create_task(delete_later(sent_msg, 120))

@dp.callback_query_handler(text="check_sub")
async def check_sub_handler(call: types.CallbackQuery):
    not_joined = await check_subscription(call.from_user.id)
    if not_joined:
        await call.answer("❌ 你还有未加入的频道！", show_alert=True)
    else:
        await call.message.delete()
        link_service = db.get_setting("LINK_SERVICE", DefaultConfig.LINK_SERVICE) or DefaultConfig.LINK_SERVICE
        link_newbie = "https://t.me/huaianbendi/6" 
        link_rules = db.get_setting("LINK_RULES", DefaultConfig.LINK_RULES) or DefaultConfig.LINK_RULES
        link_safety = db.get_setting("LINK_SAFETY", DefaultConfig.LINK_SAFETY) or DefaultConfig.LINK_SAFETY
        link_group = db.get_setting("LINK_GROUP", DefaultConfig.LINK_GROUP) or DefaultConfig.LINK_GROUP
        
        name_link = f"[{call.from_user.full_name}](tg://user?id={call.from_user.id})"
        success_text = (
            "欢迎使用麻辣鹅系统\n"
            f"    {name_link} ，鹅友，您好!\n"
            f"🤗欢迎来到[麻辣鹅圈子]({link_group})，立即开始你的麻辣探索之旅吧；\n"
            "    小鹅均为已验证资源!对眼有感即可冲，放心\"旅途\"，勿需多虑!\n"
            f"[旅前须知]:联系方式无条件获取，及时验证，请勿鸽人，素质诚信出击;[联系鹅神]({link_service})。\n"
            f"[温馨提示]:切勿相信任何非管理私聊，如有请避免踩雷[踩雷反馈]({link_service})\n"
            "[雅俗共赏]:行九浅而一深，待十侯而方毕\n"
            "[小鹅状态]: ♥️可约     😈 月休\n"
            f"[安全须知]1、[新人说明]({link_newbie}) 2、[群规及操作]({link_rules})\n\n"
            "小鹅，期待与您相约;祝\"旅途\"愉快!感谢支持"
        )

        
        start_items = db.get_start_menu_items()
        kb = InlineKeyboardMarkup(row_width=2)
        for item in start_items:
            kb.insert(InlineKeyboardButton(item['text'], callback_data=f"start_menu_{item['id']}"))

        sent_msg = await call.message.answer(
            success_text,
            parse_mode="Markdown",
            reply_markup=kb,
            disable_web_page_preview=True
        )
        asyncio.create_task(delete_later(sent_msg, 120))


# ================= 报告逻辑 =================
@dp.callback_query_handler(text="report")
async def start_report_callback(call: types.CallbackQuery):
    await call.message.answer("📝 请直接在此发送您的报告内容（支持文字、图片）：\n\n⚠️ 注意：报告将经过审核或直接发布，请勿发送违规内容。")
    await ReportStates.WAITING_FOR_CONTENT.set()
    await call.answer()

@dp.message_handler(commands=['report'])
async def start_report_command(message: types.Message):
    await message.reply("📝 请直接在此发送您的报告内容（支持文字、图片）：\n\n⚠️ 注意：报告将经过审核或直接发布，请勿发送违规内容。")
    await ReportStates.WAITING_FOR_CONTENT.set()

@dp.message_handler(state=ReportStates.WAITING_FOR_CONTENT, content_types=[types.ContentType.TEXT, types.ContentType.PHOTO])
async def process_report(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    report_channel = db.get_setting("REPORT_CHANNEL", DefaultConfig.REPORT_CHANNEL)
    
    if not report_channel:
        await message.reply("⚠️ 系统暂未配置报告频道，无法提交。请联系管理员。")
        await state.finish()
        return

    # 1. 转发到频道
    try:
        caption_prefix = f"👤 来自用户: {message.from_user.full_name} (ID: {user_id})\n\n"
        
        if message.photo:
            sent_msg = await bot.send_photo(report_channel, message.photo[-1].file_id, caption=caption_prefix + (message.caption or ""))
        else:
            sent_msg = await bot.send_message(report_channel, caption_prefix + message.text)
            
        await message.reply("✅ 报告提交成功！管理员已收到。")
    except Exception as e:
        await message.reply(f"⚠️ 报告转发失败(可能频道ID配置错误): {e}")
    
    await state.finish()
