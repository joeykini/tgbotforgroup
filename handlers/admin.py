import asyncio
import os
import time
import json
import random
from aiogram import types
from aiogram.dispatcher import FSMContext
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from loader import dp, db, bot
from config import DefaultConfig
from states import AdminStates, ReportStates
from utils import delete_later, is_admin

# ================= 辅助键盘 =================

def get_settings_keyboard():
    keyboard = InlineKeyboardMarkup(row_width=2)
    
    # 第一排：核心开关与频道
    keyboard.row(
        InlineKeyboardButton("⚙️ 开关设置", callback_data="admin_switches"),
        InlineKeyboardButton("📢 关注管理", callback_data="admin_channels")
    )
    
    # 第二排：核心内容 (格栅按钮)
    keyboard.add(InlineKeyboardButton("🔘 欢迎页-格栅按钮管理", callback_data="admin_resources"))

    # 第四排：核心链接与联系人
    keyboard.row(
        InlineKeyboardButton("🔗 链接配置", callback_data="admin_links"),
        InlineKeyboardButton("👤 联系人配置", callback_data="admin_contact")
    )
    
    # 第四排：互动管理
    keyboard.row(
        InlineKeyboardButton("🕒 定时广告", callback_data="admin_ad"),
        InlineKeyboardButton("💬 关键词", callback_data="admin_keywords")
    )
    
    # 第六排：报告
    keyboard.add(InlineKeyboardButton("📝 报告频道配置", callback_data="admin_report"))
    
    # 底部
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

# ================= 管理员后台主逻辑 =================

@dp.message_handler(commands=['settings'], user_id=DefaultConfig.ADMIN_ID)
async def cmd_settings(message: types.Message):
    msg = await message.reply("🛠 **系统设置后台**", reply_markup=get_settings_keyboard())
    await delete_later(msg, 120)
    await delete_later(message, 120)

@dp.callback_query_handler(text_startswith="admin_", user_id=DefaultConfig.ADMIN_ID, state="*")
async def admin_menu_handler(call: types.CallbackQuery, state: FSMContext = None):
    # 安全结束状态，防止 None 崩溃
    if state:
        await state.finish()
    
    action = call.data.split("_")[1]
    if action == "close":
        await call.message.delete()
        return
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
    elif action == "keywords":
        keywords = db.get_all_keywords()
        text = f"💬 **关键词回复配置**\n当前关键词数: {len(keywords)}\n\n点击下方按钮可以删除，或添加新关键词。"
        kb = InlineKeyboardMarkup(row_width=1)
        kb.add(InlineKeyboardButton("➕ 添加关键词", callback_data="add_keyword"))
        for kw in keywords:
            kb.add(InlineKeyboardButton(f"🗑 删除: {kw['keyword']}", callback_data=f"del_kw_{kw['id']}"))
        kb.add(InlineKeyboardButton("⬅️ 返回", callback_data="admin_back"))
        await call.message.edit_text(text, reply_markup=kb)
    elif action == "report":
        current = db.get_setting("REPORT_CHANNEL", "未配置")
        text = f"📝 **报告频道配置**\n当前频道ID: `{current}`\n\n请点击下方按钮修改："
        kb = InlineKeyboardMarkup().add(
            InlineKeyboardButton("修改频道ID", callback_data="edit_report_channel")
        ).add(InlineKeyboardButton("⬅️ 返回", callback_data="admin_back"))
        await call.message.edit_text(text, reply_markup=kb)
    elif action == "resources":
        res_list = db.get_resources(limit=300) 
        text = (
            "🔘 **格栅按钮/资源管理**\n\n"
            "管理逻辑：点击资源可切换【❤️/😈】，删除请点击🗑。\n"
            "⚠️ 每个页面建议不超过 15-20 个资源。"
        )
        kb = InlineKeyboardMarkup(row_width=2)
        kb.add(InlineKeyboardButton("➕ 添加新按钮/资源", callback_data="add_res_start"))
        
        for p_idx in range(1, 4):
            items = [r for r in res_list if r['page'] == p_idx]
            page_name = ["首屏", "区域", "广告/额外"][p_idx-1]
            kb.row(InlineKeyboardButton(f"--- 第{p_idx}页 ({page_name}) ---", callback_data="none"))
            
            if not items:
                kb.row(InlineKeyboardButton("（该页暂无资源）", callback_data="none"))
                continue

            active = [r for r in items if r['status'] == 1]
            resting = [r for r in items if r['status'] == 0]
            
            for r in active:
                kb.add(InlineKeyboardButton(f"❤️{r['name']}", callback_data=f"toggle_res_{r['id']}"),
                       InlineKeyboardButton("🗑", callback_data=f"del_res_{r['id']}"))
            
            for r in resting:
                kb.add(InlineKeyboardButton(f"😈{r['name']}", callback_data=f"toggle_res_{r['id']}"),
                       InlineKeyboardButton("🗑", callback_data=f"del_res_{r['id']}"))
                   
        kb.add(InlineKeyboardButton("⬅️ 返回", callback_data="admin_back"))
        await call.message.edit_text(text, reply_markup=kb)
    
    await call.answer()

# (Deleted obsolete button handlers)

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

# --- 关键词管理 ---
@dp.callback_query_handler(text="add_keyword", user_id=DefaultConfig.ADMIN_ID)
async def add_keyword_start(call: types.CallbackQuery):
    await call.message.answer("请输入要触发的 **关键词**：")
    await AdminStates.WAITING_FOR_KEYWORD_KEY.set()
    await call.answer()

@dp.message_handler(state=AdminStates.WAITING_FOR_KEYWORD_KEY, user_id=DefaultConfig.ADMIN_ID)
async def add_keyword_key(message: types.Message, state: FSMContext):
    await state.update_data(kw_key=message.text)
    await message.reply("请输入该关键词对应的 **回复内容**：")
    await AdminStates.WAITING_FOR_KEYWORD_REPLY.set()

@dp.message_handler(state=AdminStates.WAITING_FOR_KEYWORD_REPLY, user_id=DefaultConfig.ADMIN_ID)
async def add_keyword_reply_content(message: types.Message, state: FSMContext):
    data = await state.get_data()
    keyword = data.get("kw_key")
    reply = message.text
    db.add_keyword_reply(keyword, reply)
    await message.reply(f"✅ 关键词规则已添加！")
    await state.finish()

@dp.callback_query_handler(text_startswith="del_kw_", user_id=DefaultConfig.ADMIN_ID)
async def del_keyword_handler(call: types.CallbackQuery):
    kw_id = int(call.data.split("_")[-1])
    db.delete_keyword_reply(kw_id)
    await call.answer("关键词已删除")
    call.data = "admin_keywords"
    await admin_menu_handler(call, None)

# --- 强制关注频道管理 ---
@dp.callback_query_handler(text="add_channel", user_id=DefaultConfig.ADMIN_ID)
async def add_channel_start(call: types.CallbackQuery):
    await call.message.answer("请输入频道 **名称** (例如: 淮安麻辣鹅):")
    await AdminStates.WAITING_FOR_CHANNEL_NAME.set()
    await call.answer()

@dp.message_handler(state=AdminStates.WAITING_FOR_CHANNEL_NAME, user_id=DefaultConfig.ADMIN_ID)
async def add_channel_step1(message: types.Message, state: FSMContext):
    await state.update_data(ch_name=message.text)
    await message.reply("请输入频道 **ID** (例如: @huaianbendi 或 -100xxx):")
    await AdminStates.WAITING_FOR_CHANNEL_ID.set()

@dp.message_handler(state=AdminStates.WAITING_FOR_CHANNEL_ID, user_id=DefaultConfig.ADMIN_ID)
async def add_channel_step2(message: types.Message, state: FSMContext):
    await state.update_data(ch_id=message.text)
    await message.reply("请输入频道 **跳转链接** (例如: https://t.me/huaianbendi):")
    await AdminStates.WAITING_FOR_CHANNEL_URL.set()

@dp.message_handler(state=AdminStates.WAITING_FOR_CHANNEL_URL, user_id=DefaultConfig.ADMIN_ID)
async def add_channel_step3(message: types.Message, state: FSMContext):
    data = await state.get_data()
    new_ch = {"name": data['ch_name'], "id": data['ch_id'], "url": message.text}
    channels = db.get_setting("REQUIRED_CHANNELS", DefaultConfig.REQUIRED_CHANNELS)
    channels.append(new_ch)
    db.set_setting("REQUIRED_CHANNELS", channels)
    await message.reply(f"✅ 已成功添加频道: {data['ch_name']}")
    await state.finish()

@dp.callback_query_handler(text_startswith="del_channel_", user_id=DefaultConfig.ADMIN_ID)
async def del_channel_handler(call: types.CallbackQuery):
    idx = int(call.data.split("_")[2])
    channels = db.get_setting("REQUIRED_CHANNELS", DefaultConfig.REQUIRED_CHANNELS)
    if 0 <= idx < len(channels):
        channels.pop(idx)
        db.set_setting("REQUIRED_CHANNELS", channels)
        await call.answer("已删除")
        await call.message.edit_reply_markup(reply_markup=get_channels_keyboard())

# --- 开关逻辑 ---
@dp.callback_query_handler(text_startswith="toggle_", user_id=DefaultConfig.ADMIN_ID, state="*")
async def toggle_handler(call: types.CallbackQuery, state: FSMContext = None):
    if state: await state.finish()
    # 明确只处理系统开关，防止拦截 toggle_res_
    if call.data not in ["toggle_welcome", "toggle_antilink"]:
        return
        
    action = call.data.split("_")[1]
    if action == "welcome":
        curr = db.get_setting("WELCOME_ENABLED", DefaultConfig.WELCOME_ENABLED)
        db.set_setting("WELCOME_ENABLED", not curr)
    elif action == "antilink":
        curr = db.get_setting("ANTI_LINK_ENABLED", DefaultConfig.ANTI_LINK_ENABLED)
        db.set_setting("ANTI_LINK_ENABLED", not curr)
    await call.message.edit_reply_markup(reply_markup=get_switches_keyboard())
    await call.answer("设置已更新")

# --- 定时广告配置 ---
@dp.callback_query_handler(text="add_random_ad", user_id=DefaultConfig.ADMIN_ID)
async def add_random_ad_start(call: types.CallbackQuery):
    kb = InlineKeyboardMarkup().add(
        InlineKeyboardButton("🖼 带图片", callback_data="ad_img_yes"),
        InlineKeyboardButton("📝 纯文字", callback_data="ad_img_no")
    )
    await call.message.answer("广告是否包含图片？", reply_markup=kb)
    await AdminStates.WAITING_FOR_AD_IMAGE_DECISION.set()

@dp.callback_query_handler(state=AdminStates.WAITING_FOR_AD_IMAGE_DECISION, user_id=DefaultConfig.ADMIN_ID)
async def ad_image_decision(call: types.CallbackQuery, state: FSMContext):
    if call.data == "ad_img_yes":
        await call.message.answer("请发送图片，发送完点击 【✅ 完成】", 
            reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("✅ 完成", callback_data="ad_img_done")))
        await state.update_data(ad_images=[])
        await AdminStates.WAITING_FOR_AD_IMAGES.set()
    else:
        await call.message.answer("请输入广告文字内容：")
        await state.update_data(ad_images=[])
        await AdminStates.WAITING_FOR_AD_TEXT.set()
    await call.answer()

@dp.message_handler(state=AdminStates.WAITING_FOR_AD_IMAGES, content_types=types.ContentType.PHOTO, user_id=DefaultConfig.ADMIN_ID)
async def ad_image_upload(message: types.Message, state: FSMContext):
    async with state.proxy() as data:
        data['ad_images'].append(message.photo[-1].file_id)

@dp.callback_query_handler(text="ad_img_done", state=AdminStates.WAITING_FOR_AD_IMAGES, user_id=DefaultConfig.ADMIN_ID)
async def ad_image_finish(call: types.CallbackQuery):
    await call.message.answer("图片上传完成，请输入广告文字：")
    await AdminStates.WAITING_FOR_AD_TEXT.set()
    await call.answer()

@dp.message_handler(state=AdminStates.WAITING_FOR_AD_TEXT, user_id=DefaultConfig.ADMIN_ID)
async def save_ad_text(message: types.Message, state: FSMContext):
    await state.update_data(ad_content=message.text)
    await message.reply("请输入广告按钮 (格式: 文字|链接，一行一个；无则回复 skip):")
    await AdminStates.WAITING_FOR_AD_BUTTONS.set()

@dp.message_handler(state=AdminStates.WAITING_FOR_AD_BUTTONS, user_id=DefaultConfig.ADMIN_ID)
async def save_ad_buttons(message: types.Message, state: FSMContext):
    text = message.text.strip()
    buttons = []
    if text.lower() != 'skip':
        for line in text.split('\n'):
            parts = line.split('|')
            if len(parts) == 2:
                buttons.append({"text": parts[0].strip(), "url": parts[1].strip()})
    await state.update_data(ad_buttons=buttons)
    await message.reply("最后，请为广告起个名字 (便于管理):")
    await AdminStates.WAITING_FOR_AD_TITLE.set()

@dp.message_handler(state=AdminStates.WAITING_FOR_AD_TITLE, user_id=DefaultConfig.ADMIN_ID)
async def save_ad_title(message: types.Message, state: FSMContext):
    data = await state.get_data()
    db.add_ad(data['ad_content'], data['ad_images'], "photo" if data['ad_images'] else "text", message.text, data['ad_buttons'])
    await message.reply(f"✅ 广告 {message.text} 已添加")
    await state.finish()

@dp.callback_query_handler(text_startswith="view_ad_", user_id=DefaultConfig.ADMIN_ID)
async def view_ad_handler(call: types.CallbackQuery):
    ad_id = int(call.data.split("_")[-1])
    ad = db.get_ad(ad_id)
    if not ad:
        await call.answer("广告不存在")
        return
    text = f"📺 广告: {ad['title']}\n内容: {ad['content']}\n图片: {len(ad['images'])}张"
    kb = InlineKeyboardMarkup().add(InlineKeyboardButton("🗑 删除", callback_data=f"del_ad_{ad_id}")).add(InlineKeyboardButton("⬅️ 返回", callback_data="admin_ad"))
    await call.message.edit_text(text, reply_markup=kb)

@dp.callback_query_handler(text_startswith="del_ad_", user_id=DefaultConfig.ADMIN_ID)
async def del_ad_handler(call: types.CallbackQuery):
    ad_id = int(call.data.split("_")[-1])
    db.delete_ad(ad_id)
    await call.answer("已删除")
    call.data = "admin_ad"
    await admin_menu_handler(call, None)

@dp.callback_query_handler(text="edit_ad_interval", user_id=DefaultConfig.ADMIN_ID)
async def edit_ad_interval(call: types.CallbackQuery):
    await call.message.answer("请输入推送间隔 (秒):")
    await AdminStates.WAITING_FOR_AD_INTERVAL.set()

@dp.message_handler(state=AdminStates.WAITING_FOR_AD_INTERVAL, user_id=DefaultConfig.ADMIN_ID)
async def save_ad_interval(message: types.Message, state: FSMContext):
    if message.text.isdigit():
        db.set_setting("AD_INTERVAL", int(message.text))
        await message.reply("✅ 间隔已更新")
        await state.finish()

# --- 联系人配置 ---
@dp.callback_query_handler(text="edit_contact_name", user_id=DefaultConfig.ADMIN_ID)
async def edit_contact_name(call: types.CallbackQuery):
    await call.message.answer("请输入新的名称:")
    await AdminStates.WAITING_FOR_CONTACT_NAME.set()

@dp.message_handler(state=AdminStates.WAITING_FOR_CONTACT_NAME, user_id=DefaultConfig.ADMIN_ID)
async def save_contact_name(message: types.Message, state: FSMContext):
    db.set_setting("CONTACT_USER", message.text)
    await message.reply("✅ 联系人名称已更新")
    await state.finish()

@dp.callback_query_handler(text="edit_contact_url", user_id=DefaultConfig.ADMIN_ID)
async def edit_contact_url(call: types.CallbackQuery):
    await call.message.answer("请输入新的链接:")
    await AdminStates.WAITING_FOR_CONTACT_URL.set()

@dp.message_handler(state=AdminStates.WAITING_FOR_CONTACT_URL, user_id=DefaultConfig.ADMIN_ID)
async def save_contact_url(message: types.Message, state: FSMContext):
    db.set_setting("CONTACT_URL", message.text)
    await message.reply("✅ 联系人链接已更新")
    await state.finish()

# --- 报告频道 ---
@dp.callback_query_handler(text="edit_report_channel", user_id=DefaultConfig.ADMIN_ID)
async def edit_report_channel(call: types.CallbackQuery):
    await call.message.answer("请输入报告频道 ID (如 -100xxx):")
    await AdminStates.WAITING_FOR_REPORT_CHANNEL.set()

@dp.message_handler(state=AdminStates.WAITING_FOR_REPORT_CHANNEL, user_id=DefaultConfig.ADMIN_ID)
async def save_report_channel(message: types.Message, state: FSMContext):
    db.set_setting("REPORT_CHANNEL", message.text)
    await message.reply("✅ 报告频道已更新")
    await state.finish()

# (Deleted obsolete Start Menu handlers)

# --- 资源库管理逻辑 (抄袭核心) ---
@dp.callback_query_handler(text="add_res_start", user_id=DefaultConfig.ADMIN_ID)
async def add_res_start(call: types.CallbackQuery):
    await call.message.answer("请输入资源名称 (例如: 柚子):")
    await AdminStates.WAITING_FOR_RES_NAME.set()
    await call.answer()

@dp.message_handler(state=AdminStates.WAITING_FOR_RES_NAME, user_id=DefaultConfig.ADMIN_ID)
async def add_res_step1(message: types.Message, state: FSMContext):
    await state.update_data(res_name=message.text)
    await message.reply("请输入跳转链接 (URL):")
    await AdminStates.WAITING_FOR_RES_URL.set()

@dp.message_handler(state=AdminStates.WAITING_FOR_RES_URL, user_id=DefaultConfig.ADMIN_ID)
async def add_res_step2(message: types.Message, state: FSMContext):
    await state.update_data(res_url=message.text)
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(InlineKeyboardButton("🧚 颜值服务", callback_data="res_type_颜值服务"),
           InlineKeyboardButton("👩‍🍳 服务颜值", callback_data="res_type_服务颜值"),
           InlineKeyboardButton("🤸 服务好", callback_data="res_type_服务好"),
           InlineKeyboardButton("🧜 颜值高", callback_data="res_type_颜值高"))
    await message.reply("请选择服务类型：", reply_markup=kb)
    await AdminStates.WAITING_FOR_RES_TYPE.set()

@dp.callback_query_handler(state=AdminStates.WAITING_FOR_RES_TYPE, text_startswith="res_type_", user_id=DefaultConfig.ADMIN_ID)
async def add_res_step3(call: types.CallbackQuery, state: FSMContext):
    res_type = call.data.split("_")[-1]
    await state.update_data(res_type=res_type)
    
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(InlineKeyboardButton("❤️ 可约", callback_data="res_status_1"),
           InlineKeyboardButton("😈 月休", callback_data="res_status_0"))
    await call.message.edit_text("请选择初始状态：", reply_markup=kb)
    await AdminStates.WAITING_FOR_RES_STATUS.set()
    await call.answer()

@dp.callback_query_handler(state=AdminStates.WAITING_FOR_RES_STATUS, text_startswith="res_status_", user_id=DefaultConfig.ADMIN_ID)
async def add_res_step_status(call: types.CallbackQuery, state: FSMContext):
    status = int(call.data.split("_")[-1])
    await state.update_data(res_status=status)
    
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(InlineKeyboardButton("💸 5z-8z", callback_data="tag_price_5-8"),
           InlineKeyboardButton("💸 9z-12z", callback_data="tag_price_9-12"),
           InlineKeyboardButton("💸 13z-16z", callback_data="tag_price_13-16"),
           InlineKeyboardButton("💸 17z+", callback_data="tag_price_17+"))
    await call.message.edit_text("请选择价格标签选项：", reply_markup=kb)
    await AdminStates.WAITING_FOR_RES_PRICE.set()
    await call.answer()

@dp.callback_query_handler(state=AdminStates.WAITING_FOR_RES_PRICE, text_startswith="tag_price_", user_id=DefaultConfig.ADMIN_ID)
async def add_res_step4(call: types.CallbackQuery, state: FSMContext):
    price_tag = call.data.split("_")[-1]
    # 将标签存入 tags (JSON list)
    await state.update_data(res_tags=[f"price_{price_tag}"])
    # 提取数字作为主价格 (可选，这里取下限)
    try:
        main_price = int(price_tag.split('-')[0].replace('+', ''))
    except:
        main_price = 0
    await state.update_data(res_price=main_price)

    kb = InlineKeyboardMarkup(row_width=2)
    regions = ["清江浦", "淮安区", "淮阴区", "洪泽区", "涟水县", "盱眙县", "金湖县"]
    for r in regions:
        kb.add(InlineKeyboardButton(r, callback_data=f"res_region_{r}"))
    await call.message.edit_text("请选择所属区域：", reply_markup=kb)
    await AdminStates.WAITING_FOR_RES_REGION.set()
    await call.answer()

@dp.callback_query_handler(state=AdminStates.WAITING_FOR_RES_REGION, text_startswith="res_region_", user_id=DefaultConfig.ADMIN_ID)
async def add_res_step5(call: types.CallbackQuery, state: FSMContext):
    region = call.data.split("_")[-1]
    await state.update_data(res_region=region)
    kb = InlineKeyboardMarkup(row_width=2).add(
        InlineKeyboardButton("第一页 (首屏)", callback_data="res_page_1"),
        InlineKeyboardButton("第二页 (区域页)", callback_data="res_page_2"),
        InlineKeyboardButton("第三页 (广告/额外)", callback_data="res_page_3")
    )
    await call.message.edit_text("请选择该资源存放的页面：", reply_markup=kb)
    # 不再需要 WAITING_FOR_RES_PAGE 状态，因为 add_res_final 已经处理了 res_page_ 开头
    # 但由于之前没进状态，这里我们显式保留状态或者直接在 final 处理所有状态
    await call.answer()

@dp.callback_query_handler(text_startswith="res_page_", user_id=DefaultConfig.ADMIN_ID, state="*")
async def add_res_final(call: types.CallbackQuery, state: FSMContext):
    # 如果用户没在一流流程中但点击了按钮，可能 data 为空，这里加个保护
    data = await state.get_data()
    if not data or 'res_name' not in data:
        await call.answer("❌ 流程已过期，请重新添加。", show_alert=True)
        await state.finish()
        return

    page = int(call.data.split("_")[-1])
    db.add_resource(
        name=data['res_name'],
        url=data['res_url'],
        price=data['res_price'],
        region=data['res_region'],
        tags=data.get('res_tags', []),
        res_type=data.get('res_type'),
        status=data.get('res_status', 1),
        page=page
    )
    await call.message.answer(f"✅ 资源 {data['res_name']} 已入库并添加到第 {page} 页！")
    await state.finish()
    await call.answer()

@dp.callback_query_handler(text_startswith="toggle_res_", user_id=DefaultConfig.ADMIN_ID, state="*")
async def toggle_res_handler(call: types.CallbackQuery, state: FSMContext = None):
    if state: await state.finish()
    res_id = int(call.data.split("_")[2])
    db.toggle_resource_status(res_id)
    await reset_message_timer(call.message)
    await call.answer("状态已切换")
    call.data = "admin_resources"
    await admin_menu_handler(call, None)

@dp.callback_query_handler(text_startswith="del_res_", user_id=DefaultConfig.ADMIN_ID, state="*")
async def del_res_handler(call: types.CallbackQuery, state: FSMContext = None):
    if state: await state.finish()
    res_id = int(call.data.split("_")[2])
    db.delete_resource(res_id)
    await call.answer("已删除")
    call.data = "admin_resources"
    await admin_menu_handler(call, None)

# ================= 系统命令 =================

@dp.message_handler(commands=['broadcast'], user_id=DefaultConfig.ADMIN_ID)
async def cmd_broadcast(message: types.Message):
    users = db.get_all_users()
    count = 0
    args = message.get_args()
    if not args: return
    for uid in users:
        try: 
            await bot.send_message(uid, f"📢 {args}")
            count += 1
            await asyncio.sleep(0.05)
        except: pass
    await message.reply(f"✅ 送达: {count} 人")

@dp.message_handler(commands=['export'], user_id=DefaultConfig.ADMIN_ID)
async def cmd_export_db(message: types.Message):
    await message.reply_document(types.InputFile(DefaultConfig.DB_NAME))

@dp.message_handler(commands=['import'], content_types=types.ContentType.DOCUMENT, user_id=DefaultConfig.ADMIN_ID)
async def cmd_import_db(message: types.Message):
    if message.caption and '/import' in message.caption:
        await message.document.download(destination_file=DefaultConfig.DB_NAME)
        db.reload()
        await message.reply("✅ 导入成功")
