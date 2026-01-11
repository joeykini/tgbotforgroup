import asyncio
from aiogram import types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.dispatcher import FSMContext

from loader import dp, db, bot
from config import DefaultConfig
from states import ReportStates
from utils import delete_later, check_subscription, get_subscription_keyboard

# ================= 辅助函数：构造多页欢迎按钮 =================

def get_welcome_keyboard(page=1):
    kb = InlineKeyboardMarkup(row_width=2)
    custom_btns = db.get_buttons(page=page)
    
    # 添加自定义配置的按钮 (直接跳转链接)
    for btn in custom_btns:
        kb.insert(InlineKeyboardButton(btn['text'], url=btn['url']))
    
    # 如果是第一页，添加“区域”按钮跳转到第二页
    if page == 1:
        # 该按钮始终排在最后
        kb.add(InlineKeyboardButton("📍 区域", callback_data="welcome_page_2"))
    else:
        # 如果是第二页，添加返回按钮
        kb.add(InlineKeyboardButton("⬅️ 返回", callback_data="welcome_page_1"))
        
    return kb

# ================= 私聊/菜单逻辑 =================

@dp.message_handler(commands=['start'], chat_type=types.ChatType.PRIVATE)
async def cmd_start(message: types.Message):
    # 检测关注状态
    not_joined = await check_subscription(message.from_user.id)
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
        
        sent_msg = await message.answer(text, reply_markup=get_subscription_keyboard(not_joined), parse_mode="Markdown", disable_web_page_preview=True)
        asyncio.create_task(delete_later(sent_msg, 120))
        return

    name_link = f"[{message.from_user.full_name}](tg://user?id={message.from_user.id})"
    
    # 链接配置
    link_service = db.get_setting("LINK_SERVICE", DefaultConfig.LINK_SERVICE) or DefaultConfig.LINK_SERVICE
    link_rules = db.get_setting("LINK_RULES", DefaultConfig.LINK_RULES) or DefaultConfig.LINK_RULES
    link_group = db.get_setting("LINK_GROUP", DefaultConfig.LINK_GROUP) or DefaultConfig.LINK_GROUP
    link_newbie = "https://t.me/huaianbendi/6" 

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
    
    kb = get_welcome_keyboard(page=1)
    sent_msg = await message.answer(success_text, parse_mode="Markdown", reply_markup=kb, disable_web_page_preview=True)
    
    asyncio.create_task(delete_later(sent_msg, 120))
    asyncio.create_task(delete_later(message, 120))

# --- 多页欢迎菜单切换逻辑 ---
@dp.callback_query_handler(text_startswith="welcome_page_")
async def welcome_pagination_handler(call: types.CallbackQuery):
    page = int(call.data.split("_")[-1])
    kb = get_welcome_keyboard(page=page)
    try:
        await call.message.edit_reply_markup(reply_markup=kb)
    except: pass
    await call.answer()

# --- 旧的 Start 菜单回调保持兼容 ---
@dp.callback_query_handler(text_startswith="start_menu_")
async def start_menu_item_handler(call: types.CallbackQuery):
    item_id = int(call.data.split("_")[-1])
    item = db.get_start_menu_item(item_id)
    if not item:
        await call.answer("该菜单项已不存在", show_alert=True)
        return
    try: await call.message.delete()
    except: pass
    
    kb = get_welcome_keyboard(page=1)
    sent_msg = None
    if item['type'] == 'report':
        text = "📝 **投诉/反馈**\n\n请直接在此发送您的反馈内容（文字或图片），我会转发给管理员。"
        await ReportStates.WAITING_FOR_CONTENT.set()
        sent_msg = await call.message.answer(text, parse_mode="Markdown", reply_markup=kb)
    elif item['type'] == 'link':
        text = f"🔗 **{item['text']}**\n\n点击下方按钮跳转："
        link_kb = InlineKeyboardMarkup(row_width=1).add(InlineKeyboardButton("👉 点击跳转", url=item['value']))
        sent_msg = await call.message.answer(text, parse_mode="Markdown", reply_markup=link_kb)
    elif item['type'] == 'reply':
        if item['media']:
            sent_msg = await call.message.answer_photo(item['media'], caption=item['value'], reply_markup=kb)
        else:
            sent_msg = await call.message.answer(item['value'], reply_markup=kb)
    await call.answer()
    if sent_msg: asyncio.create_task(delete_later(sent_msg, 120))

@dp.callback_query_handler(text="check_sub")
async def check_sub_handler(call: types.CallbackQuery):
    not_joined = await check_subscription(call.from_user.id)
    if not_joined:
        await call.answer("❌ 你还有未加入的频道！", show_alert=True)
    else:
        await call.message.delete()
        # ... 复用 cmd_start 里的 success_text (略，这里直接重定向或复制) ...
        name_link = f"[{call.from_user.full_name}](tg://user?id={call.from_user.id})"
        link_group = db.get_setting("LINK_GROUP", DefaultConfig.LINK_GROUP) or DefaultConfig.LINK_GROUP
        link_service = db.get_setting("LINK_SERVICE", DefaultConfig.LINK_SERVICE) or DefaultConfig.LINK_SERVICE
        link_newbie = "https://t.me/huaianbendi/6" 
        link_rules = db.get_setting("LINK_RULES", DefaultConfig.LINK_RULES) or DefaultConfig.LINK_RULES

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
        await call.message.answer(success_text, parse_mode="Markdown", reply_markup=get_welcome_keyboard(page=1), disable_web_page_preview=True)

# ================= 报告逻辑 =================
@dp.callback_query_handler(text="report")
async def start_report_callback(call: types.CallbackQuery):
    await call.message.answer("📝 请直接在此发送您的反馈内容。")
    await ReportStates.WAITING_FOR_CONTENT.set()
    await call.answer()

@dp.message_handler(state=ReportStates.WAITING_FOR_CONTENT, content_types=[types.ContentType.TEXT, types.ContentType.PHOTO])
async def process_report(message: types.Message, state: FSMContext):
    report_channel = db.get_setting("REPORT_CHANNEL", DefaultConfig.REPORT_CHANNEL)
    if not report_channel:
        await message.reply("⚠️ 系统暂未配置报告频道。")
        await state.finish()
        return
    try:
        prefix = f"👤 来自: {message.from_user.full_name} ({message.from_user.id})\n\n"
        if message.photo:
            await bot.send_photo(report_channel, message.photo[-1].file_id, caption=prefix + (message.caption or ""))
        else:
            await bot.send_message(report_channel, prefix + message.text)
        await message.reply("✅ 报告已提交。")
    except Exception as e:
        await message.reply(f"⚠️ 提交失败: {e}")
    await state.finish()
