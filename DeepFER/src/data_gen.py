import tensorflow as tf
import numpy as np
import os
from config import cfg


def load_dataset(split='Training'):
    img_path = os.path.join(cfg.PROCESSED_DIR, f'{split}_img.npy')
    lbl_path = os.path.join(cfg.PROCESSED_DIR, f'{split}_label.npy')
    feat_path = os.path.join(cfg.PROCESSED_DIR, f'{split}_feat.npy')

    images = np.load(img_path)
    labels = np.load(lbl_path)
    features = np.load(feat_path)

    # 图像归一化 [0, 255] -> [0, 1]
    images = images.astype('float32') / 255.0

    return images, features, labels


def create_pipeline(split='Training', shuffle=False):
    images, features, labels = load_dataset(split)

    # 构建数据集
    # 输入是字典形式：{'img_input': ..., 'feat_input': ...}
    ds = tf.data.Dataset.from_tensor_slices((
        {'img_input': images, 'feat_input': features},
        labels
    ))

    if shuffle:
        ds = ds.shuffle(buffer_size=10000)

    ds = ds.batch(cfg.BATCH_SIZE)
    ds = ds.prefetch(tf.data.AUTOTUNE)  # 自动优化管道

    return ds, features.shape[1]