# model_loader.py
import os
import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer
import logging

logger = logging.getLogger(__name__)


class ModelLoader:
    """专业模型加载器，处理所有与模型加载相关的复杂问题"""

    def __init__(self, model_path="./local_models/emotion_model"):
        self.model_path = model_path
        self.model = None
        self.tokenizer = None
        self.loaded = False

    # model_loader.py 修改后的 _load_model 方法
    def load(self):
        """主加载入口：安全加载模型和分词器"""
        try:
            logger.info(f"开始加载模型，路径: {self.model_path}")

            # 1. 验证路径
            self._validate_path()

            # 2. 加载分词器
            self.tokenizer = AutoTokenizer.from_pretrained(self.model_path)
            logger.info("分词器加载成功")

            # 3. 检测是否有GPU可用
            device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
            logger.info(f"使用设备: {device}")

            # 4. 加载模型（简化版本，不依赖accelerate）
            self.model = AutoModelForSequenceClassification.from_pretrained(
                self.model_path
            )

            # 5. 移动模型到对应设备
            self.model.to(device)
            self.device = device

            # 6. 设置为评估模式
            self.model.eval()

            self.loaded = True
            logger.info("模型加载成功")
            return True

        except Exception as e:
            logger.error(f"模型加载失败: {e}", exc_info=True)
            self._cleanup()
            return False

        except Exception as e:
            logger.error(f"模型加载失败: {e}", exc_info=True)
            self._cleanup()
            return False

    # 修改 model_loader.py 的 _validate_path 方法
    def _validate_path(self):
        """更灵活的文件验证"""
        if not os.path.exists(self.model_path):
            raise FileNotFoundError(f"模型路径不存在: {self.model_path}")

        # 检查config.json（必须）
        if not os.path.exists(os.path.join(self.model_path, 'config.json')):
            raise FileNotFoundError("缺失 config.json")

        # 检查模型权重文件（支持多种格式）
        model_files = ['pytorch_model.bin', 'model.safetensors', 'tf_model.h5']
        found = False
        for f in model_files:
            if os.path.exists(os.path.join(self.model_path, f)):
                found = True
                self.model_file_type = f
                break

        if not found:
            available = os.listdir(self.model_path)
            raise FileNotFoundError(
                f"未找到模型权重文件。目录中的文件: {available}"
            )

    def _cleanup(self):
        """清理资源"""
        del self.model
        del self.tokenizer
        torch.cuda.empty_cache() if torch.cuda.is_available() else None

    # 修改 predict 方法
    def predict(self, text):
        """执行预测（封装了tokenize和模型推理）"""
        if not self.loaded:
            raise RuntimeError("模型未加载")

        # Tokenize
        inputs = self.tokenizer(text, return_tensors="pt", truncation=True, max_length=512)

        # 移动输入到正确设备
        inputs = {k: v.to(self.device) for k, v in inputs.items()}

        # 推理
        with torch.no_grad():
            outputs = self.model(**inputs)

        # 处理输出（移动回CPU用于后续处理）
        probabilities = torch.nn.functional.softmax(outputs.logits.cpu(), dim=-1)
        predicted_class_id = probabilities.argmax().item()

        # 获取标签名称
        label = self.model.config.id2label.get(predicted_class_id, f"LABEL_{predicted_class_id}")
        confidence = probabilities[0][predicted_class_id].item()

        return label, confidence