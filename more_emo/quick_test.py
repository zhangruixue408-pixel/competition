# quick_test.py
"""最简测试脚本"""

import requests


def test():
    """测试接口"""
    print("测试情绪对话接口...")

    try:
        # 发送测试请求
        resp = requests.post(
            "http://localhost:5000/chat/reply",
            json={"message": "我不想上班，好痛苦，好累啊"},
            timeout=5
        )

        # 解析响应
        data = resp.json()

        if data.get("success"):
            print("✅ 接口正常")
            print(f"情绪: {data['emotion']}")
            print(f"回复: {data['reply'][:80]}...")
            return True
        else:
            print(f"❌ 失败: {data.get('error', '未知错误')}")
            return False

    except requests.exceptions.ConnectionError:
        print("❌ 连接失败 - 请启动服务")
        return False
    except Exception as e:
        print(f"❌ 错误: {e}")
        return False


if __name__ == "__main__":
    test()

