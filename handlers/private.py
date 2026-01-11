import asyncio
from aiogram import types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.dispatcher import FSMContext

from loader import dp, db, bot
from config import DefaultConfig
from states import ReportStates
from utils import delete_later, check_subscription, get_subscription_keyboard

# ================= 辅助函数：构造 3 列资源网格 =================

def get_resource_grid_keyboard(offset=0):
    kb = InlineKeyboardMarkup(row_width=3)
    
    # 1. 获取资源列表 (取12条)
    resources = db.get_resources(limit=12, offset=offset)
    
    # 2. 构造 3 列网格
    row = []
    for r in resources:
        icon = "❤️" if r['status'] == 1 else "😈"
        btn_text = f"{icon} {r['name']}"
        row.append(InlineKeyboardButton(btn_text, url=r['url']))
        if len(row) == 3:
            kb.row(*row)
            row = []
    if row: # 最后一排不满 3 个也加上
        kb.row(*row)
    
    # 3. 底部导航栏 (模仿蓝精灵)
    kb.row(
        InlineKeyboardButton("🦋 我的蓝精灵", callback_data="my_stats"),
        InlineKeyboardButton("🐕 区域、属性", callback_data="attr_filter")
    )
    
    return kb

# ================= 私聊/菜单逻辑 =================

@dp.message_handler(commands=['start'], chat_type=types.ChatType.PRIVATE)
async def cmd_start(message: types.Message):
    # 记录私聊记录
    db.log_user(message.from_user.id, message.from_user.username or message.from_user.full_name, is_group=False)

    # 检测关注状态
    not_joined = await check_subscription(message.from_user.id)
    link_huaian = db.get_setting("LINK_HUAIAN", DefaultConfig.LINK_HUAIAN)

    if not_joined:
        text = (
            "麻辣鹅「淮安榜提示」\n\n"
            f"鹅友，你好！请先加入 [淮安榜]({link_huaian}) !\n\n"
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
        f"[旅前须知]:联系方式无条件获取，及时验证，请勿鸽人，素质诚信出击;[联系鹅神]({link_service})。\n"
        f"[温馨提示]:切勿相信任何非管理私聊，如有请避免踩雷[踩雷反馈]({link_service})\n"
        "雅俗共赏:行九浅而一深，待十侯而方毕\n"
        "小鹅状态: ❤️可约     😈 月休\n"
        f"安全须知1、[新人说明]({link_newbie}) 2、[群规及操作]({link_rules})\n\n"
        "小精灵，期待与您相约;祝\"旅途\"愉快!感谢支持"
    )
    
    kb = get_resource_grid_keyboard(offset=0)
    sent_msg = await message.answer(success_text, parse_mode="Markdown", reply_markup=kb, disable_web_page_preview=True)
    
    asyncio.create_task(delete_later(sent_msg, 120))
    asyncio.create_task(delete_later(message, 120))

# --- 个人中心 (Butterfly: 我的蓝精灵) ---
@dp.callback_query_handler(text="my_stats")
async def my_stats_handler(call: types.CallbackQuery):
    stats = db.get_user_stats(call.from_user.id)
    if not stats: 
        await call.answer("暂无数据")
        return
    
    text = (
        f"欢迎使用麻辣鹅系统\n"
        f"   [{call.from_user.full_name}](tg://user?id={call.from_user.id})，鹅友，您好!\n"
        "🤗欢迎来到麻辣鹅圈子，立即开始你的麻辣探索之旅吧;\n"
        f"我的ID: `{stats['id']}` ID不要透露给任何人\n"
        f"我的驾照: {stats['level']}\n"
        "下一次: 凡人世界·初级\n\n"
        "----- 【累计水群】 -----\n"
        f"累计发言:{stats['total']}条\n"
        f"日发言:{stats['daily']}条\n"
        f"月发言:{stats['monthly']}条\n"
        f"群聊(有效):{stats['group']}条\n"
        f"私聊(无效):{stats['private']}条"
    )
    
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(InlineKeyboardButton("♻️ 邀请奖励", callback_data="invite_reward"),
           InlineKeyboardButton("📚 我的报告", callback_data="my_reports"))
    kb.add(InlineKeyboardButton("🗣 探索情况", callback_data="explore_status"),
           InlineKeyboardButton("🎁 福利列表", callback_data="welfare_list"))
    kb.add(InlineKeyboardButton("⬅️ 返 回", callback_data="back_to_start"))
    
    await call.message.edit_text(text, parse_mode="Markdown", reply_markup=kb)
    await call.answer()

# --- 区域、属性 (Dog: 区域、属性) ---
@dp.callback_query_handler(text="attr_filter")
async def attr_filter_handler(call: types.CallbackQuery):
    text = (
        "蓝精灵「精灵属性」\n\n"
        "约课模式、精灵类型、收录排序、报告排序、好评排序等等等\n"
        "新人排序:收录时间，倒序分组\n"
        "报告:最多报告，排名靠前\n"
        "好评:近周期内好评数排序\n"
        "精灵类型:待反馈，以蓝友实操，验码反馈\n"
        "精灵指数:综合6个维度、通算法计算得到某一个精灵的指数（构思中）\n"
        "持续整理中"
    )
    
    kb = InlineKeyboardMarkup(row_width=4)
    kb.add(InlineKeyboardButton("🧚 颜值服务", callback_data="filter_yan"),
           InlineKeyboardButton("👩‍🍳 服务颜值", callback_data="filter_ser"),
           InlineKeyboardButton("🤸 服务好", callback_data="filter_good"),
           InlineKeyboardButton("🧜 颜值高", callback_data="filter_high"))
    
    kb.row(InlineKeyboardButton("🧚 新人排序", callback_data="sort_new"),
           InlineKeyboardButton("🏳️ 验证报告", callback_data="sort_report"),
           InlineKeyboardButton("🥇 好评多", callback_data="sort_praise"))
    
    kb.row(InlineKeyboardButton("💸 5z-8z", callback_data="price_1"),
           InlineKeyboardButton("💸 9z-12z", callback_data="price_2"),
           InlineKeyboardButton("💸 13z-16z", callback_data="price_3"),
           InlineKeyboardButton("💸 17z+", callback_data="price_4"))
           
    kb.row(InlineKeyboardButton("🌏 精灵区域", callback_data="region_list"),
           InlineKeyboardButton("⬅️ 返 回", callback_data="back_to_start"))
    
    await call.message.edit_text(text, parse_mode="Markdown", reply_markup=kb)
    await call.answer()

# --- 返回主菜单 ---
@dp.callback_query_handler(text="back_to_start")
async def back_to_start_handler(call: types.CallbackQuery):
    not_joined = await check_subscription(call.from_user.id)
    if not_joined: 
        await call.answer("请先关注频道")
        return
    
    name_link = f"[{call.from_user.full_name}](tg://user?id={call.from_user.id})"
    link_group = db.get_setting("LINK_GROUP", DefaultConfig.LINK_GROUP) or DefaultConfig.LINK_GROUP
    link_service = db.get_setting("LINK_SERVICE", DefaultConfig.LINK_SERVICE) or DefaultConfig.LINK_SERVICE
    link_rules = db.get_setting("LINK_RULES", DefaultConfig.LINK_RULES) or DefaultConfig.LINK_RULES

    success_text = (
        "欢迎使用麻辣鹅系统\n"
        f"    {name_link} ，鹅友，您好!\n"
        f"🤗欢迎来到[麻辣鹅圈子]({link_group})，立即开始你的麻辣探索之旅吧；\n"
        f"    小鹅均为已验证资源!对眼有感即可冲，放心\"旅途\"，勿需多虑!\n"
        f"旅前须知:联系方式无条件获取，及时验证，请勿鸽人，素质诚信出击;[联系鹅神]({link_service})。\n"
        f"温馨提示:切勿相信任何非管理私聊，如有请避免踩雷[踩雷反馈]({link_service})\n"
        "雅俗共赏:行九浅而一深，待十侯而方毕\n"
        "小鹅状态: ❤️可约     😈 月休\n"
        f"安全须知1、[新人说明](https://t.me/huaianbendi/6) 2、[群规及操作]({link_rules})\n\n"
        "小精灵，期待与您相约;祝\"旅途\"愉快!感谢支持"
    )
    
    await call.message.edit_text(success_text, parse_mode="Markdown", reply_markup=get_resource_grid_keyboard(0), disable_web_page_preview=True)
    await call.answer()

@dp.callback_query_handler(text="check_sub")
async def check_sub_handler(call: types.CallbackQuery):
    not_joined = await check_subscription(call.from_user.id)
    if not_joined:
        await call.answer("❌ 你还有未加入的频道！", show_alert=True)
    else:
        await call.message.delete()
        await cmd_start(call.message)

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
