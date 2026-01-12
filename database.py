import sqlite3
import json
import time
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
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    points INTEGER DEFAULT 0,
                    level TEXT DEFAULT '萌新',
                    total_msgs INTEGER DEFAULT 0,
                    daily_msgs INTEGER DEFAULT 0,
                    monthly_msgs INTEGER DEFAULT 0,
                    group_msgs INTEGER DEFAULT 0,
                    private_msgs INTEGER DEFAULT 0,
                    referred_by INTEGER,
                    last_active DATE DEFAULT (DATE('now'))
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
                CREATE TABLE IF NOT EXISTS resources (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT,
                    url TEXT,
                    status INTEGER DEFAULT 1, -- 1=❤️, 0=😈
                    price INTEGER DEFAULT 0,
                    region TEXT,
                    tags TEXT, -- JSON list
                    type TEXT, -- 颜值/服务等
                    page INTEGER DEFAULT 1
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS resources (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT,
                    url TEXT,
                    status INTEGER DEFAULT 1, -- 1=❤️, 0=😈
                    price INTEGER DEFAULT 0,
                    region TEXT,
                    tags TEXT, -- JSON list
                    type TEXT -- 颜值/服务等
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
            
            # Migration for users table
            cursor.execute("PRAGMA table_info(users)")
            user_cols = [info[1] for info in cursor.fetchall()]
            if 'total_msgs' not in user_cols:
                cursor.execute("ALTER TABLE users ADD COLUMN level TEXT DEFAULT '萌新'")
                cursor.execute("ALTER TABLE users ADD COLUMN total_msgs INTEGER DEFAULT 0")
                cursor.execute("ALTER TABLE users ADD COLUMN daily_msgs INTEGER DEFAULT 0")
                cursor.execute("ALTER TABLE users ADD COLUMN monthly_msgs INTEGER DEFAULT 0")
                cursor.execute("ALTER TABLE users ADD COLUMN group_msgs INTEGER DEFAULT 0")
                cursor.execute("ALTER TABLE users ADD COLUMN private_msgs INTEGER DEFAULT 0")
                cursor.execute("ALTER TABLE users ADD COLUMN referred_by INTEGER")
                cursor.execute("ALTER TABLE users ADD COLUMN last_active DATE DEFAULT (DATE('now'))")

            # Migration: Add page column to resources
            cursor.execute("PRAGMA table_info(resources)")
            cols = [info[1] for info in cursor.fetchall()]
            if 'page' not in cols:
                cursor.execute("ALTER TABLE resources ADD COLUMN page INTEGER DEFAULT 1")
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS reports (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    resource_name TEXT,
                    content TEXT,
                    media_id TEXT,
                    media_type TEXT,
                    likes TEXT DEFAULT '[]', -- JSON list of user_ids
                    dislikes TEXT DEFAULT '[]', -- JSON list of user_ids
                    msg_id INTEGER, -- message_id in channel
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS check_ins (
                    user_id INTEGER,
                    check_date DATE DEFAULT (DATE('now')),
                    PRIMARY KEY (user_id, check_date)
                )
            """)
            
            conn.commit()

    # --- Resources (Master Grid) Methods ---
    def add_resource(self, name, url, status=1, price=0, region=None, tags=None, res_type=None, page=1):
        with self._get_conn() as conn:
            tags_json = json.dumps(tags or [])
            conn.execute("""
                INSERT INTO resources (name, url, status, price, region, tags, type, page) 
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (name, url, status, price, region, tags_json, res_type, page))

    def delete_resource(self, res_id):
        with self._get_conn() as conn:
            conn.execute("DELETE FROM resources WHERE id = ?", (res_id,))

    def toggle_resource_status(self, res_id):
        with self._get_conn() as conn:
            conn.execute("UPDATE resources SET status = 1 - status WHERE id = ?", (res_id,))

    def get_resources(self, page=None, limit=50, offset=0, filters=None):
        with self._get_conn() as conn:
            sql = "SELECT id, name, url, status, price, region, tags, type, page FROM resources"
            params = []
            clauses = []
            if page:
                clauses.append("page = ?")
                params.append(page)
            if filters:
                for k, v in filters.items():
                    clauses.append(f"{k} = ?")
                    params.append(v)
            
            if clauses:
                sql += " WHERE " + " AND ".join(clauses)
            
            sql += " ORDER BY status DESC, id DESC LIMIT ? OFFSET ?"
            params.extend([limit, offset])
            
            cursor = conn.execute(sql, params)
            return [self._parse_resource_row(r) for r in cursor.fetchall()]

    def _parse_resource_row(self, row):
        return {
            "id": row[0], "name": row[1], "url": row[2],
            "status": row[3], "price": row[4], "region": row[5],
            "tags": json.loads(row[6]) if row[6] else [],
            "type": row[7], "page": row[8]
        }

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

    # (Deleted obsolete Start Menu methods)

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

    def log_user(self, user_id, username, is_group=True):
        """记录用户信息并统计消息"""
        with self._get_conn() as conn:
            # 1. 尝试初始化或更新基本信息
            conn.execute("""
                INSERT OR IGNORE INTO users (user_id, username) 
                VALUES (?, ?)
            """, (user_id, username))
            
            # 2. 每日清零检测 (重置逻辑在查询时做更稳，但在这里做也行)
            cursor = conn.execute("SELECT last_active FROM users WHERE user_id = ?", (user_id,))
            row = cursor.fetchone()
            today = time.strftime("%Y-%m-%d")
            
            sql_updates = ["total_msgs = total_msgs + 1", "last_active = ?"]
            params = [today]
            
            if row and row[0] != today:
                # 跨天了，重置日增长
                sql_updates.append("daily_msgs = 1")
            else:
                sql_updates.append("daily_msgs = daily_msgs + 1")
            
            if is_group:
                sql_updates.append("group_msgs = group_msgs + 1")
                sql_updates.append("points = points + 1")
            else:
                sql_updates.append("private_msgs = private_msgs + 1")
                
            conn.execute(f"UPDATE users SET {', '.join(sql_updates)} WHERE user_id = ?", params + [user_id])

    def add_points(self, user_id, amount):
        with self._get_conn() as conn:
            conn.execute("UPDATE users SET points = points + ? WHERE user_id = ?", (amount, user_id))

    def get_user_stats(self, user_id):
        with self._get_conn() as conn:
            cursor = conn.execute("""
                SELECT user_id, username, level, total_msgs, daily_msgs, monthly_msgs, group_msgs, private_msgs, points 
                FROM users WHERE user_id = ?
            """, (user_id,))
            row = cursor.fetchone()
            if not row: return None
            return {
                "id": row[0], "name": row[1], "level": row[2],
                "total": row[3], "daily": row[4], "monthly": row[5],
                "group": row[6], "private": row[7], "points": row[8]
            }

    # --- Reports Methods ---
    def add_report(self, user_id, resource_name, content, media_id=None, media_type=None):
        with self._get_conn() as conn:
            cursor = conn.execute("""
                INSERT INTO reports (user_id, resource_name, content, media_id, media_type)
                VALUES (?, ?, ?, ?, ?)
            """, (user_id, resource_name, content, media_id, media_type))
            return cursor.lastrowid

    def update_report_msg(self, report_id, msg_id):
        with self._get_conn() as conn:
            conn.execute("UPDATE reports SET msg_id = ? WHERE id = ?", (msg_id, report_id))

    def get_report(self, report_id):
        with self._get_conn() as conn:
            row = conn.execute("SELECT * FROM reports WHERE id = ?", (report_id,)).fetchone()
            if not row: return None
            return {
                "id": row[0], "user_id": row[1], "resource_name": row[2],
                "content": row[3], "media_id": row[4], "media_type": row[5],
                "likes": json.loads(row[6]), "dislikes": json.loads(row[7]),
                "msg_id": row[8]
            }

    def toggle_vote(self, report_id, user_id, is_like=True):
        """记录投票，同一人只能二选一"""
        report = self.get_report(report_id)
        if not report: return None
        
        likes = set(report['likes'])
        dislikes = set(report['dislikes'])
        
        if is_like:
            if user_id in likes:
                likes.remove(user_id)
            else:
                likes.add(user_id)
                if user_id in dislikes: dislikes.remove(user_id)
        else:
            if user_id in dislikes:
                dislikes.remove(user_id)
            else:
                dislikes.add(user_id)
                if user_id in likes: likes.remove(user_id)
        
        with self._get_conn() as conn:
            conn.execute("UPDATE reports SET likes = ?, dislikes = ? WHERE id = ?", 
                         (json.dumps(list(likes)), json.dumps(list(dislikes)), report_id))
            
        return len(likes), len(dislikes)


    def get_reports_by_mascot(self, mascot_name, limit=5):
        with self._get_conn() as conn:
            cursor = conn.execute("""
                SELECT * FROM reports WHERE resource_name = ? 
                ORDER BY (json_array_length(likes) - json_array_length(dislikes)) DESC, created_at DESC 
                LIMIT ?
            """, (mascot_name, limit))
            return [self._parse_report_row(r) for r in cursor.fetchall()]

    def get_user_reports_count(self, user_id):
        with self._get_conn() as conn:
            res = conn.execute("SELECT COUNT(*) FROM reports WHERE user_id = ?", (user_id,)).fetchone()
            return res[0] if res else 0

    def get_user_reports_list(self, user_id, limit=3):
        with self._get_conn() as conn:
            cursor = conn.execute("SELECT resource_name FROM reports WHERE user_id = ? ORDER BY created_at DESC LIMIT ?", (user_id, limit))
            return [row[0] for row in cursor.fetchall()]

    def do_check_in(self, user_id):
        """每日签到逻辑，返回 (是否成功, 获得的积分/原因)"""
        today = time.strftime("%Y-%m-%d")
        with self._get_conn() as conn:
            # 检查今天是否签过到
            exists = conn.execute("SELECT 1 FROM check_ins WHERE user_id = ? AND check_date = ?", (user_id, today)).fetchone()
            if exists:
                return False, "您今天已经签过到了哦！明日再来吧～"
            
            # 签到
            conn.execute("INSERT INTO check_ins (user_id, check_date) VALUES (?, ?)", (user_id, today))
            
            # 随机奖励 1-5 积分
            import random
            points = random.randint(1, 5)
            self.add_points(user_id, points)
            return True, points

    def _parse_report_row(self, row):
        return {
            "id": row[0], "user_id": row[1], "resource_name": row[2],
            "content": row[3], "media_id": row[4], "media_type": row[5],
            "likes": json.loads(row[6]), "dislikes": json.loads(row[7]),
            "msg_id": row[8], "created_at": row[9]
        }

    # (Obsolete Methods Consolidated Above)
