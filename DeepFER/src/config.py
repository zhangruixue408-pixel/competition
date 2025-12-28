import os


class Config:
    # 路径
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    RAW_DATA_DIR = os.path.join(BASE_DIR, 'data', 'raf-db')
    PROCESSED_DIR = os.path.join(BASE_DIR, 'data', 'processed')
    CHECKPOINT_DIR = os.path.join(BASE_DIR, 'checkpoints')
    LANDMARK_PATH = os.path.join(BASE_DIR, 'data', 'shape_predictor_68_face_landmarks.dat')

    # 图像参数
    IMG_SIZE = 224  # 提升到 224 以适配 ResNet50
    NUM_CLASSES = 7
    # RAF-DB 的标签通常是 1:Surprise, 2:Fear, 3:Disgust, 4:Happy, 5:Sad, 6:Angry, 7:Neutral
    # 我们需要重映射到 0-6，且顺序要固定！
    CLASS_MAP = {1: 5, 2: 2, 3: 1, 4: 3, 5: 4, 6: 0, 7: 6}
    # 最终映射为: ['Angry', 'Disgust', 'Fear', 'Happy', 'Sad', 'Surprise', 'Neutral']
    EMOTIONS = ['Angry', 'Disgust', 'Fear', 'Happy', 'Sad', 'Surprise', 'Neutral']

    # 特征维度 (HOG + Landmarks)
    # 136 (Landmarks) + HOG (根据 224 图计算)
    # 下面的 features.py 会自动计算这个维度，这里不需要死记

    # 训练参数
    BATCH_SIZE = 16  # 224图片较大，显存小的话改成 16
    EPOCHS = 40  # RAF-DB 收敛较快
    LEARNING_RATE = 1e-6  # 迁移学习需要更小的学习率


cfg = Config()