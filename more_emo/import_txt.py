# import_txt.py 修改后的开头部分
import re
import json
import os
# 导入你的配置和类
from db_helper import DBHelper, BookDB

# 1. 模拟 app.py 的配置加载方式
db_config = {
    "host": "localhost",
    "user": "root",       # 确认你的数据库用户名
    "password": "123456", # 确认你的数据库密码
    "database": "book_db", # 你的数据库名
    "port": 3306,
    "charset": "utf8mb4"
}

# 2. 正确初始化 (传入 config 参数)
db_helper = DBHelper(config=db_config)
# 如果你需要使用 BookDB 的方法，也可以初始化它
book_db = BookDB(db_helper)



def parse_txt_to_chapters(file_path):
    """
    将 TXT 小说按章节切割
    """
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # 正则匹配章节标题 (例如: "第1章", "第一章", "Chapter 1")
    # 这是一个通用的正则，能匹配大部分小说格式
    pattern = r'(第[0-9一二三四五六七八九十百]+[章回节].*)'

    # 切割
    parts = re.split(pattern, content)

    chapters = []
    # parts[0] 通常是前言或空字符串
    if parts[0].strip():
        chapters.append({"title": "前言/序", "content": parts[0].strip()})

    # 循环处理 (标题, 内容) 对
    for i in range(1, len(parts), 2):
        title = parts[i].strip()
        text = parts[i + 1].strip() if i + 1 < len(parts) else ""
        if text:
            chapters.append({
                "title": title,
                "content": text
            })

    return chapters


def import_book(txt_path, book_id):
    print(f"正在读取文件: {txt_path} ...")
    if not os.path.exists(txt_path):
        print("错误：文件不存在")
        return

    try:
        chapters = parse_txt_to_chapters(txt_path)
        print(f"解析成功，共发现 {len(chapters)} 个章节")

        # 将章节列表转换为 JSON 字符串
        chapters_json = json.dumps(chapters, ensure_ascii=False)

        # 更新数据库
        sql = "UPDATE books SET content = %s WHERE id = %s"
        # 注意：这里我们把 JSON 存入 content 字段（或者你可以专门建一个 chapters 字段）
        # 如果你的 SQL 表里 content 足够大 (LONGTEXT)，可以直接存

        db_helper.execute_update(sql, (chapters_json, book_id))
        print(f"✅ 书籍 (ID: {book_id}) 内容导入成功！")

    except Exception as e:
        print(f"❌ 导入失败: {e}")


if __name__ == "__main__":
    # 使用指南
    print("=== 书籍内容导入工具 ===")
    print("1. 请确保数据库中已经有这本书的记录（通过爬虫爬取了标题）")
    print("2. 请下载该书的 .txt 文件")

    bid = input("请输入要导入内容的数据库 Book ID (数字): ")
    path = input("请输入 .txt 文件的完整路径: ").strip('"')  # 去除可能存在的引号

    import_book(path, bid)