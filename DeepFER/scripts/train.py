import tensorflow as tf
from tensorflow.keras import mixed_precision
import numpy as np
import os
import sys

# 第一步：物理定位根目录
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

print(f"Current System Path: {BASE_DIR}")

# 第三步：导入项目模块
try:
    from src.config import cfg
    from src.models import build_transfer_model
    print("Import successful!")
except ImportError as e:
    print(f"Import failed: {e}")
    sys.exit(1)

# 开启混合精度加速 (RTX 4060 支持)
mixed_precision.set_global_policy('mixed_float16')

def load_data(split):
    """从磁盘加载数据到内存"""
    img = np.load(os.path.join(cfg.PROCESSED_DIR, f'{split}_img.npy'))
    feat = np.load(os.path.join(cfg.PROCESSED_DIR, f'{split}_feat.npy'))
    lbl = np.load(os.path.join(cfg.PROCESSED_DIR, f'{split}_lbl.npy'))
    return img, feat, lbl

def get_generator(images, features, labels):
    """懒加载生成器：每次只读入当前 batch 的数据到 GPU"""
    def gen():
        for i in range(len(images)):
            yield {
                'img_input': images[i],
                'feat_input': features[i]
            }, labels[i]
    return gen

def main():
    # 1. 加载数据
    print("加载数据中...")
    x_train_img, x_train_feat, y_train = load_data('train')
    x_test_img, x_test_feat, y_test = load_data('test')

    feat_dim = x_train_feat.shape[1]
    print(f"检测到特征维度: {feat_dim}")

    # 2. 构建 Dataset 对象 (改用 Generator 模式解决 6.88GiB 显存报错)
    output_signature = (
        {
            'img_input': tf.TensorSpec(shape=(cfg.IMG_SIZE, cfg.IMG_SIZE, 3), dtype=tf.float32),
            'feat_input': tf.TensorSpec(shape=(feat_dim,), dtype=tf.float32)
        },
        tf.TensorSpec(shape=(), dtype=tf.int32)
    )

    train_ds = tf.data.Dataset.from_generator(
        get_generator(x_train_img, x_train_feat, y_train),
        output_signature=output_signature
    ).shuffle(6000).batch(cfg.BATCH_SIZE).prefetch(tf.data.AUTOTUNE)

    test_ds = tf.data.Dataset.from_generator(
        get_generator(x_test_img, x_test_feat, y_test),
        output_signature=output_signature
    ).batch(cfg.BATCH_SIZE).prefetch(tf.data.AUTOTUNE)

    # 3. 模型构建
    model = build_transfer_model(feat_dim)

    optimizer = tf.keras.optimizers.Adam(learning_rate=cfg.LEARNING_RATE)

    model.compile(
        optimizer=optimizer,
        loss='sparse_categorical_crossentropy',
        metrics=['accuracy']
    )

    # --- 新增：加载备份权重逻辑 ---
    backup_path = r'D:\competent\DeepFER\checkpoints\best_rafdb.keras'

    if os.path.exists(backup_path):
        print(f"检测到历史权重，正在从 {backup_path} 加载进行全量微调...")
        # 使用 load_weights 加载权重
        # 如果模型结构完全一致，这会将 79.2% 的状态恢复
        model.load_weights(backup_path)
        print("权重加载成功！")
    else:
        print(f"警告：未找到备份文件 {backup_path}，请确认路径是否正确！")
        # 如果找不到权重，建议直接停止，防止再次重练
        import sys
        sys.exit(1)

    # 4. 回调
    checkpoint_path = os.path.join(cfg.CHECKPOINT_DIR, 'best_rafdb.keras')
    if not os.path.exists(cfg.CHECKPOINT_DIR):
        os.makedirs(cfg.CHECKPOINT_DIR)

    callbacks = [
        tf.keras.callbacks.ModelCheckpoint(checkpoint_path, save_best_only=True, monitor='val_accuracy'),
        tf.keras.callbacks.EarlyStopping(patience=10, restore_best_weights=True, monitor='val_accuracy'),
        tf.keras.callbacks.ReduceLROnPlateau(factor=0.5, patience=5, monitor='val_loss')
    ]

    # 5. 训练
    print("开始训练...")
    model.fit(
        train_ds,
        epochs=cfg.EPOCHS,
        validation_data=test_ds,
        callbacks=callbacks
    )

if __name__ == "__main__":
    main()