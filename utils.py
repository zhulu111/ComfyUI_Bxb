import base64
import sys
import time
import urllib.request
import subprocess
import os
import platform
import tarfile
import zipfile
from functools import lru_cache
import shutil
from PIL import Image, PngImagePlugin
import json
from tqdm import tqdm
import io
from pathlib import Path
import ssl
import mimetypes
import imghdr
import piexif
from .public import args, find_project_root, generate_md5_uid_timestamp, determine_file_type, find_project_custiom_nodes_path
import folder_paths
from concurrent.futures import ThreadPoolExecutor
input_directory = folder_paths.get_input_directory()
os.makedirs(input_directory, exist_ok=True)
save_input_directory = input_directory + '/temp'
os.makedirs(save_input_directory, exist_ok=True)
FFMPEG_URLS = {
    "amd64-static": "https://tt-1254127940.cos.ap-guangzhou.myqcloud.com/ffmpeg/ffmpeg-release-amd64-static.tar.xz",
    "i686-static": "https://tt-1254127940.cos.ap-guangzhou.myqcloud.com/ffmpeg/ffmpeg-release-i686-static.tar.xz",
    "arm64-static": "https://tt-1254127940.cos.ap-guangzhou.myqcloud.com/ffmpeg/ffmpeg-release-arm64-static.tar.xz",
    "armhf-static": "https://tt-1254127940.cos.ap-guangzhou.myqcloud.com/ffmpeg/ffmpeg-release-armhf-static.tar.xz",
    "armel-static": "https://tt-1254127940.cos.ap-guangzhou.myqcloud.com/ffmpeg/ffmpeg-release-armel-static.tar.xz",
    "osx64": "https://tt-1254127940.cos.ap-guangzhou.myqcloud.com/ffmpeg/ffmpeg-116599-g43cde54fc1.zip",
    "win64-full": "https://tt-1254127940.cos.ap-guangzhou.myqcloud.com/ffmpeg/ffmpeg-release-essentials.zip"
}
ssl._create_default_https_context = ssl._create_unverified_context
ffmpeg_path_exe = ''
ffprobe_exe_path = ''
temp_path = find_project_custiom_nodes_path() + 'ComfyUI_Bxb/temp_bxb/'
try:
    resample_filter = Image.Resampling.LANCZOS
except AttributeError:
    resample_filter = Image.LANCZOS
def file_to_base64(file_path):
    mime_type, _ = mimetypes.guess_type(file_path)
    if mime_type is None:
        raise ValueError("无法识别的文件类型")
    with open(file_path, "rb") as file:
        base64_encoded = base64.b64encode(file.read()).decode('utf-8')
    base64_prefix = f"data:{mime_type};base64,"
    return base64_prefix + base64_encoded
def compress_image(input_image_path, output_image_path=None, target_width=None, quality=85):
    
    img = Image.open(input_image_path)
    if target_width is None:
        target_width = img.size[0]
    width_percent = target_width / float(img.size[0])
    target_height = int((float(img.size[1]) * float(width_percent)))
    img_resized = img.resize((target_width, target_height), Image.LANCZOS)
    if output_image_path is None:
        output_image_path = input_image_path
    if output_image_path == input_image_path:
        os.remove(input_image_path)
    img_resized.save(output_image_path, quality=quality, optimize=True)
def cut_and_compress_video(input_video_path, output_video_path=None, target_width=None, duration=None):
    
    probe_command = [
        ffmpeg_path_exe, '-v', 'error', '-select_streams', 'v:0', '-show_entries',
        'stream=width,height', '-of', 'csv=p=0:s=x', input_video_path
    ]
    result = subprocess.run(probe_command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    original_width, original_height = map(int, result.stdout.strip().split('x'))
    if target_width is None:
        target_width = original_width
    width_ratio = target_width / float(original_width)
    target_height = int(original_height * width_ratio)
    if output_video_path is None:
        output_video_path = input_video_path
    command = [
        ffmpeg_path_exe,
        '-i', input_video_path,
        '-vf', f'scale={target_width}:{target_height}',
        '-r', '24',
        '-c:v', 'libx264',
        '-preset', 'medium',
        '-crf', '28',
        '-c:a', 'aac',
        '-b:a', '128k',
        '-strict', 'experimental',
        '-y',
        output_video_path
    ]
    if duration is not None:
        command.insert(1, '-t')
        command.insert(2, str(duration))
    subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
def get_platform():
    architecture = platform.machine()
    if sys.platform.startswith("linux"):
        if architecture == "x86_64":
            return "amd64-static"
        elif architecture == "i686":
            return "i686-static"
        elif architecture == "aarch64":
            return "arm64-static"
        elif architecture == "armv7l":
            return "armhf-static"
        elif architecture == "armel":
            return "armel-static"
    elif sys.platform.startswith("darwin"):
        return "osx64"
    elif sys.platform.startswith("win"):
        return "win64-full"
    else:
        raise RuntimeError("Unsupported platform")
def download_ffmpeg(target_dir):
    def reporthook(block_num, block_size, total_size):
        if reporthook.tbar is None:
            reporthook.tbar = tqdm(total=total_size, unit='B', unit_scale=True)
        downloaded = block_num * block_size
        if downloaded < total_size:
            reporthook.tbar.update(block_size)
        else:
            reporthook.tbar.close()
            reporthook.tbar = None
    reporthook.tbar = None
    plat = get_platform()
    url = FFMPEG_URLS.get(plat)
    if not url:
        raise RuntimeError(f"不支持的平台或配置: {plat}")
    target_dir = Path(target_dir).resolve()
    target_dir.mkdir(parents=True, exist_ok=True)
    file_extension = url.split('.')[-1]
    archive_path = target_dir / f"ffmpeg-{plat}.{file_extension}"
    print(f"正在下载 FFmpeg for {plat}...")
    no_proxy_handler = urllib.request.ProxyHandler({})
    opener = urllib.request.build_opener(no_proxy_handler)
    with opener.open(url) as response:
        with open(archive_path, 'wb') as out_file:
            block_size = 8192
            total_size = int(response.headers.get('Content-Length', 0))
            reporthook(0, block_size, total_size)
            while True:
                buffer = response.read(block_size)
                if not buffer:
                    break
                out_file.write(buffer)
                reporthook(len(buffer) // block_size, block_size, total_size)
    print(f"正在解压 FFmpeg...")
    extracted_dir = target_dir / "ffmpeg"
    if file_extension == "zip":
        with zipfile.ZipFile(archive_path, 'r') as zip_ref:
            zip_ref.extractall(extracted_dir)
    elif file_extension == "xz":
        with tarfile.open(archive_path, 'r:xz') as tar_ref:
            tar_ref.extractall(extracted_dir)
    ffmpeg_exe = find_ffmpeg_executable(extracted_dir)
    os.remove(archive_path)
    if not ffmpeg_exe or not ffmpeg_exe.exists():
        raise RuntimeError(f"从 {archive_path} 提取 FFmpeg 可执行文件失败")
    return str(ffmpeg_exe)
@lru_cache()
def find_ffmpeg_executable(search_dir):
    
    if not os.path.exists(search_dir):
        return None
    os.chmod(search_dir, 0o755)
    for root, dirs, files in os.walk(search_dir):
        for file in files:
            if file.lower() == "ffmpeg.exe" or file.lower() == "ffmpeg":
                return Path(root) / file
    return None
@lru_cache()
def find_ffprobe_executable(search_dir):
    
    for root, dirs, files in os.walk(search_dir):
        for file in files:
            if file.lower() == "ffprobe.exe" or file.lower() == "ffprobe":
                return Path(root) / file
    return None
@lru_cache()
def get_ffmpeg_executable():
    global ffmpeg_path_exe, ffprobe_exe_path
    target_dir = find_project_custiom_nodes_path() + 'ComfyUI_Bxb/tools/'
    ffmpeg_exe = find_ffmpeg_executable(target_dir + "/ffmpeg")
    if ffmpeg_exe and ffmpeg_exe.exists() and is_valid_exe(ffmpeg_exe):
        ffmpeg_path_exe = str(ffmpeg_exe)
        ffprobe_exe = find_ffprobe_executable(target_dir + "/ffmpeg")
        ffprobe_exe_path = str(ffprobe_exe)
        os.chmod(ffprobe_exe_path, 0o755)
        return str(ffmpeg_exe)
    remove_target_dir = target_dir + "/ffmpeg"
    if os.path.exists(remove_target_dir):
        shutil.rmtree(remove_target_dir)
    exe = download_ffmpeg(target_dir)
    if exe and os.path.isfile(exe) and is_valid_exe(exe):
        ffmpeg_path_exe = exe
        ffprobe_exe = find_ffprobe_executable(target_dir + "/ffmpeg")
        ffprobe_exe_path = str(ffprobe_exe)
        os.chmod(ffprobe_exe_path, 0o755)
        return exe
    raise RuntimeError("FFmpeg not found or is invalid.")
def is_valid_exe(exe):
    
    try:
        os.chmod(exe, 0o755)
        result = subprocess.run([exe, '-version'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return result.returncode == 0
    except Exception:
        return False
from io import BytesIO
def get_image_dimensions(input_file, custom_data=None):
    with Image.open(input_file) as img:
        width, height = img.size
        img_format = img.format
        if not custom_data or (img_format != 'PNG' and img_format != 'JPEG'):
            file_size_bytes = os.path.getsize(input_file)
            file_size_mb = file_size_bytes / (1024 * 1024)
            return width, height, file_size_mb
        img_byte_arr = BytesIO()
        if img_format == 'PNG':
            meta = PngImagePlugin.PngInfo()
            for key, value in custom_data.items():
                if isinstance(value, bytes):
                    value = base64.b64encode(value).decode('utf-8')
                meta.add_text(key, value)
            img.save(img_byte_arr, format="PNG", pnginfo=meta)
        elif img_format == 'JPEG':
            img = img.convert("RGB")
            exif_dict = {"0th": {}, "Exif": {}, "GPS": {}, "1st": {}, "thumbnail": None}
            for key, value in custom_data.items():
                exif_dict["0th"][piexif.ImageIFD.Make] = str(value)
            exif_bytes = piexif.dump(exif_dict)
            img.save(img_byte_arr, format="JPEG", exif=exif_bytes)
        img_byte_arr.seek(0)
        image_bytes = img_byte_arr.getvalue()
        with open(input_file, "wb") as f:
            f.write(image_bytes)
        file_size_bytes = len(image_bytes)
        file_size_mb = file_size_bytes / (1024 * 1024)
    return width, height, file_size_mb
def get_video_dimensions(input_file):
    command = [
        ffprobe_exe_path,
        '-v', 'error',
        '-select_streams', 'v:0',
        '-show_entries', 'stream=width,height',
        '-of', 'json',
        input_file
    ]
    result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    result_json = json.loads(result.stdout)
    width = result_json['streams'][0]['width']
    height = result_json['streams'][0]['height']
    file_size_bytes = os.path.getsize(input_file)
    file_size_mb = file_size_bytes / (1024 * 1024)
    return width, height, file_size_mb
def cut_video(input_file, start_seconds, end_seconds, output_file, width, height, fps=24, threads=4):
    
    duration = end_seconds - start_seconds
    if duration <= 0:
        raise ValueError("结束时间必须大于开始时间")
    scale_filter = f'scale={width}:{height}:force_original_aspect_ratio=increase'
    crop_filter = f'crop={width}:{height}'
    filter_complex = f'{scale_filter},{crop_filter}'
    command = [
        ffmpeg_path_exe,
        '-ss', str(start_seconds),
        '-i', input_file,
        '-t', str(duration),
        '-r', str(fps),
        '-vf', filter_complex,
        '-c:v', 'libx264',
        '-c:a', 'aac',
        '-threads', str(threads),
        '-strict', 'experimental',
        '-y',
        output_file
    ]
    subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    return duration
def loop_video_to_duration(input_file, output_file, target_duration):
    
    command = [
        ffmpeg_path_exe,
        '-stream_loop', '-1',
        '-i', input_file,
        '-t', str(target_duration),
        '-c:v', 'libx264',
        '-c:a', 'aac',
        '-threads', '8',
        '-y',
        output_file
    ]
    subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
def merge_videos_horizontally(input_file1, input_file2, output_file='temp_frames'):
    
    command = [
        ffmpeg_path_exe,
        '-i', input_file1,
        '-i', input_file2,
        '-filter_complex', '[0:v][1:v]hstack=inputs=2[v]',
        '-map', '[v]',
        '-c:v', 'libx264',
        '-threads', '8',
        '-y',
        output_file
    ]
    subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
def get_file_count_in_directory():
    directory = Path(temp_path)
    if not directory.exists():
        directory.mkdir(parents=True, exist_ok=True)
    file_count = len([file for file in directory.iterdir() if file.is_file()])
    return file_count
def resize_and_crop_image(image_path, output_path, width, height):
    
    command = [
        ffmpeg_path_exe,
        '-i', str(image_path),
        '-vf', f"scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height}",
        '-q:v', '2',
        str(output_path)
    ]
    try:
        subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    except subprocess.CalledProcessError as e:
        print(f"Error during resizing and cropping image: {e}")
def process_image(input_image_path_left=None, input_image_path_right=None, output_image_path="output.png",
                  canvas_size=(800, 600), overlay_image_path=None):
    canvas = Image.new('RGBA', canvas_size, (0, 0, 0, 0))
    half_width = canvas_size[0] // 2
    target_height = canvas_size[1]
    if input_image_path_left:
        img_left = Image.open(input_image_path_left).convert("RGBA")
        img_width, img_height = img_left.size
        scale = max(half_width / img_width, target_height / img_height)
        new_size = (int(img_width * scale), int(img_height * scale))
        img_resized = img_left.resize(new_size, resample_filter)
        img_cropped = img_resized.crop((
            (img_resized.width - half_width) // 2,
            (img_resized.height - target_height) // 2,
            (img_resized.width + half_width) // 2,
            (img_resized.height + target_height) // 2
        ))
        canvas.paste(img_cropped, (0, 0), img_cropped)
    if input_image_path_right:
        img_right = Image.open(input_image_path_right).convert("RGBA")
        img_width, img_height = img_right.size
        scale = max(half_width / img_width, target_height / img_height)
        new_size = (int(img_width * scale), int(img_height * scale))
        img_resized = img_right.resize(new_size, resample_filter)
        img_cropped = img_resized.crop((
            (img_resized.width - half_width) // 2,
            (img_resized.height - target_height) // 2,
            (img_resized.width + half_width) // 2,
            (img_resized.height + target_height) // 2
        ))
        canvas.paste(img_cropped, (half_width, 0), img_cropped)
    if overlay_image_path and os.path.exists(overlay_image_path):
        overlay_img = Image.open(overlay_image_path).convert("RGBA")
        overlay_scale = min(canvas_size[0] / 2 / overlay_img.width, canvas_size[1] / 2 / overlay_img.height)
        overlay_new_size = (int(overlay_img.width * overlay_scale), int(overlay_img.height * overlay_scale))
        if input_image_path_left is not None and input_image_path_right is not None and os.path.exists(input_image_path_left) and os.path.exists(input_image_path_right):
            overlay_new_size = (int(canvas_size[0] / 15), int(canvas_size[0] / 15))
        overlay_img_resized = overlay_img.resize(overlay_new_size, resample_filter)
        overlay_x = (canvas_size[0] - overlay_new_size[0]) // 2
        overlay_y = (canvas_size[1] - overlay_new_size[1]) // 2
        canvas.paste(overlay_img_resized, (overlay_x, overlay_y), overlay_img_resized)
    canvas.save(output_image_path, format='PNG', optimize=True)
def resize_and_crop(image, target_width, target_height):
    
    scale = max(target_width / image.width, target_height / image.height)
    new_size = (int(image.width * scale), int(image.height * scale))
    resized_image = image.resize(new_size, resample_filter)
    left = (resized_image.width - target_width) // 2
    top = (resized_image.height - target_height) // 2
    right = (resized_image.width + target_width) // 2
    bottom = (resized_image.height + target_height) // 2
    cropped_image = resized_image.crop((left, top, right, bottom))
    return cropped_image
def process_and_merge_image_video(image_file, video_file, output_file, overlay_image, side='left', target_width=330, target_height=480,
                                  start_seconds=0, end_seconds=None, fps=24):
    
    temp_black_background = ''
    if not image_file:
        img = Image.new('RGBA', (target_width, target_height), (0, 0, 0, 255))
        temp_black_background = temp_path + generate_md5_uid_timestamp(
            'temp_black_background') + 'temp_black_background.png'
        img.save(temp_black_background)
        image_file = temp_black_background
    image = Image.open(image_file).convert("RGBA")
    image_resized = resize_and_crop(image, target_width, target_height)
    video_resized_png = temp_path + generate_md5_uid_timestamp(str(time.process_time())) + 'resized_video.png'
    image_resized.save(video_resized_png)
    video_file_temp = ''
    if end_seconds is not None:
        video_file_temp = temp_path + generate_md5_uid_timestamp(str(time.process_time())) + 'cut_video.mp4'
        cut_video(video_file, start_seconds, end_seconds, video_file_temp, target_width, target_height, fps)
        video_file = video_file_temp
    scale_filter = f'scale={target_width}:{target_height}:force_original_aspect_ratio=increase'
    crop_filter = f'crop={target_width}:{target_height}'
    filter_complex = f'{scale_filter},{crop_filter}'
    overlay_new_width = int(target_width * 2 / 15)
    overlay_new_height = int(target_width * 2 / 15)
    overlay_x = (target_width * 2 - overlay_new_width) // 2
    overlay_y = (target_height - overlay_new_height) // 2
    if side == 'left':
        filter_complex = (
            f"[0:v]{scale_filter},{crop_filter}[vid];"
            f"[1:v]scale={target_width}:{target_height}[img];"
            f"[img][vid]hstack=inputs=2[base];"
            f"[2:v]scale={overlay_new_width}:{overlay_new_height}[ovrl];"
            f"[base][ovrl]overlay={overlay_x}:{overlay_y}[v]"
        )
    else:
        filter_complex = (
            f"[0:v]{scale_filter},{crop_filter}[vid];"
            f"[1:v]scale={target_width}:{target_height}[img];"
            f"[vid][img]hstack=inputs=2[base];"
            f"[2:v]scale={overlay_new_width}:{overlay_new_height}[ovrl];"
            f"[base][ovrl]overlay={overlay_x}:{overlay_y}[v]"
        )
    command = [
        ffmpeg_path_exe,
        '-i', video_file,
        '-i', video_resized_png,
        '-i', 'pipe:0',
        '-filter_complex', filter_complex,
        '-map', '[v]',
        '-c:v', 'libx264',
        '-pix_fmt', 'yuv420p',
        '-threads', '4',
        '-an',
        '-y',
        output_file
    ]
    with open(overlay_image, 'rb') as overlay_img_file:
        subprocess.run(command, stdin=overlay_img_file, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    os.remove(video_resized_png)
    if temp_black_background:
        os.remove(temp_black_background)
    if video_file_temp:
        os.remove(video_file_temp)
def process_and_merge_videos(input_file1, input_file2, start_seconds1, end_seconds1, start_seconds2, end_seconds2,
                             output_file, overlay_image, fps=24):
    global CANVAS_MAX_HEIGHT, CANVAS_MAX_WIDTH
    video_width1, video_height1, video_size = get_video_dimensions(input_file2)
    get_file_count_in_directory()
    cut1 = temp_path + generate_md5_uid_timestamp('cut1.mp4') + 'cut1.mp4'
    cut2 = temp_path + generate_md5_uid_timestamp('cut1.mp4') + 'cut2.mp4'
    cut1_looped = temp_path + generate_md5_uid_timestamp('cut1.mp4') + 'cut1_looped.mp4'
    cut2_looped = temp_path + generate_md5_uid_timestamp('cut1.mp4') + 'cut2_looped.mp4'
    max_width = CANVAS_MAX_WIDTH / 2
    max_height = CANVAS_MAX_HEIGHT
    max_width = video_width1
    max_height = video_height1
    duration1 = cut_video(input_file1, start_seconds1, end_seconds1, cut1, max_width, max_height, fps)
    duration2 = cut_video(input_file2, start_seconds2, end_seconds2, cut2, max_width, max_height, fps)
    max_duration = max(duration1, duration2)
    if duration1 < max_duration:
        loop_video_to_duration(cut1, cut1_looped, max_duration)
        video1_file = cut1_looped
    else:
        video1_file = cut1
    if duration2 < max_duration:
        loop_video_to_duration(cut2, cut2_looped, max_duration)
        video2_file = cut2_looped
    else:
        video2_file = cut2
    overlay_new_width = int(max_width * 2 / 15)
    overlay_new_height = int(max_width * 2 / 15)
    overlay_x = (max_width * 2 - overlay_new_width) // 2
    overlay_y = (max_height - overlay_new_height) // 2
    process_videos_with_overlay(video1_file, video2_file, overlay_image, output_file,
                                overlay_new_width=overlay_new_width,
                                overlay_new_height=overlay_new_height,
                                overlay_x=overlay_x,
                                overlay_y=overlay_y,
                                )
    if os.path.exists(cut1):
        os.remove(cut1)
    if os.path.exists(cut2):
        os.remove(cut2)
    if os.path.exists(cut1_looped):
        os.remove(cut1_looped)
    if os.path.exists(cut2_looped):
        os.remove(cut2_looped)
def process_videos_with_overlay(input_file1, input_file2, overlay_image, output_file,
                                overlay_new_width=100, overlay_new_height=100,
                                overlay_x=0, overlay_y=0, fps=24):
    
    command = [
        ffmpeg_path_exe,
        '-i', input_file1,
        '-i', input_file2,
        '-i', overlay_image,
        '-filter_complex',
        f"[0:v][1:v]hstack=inputs=2[base];"
        f"[2:v]scale={overlay_new_width}:{overlay_new_height}[ovrl];"
        f"[base][ovrl]overlay={overlay_x}:{overlay_y}",
        '-c:v', 'libx264',
        '-pix_fmt', 'yuv420p',
        '-threads', '8',
        '-y',
        output_file
    ]
    try:
        subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    except subprocess.CalledProcessError as e:
        print(f"FFmpeg 命令执行失败: {e.stderr.decode()}")
        raise
def apply_overlay_to_video(video_file, overlay_image_file, output_file, file_num=1):
    
    video_width, video_height, size_mb = get_video_dimensions(video_file)
    overlay_image = Image.open(overlay_image_file).convert("RGBA")
    overlay_ratio = overlay_image.width / overlay_image.height
    if file_num == 1:
        if video_width < video_height:
            overlay_new_width = video_width // 2
            overlay_new_height = int(overlay_new_width / overlay_ratio)
        else:
            overlay_new_height = video_height // 2
            overlay_new_width = int(overlay_new_height * overlay_ratio)
    else:
        overlay_new_width = int(video_width / 15)
        overlay_new_height = int(video_width / 15)
    overlay_resized = overlay_image.resize((overlay_new_width, overlay_new_height), resample_filter)
    img_byte_arr = io.BytesIO()
    overlay_resized.save(img_byte_arr, format='PNG')
    img_byte_arr = img_byte_arr.getvalue()
    overlay_x = (video_width - overlay_new_width) // 2
    overlay_y = (video_height - overlay_new_height) // 2
    command = [
        ffmpeg_path_exe,
        '-i', video_file,
        '-i', 'pipe:0',
        '-filter_complex',
        f'[1:v]scale={overlay_new_width}:{overlay_new_height}[ovrl];[0:v][ovrl]overlay={overlay_x}:{overlay_y}',
        '-c:v', 'libx264',
        '-pix_fmt', 'yuv420p',
        '-y',
        output_file
    ]
    process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout, stderr = process.communicate(input=img_byte_arr)
    if process.returncode != 0:
        raise Exception(f"FFmpeg 命令执行失败: {stderr.decode()}")
def is_image(file_path):
    
    if imghdr.what(file_path):
        return True
    mime_type, _ = mimetypes.guess_type(file_path)
    if mime_type and mime_type.startswith('image'):
        return mime_type
    return False
def is_video(file_path):
    
    mime_type, _ = mimetypes.guess_type(file_path)
    if mime_type and mime_type.startswith('video'):
        return mime_type
    try:
        command = [
            ffmpeg_path_exe,
            '-v', 'error',
            '-select_streams', 'v:0',
            '-show_entries', 'stream=codec_name',
            '-of', 'csv=p=0',
            '-i', file_path
        ]
        result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        codec_name = result.stdout.strip()
        if codec_name:
            mime_types = {
                'h264': 'video/mp4',
                'hevc': 'video/mp4',
                'vp8': 'video/webm',
                'vp9': 'video/webm',
                'av1': 'video/mp4',
                'mpeg4': 'video/mp4',
                'theora': 'video/ogg',
                'wmv3': 'video/x-ms-wmv',
                'vp6f': 'video/x-flv',
            }
            return mime_types.get(codec_name, 'video/unknown')
    except FileNotFoundError:
        print(f"{ffmpeg_path_exe} not found, unable to confirm if the file is a video.")
    return False
CANVAS_MAX_WIDTH = 1000
CANVAS_MAX_HEIGHT = 1000
END_SECONDS = 3
def optimize_dimensions(w1, h1, w2, h2):
    
    def adjust(value):
        return value - (value % 4)
    half_width = min(w2, CANVAS_MAX_WIDTH // 2)
    height = int(half_width * h2 / w2)
    return adjust(half_width * 2), adjust(height)
def process_file(file_path, side, target_width, target_height):
    
    file_info = {
        'file_type': '',
        'mime_type': '',
        'width': 0,
        'height': 0,
        'base_64': ''
    }
    file_mime_type, file_type = determine_file_type(file_path)
    file_info['file_type'] = file_type
    file_info['mime_type'] = file_mime_type
    if file_type == 'image':
        width, height, size_mb = get_image_dimensions(file_path)
        if size_mb > 5:
            compress_image(file_path, target_width=target_width)
            width, height, _ = get_image_dimensions(file_path)
        file_info['width'] = width
        file_info['height'] = height
        file_info['base_64'] = file_to_base64(file_path)
        return file_path, file_info
    elif file_type == 'video':
        width, height, size_mb = get_video_dimensions(file_path)
        if size_mb > 20:
            cut_and_compress_video(file_path, target_width=target_width, duration=5)
            width, height, _ = get_video_dimensions(file_path)
        file_info['width'] = width
        file_info['height'] = height
        file_info['base_64'] = file_to_base64(file_path)
        return file_path, file_info
    else:
        raise ValueError(f"Unsupported file type for {side} side.")
def do_zhutu(file_left='', file_right='', overlay_path=''):
    
    if not file_left and not file_right:
        return {'error': '请上传两张图片或两张视频', 'code': 1}
    out_put_name = generate_md5_uid_timestamp(overlay_path)
    out_put_png = out_put_name + '.png'
    out_put_mp4 = out_put_name + '.mp4'
    out_put_mp4_temp = out_put_name + 'temp.mp4'
    out_put_name_mp4_temp = folder_paths.get_input_directory() + '/' + out_put_mp4_temp
    out_put_name_mp4 = folder_paths.get_input_directory() + '/' + out_put_mp4
    out_put_name_png = folder_paths.get_input_directory() + '/' + out_put_png
    base_size = {}
    with ThreadPoolExecutor() as executor:
        futures = {}
        if file_left:
            futures['left'] = executor.submit(process_file, file_left, 'left', CANVAS_MAX_WIDTH // 2, CANVAS_MAX_HEIGHT)
        if file_right:
            futures['right'] = executor.submit(process_file, file_right, 'right', CANVAS_MAX_WIDTH // 2, CANVAS_MAX_HEIGHT)
        for side, future in futures.items():
            try:
                file_path, file_info = future.result()
                base_size[side] = file_info
            except Exception as e:
                return {'error': str(e), 'code': 1}
    if 'left' in base_size and 'right' in base_size:
        canvas_width, canvas_height = optimize_dimensions(
            base_size['left']['width'], base_size['left']['height'],
            base_size['right']['width'], base_size['right']['height']
        )
    else:
        canvas_width, canvas_height = CANVAS_MAX_WIDTH, CANVAS_MAX_HEIGHT
    try:
        if 'left' in base_size and 'right' in base_size:
            if base_size['left']['file_type'] == 'image' and base_size['right']['file_type'] == 'image':
                process_image(
                    input_image_path_left=file_left,
                    input_image_path_right=file_right,
                    output_image_path=out_put_name_png,
                    canvas_size=(canvas_width, canvas_height),
                    overlay_image_path=overlay_path
                )
                result_type = 'image'
            elif base_size['left']['file_type'] == 'video' and base_size['right']['file_type'] == 'video':
                process_and_merge_videos(
                    file_left, file_right, 0, END_SECONDS, 0, END_SECONDS,
                    output_file=out_put_name_mp4,
                    overlay_image=overlay_path
                )
                result_type = 'video'
            else:
                if base_size['left']['file_type'] == 'video':
                    process_and_merge_image_video(
                        file_right, file_left, out_put_name_mp4,
                        overlay_path,
                        side='right', target_width=canvas_width // 2, target_height=canvas_height,
                        start_seconds=0, end_seconds=END_SECONDS, fps=24
                    )
                else:
                    process_and_merge_image_video(
                        file_left, file_right, out_put_name_mp4,
                        overlay_path,
                        side='left', target_width=canvas_width // 2, target_height=canvas_height,
                        start_seconds=0, end_seconds=END_SECONDS, fps=24
                    )
                result_type = 'video'
        else:
            if 'left' in base_size:
                single_file = file_left
                side = 'left'
                file_info = base_size['left']
            else:
                single_file = file_right
                side = 'right'
                file_info = base_size['right']
            if file_info['file_type'] == 'image':
                process_image(
                    **{f"input_image_path_{side}": single_file},
                    output_image_path=out_put_name_png,
                    canvas_size=(canvas_width, canvas_height),
                    overlay_image_path=overlay_path
                )
                result_type = 'image'
            else:
                process_and_merge_image_video(
                    None, single_file, out_put_name_mp4,
                    overlay_path,
                    side='right' if side == 'left' else 'left',
                    target_width=canvas_width // 2, target_height=canvas_height,
                    start_seconds=0, end_seconds=END_SECONDS, fps=24
                )
                result_type = 'video'
        if result_type == 'image':
            result_data = file_to_base64(out_put_name_png)
            filename = out_put_png
        else:
            result_data = file_to_base64(out_put_name_mp4)
            filename = out_put_mp4
        return {
            'data': result_data,
            'filename': filename,
            'code': 0,
            'type': result_type,
            'size': {'width': canvas_width, 'height': canvas_height},
            'base_size': base_size
        }
    finally:
        if os.path.exists(out_put_name_mp4_temp):
            os.remove(out_put_name_mp4_temp)
def get_video_duration(video_path):
    result = subprocess.run(
        [ffprobe_exe_path, '-v', 'error', '-show_entries', 'format=duration',
         '-of', 'default=noprint_wrappers=1:nokey=1', video_path],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    return float(result.stdout.strip())
def extract_frames(video_path, num_frames=3):
    duration = get_video_duration(video_path)
    frame_times = []
    if duration < 1.0:
        frame_times = [0]
    else:
        frame_times = [(duration / (num_frames + 1)) * (i + 1) for i in range(num_frames)]
    frame_contents = []
    for time in frame_times:
        result = subprocess.run(
            [ffmpeg_path_exe, '-ss', str(time), '-i', video_path, '-vframes', '1',
             '-f', 'image2pipe', '-vcodec', 'png', '-'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        frame_contents.append(result.stdout)
    return frame_contents
