# emotion_engine.py
import time
from typing import Dict, Any
from model_loader import ModelLoader
from translation_service import TranslationService


class EmotionEngine:
    """情绪分析引擎：集成三层优化逻辑"""

    def __init__(self, model_loader: ModelLoader, translation_service: TranslationService = None):
        self.model_loader = model_loader
        self.translation_service = translation_service

        # 初始化规则引擎
        self._init_rules()

        # 性能统计
        self.request_count = 0
        self.total_time = 0.0

    def _init_rules(self):
        """初始化规则库"""
        self.high_priority_rules = {
            "呵呵": "disgust", "呵呵哒": "disgust",
            "您可真是个大聪明": "disgust", "真是服了": "disgust",
            "气死我了": "anger", "喜极而泣": "joy", "无语": "disgust",
            "怎么这样啊":"disgust","劳累":"sad","疲惫":"sad"
        }

        self.post_process_rules = {
            "cried with joy": "joy",
            "unsettling": "sadness",
            "work overtime for free": "anger",
        }

        # 标签映射（根据你的模型实际情况调整）
        self.label_mapping = {
            'sadness': 'sadness',
            'joy': 'joy',
            'love': 'joy',  # 合并love到joy
            'anger': 'anger',
            'fear': 'fear',
            'surprise': 'surprise'
        }

    def analyze(self, chinese_text: str) -> Dict[str, Any]:
        """分析中文文本情绪"""
        start_time = time.time()
        self.request_count += 1

        # 第一层：规则匹配
        rule_emotion = self._apply_rules(chinese_text)
        if rule_emotion:
            processing_time = time.time() - start_time
            self.total_time += processing_time
            return {
                "emotion": rule_emotion,
                "confidence": 1.0,
                "source": "rule",
                "processing_time": processing_time,
                "success": True
            }

        # 第二层：翻译+模型分析
        translated_text = None
        if self.translation_service:
            translated_text = self.translation_service.translate(chinese_text)

        if translated_text:
            # 使用模型分析
            try:
                raw_label, confidence = self.model_loader.predict(translated_text)

                # 第三层：后处理
                final_emotion = self._post_process(chinese_text, translated_text, raw_label)

                # 标签映射
                final_emotion = self.label_mapping.get(final_emotion, final_emotion)

                processing_time = time.time() - start_time
                self.total_time += processing_time

                return {
                    "emotion": final_emotion,
                    "confidence": confidence,
                    "source": "model",
                    "translated": translated_text,
                    "processing_time": processing_time,
                    "success": True
                }

            except Exception as e:
                print(f"模型分析失败: {e}")
                # 降级处理

        # 降级方案：简单关键词匹配
        return self._fallback_analysis(chinese_text, start_time)

    def _apply_rules(self, text: str):
        """应用前置规则"""
        for keyword, emotion in self.high_priority_rules.items():
            if keyword in text:
                return emotion
        return None

    def _post_process(self, original: str, translated: str, predicted_label: str):
        """后处理校准"""
        # 混合情绪校准
        if predicted_label == 'joy' and any(word in translated for word in ['surprise', 'suddenly']):
            return 'surprise'

        # 关键词修正
        for keyword, emotion in self.post_process_rules.items():
            if keyword in translated:
                return emotion

        return predicted_label

    def _fallback_analysis(self, text: str, start_time: float):
        """降级分析方案"""
        # 简单的关键词匹配（可进一步完善）
        keywords_mapping = {
            '开心': 'joy', '高兴': 'joy', '快乐': 'joy',
            '生气': 'anger', '愤怒': 'anger', '恼火': 'anger',
            '伤心': 'sadness', '难过': 'sadness', '悲伤': 'sadness',
            '害怕': 'fear', '恐惧': 'fear', '吓人': 'fear',
            '恶心': 'disgust', '讨厌': 'disgust'
        }

        for keyword, emotion in keywords_mapping.items():
            if keyword in text:
                processing_time = time.time() - start_time
                self.total_time += processing_time
                return {
                    "emotion": emotion,
                    "confidence": 0.7,
                    "source": "fallback",
                    "processing_time": processing_time,
                    "success": True
                }

        # 默认返回中性
        processing_time = time.time() - start_time
        self.total_time += processing_time
        return {
            "emotion": "neutral",
            "confidence": 0.5,
            "source": "fallback",
            "processing_time": processing_time,
            "success": True
        }

    def get_stats(self):
        """获取引擎统计信息"""
        return {
            "request_count": self.request_count,
            "avg_processing_time": self.total_time / self.request_count if self.request_count > 0 else 0,
            "rules_count": len(self.high_priority_rules)
        }