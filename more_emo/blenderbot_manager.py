# blenderbot_manager.py
"""
BlenderBot模型管理器
负责加载模型、生成回复和管理对话状态
"""
import torch
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM
import logging
from typing import Dict, List, Optional, Tuple
import json
import os

logger = logging.getLogger(__name__)


class BlenderBotManager:
    """BlenderBot模型管理器"""

    def __init__(self, model_path: str, device: str = None, config: Dict = None):
        """
        初始化BlenderBot管理器

        Args:
            model_path: 模型路径
            device: 指定设备 (cpu/cuda)
            config: 配置参数
        """
        self.model_path = model_path
        self.model = None
        self.tokenizer = None
        self.device = device or ('cuda' if torch.cuda.is_available() else 'cpu')
        self.config = config or {}

        # 对话历史管理
        self.conversation_history = []
        self.max_history = self.config.get('max_history', 5)

        # 生成参数
        self.generation_config = {
            'max_length': self.config.get('max_length', 200),
            'min_length': self.config.get('min_length', 20),
            'temperature': self.config.get('temperature', 0.9),
            'top_p': self.config.get('top_p', 0.95),
            'repetition_penalty': self.config.get('repetition_penalty', 1.2),
            'num_beams': self.config.get('num_beams', 3),
            'early_stopping': self.config.get('early_stopping', True),
        }

        # 情感提示模板
        self.emotion_prompts = self.config.get('emotion_prompts', {
            'joy': "用户开心地说：",
            'anger': "用户生气地说：",
            'sadness': "用户难过地说：",
            'fear': "用户害怕地说：",
            'disgust': "用户厌恶地说：",
            'surprise': "用户惊讶地说：",
            'neutral': "用户说："
        })

        # 情感特定的生成参数
        self.emotion_generation_config = self.config.get('emotion_generation_config', {
            'joy': {'temperature': 0.9, 'top_p': 0.95},
            'anger': {'temperature': 0.7, 'repetition_penalty': 1.5},
            'sadness': {'temperature': 0.6, 'length_penalty': 1.2},
            'fear': {'temperature': 0.7, 'top_p': 0.9},
            'default': self.generation_config
        })

        logger.info(f"BlenderBot管理器初始化完成，使用设备: {self.device}")

    # blenderbot_manager.py - 修改 load_model 方法
    def load_model(self) -> bool:
        """加载模型和分词器"""
        try:
            logger.info(f"正在加载BlenderBot模型，路径: {self.model_path}")

            # 检查路径是否存在
            if not os.path.exists(self.model_path):
                logger.error(f"模型路径不存在: {self.model_path}")
                return False

            # 方法1：尝试使用绝对路径加载
            abs_path = os.path.abspath(self.model_path)
            logger.info(f"使用绝对路径: {abs_path}")

            # 方法2：检查是否是一个有效的transformers模型目录
            required_files = ['config.json', 'pytorch_model.bin', 'tokenizer_config.json']
            for file in required_files:
                file_path = os.path.join(abs_path, file)
                if not os.path.exists(file_path):
                    logger.warning(f"缺少必要文件: {file}")

            # 尝试加载分词器 - 修复参数格式
            try:
                self.tokenizer = AutoTokenizer.from_pretrained(
                    abs_path,
                    local_files_only=True
                )
                logger.info("分词器加载成功")
            except Exception as tokenizer_error:
                logger.error(f"分词器加载失败: {tokenizer_error}")

                # 尝试使用绝对路径字符串
                try:
                    self.tokenizer = AutoTokenizer.from_pretrained(
                        abs_path,
                        local_files_only=False
                    )
                    logger.info("分词器加载成功（使用非本地模式）")
                except Exception as e2:
                    logger.error(f"分词器二次加载失败: {e2}")
                    return False

            # 尝试加载模型
            try:
                self.model = AutoModelForSeq2SeqLM.from_pretrained(
                    abs_path,
                    local_files_only=True
                )
            except Exception as model_error:
                logger.error(f"模型加载失败: {model_error}")

                # 尝试使用绝对路径字符串
                try:
                    self.model = AutoModelForSeq2SeqLM.from_pretrained(
                        abs_path,
                        local_files_only=False
                    )
                except Exception as e2:
                    logger.error(f"模型二次加载失败: {e2}")
                    return False

            # 移动到指定设备
            self.model = self.model.to(self.device)
            self.model.eval()

            logger.info(f"模型加载成功，移动到设备: {self.device}")

            # 测试模型是否正常工作
            test_result = self.test_model()
            if test_result:
                logger.info("模型测试通过")
            else:
                logger.warning("模型测试失败，但已加载")

            return True

        except Exception as e:
            logger.error(f"加载模型失败: {e}", exc_info=True)
            return False

    def test_model(self) -> bool:
        """测试模型是否能正常工作"""
        try:
            test_input = "Hello, how are you?"
            _ = self.generate_response(test_input, test_mode=True)
            return True
        except Exception as e:
            logger.error(f"模型测试失败: {e}")
            return False

    def add_emotion_context(self, text: str, emotion: str = None) -> str:
        """
        为输入文本添加情感上下文

        Args:
            text: 原始文本
            emotion: 情感标签

        Returns:
            添加情感上下文后的文本
        """
        if not emotion or emotion not in self.emotion_prompts:
            return text

        # 获取情感提示
        emotion_prompt = self.emotion_prompts.get(emotion, self.emotion_prompts['neutral'])

        # 构建带情感的输入
        if emotion_prompt.endswith("说："):
            # 中文格式
            return f"{emotion_prompt}{text}"
        else:
            # 英文格式
            return f"[{emotion_prompt}] {text}"

    def get_generation_params(self, emotion: str = None) -> Dict:
        """
        根据情感获取生成参数

        Args:
            emotion: 情感标签

        Returns:
            生成参数配置
        """
        base_params = self.generation_config.copy()

        if emotion and emotion in self.emotion_generation_config:
            # 更新情感特定的参数
            emotion_params = self.emotion_generation_config[emotion]
            base_params.update(emotion_params)

        return base_params

    def format_history(self, history: List[Dict] = None) -> str:
        """
        格式化对话历史

        Args:
            history: 对话历史列表

        Returns:
            格式化后的历史文本
        """
        if not history:
            history = self.conversation_history

        if not history:
            return ""

        formatted = []
        for i, exchange in enumerate(history[-self.max_history:], 1):
            if exchange.get('role') == 'user':
                text = exchange.get('text', '')
                emotion = exchange.get('emotion', '')

                # 添加情感上下文
                if emotion:
                    text = self.add_emotion_context(text, emotion)

                formatted.append(f"User {i}: {text}")
            else:
                formatted.append(f"Bot {i}: {exchange.get('text', '')}")

        return "\n".join(formatted)

    def generate_response(self,
                          user_input: str,
                          emotion: str = None,
                          history: List[Dict] = None,
                          test_mode: bool = False) -> str:
        """
        生成回复

        Args:
            user_input: 用户输入
            emotion: 用户情感
            history: 对话历史
            test_mode: 是否为测试模式

        Returns:
            生成的回复
        """
        if not self.model or not self.tokenizer:
            logger.error("模型未加载")
            return "模型未加载，请先调用load_model()"

        try:
            # 准备输入
            if emotion:
                user_input_with_emotion = self.add_emotion_context(user_input, emotion)
            else:
                user_input_with_emotion = user_input

            # 获取对话历史
            if history is None:
                history = self.conversation_history

            # 构建完整输入
            if history:
                history_text = self.format_history(history)
                full_input = f"{history_text}\nUser: {user_input_with_emotion}\nBot:"
            else:
                full_input = f"User: {user_input_with_emotion}\nBot:"

            # 获取生成参数
            generation_params = self.get_generation_params(emotion)

            # 编码输入
            inputs = self.tokenizer(
                full_input,
                return_tensors="pt",
                truncation=True,
                max_length=512
            ).to(self.device)

            # 生成回复
            with torch.no_grad():
                outputs = self.model.generate(
                    **inputs,
                    **generation_params
                )

            # 解码输出
            response = self.tokenizer.decode(
                outputs[0],
                skip_special_tokens=True
            ).strip()

            # 清理回复（移除可能的重复）
            response = self._clean_response(response)

            if not test_mode:
                # 更新对话历史
                self._update_history(user_input, response, emotion)

            return response

        except Exception as e:
            logger.error(f"生成回复失败: {e}", exc_info=True)
            return f"抱歉，我遇到了一些问题: {str(e)[:50]}..."

    def _clean_response(self, response: str) -> str:
        """清理回复文本"""
        # 移除可能的多余前缀
        prefixes_to_remove = ["Bot:", "Assistant:", "Response:", "回复:", "答："]
        for prefix in prefixes_to_remove:
            if response.startswith(prefix):
                response = response[len(prefix):].strip()

        # 移除可能的重复
        lines = response.split('\n')
        if len(lines) > 1 and lines[0] in lines[1:]:
            # 第一行在后续重复了
            return lines[0]

        return response.strip()

    def _update_history(self, user_input: str, bot_response: str, emotion: str = None):
        """更新对话历史"""
        # 添加用户输入
        self.conversation_history.append({
            'role': 'user',
            'text': user_input,
            'emotion': emotion
        })

        # 添加机器人回复
        self.conversation_history.append({
            'role': 'bot',
            'text': bot_response
        })

        # 保持历史长度
        if len(self.conversation_history) > self.max_history * 2:
            self.conversation_history = self.conversation_history[-(self.max_history * 2):]

    def reset_conversation(self):
        """重置对话历史"""
        self.conversation_history = []
        logger.info("对话历史已重置")

    def get_conversation_stats(self) -> Dict:
        """获取对话统计信息"""
        user_messages = [h for h in self.conversation_history if h['role'] == 'user']
        bot_messages = [h for h in self.conversation_history if h['role'] == 'bot']

        return {
            'total_exchanges': len(self.conversation_history) // 2,
            'user_messages': len(user_messages),
            'bot_messages': len(bot_messages),
            'max_history': self.max_history,
            'emotion_counts': self._count_emotions(user_messages)
        }

    def _count_emotions(self, user_messages: List[Dict]) -> Dict:
        """统计各种情感的出现次数"""
        emotion_counts = {}
        for msg in user_messages:
            emotion = msg.get('emotion')
            if emotion:
                emotion_counts[emotion] = emotion_counts.get(emotion, 0) + 1
        return emotion_counts

    def save_conversation(self, filepath: str):
        """保存对话历史到文件"""
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(self.conversation_history, f, ensure_ascii=False, indent=2)
            logger.info(f"对话历史已保存到: {filepath}")
        except Exception as e:
            logger.error(f"保存对话历史失败: {e}")

    def load_conversation(self, filepath: str):
        """从文件加载对话历史"""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                self.conversation_history = json.load(f)
            logger.info(f"对话历史已从 {filepath} 加载")
        except Exception as e:
            logger.error(f"加载对话历史失败: {e}")


# 配置示例
DEFAULT_BLENDERBOT_CONFIG = {
    # 模型参数
    'model_path': './local_models/blenderbot',

    # 对话历史
    'max_history': 5,

    # 生成参数
    'max_length': 200,
    'min_length': 20,
    'temperature': 0.9,
    'top_p': 0.95,
    'repetition_penalty': 1.2,
    'num_beams': 3,
    'early_stopping': True,

    # 情感提示
    'emotion_prompts': {
        'joy': "用户开心地说：",
        'anger': "用户生气地说：",
        'sadness': "用户难过地说：",
        'fear': "用户害怕地说：",
        'disgust': "用户厌恶地说：",
        'surprise': "用户惊讶地说：",
        'neutral': "用户说："
    },

    # 情感特定生成参数
    'emotion_generation_config': {
        'joy': {'temperature': 0.9, 'top_p': 0.95},
        'anger': {'temperature': 0.7, 'repetition_penalty': 1.5},
        'sadness': {'temperature': 0.6, 'length_penalty': 1.2},
        'fear': {'temperature': 0.7, 'top_p': 0.9}
    }
}


def create_blenderbot_manager(config: Dict = None) -> BlenderBotManager:
    """
    创建BlenderBot管理器实例

    Args:
        config: 配置字典

    Returns:
        BlenderBotManager实例
    """
    # 合并默认配置和用户配置
    final_config = DEFAULT_BLENDERBOT_CONFIG.copy()
    if config:
        final_config.update(config)

    # 创建管理器
    manager = BlenderBotManager(
        model_path=final_config['model_path'],
        config=final_config
    )

    # 加载模型
    if manager.load_model():
        logger.info("BlenderBot管理器创建成功")
        return manager
    else:
        logger.error("BlenderBot管理器创建失败")
        return None