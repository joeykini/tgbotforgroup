import os


def _load_dotenv():
    """加载项目根目录 .env（不覆盖已有环境变量）。"""
    env_path = os.path.join(os.path.dirname(__file__), ".env")
    if not os.path.isfile(env_path):
        return
    with open(env_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            key = key.strip()
            val = val.strip().strip('"').strip("'")
            os.environ.setdefault(key, val)


_load_dotenv()


def _require_env(name: str) -> str:
    val = os.getenv(name, "").strip()
    if not val:
        raise RuntimeError(
            f"缺少环境变量 {name}。请复制 .env.example 为 .env 并填写，或在系统中 export 该变量。"
        )
    return val


def _int_env(name: str, default: int = None) -> int:
    val = os.getenv(name, "").strip()
    if not val:
        if default is None:
            raise RuntimeError(f"缺少环境变量 {name}")
        return default
    return int(val)


def _list_env(name: str, default: list) -> list:
    val = os.getenv(name, "").strip()
    if not val:
        return default
    return [item.strip() for item in val.split(",") if item.strip()]


class DefaultConfig:
    # 敏感配置 — 仅从环境变量读取
    API_TOKEN = _require_env("BOT_API_TOKEN")
    ADMIN_ID = _int_env("BOT_ADMIN_ID")
    DB_NAME = os.getenv("BOT_DB_NAME", "bot_data.db")

    # 拥有 Bot 后台权限的频道/群组（其管理员均可操作 /settings）
    ADMIN_CHATS = _list_env("BOT_ADMIN_CHATS", ["@huaianbendi", "@hamalae8"])

    # 默认动态配置
    AD_INTERVAL = 8 * 60 * 60
    WELCOME_ENABLED = True
    ANTI_LINK_ENABLED = True
    REQUIRED_CHANNELS = [
        {"name": "淮安麻辣鹅", "id": "@huaianbendi", "url": "https://t.me/huaianbendi"},
        {"name": "麻辣鹅圈子", "id": "@hamalae8", "url": "https://t.me/hamalae8"},
    ]
    CONTACT_USER = "客服/投稿"
    CONTACT_URL = "https://t.me/egchabot"
    AD_CONTENT = "📢 定时广告：记得回来看看哦！"
    REPORT_CHANNEL = None

    # 链接配置默认值
    LINK_NEWBIE = "https://t.me/huaianbendi/6"
    LINK_RULES = "https://t.me/huaianbendi/7"
    LINK_SAFETY = "https://t.me/ljltop/2348"
    LINK_TERMS = "https://t.me/huaianbendi/8"
    LINK_SERVICE = "https://t.me/egchabot"
    LINK_HUAIAN = "https://t.me/huaianbendi"
    LINK_GROUP = "https://t.me/hamalae8"
    LINK_VPN = "https://t.me/huaianbendi/25"

    # 频道同步
    SYNC_CHANNEL = os.getenv("BOT_SYNC_CHANNEL", "huaianbendi")
    SYNC_INTERVAL = _int_env("BOT_SYNC_INTERVAL", 4 * 60 * 60)
    ANTI_BOT_ENABLED = False  # 默认不自动踢 Bot，避免影响其他定时发消息 Bot
