"""
MSST音轨分离模块 - 修复版 v4.1
修复内容:
1. 使用正确的脚本路径 scripts/msst_cli.py
2. 正确处理输出目录和文件查找
3. 输出文件夹以歌曲名命名
4. 分离后自动压缩音轨（1:10比例，使用高质量AAC/OGG编码）
"""

import os
import sys
import shutil
import subprocess
import json
from pathlib import Path
from PyQt6.QtCore import QThread, pyqtSignal


class AudioCompressor:
    """
    音频压缩工具类
    
    使用FFmpeg进行高质量压缩，目标约1:10压缩比
    优先使用AAC编码（兼容性好），备选OGG Vorbis
    """
    
    @staticmethod
    def find_ffmpeg() -> str:
        """查找FFmpeg可执行文件"""
        # 检查系统PATH
        ffmpeg_names = ['ffmpeg', 'ffmpeg.exe']
        
        for name in ffmpeg_names:
            # 检查PATH
            result = shutil.which(name)
            if result:
                return result
        
        # 检查常见安装位置
        common_paths = [
            r"C:\ffmpeg\bin\ffmpeg.exe",
            r"C:\Program Files\ffmpeg\bin\ffmpeg.exe",
            r"C:\Program Files (x86)\ffmpeg\bin\ffmpeg.exe",
            "/usr/bin/ffmpeg",
            "/usr/local/bin/ffmpeg",
            "/opt/homebrew/bin/ffmpeg",
        ]
        
        for path in common_paths:
            if os.path.exists(path):
                return path
        
        return ""
    
    @staticmethod
    def compress_audio(input_path: str, output_path: str = None, 
                       target_bitrate: str = "64k",
                       progress_callback=None) -> tuple:
        """
        压缩音频文件
        
        Args:
            input_path: 输入文件路径
            output_path: 输出文件路径（默认替换原文件）
            target_bitrate: 目标比特率（默认64k，约1:10压缩）
            progress_callback: 进度回调函数
            
        Returns:
            (success: bool, message: str, output_path: str)
        """
        ffmpeg = AudioCompressor.find_ffmpeg()
        if not ffmpeg:
            return False, "未找到FFmpeg，请安装FFmpeg后重试", ""
        
        if not os.path.exists(input_path):
            return False, f"输入文件不存在: {input_path}", ""
        
        # 确定输出路径和格式
        if output_path is None:
            # 默认输出为m4a格式（AAC编码，兼容性好）
            base = os.path.splitext(input_path)[0]
            output_path = base + ".m4a"
        
        output_ext = os.path.splitext(output_path)[1].lower()
        
        # 临时输出文件
        temp_output = output_path + ".temp" + output_ext
        
        try:
            # 构建FFmpeg命令
            # 使用高质量设置，保持尽可能好的音质
            if output_ext in ['.m4a', '.aac']:
                # AAC编码 - 使用VBR模式获得更好音质
                cmd = [
                    ffmpeg, '-y', '-i', input_path,
                    '-c:a', 'aac',
                    '-b:a', target_bitrate,
                    '-vbr', '4',  # VBR质量级别 (1-5, 4是高质量)
                    '-movflags', '+faststart',  # 优化网络播放
                    temp_output
                ]
            elif output_ext == '.ogg':
                # OGG Vorbis编码
                cmd = [
                    ffmpeg, '-y', '-i', input_path,
                    '-c:a', 'libvorbis',
                    '-b:a', target_bitrate,
                    '-q:a', '4',  # 质量级别
                    temp_output
                ]
            elif output_ext == '.opus':
                # Opus编码 - 最高效的编码器
                cmd = [
                    ffmpeg, '-y', '-i', input_path,
                    '-c:a', 'libopus',
                    '-b:a', target_bitrate,
                    '-vbr', 'on',
                    '-compression_level', '10',
                    temp_output
                ]
            else:
                # MP3编码
                cmd = [
                    ffmpeg, '-y', '-i', input_path,
                    '-c:a', 'libmp3lame',
                    '-b:a', target_bitrate,
                    '-q:a', '2',  # VBR质量
                    temp_output
                ]
            
            if progress_callback:
                progress_callback(f"正在压缩: {os.path.basename(input_path)}")
            
            # 执行压缩
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding='utf-8',
                errors='replace'
            )
            
            if result.returncode != 0:
                # 清理临时文件
                if os.path.exists(temp_output):
                    os.remove(temp_output)
                return False, f"压缩失败: {result.stderr[-500:]}", ""
            
            # 检查输出文件
            if not os.path.exists(temp_output):
                return False, "压缩后的文件未生成", ""
            
            # 获取文件大小信息
            original_size = os.path.getsize(input_path)
            compressed_size = os.path.getsize(temp_output)
            ratio = original_size / compressed_size if compressed_size > 0 else 0
            
            # 移动临时文件到最终位置
            if os.path.exists(output_path):
                os.remove(output_path)
            shutil.move(temp_output, output_path)
            
            # 删除原始WAV文件（如果输出路径不同）
            if input_path != output_path and os.path.exists(input_path):
                os.remove(input_path)
            
            return True, f"压缩完成 (比例 1:{ratio:.1f})", output_path
            
        except Exception as e:
            # 清理临时文件
            if os.path.exists(temp_output):
                os.remove(temp_output)
            return False, f"压缩出错: {str(e)}", ""
    
    @staticmethod
    def compress_directory(directory: str, target_bitrate: str = "64k",
                          output_format: str = "m4a",
                          progress_callback=None) -> tuple:
        """
        压缩目录中的所有音频文件
        
        Args:
            directory: 目录路径
            target_bitrate: 目标比特率
            output_format: 输出格式
            progress_callback: 进度回调
            
        Returns:
            (success: bool, message: str, compressed_files: list)
        """
        if not os.path.exists(directory):
            return False, "目录不存在", []
        
        # 查找需要压缩的文件（WAV和FLAC通常需要压缩）
        source_formats = ('.wav', '.flac', '.aiff', '.aif')
        files_to_compress = []
        
        for f in os.listdir(directory):
            if f.lower().endswith(source_formats):
                files_to_compress.append(os.path.join(directory, f))
        
        if not files_to_compress:
            return True, "没有需要压缩的文件", []
        
        compressed_files = []
        failed_files = []
        total = len(files_to_compress)
        
        for i, filepath in enumerate(files_to_compress):
            if progress_callback:
                progress_callback(f"压缩中 ({i+1}/{total}): {os.path.basename(filepath)}")
            
            # 确定输出路径
            base = os.path.splitext(filepath)[0]
            output_path = base + "." + output_format.lstrip('.')
            
            success, msg, out_path = AudioCompressor.compress_audio(
                filepath, output_path, target_bitrate, progress_callback
            )
            
            if success:
                compressed_files.append(out_path)
            else:
                failed_files.append((filepath, msg))
        
        if failed_files:
            failed_msg = "\n".join([f"{os.path.basename(f)}: {m}" for f, m in failed_files])
            return False, f"部分文件压缩失败:\n{failed_msg}", compressed_files
        
        return True, f"成功压缩 {len(compressed_files)} 个文件", compressed_files


class MSSTSeparatorThread(QThread):
    """MSST分离线程 - 通过subprocess调用MSST推理脚本"""
    progress = pyqtSignal(str)
    finished = pyqtSignal(bool, str, str)
    
    def __init__(self, msst_path: str, input_file: str, output_dir: str, 
                 model_type: str, config_path: str, model_path: str, output_format: str = 'wav',
                 python_path: str = '', compress_output: bool = True,
                 compress_bitrate: str = '64k', compress_format: str = 'm4a'):
        super().__init__()
        self.msst_path = msst_path
        self.input_file = input_file
        self.output_dir = output_dir
        self.model_type = model_type
        self.config_path = config_path
        self.model_path = model_path
        self.output_format = output_format
        self.python_path = python_path  # MSST使用的Python解释器路径
        self._process = None
        # 压缩选项
        self.compress_output = compress_output
        self.compress_bitrate = compress_bitrate
        self.compress_format = compress_format
        
    def run(self):
        try:
            self.progress.emit("正在准备分离...")
            
            # 创建输出目录（以歌曲名命名）
            os.makedirs(self.output_dir, exist_ok=True)
            
            # 创建临时输入目录
            temp_input = os.path.join(os.path.dirname(self.output_dir), "_temp_input")
            os.makedirs(temp_input, exist_ok=True)
            
            # 复制输入文件
            input_basename = os.path.basename(self.input_file)
            temp_file = os.path.join(temp_input, input_basename)
            shutil.copy2(self.input_file, temp_file)
            
            self.progress.emit("正在调用MSST进行分离...")
            
            # 尝试多个可能的脚本路径
            possible_scripts = [
                os.path.join(self.msst_path, "scripts", "msst_cli.py"),
                os.path.join(self.msst_path, "inference", "msst_infer.py"),
                os.path.join(self.msst_path, "msst_cli.py"),
            ]
            
            inference_script = None
            for script in possible_scripts:
                if os.path.exists(script):
                    inference_script = script
                    break
                    
            if not inference_script:
                self.finished.emit(False, f"找不到MSST推理脚本。\n已尝试: {', '.join(possible_scripts)}", "")
                shutil.rmtree(temp_input, ignore_errors=True)
                return
            
            # 确定Python解释器
            python_exe = self.python_path if self.python_path else self._find_python()
            
            # 构建命令 - 根据文档使用正确的参数
            cmd = [
                python_exe,
                inference_script,
                "--model_type", self.model_type,
                "--config_path", self.config_path,
                "--model_path", self.model_path,
                "-i", temp_input,  # 使用 -i 或 --input_folder
                "-o", self.output_dir,  # 使用 -o 或 --output_folder
                "--output_format", self.output_format,
            ]
            
            self.progress.emit(f"执行命令: {os.path.basename(inference_script)}...")
            
            # 设置环境变量，确保能找到MSST的模块
            env = os.environ.copy()
            # 将MSST根目录添加到PYTHONPATH
            pythonpath = env.get('PYTHONPATH', '')
            if pythonpath:
                env['PYTHONPATH'] = f"{self.msst_path}{os.pathsep}{pythonpath}"
            else:
                env['PYTHONPATH'] = self.msst_path
            
            # 使用subprocess运行
            self._process = subprocess.Popen(
                cmd,
                cwd=self.msst_path,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding='utf-8',
                errors='replace'
            )
            
            # 读取输出
            output_lines = []
            while True:
                line = self._process.stdout.readline()
                if not line and self._process.poll() is not None:
                    break
                if line:
                    line = line.strip()
                    output_lines.append(line)
                    # 解析进度信息
                    if "Processing" in line or "处理" in line or "Separating" in line:
                        self.progress.emit(line)
                    elif "%" in line:
                        self.progress.emit(line)
                    elif "Loading" in line or "加载" in line:
                        self.progress.emit(line)
                        
            return_code = self._process.wait()
            
            # 清理临时目录
            shutil.rmtree(temp_input, ignore_errors=True)
            
            # 检查输出文件 - 可能在输出目录或其子目录中
            output_files = self._find_output_files(self.output_dir)
            
            if output_files:
                # 如果文件在子目录中，移动到主输出目录
                self._move_files_to_output_dir(output_files, self.output_dir)
                final_files = self._find_output_files(self.output_dir, recursive=False)
                
                # 压缩输出文件（如果启用）
                if self.compress_output and final_files:
                    self.progress.emit("正在压缩音轨文件...")
                    
                    success, msg, compressed = AudioCompressor.compress_directory(
                        self.output_dir,
                        target_bitrate=self.compress_bitrate,
                        output_format=self.compress_format,
                        progress_callback=lambda m: self.progress.emit(m)
                    )
                    
                    if success:
                        # 重新获取压缩后的文件列表
                        final_files = self._find_output_files(self.output_dir, recursive=False)
                        self.finished.emit(True, f"分离并压缩完成! 生成了 {len(final_files)} 个音轨", self.output_dir)
                    else:
                        # 压缩失败，但分离成功
                        self.finished.emit(True, f"分离完成，但压缩失败: {msg}\n生成了 {len(final_files)} 个音轨", self.output_dir)
                else:
                    self.finished.emit(True, f"分离完成! 生成了 {len(final_files)} 个音轨", self.output_dir)
            elif return_code == 0:
                # 进程成功但没找到文件，可能文件名或路径问题
                self.finished.emit(False, f"分离进程完成但未找到输出文件\n\n输出目录: {self.output_dir}\n\n请检查MSST配置是否正确", "")
            else:
                error_output = '\n'.join(output_lines[-15:])  # 取最后15行作为错误信息
                self.finished.emit(False, f"分离失败 (返回码: {return_code})\n\n{error_output}", "")
                
        except FileNotFoundError as e:
            self.finished.emit(False, f"找不到Python解释器或脚本: {str(e)}\n\n请在MSST设置中配置正确的Python路径", "")
        except Exception as e:
            import traceback
            self.finished.emit(False, f"分离过程出错: {str(e)}\n\n{traceback.format_exc()}", "")
            
    def _find_output_files(self, directory: str, recursive: bool = True) -> list:
        """查找输出的音频文件"""
        audio_extensions = ('.wav', '.flac', '.mp3', '.m4a', '.aac', '.ogg', '.opus')
        output_files = []
        
        if recursive:
            for root, dirs, files in os.walk(directory):
                for f in files:
                    if f.lower().endswith(audio_extensions) and not f.startswith('_'):
                        output_files.append(os.path.join(root, f))
        else:
            for f in os.listdir(directory):
                filepath = os.path.join(directory, f)
                if os.path.isfile(filepath) and f.lower().endswith(audio_extensions) and not f.startswith('_'):
                    output_files.append(filepath)
                    
        return output_files
        
    def _move_files_to_output_dir(self, files: list, output_dir: str):
        """将子目录中的文件移动到输出目录"""
        for filepath in files:
            if os.path.dirname(filepath) != output_dir:
                dest = os.path.join(output_dir, os.path.basename(filepath))
                # 如果目标已存在，添加序号
                if os.path.exists(dest):
                    base, ext = os.path.splitext(dest)
                    counter = 1
                    while os.path.exists(f"{base}_{counter}{ext}"):
                        counter += 1
                    dest = f"{base}_{counter}{ext}"
                try:
                    shutil.move(filepath, dest)
                except Exception:
                    pass
                    
        # 清理空的子目录
        for root, dirs, files in os.walk(output_dir, topdown=False):
            for d in dirs:
                dir_path = os.path.join(root, d)
                try:
                    if not os.listdir(dir_path):
                        os.rmdir(dir_path)
                except Exception:
                    pass
            
    def _find_python(self) -> str:
        """查找MSST可能使用的Python解释器"""
        # 检查MSST目录下是否有venv或conda环境
        possible_paths = [
            # Windows venv
            os.path.join(self.msst_path, "venv", "Scripts", "python.exe"),
            os.path.join(self.msst_path, ".venv", "Scripts", "python.exe"),
            os.path.join(self.msst_path, "env", "Scripts", "python.exe"),
            # Linux/Mac venv
            os.path.join(self.msst_path, "venv", "bin", "python"),
            os.path.join(self.msst_path, ".venv", "bin", "python"),
            os.path.join(self.msst_path, "env", "bin", "python"),
            # conda env (常见名称)
            os.path.join(self.msst_path, "conda_env", "python.exe"),
        ]
        
        for path in possible_paths:
            if os.path.exists(path):
                return path
                
        # 默认使用系统Python
        return sys.executable
        
    def stop(self):
        """停止分离进程"""
        if self._process and self._process.poll() is None:
            self._process.terminate()


def check_msst_environment(msst_path: str) -> tuple:
    """检查MSST环境是否正确配置"""
    if not msst_path:
        return False, "未设置MSST路径"
        
    if not os.path.exists(msst_path):
        return False, f"MSST路径不存在: {msst_path}"
    
    # 检查必要目录
    required_items = ["configs", "pretrain"]
    
    missing = []
    for item in required_items:
        if not os.path.exists(os.path.join(msst_path, item)):
            missing.append(item)
            
    if missing:
        return False, f"MSST目录缺少必要组件: {', '.join(missing)}"
        
    # 检查推理脚本 - 尝试多个可能的路径
    script_paths = [
        os.path.join(msst_path, "scripts", "msst_cli.py"),
        os.path.join(msst_path, "inference", "msst_infer.py"),
    ]
    
    script_found = False
    for script in script_paths:
        if os.path.exists(script):
            script_found = True
            break
            
    if not script_found:
        return False, "找不到推理脚本: scripts/msst_cli.py 或 inference/msst_infer.py"
        
    return True, "MSST环境配置正确"
