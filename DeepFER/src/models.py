import tensorflow as tf
from tensorflow.keras import layers, models, regularizers
from src.config import cfg

def build_transfer_model(feat_dim):
    # --- 输入层 ---
    img_input = layers.Input(shape=(cfg.IMG_SIZE, cfg.IMG_SIZE, 3), name='img_input')
    feat_input = layers.Input(shape=(feat_dim,), name='feat_input')

    # --- 1. 数据增强层 (只有在训练阶段会生效) ---
    # 这一步是解决过拟合的关键，让模型无法死记硬背
    data_aug = tf.keras.Sequential([
        layers.RandomFlip("horizontal"),        # 随机水平翻转
        layers.RandomRotation(0.1),             # 随机旋转 10 度
        layers.RandomContrast(0.1),             # 随机对比度
        layers.RandomTranslation(0.1, 0.1),     # 随机平移
    ])(img_input)

    # --- 2. 视觉流 (ResNet50V2) ---
    base_model = tf.keras.applications.ResNet50V2(
        include_top=False,
        weights='imagenet',
        input_tensor=data_aug  # 将增强后的图片输入模型
    )
    base_model.trainable = True
    # 这是一个高级技巧：微调时保持 BN 层冻结，能显著提高稳定性
    for layer in base_model.layers:
        if isinstance(layer, layers.BatchNormalization):
            layer.trainable = False

    x = base_model.output
    x = layers.GlobalAveragePooling2D()(x)
    x = layers.Dense(512, activation='relu', kernel_regularizer=regularizers.l2(0.01))(x) # 加入L2正则
    x = layers.Dropout(0.6)(x)  # 提高 Dropout

    # --- 3. 几何特征流 ---
    y = layers.Dense(512, activation='relu', kernel_regularizer=regularizers.l2(0.01))(feat_input)
    y = layers.BatchNormalization()(y)
    y = layers.Dropout(0.6)(y)

    # --- 4. 融合层 ---
    combined = layers.Concatenate()([x, y])
    combined = layers.BatchNormalization()(combined)  # 加入这一行：平衡两个流的特征分布
    z = layers.Dense(256, activation='relu', kernel_regularizer=regularizers.l2(0.01))(combined)
    z = layers.Dropout(0.5)(z)

    # --- 输出层 ---
    # 针对混合精度，最后一层通常保持 float32 增加稳定性
    outputs = layers.Dense(cfg.NUM_CLASSES, activation='softmax', dtype='float32')(z)

    model = models.Model(inputs=[img_input, feat_input], outputs=outputs)
    return model