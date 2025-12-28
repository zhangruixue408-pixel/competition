# edge_douban_crawler.py
"""
完整的Edge浏览器豆瓣书籍爬虫
"""
import os
import time
import random
import re
import json
from urllib.parse import quote
from datetime import datetime

from selenium import webdriver
from selenium.webdriver.edge.service import Service
from selenium.webdriver.edge.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
import pymysql
import requests

# 导入你的数据库模块
try:
    from db_helper import DBHelper, BookDB, multi_db_helper

    DB_AVAILABLE = True
except ImportError:
    print("⚠️ 数据库模块不可用，将以测试模式运行")
    DB_AVAILABLE = False


class EdgeDoubanCrawler:
    """使用Edge浏览器的豆瓣图书爬虫"""

    def __init__(self, db_helper=None, headless=True):
        """
        初始化爬虫

        Args:
            db_helper: 数据库助手实例
            headless: 是否使用无头模式
        """
        # 使用提供的db_helper或创建新的
        if db_helper:
            self.db = db_helper
            self.book_db = BookDB(db_helper) if hasattr(db_helper, 'book_db') else None
        elif DB_AVAILABLE:
            # 如果没有提供db_helper，但DB_AVAILABLE为True，使用multi_db_helper
            self.db = multi_db_helper
            self.db.default_db = "book_db"  # 设置书城的默认数据库
            self.book_db = BookDB(self.db)
        else:
            self.db = None
            self.book_db = None

        # 初始化Edge浏览器
        self.driver = self.init_edge_driver(headless=headless)

        # 用户代理
        self.user_agent = self.driver.execute_script("return navigator.userAgent;")
        print(f"📱 使用浏览器: Edge - {self.user_agent[:50]}...")

        # 存储cookies文件路径
        self.cookies_file = 'douban_cookies_edge.json'

    def init_edge_driver(self, headless=True):
        """初始化Edge浏览器驱动"""
        print("🚀 正在初始化Edge浏览器...")

        # Edge选项
        edge_options = Options()

        if headless:
            edge_options.add_argument('--headless')  # 无头模式
            edge_options.add_argument('--disable-gpu')

        # 模拟真实浏览器
        edge_options.add_argument('--disable-blink-features=AutomationControlled')
        edge_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        edge_options.add_experimental_option('useAutomationExtension', False)

        # 添加其他选项
        edge_options.add_argument('--no-sandbox')
        edge_options.add_argument('--disable-dev-shm-usage')
        edge_options.add_argument('--disable-web-security')
        edge_options.add_argument('--allow-running-insecure-content')
        edge_options.add_argument('--window-size=1920,1080')

        # 设置用户代理
        user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36 Edg/119.0.0.0',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36 Edg/118.0.0.0',
        ]
        edge_options.add_argument(f'user-agent={random.choice(user_agents)}')

        # 禁用图片加载以加快速度（可选）
        # prefs = {"profile.managed_default_content_settings.images": 2}
        # edge_options.add_experimental_option("prefs", prefs)

        try:
            # Edge通常不需要指定驱动路径，系统会自动查找
            driver = webdriver.Edge(options=edge_options)

            # 执行JavaScript来隐藏自动化特征
            driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

            print("✅ Edge浏览器初始化成功")
            return driver

        except Exception as e:
            print(f"❌ Edge浏览器初始化失败: {e}")
            print("💡 解决方案:")
            print("1. 确保已安装最新版Microsoft Edge浏览器")
            print("2. 可能需要安装Microsoft Edge WebDriver")
            print("3. 下载地址: https://developer.microsoft.com/en-us/microsoft-edge/tools/webdriver/")
            raise

    def save_cookies(self):
        """保存cookies到文件"""
        cookies = self.driver.get_cookies()
        with open(self.cookies_file, 'w', encoding='utf-8') as f:
            json.dump(cookies, f, ensure_ascii=False, indent=2)
        print(f"✅ Cookies已保存到 {self.cookies_file}")

    def load_cookies(self):
        """从文件加载cookies"""
        if not os.path.exists(self.cookies_file):
            print(f"⚠️ Cookies文件不存在: {self.cookies_file}")
            return False

        try:
            with open(self.cookies_file, 'r', encoding='utf-8') as f:
                cookies = json.load(f)

            # 先访问豆瓣首页以设置域名
            self.driver.get('https://www.douban.com')
            time.sleep(2)

            # 添加cookies
            for cookie in cookies:
                try:
                    # 移除无效字段
                    if 'expiry' in cookie:
                        cookie['expiry'] = int(cookie['expiry'])

                    self.driver.add_cookie(cookie)
                except Exception as e:
                    print(f"⚠️ 添加cookie失败: {e}")
                    continue

            print(f"✅ Cookies加载成功")
            return True

        except Exception as e:
            print(f"❌ 加载cookies失败: {e}")
            return False

    def login_douban(self, username=None, password=None):
        """手动登录豆瓣"""
        print("🔐 正在打开豆瓣登录页面...")

        # 打开登录页面
        self.driver.get('https://www.douban.com/login')
        time.sleep(3)

        if username and password:
            print("尝试自动登录...")
            try:
                # 尝试查找用户名和密码输入框（豆瓣可能有多种登录方式）
                username_inputs = self.driver.find_elements(By.NAME, 'username')
                password_inputs = self.driver.find_elements(By.NAME, 'password')

                if username_inputs and password_inputs:
                    username_inputs[0].send_keys(username)
                    password_inputs[0].send_keys(password)

                    # 查找登录按钮
                    login_buttons = self.driver.find_elements(By.CLASS_NAME, 'btn-account')
                    if login_buttons:
                        login_buttons[0].click()
                    else:
                        # 尝试通过XPath查找
                        login_buttons = self.driver.find_elements(By.XPATH, "//input[@type='submit']")
                        if login_buttons:
                            login_buttons[0].click()

                    print("✅ 已提交登录信息")
                    time.sleep(3)
                else:
                    print("⚠️ 未找到登录表单，需要手动登录")

            except Exception as e:
                print(f"❌ 自动登录失败: {e}")
                print("请手动登录...")

        # 等待用户手动登录
        input("👤 请在浏览器中完成登录（如有验证码请处理），然后按回车键继续...")

        # 保存cookies
        self.save_cookies()
        print("✅ 登录完成，cookies已保存")

    def search_books(self, keyword, count=10, scroll_times=3):
        """
        使用Edge搜索豆瓣书籍

        Args:
            keyword: 搜索关键词
            count: 要获取的书籍数量
            scroll_times: 滚动次数以加载更多内容
        """
        try:
            encoded_keyword = quote(keyword.encode('utf-8'))
            url = f'https://search.douban.com/book/subject_search?search_text={encoded_keyword}&cat=1001'

            print(f"🔍 搜索关键词: {keyword}")
            print(f"🌐 访问URL: {url}")

            # 访问搜索页面
            self.driver.get(url)
            time.sleep(4)  # 等待初始加载

            # 等待页面加载
            print("⏳ 等待页面加载...")

            # 方法1：等待特定元素出现
            try:
                wait = WebDriverWait(self.driver, 20)
                # 豆瓣搜索结果页面可能有多种结构
                wait.until(
                    EC.presence_of_element_located(
                        (By.CSS_SELECTOR, "div.item-root, div.sc-bZQynM, div[data-id], div.title"))
                )
                print("✅ 页面主要内容已加载")
            except Exception as e:
                print(f"⚠️ 等待超时，可能页面结构不同: {e}")
                # 即使超时也继续，可能页面已经加载了

            # 模拟人类行为：随机滚动以加载更多内容
            print(f"🔄 模拟滚动 {scroll_times} 次以加载更多内容...")
            for i in range(scroll_times):
                # 随机滚动
                scroll_height = random.randint(300, 1200)
                self.driver.execute_script(f"window.scrollTo(0, {scroll_height});")
                time.sleep(random.uniform(1.5, 3))

                # 偶尔滚动到底部
                if i % 2 == 0:
                    self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                    time.sleep(random.uniform(2, 4))

            # 最后等待一下让内容完全加载
            time.sleep(3)

            # 获取页面源码
            page_source = self.driver.page_source

            # 保存页面用于调试
            debug_file = f'edge_douban_{keyword}_{int(time.time())}.html'
            with open(debug_file, 'w', encoding='utf-8') as f:
                f.write(page_source)
            print(f"💾 页面源码已保存到 {debug_file}")

            # 解析页面
            soup = BeautifulSoup(page_source, 'html.parser')
            books = self.parse_search_results(soup, count)

            print(f"✅ 搜索完成，找到 {len(books)} 本书")
            return books

        except Exception as e:
            print(f"❌ 搜索失败: {e}")
            import traceback
            traceback.print_exc()

            # 保存错误截图
            try:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                self.driver.save_screenshot(f'edge_error_{keyword}_{timestamp}.png')
                print(f"📸 错误截图已保存")
            except:
                pass

            return []

    def parse_search_results(self, soup, max_count):
        """解析搜索结果页面"""
        books = []

        print("🧠 开始解析页面内容...")

        # 首先检查页面是否有数据
        if "正在搜索" in soup.text or "加载中" in soup.text:
            print("⚠️ 页面可能还在加载中，数据可能不完整")

        # 策略1：查找所有包含书籍信息的div
        # 豆瓣的书籍条目通常有这些特征
        book_candidates = []

        # 查找所有包含"/subject/"的链接
        subject_links = soup.find_all('a', href=lambda x: x and '/subject/' in x)
        print(f"找到 {len(subject_links)} 个subject链接")

        # 为每个subject链接找到最近的父div作为书籍容器
        for link in subject_links[:max_count * 3]:  # 多找一些
            # 向上找父元素，直到找到合适的div容器
            parent = link.parent
            for _ in range(5):  # 最多向上找5层
                if parent and parent.name == 'div':
                    if parent not in book_candidates:
                        # 检查这个div是否包含书籍相关信息
                        has_title = link.text.strip()
                        has_other_info = parent.text and len(parent.text.strip()) > 20
                        if has_title and has_other_info:
                            book_candidates.append(parent)
                            break
                if parent:
                    parent = parent.parent
                else:
                    break

        # 策略2：查找所有图片，找到书籍封面
        if len(book_candidates) < max_count:
            imgs = soup.find_all('img')
            for img in imgs:
                src = img.get('src', '')
                alt = img.get('alt', '')
                # 检查是否可能是书籍封面
                if src and ('cover' in src or 'img' in src or 'book' in alt.lower()):
                    parent_div = img.find_parent('div')
                    if parent_div and parent_div not in book_candidates:
                        book_candidates.append(parent_div)

        print(f"总共找到 {len(book_candidates)} 个候选书籍条目")

        # 提取每个候选条目的信息
        seen_titles = set()
        for i, item in enumerate(book_candidates):
            if len(books) >= max_count:
                break

            try:
                book_info = self.extract_book_info(item)
                if book_info and book_info.get('title'):
                    title = book_info['title']

                    # 去重
                    if title in seen_titles:
                        print(f"  ⚠️ 跳过重复: {title[:30]}...")
                        continue

                    seen_titles.add(title)
                    books.append(book_info)
                    print(f"  ✅ {len(books)}. {title[:40]}... - {book_info.get('author', '未知')[:20]}")
            except Exception as e:
                print(f"  解析第{i + 1}个条目时出错: {e}")
                continue

        return books

    def extract_book_info(self, item):
        """从单个条目中提取书籍信息"""
        info = {}

        # 1. 提取标题 - 查找所有a标签中的文本
        title = ''

        # 首先查找包含"/subject/"的链接文本
        for a in item.find_all('a', href=lambda x: x and '/subject/' in x):
            text = a.text.strip()
            if text and len(text) > 2 and len(text) < 100:
                title = text
                break

        # 如果没找到，查找任何a标签
        if not title:
            for a in item.find_all('a'):
                text = a.text.strip()
                if text and 2 < len(text) < 100 and not text.startswith('http'):
                    title = text
                    break

        info['title'] = title

        # 2. 提取链接
        detail_url = ''
        for a in item.find_all('a', href=lambda x: x and '/subject/' in x):
            href = a.get('href', '')
            if '/subject/' in href:
                detail_url = href
                # 确保是完整URL
                if not detail_url.startswith('http'):
                    detail_url = 'https://book.douban.com' + detail_url
                break

        info['detail_url'] = detail_url

        # 3. 提取封面
        cover = ''
        for img in item.find_all('img'):
            src = img.get('src', '')
            if src and ('cover' in src or 'img' in src):
                cover = src
                # 尝试获取大一点的图片
                if 'spic' in cover:
                    cover = cover.replace('spic', 'lpic')
                elif 's_ratio' in cover:
                    cover = cover.replace('s_ratio', 'm_ratio')
                break

        info['cover'] = cover

        # 4. 提取作者和出版社信息
        author = '未知作者'
        publisher = ''

        # 查找包含斜杠分隔的文本（作者/出版社/出版日期/价格）
        for elem in item.find_all(['div', 'span', 'p']):
            text = elem.text.strip()
            if '/' in text and 10 < len(text) < 200:
                parts = [p.strip() for p in text.split('/') if p.strip()]
                if len(parts) >= 3:
                    # 通常格式：作者 / 出版社 / 出版日期 / 价格
                    author = parts[0]
                    if len(parts) >= 4:
                        # 尝试识别出版社（通常不是纯数字）
                        for part in parts[1:-2]:  # 跳过第一个（作者）和最后两个（日期、价格）
                            if not re.match(r'^\d', part) and len(part) < 30:
                                publisher = part
                                break
                    break

        info['author'] = author
        info['publisher'] = publisher

        # 5. 提取评分
        rating = 4.0

        # 查找评分数字（格式如：8.5、9.0等）
        for elem in item.find_all(['span', 'div', 'p']):
            text = elem.text.strip()
            # 匹配数字评分
            rating_match = re.search(r'(\d+\.\d+)', text)
            if rating_match:
                try:
                    rating_val = float(rating_match.group(1))
                    if 1 <= rating_val <= 10:
                        rating = rating_val
                        break
                except:
                    pass

        info['rating'] = rating

        # 6. 其他信息
        info['source'] = 'douban_edge'

        return info

    def get_book_detail(self, detail_url):
        """获取书籍详情页信息"""
        if not detail_url:
            return None

        print(f"📖 获取详情: {detail_url[:60]}...")

        try:
            # 访问详情页
            self.driver.get(detail_url)
            time.sleep(4)  # 等待页面加载

            # 等待主要内容加载
            try:
                wait = WebDriverWait(self.driver, 15)
                # 等待信息区域或标题加载
                wait.until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "#info, span[property='v:itemreviewed']"))
                )
            except:
                print("⚠️ 详情页加载可能较慢或结构不同")

            # 获取页面源码
            page_source = self.driver.page_source
            soup = BeautifulSoup(page_source, 'html.parser')

            # 解析详情信息
            detail = self.parse_detail_page(soup)

            print(f"  ✅ 详情获取成功")
            return detail

        except Exception as e:
            print(f"  ❌ 详情获取失败: {e}")
            return None

    def parse_detail_page(self, soup):
        """解析详情页信息"""
        detail = {}

        # 1. 标题
        title_elem = soup.find('span', property='v:itemreviewed')
        if title_elem:
            detail['title'] = title_elem.text.strip()
        else:
            # 备选选择器
            title_elem = soup.find('h1')
            if title_elem:
                detail['title'] = title_elem.text.strip()

        # 2. 封面（大图）
        cover_elem = soup.find('img', alt=detail.get('title', ''))
        if not cover_elem:
            # 尝试其他选择器
            cover_elem = soup.find('a', class_='nbg')
            if cover_elem:
                cover_elem = cover_elem.find('img')

        if cover_elem and cover_elem.get('src'):
            cover_url = cover_elem['src']
            # 替换为大尺寸
            if 's_ratio_poster' in cover_url:
                cover_url = cover_url.replace('s_ratio_poster', 'l_ratio_poster')
            detail['cover'] = cover_url

        # 3. 信息区域（作者、出版社等）
        info_soup = soup.find('div', id='info')
        if info_soup:
            info_text = info_soup.get_text('\n', strip=True)

            # 提取作者
            author_match = re.search(r'作者[:\s]\s*(.+)', info_text)
            if author_match:
                detail['author'] = author_match.group(1).split('\n')[0].strip()

            # 提取出版社
            publisher_match = re.search(r'出版社[:\s]\s*(.+)', info_text)
            if publisher_match:
                detail['publisher'] = publisher_match.group(1).split('\n')[0].strip()

            # 提取出版日期
            pubdate_match = re.search(r'出版年[:\s]\s*(.+)', info_text)
            if pubdate_match:
                detail['publish_date'] = pubdate_match.group(1).split('\n')[0].strip()

            # 提取ISBN
            isbn_match = re.search(r'ISBN[:\s]\s*(\d+)', info_text)
            if isbn_match:
                detail['isbn'] = isbn_match.group(1).strip()

            # 提取页数
            pages_match = re.search(r'页数[:\s]\s*(\d+)', info_text)
            if pages_match:
                try:
                    detail['pages'] = int(pages_match.group(1))
                except:
                    detail['pages'] = 0

        # 4. 评分
        rating_elem = soup.find('strong', class_='ll rating_num')
        if rating_elem:
            try:
                detail['rating'] = float(rating_elem.text.strip())
            except:
                detail['rating'] = 4.0

        # 5. 简介
        intro_elem = soup.find('div', class_='intro')
        if intro_elem:
            # 获取所有段落
            paragraphs = intro_elem.find_all('p')
            brief = ' '.join([p.text.strip() for p in paragraphs if p.text.strip()])
            if brief:
                detail['brief'] = brief[:300] + '...' if len(brief) > 300 else brief

        # 6. 标签
        tags_elem = soup.find('div', id='db-tags-section')
        if tags_elem:
            tags = tags_elem.find_all('a', class_='tag')
            tag_list = [tag.text.strip() for tag in tags[:5]]
            detail['tags'] = tag_list

        return detail

    def crawl_and_save(self, keywords, books_per_keyword=5, use_details=True):
        """爬取并保存书籍信息 - 不改动BookDB的去重版本"""
        all_books = []

        for keyword in keywords:
            print(f"\n{'=' * 60}")
            print(f"开始爬取: {keyword}")
            print(f"{'=' * 60}")

            # 搜索书籍，多取一点备用（防止重复导致抓取数量不足）
            books = self.search_books(keyword, count=books_per_keyword * 3)

            if not books:
                print(f"❌ 关键词 '{keyword}' 未找到任何书籍")
                continue

            # 使用计数器确保每个关键词抓取到足够量的新书
            processed_count = 0

            for book in books:
                if processed_count >= books_per_keyword:
                    break

                # --- 核心修改：在处理逻辑最开始提取 title ---
                title = book.get('title', '未知')

                # --- 关键：直接调用 db_helper 的底层 query 方法进行去重检查 ---
                # 这种方法不需要在 BookDB 里写新函数，直接在爬虫里写 SQL
                if self.db and DB_AVAILABLE:
                    try:
                        # 这里的 self.db 指向的是你的 DBHelper 实例
                        check_sql = "SELECT id FROM books WHERE title = %s LIMIT 1"
                        # 执行查询，注意 params 必须是元组形式 (%s, )
                        exists = self.db.query(check_sql, (title,))

                        if exists:
                            print(f"  >> [数据库已存在] 跳过: 《{title}》")
                            continue
                    except Exception as e:
                        print(f"  ⚠️ 查重失败 (跳过检查): {e}")

                print(f"\n[{processed_count + 1}/{books_per_keyword}] 处理: {title}")

                # 获取详情（可选）
                detail = None
                if use_details and book.get('detail_url'):
                    detail = self.get_book_detail(book['detail_url'])

                if detail:
                    # 合并信息，详情页信息优先
                    book_info = {**book, **detail}
                else:
                    book_info = book

                # 补充缺失字段 - 添加后端需要的字段
                if 'brief' not in book_info or not book_info['brief']:
                    book_info['brief'] = f'{keyword}相关书籍，内容精彩...'

                book_info.setdefault('category', self.map_category(keyword))
                book_info.setdefault('pages', random.randint(200, 400))
                book_info.setdefault('rating', 4.0 + random.random() * 2)

                # 处理标签
                if 'tags' in book_info and isinstance(book_info['tags'], list):
                    tags_str = ','.join(book_info['tags'][:3])
                else:
                    tags_str = keyword

                book_info['tags'] = tags_str

                # 添加后端需要的额外字段
                book_info.setdefault('content', '')
                book_info.setdefault('chapters', [])
                book_info.setdefault('publisher', book_info.get('publisher', ''))
                book_info.setdefault('publish_date', book_info.get('publish_date', ''))
                book_info.setdefault('isbn', book_info.get('isbn', ''))
                book_info.setdefault('source', 'douban_edge')

                # 保存到数据库
                if self.db and DB_AVAILABLE:
                    try:
                        book_id = self.save_to_database(book_info)
                        if book_id:
                            all_books.append(book_info)
                            processed_count += 1
                            print(f"  ✅ 保存成功 (ID: {book_id})")
                        else:
                            print(f"  ⚠️ 数据库保存失败或书籍已重复")
                    except Exception as e:
                        print(f"  ❌ 数据库保存失败: {e}")
                else:
                    processed_count += 1
                    print(f"  ⚠️ 数据库不可用，跳过保存")

                # 随机延迟
                delay = random.uniform(2, 5)
                print(f"  ⏳ 等待 {delay:.1f} 秒...")
                time.sleep(delay)

        print(f"\n{'=' * 60}")
        print(f"✅ 任务完成！本次共入库 {len(all_books)} 本新书")
        print(f"{'=' * 60}")

        return all_books

    def map_category(self, keyword):
        """映射关键词到分类"""
        category_map = {
            '心理学': '心理入门',
            '心理': '心理入门',
            '情绪': '心理入门',
            '正念': '正念冥想',
            '冥想': '正念冥想',
            '压力': '压力管理',
            '焦虑': '压力管理',
            '自我成长': '自我成长',
            '个人成长': '自我成长',
            '成功学': '自我成长',
            '情商': '心理入门',
            '心理治疗': '心理入门',
            '心理咨询': '心理入门'
        }

        for k, v in category_map.items():
            if k in keyword:
                return v

        return '心理入门'  # 默认分类

    def save_to_database(self, book_info):
        """保存书籍信息到数据库 - 修改版，使用db_helper的方法"""
        try:
            # 检查是否已存在（通过标题和作者）
            check_sql = """
                SELECT id FROM books 
                WHERE title = %s AND author LIKE %s 
                LIMIT 1
            """

            # 使用db_helper的query方法
            result = self.db.query(
                check_sql,
                (book_info['title'], f"%{book_info.get('author', '')}%")
            )

            if result:
                print(f"  ⚠️ 书籍已存在: {book_info['title']}")
                return result[0]['id']

            # 插入新书籍 - 与你的表结构对齐
            insert_sql = """
                INSERT INTO books 
                (title, author, cover, brief, category, tags, content, chapters,
                 rating, pages, publisher, publish_date, isbn, source, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
            """

            # 处理content和chapters字段（如果没有，使用空值）
            content = book_info.get('content', '')
            chapters = book_info.get('chapters', [])

            # 如果chapters是列表，转换为JSON字符串
            if isinstance(chapters, list):
                chapters = json.dumps(chapters, ensure_ascii=False)

            params = (
                book_info.get('title', ''),
                book_info.get('author', '未知作者'),
                book_info.get('cover', ''),
                book_info.get('brief', ''),
                book_info.get('category', '心理入门'),
                book_info.get('tags', ''),
                content,  # content字段
                chapters,  # chapters字段（JSON格式）
                float(book_info.get('rating', 4.5)),
                int(book_info.get('pages', 0)),
                book_info.get('publisher', ''),
                book_info.get('publish_date', None),
                book_info.get('isbn', ''),
                book_info.get('source', 'douban_edge')
            )

            # 执行插入，使用insert方法（返回影响行数）
            result = self.db.insert(insert_sql, params)

            # 如果插入成功，获取最后插入的ID
            if result > 0:
                # 查询最后插入的ID
                last_id_sql = "SELECT LAST_INSERT_ID() as id"
                id_result = self.db.query(last_id_sql)
                if id_result:
                    book_id = id_result[0]['id']
                    return book_id

            print(f"  插入失败，影响行数: {result}")
            return None

        except Exception as e:
            print(f"  数据库保存错误: {e}")
            import traceback
            traceback.print_exc()
            return None

    def close(self):
        """关闭浏览器"""
        if hasattr(self, 'driver') and self.driver:
            print("👋 正在关闭Edge浏览器...")
            self.driver.quit()
            print("✅ Edge浏览器已关闭")


def quick_test():
    """快速测试函数"""
    print("🧪 Edge豆瓣爬虫快速测试")

    crawler = EdgeDoubanCrawler(headless=False)  # 显示浏览器窗口以便观察

    try:
        # 测试搜索
        books = crawler.search_books('心理学', count=3)

        if books:
            print(f"\n✅ 成功找到 {len(books)} 本书:")
            for i, book in enumerate(books):
                print(f"\n{i + 1}. 《{book.get('title')}》")
                print(f"   作者: {book.get('author')}")
                print(f"   评分: {book.get('rating')}")
                print(f"   封面: {book.get('cover', '无')[:50]}...")
                if book.get('detail_url'):
                    print(f"   链接: {book.get('detail_url')[:80]}...")
        else:
            print("❌ 未找到任何书籍")

            # 显示当前页面
            input("\n按回车键查看浏览器页面...")
            print("浏览器窗口应显示豆瓣搜索页面")

    finally:
        crawler.close()


def main():
    """主函数 - 修改版"""
    print("=" * 60)
    print("📚 Edge浏览器豆瓣书籍爬虫")
    print("=" * 60)

    print("\n请选择运行模式:")
    print("1. 快速测试（不保存数据）")
    print("2. 完整爬取（保存到数据库）")
    print("3. 登录豆瓣并保存cookies")
    print("4. 仅搜索并保存为JSON文件")

    mode = input("请输入选择 (1/2/3/4): ").strip()

    if mode == '1':
        # 快速测试
        quick_test()

    elif mode == '2':
        # 完整爬取模式
        if not DB_AVAILABLE:
            print("❌ 数据库模块不可用，请检查db_helper.py")
            return

        try:
            # 创建爬虫实例，传入数据库连接
            crawler = EdgeDoubanCrawler(headless=True)

            try:
                # 获取爬取关键词
                keywords_input = input("请输入搜索关键词（多个用逗号分隔）: ").strip()
                if keywords_input:
                    keywords = [k.strip() for k in keywords_input.split(',') if k.strip()]
                else:
                    keywords = ['心理学', '正念冥想', '压力管理']
                    print(f"使用默认关键词: {keywords}")

                # 获取爬取数量
                try:
                    count = int(input("每个关键词爬取几本书? (默认3): ") or "3")
                except:
                    count = 3

                # 是否获取详情
                use_details_input = input("是否获取每本书的详情页信息? (y/n, 默认y): ").strip().lower()
                use_details = use_details_input != 'n'

                # 开始爬取
                books = crawler.crawl_and_save(keywords, books_per_keyword=count, use_details=use_details)

                # 统计结果
                if crawler.db:
                    count_sql = "SELECT COUNT(*) as total FROM books"
                    result = crawler.db.query(count_sql)
                    print(f"\n📊 数据库现有书籍总数: {result[0]['total']} 本")

                    # 显示最近添加的书籍
                    recent_sql = "SELECT id, title, author FROM books ORDER BY id DESC LIMIT 5"
                    recent_books = crawler.db.query(recent_sql)
                    print("\n📚 最近添加的书籍:")
                    for book in recent_books:
                        print(f"  ID:{book['id']} - 《{book['title']}》 - {book['author']}")

            finally:
                crawler.close()

        except Exception as e:
            print(f"❌ 数据库连接或爬取失败: {e}")
            import traceback
            traceback.print_exc()

    elif mode == '3':
        # 登录模式
        print("\n🔐 豆瓣登录模式")

        crawler = EdgeDoubanCrawler(headless=False)  # 显示浏览器窗口

        try:
            username = input("豆瓣用户名/邮箱 (可选，直接回车跳过自动登录): ").strip()
            password = input("豆瓣密码 (可选): ").strip() if username else None

            crawler.login_douban(username if username else None, password)

            print("\n✅ 登录完成！")
            print("下次运行爬虫时会自动使用保存的cookies")

        finally:
            crawler.close()

    elif mode == '4':
        # 仅搜索并保存为JSON
        crawler = EdgeDoubanCrawler(headless=True)

        try:
            # 获取爬取关键词
            keywords_input = input("请输入搜索关键词（多个用逗号分隔）: ").strip()
            if keywords_input:
                keywords = [k.strip() for k in keywords_input.split(',') if k.strip()]
            else:
                keywords = ['心理学', '自我成长']
                print(f"使用默认关键词: {keywords}")

            # 获取爬取数量
            try:
                count = int(input("每个关键词爬取几本书? (默认5): ") or "5")
            except:
                count = 5

            # 开始爬取
            books = crawler.crawl_and_save(keywords, books_per_keyword=count, use_details=False)

            if books:
                # 保存为JSON文件
                filename = f'douban_books_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
                with open(filename, 'w', encoding='utf-8') as f:
                    json.dump(books, f, ensure_ascii=False, indent=2)
                print(f"✅ 成功收集 {len(books)} 本书籍数据")
                print(f"📁 数据已保存到: {filename}")

        finally:
            crawler.close()

    else:
        print("❌ 无效选择，退出程序")


if __name__ == '__main__':
    main()