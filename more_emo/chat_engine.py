# chat_engine.py
"""
聊天引擎
整合情绪分析、BlenderBot和对话管理
"""
import time
from typing import Dict, Optional, Any
import logging
from emotion_engine import EmotionEngine
from blenderbot_manager import BlenderBotManager
from conversation_manager import ConversationManager

logger = logging.getLogger(__name__)


class ChatEngine:
    """聊天引擎：整合所有模块"""

    def __init__(self,
                 emotion_engine: EmotionEngine,
                 blenderbot_manager: BlenderBotManager,
                 config: Dict = None):
        """
        初始化聊天引擎

        Args:
            emotion_engine: 情绪分析引擎
            blenderbot_manager: BlenderBot管理器
            config: 配置参数
        """
        self.emotion_engine = emotion_engine
        self.blenderbot = blenderbot_manager
        self.config = config or {}

        # 创建对话管理器
        self.conversation_manager = ConversationManager(
            max_history=self.config.get('max_history', 5)
        )

        # 后处理器
        self.post_processors = self._init_post_processors()

        # 性能统计
        self.stats = {
            'total_requests': 0,
            'total_processing_time': 0.0,
            'emotion_distribution': {},
            'error_count': 0
        }

        logger.info("聊天引擎初始化完成")

    def _init_post_processors(self) -> Dict:
        """初始化后处理器"""
        return {
            'emotion_adjustment': self.config.get('enable_emotion_adjustment', True),
            'safety_filter': self.config.get('enable_safety_filter', True),
            'length_control': self.config.get('enable_length_control', True)
        }

    def chat(self,
             user_input: str,
             session_id: str = None,
             include_translation: bool = False,
             return_raw: bool = False) -> Dict:
        """
        处理用户输入并生成回复

        Args:
            user_input: 用户输入文本
            session_id: 会话ID（可选）
            include_translation: 是否包含翻译结果
            return_raw: 是否返回原始数据

        Returns:
            包含回复和相关信息的字典
        """
        start_time = time.time()
        self.stats['total_requests'] += 1

        try:
            # 1. 情感分析
            emotion_result = self.emotion_engine.analyze(user_input)

            if not emotion_result['success']:
                logger.warning(f"情感分析失败: {emotion_result}")
                # 使用中性情感作为后备
                emotion_result = {
                    'emotion': 'neutral',
                    'confidence': 0.5,
                    'source': 'fallback'
                }

            emotion = emotion_result['emotion']
            confidence = emotion_result['confidence']
            emotion_source = emotion_result['source']

            # 2. 更新情感统计
            self._update_emotion_stats(emotion)

            # 3. 生成回复
            bot_response = self.blenderbot.generate_response(
                user_input=user_input,
                emotion=emotion,
                history=self.conversation_manager.history
            )

            # 4. 后处理
            if self.post_processors['emotion_adjustment']:
                bot_response = self._adjust_response_for_emotion(bot_response, emotion)

            if self.post_processors['safety_filter']:
                bot_response = self._apply_safety_filter(bot_response)

            if self.post_processors['length_control']:
                bot_response = self._control_response_length(bot_response)

            # 5. 更新对话历史
            self.conversation_manager.add_exchange(
                user_input=user_input,
                bot_response=bot_response,
                emotion=emotion,
                confidence=confidence
            )

            # 6. 计算处理时间
            processing_time = time.time() - start_time
            self.stats['total_processing_time'] += processing_time

            # 7. 构建响应
            response_data = {
                'success': True,
                'response': bot_response,
                'emotion': emotion,
                'emotion_confidence': confidence,
                'emotion_source': emotion_source,
                'processing_time': processing_time,
                'conversation_stats': self.conversation_manager.get_conversation_summary(),
                'session_id': self.conversation_manager.session_id
            }

            # 可选：包含翻译结果
            if include_translation and 'translated' in emotion_result:
                response_data['translated_input'] = emotion_result['translated']

            # 可选：包含原始情感结果
            if return_raw:
                response_data['raw_emotion_result'] = emotion_result

            logger.info(f"聊天处理完成: {user_input[:30]}... -> {emotion} ({processing_time:.2f}s)")

            return response_data

        except Exception as e:
            self.stats['error_count'] += 1
            logger.error(f"聊天处理失败: {e}", exc_info=True)

            # 返回错误响应
            return {
                'success': False,
                'response': "抱歉，处理您的请求时出现了问题。请稍后再试。",
                'error': str(e)[:100],
                'processing_time': time.time() - start_time
            }

    def _adjust_response_for_emotion(self, response: str, emotion: str) -> str:
        """根据情感调整回复"""
        # 简单的情绪词汇调整（可根据需要扩展）
        emotion_adjustments = {
            'joy': {
                '不好': '很好',
                '难过': '开心',
                '抱歉': '太好了'
            },
            'sadness': {
                '开心': '理解',
                '太好了': '我明白',
                '恭喜': '抱抱你'
            },
            'anger': {
                '开心': '冷静',
                '太好了': '我理解',
                '别急': '请冷静'
            }
        }

        if emotion in emotion_adjustments:
            adjustments = emotion_adjustments[emotion]
            for old, new in adjustments.items():
                if old in response:
                    response = response.replace(old, new)

        return response

    def _apply_safety_filter(self, response: str) -> str:
        """应用安全过滤器"""
        # 敏感词过滤（示例）
        sensitive_words = [
            '自杀', '杀人', '暴力', '色情',
            'kill myself', 'violence', 'porn'
        ]

        for word in sensitive_words:
            if word in response.lower():
                logger.warning(f"检测到敏感词: {word}")
                return "抱歉，我无法回复这个问题。"

        return response

    def _control_response_length(self, response: str, max_length: int = 300) -> str:
        """控制回复长度"""
        if len(response) > max_length:
            # 在句号、问号或感叹号处截断
            for i in range(max_length - 20, max_length):
                if i < len(response) and response[i] in '。！？.!?':
                    return response[:i + 1]

            # 如果没有合适的截断点，直接截断
            return response[:max_length] + "..."

        return response

    def _update_emotion_stats(self, emotion: str):
        """更新情感统计"""
        self.stats['emotion_distribution'][emotion] = \
            self.stats['emotion_distribution'].get(emotion, 0) + 1

    def get_engine_stats(self) -> Dict:
        """获取引擎统计信息"""
        avg_processing_time = 0
        if self.stats['total_requests'] > 0:
            avg_processing_time = self.stats['total_processing_time'] / self.stats['total_requests']

        return {
            'total_requests': self.stats['total_requests'],
            'avg_processing_time': avg_processing_time,
            'emotion_distribution': self.stats['emotion_distribution'],
            'error_count': self.stats['error_count'],
            'conversation_count': self.conversation_manager.state['turn_count'],
            'session_id': self.conversation_manager.session_id
        }

    def reset_conversation(self, new_session_id: str = None) -> str:
        """重置对话"""
        self.conversation_manager.reset(new_session_id)
        logger.info(f"对话已重置，新会话ID: {self.conversation_manager.session_id}")
        return self.conversation_manager.session_id

    def get_conversation_history(self, format_type: str = 'simple') -> str:
        """获取对话历史"""
        return self.conversation_manager.get_formatted_history(format_type)

    def save_conversation(self, filepath: str = None) -> bool:
        """保存对话"""
        if not filepath:
            timestamp = time.strftime('%Y%m%d_%H%M%S')
            filepath = f"conversation_{self.conversation_manager.session_id}_{timestamp}.json"

        return self.conversation_manager.save_to_file(filepath)


# 快速创建函数
def create_chat_engine(emotion_engine: EmotionEngine = None,
                       blenderbot_config: Dict = None,
                       chat_config: Dict = None) -> Optional[ChatEngine]:
    """
    创建聊天引擎

    Args:
        emotion_engine: 情绪分析引擎
        blenderbot_config: BlenderBot配置
        chat_config: 聊天引擎配置

    Returns:
        ChatEngine实例或None
    """
    try:
        # 导入必要的模块
        from blenderbot_manager import create_blenderbot_manager

        # 创建BlenderBot管理器
        blenderbot_manager = create_blenderbot_manager(blenderbot_config)
        if not blenderbot_manager:
            logger.error("无法创建BlenderBot管理器")
            return None

        # 如果没有提供情绪分析引擎，尝试创建一个
        if not emotion_engine:
            logger.warning("未提供情绪分析引擎，尝试创建...")
            # 这里需要根据你的实际情况创建EmotionEngine
            # 为了示例，我们返回None
            return None

        # 创建聊天引擎
        engine = ChatEngine(
            emotion_engine=emotion_engine,
            blenderbot_manager=blenderbot_manager,
            config=chat_config or {}
        )

        logger.info("聊天引擎创建成功")
        return engine

    except Exception as e:
        logger.error(f"创建聊天引擎失败: {e}", exc_info=True)
        return None