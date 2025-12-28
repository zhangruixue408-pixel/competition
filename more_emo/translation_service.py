# translation_service.py
import hashlib
import random
import requests
from typing import Optional


class TranslationService:
    """翻译服务，目前支持百度API"""

    def __init__(self, app_id: str, api_key: str, secret_key: str):
        self.app_id = app_id
        self.api_key = api_key
        self.secret_key = secret_key
        self.endpoint = "https://api.fanyi.baidu.com/api/trans/vip/translate"

    def translate(self, text: str, from_lang: str = 'zh', to_lang: str = 'en') -> Optional[str]:
        """执行翻译，返回翻译后的文本或None"""
        if not text.strip():
            return None

        try:
            # 生成签名
            salt = str(random.randint(32768, 65536))
            sign_str = self.app_id + text + salt + self.secret_key
            sign = hashlib.md5(sign_str.encode()).hexdigest()

            # 构建请求
            params = {
                'q': text,
                'from': from_lang,
                'to': to_lang,
                'appid': self.app_id,
                'salt': salt,
                'sign': sign
            }

            # 发送请求
            response = requests.get(self.endpoint, params=params, timeout=10)
            result = response.json()

            # 解析结果
            if 'trans_result' in result:
                return result['trans_result'][0]['dst']
            else:
                error_msg = result.get('error_msg', '未知错误')
                print(f"翻译API错误: {error_msg}")
                return None

        except requests.exceptions.Timeout:
            print("翻译请求超时")
            return None
        except Exception as e:
            print(f"翻译请求异常: {e}")
            return None

    def batch_translate(self, texts: list, **kwargs) -> list:
        """批量翻译（简单实现，可优化）"""
        return [self.translate(text, **kwargs) for text in texts]