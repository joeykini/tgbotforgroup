import asyncio
import logging
from aiogram import types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.dispatcher import FSMContext

from loader import dp, db, bot
from config import DefaultConfig
from states import ReportStates
from utils import delete_later, check_subscription, get_subscription_keyboard, reset_message_timer

# ================= 辅助函数：构造 3 列资源网格 =================

def get_resource_grid_keyboard(page=1):
    kb = InlineKeyboardMarkup(row_width=3)
    
    if page == 2:
        # 区域选择页面：显示 7 个行政区
        regions = ["清江浦", "淮安区", "淮阴区", "洪泽区", "涟水县", "盱眙县", "金湖县"]
        btns = [InlineKeyboardButton(r, callback_data=f"filter_region_{r}") for r in regions]
        # 每行 3 个
        for i in range(0, len(btns), 3):
            kb.row(*btns[i:i+3])
        
        kb.row(
            InlineKeyboardButton("❮ 首屏", callback_data="welcome_page_1"),
            InlineKeyboardButton("🌸 广告页 ❯", callback_data="welcome_page_3")
        )
        return kb

    # 统一从 resources 表获取数据 (Page 1 or 3)
    items = db.get_resources(page=page)
    
    # 按状态分组
    active = [r for r in items if r.get('status') == 1]
    resting = [r for r in items if r.get('status') == 0]
    
    # 构造网格的辅助函数
    def add_items_to_kb(res_items):
        if not res_items: return
        row = []
        for item in res_items:
            icon = "❤️" if item.get('status') == 1 else "😈"
            kb_text = f"{icon}{item['name']}"
            kb_url = item['url']
            row.append(InlineKeyboardButton(kb_text, url=kb_url))
            if len(row) == 3:
                kb.row(*row)
                row = []
        if row:
            kb.row(*row)

    # 先放可约，再放月休
    add_items_to_kb(active)
    add_items_to_kb(resting)
    
    # 底部导航栏
    if page == 1:
        link_vpn = db.get_setting("LINK_VPN", DefaultConfig.LINK_VPN)
        kb.row(InlineKeyboardButton("✈️ VPN推荐", url=link_vpn))
        kb.row(
            InlineKeyboardButton("🦋 我的统计", callback_data="my_home_stats"),
            InlineKeyboardButton("🐕 区域页 ❯", callback_data="welcome_page_2")
        )
    else: # page 3
        kb.row(
            InlineKeyboardButton("❮ 区域页", callback_data="welcome_page_2"),
            InlineKeyboardButton("🏠 返回首页", callback_data="welcome_page_1")
        )
    
    return kb

def get_region_resources_keyboard(region):
    kb = InlineKeyboardMarkup(row_width=3)
    items = db.get_resources(filters={"region": region}, limit=100)
    
    active = [r for r in items if r.get('status') == 1]
    resting = [r for r in items if r.get('status') == 0]
    
    def add_items_to_kb(res_items):
        if not res_items: return
        row = []
        for item in res_items:
            icon = "❤️" if item.get('status') == 1 else "😈"
            kb_text = f"{icon}{item['name']}"
            kb_url = item['url']
            row.append(InlineKeyboardButton(kb_text, url=kb_url))
            if len(row) == 3:
                kb.row(*row)
                row = []
        if row: kb.row(*row)

    add_items_to_kb(active)
    add_items_to_kb(resting)
    
    kb.add(InlineKeyboardButton("⬅️ 返回区域列表", callback_data="welcome_page_2"))
    return kb

def get_welcome_text(user_full_name, user_id):
    name_link = f"[{user_full_name}](tg://user?id={user_id})"
    link_group = db.get_setting("LINK_GROUP", DefaultConfig.LINK_GROUP) or DefaultConfig.LINK_GROUP
    link_service = db.get_setting("LINK_SERVICE", DefaultConfig.LINK_SERVICE) or DefaultConfig.LINK_SERVICE
    link_rules = db.get_setting("LINK_RULES", DefaultConfig.LINK_RULES) or DefaultConfig.LINK_RULES
    link_newbie = "https://t.me/huaianbendi/6" 

    return (
        "欢迎使用麻辣鹅系统\n"
        f"    {name_link} ，鹅友，您好!\n"
        f"🤗欢迎来到[麻辣鹅圈子]({link_group})，立即开始你的麻辣探索之旅吧；\n"
        f"    小鹅均为已验证资源!对眼有感即可冲，放心\"旅途\"，勿需多虑!\n"
        f"[旅前须知]:联系方式无条件获取，及时验证，请勿鸽人，素质诚信出击;[联系鹅神]({link_service})。\n"
        f"[温馨提示]:切勿相信任何非管理私聊，如有请避免踩雷[踩雷反馈]({link_service})\n"
        "雅俗共赏:行九浅而一深，待十侯而方毕\n"
        "小鹅状态: ❤️可约     😈 月休\n"
        f"安全须知1、[新人说明]({link_newbie}) 2、[群规及操作]({link_rules})\n\n"
        "小鹅，期待与您相约;祝\"旅途\"愉快!感谢支持"
    )

@dp.message_handler(commands=['start'], chat_type=types.ChatType.PRIVATE)
async def cmd_start(message: types.Message):
    # 记录私聊记录
    args = message.get_args()
    user_id = message.from_user.id
    
    # 检测是否是新用户并处理邀请
    is_new_user = False
    with db._get_conn() as conn:
        res = conn.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,)).fetchone()
        if not res:
            is_new_user = True

    db.log_user(user_id, message.from_user.username or message.from_user.full_name, is_group=False)

    if is_new_user and args and args.isdigit():
        referrer_id = int(args)
        if referrer_id != user_id:
            db.add_points(referrer_id, 10) # 邀请奖励 10 积分
            with db._get_conn() as conn:
                conn.execute("UPDATE users SET referred_by = ? WHERE user_id = ?", (referrer_id, user_id))
            try:
                await bot.send_message(referrer_id, f"🎊 嘿！鹅友 {message.from_user.full_name} 通过您的链接开启了探索，您获得了 10 积分！")
            except: pass

    # 报告请在本群操作，不再跳转私聊
    if args and (args.startswith("report_") or args.startswith("view_report_")):
        await message.reply("📝 请在群内发送 `报告 名字` 或 `看报告 名字`，无需私聊本 Bot。", parse_mode="Markdown")
        return

    # 检测关注状态
    not_joined = await check_subscription(user_id)
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
        await delete_later(sent_msg, 120)
        return

    success_text = get_welcome_text(message.from_user.full_name, message.from_user.id)
    kb = get_resource_grid_keyboard(page=1)
    sent_msg = await message.answer(success_text, parse_mode="Markdown", reply_markup=kb, disable_web_page_preview=True)
    
    await delete_later(sent_msg, 120)
    await delete_later(message, 120)

@dp.callback_query_handler(text="welcome_page_1", state="*")
@dp.callback_query_handler(text="welcome_page_2", state="*")
@dp.callback_query_handler(text="welcome_page_3", state="*")
async def welcome_pagination_handler(call: types.CallbackQuery, state: FSMContext = None):
    if state: await state.finish()
    try:
        page = int(call.data.split("_")[-1])
        kb = get_resource_grid_keyboard(page=page)
        text = get_welcome_text(call.from_user.full_name, call.from_user.id)
        
        await reset_message_timer(call.message)
        await call.message.edit_text(text, parse_mode="Markdown", reply_markup=kb, disable_web_page_preview=True)
    except Exception as e:
        # 忽略 "Message is not modified" 错误
        if "message is not modified" not in str(e).lower():
            print(f"Pagination error: {e}")
    await call.answer()

@dp.callback_query_handler(text_startswith="filter_region_", state="*")
async def region_filter_handler(call: types.CallbackQuery, state: FSMContext = None):
    if state: await state.finish()
    try:
        region = call.data.replace("filter_region_", "")
        kb = get_region_resources_keyboard(region)
        text = get_welcome_text(call.from_user.full_name, call.from_user.id)
        text = f"📍 当前选择区域：{region}\n\n" + text
        
        await reset_message_timer(call.message)
        await call.message.edit_text(text, parse_mode="Markdown", reply_markup=kb, disable_web_page_preview=True)
    except:
        pass
    await call.answer()

# --- 个人中心 (Butterfly: 我的麻辣鹅) ---
@dp.callback_query_handler(text="my_home_stats", state="*")
async def my_stats_handler(call: types.CallbackQuery, state: FSMContext = None):
    if state: await state.finish()
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
        f"私聊(无效):{stats['private']}条\n"
        f"----- 【鹅神积分】 -----\n"
        f"当前积分: {stats['points']} 🦢\n"
        "*(注: 积分可通过在群内发言获得)*"
    )
    
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(InlineKeyboardButton("♻️ 邀请奖励", callback_data="invite_reward"),
           InlineKeyboardButton("📚 我的报告", callback_data="my_reports"))
    kb.add(InlineKeyboardButton("🗣 探索情况", callback_data="explore_status"),
           InlineKeyboardButton("🎁 福利列表", callback_data="welfare_list"))
    kb.add(InlineKeyboardButton("⬅️ 返 回", callback_data="welcome_page_1"))
    
    await call.message.edit_text(text, parse_mode="Markdown", reply_markup=kb)
    await call.answer()

@dp.callback_query_handler(text="invite_reward", state="*")
@dp.callback_query_handler(text="my_reports", state="*")
@dp.callback_query_handler(text="explore_status", state="*")
@dp.callback_query_handler(text="welfare_list", state="*")
async def stats_sub_handler(call: types.CallbackQuery, state: FSMContext = None):
    if state: await state.finish()
    
    action = call.data
    kb = InlineKeyboardMarkup().add(InlineKeyboardButton("⬅️ 返回统计", callback_data="my_home_stats"))
    
    if action == "invite_reward":
        bot_info = await bot.get_me()
        invite_link = f"https://t.me/{bot_info.username}?start={call.from_user.id}"
        text = (
            "♻️ **邀请奖励说明**\n\n"
            "邀请好友加入淮安榜，可获得以下奖励：\n"
            "1. 每成功邀请 1 位好友：获得 10 积分\n"
            "2. 累计邀请 10 位好友：获得「探险家」称号\n\n"
            "**您的专属邀请链接：**\n"
            f"`{invite_link}`\n\n"
            "*(点击链接即可复制，发送给好友，对方点击「开始」后即可生效)*"
        )
    elif action == "my_reports":
        count = db.get_user_reports_count(call.from_user.id)
        recent = db.get_user_reports_list(call.from_user.id)
        
        text = (
            "📚 **我的报告**\n\n"
            f"您共提交了 **{count}** 份实操反馈。\n\n"
        )
        if recent:
            text += "**最近报告的小鹅：**\n"
            for name in recent:
                text += f"- #{name}\n"
        else:
            text += "🧩 您尚未提交任何报告，点击「报告」按钮提交您的第一份实操反馈吧！"
    elif action == "explore_status":
        text = (
            "🗣 **探索情况与积分规则**\n\n"
            "**1. 积分获取：**\n"
            "- 群内有效发言：+1 积分/条\n"
            "- 邀请好友、提交报告等均可获得额外积分奖励。\n"
            "- 私聊机器人由于不产生互动，不计入积分。\n\n"
            "**2. 等级制度：**\n"
            "- 萌新：0-100 积分\n"
            "- 探路者：101-500 积分\n"
            "- 鹅神使者：501+ 积分\n\n"
            "持续活跃可解锁更多私密资源与福利。"
        )
    elif action == "welfare_list":
        text = (
            "🎁 **福利列表**\n\n"
            "当前可用福利：\n"
            "1. **每日签到**：每日可领取 1-5 随机积分奖励。\n"
            "2. **新人首充礼包**：内含 50 积分（构思中）。\n\n"
            "点击下方按钮进行签到：适配中..."
        )
        kb.insert(InlineKeyboardButton("📅 立即签到", callback_data="do_check_in"))
    else:
        text = "功能模块建设中..."

    await call.message.edit_text(text, parse_mode="Markdown", reply_markup=kb)
    await call.answer()

@dp.callback_query_handler(text="do_check_in", state="*")
async def check_in_handler(call: types.CallbackQuery):
    success, result = db.do_check_in(call.from_user.id)
    if success:
        await call.answer(f"✅ 签到成功！恭喜获得 {result} 鹅神积分！🦢", show_alert=True)
        # 刷新页面显示最新积分 (可选，这里我们直接弹窗更直观)
        await my_stats_handler(call)
    else:
        await call.answer(result, show_alert=True)

# --- 区域页原逻辑 (保留用于 attr_filter 按钮如果将来要用) ---
@dp.callback_query_handler(text="attr_filter")
async def attr_filter_handler(call: types.CallbackQuery):
    text = (
        "麻辣鹅「小鹅属性」\n\n"
        "约课模式、小鹅类型、收录排序、报告排序、好评排序等等等\n"
        "新人排序:收录时间，倒序分组\n"
        "报告:最多报告，排名靠前\n"
        "好评:近周期内好评数排序\n"
        "小鹅类型:待反馈，以鹅友实操，验码反馈\n"
        "小鹅指数:综合6个维度、通算法计算得到某一个小鹅的指数（构思中）\n"
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
           
    kb.row(InlineKeyboardButton("🌏 小鹅区域", callback_data="region_list"),
           InlineKeyboardButton("⬅️ 返 回", callback_data="welcome_page_1"))
    
    await call.message.edit_text(text, parse_mode="Markdown", reply_markup=kb)
    await call.answer()

# --- 返回主菜单 ---
@dp.callback_query_handler(text="back_to_start", state="*")
async def back_to_start_handler(call: types.CallbackQuery, state: FSMContext = None):
    if state: await state.finish()
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
        "小鹅，期待与您相约;祝\"旅途\"愉快!感谢支持"
    )
    
    await reset_message_timer(call.message)
    await call.message.edit_text(success_text, parse_mode="Markdown", reply_markup=get_resource_grid_keyboard(1), disable_web_page_preview=True)
    await call.answer()

# (Deleted obsolete start_item handler)

@dp.callback_query_handler(text="check_sub")
async def check_sub_handler(call: types.CallbackQuery):
    not_joined = await check_subscription(call.from_user.id)
    if not_joined:
        await call.answer("❌ 你还有未加入的频道！", show_alert=True)
    else:
        await call.message.delete()
        await cmd_start(call.message)

@dp.chat_member_handler()
async def auto_check_sub(chat_member: types.ChatMemberUpdated):
    """用户加入频道/群组时仅记录，不主动私聊发消息。"""
    if chat_member.new_chat_member.status not in ["member", "administrator", "creator"]:
        return
    user_id = chat_member.from_user.id
    db.log_user(user_id, chat_member.from_user.username or chat_member.from_user.full_name, is_group=False)

from report_utils import REPORT_TEMPLATE, get_report_kb

# ================= 报告逻辑（私聊仅查看，提交请在群内） =================

@dp.message_handler(state=ReportStates.WAITING_FOR_REPORT_CONTENT, content_types=[types.ContentType.TEXT, types.ContentType.PHOTO, types.ContentType.VIDEO])
async def process_report_content(message: types.Message, state: FSMContext):
    # 报告仅在群内提交，私聊不发
    if message.chat.type == types.ChatType.PRIVATE:
        await state.finish()
        await message.reply("📝 请在群内发送 `报告 小鹅名字` 提交反馈，无需私聊本 Bot。", parse_mode="Markdown")
        return

    data = await state.get_data()
    mascot_name = data.get("report_mascot", "未知")
    
    content = message.text or message.caption or ""
    if not content:
        await message.reply("⚠️ 请发送填好模版的文字内容（可附带图片/视频）。")
        return

    media_id = None
    media_type = None
    if message.photo:
        media_id = message.photo[-1].file_id
        media_type = "photo"
    elif message.video:
        media_id = message.video.file_id
        media_type = "video"

    # 匿名检测
    is_anonymous = "我要匿名" in content
    sender_name = "匿名鹅友" if is_anonymous else message.from_user.full_name
    content = content.replace("我要匿名", "").strip()

    # 保存到数据库
    report_id = db.add_report(message.from_user.id, mascot_name, content, media_id, media_type)

    # 推送目标：优先使用来源群组，否则使用配置频道
    target_chat = data.get("target_chat") or db.get_setting("REPORT_CHANNEL", DefaultConfig.REPORT_CHANNEL)
    
    if target_chat:
        prefix = f"👤 **来自: {sender_name}**\n\n"
        report_text = prefix + content
        sent_msg = None
        try:
            kb = get_report_kb(report_id)
            if media_type == "photo":
                sent_msg = await bot.send_photo(target_chat, media_id, caption=report_text, reply_markup=kb, parse_mode="Markdown")
            elif media_type == "video":
                sent_msg = await bot.send_video(target_chat, media_id, caption=report_text, reply_markup=kb, parse_mode="Markdown")
            else:
                sent_msg = await bot.send_message(target_chat, report_text, reply_markup=kb, parse_mode="Markdown")
            
            if sent_msg:
                db.update_report_msg(report_id, sent_msg.message_id)
        except Exception as e:
            logging.error(f"Failed to send report to target {target_chat}: {e}")

    await message.reply("✅ 报告已提交，感谢您的真实反馈！\n积分奖励已到账（构思中）。")
    await state.finish()

@dp.callback_query_handler(text_startswith="vote_", state="*")
async def vote_handler(call: types.CallbackQuery):
    parts = call.data.split("_")
    action = parts[1] # like / dislike
    report_id = int(parts[2])
    
    res = db.toggle_vote(report_id, call.from_user.id, is_like=(action=="like"))
    if not res:
        await call.answer("报告不存在")
        return
    
    likes, dislikes = res
    try:
        await call.message.edit_reply_markup(reply_markup=get_report_kb(report_id, likes, dislikes))
        await call.answer(f"投票成功！当前：👍{likes} 👎{dislikes}")
    except Exception as e:
        if "message is not modified" not in str(e).lower():
            await call.answer("由于消息过旧，无法更新按钮显示，但投票已记录。")
        else:
            await call.answer("您已点击过。")

@dp.message_handler(lambda m: m.text and m.text.startswith("看报告"), chat_type=types.ChatType.PRIVATE, state="*")
async def view_reports_msg(message: types.Message, state: FSMContext = None):
    if state: await state.finish()
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("📝 请输入要查看的小鹅名字，例如：`看报告 欣欣宝`")
        return
    
    mascot_name = parts[1].strip()
    reports = db.get_reports_by_mascot(mascot_name)
    
    if not reports:
        await message.answer(f"🔍 暂无关于 `#{mascot_name}` 的实操报告，快去提交第一份吧！", parse_mode="Markdown")
        return

    await message.answer(f"📚 为您找到关于 `#{mascot_name}` 的最新/精选报告：", parse_mode="Markdown")
    
    for r in reports:
        likes = len(r['likes'])
        dislikes = len(r['dislikes'])
        prefix = f"👤 **报告人ID: {r['user_id']}** (👍{likes} 👎{dislikes})\n\n"
        text = prefix + r['content']
        kb = get_report_kb(r['id'], likes, dislikes)
        
        try:
            if r['media_type'] == "photo":
                await message.answer_photo(r['media_id'], caption=text, reply_markup=kb, parse_mode="Markdown")
            elif r['media_type'] == "video":
                await message.answer_video(r['media_id'], caption=text, reply_markup=kb, parse_mode="Markdown")
            else:
                await message.answer(text, reply_markup=kb, parse_mode="Markdown")
        except Exception as e:
            logging.error(f"Error displaying report {r['id']}: {e}")

# --- 原有的回调触发 ---
@dp.callback_query_handler(text="report", state="*")
async def start_report_callback(call: types.CallbackQuery, state: FSMContext = None):
    if state: await state.finish()
    await call.answer("请在群内发送：报告 小鹅名字", show_alert=True)
