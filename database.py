import sqlite3
import json
from config import DefaultConfig

class Database:
    def __init__(self, db_name=DefaultConfig.DB_NAME):
        self.db_name = db_name
        self.conn = None
        self.create_tables()

    def _get_conn(self):
        if not self.conn:
            self.conn = sqlite3.connect(self.db_name, check_same_thread=False)
        return self.conn
    
    def reload(self):
        """重载数据库连接（用于恢复备份后）"""
        if self.conn:
            try: self.conn.close()
            except: pass
        self.conn = None
        self.create_tables()

    def create_tables(self):
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY, username TEXT, points INTEGER DEFAULT 0
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS buttons (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, text TEXT, url TEXT
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS custom_buttons (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    text TEXT,
                    url TEXT
                )
            """)
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS start_menu (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    text TEXT,
                    action_type TEXT, -- link, reply, report
                    action_value TEXT, -- url or text content
                    media_id TEXT, -- file_id for images
                    row_index INTEGER DEFAULT 0
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS keyword_replies (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    keyword TEXT UNIQUE,
                    reply_content TEXT
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS scheduled_ads (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    content TEXT,
                    images TEXT, -- JSON list of file_ids
                    msg_type TEXT, -- text, photo, album
                    title TEXT, -- Helper name
                    buttons TEXT -- JSON list of [text, url]
                )
            """)
            
            # Migration: Check if columns exist
            cursor.execute("PRAGMA table_info(scheduled_ads)")
            columns = [info[1] for info in cursor.fetchall()]
            if 'title' not in columns:
                cursor.execute("ALTER TABLE scheduled_ads ADD COLUMN title TEXT")
            if 'buttons' not in columns:
                cursor.execute("ALTER TABLE scheduled_ads ADD COLUMN buttons TEXT")
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS message_forwards (
                    group_message_id INTEGER PRIMARY KEY,
                    user_id INTEGER,
                    original_message_id INTEGER
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS active_groups (
                    chat_id INTEGER PRIMARY KEY,
                    title TEXT
                )
            """)
            
            conn.commit()

    # --- Custom Buttons Methods ---
    def add_button(self, text, url):
        with self._get_conn() as conn:
            conn.execute("INSERT INTO custom_buttons (text, url) VALUES (?, ?)", (text, url))

    def delete_button(self, button_id):
        with self._get_conn() as conn:
            conn.execute("DELETE FROM custom_buttons WHERE id = ?", (button_id,))

    def get_buttons(self):
        with self._get_conn() as conn:
            cursor = conn.execute("SELECT id, text, url FROM custom_buttons")
            return [{"id": row[0], "text": row[1], "url": row[2]} for row in cursor.fetchall()]

    # --- Scheduled Ads Methods ---
    def add_ad(self, content, images, msg_type, title=None, buttons=None):
        with self._get_conn() as conn:
            images_json = json.dumps(images or [])
            buttons_json = json.dumps(buttons or [])
            conn.execute("INSERT INTO scheduled_ads (content, images, msg_type, title, buttons) VALUES (?, ?, ?, ?, ?)", 
                         (content, images_json, msg_type, title, buttons_json))

    def update_ad(self, ad_id, **kwargs):
        """Update specific fields of an ad"""
        valid_keys = ['content', 'images', 'msg_type', 'title', 'buttons']
        updates = []
        values = []
        for key, value in kwargs.items():
            if key in valid_keys:
                if key in ['images', 'buttons']:
                    value = json.dumps(value or [])
                updates.append(f"{key} = ?")
                values.append(value)
        
        if not updates: return
        
        values.append(ad_id)
        sql = f"UPDATE scheduled_ads SET {', '.join(updates)} WHERE id = ?"
        with self._get_conn() as conn:
            conn.execute(sql, values)

    def delete_ad(self, ad_id):
        with self._get_conn() as conn:
            conn.execute("DELETE FROM scheduled_ads WHERE id = ?", (ad_id,))

    def get_ad(self, ad_id):
        with self._get_conn() as conn:
            row = conn.execute("SELECT id, content, images, msg_type, title, buttons FROM scheduled_ads WHERE id=?", (ad_id,)).fetchone()
            if not row: return None
            return self._parse_ad_row(row)

    def get_all_ads(self):
        with self._get_conn() as conn:
            cursor = conn.execute("SELECT id, content, images, msg_type, title, buttons FROM scheduled_ads")
            return [self._parse_ad_row(row) for row in cursor.fetchall()]

    def _parse_ad_row(self, row):
        try:
            images = json.loads(row[2])
        except:
            images = []
        try:
            # 兼容旧数据，如果没有 buttons 列或为 None
            buttons = json.loads(row[5]) if len(row) > 5 and row[5] else []
        except:
            buttons = []
            
        return {
            "id": row[0],
            "content": row[1],
            "images": images,
            "msg_type": row[3],
            "title": row[4] if len(row) > 4 else None,
            "buttons": buttons
        }

    # --- Keyword Reply Methods ---
    def add_keyword_reply(self, keyword, reply_content):
        with self._get_conn() as conn:
            conn.execute("INSERT OR REPLACE INTO keyword_replies (keyword, reply_content) VALUES (?, ?)", (keyword, reply_content))

    def delete_keyword_reply(self, keyword_id):
        with self._get_conn() as conn:
            conn.execute("DELETE FROM keyword_replies WHERE id = ?", (keyword_id,))

    def get_all_keywords(self):
        with self._get_conn() as conn:
            cursor = conn.execute("SELECT id, keyword, reply_content FROM keyword_replies")
            return [{"id": row[0], "keyword": row[1], "reply_content": row[2]} for row in cursor.fetchall()]

    def get_keyword_reply(self, text):
        """查找匹配的关键词回复"""
        keywords = self.get_all_keywords()
        for kw in keywords:
            if kw['keyword'] in text:
                return kw['reply_content']
        return None

    # --- Start Menu Methods (NEW) ---
    def add_start_menu_item(self, text, action_type, action_value=None, media_id=None):
        with self._get_conn() as conn:
            conn.execute("INSERT INTO start_menu (text, action_type, action_value, media_id) VALUES (?, ?, ?, ?)", 
                         (text, action_type, action_value, media_id))

    def delete_start_menu_item(self, item_id):
        with self._get_conn() as conn:
            conn.execute("DELETE FROM start_menu WHERE id = ?", (item_id,))

    def get_start_menu_items(self):
        with self._get_conn() as conn:
            cursor = conn.execute("SELECT id, text, action_type, action_value, media_id FROM start_menu")
            return [{"id": row[0], "text": row[1], "type": row[2], "value": row[3], "media": row[4]} for row in cursor.fetchall()]

    def get_start_menu_item(self, item_id):
        with self._get_conn() as conn:
            row = conn.execute("SELECT id, text, action_type, action_value, media_id FROM start_menu WHERE id = ?", (item_id,)).fetchone()
            if not row: return None
            return {"id": row[0], "text": row[1], "type": row[2], "value": row[3], "media": row[4]}

    # --- Settings Methods ---
    def set_setting(self, key, value):
        """保存配置 (自动JSON序列化)"""
        if isinstance(value, (list, dict)):
            value = json.dumps(value, ensure_ascii=False)
        else:
            value = str(value)
            
        with self._get_conn() as conn:
            conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value))

    def get_setting(self, key, default=None):
        """读取配置 (自动JSON反序列化)"""
        with self._get_conn() as conn:
            res = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
            if not res:
                return default
            
            val = res[0]
            try:
                return json.loads(val)
            except (json.JSONDecodeError, TypeError):
                if val.isdigit(): return int(val)
                if val.lower() == 'true': return True
                if val.lower() == 'false': return False
                return val

    def save_forward(self, group_msg_id, user_id, original_msg_id):
        with self._get_conn() as conn:
            conn.execute("INSERT OR REPLACE INTO message_forwards (group_message_id, user_id, original_message_id) VALUES (?, ?, ?)", 
                         (group_msg_id, user_id, original_msg_id))
            
    def get_forward_info(self, group_msg_id):
        with self._get_conn() as conn:
            cursor = conn.execute("SELECT user_id, original_message_id FROM message_forwards WHERE group_message_id = ?", (group_msg_id,))
            row = cursor.fetchone()
            return row if row else (None, None)

    def add_group(self, chat_id, title):
        with self._get_conn() as conn:
            conn.execute("INSERT OR REPLACE INTO active_groups (chat_id, title) VALUES (?, ?)", (chat_id, title))

    def get_all_groups(self):
        with self._get_conn() as conn:
            try:
                cursor = conn.execute("SELECT chat_id FROM active_groups")
                return [row[0] for row in cursor.fetchall()]
            except:
                return []

    def get_all_users(self):
        """获取所有已记录的用户ID"""
        with self._get_conn() as conn:
            try:
                cursor = conn.execute("SELECT user_id FROM users")
                return [row[0] for row in cursor.fetchall()]
            except:
                return []

    def log_user(self, user_id, username):
        """记录用户信息"""
        with self._get_conn() as conn:
            conn.execute("INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)", (user_id, username))
