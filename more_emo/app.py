import os
import sys
import time
import json
from flask import Flask, request, jsonify
from flask_cors import CORS
import tempfile
import subprocess
import wave
# =========================================================
# 路径配置和初始化
# =========================================================

# 设置项目路径
current_dir = os.path.dirname(os.path.abspath(__file__)) # D:\competent\more_emo
parent_dir = os.path.dirname(current_dir)                # D:\competent
cv_project_path = os.path.join(parent_dir, 'DeepFER')

# 定义语音服务所在的文件夹路径
# speech_project_path = os.path.join(parent_dir, 'websdk-python-demo-main')

# 添加路径到系统
paths_to_add = [
    cv_project_path,
    os.path.join(cv_project_path, 'src'),
    current_dir,
    # speech_project_path  # 将语音项目路径加入搜索列表
]

for path in paths_to_add:
    if path not in sys.path:
        sys.path.insert(0, path)

# 导入自定义模块
from src.inference_engine import CVFEREngine
from db_helper import multi_db_helper, book_db, TEST_DB, TREEHOLE_DB, MOOD_DB
from dotenv import load_dotenv


from speech_service import SpeechService


# =========================================================
# 应用初始化
# =========================================================

app = Flask(__name__)
CORS(app)

# 全局服务实例
cv_engine = None
emotion_engine = None
blenderbot_tokenizer = None
blenderbot_model = None
chat_engine = None
speech_service = SpeechService()
# 模型路径配置
EMOTION_MODEL_PATH = "D:/competent/more_emo/local_models/emotion_model"
BLENDERBOT_MODEL_PATH = "D:/competent/more_emo/local_models/blenderbot"

# 情绪映射
EMOTION_MAP_CN = {
    'joy': '开心', 'anger': '愤怒', 'sadness': '悲伤',
    'fear': '恐惧', 'surprise': '惊讶', 'disgust': '厌恶',
    'neutral': '平静'
}


# =========================================================
# 辅助函数
# =========================================================
def _get_user(data_or_args):
    """获取用户信息"""
    return (data_or_args.get("user") or
            data_or_args.get("login_name") or
            data_or_args.get("username") or
            "guest")
# =========================================================
# 语音情感分析接口 (核心整合部分)
# =========================================================
# app.py 路由部分

@app.route('/api/analyze_voice', methods=['POST'])
def analyze_voice():
    if 'file' not in request.files:
        return jsonify({"code": 400, "msg": "未找到音频文件"}), 400

    audio_file = request.files['file']

    # 使用原始文件扩展名
    original_filename = audio_file.filename
    file_ext = os.path.splitext(original_filename)[1]

    if not file_ext:
        file_ext = '.wav'  # 默认使用.wav

    temp_path = os.path.join(tempfile.gettempdir(), f"speech_{int(time.time())}{file_ext}")
    audio_file.save(temp_path)

    file_size = os.path.getsize(temp_path)
    print(f"DEBUG: 收到音频，大小: {file_size} bytes")
    print(f"DEBUG: 音频文件名: {original_filename}")
    print(f"DEBUG: 保存为: {temp_path}")

    try:
        text = speech_service.recognize(temp_path)
        return jsonify({"code": 200, "text": text})

    except Exception as e:
        print(f"ERROR: {str(e)}")
        return jsonify({"code": 500, "msg": str(e)}), 500
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)
# =========================================================
# 1. 登录与注册接口
# =========================================================

# 建议加上 /api 前缀，这是标准的做法
@app.route('/api/login', methods=['POST', 'GET'])
def login():
    # 打印收到的请求，方便在控制台调试
    print(f"收到登录请求: {request.method}")

    if request.method == 'GET':
        name = request.args.get('name')
        pwd = request.args.get('pwd')
    else:
        # 兼容 uni.request 发送的多种数据格式
        data = request.get_json() or request.form or {}
        name = data.get('name')
        pwd = data.get('pwd')

    print(f"尝试登录用户: {name}")

    if not name or not pwd:
        return jsonify({"msg": "请输入用户名和密码", "code": 400}), 400

    try:
        # 注意：如果 TEST_DB 已经指定了数据库为 test，直接写 FROM login 即可
        sql = 'SELECT * FROM login WHERE login_name = %s AND pwd = %s LIMIT 1'
        result = multi_db_helper.query(sql, (name, pwd), db=TEST_DB)

        if result:
            return jsonify({"msg": "登录成功！", "code": 200, "user": {"name": name}})
        else:
            return jsonify({"msg": "用户名或密码错误!", "code": 201})

    except Exception as e:
        print(f"数据库查询出错: {e}")
        return jsonify({"msg": "服务器内部错误", "code": 500}), 500

@app.route('/api/register', methods=['POST'])
def register():
    data = request.get_json() or request.form
    acc, pwd, email, fname = data.get('account'), data.get('pwd'), data.get('email'), data.get('fullName')

    check_sql = 'SELECT 1 FROM test.login WHERE login_name = %s OR email = %s LIMIT 1'
    if multi_db_helper.query(check_sql, (acc, email), db=TEST_DB):
        return jsonify({"msg": "账号或邮箱已存在", "code": 201})

    ins_sql = 'INSERT INTO test.login (login_name, pwd, email, full_name) VALUES (%s, %s, %s, %s)'
    multi_db_helper.query(ins_sql, (acc, pwd, email, fname), db=TEST_DB)
    return jsonify({"msg": "注册成功", "code": 200})


# =========================================================
# 2. 树洞功能接口
# =========================================================

@app.route('/api/posts', methods=['GET'])
def get_posts():
    sql = "SELECT * FROM treehole_posts ORDER BY create_time DESC"
    return jsonify({"code": 200, "data": multi_db_helper.query(sql, db=TREEHOLE_DB)})


@app.route('/api/posts/list', methods=['GET'])
def get_posts_list():
    sql = "SELECT * FROM treehole_posts ORDER BY create_time DESC LIMIT 20"
    try:
        rows = multi_db_helper.query(sql, db=TREEHOLE_DB)
        for row in rows:
            if row.get('images_json'):
                try:
                    row['images'] = json.loads(row['images_json'])
                except:
                    row['images'] = []
            else:
                row['images'] = []
        return jsonify({"code": 200, "data": rows})
    except Exception as e:
        return jsonify({"code": 500, "msg": str(e)}), 500


@app.route('/api/posts/create', methods=['POST'])
def create_post():
    data = request.get_json() or request.form or {}
    content = data.get('content')

    if not content:
        return jsonify({"code": 400, "msg": "内容不能为空"}), 400

    sql = """
    INSERT INTO treehole_posts 
      (anonymous_name, anonymous_avatar, content, mood, category, tags, images, is_burn_after_read, create_time, comment_count)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW(), 0)
    """

    try:
        multi_db_helper.query(sql, (
            data.get('anonymous_name', '匿名用户'),
            data.get('anonymous_avatar', '😊'),
            content,
            data.get('mood', ''),
            data.get('category', ''),
            data.get('tags', '[]'),
            data.get('images', '[]'),
            data.get('is_burn_after_read', 0)
        ), db=TREEHOLE_DB)
        return jsonify({"code": 200, "msg": "帖子发布成功"})
    except Exception as e:
        return jsonify({"code": 500, "msg": f"服务器错误: {str(e)}"}), 500


@app.route('/api/posts/create_v2', methods=['POST'])
def create_post_v2():
    data = request.get_json() or request.form or {}
    user = data.get('user', 'guest')
    content = data.get('content')

    if not content:
        return jsonify({"code": 400, "msg": "内容不能为空"}), 400

    images_json = json.dumps(data.get('images', []))

    sql = "INSERT INTO treehole_posts (user_name, content, images_json, create_time) VALUES (%s, %s, %s, NOW())"

    try:
        multi_db_helper.query(sql, (user, content, images_json), db=TREEHOLE_DB)
        return jsonify({"code": 200, "msg": "发布成功", "data": {"user": user}})
    except Exception as e:
        return jsonify({"code": 500, "msg": "数据库写入失败"}), 500


#获取评论列表
@app.route('/api/comments', methods=['GET'])
def get_comments():
    post_id = request.args.get('post_id')
    if not post_id:
        return jsonify({"code": 400, "msg": "缺少 post_id"}), 400

    # 根据 treehole.sql 里的字段名进行查询
    sql = "SELECT * FROM treehole_comments WHERE post_id = %s ORDER BY create_time ASC"
    try:
        comments = multi_db_helper.query(sql, (post_id,), db=TREEHOLE_DB)
        return jsonify({"code": 200, "data": comments})
    except Exception as e:
        return jsonify({"code": 500, "msg": str(e)}), 500
@app.route('/api/comments/create', methods=['POST'])
def create_comment():
    data = request.get_json() or request.form or {}
    post_id, content = data.get('post_id'), data.get('content')

    if not post_id or not content:
        return jsonify({"code": 400, "msg": "post_id和内容不能为空"}), 400

    try:
        sql = """
        INSERT INTO treehole_comments 
          (post_id, anonymous_name, anonymous_avatar, content, create_time)
        VALUES (%s, %s, %s, %s, NOW())
        """
        multi_db_helper.query(sql, (
            post_id,
            data.get('anonymous_name', '匿名用户'),
            data.get('anonymous_avatar', '😊'),
            content
        ), db=TREEHOLE_DB)

        multi_db_helper.query(
            "UPDATE treehole_posts SET comment_count = comment_count + 1 WHERE id = %s",
            (post_id,), db=TREEHOLE_DB
        )

        return jsonify({"code": 200, "msg": "评论成功"})
    except Exception as e:
        return jsonify({"code": 500, "msg": f"服务器错误: {str(e)}"}), 500

# 自动回复
@app.route('/api/posts/auto_comment', methods=['POST'])
def auto_comment_post():
    data = request.get_json()
    post_id = data.get('post_id')

    if not post_id:
        return jsonify({"code": 400, "msg": "缺少 post_id"}), 400

    try:
        # 1. 先从数据库查出帖子的内容
        post_sql = "SELECT content FROM treehole_posts WHERE id = %s"
        post_data = multi_db_helper.query(post_sql, (post_id,), db=TREEHOLE_DB)

        if not post_data:
            return jsonify({"code": 404, "msg": "帖子不存在"}), 404

        post_content = post_data[0]['content']

        # 2. 调用 ChatEngine 生成 AI 回复
        # 这里的 chat_engine 是你初始化好的实例
        # 我们模拟一个 prompt 让 AI 变成温暖的树洞倾听者
        ai_prompt = f"作为一个温暖的树洞陪伴者，请回复下面这段心情：{post_content}"
        ai_response_data = chat_engine.chat(ai_prompt)  # 调用你的 chat_engine.py
        ai_reply = ai_response_data.get('response', "抱抱你，我一直都在。")

        # 3. 将 AI 回复作为评论存入 treehole_comments
        comment_sql = """
            INSERT INTO treehole_comments 
            (post_id, anonymous_name, anonymous_avatar, content, create_time)
            VALUES (%s, %s, %s, %s, NOW())
        """
        multi_db_helper.insert(comment_sql, (
            post_id,
            "AI 治愈小助手",
            "🤖",
            ai_reply
        ), db=TREEHOLE_DB)

        # 4. 更新帖子评论数
        multi_db_helper.execute(
            "UPDATE treehole_posts SET comment_count = comment_count + 1 WHERE id = %s",
            (post_id,), db=TREEHOLE_DB
        )

        return jsonify({
            "code": 200,
            "msg": "AI 评论已生成",
            "data": {"content": ai_reply}
        })

    except Exception as e:
        return jsonify({"code": 500, "msg": str(e)}), 500

@app.route('/api/posts/like', methods=['POST'])
def like_post():
    data = request.get_json()
    post_id = data.get('post_id')

    if not post_id:
        return jsonify({"code": 400, "msg": "缺少帖子ID"}), 400

    sql = "UPDATE treehole_posts SET like_count = like_count + 1 WHERE id = %s"
    try:
        multi_db_helper.query(sql, (post_id,), db=TREEHOLE_DB)
        return jsonify({"code": 200, "msg": "点赞成功"})
    except Exception as e:
        return jsonify({"code": 500, "msg": str(e)}), 500
# =========================================================
# 呼吸训练打卡
# =========================================================

@app.route('/api/breath/checkin', methods=['POST'])
def breath_checkin_create_or_update():
    """
    创建 / 更新当天的呼吸训练记录
    """
    data = request.get_json() or request.form or {}
    user = _get_user(data)

    mode_key = data.get("mode_key")
    mode_name = data.get("mode_name")
    duration_seconds = data.get("duration_seconds", 0)
    completed_cycles = data.get("completed_cycles", 0)

    if not mode_key or not mode_name:
        return jsonify({"code": 400, "msg": "mode_key 和 mode_name 不能为空"}), 400

    try:
        duration_seconds = int(duration_seconds)
        completed_cycles = int(completed_cycles)
    except Exception:
        return jsonify({"code": 400, "msg": "参数格式错误"}), 400

    if duration_seconds < 0 or completed_cycles < 0:
        return jsonify({"code": 400, "msg": "时长和循环次数不能为负数"}), 400

    sql = """
    INSERT INTO `Mood Check-In`.breath_trainings
      (user_name, training_date, mode_key, mode_name, duration_seconds, completed_cycles, create_time, update_time)
    VALUES
      (%s, CURDATE(), %s, %s, %s, %s, NOW(), NOW())
    ON DUPLICATE KEY UPDATE
      mode_key = VALUES(mode_key),
      mode_name = VALUES(mode_name),
      duration_seconds = duration_seconds + VALUES(duration_seconds),
      completed_cycles = completed_cycles + VALUES(completed_cycles),
      update_time = NOW();
    """

    multi_db_helper.query(
        sql,
        (user, mode_key, mode_name, duration_seconds, completed_cycles),
        db=MOOD_DB
    )

    return jsonify({
        "code": 200,
        "msg": "训练记录保存成功",
        "data": {
            "user": user,
            "training_date": str(multi_db_helper.today_date())
        }
    })


@app.route('/api/breath/today', methods=['GET'])
def breath_today():
    args = request.args or {}
    user = _get_user(args)

    sql = """
    SELECT *
    FROM `Mood Check-In`.breath_trainings
    WHERE user_name = %s AND training_date = CURDATE()
    LIMIT 1
    """
    rows = multi_db_helper.query(sql, (user,), db=MOOD_DB)
    return jsonify({"code": 200, "data": rows[0] if rows else None})


@app.route('/api/breath/recent', methods=['GET'])
def breath_recent():
    args = request.args or {}
    user = _get_user(args)

    limit = args.get("limit", 10)
    try:
        limit = max(1, min(int(limit), 60))
    except Exception:
        limit = 10

    sql = """
    SELECT *
    FROM `Mood Check-In`.breath_trainings
    WHERE user_name = %s
    ORDER BY training_date DESC, update_time DESC
    LIMIT %s
    """
    rows = multi_db_helper.query(sql, (user, limit), db=MOOD_DB)
    return jsonify({"code": 200, "data": rows})


@app.route('/api/breath/stats', methods=['GET'])
def breath_stats():
    args = request.args or {}
    user = _get_user(args)

    # 总训练时长（秒）和总完成次数
    sql_total = """
    SELECT 
        IFNULL(SUM(duration_seconds), 0) AS totalSeconds,
        IFNULL(SUM(completed_cycles), 0) AS totalCycles,
        COUNT(DISTINCT training_date) AS totalDays
    FROM `Mood Check-In`.breath_trainings
    WHERE user_name = %s
    """
    total_row = multi_db_helper.query(sql_total, (user,), db=MOOD_DB)[0]

    # 计算连续天数
    sql_dates = """
    SELECT training_date
    FROM `Mood Check-In`.breath_trainings
    WHERE user_name = %s
    ORDER BY training_date DESC
    LIMIT 366
    """
    date_rows = multi_db_helper.query(sql_dates, (user,), db=MOOD_DB)
    continuous = multi_db_helper.calc_continuous_days([r["training_date"] for r in date_rows])

    # 格式化总时长
    total_seconds = int(total_row.get("totalSeconds", 0))
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    total_time_str = f"{hours}小时{minutes}分" if hours > 0 else f"{minutes}分钟"

    return jsonify({
        "code": 200,
        "data": {
            "totalTime": total_time_str,
            "totalSeconds": total_seconds,
            "totalCycles": int(total_row.get("totalCycles", 0)),
            "continuousDays": continuous,
            "totalDays": int(total_row.get("totalDays", 0))
        }
    })

# =========================================================
# 3. 情绪打卡接口
# =========================================================

@app.route('/api/mood/checkin', methods=['POST'])
def mood_checkin():
    """创建/更新当天的情绪打卡"""
    data = request.get_json() or request.form or {}
    user = _get_user(data)

    mood_key = data.get("mood_key")
    intensity = data.get("intensity", 5)

    if not mood_key:
        return jsonify({"code": 400, "msg": "mood_key 不能为空"}), 400

    try:
        intensity = max(1, min(int(intensity), 10))
    except:
        return jsonify({"code": 400, "msg": "intensity 必须是1~10的整数"}), 400

    sql = """
    INSERT INTO `Mood Check-In`.mood_checkins
      (user_name, mood_key, mood_name, intensity, score, tags_json, diary_text, checkin_date, create_time, update_time)
    VALUES (%s, %s, %s, %s, %s, %s, %s, CURDATE(), NOW(), NOW())
    ON DUPLICATE KEY UPDATE
      mood_key = VALUES(mood_key), mood_name = VALUES(mood_name), intensity = VALUES(intensity),
      score = VALUES(score), tags_json = VALUES(tags_json), diary_text = VALUES(diary_text), update_time = NOW()
    """

    multi_db_helper.query(sql, (
        user, mood_key, data.get("mood_name"), intensity, intensity,
        multi_db_helper.to_json(data.get("tags", [])), data.get("diary_text", "")
    ), db=MOOD_DB)

    return jsonify(
        {"code": 200, "msg": "打卡成功", "data": {"user": user, "checkin_date": str(multi_db_helper.today_date())}})


@app.route('/api/mood/today', methods=['GET'])
def mood_checkin_today():
    user = _get_user(request.args or {})
    sql = "SELECT * FROM `Mood Check-In`.mood_checkins WHERE user_name = %s AND checkin_date = CURDATE() LIMIT 1"
    rows = multi_db_helper.query(sql, (user,), db=MOOD_DB)
    return jsonify({"code": 200, "data": rows[0] if rows else None})


@app.route('/api/mood/recent', methods=['GET'])
def mood_checkin_recent():
    args = request.args or {}
    user = _get_user(args)
    try:
        limit = max(1, min(int(args.get("limit", 7)), 60))
    except:
        limit = 7

    sql = """
    SELECT * FROM `Mood Check-In`.mood_checkins 
    WHERE user_name = %s 
    ORDER BY checkin_date DESC, update_time DESC 
    LIMIT %s
    """
    rows = multi_db_helper.query(sql, (user, limit), db=MOOD_DB)
    return jsonify({"code": 200, "data": rows})


@app.route('/api/mood/week', methods=['GET'])
def mood_week_overview():
    user = _get_user(request.args or {})
    sql = """
    SELECT checkin_date, mood_key, mood_name, score
    FROM `Mood Check-In`.mood_checkins
    WHERE user_name = %s AND checkin_date >= DATE_SUB(CURDATE(), INTERVAL 6 DAY)
    ORDER BY checkin_date ASC
    """
    rows = multi_db_helper.query(sql, (user,), db=MOOD_DB)
    return jsonify({"code": 200, "data": rows})


@app.route('/api/mood/stats', methods=['GET'])
def mood_stats():
    user = _get_user(request.args or {})

    sql_total = "SELECT COUNT(*) AS totalDays, IFNULL(ROUND(AVG(score), 2), 0) AS avgScore FROM `Mood Check-In`.mood_checkins WHERE user_name = %s"
    total_row = multi_db_helper.query(sql_total, (user,), db=MOOD_DB)[0]

    sql_dates = "SELECT checkin_date FROM `Mood Check-In`.mood_checkins WHERE user_name = %s ORDER BY checkin_date DESC LIMIT 366"
    date_rows = multi_db_helper.query(sql_dates, (user,), db=MOOD_DB)
    continuous = multi_db_helper.calc_continuous_days([r["checkin_date"] for r in date_rows])

    return jsonify({
        "code": 200,
        "data": {
            "continuousDays": continuous,
            "totalDays": int(total_row.get("totalDays", 0)),
            "avgScore": float(total_row.get("avgScore", 0))
        }
    })


@app.route('/api/mood/history', methods=['GET'])
def mood_history():
    user = request.args.get("user", "guest")
    sql = """
    SELECT checkin_date, score, mood_name 
    FROM mood_checkins 
    WHERE user_name = %s 
    ORDER BY checkin_date DESC LIMIT 7
    """
    rows = multi_db_helper.query(sql, (user,), db=MOOD_DB)
    return jsonify({"code": 200, "data": rows})


# =========================================================
# 4. 睡眠监测接口
# =========================================================

@app.route('/api/sleep/checkin', methods=['POST'])
def sleep_checkin():
    """创建 / 更新当天睡眠打卡"""
    data = request.get_json() or request.form or {}
    user = _get_user(data)

    sleep_hours, sleep_quality = data.get("sleep_hours"), data.get("sleep_quality")
    if sleep_hours is None or sleep_quality is None:
        return jsonify({"code": 400, "msg": "sleep_hours 和 sleep_quality 不能为空"}), 400

    try:
        sleep_hours, sleep_quality = float(sleep_hours), int(sleep_quality)
        if sleep_quality < 1 or sleep_quality > 5:
            return jsonify({"code": 400, "msg": "sleep_quality 取值 1~5"}), 400
    except:
        return jsonify({"code": 400, "msg": "参数格式错误"}), 400

    sql = """
    INSERT INTO `Mood Check-In`.sleep
      (user_name, sleep_date, sleep_hours, sleep_quality, bedtime, wake_time, dream, note, create_time, update_time)
    VALUES (%s, CURDATE(), %s, %s, %s, %s, %s, %s, NOW(), NOW())
    ON DUPLICATE KEY UPDATE
      sleep_hours = VALUES(sleep_hours), sleep_quality = VALUES(sleep_quality),
      bedtime = VALUES(bedtime), wake_time = VALUES(wake_time),
      dream = VALUES(dream), note = VALUES(note), update_time = NOW()
    """

    multi_db_helper.query(sql, (
        user, sleep_hours, sleep_quality,
        data.get("bedtime"), data.get("wake_time"),
        int(data.get("dream") or 0), data.get("note", "")
    ), db=MOOD_DB)

    return jsonify(
        {"code": 200, "msg": "睡眠打卡成功", "data": {"user": user, "sleep_date": str(multi_db_helper.today_date())}})


@app.route('/api/sleep/today', methods=['GET'])
def sleep_today():
    user = _get_user(request.args or {})
    sql = "SELECT * FROM `Mood Check-In`.sleep WHERE user_name = %s AND sleep_date = CURDATE() LIMIT 1"
    rows = multi_db_helper.query(sql, (user,), db=MOOD_DB)
    record = multi_db_helper.format_sleep_record(rows[0]) if rows else None
    return jsonify({"code": 200, "data": record})


@app.route('/api/sleep/recent', methods=['GET'])
def sleep_recent():
    args = request.args or {}
    user = _get_user(args)

    try:
        limit = max(1, min(int(args.get("limit", 7)), 60))
    except:
        limit = 7

    sql = "SELECT * FROM `Mood Check-In`.sleep WHERE user_name = %s ORDER BY sleep_date DESC LIMIT %s"
    rows = multi_db_helper.query(sql, (user, limit), db=MOOD_DB)
    formatted_rows = [multi_db_helper.format_sleep_record(record) for record in rows]
    return jsonify({"code": 200, "data": formatted_rows})


# =========================================================
# 5. 书籍相关接口
# =========================================================

@app.route('/api/books/list', methods=['POST'])
def get_books_list():
    try:
        data = request.get_json() or {}
        result = book_db.get_books(
            page=int(data.get('page', 1)),
            page_size=int(data.get('pageSize', 10)),
            category=data.get('category', ''),
            keyword=data.get('keyword', '')
        )
        return jsonify({"success": True, "code": 200, "message": "获取成功", "data": result})
    except Exception as e:
        return jsonify({"success": False, "code": 500, "message": f"获取书籍列表失败: {str(e)}", "data": None}), 500


@app.route('/api/books/detail', methods=['POST'])
def get_book_detail():
    try:
        data = request.get_json() or {}
        book_id = data.get('book_id')

        if not book_id:
            return jsonify({"success": False, "code": 400, "message": "缺少book_id参数", "data": None}), 400

        book = book_db.get_book_by_id(book_id)
        return jsonify({"success": True, "code": 200, "message": "获取成功", "data": book}) if book else \
            jsonify({"success": False, "code": 404, "message": "书籍不存在", "data": None}), 404
    except Exception as e:
        return jsonify({"success": False, "code": 500, "message": f"获取书籍详情失败: {str(e)}", "data": None}), 500


@app.route('/api/books/search', methods=['POST'])
def search_books():
    try:
        data = request.get_json() or {}
        keyword = data.get('keyword', '').strip()
        limit = int(data.get('limit', 20))

        if not keyword:
            return jsonify({"success": False, "code": 400, "message": "请输入搜索关键词", "data": None}), 400

        books = book_db.search_books(keyword, limit)
        return jsonify({"success": True, "code": 200, "message": "搜索成功", "data": books})
    except Exception as e:
        return jsonify({"success": False, "code": 500, "message": f"搜索失败: {str(e)}", "data": None}), 500


@app.route('/api/books/favorite', methods=['POST'])
def toggle_favorite():
    try:
        data = request.get_json() or {}
        user_id, book_id = data.get('user_id', 'anonymous'), data.get('book_id')

        if not book_id:
            return jsonify({"success": False, "code": 400, "message": "缺少book_id参数", "data": None}), 400

        is_favorited = book_db.is_favorited(user_id, book_id)

        if is_favorited:
            book_db.remove_favorite(user_id, book_id)
            action, favorited = 'removed', False
        else:
            book_db.add_favorite(user_id, book_id)
            action, favorited = 'added', True

        return jsonify({"success": True, "code": 200, "message": f"收藏{action}成功",
                        "data": {"favorited": favorited, "action": action}})
    except Exception as e:
        return jsonify({"success": False, "code": 500, "message": f"操作失败: {str(e)}", "data": None}), 500


@app.route('/api/books/favorites', methods=['POST'])
def get_favorites():
    try:
        data = request.get_json() or {}
        result = book_db.get_user_favorites(
            user_id=data.get('user_id', 'anonymous'),
            page=int(data.get('page', 1)),
            page_size=int(data.get('pageSize', 10))
        )
        return jsonify({"success": True, "code": 200, "message": "获取成功", "data": result})
    except Exception as e:
        return jsonify({"success": False, "code": 500, "message": f"获取收藏列表失败: {str(e)}", "data": None}), 500


@app.route('/api/books/<int:book_id>/content', methods=['GET'])
def get_book_content(book_id):
    try:
        sql = "SELECT title, author, content, chapters FROM books WHERE id = %s"
        result = multi_db_helper.query(sql, (book_id,), db="book_db")

        if not result:
            return jsonify({"code": 404, "message": "书籍不存在"}), 404

        book = result[0]
        content = book.get('content')

        if not content:
            return jsonify({
                "code": 200,
                "data": {
                    "title": book['title'],
                    "chapters": [{"title": "第一章：演示章节", "content": "这是自动生成的演示内容。"}]
                }
            })

        try:
            chapter_list = json.loads(content) if isinstance(content, str) else content
        except:
            chapter_list = [{"title": "全文", "content": content}]

        return jsonify({"code": 200, "data": {"title": book['title'], "chapters": chapter_list}})
    except Exception as e:
        return jsonify({"code": 500, "message": f"服务器错误: {str(e)}"}), 500


# =========================================================
# 6. 情绪分析与聊天接口
# =========================================================

@app.route('/api/analyze_emotion', methods=['POST'])
def analyze_emotion_only():
    """纯文本情绪分析接口"""
    if emotion_engine is None:
        return jsonify({"code": 503, "message": "情绪分析引擎未就绪"}), 503

    try:
        data = request.get_json()
        text = data.get('text', '').strip()

        if not text:
            return jsonify({"code": 400, "message": "文本不能为空"}), 400

        start_time = time.time()
        result = emotion_engine.analyze(text)
        emotion = result.get('emotion', 'neutral')

        positive_emotions = ['joy', 'love', 'surprise']
        negative_emotions = ['anger', 'sadness', 'fear', 'disgust']
        sentiment = 'neutral'
        if emotion in positive_emotions:
            sentiment = 'positive'
        elif emotion in negative_emotions:
            sentiment = 'negative'

        return jsonify({
            "code": 200, "message": "分析成功",
            "data": {
                "emotion": emotion, "sentiment": sentiment,
                "confidence": result.get('confidence', 0.5),
                "source": result.get('source', 'model'),
                "translated": result.get('translated', ''),
                "processing_time": time.time() - start_time
            }
        })
    except Exception as e:
        return jsonify({"code": 500, "message": f"分析失败: {str(e)}"}), 500


@app.route('/api/predict_face', methods=['POST'])
def predict_face():
    """面部情绪识别"""
    try:
        data = request.json
        if not data or 'image' not in data:
            return jsonify({"success": False, "error": "数据包为空"}), 400

        result = cv_engine.predict_from_base64(data['image'])

        if result is None:
            return jsonify({"success": False, "error": "未能识别到面部"}), 200

        return jsonify({
            "success": True,
            "emotion": result['emotion'],
            "confidence": result['confidence']
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/chat/reply', methods=['POST'])
def chat():
    """聊天接口"""
    if emotion_engine is None or blenderbot_model is None:
        return jsonify({"success": False, "error": "服务未初始化"}), 503

    try:
        data = request.get_json()
        if not data or 'msg' not in data:
            return jsonify({"success": False, "error": "缺少 'msg' 字段"}), 400

        user_input = data['msg'].strip()
        if not user_input:
            return jsonify({"success": False, "error": "消息不能为空"}), 400

        start_time = time.time()

        # 情绪分析
        emotion_result = emotion_engine.analyze(user_input)
        emotion = emotion_result.get("emotion", "neutral")

        # 生成回复
        text_for_bot = emotion_result.get("translated", "") or user_input
        bot_response = generate_response_with_emotion(text_for_bot, emotion)

        # 汉化回复
        final_reply_cn = bot_response
        if emotion_engine.translation_service:
            res = emotion_engine.translation_service.translate(bot_response, from_lang='en', to_lang='zh')
            if res: final_reply_cn = res

        return jsonify({
            "success": True,
            "reply": final_reply_cn,
            "emotion": EMOTION_MAP_CN.get(emotion, emotion),
            "emotion_en": emotion,
            "emotion_confidence": emotion_result.get("confidence", 0.5),
            "processing_time": round(time.time() - start_time, 3),
            "timestamp": time.time()
        })
    except Exception as e:
        return jsonify({"success": False, "error": f"处理请求时出错: {str(e)}"}), 500


def generate_response_with_emotion(user_input, emotion):
    """根据用户输入和情绪生成回复"""
    import torch

    emotion_prefixes = {
        'joy': '[User is happy] ', 'anger': '[User is angry] ',
        'sadness': '[User is sad] ', 'fear': '[User is scared] ',
        'surprise': '[User is surprised] ', 'disgust': '[User is disgusted] ',
        'neutral': ''
    }

    input_text = f"{emotion_prefixes.get(emotion, '')}{user_input}"
    device = next(blenderbot_model.parameters()).device

    inputs = blenderbot_tokenizer(
        input_text, return_tensors="pt",
        truncation=True, max_length=256
    ).to(device)

    with torch.no_grad():
        outputs = blenderbot_model.generate(
            **inputs, max_length=200, temperature=0.9,
            top_p=0.95, repetition_penalty=1.2, num_beams=3
        )

    response = blenderbot_tokenizer.decode(outputs[0], skip_special_tokens=True)
    return response[4:].strip() if response.startswith("Bot:") else response


# =========================================================
# 7. 管理接口
# =========================================================

@app.route('/api/admin/books/add', methods=['POST'])
def add_book():
    """添加书籍（管理接口）"""
    try:
        data = request.get_json()

        for field in ['title', 'author', 'category']:
            if field not in data:
                return jsonify({"success": False, "message": f"缺少必要字段: {field}"}), 400

        book_id = book_db.add_book(data)
        return jsonify({"success": True, "message": "添加成功", "data": {"id": book_id}})
    except Exception as e:
        return jsonify({"success": False, "message": f"添加书籍失败: {str(e)}"}), 500


@app.route('/api/admin/books/update', methods=['POST'])
def update_book():
    """更新书籍（管理接口）"""
    try:
        data = request.get_json()
        book_id = data.get('id')

        if not book_id:
            return jsonify({"success": False, "message": "缺少书籍ID"}), 400

        success = book_db.update_book(book_id, data)

        return jsonify({"success": True, "message": "更新成功"}) if success else \
            jsonify({"success": False, "message": "书籍不存在或更新失败"}), 404
    except Exception as e:
        return jsonify({"success": False, "message": f"更新书籍失败: {str(e)}"}), 500


# =========================================================
# 服务初始化
# =========================================================
def init_services():
    """初始化所有必要服务"""
    # 1. 必须在这里加入 speech_service 的全局声明
    global emotion_engine, blenderbot_tokenizer, blenderbot_model, cv_engine, speech_service

    # 1. 强制在初始化最开始加载 .env
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
    load_dotenv(dotenv_path=env_path)

    print("正在初始化服务...")

    try:
        # --- 1. 初始化情绪分析引擎 ---
        print("初始化情绪分析引擎...")
        from model_loader import ModelLoader
        from translation_service import TranslationService
        from emotion_engine import EmotionEngine

        emotion_model_loader = ModelLoader(EMOTION_MODEL_PATH)
        if not emotion_model_loader.load():
            print("❌ 情绪分析模型加载失败")
            return False

        translator = TranslationService(
            app_id="20251202002510818",
            api_key="FOMW_d4n9kfi2l220ai5m9s6g",
            secret_key="LILRyPvwmcc3YaryfNYi"
        )

        emotion_engine = EmotionEngine(emotion_model_loader, translator)
        print("✅ 情绪分析引擎就绪")

        # --- 2. 加载 BlenderBot 模型 ---
        print("加载 BlenderBot 模型...")
        from transformers import AutoTokenizer, AutoModelForSeq2SeqLM
        import torch

        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        print(f"使用设备: {device}")

        blenderbot_tokenizer = AutoTokenizer.from_pretrained(BLENDERBOT_MODEL_PATH)
        blenderbot_model = AutoModelForSeq2SeqLM.from_pretrained(BLENDERBOT_MODEL_PATH)
        blenderbot_model = blenderbot_model.to(device)
        blenderbot_model.eval()
        print("✅ BlenderBot 模型就绪")

        model_path = r'D:\competent\DeepFER\checkpoints\best_rafdb.keras'
        cv_engine = CVFEREngine(model_path)
        print("✅ CV表情识别引擎就绪")

        print("正在初始化讯飞语音服务...")
        # 注意：SpeechService 内部会自动去读 .env 文件里的 APP_ID 等信息
        speech_service = SpeechService()
        if speech_service.client:
            print("✅ 讯飞语音服务就绪")
        else:
            print("⚠️ 语音服务初始化完成但 client 为空，请检查 .env 配置")

        return True

    except Exception as e:
        print(f"❌ 服务初始化失败: {e}")
        import traceback
        traceback.print_exc()
        return False


# =========================================================
# 主程序入口
# =========================================================

if __name__ == '__main__':
    if init_services():
        print("\n" + "=" * 50)
        print("✅ 服务初始化成功")
        print("📡 服务地址: http://localhost:5000")
        print("=" * 50 + "\n")
        app.run(host='0.0.0.0', port=5000, debug=False)
    else:
        print("❌ 服务初始化失败，无法启动")
