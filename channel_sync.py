"""从淮安榜频道抓取老师信息，同步到资源库与关键词回复。"""
import html
import logging
import re
import time
from urllib.error import URLError
from urllib.request import Request, urlopen

from config import DefaultConfig

logger = logging.getLogger(__name__)

REGIONS = ["清江浦", "淮安区", "淮阴区", "洪泽区", "涟水县", "盱眙县", "金湖县"]
REGION_ALIASES = {
    "清江浦区": "清江浦", "清江浦": "清江浦",
    "淮安区": "淮安区", "淮安": "淮安区",
    "淮阴区": "淮阴区", "淮阴": "淮阴区",
    "洪泽区": "洪泽区", "洪泽": "洪泽区",
    "涟水县": "涟水县", "涟水": "涟水县",
    "盱眙县": "盱眙县", "盱眙": "盱眙县",
    "金湖县": "金湖县", "金湖": "金湖县",
}
PRICE_TIERS = [
    ("5z-8z", 400, 899),
    ("9z-12z", 900, 1299),
    ("13z-16z", 1300, 1699),
    ("17z+", 1700, 999999),
]
PRICE_KEYWORDS = ["5z-8z", "9z-12z", "13z-16z", "17z+"]
AUTO_KEYWORD_PREFIX = "__auto__"


def _fetch_url(url: str) -> str:
    req = Request(url, headers={"User-Agent": "Mozilla/5.0 (compatible; HuaianBot/1.0)"})
    with urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8", errors="replace")


def _extract_before_link(page_html: str):
    m = re.search(r'<link rel="prev" href="/s/[^"]+\?before=(\d+)"', page_html)
    return int(m.group(1)) if m else None


def _extract_message_blocks(page_html: str) -> list:
    raw_blocks = re.findall(
        r'tgme_widget_message_text[^>]*>(.*?)</div>\s*</div>\s*<div class="tgme_widget_message_footer',
        page_html,
        re.DOTALL,
    )
    blocks = []
    for raw in raw_blocks:
        text = html.unescape(re.sub(r"<[^>]+>", "\n", raw))
        text = re.sub(r"\n{2,}", "\n", text).strip()
        if "名字:" in text or "名字：" in text:
            blocks.append(text)
    return blocks


def fetch_channel_teachers(channel: str = "huaianbendi", max_pages: int = 15) -> list:
    """抓取频道公开预览页，返回去重后的老师列表（同名保留最新一条）。"""
    teachers_by_name = {}
    url = f"https://t.me/s/{channel.lstrip('@')}"
    pages = 0

    while url and pages < max_pages:
        try:
            page_html = _fetch_url(url)
        except URLError as e:
            logger.error("频道抓取失败 %s: %s", url, e)
            break

        parser_blocks = _extract_message_blocks(page_html)
        for block in parser_blocks:
            teacher = parse_teacher_block(block)
            if teacher and teacher["name"] not in teachers_by_name:
                # 从最新帖往旧帖翻页，同名只保留最先出现的（即最新一条）
                teachers_by_name[teacher["name"]] = teacher

        before = _extract_before_link(page_html)
        if before is None:
            break
        url = f"https://t.me/s/{channel.lstrip('@')}?before={before}"
        pages += 1

    return list(teachers_by_name.values())


def parse_price(raw: str) -> int:
    if not raw:
        return 0
    digits = re.sub(r"[^\d]", "", raw)
    if not digits:
        return 0
    val = int(digits)
    # 频道里 "12" 通常表示 12张 = 1200
    if val < 100:
        val *= 100
    return val


def normalize_region(raw: str) -> str:
    raw = (raw or "").strip()
    for key, val in REGION_ALIASES.items():
        if key in raw:
            return val
    return raw.replace("区", "").replace("县", "") or "其他"


def get_price_tier(price: int) -> str:
    for label, low, high in PRICE_TIERS:
        if low <= price <= high:
            return label
    return "其他"


def parse_teacher_block(text: str):
    name_m = re.search(r"名字[:：]\s*(\S+)", text)
    if not name_m:
        return None

    price_m = re.search(r"一次价格[:：]\s*(\S+)", text)
    region_m = re.search(r"地区[:：]\s*(\S+)", text)
    # 优先使用「电报」后的个人账号，其次才用「频道」链接
    telegram_m = re.search(r"电报[:：]\s*\n?\s*(@?[A-Za-z0-9_]+)", text)
    channel_m = re.search(r"频道[:：]\s*\n?\s*(https?://t\.me/\S+|@[A-Za-z0-9_]+)", text)

    price = parse_price(price_m.group(1) if price_m else "")
    region = normalize_region(region_m.group(1) if region_m else "")

    url = ""
    telegram = ""
    if telegram_m:
        telegram = telegram_m.group(1).strip()
        if not telegram.startswith("@"):
            telegram = f"@{telegram}"
        url = f"https://t.me/{telegram.lstrip('@')}"
    elif channel_m:
        url = channel_m.group(1).strip()
        if url.startswith("@"):
            url = f"https://t.me/{url.lstrip('@')}"

    if not url:
        return None

    return {
        "name": name_m.group(1).strip(),
        "price": price,
        "price_tier": get_price_tier(price),
        "region": region,
        "url": url,
        "telegram": telegram,
        "status": 1,
    }


def _format_teacher_line(t: dict) -> str:
    price_z = t["price"] // 100 if t["price"] else "?"
    contact = t.get("telegram") or t["url"]
    return f"❤️ {t['name']} ({price_z}z) → {contact}"


def build_region_keyword_content(region: str, teachers: list) -> str:
    region_teachers = [t for t in teachers if t["region"] == region]
    if not region_teachers:
        return f"📍 **{region}** 暂无在榜老师\n\n数据来自 [淮安榜](https://t.me/huaianbendi)"

    lines = [f"📍 **{region}** 在榜老师（按价格）\n"]
    for tier in PRICE_KEYWORDS:
        group = sorted(
            [t for t in region_teachers if t["price_tier"] == tier],
            key=lambda x: x["price"],
        )
        if group:
            lines.append(f"\n💸 **{tier}**")
            lines.extend(_format_teacher_line(t) for t in group)

    other = [t for t in region_teachers if t["price_tier"] == "其他"]
    if other:
        lines.append("\n💸 **其他**")
        lines.extend(_format_teacher_line(t) for t in other)

    lines.append(f"\n\n🔄 数据同步自 [淮安榜](https://t.me/huaianbendi)")
    return "\n".join(lines)


def build_price_keyword_content(tier: str, teachers: list) -> str:
    group = sorted(
        [t for t in teachers if t["price_tier"] == tier],
        key=lambda x: (x["region"], x["price"]),
    )
    if not group:
        return f"💸 **{tier}** 暂无在榜老师\n\n数据来自 [淮安榜](https://t.me/huaianbendi)"

    lines = [f"💸 **{tier}** 在榜老师（按地区）\n"]
    current_region = None
    for t in group:
        if t["region"] != current_region:
            current_region = t["region"]
            lines.append(f"\n📍 **{current_region}**")
        lines.append(_format_teacher_line(t))

    lines.append(f"\n\n🔄 数据同步自 [淮安榜](https://t.me/huaianbendi)")
    return "\n".join(lines)


def build_mala_keyword_content(teachers: list) -> str:
    lines = [
        "🦢 **麻辣鹅 · 淮安榜实时资源**\n",
        f"共 {len(teachers)} 位在榜老师，按地区发送关键词即可查看：\n",
    ]
    for region in REGIONS:
        count = sum(1 for t in teachers if t["region"] == region)
        if count:
            lines.append(f"• 发送 `{region}` 查看 {count} 位")

    lines.extend([
        "\n按价格档查看：",
        "• `5z-8z` · `9z-12z` · `13z-16z` · `17z+`",
        "\n私聊机器人可浏览完整按钮列表 👇",
    ])
    return "\n".join(lines)


def sync_channel_to_db(db, channel: str = None) -> dict:
    """抓取频道并写入 resources + 自动关键词。返回统计信息。"""
    channel = channel or db.get_setting("SYNC_CHANNEL", DefaultConfig.SYNC_CHANNEL)
    teachers = fetch_channel_teachers(channel)

    db.replace_channel_resources(teachers)

    auto_keywords = {f"{AUTO_KEYWORD_PREFIX}麻辣鹅": build_mala_keyword_content(teachers)}
    for region in REGIONS:
        auto_keywords[f"{AUTO_KEYWORD_PREFIX}{region}"] = build_region_keyword_content(region, teachers)
    for tier in PRICE_KEYWORDS:
        auto_keywords[f"{AUTO_KEYWORD_PREFIX}{tier}"] = build_price_keyword_content(tier, teachers)

    db.replace_auto_keywords(auto_keywords)

    stats = {
        "count": len(teachers),
        "channel": channel,
        "synced_at": int(time.time()),
        "by_region": {r: sum(1 for t in teachers if t["region"] == r) for r in REGIONS},
        "by_tier": {t: sum(1 for x in teachers if x["price_tier"] == t) for t in PRICE_KEYWORDS},
    }
    db.set_setting("LAST_SYNC_STATS", stats)
    logger.info("频道同步完成: %d 位老师", len(teachers))
    return stats
