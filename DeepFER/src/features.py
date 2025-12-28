import cv2
import dlib
import numpy as np
import os
from skimage.feature import hog

# 尝试兼容不同的导入路径
try:
    from src.config import cfg
except ImportError:
    from config import cfg
# 全局加载器，避免多进程重复加载
_detector = None
_predictor = None


def init_models():
    """在进程启动时调用"""
    global _detector, _predictor
    if _detector is None:
        _detector = dlib.get_frontal_face_detector()
    if _predictor is None:
        if not os.path.exists(cfg.LANDMARK_PATH):
            raise FileNotFoundError(f"缺少关键点模型: {cfg.LANDMARK_PATH}")
        _predictor = dlib.shape_predictor(cfg.LANDMARK_PATH)


def extract_dual_features(image_bgr):
    """
    输入: 原始 BGR 图像 (任意尺寸)
    输出: (img_tensor, feat_vector)
    """
    # 确保模型已加载
    init_models()

    # 1. 图像流预处理 (Image Stream)
    # Resize 到 224x224 适配 ResNet
    img_resized = cv2.resize(image_bgr, (cfg.IMG_SIZE, cfg.IMG_SIZE))
    # 转换颜色 BGR -> RGB (深度学习标准)
    img_rgb = cv2.cvtColor(img_resized, cv2.COLOR_BGR2RGB)
    # 归一化: ResNet 通常使用 preprocess_input，但这里我们简单做 /255.0
    # 如果用 tf.keras.applications.resnet50.preprocess_input 会更好，但需保持一致
    img_tensor = img_rgb.astype('float32') / 255.0

    # 2. 几何特征流 (Geometric Stream)
    extra_features = []

    # 为了特征提取稳定，使用灰度图
    gray = cv2.cvtColor(img_resized, cv2.COLOR_BGR2GRAY)

    # --- A. Landmarks (关键点) ---
    # RAF-DB aligned 版本通常已经就是人脸了，检测器可能反而检测不到
    # 所以策略是：先检测，检测不到就默认全图是脸
    rects = _detector(gray, 1)
    rect = rects[0] if len(rects) > 0 else dlib.rectangle(0, 0, cfg.IMG_SIZE, cfg.IMG_SIZE)

    shape = _predictor(gray, rect)
    landmarks = np.array([[p.x, p.y] for p in shape.parts()])

    # 【关键】坐标归一化：除以图片尺寸，使其在 0-1 之间
    landmarks_norm = landmarks / float(cfg.IMG_SIZE)
    extra_features.extend(landmarks_norm.flatten())  # 68*2 = 136 维

    # --- B. HOG (纹理特征) ---
    # 224x224 图片，cell=16x16 -> 14x14 cells
    # block=1x1 -> 14x14 blocks
    # orientations=8 -> 14*14*8 = 1568 维
    feat_hog = hog(gray, orientations=8, pixels_per_cell=(16, 16),
                   cells_per_block=(1, 1), visualize=False)
    extra_features.extend(feat_hog)

    # 拼接并转为 float32
    feat_vector = np.array(extra_features, dtype=np.float32)

    return img_tensor, feat_vector