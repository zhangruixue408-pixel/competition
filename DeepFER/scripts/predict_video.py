import tensorflow as tf
import numpy as np
import cv2
import os
import sys
import dlib
import time
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


def process_frame(frame, model):
    """
    处理单帧图像并返回预测结果和绘制了信息后的图像
    """
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    rects = detector(gray, 0)  # 0 表示不进行上采样，为了速度

    if len(rects) == 0:
        return frame, "No Face"

    # 仅处理最大的一张脸
    rect = max(rects, key=lambda r: r.width() * r.height())
    x, y, w, h = rect.left(), rect.top(), rect.width(), rect.height()

    # 1. 裁剪并预处理
    pad = int(w * 0.15)
    h_img, w_img = frame.shape[:2]
    y1, y2 = max(0, y - pad), min(h_img, y + h + pad)
    x1, x2 = max(0, x - pad), min(w_img, x + w + pad)

    face_crop = frame[y1:y2, x1:x2]
    if face_crop.size == 0: return frame, "Crop Error"

    face_resized = cv2.resize(face_crop, (cfg.IMG_SIZE, cfg.IMG_SIZE))

    # 2. 视觉流输入
    img_rgb = cv2.cvtColor(face_resized, cv2.COLOR_BGR2RGB)
    img_tensor = img_rgb.astype('float32') / 255.0
    img_tensor = np.expand_dims(img_tensor, axis=0)

    # 3. 几何流输入
    gray_resized = cv2.cvtColor(face_resized, cv2.COLOR_BGR2GRAY)
    # 强制在 224x224 的图中提取关键点以匹配训练分布
    inner_rect = dlib.rectangle(0, 0, cfg.IMG_SIZE, cfg.IMG_SIZE)
    shape = predictor(gray_resized, inner_rect)

    # 坐标归一化
    landmarks = np.array([[p.x, p.y] for p in shape.parts()])
    landmarks_norm = landmarks / float(cfg.IMG_SIZE)

    # HOG
    feat_hog = hog(gray_resized, orientations=8, pixels_per_cell=(16, 16),
                   cells_per_block=(1, 1), visualize=False)

    feat_vector = np.concatenate([landmarks_norm.flatten(), feat_hog])
    feat_vector = np.expand_dims(feat_vector.astype(np.float32), axis=0)

    # 4. 推理
    preds = model.predict([img_tensor, feat_vector], verbose=0)[0]
    idx = np.argmax(preds)
    label = cfg.EMOTIONS[idx]
    prob = preds[idx]

    # 5. 绘制可视化
    color = (0, 255, 0) if label == 'Happy' else (255, 0, 0)
    cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
    text = f"{label}: {prob * 100:.1f}%"
    cv2.putText(frame, text, (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)

    return frame, label


def main():
    MODEL_PATH = r'D:\competent\DeepFER\checkpoints\best_rafdb.keras'

    # 先构建模型以获取特征维度
    # 注意：这里的特征维度需要和训练时一致，136 (Landmarks) + 1568 (HOG) = 1704
    # 如果你的 HOG 参数变了，这里需要相应调整
    dummy_feat_dim = 1704
    model = build_transfer_model(dummy_feat_dim)
    model.load_weights(MODEL_PATH)
    print("模型加载完成，正在启动摄像头...")

    cap = cv2.VideoCapture(0)  # 0 是默认摄像头

    # 性能优化：降低分辨率可以显著提升检测速度
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

    prev_time = 0

    while True:
        ret, frame = cap.read()
        if not ret: break

        # 处理当前帧
        processed_frame, result = process_frame(frame, model)

        # 计算并显示 FPS
        curr_time = time.time()
        fps = 1 / (curr_time - prev_time)
        prev_time = curr_time
        cv2.putText(processed_frame, f"FPS: {int(fps)}", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)

        cv2.imshow('Real-time FER (Deep Dual-Stream)', processed_frame)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()