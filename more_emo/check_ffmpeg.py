# check_ffmpeg.py
import subprocess
import sys

def check_ffmpeg():
    try:
        result = subprocess.run(
            ['ffmpeg', '-version'],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            print("✅ ffmpeg 已安装")
            # 提取版本信息
            lines = result.stdout.split('\n')
            if lines:
                print(f"版本: {lines[0]}")
            return True
        else:
            print("❌ ffmpeg 安装有问题")
            return False
    except FileNotFoundError:
        print("❌ ffmpeg 未找到，请安装 ffmpeg 并添加到 PATH")
        print("安装方法:")
        print("1. 下载: https://github.com/BtbN/FFmpeg-Builds/releases")
        print("2. 解压到 C:\\ffmpeg")
        print("3. 添加 C:\\ffmpeg\\bin 到系统 PATH")
        print("4. 重启命令行")
        return False
    except Exception as e:
        print(f"❌ 检查 ffmpeg 时出错: {e}")
        return False

if __name__ == "__main__":
    if check_ffmpeg():
        print("\n✅ ffmpeg 可用，可以继续测试")
        sys.exit(0)
    else:
        print("\n❌ 请先安装 ffmpeg")
        sys.exit(1)