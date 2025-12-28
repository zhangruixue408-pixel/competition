# speech_service.py - 使用 ffmpeg-python
import os
import time
import tempfile
import subprocess
from xfyunsdkspeech.iat_client import IatClient
from dotenv import load_dotenv
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SpeechService:
    def __init__(self):
        load_dotenv(override=True)
        self.client = IatClient(
            app_id=os.getenv('APP_ID'),
            api_key=os.getenv('API_KEY'),
            api_secret=os.getenv('API_SECRET'),
            dwa="wpgs"
        )

    def check_ffmpeg_installed(self):
        """检查 ffmpeg 是否安装"""
        try:
            subprocess.run(['ffmpeg', '-version'],
                           capture_output=True,
                           check=True,
                           timeout=5)
            return True
        except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
            return False

    def convert_audio_with_ffmpeg_python(self, input_path):
        """使用 ffmpeg-python 库转换音频"""
        print(f"DEBUG: 使用 ffmpeg-python 转换音频: {input_path}")

        # 检查 ffmpeg 是否安装
        if not self.check_ffmpeg_installed():
            raise Exception(
                "ffmpeg 未安装。请安装 ffmpeg: Windows用户可以从 https://ffmpeg.org/download.html 下载并添加到系统PATH")

        # 检查文件
        if not os.path.exists(input_path):
            raise Exception(f"文件不存在: {input_path}")

        print(f"DEBUG: 输入文件大小: {os.path.getsize(input_path)} 字节")

        # 创建临时 PCM 文件
        temp_pcm = tempfile.NamedTemporaryFile(suffix='.pcm', delete=False)
        temp_pcm.close()
        pcm_path = temp_pcm.name

        print(f"DEBUG: 临时 PCM 文件路径: {pcm_path}")

        try:
            # 方法1：先尝试使用 ffmpeg-python
            try:
                import ffmpeg

                print("DEBUG: 尝试使用 ffmpeg-python 直接转换...")
                process = (
                    ffmpeg
                    .input(input_path)
                    .output(
                        pcm_path,
                        acodec='pcm_s16le',
                        ac=1,  # 单声道
                        ar=16000,  # 16k 采样率
                        f='s16le'  # 输出格式
                    )
                    .overwrite_output()
                    .run_async(pipe_stdout=True, pipe_stderr=True, quiet=True)
                )

                # 等待转换完成，设置超时
                stdout, stderr = process.communicate(timeout=10)

                if process.returncode != 0:
                    error_msg = stderr.decode('utf-8',
                                              errors='ignore') if stderr else f"ffmpeg 返回错误码: {process.returncode}"
                    print(f"DEBUG: ffmpeg-python 转换失败: {error_msg}")
                    raise Exception(f"ffmpeg-python 转换失败")

            except ImportError:
                print("DEBUG: ffmpeg-python 未安装，使用子进程方式")
                raise Exception("ffmpeg-python 未安装")
            except Exception as e:
                print(f"DEBUG: ffmpeg-python 转换异常: {e}")
                # 继续尝试方法2

            # 方法2：使用子进程直接调用 ffmpeg（更可靠）
            print("DEBUG: 使用子进程调用 ffmpeg...")
            cmd = [
                'ffmpeg',
                '-i', input_path,
                '-acodec', 'pcm_s16le',
                '-ac', '1',
                '-ar', '16000',
                '-f', 's16le',
                '-y',  # 覆盖输出文件
                pcm_path
            ]

            print(f"DEBUG: 执行命令: {' '.join(cmd)}")

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode != 0:
                print(f"ERROR: ffmpeg 命令失败: {result.stderr}")
                raise Exception(f"ffmpeg 转换失败: {result.stderr[:200]}")

            # 检查输出文件
            if os.path.exists(pcm_path):
                file_size = os.path.getsize(pcm_path)
                print(f"DEBUG: PCM 文件创建成功，大小: {file_size} 字节")

                if file_size == 0:
                    raise Exception("PCM 文件为空")

                with open(pcm_path, 'rb') as f:
                    pcm_data = f.read()

                print(f"DEBUG: 转换成功，PCM 数据大小: {len(pcm_data)} 字节")
                return pcm_data
            else:
                raise Exception("PCM 文件未创建")

        except subprocess.TimeoutExpired:
            raise Exception("ffmpeg 转换超时")
        except Exception as e:
            print(f"ERROR: 转换过程中出现错误: {e}")
            import traceback
            traceback.print_exc()
            raise
        finally:
            # 清理临时文件
            if os.path.exists(pcm_path):
                print(f"DEBUG: 清理临时文件: {pcm_path}")
                try:
                    os.unlink(pcm_path)
                except Exception as e:
                    print(f"WARNING: 清理临时文件失败: {e}")

    def recognize(self, audio_file_path) -> str:
        if not self.client:
            raise Exception("语音服务未正确初始化配置")

        print(f"DEBUG: 开始识别音频文件: {audio_file_path}")

        # 检查文件
        if not os.path.exists(audio_file_path):
            return f"文件不存在: {audio_file_path}"

        if not os.access(audio_file_path, os.R_OK):
            return f"文件不可读: {audio_file_path}"

        # 转换音频为 PCM 格式
        try:
            pcm_data = self.convert_audio_with_ffmpeg_python(audio_file_path)
        except Exception as e:
            print(f"ERROR: 音频转换失败: {e}")
            return f"音频转换失败: {str(e)}"

        if not pcm_data or len(pcm_data) == 0:
            return "音频转换后为空数据"

        # 创建一个简单的类文件对象
        class FileLikeObject:
            def __init__(self, pcm_data):
                self.data = pcm_data
                self.position = 0
                self.chunk_size = 1280  # 40ms数据块

            def read(self, size=-1):
                # 忽略传入的size参数，使用固定chunk_size
                # 并添加延迟模拟实时流
                time.sleep(0.04)

                if self.position >= len(self.data):
                    return b''

                end_pos = self.position + self.chunk_size
                if end_pos > len(self.data):
                    end_pos = len(self.data)

                chunk = self.data[self.position:end_pos]
                self.position = end_pos
                return chunk

            def close(self):
                self.data = b''
                self.position = 0

        # 使用 PCM 数据创建文件对象
        file_obj = FileLikeObject(pcm_data)

        try:
            print(f"DEBUG: 开始向讯飞发送音频流...")
            full_text = ""
            has_result = False

            for chunk in self.client.stream(file_obj):
                if isinstance(chunk, dict) and 'result' in chunk and 'ws' in chunk['result']:
                    words = chunk['result']['ws']
                    for word_item in words:
                        for char_info in word_item['cw']:
                            w = char_info.get('w', '')
                            full_text += w
                            if w:
                                print(f"识别: {w}", end=' ')
                                has_result = True

                if isinstance(chunk, dict) and chunk.get('result', {}).get('ls', False):
                    print("\nDEBUG: 收到最终结果标志")
                    break

            print(f"\nDEBUG: 识别完成，最终结果: {full_text}")
            return full_text if full_text else "未能识别到有效语音"

        except Exception as e:
            print(f"ERROR: 识别失败: {e}")
            import traceback
            traceback.print_exc()
            return f"识别失败: {str(e)}"
        finally:
            file_obj.close()