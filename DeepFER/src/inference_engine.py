import cv2
import numpy as np
import dlib
import base64
import os
from skimage.feature import hog
from src.config import cfg
from src.models import build_transfer_model


class CVFEREngine:
    def __init__(self, model_path):
        # 1. 初始化检测器
        self.detector = dlib.get_frontal_face_detector()
        self.predictor = dlib.shape_predictor(cfg.LANDMARK_PATH)

        # 备用检测器：针对暗光或模糊情况
        self.haar_detector = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')

        # 2. 加载深度学习模型 (1704 维特征)
        self.model = build_transfer_model(1704)
        self.model.load_weights(model_path)
        print("✅ 后端诊断引擎已启动，准备捕获数据...")

    def predict_from_base64(self, b64_str):
        try:
            # --- 步骤 A: 严苛的数据解码 ---
            if ',' in b64_str:
                b64_str = b64_str.split(',')[1]

            # 自动修复 Base64 填充
            missing_padding = len(b64_str) % 4
            if missing_padding:
                b64_str += '=' * (4 - missing_padding)

            img_data = base64.b64decode(b64_str)
            nparr = np.frombuffer(img_data, np.uint8)
            img_bgr = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

            if img_bgr is None:
                print("❌ 数据传输异常：图片解码失败，请检查前端 Base64 格式")
                return None

            # 【关键】将收到的原始数据保存下来，供你人工排查
            cv2.imwrite("debug_received.jpg", img_bgr)

            # --- 步骤 B: 多维度旋转/镜像盲测 ---
            # 解决你提到的“左耳变右耳”和可能的手机旋转问题
            h, w = img_bgr.shape[:2]
            target_w = 640
            scale = target_w / w
            img_small = cv2.resize(img_bgr, (target_w, int(h * scale)))

            found_rect = None
            work_img = None

            # 测试 8 种组合：[原图, 镜像] x [0, 90, 180, 270度]
            for is_flip in [False, True]:
                if found_rect: break
                base = cv2.flip(img_small, 1) if is_flip else img_small

                for angle in [None, cv2.ROTATE_90_CLOCKWISE, cv2.ROTATE_180, cv2.ROTATE_90_COUNTERCLOCKWISE]:
                    curr = cv2.rotate(base, angle) if angle is not None else base
                    gray = cv2.cvtColor(curr, cv2.COLOR_BGR2GRAY)

                    # 尝试 Dlib 检测 (上采样 1 次)
                    rects = self.detector(gray, 1)
                    if len(rects) == 0:
                        # 尝试 Haar 检测
                        faces = self.haar_detector.detectMultiScale(gray, 1.1, 5)
                        rects = [dlib.rectangle(int(x), int(y), int(x + w), int(y + h)) for (x, y, w, h) in faces]

                    if len(rects) > 0:
                        found_rect = max(rects, key=lambda r: r.width() * r.height())
                        work_img = curr
                        print(f"✅ 人脸捕获成功! (镜像: {is_flip}, 旋转码: {angle})")
                        break

            if not found_rect:
                print("❌ 算法已尽力：8种姿态均未发现人脸，请检查 debug_received.jpg")
                return None

            # --- 步骤 C: 特征提取与推理 (修复 NameError) ---
            x, y, fw, fh = found_rect.left(), found_rect.top(), found_rect.width(), found_rect.height()
            pad = int(fw * 0.15)
            ih, iw = work_img.shape[:2]

            face_crop = work_img[max(0, y - pad):min(ih, y + fh + pad), max(0, x - pad):min(iw, x + fw + pad)]
            face_resized = cv2.resize(face_crop, (cfg.IMG_SIZE, cfg.IMG_SIZE))

            # 1. 图像流
            img_tensor = np.expand_dims(cv2.cvtColor(face_resized, cv2.COLOR_BGR2RGB).astype('float32') / 255.0, axis=0)

            # 2. 几何流 (关键点)
            gray_res = cv2.cvtColor(face_resized, cv2.COLOR_BGR2GRAY)
            shape = self.predictor(gray_res, dlib.rectangle(0, 0, 224, 224))
            landmarks = np.array([[p.x, p.y] for p in shape.parts()]) / 224.0

            # 3. HOG 特征
            feat_hog = hog(gray_res, orientations=8, pixels_per_cell=(16, 16), cells_per_block=(1, 1))

            # 4. 向量合并
            feat_vector = np.expand_dims(np.concatenate([landmarks.flatten(), feat_hog]).astype(np.float32), axis=0)

            # 5. 模型预测
            preds = self.model.predict([img_tensor, feat_vector], verbose=0)[0]
            idx = np.argmax(preds)

            return {
                "emotion": cfg.EMOTIONS[idx],
                "confidence": float(preds[idx])
            }

        except Exception as e:
            print(f"❌ 运行崩溃: {str(e)}")
            import traceback
            traceback.print_exc()
            return None