class DefaultConfig:
    # 基础配置 (Token和ID通常不建议动态修改，除非重启Bot)
    API_TOKEN = '8479273528:AAFA6c52AuxfXY3nd_nnAuFlwKQqxbfDrlI'
    ADMIN_ID = 6799513564
    DB_NAME = "bot_data.db"
    
    # 默认动态配置
    AD_INTERVAL = 8 * 60 * 60
    WELCOME_ENABLED = True
    ANTI_LINK_ENABLED = True
    REQUIRED_CHANNELS = [
        {"name": "淮安麻辣鹅", "id": "@huaianbendi", "url": "https://t.me/huaianbendi"},
        {"name": "麻辣鹅圈子", "id": "@hamalae8", "url": "https://t.me/hamalae8"},
    ]
    CONTACT_USER = "客服/投稿"
    CONTACT_URL = "https://t.me/egchabot" # 指向新的双向Bot
    AD_CONTENT = "📢 定时广告：记得回来看看哦！"
    REPORT_CHANNEL = None # 报告频道ID (需管理员设置)
    
    # 链接配置默认值
    LINK_NEWBIE = "https://t.me/huaianbendi/6"      # 新人说明
    LINK_RULES = "https://t.me/huaianbendi/7"       # 群规及操作
    LINK_SAFETY = "https://t.me/ljltop/2348"      # 安全指南 
    LINK_TERMS = "https://t.me/huaianbendi/8"       # 术语
    LINK_SERVICE = "https://t.me/egchabot"      # 客服/鹅神 (指向新Bot)
    LINK_HUAIAN = "https://t.me/huaianbendi"      # 淮安榜
    LINK_GROUP = "https://t.me/hamalae8"          # 群组
