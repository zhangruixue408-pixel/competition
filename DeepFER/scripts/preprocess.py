import os
import cv2
import numpy as np
import sys
from tqdm import tqdm
from concurrent.futures import ProcessPoolExecutor

# 获取当前脚本所在目录的上一级目录（即 DeepFER 根目录）
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR) # 插入到路径最前面，确保优先从这里找 src

from src.config import cfg
from src.features import extract_dual_features, init_models


def process_single_image(args):
    """单个图片的处理函数"""
    img_path, label = args
    try:
        # 读取图片
        img = cv2.imread(img_path)
        if img is None: return None

        # 调用【核心】特征提取
        img_tensor, feat_vector = extract_dual_features(img)

        return {
            'img': img_tensor,
            'feat': feat_vector,
            'label': label
        }
    except Exception as e:
        return None


def preprocess_rafdb():
    if not os.path.exists(cfg.PROCESSED_DIR):
        os.makedirs(cfg.PROCESSED_DIR)

    # 扫描文件夹构建任务列表
    datasets = {'train': [], 'test': []}

    print("扫描 RAF-DB 目录...")
    # 假设结构: data/raf-db/train/1/*.jpg
    for split in ['train', 'test']:
        split_path = os.path.join(cfg.RAW_DATA_DIR, split)
        # 遍历标签文件夹 1-7
        for label_dir in os.listdir(split_path):
            if not label_dir.isdigit(): continue

            original_label = int(label_dir)  # 1-7
            # 映射标签到 0-6
            mapped_label = cfg.CLASS_MAP.get(original_label)
            if mapped_label is None: continue

            folder_path = os.path.join(split_path, label_dir)
            for img_name in os.listdir(folder_path):
                if img_name.lower().endswith(('.jpg', '.jpeg', '.png')):
                    img_path = os.path.join(folder_path, img_name)
                    datasets[split].append((img_path, mapped_label))

    # 执行处理
    for split, tasks in datasets.items():
        print(f"\n正在处理 {split} 集 (共 {len(tasks)} 张)...")

        X_img, X_feat, Y = [], [], []

        # 多进程处理
        with ProcessPoolExecutor(initializer=init_models) as executor:
            # 这里的 batch_size 设置大一点可以减少 IPC 开销
            results = list(tqdm(executor.map(process_single_image, tasks), total=len(tasks)))

        # 过滤失败的图片
        for res in results:
            if res is not None:
                X_img.append(res['img'])
                X_feat.append(res['feat'])
                Y.append(res['label'])

        # 转换为 numpy 数组
        X_img = np.array(X_img, dtype='float32')
        X_feat = np.array(X_feat, dtype='float32')
        Y = np.array(Y, dtype='int32')

        print(f"  图像维度: {X_img.shape}")  # (N, 224, 224, 3)
        print(f"  特征维度: {X_feat.shape}")  # (N, 1704) 左右

        # 保存
        np.save(os.path.join(cfg.PROCESSED_DIR, f'{split}_img.npy'), X_img)
        np.save(os.path.join(cfg.PROCESSED_DIR, f'{split}_feat.npy'), X_feat)
        np.save(os.path.join(cfg.PROCESSED_DIR, f'{split}_lbl.npy'), Y)


if __name__ == "__main__":
    preprocess_rafdb()