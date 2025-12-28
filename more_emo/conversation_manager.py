# conversation_manager.py
"""
对话管理器
负责管理对话历史、上下文和状态
"""
import json
import time
from typing import Dict, List, Optional, Any
import logging

logger = logging.getLogger(__name__)


class ConversationManager:
    """对话管理器"""

    def __init__(self, max_history: int = 5, session_id: str = None):
        """
        初始化对话管理器

        Args:
            max_history: 最大历史记录数
            session_id: 会话ID
        """
        self.max_history = max_history
        self.session_id = session_id or f"session_{int(time.time())}"

        # 对话历史
        self.history = []

        # 对话状态
        self.state = {
            'created_at': time.time(),
            'last_updated': time.time(),
            'turn_count': 0,
            'emotion_trend': [],  # 情感趋势
            'topics': []  # 话题列表
        }

        logger.info(f"对话管理器初始化完成，会话ID: {self.session_id}")

    def add_exchange(self,
                     user_input: str,
                     bot_response: str,
                     emotion: str = None,
                     confidence: float = None,
                     metadata: Dict = None):
        """
        添加一轮对话

        Args:
            user_input: 用户输入
            bot_response: 机器人回复
            emotion: 用户情感
            confidence: 情感置信度
            metadata: 额外元数据
        """
        exchange = {
            'user': {
                'text': user_input,
                'emotion': emotion,
                'confidence': confidence,
                'timestamp': time.time()
            },
            'bot': {
                'text': bot_response,
                'timestamp': time.time()
            },
            'metadata': metadata or {}
        }

        self.history.append(exchange)

        # 更新状态
        self.state['turn_count'] += 1
        self.state['last_updated'] = time.time()

        # 记录情感趋势
        if emotion:
            self.state['emotion_trend'].append({
                'emotion': emotion,
                'confidence': confidence,
                'timestamp': time.time()
            })
            # 只保留最近的情感记录
            if len(self.state['emotion_trend']) > 10:
                self.state['emotion_trend'] = self.state['emotion_trend'][-10:]

        # 保持历史长度
        if len(self.history) > self.max_history:
            self.history = self.history[-self.max_history:]

        logger.debug(f"添加对话交换，当前轮次: {self.state['turn_count']}")

    def get_formatted_history(self, format_type: str = 'simple') -> str:
        """
        获取格式化后的对话历史

        Args:
            format_type: 格式类型 (simple/detailed/blenderbot)

        Returns:
            格式化后的历史文本
        """
        if format_type == 'simple':
            return self._format_simple()
        elif format_type == 'detailed':
            return self._format_detailed()
        elif format_type == 'blenderbot':
            return self._format_blenderbot()
        else:
            return self._format_simple()

    def _format_simple(self) -> str:
        """简单格式：只包含文本"""
        formatted = []
        for i, exchange in enumerate(self.history[-self.max_history:], 1):
            formatted.append(f"User {i}: {exchange['user']['text']}")
            formatted.append(f"Bot {i}: {exchange['bot']['text']}")
        return "\n".join(formatted)

    def _format_detailed(self) -> str:
        """详细格式：包含情感和元数据"""
        formatted = []
        for i, exchange in enumerate(self.history[-self.max_history:], 1):
            user_text = exchange['user']['text']
            emotion = exchange['user'].get('emotion')
            confidence = exchange['user'].get('confidence')

            if emotion:
                formatted.append(f"User {i} [{emotion}:{confidence:.2f}]: {user_text}")
            else:
                formatted.append(f"User {i}: {user_text}")

            formatted.append(f"Bot {i}: {exchange['bot']['text']}")

        return "\n".join(formatted)

    def _format_blenderbot(self) -> str:
        """BlenderBot格式：适合模型输入的格式"""
        formatted = []
        for exchange in self.history[-self.max_history:]:
            formatted.append(f"User: {exchange['user']['text']}")
            formatted.append(f"Bot: {exchange['bot']['text']}")
        return "\n".join(formatted)

    def get_last_n_exchanges(self, n: int = 3) -> List[Dict]:
        """获取最近n轮对话"""
        return self.history[-n:] if n <= len(self.history) else self.history.copy()

    def get_emotion_summary(self) -> Dict:
        """获取情感摘要"""
        if not self.state['emotion_trend']:
            return {'dominant_emotion': 'neutral', 'emotion_counts': {}}

        # 统计情感频率
        emotion_counts = {}
        for entry in self.state['emotion_trend']:
            emotion = entry['emotion']
            emotion_counts[emotion] = emotion_counts.get(emotion, 0) + 1

        # 找到主要情感
        dominant_emotion = max(emotion_counts.items(), key=lambda x: x[1])[0] if emotion_counts else 'neutral'

        # 计算情感稳定性
        emotion_stability = self._calculate_emotion_stability()

        return {
            'dominant_emotion': dominant_emotion,
            'emotion_counts': emotion_counts,
            'emotion_stability': emotion_stability,
            'trend_length': len(self.state['emotion_trend'])
        }

    def _calculate_emotion_stability(self) -> float:
        """计算情感稳定性（0-1，越高越稳定）"""
        if len(self.state['emotion_trend']) < 2:
            return 1.0

        # 计算情感变化的次数
        changes = 0
        for i in range(1, len(self.state['emotion_trend'])):
            if self.state['emotion_trend'][i]['emotion'] != self.state['emotion_trend'][i - 1]['emotion']:
                changes += 1

        stability = 1.0 - (changes / (len(self.state['emotion_trend']) - 1))
        return max(0.0, min(1.0, stability))

    def get_conversation_summary(self) -> Dict:
        """获取对话摘要"""
        return {
            'session_id': self.session_id,
            'turn_count': self.state['turn_count'],
            'history_length': len(self.history),
            'created_at': time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(self.state['created_at'])),
            'last_updated': time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(self.state['last_updated'])),
            'emotion_summary': self.get_emotion_summary(),
            'recent_topics': self._extract_topics()
        }

    def _extract_topics(self) -> List[str]:
        """提取话题（简单实现）"""
        topics = []
        topic_keywords = {
            '天气': ['天气', '下雨', '晴天', '温度'],
            '工作': ['工作', '上班', '项目', '会议'],
            '学习': ['学习', '考试', '课程', '作业'],
            '生活': ['吃饭', '睡觉', '运动', '购物'],
            '情感': ['开心', '难过', '生气', '喜欢']
        }

        for exchange in self.history[-5:]:
            text = exchange['user']['text'].lower() + exchange['bot']['text'].lower()
            for topic, keywords in topic_keywords.items():
                if any(keyword in text for keyword in keywords):
                    if topic not in topics:
                        topics.append(topic)

        return topics[:3]  # 返回最多3个话题

    def reset(self, new_session_id: str = None):
        """重置对话"""
        old_session_id = self.session_id
        self.session_id = new_session_id or f"session_{int(time.time())}"
        self.history = []
        self.state = {
            'created_at': time.time(),
            'last_updated': time.time(),
            'turn_count': 0,
            'emotion_trend': [],
            'topics': []
        }

        logger.info(f"对话已重置: {old_session_id} -> {self.session_id}")

    def save_to_file(self, filepath: str):
        """保存对话到文件"""
        try:
            data = {
                'session_id': self.session_id,
                'history': self.history,
                'state': self.state,
                'saved_at': time.time()
            }

            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            logger.info(f"对话已保存到: {filepath}")
            return True
        except Exception as e:
            logger.error(f"保存对话失败: {e}")
            return False

    def load_from_file(self, filepath: str) -> bool:
        """从文件加载对话"""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)

            self.session_id = data.get('session_id', self.session_id)
            self.history = data.get('history', [])
            self.state = data.get('state', self.state)

            logger.info(f"对话已从 {filepath} 加载")
            return True
        except Exception as e:
            logger.error(f"加载对话失败: {e}")
            return False


class MultiSessionManager:
    """多会话管理器（可选）"""

    def __init__(self, max_sessions: int = 10):
        self.max_sessions = max_sessions
        self.sessions = {}  # session_id -> ConversationManager
        self.active_session_id = None

    def create_session(self, session_id: str = None) -> str:
        """创建新会话"""
        if not session_id:
            session_id = f"session_{int(time.time())}_{len(self.sessions)}"

        if session_id in self.sessions:
            logger.warning(f"会话已存在: {session_id}")
            return session_id

        self.sessions[session_id] = ConversationManager(session_id=session_id)

        # 限制会话数量
        if len(self.sessions) > self.max_sessions:
            # 移除最旧的会话
            oldest_key = min(self.sessions.keys(), key=lambda k: self.sessions[k].state['created_at'])
            del self.sessions[oldest_key]

        self.active_session_id = session_id
        return session_id

    def get_session(self, session_id: str = None) -> Optional[ConversationManager]:
        """获取会话"""
        if not session_id:
            session_id = self.active_session_id

        return self.sessions.get(session_id)

    def get_active_session(self) -> Optional[ConversationManager]:
        """获取当前活跃会话"""
        return self.get_session(self.active_session_id)

    def switch_session(self, session_id: str) -> bool:
        """切换会话"""
        if session_id in self.sessions:
            self.active_session_id = session_id
            return True
        return False

    def delete_session(self, session_id: str) -> bool:
        """删除会话"""
        if session_id in self.sessions:
            del self.sessions[session_id]
            if self.active_session_id == session_id:
                self.active_session_id = None
            return True
        return False

    def get_session_list(self) -> List[Dict]:
        """获取会话列表"""
        sessions = []
        for session_id, manager in self.sessions.items():
            summary = manager.get_conversation_summary()
            sessions.append({
                'session_id': session_id,
                'turn_count': summary['turn_count'],
                'created_at': summary['created_at'],
                'last_updated': summary['last_updated'],
                'dominant_emotion': summary['emotion_summary']['dominant_emotion'],
                'is_active': session_id == self.active_session_id
            })

        return sorted(sessions, key=lambda x: x['last_updated'], reverse=True)