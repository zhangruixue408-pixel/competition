import tensorflow as tf
import numpy as np
import cv2
import os
import sys
import dlib
from skimage.feature import hog

# 1. 定位根目录
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from src.config import cfg
from src.models import build_transfer_model

# 初始化 Dlib
detector = dlib.get_frontal_face_detector()
predictor = dlib.shape_predictor(cfg.LANDMARK_PATH)


def crop_face(img_bgr):
    """
    核心修复：从大图中检测并裁剪出人脸
    """
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    rects = detector(gray, 1)

    if len(rects) == 0:
        print("⚠️ 警告：图中未检测到人脸！将使用原图尝试...")
        return img_bgr

    # 找到面积最大的人脸
    rect = max(rects, key=lambda r: r.width() * r.height())
    x, y, w, h = rect.left(), rect.top(), rect.width(), rect.height()

    # --- 关键：添加 Padding (像 RAF-DB 一样保留一点边缘) ---
    # RAF-DB 的 aligned 图片通常不是紧贴皮肤的，有一点宽松度
    pad = int(w * 0.15)  # 15% 的边距
    h_img, w_img = img_bgr.shape[:2]

    y1 = max(0, y - pad)
    y2 = min(h_img, y + h + pad)
    x1 = max(0, x - pad)
    x2 = min(w_img, x + w + pad)

    face_crop = img_bgr[y1:y2, x1:x2]
    return face_crop


def extract_features_inference(face_img):
    """
    输入必须已经是裁剪好的人脸图像 (Face Crop)
    """
    # 1. 统一缩放到 224x224 (模拟训练时的输入)
    img_resized = cv2.resize(face_img, (cfg.IMG_SIZE, cfg.IMG_SIZE))

    # --- 视觉流 ---
    img_rgb = cv2.cvtColor(img_resized, cv2.COLOR_BGR2RGB)
    img_tensor = img_rgb.astype('float32') / 255.0
    img_tensor = np.expand_dims(img_tensor, axis=0)

    # --- 几何流 ---
    gray_resized = cv2.cvtColor(img_resized, cv2.COLOR_BGR2GRAY)

    # 既然已经裁切好了，我们假设整张图就是脸
    # 这里我们不再重新 detect，而是直接把整张图当做 ROI
    # 这样可以避免 resize 后 dlib 检测失败的问题，且强制对齐
    rect = dlib.rectangle(0, 0, cfg.IMG_SIZE, cfg.IMG_SIZE)

    # 提取关键点
    shape = predictor(gray_resized, rect)
    landmarks = np.array([[p.x, p.y] for p in shape.parts()])

    # 归一化
    landmarks_norm = landmarks / float(cfg.IMG_SIZE)
    feat_flat = list(landmarks_norm.flatten())

    # 提取 HOG
    feat_hog = hog(gray_resized, orientations=8, pixels_per_cell=(16, 16),
                   cells_per_block=(1, 1), visualize=False)
    feat_flat.extend(feat_hog)

    feat_vector = np.array(feat_flat, dtype=np.float32)
    feat_vector = np.expand_dims(feat_vector, axis=0)

    return img_tensor, feat_vector


def run_inference(image_path, model_path):
    # 1. 读取原始大图
    if not os.path.exists(image_path):
        print(f"错误：找不到图片 {image_path}")
        return
    raw_img = cv2.imread(image_path)

    # 2. 核心步骤：先裁剪！
    print("正在检测并裁剪人脸...")
    face_img = crop_face(raw_img)

    # 显示一下裁剪结果，确认裁对了吗
    # cv2.imshow('Debug: Face Crop', face_img)
    # cv2.waitKey(1000)

    # 3. 提取特征
    print("正在提取双流特征...")
    try:
        img_input, feat_input = extract_features_inference(face_img)
    except Exception as e:
        print(f"特征提取出错: {e}")
        return

    # 4. 加载模型
    feat_dim = feat_input.shape[1]
    model = build_transfer_model(feat_dim)
    # 屏蔽烦人的 Warning
    import logging
    tf.get_logger().setLevel(logging.ERROR)
    print(f"正在加载权重: {model_path} (特征维数: {feat_dim})")
    model.load_weights(model_path)

    # 5. 推理
    preds = model.predict([img_input, feat_input], verbose=0)[0]

    # 6. 展示结果
    results = []
    for i, prob in enumerate(preds):
        results.append((cfg.EMOTIONS[i], prob))
    results.sort(key=lambda x: x[1], reverse=True)

    print("\n" + "=" * 30)
    print(f"最终预测结果")
    print("=" * 30)

    top_emotion = results[0][0]
    for emotion, prob in results:
        bar = "█" * int(prob * 20)
        # 变色高亮预测结果
        prefix = ">> " if emotion == top_emotion else "   "
        print(f"{prefix}{emotion:10s}: [{bar:20s}] {prob * 100:6.2f}%")

    # 可视化弹窗
    h, w = raw_img.shape[:2]
    # 在原图上写字
    cv2.putText(raw_img, f"Pred: {top_emotion}", (20, 50),
                cv2.FONT_HERSHEY_SIMPLEX, 1.5, (0, 255, 0), 3)

    # 缩小一点方便展示
    if h > 800:
        scale = 800 / h
        raw_img = cv2.resize(raw_img, (int(w * scale), int(h * scale)))

    cv2.imshow('Final Result', raw_img)
    print("\n按任意键退出...")
    cv2.waitKey(0)
    cv2.destroyAllWindows()


if __name__ == "__main__":
    MODEL_PATH = r'D:\competent\DeepFER\checkpoints\best_rafdb.keras'
    # 请换一张开心的大图，甚至是全身照试试
    TEST_IMG = r'D:\competent\DeepFER\data\scare\sc2.jpg'

    run_inference(TEST_IMG, MODEL_PATH)