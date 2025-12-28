# 创建 scripts/debug_labels.py
import numpy as np
import cv2
import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)
from src.config import cfg


def check_data():
    # 加载处理好的训练数据
    print("正在加载训练数据...")
    imgs = np.load(os.path.join(cfg.PROCESSED_DIR, 'train_img.npy'))
    lbls = np.load(os.path.join(cfg.PROCESSED_DIR, 'train_lbl.npy'))

    # 查找被标记为 Happy (cfg.CLASS_MAP[4] -> 3) 的图片
    happy_idx = 3
    sad_idx = 4

    print(f"配置中 Happy 的索引应该是: {happy_idx}")
    print(f"配置中 Sad 的索引应该是: {sad_idx}")

    # 找到所有 Happy 的索引
    happy_samples = np.where(lbls == happy_idx)[0]

    if len(happy_samples) == 0:
        print("错误：训练集中找不到标签为 3 (Happy) 的数据！")
        return

    print(f"找到 {len(happy_samples)} 张 Happy 样本。随机展示一张...")

    # 随机抽一张
    idx = np.random.choice(happy_samples)
    img = imgs[idx]  # 已经是归一化后的 float32 (0-1) RGB

    # 还原显示
    img_show = (img * 255).astype(np.uint8)
    img_show = cv2.cvtColor(img_show, cv2.COLOR_RGB2BGR)

    cv2.putText(img_show, f"Label: {lbls[idx]} (Happy)", (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)

    cv2.imshow('Is this Happy?', img_show)
    print("请看弹出的窗口：这张图是笑脸吗？如果是哭脸，说明映射反了！")
    cv2.waitKey(0)
    cv2.destroyAllWindows()


if __name__ == "__main__":
    check_data()