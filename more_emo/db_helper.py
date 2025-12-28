# db_helper.py
"""
数据库操作工具类
封装所有数据库相关操作
支持多数据库切换
"""
import pymysql
from pymysql.cursors import DictCursor
import json
import datetime
from dbutils.pooled_db import PooledDB


class DBHelper:
    def __init__(self, config):
        # 基础配置
        self.base_config = config.copy()
        if 'database' in self.base_config:
            self.default_db = self.base_config.pop('database')
        else:
            self.default_db = 'treehole'

        # 连接池缓存
        self._pools = {}

    def _get_pool(self, db_name=None):
        """获取或创建对应数据库的连接池"""
        dbname = db_name or self.default_db
        if dbname not in self._pools:
            cfg = self.base_config.copy()
            cfg['database'] = dbname
            # 创建连接池
            self._pools[dbname] = PooledDB(
                creator=pymysql,
                maxconnections=10,
                blocking=True,
                **cfg
            )
        return self._pools[dbname]

    # =========================================================
    # 1. 核心方法：执行增删改 (之前缺失的部分!)
    # =========================================================
    def execute(self, sql: str, params=None, db: str = None):
        """
        执行 INSERT/UPDATE/DELETE 语句
        返回: 新插入行的主键 ID (lastrowid) 或受影响行数
        """
        pool = self._get_pool(db)
        conn = pool.connection()
        cursor = conn.cursor()
        try:
            cursor.execute(sql, params or ())
            conn.commit()
            # 爬虫非常需要这个返回值(book_id)
            return cursor.lastrowid
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            cursor.close()
            conn.close()

    # =========================================================
    # 2. 核心方法：执行查询
    # =========================================================
    def query(self, sql: str, params=None, db: str = None):
        """
        执行 SELECT 语句
        返回: 字典列表
        """
        pool = self._get_pool(db)
        conn = pool.connection()
        cursor = conn.cursor(cursor=DictCursor)  # 确保返回字典
        try:
            cursor.execute(sql, params or ())
            return cursor.fetchall()
        finally:
            cursor.close()
            conn.close()

    # =========================================================
    # 3. 适配层 (完美兼容你的两个爬虫代码)
    # =========================================================

    # 适配 edge_douban_crawler.py (调用 self.db.insert)
    def insert(self, sql: str, params=None, db: str = None):
        return self.execute(sql, params, db)

    # 适配 book_crawler.py (调用 self.db.execute_insert)
    def execute_insert(self, sql: str, params=None, db: str = None):
        return self.execute(sql, params, db)

    # 适配可能的查询别名
    def execute_query(self, sql: str, params=None, db: str = None):
        return self.query(sql, params, db)

    def execute_update(self, sql: str, params=None, db: str = None):
        return self.execute(sql, params, db)

    def _get_pool(self, db_name=None):
        """获取或创建对应数据库的连接池"""
        dbname = db_name or self.default_db
        if dbname not in self._pools:
            cfg = self.base_config.copy()
            cfg['database'] = dbname
            # 创建连接池
            self._pools[dbname] = PooledDB(
                creator=pymysql,
                maxconnections=10,
                blocking=True,
                **cfg
            )
        return self._pools[dbname]

    def query(self, sql: str, params=None, db: str = None):
        """
        执行 SQL：
        - SELECT -> 返回 list[dict]
        - 非 SELECT -> commit 并返回影响行数
        """
        pool = self._get_pool(db)
        conn = pool.connection()
        cursor = conn.cursor()
        try:
            cursor.execute(sql, params or ())
            if sql.strip().upper().startswith('SELECT'):
                return cursor.fetchall()
            else:
                conn.commit()
                return cursor.rowcount
        finally:
            cursor.close()
            conn.close()

    # =========================================================
    # 工具函数（原db_util中的功能）
    # =========================================================

    @staticmethod
    def to_json(obj) -> str:
        """把 list/dict 转成 JSON 字符串"""
        return json.dumps(obj, ensure_ascii=False)

    @staticmethod
    def today_date() -> datetime.date:
        return datetime.date.today()

    @staticmethod
    def calc_continuous_days(dates_desc) -> int:
        """
        计算连续打卡天数：
        - 输入：按时间倒序的 date 列表
        - 规则：从今天开始连续往前数，遇到断档停止
        """
        if not dates_desc:
            return 0

        def _to_date(x):
            if x is None:
                return None
            if isinstance(x, datetime.datetime):
                return x.date()
            if isinstance(x, datetime.date):
                return x
            # 'YYYY-MM-DD'
            try:
                return datetime.datetime.strptime(str(x)[:10], "%Y-%m-%d").date()
            except Exception:
                return None

        date_set = set()
        for d in dates_desc:
            dd = _to_date(d)
            if dd:
                date_set.add(dd)

        today = datetime.date.today()
        continuous = 0
        cur = today
        while cur in date_set:
            continuous += 1
            cur = cur - datetime.timedelta(days=1)
        return continuous

    def format_sleep_record(self, record):
        """将 sleep 记录中的 timedelta 对象转换为字符串"""
        if not record:
            return None

        # 创建副本以避免修改原始数据
        formatted = record.copy()

        # 转换 bedtime (timedelta -> HH:MM)
        if 'bedtime' in formatted and hasattr(formatted['bedtime'], 'total_seconds'):
            total_sec = int(formatted['bedtime'].total_seconds())
            hours = total_sec // 3600
            minutes = (total_sec % 3600) // 60
            formatted['bedtime'] = f"{hours:02d}:{minutes:02d}"

        # 转换 wake_time (timedelta -> HH:MM)
        if 'wake_time' in formatted and hasattr(formatted['wake_time'], 'total_seconds'):
            total_sec = int(formatted['wake_time'].total_seconds())
            hours = total_sec // 3600
            minutes = (total_sec % 3600) // 60
            formatted['wake_time'] = f"{hours:02d}:{minutes:02d}"

        # 转换 datetime/date 为字符串
        for key, value in formatted.items():
            if isinstance(value, (datetime.date, datetime.datetime)):
                formatted[key] = str(value)

        return formatted


# =========================================================
# 多数据库助手（替代原db_util）
# =========================================================

# 基础数据库配置
BASE_DB_CONFIG = {
    'host': '127.0.0.1',
    'port': 3306,
    'user': 'root',
    'password': '123456',
    'charset': 'utf8mb4',
    'cursorclass': DictCursor
}

# 创建全局多数据库实例
multi_db_helper = DBHelper(BASE_DB_CONFIG)

# 数据库常量
TEST_DB = "test"
TREEHOLE_DB = "treehole"
MOOD_DB = "Mood Check-In"


# =========================================================
# 书城数据库操作类（保持不变）
# =========================================================
class BookDB:
    def __init__(self, db_helper):
        self.db = db_helper
        self.db.default_db = "book_db"  # 设置书城的默认数据库

    # ========== 书籍相关操作 ==========
    def get_books(self, page=1, page_size=10, category=None, keyword=None):
        """
        获取书籍列表
        """
        offset = (page - 1) * page_size

        sql = """
            SELECT id, title, author, cover, brief, category, tags, rating, pages, 
                   created_at, updated_at
            FROM books 
            WHERE 1=1
        """
        params = []

        if keyword and keyword.strip():
            keyword_like = f"%{keyword.strip()}%"
            sql += " AND (title LIKE %s OR author LIKE %s OR brief LIKE %s OR tags LIKE %s)"
            params.extend([keyword_like, keyword_like, keyword_like, keyword_like])

        if category and category.strip() and category != '全部':
            sql += " AND category = %s"
            params.append(category.strip())

        # 获取总数
        count_sql = f"SELECT COUNT(*) as total FROM ({sql}) as t"
        total_result = self.db.query(count_sql, params)
        total = total_result[0]['total'] if total_result else 0

        # 获取分页数据
        sql += " ORDER BY id DESC LIMIT %s OFFSET %s"
        params.extend([page_size, offset])

        books = self.db.query(sql, params)

        # 处理tags字段
        for book in books:
            if book['tags']:
                book['tags'] = [tag.strip() for tag in book['tags'].split(',') if tag.strip()]
            else:
                book['tags'] = []

        return {
            "list": books,
            "total": total,
            "page": page,
            "pageSize": page_size,
            "totalPages": (total + page_size - 1) // page_size
        }

    def get_book_by_id(self, book_id):
        """
        根据ID获取书籍详情
        """
        sql = "SELECT * FROM books WHERE id = %s"
        books = self.db.query(sql, (book_id,))

        if not books:
            return None

        book = books[0]

        # 处理tags
        if book['tags']:
            book['tags'] = [tag.strip() for tag in book['tags'].split(',') if tag.strip()]

        # 处理chapters（JSON字符串转对象）
        if book.get('chapters'):
            try:
                book['chapters'] = json.loads(book['chapters'])
            except:
                book['chapters'] = []
        else:
            book['chapters'] = []

        return book

    def add_book(self, book_data):
        """
        添加书籍
        """
        sql = """
            INSERT INTO books 
            (title, author, cover, brief, category, tags, content, chapters, 
             rating, pages, publisher, publish_date, isbn)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """

        # 处理tags
        tags = book_data.get('tags', [])
        tags_str = ','.join(tags) if isinstance(tags, list) else str(tags)

        # 处理chapters
        chapters = book_data.get('chapters', [])
        chapters_json = json.dumps(chapters, ensure_ascii=False)

        params = (
            book_data['title'],
            book_data['author'],
            book_data.get('cover', ''),
            book_data.get('brief', ''),
            book_data['category'],
            tags_str,
            book_data.get('content', ''),
            chapters_json,
            book_data.get('rating', 4.5),
            book_data.get('pages', 0),
            book_data.get('publisher', ''),
            book_data.get('publish_date'),
            book_data.get('isbn', '')
        )

        book_id = self.db.query(sql, params)
        return book_id

    def update_book(self, book_id, book_data):
        """
        更新书籍
        """
        sql = """
            UPDATE books 
            SET title=%s, author=%s, cover=%s, brief=%s, category=%s, 
                tags=%s, content=%s, chapters=%s, rating=%s, pages=%s,
                publisher=%s, publish_date=%s, isbn=%s, updated_at=NOW()
            WHERE id = %s
        """

        # 处理tags
        tags = book_data.get('tags', [])
        tags_str = ','.join(tags) if isinstance(tags, list) else str(tags)

        # 处理chapters
        chapters = book_data.get('chapters', [])
        chapters_json = json.dumps(chapters, ensure_ascii=False)

        params = (
            book_data['title'],
            book_data['author'],
            book_data.get('cover', ''),
            book_data.get('brief', ''),
            book_data['category'],
            tags_str,
            book_data.get('content', ''),
            chapters_json,
            book_data.get('rating', 4.5),
            book_data.get('pages', 0),
            book_data.get('publisher', ''),
            book_data.get('publish_date'),
            book_data.get('isbn', ''),
            book_id
        )

        rows = self.db.query(sql, params)
        return rows > 0

    def delete_book(self, book_id):
        """
        删除书籍
        """
        sql = "DELETE FROM books WHERE id = %s"
        rows = self.db.query(sql, (book_id,))
        return rows > 0

    def search_books(self, keyword, limit=20):
        """
        搜索书籍
        """
        keyword_like = f"%{keyword}%"
        sql = """
            SELECT id, title, author, cover, brief, category, tags, rating
            FROM books 
            WHERE title LIKE %s OR author LIKE %s OR brief LIKE %s
            ORDER BY id DESC
            LIMIT %s
        """

        books = self.db.query(sql, (keyword_like, keyword_like, keyword_like, limit))

        for book in books:
            if book['tags']:
                book['tags'] = [tag.strip() for tag in book['tags'].split(',') if tag.strip()]

        return books

    # ========== 用户收藏相关操作 ==========
    def add_favorite(self, user_id, book_id):
        """
        添加收藏
        """
        sql = "INSERT IGNORE INTO user_favorites (user_id, book_id) VALUES (%s, %s)"
        rows = self.db.query(sql, (user_id, book_id))
        return rows > 0

    def remove_favorite(self, user_id, book_id):
        """
        移除收藏
        """
        sql = "DELETE FROM user_favorites WHERE user_id = %s AND book_id = %s"
        rows = self.db.query(sql, (user_id, book_id))
        return rows > 0

    def get_user_favorites(self, user_id, page=1, page_size=10):
        """
        获取用户收藏列表
        """
        offset = (page - 1) * page_size

        # 1. 先获取总数
        count_sql = """
            SELECT COUNT(*) as total
            FROM user_favorites uf
            WHERE uf.user_id = %s
        """
        count_result = self.db.query(count_sql, (user_id,))
        total = count_result[0]['total'] if count_result else 0

        # 2. 获取分页数据
        sql = """
            SELECT 
                b.id, b.title, b.author, b.cover, b.brief, b.category, 
                b.tags, b.rating, b.pages, b.publisher, b.publish_date,
                uf.created_at as favorited_at
            FROM user_favorites uf
            JOIN books b ON uf.book_id = b.id
            WHERE uf.user_id = %s
            ORDER BY uf.created_at DESC
            LIMIT %s OFFSET %s
        """

        books = self.db.query(sql, (user_id, page_size, offset))

        # 3. 处理tags字段
        for book in books:
            if book.get('tags'):
                book['tags'] = [tag.strip() for tag in book['tags'].split(',') if tag.strip()]
            else:
                book['tags'] = []

        # 4. 构建完整返回结构
        return {
            "list": books,
            "total": total,
            "page": page,
            "pageSize": page_size,
            "totalPages": (total + page_size - 1) // page_size if page_size > 0 else 0,
            "hasMore": page * page_size < total
        }

    def is_favorited(self, user_id, book_id):
        """
        检查是否已收藏
        """
        sql = "SELECT 1 FROM user_favorites WHERE user_id = %s AND book_id = %s"
        result = self.db.query(sql, (user_id, book_id))
        return len(result) > 0


# 创建书城数据库实例
book_db = BookDB(multi_db_helper)