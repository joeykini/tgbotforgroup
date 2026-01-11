import asyncio
import os
import time
from aiogram import types
from aiogram.dispatcher import FSMContext
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from loader import dp, db, bot
from config import DefaultConfig
from states import AdminStates, ReportStates
from utils import delete_later, is_admin

# ================= 辅助键盘 =================

def get_settings_keyboard():
    keyboard = InlineKeyboardMarkup(row_width=1)
    keyboard.add(InlineKeyboardButton("📢 强制关注频道管理", callback_data="admin_channels"))
    keyboard.add(InlineKeyboardButton("⚙️ 功能开关设置", callback_data="admin_switches"))
    keyboard.add(InlineKeyboardButton("🔗 链接配置", callback_data="admin_links"))
    keyboard.add(InlineKeyboardButton("👤 联系人配置", callback_data="admin_contact"))
    keyboard.add(InlineKeyboardButton("🔘 自定义按钮", callback_data="admin_buttons"))
    keyboard.add(InlineKeyboardButton("🚀 /start 菜单配置", callback_data="admin_start_menu"))
    keyboard.add(InlineKeyboardButton("🕒 定时广告配置", callback_data="admin_ad"))
    keyboard.add(InlineKeyboardButton("📝 报告频道配置", callback_data="admin_report"))
    keyboard.add(InlineKeyboardButton("💬 关键词回复", callback_data="admin_keywords"))
    keyboard.add(InlineKeyboardButton("❌ 关闭菜单", callback_data="admin_close"))
    return keyboard

def get_switches_keyboard():
    welcome = db.get_setting("WELCOME_ENABLED", DefaultConfig.WELCOME_ENABLED)
    antilink = db.get_setting("ANTI_LINK_ENABLED", DefaultConfig.ANTI_LINK_ENABLED)
    
    keyboard = InlineKeyboardMarkup(row_width=1)
    keyboard.add(InlineKeyboardButton(f"入群欢迎: {'✅ 开启' if welcome else '❌ 关闭'}", callback_data="toggle_welcome"))
    keyboard.add(InlineKeyboardButton(f"防链接: {'✅ 开启' if antilink else '❌ 关闭'}", callback_data="toggle_antilink"))
    keyboard.add(InlineKeyboardButton("⬅️ 返回", callback_data="admin_back"))
    return keyboard

def get_channels_keyboard():
    channels = db.get_setting("REQUIRED_CHANNELS", DefaultConfig.REQUIRED_CHANNELS)
    keyboard = InlineKeyboardMarkup(row_width=1)
    for idx, ch in enumerate(channels):
        keyboard.add(InlineKeyboardButton(f"🗑 删除: {ch['name']}", callback_data=f"del_channel_{idx}"))
    keyboard.add(InlineKeyboardButton("➕ 添加新频道", callback_data="add_channel"))
    keyboard.add(InlineKeyboardButton("⬅️ 返回", callback_data="admin_back"))
    return keyboard

# ================= 管理员后台逻辑 =================

@dp.message_handler(commands=['settings'], user_id=DefaultConfig.ADMIN_ID)
async def cmd_settings(message: types.Message):
    msg = await message.reply("🛠 **系统设置后台**", reply_markup=get_settings_keyboard())
    asyncio.create_task(delete_later(msg, 120))
    asyncio.create_task(delete_later(message, 120))

@dp.callback_query_handler(text_startswith="admin_", user_id=DefaultConfig.ADMIN_ID, state="*")
async def admin_menu_handler(call: types.CallbackQuery, state: FSMContext):
    await state.finish()
    
    action = call.data.split("_")[1]
    if action == "close":
        await call.message.delete()
    elif action == "back":
        await call.message.edit_text("🛠 **系统设置后台**", reply_markup=get_settings_keyboard())
        await call.answer("已返回主菜单")
        return
    elif action == "switches":
        await call.message.edit_text("⚙️ **功能开关**", reply_markup=get_switches_keyboard())
    elif action == "channels":
        await call.message.edit_text("📢 **频道管理**\n点击按钮删除对应频道，或点击添加。", reply_markup=get_channels_keyboard())
    elif action == "links":
        text = "🔗 **链接配置**\n点击按钮修改对应文字的跳转链接："
        kb = InlineKeyboardMarkup(row_width=2)
        kb.add(InlineKeyboardButton("新人说明", callback_data="edit_link_newbie"))
        kb.add(InlineKeyboardButton("群规及操作", callback_data="edit_link_rules"))
        kb.add(InlineKeyboardButton("安全指南", callback_data="edit_link_safety"))
        kb.add(InlineKeyboardButton("术语", callback_data="edit_link_terms"))
        kb.add(InlineKeyboardButton("客服/鹅神", callback_data="edit_link_service"))
        kb.add(InlineKeyboardButton("淮安榜 (主频道)", callback_data="edit_link_huaian"))
        kb.add(InlineKeyboardButton("群组", callback_data="edit_link_group"))
        kb.add(InlineKeyboardButton("⬅️ 返回", callback_data="admin_back"))
        await call.message.edit_text(text, reply_markup=kb)
    elif action == "contact":
        contact_user = db.get_setting("CONTACT_USER", DefaultConfig.CONTACT_USER)
        contact_url = db.get_setting("CONTACT_URL", DefaultConfig.CONTACT_URL)
        text = f"👤 **当前联系人配置**\n名称: {contact_user}\n链接: {contact_url}\n\n请选择要修改的项目："
        kb = InlineKeyboardMarkup().add(
            InlineKeyboardButton("修改名称", callback_data="edit_contact_name"),
            InlineKeyboardButton("修改链接", callback_data="edit_contact_url")
        ).add(InlineKeyboardButton("⬅️ 返回", callback_data="admin_back"))
        await call.message.edit_text(text, reply_markup=kb)
    elif action == "ad":
        interval = db.get_setting("AD_INTERVAL", DefaultConfig.AD_INTERVAL)
        ads = db.get_all_ads()
        text = f"🕒 **定时广告配置**\n推送间隔: {interval}秒\n当前广告数: {len(ads)}\n\n⚠️ 系统将随机抽取一条发送。"
        kb = InlineKeyboardMarkup(row_width=1)
        kb.add(InlineKeyboardButton("➕ 添加新广告", callback_data="add_random_ad"))
        kb.add(InlineKeyboardButton("⏱ 修改间隔", callback_data="edit_ad_interval"))
        for ad in ads:
            display_name = ad['title'] if ad.get('title') else (ad['content'][:15] + '...') if ad['content'] else "[纯图片]"
            kb.add(InlineKeyboardButton(f"{display_name}", callback_data=f"view_ad_{ad['id']}"))
        kb.add(InlineKeyboardButton("⬅️ 返回", callback_data="admin_back"))
        await call.message.edit_text(text, reply_markup=kb)
    elif action == "report":
        current = db.get_setting("REPORT_CHANNEL", "未配置")
        text = f"📝 **报告频道配置**\n当前频道ID: `{current}`\n\n请点击下方按钮修改："
        kb = InlineKeyboardMarkup().add(
            InlineKeyboardButton("修改频道ID", callback_data="edit_report_channel")
        ).add(InlineKeyboardButton("⬅️ 返回", callback_data="admin_back"))
        await call.message.edit_text(text, reply_markup=kb)
    elif action == "buttons":
        buttons = db.get_buttons()
        text = "🔘 **自定义按钮管理**\n点击按钮可以删除它，或者点击下方添加新按钮。"
        kb = InlineKeyboardMarkup(row_width=1)
        for btn in buttons:
            kb.add(InlineKeyboardButton(f"🗑 {btn['text']} -> {btn['url']}", callback_data=f"del_btn_{btn['id']}"))
        kb.add(InlineKeyboardButton("➕ 添加按钮", callback_data="add_btn"))
        kb.add(InlineKeyboardButton("⬅️ 返回", callback_data="admin_back"))
        await call.message.edit_text(text, reply_markup=kb)
    elif action == "keywords":
        keywords = db.get_all_keywords()
        text = f"💬 **关键词回复配置**\n当前关键词数: {len(keywords)}\n\n点击下方按钮可以删除，或添加新关键词。"
        kb = InlineKeyboardMarkup(row_width=1)
        kb.add(InlineKeyboardButton("➕ 添加关键词", callback_data="add_keyword"))
        for kw in keywords:
            kb.add(InlineKeyboardButton(f"🗑 删除: {kw['keyword']}", callback_data=f"del_kw_{kw['id']}"))
        kb.add(InlineKeyboardButton("⬅️ 返回", callback_data="admin_back"))
        await call.message.edit_text(text, reply_markup=kb)
    elif action == "start_menu":
        items = db.get_start_menu_items()
        text = f"🚀 **Start 菜单配置**\n当前菜单项数: {len(items)}\n\n点击下方按钮可以删除，或添加新菜单项。"
        kb = InlineKeyboardMarkup(row_width=1)
        kb.add(InlineKeyboardButton("➕ 添加新菜单项", callback_data="add_start_item"))
        for item in items:
            type_icon = "🔗" if item['type'] == 'link' else ("🖼" if item['media'] else "📝")
            kb.add(InlineKeyboardButton(f"🗑 {type_icon} {item['text']}", callback_data=f"del_start_item_{item['id']}"))
        kb.add(InlineKeyboardButton("⬅️ 返回", callback_data="admin_back"))
        await call.message.edit_text(text, reply_markup=kb)
    
    await call.answer()

# --- 关键词回复逻辑 ---
@dp.callback_query_handler(text="add_keyword", user_id=DefaultConfig.ADMIN_ID)
async def add_keyword_start(call: types.CallbackQuery):
    msg = await call.message.answer("请输入要触发的 **关键词**：")
    asyncio.create_task(delete_later(msg, 120))
    await AdminStates.WAITING_FOR_KEYWORD_KEY.set()
    await call.answer()

@dp.message_handler(state=AdminStates.WAITING_FOR_KEYWORD_KEY, user_id=DefaultConfig.ADMIN_ID)
async def add_keyword_key(message: types.Message, state: FSMContext):
    await state.update_data(kw_key=message.text)
    msg = await message.reply("请输入该关键词对应的 **回复内容**：")
    asyncio.create_task(delete_later(msg, 120))
    await AdminStates.WAITING_FOR_KEYWORD_REPLY.set()
    asyncio.create_task(delete_later(message, 120))

@dp.message_handler(state=AdminStates.WAITING_FOR_KEYWORD_REPLY, user_id=DefaultConfig.ADMIN_ID)
async def add_keyword_reply_content(message: types.Message, state: FSMContext):
    data = await state.get_data()
    keyword = data.get("kw_key")
    reply = message.text
    db.add_keyword_reply(keyword, reply)
    msg = await message.reply(f"✅ 关键词规则已添加！\n当发送 `{keyword}` 时，自动回复内容。", parse_mode="Markdown")
    asyncio.create_task(delete_later(msg, 120))
    asyncio.create_task(delete_later(message, 120))
    await state.finish()

@dp.callback_query_handler(text_startswith="del_kw_", user_id=DefaultConfig.ADMIN_ID)
async def del_keyword_handler(call: types.CallbackQuery):
    kw_id = int(call.data.split("_")[-1])
    db.delete_keyword_reply(kw_id)
    await call.answer("关键词已删除")
    await admin_menu_handler(call, None) # Refresh

# --- 自定义按钮逻辑 ---
@dp.callback_query_handler(text="add_btn", user_id=DefaultConfig.ADMIN_ID)
async def add_btn_start(call: types.CallbackQuery):
    await call.message.answer("请输入按钮显示的文字：")
    await AdminStates.WAITING_FOR_BUTTON_TEXT.set()
    await call.answer()

@dp.message_handler(state=AdminStates.WAITING_FOR_BUTTON_TEXT, user_id=DefaultConfig.ADMIN_ID)
async def add_btn_text(message: types.Message, state: FSMContext):
    await state.update_data(btn_text=message.text)
    await message.answer("请输入按钮跳转的链接 (必须以 http 或 https 开头)：")
    await AdminStates.WAITING_FOR_BUTTON_URL.set()

@dp.message_handler(state=AdminStates.WAITING_FOR_BUTTON_URL, user_id=DefaultConfig.ADMIN_ID)
async def add_btn_url(message: types.Message, state: FSMContext):
    url = message.text
    if not url.startswith("http"):
        await message.answer("❌ 链接格式错误！请重新输入 (发送 /cancel 取消)：")
        return
    data = await state.get_data()
    btn_text = data.get("btn_text")
    db.add_button(btn_text, url)
    await message.answer(f"✅ 已添加按钮：[{btn_text}]({url})", parse_mode="Markdown", disable_web_page_preview=True)
    await state.finish()

@dp.callback_query_handler(text_startswith="del_btn_", user_id=DefaultConfig.ADMIN_ID)
async def del_btn_handler(call: types.CallbackQuery):
    btn_id = int(call.data.split("_")[2])
    db.delete_button(btn_id)
    await call.answer("✅ 按钮已删除")
    await admin_menu_handler(call, None) # Refresh

# --- 报告频道配置逻辑 ---
@dp.callback_query_handler(text="edit_report_channel", user_id=DefaultConfig.ADMIN_ID)
async def edit_report_channel(call: types.CallbackQuery):
    await call.message.answer("请输入新的报告频道ID (例如 -100123456789)：")
    await AdminStates.WAITING_FOR_REPORT_CHANNEL.set()
    await call.answer()

@dp.message_handler(state=AdminStates.WAITING_FOR_REPORT_CHANNEL, user_id=DefaultConfig.ADMIN_ID)
async def save_report_channel(message: types.Message, state: FSMContext):
    try:
        channel_id = int(message.text)
        db.set_setting("REPORT_CHANNEL", channel_id)
        await message.reply(f"✅ 报告频道已更新为: `{channel_id}`", parse_mode="Markdown")
        await state.finish()
    except ValueError:
        await message.reply("❌ ID必须是数字！请重新输入或发送 /cancel 取消。")

# --- 链接配置逻辑 ---
@dp.callback_query_handler(text_startswith="edit_link_", user_id=DefaultConfig.ADMIN_ID)
async def edit_link_handler(call: types.CallbackQuery):
    link_type = call.data.replace("edit_link_", "").upper()
    await call.message.answer(f"请输入新的链接 (用于 {link_type})：")
    state_map = {
        "NEWBIE": AdminStates.WAITING_FOR_LINK_NEWBIE,
        "RULES": AdminStates.WAITING_FOR_LINK_RULES,
        "SAFETY": AdminStates.WAITING_FOR_LINK_SAFETY,
        "TERMS": AdminStates.WAITING_FOR_LINK_TERMS,
        "SERVICE": AdminStates.WAITING_FOR_LINK_SERVICE,
        "HUAIAN": AdminStates.WAITING_FOR_LINK_HUAIAN,
        "GROUP": AdminStates.WAITING_FOR_LINK_GROUP
    }
    if link_type in state_map:
        await state_map[link_type].set()
    await call.answer()

@dp.message_handler(state=[AdminStates.WAITING_FOR_LINK_NEWBIE, AdminStates.WAITING_FOR_LINK_RULES, 
                           AdminStates.WAITING_FOR_LINK_SAFETY, AdminStates.WAITING_FOR_LINK_TERMS, 
                           AdminStates.WAITING_FOR_LINK_SERVICE, AdminStates.WAITING_FOR_LINK_HUAIAN, 
                           AdminStates.WAITING_FOR_LINK_GROUP], user_id=DefaultConfig.ADMIN_ID)
async def save_link_config(message: types.Message, state: FSMContext):
    current_state = await state.get_state()
    state_name = current_state.split(':')[-1]
    key_map = {
        "WAITING_FOR_LINK_NEWBIE": "LINK_NEWBIE",
        "WAITING_FOR_LINK_RULES": "LINK_RULES",
        "WAITING_FOR_LINK_SAFETY": "LINK_SAFETY",
        "WAITING_FOR_LINK_TERMS": "LINK_TERMS",
        "WAITING_FOR_LINK_SERVICE": "LINK_SERVICE",
        "WAITING_FOR_LINK_HUAIAN": "LINK_HUAIAN",
        "WAITING_FOR_LINK_GROUP": "LINK_GROUP"
    }
    if state_name in key_map:
        db.set_setting(key_map[state_name], message.text)
        await message.reply(f"✅ 链接已更新！")
    await state.finish()

# --- 开关、频道、联系人、广告管理逻辑 (省略部分重复细节) ---
# ... 这里可以继续搬运剩下的 admin 逻辑 ...

@dp.callback_query_handler(text_startswith="toggle_", user_id=DefaultConfig.ADMIN_ID)
async def toggle_handler(call: types.CallbackQuery):
    action = call.data.split("_")[1]
    if action == "welcome":
        curr = db.get_setting("WELCOME_ENABLED", DefaultConfig.WELCOME_ENABLED)
        db.set_setting("WELCOME_ENABLED", not curr)
    elif action == "antilink":
        curr = db.get_setting("ANTI_LINK_ENABLED", DefaultConfig.ANTI_LINK_ENABLED)
        db.set_setting("ANTI_LINK_ENABLED", not curr)
    await call.message.edit_reply_markup(reply_markup=get_switches_keyboard())
    await call.answer("设置已更新")

@dp.callback_query_handler(text_startswith="del_channel_", user_id=DefaultConfig.ADMIN_ID)
async def del_channel_handler(call: types.CallbackQuery):
    idx = int(call.data.split("_")[2])
    channels = db.get_setting("REQUIRED_CHANNELS", DefaultConfig.REQUIRED_CHANNELS)
    if 0 <= idx < len(channels):
        channels.pop(idx)
        db.set_setting("REQUIRED_CHANNELS", channels)
        await call.answer("已删除")
        await call.message.edit_reply_markup(reply_markup=get_channels_keyboard())

@dp.callback_query_handler(text="add_channel", user_id=DefaultConfig.ADMIN_ID)
async def add_channel_start(call: types.CallbackQuery):
    await call.message.answer("格式：`名称|ID|链接`")
    await AdminStates.WAITING_FOR_CHANNEL_INFO.set()

@dp.message_handler(state=AdminStates.WAITING_FOR_CHANNEL_INFO, user_id=DefaultConfig.ADMIN_ID)
async def add_channel_save(message: types.Message, state: FSMContext):
    parts = message.text.split('|')
    if len(parts) == 3:
        new_ch = {"name": parts[0].strip(), "id": parts[1].strip(), "url": parts[2].strip()}
        channels = db.get_setting("REQUIRED_CHANNELS", DefaultConfig.REQUIRED_CHANNELS)
        channels.append(new_ch)
        db.set_setting("REQUIRED_CHANNELS", channels)
        await message.reply("✅ 已添加")
        await state.finish()

# ================= 系统命令 =================

@dp.message_handler(commands=['broadcast'], user_id=DefaultConfig.ADMIN_ID)
async def cmd_broadcast(message: types.Message):
    # 此处需要 Database.get_all_users，实现在 database.py 中
    from database import Database
    db_instance = Database() 
    users = db_instance._get_conn().execute("SELECT user_id FROM users").fetchall()
    users = [u[0] for u in users]
    count = 0
    for uid in users:
        try: 
            await bot.send_message(uid, f"📢 {message.get_args()}")
            count += 1
            await asyncio.sleep(0.05)
        except: pass
    await message.reply(f"✅ 发送完成，送达: {count} 人")

@dp.message_handler(commands=['export'], user_id=DefaultConfig.ADMIN_ID)
async def cmd_export_db(message: types.Message):
    if os.path.exists(DefaultConfig.DB_NAME):
        await message.reply_document(types.InputFile(DefaultConfig.DB_NAME))

@dp.message_handler(commands=['import'], content_types=types.ContentType.DOCUMENT, user_id=DefaultConfig.ADMIN_ID)
async def cmd_import_db(message: types.Message):
    doc = message.document
    await doc.download(destination_file=DefaultConfig.DB_NAME)
    db.reload()
    await message.reply("✅ 数据库已导入并重载")
