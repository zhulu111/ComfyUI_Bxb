import json
import re
import time
from datetime import datetime
from .install import *
from .mime import add_mime_types
add_mime_types()
from .utils import get_ffmpeg_executable, do_zhutu, get_video_dimensions, get_image_dimensions, extract_frames
import concurrent.futures
import asyncio
import aiohttp
import aiohttp_cors
import server
import folder_paths
from aiohttp import web
from collections import deque
import inspect
import os
import uuid
import hashlib
import platform
import stat
import nodes
import urllib.request
import numpy as np
import shutil
from .wss import thread_run, update_worker_flow, UploadManager
from .public import get_port_from_cmdline, set_token, is_aspect_ratio_within_limit, get_version, \
    set_openid, get_openid, find_project_root, args, get_base_url, get_filenames, get_output, get_workflow, \
    find_project_bxb, loca_download_image, delete_workflow, read_json_file, determine_file_type, print_exception_in_chinese, remove_query_parameters, combine_images, get_upload_url, send_binary_data, async_download_image, find_project_custiom_nodes_path
ffmpeg_exe_path = get_ffmpeg_executable()
temp_path = find_project_custiom_nodes_path() + 'ComfyUI_Bxb/temp_bxb/'
if os.path.exists(temp_path):
    shutil.rmtree(temp_path)
os.makedirs(temp_path, exist_ok=True)
import threading
from PIL import Image
input_directory = folder_paths.get_input_directory()
os.makedirs(input_directory, exist_ok=True)
save_input_directory = input_directory + '/temp'
os.makedirs(save_input_directory, exist_ok=True)
load_class = 'bxbSwitch'
def get_time():
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
def get_mac_address():
    mac = uuid.getnode()
    return ':'.join(('%012X' % mac)[i:i + 2] for i in range(0, 12, 2))
def generate_unique_subdomain(mac_address, port):
    unique_key = f"{mac_address}:{port}"
    hash_object = hashlib.sha256(unique_key.encode())
    subdomain = hash_object.hexdigest()[:12]
    return subdomain
def set_executable_permission(file_path):
    try:
        st = os.stat(file_path)
        os.chmod(file_path, st.st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        print(f"Execution permissions set on {file_path}")
    except Exception as e:
        print(f"Failed to set execution permissions: {e}")
def download_file(url, dest_path):
    try:
        with urllib.request.urlopen(url) as response, open(dest_path, 'wb') as out_file:
            data = response.read()
            out_file.write(data)
    except Exception as e:
        print(f"Failed to download the file: {e}")
PLUGIN_DIR = os.path.dirname(os.path.abspath(__file__))
SD_CLIENT_DIR = os.path.join(PLUGIN_DIR, "sdc")
SDC_EXECUTABLE = os.path.join(SD_CLIENT_DIR, "sdc" if platform.system() != "Windows" else "sdc.exe")
INI_FILE = os.path.join(SD_CLIENT_DIR, "sdc.toml")
LOG_FILE = os.path.join(SD_CLIENT_DIR, "sdc.log")
class SDClient:
    RED = "\033[91m"
    RESET = "\033[0m"
    def __init__(self, local_port, subdomain):
        self.local_port = local_port
        self.server_addr = "suidao.9syun.com"
        self.server_port = "7000"
        self.token = "my_secure_token"
        self.subdomain = subdomain
        self.sd_process = None
        self.connected = False
        self.monitoring_thread = None
        self.stop_monitoring = False
    def create_sdc_ini(self, file_path, subdomain):
        config_content = f"""
[common]
server_addr = "{self.server_addr}"
server_port = {self.server_port}
token = "{self.token}"
login_fail_exit = false

[{subdomain}]
type = "http"
local_port = {self.local_port}
subdomain = "{subdomain}"
remote_port = 0
log_file = "{LOG_FILE}"
log_level = "info"
"""
        with open(file_path, "w") as config_file:
            config_file.write(config_content)
    def tail_log(self, filename, num_lines=20):
        try:
            with open(filename, "r") as file:
                return deque(file, num_lines)
        except FileNotFoundError:
            return deque()
    def check_sd_log_for_status(self):
        success_keywords = ["login to server success", "start proxy success"]
        failure_keywords = ["connect to server error", "read tcp", "session shutdown"]
        connection_attempt_pattern = re.compile(r"try to connect to server")
        latest_lines = self.tail_log(LOG_FILE, 20)
        connection_attempt_index = None
        for index, line in enumerate(latest_lines):
            if connection_attempt_pattern.search(line):
                connection_attempt_index = index
        if connection_attempt_index is not None and connection_attempt_index + 1 < len(latest_lines):
            next_line = latest_lines[connection_attempt_index + 1]
            for keyword in success_keywords:
                if keyword in next_line:
                    return "connected"
            return "disconnected"
        return "disconnected"
    def check_and_download_executable(self):
        if platform.system() != "Windows":
            if not os.path.exists(SDC_EXECUTABLE):
                download_file("https://tt-1254127940.file.myqcloud.com/tech_huise/66/qita/sdc", SDC_EXECUTABLE)
                set_executable_permission(SDC_EXECUTABLE)
    def start(self):
        self.create_sdc_ini(INI_FILE, self.subdomain)
        open(LOG_FILE, "w").close()
        env1 = os.environ.copy()
        env1['http_proxy'] = ''
        env1['https_proxy'] = ''
        env1['no_proxy'] = '*'
        try:
            with open(LOG_FILE, "a") as log_file:
                self.sd_process = subprocess.Popen([SDC_EXECUTABLE, "-c", INI_FILE], stdout=log_file, stderr=log_file,
                                                   env=env1)
            print(f"SD client started with PID: {self.sd_process.pid}")
            self.stop_monitoring = False
            self.monitoring_thread = threading.Thread(target=self.monitor_connection_status, daemon=True)
            self.monitoring_thread.start()
        except FileNotFoundError:
            print(f"Error: '{SDC_EXECUTABLE}' not found。")
        except Exception as e:
            print(f"Error starting SD client: {e}")
    def monitor_connection_status(self):
        while not self.stop_monitoring:
            status = self.check_sd_log_for_status()
            if status == "connected":
                if not self.connected:
                    print(f"SD client successfully connected with PID: {self.sd_process.pid}")
                    self.connected = True
            else:
                if self.connected:
                    print(f"{self.RED}Waiting for SD client to connect...{self.RESET}")
                    self.connected = False
            time.sleep(1)
    def stop(self):
        if self.sd_process and self.sd_process.poll() is None:
            self.sd_process.terminate()
            self.sd_process.wait()
            print("SD client stopped。")
        else:
            print("SD client is not running。")
        self.connected = False
        self.stop_monitoring = True
    def is_connected(self):
        return self.connected
    def clear_log(self):
        if os.path.exists(LOG_FILE):
            open(LOG_FILE, "w").close()
            print("SD client log cleared。")
subdomain = ""
websocket = None
if platform.system() != "Darwin":
    local_port = get_port_from_cmdline()
    subdomain = generate_unique_subdomain(get_mac_address(), local_port)
    SDC_EXECUTABLE = os.path.join(SD_CLIENT_DIR, "sdc" if platform.system() != "Windows" else "sdc.exe")
    if os.path.exists(SDC_EXECUTABLE):
        sd_client = SDClient(local_port=local_port, subdomain=subdomain)
        sd_client.start()
thread_run()
def extract_and_verify_images(output):
    results = {}
    app_img_keys = []
    for key, node in output.items():
        if node["class_type"] == "sdBxb":
            inputs = node.get("inputs", {})
            for k, v in inputs.items():
                if k.startswith("app_img") and isinstance(v, list) and len(v) > 0:
                    app_img_keys.append((k, v[0]))
    err = 0
    err_msg = ''
    for app_img_key, img_key in app_img_keys:
        if str(img_key) in output:
            image_node = output[str(img_key)]
            image_path = image_node.get("inputs", {}).get("image")
            if image_path:
                if verify_image_exists(folder_paths.get_input_directory() + '/' + image_path):
                    results[app_img_key] = {"image_path": image_path, "status": "图片存在"}
                else:
                    err = err + 1
                    err_msg = err_msg + f"图片不存在: {app_img_key}\n"
            else:
                err = err + 1
                err_msg = err_msg + f"图片不存在: {app_img_key}\n"
        else:
            err = err + 1
            err_msg = err_msg + f"图片不存在: {app_img_key}\n"
    return {
        "results": results,
        "err": err,
        "err_msg": err_msg
    }
def verify_image_exists(path):
    if os.path.exists(path):
        valid_extensions = {".jpg", ".jpeg", ".png", ".gif"}
        ext = os.path.splitext(path)[1].lower()
        if ext in valid_extensions:
            return True
    return False
@server.PromptServer.instance.routes.post("/manager/tech_zhulu")
async def tech_zhulu(request):
    json_data = await request.json()
    if 'postData' in json_data and isinstance(json_data['postData'], dict):
        json_data['postData']['subdomain'] = subdomain
    connector = aiohttp.TCPConnector()
    async with aiohttp.ClientSession(connector=connector) as session:
        json_data['version'] = get_version()
        techsid = json_data.get('comfyui_tid', '')
        upload_url = get_base_url() + json_data['r'] + '&techsid=we7sid-' + techsid
        if json_data['r'] == 'comfyui.apiv2.upload':
            err_info = {
                "errno": 0,
                "message": "ERROR",
                "data": {
                    "data": {
                        "message": '该节点已废弃,请刷新浏览器后,点击屏幕右上角封装应用',
                        "code": 0,
                    }
                }
            }
            return web.Response(status=200, text=json.dumps(err_info))
            output = json_data['postData']['output']
            workflow = json_data['postData']['workflow']
            try:
                output_verify = extract_and_verify_images(output)
                if output_verify['err'] > 0:
                    err_info = {
                        "errno": 0,
                        "message": "ERROR",
                        "data": {
                            "data": {
                                "message": output_verify['err_msg'],
                                "code": 0,
                            }
                        }
                    }
                    return web.Response(status=200, text=json.dumps(err_info))
                json_data['postData'].pop('output')
                json_data['postData'].pop('workflow')
                form_data = aiohttp.FormData()
                form_data.add_field('json_data', json.dumps(json_data))
                if 'zhutus' in json_data['postData']:
                    for item in json_data['postData']['zhutus']:
                        with open(folder_paths.get_input_directory() + '/' + item, 'rb') as f:
                            file_content = f.read()
                        form_data.add_field('zhutus[]', file_content, filename=os.path.basename(item),
                                            content_type='application/octet-stream')
            except Exception as e:
                return web.Response(status=200, text=e)
            async with session.post(upload_url, data=form_data) as response:
                try:
                    response_result = await response.text()
                    result = json.loads(response_result)
                    if 'data' in result and isinstance(result['data'], dict):
                        if 'data' in result['data'] and isinstance(result['data']['data'], dict):
                            result_data = result['data']['data']
                            if techsid != '' and techsid != 'init' and result_data['code'] == 1:
                                await update_worker_flow(result_data['name'], output)
                                await update_worker_flow(result_data['name'], workflow, 'workflow/')
                        return web.Response(status=response.status, text=response_result)
                    else:
                        return web.Response(status=response.status, text=await response.text())
                except json.JSONDecodeError as e:
                    return web.Response(status=response.status, text=await response.text())
        else:
            async with session.post(upload_url, json=json_data) as resp:
                if resp.status == 200 and resp.headers.get('Content-Type') == 'application/json':
                    try:
                        other_api_data = await resp.json()
                        result = web.json_response(other_api_data)
                        return result
                    except aiohttp.ContentTypeError:
                        error_text = await resp.text()
                        return web.Response(text=error_text, status=400)
                if resp.status == 200 and resp.headers.get('Content-Type') == 'text/html; charset=utf-8':
                    try:
                        result = await resp.text()
                        result = json.loads(result)
                        return web.json_response(result)
                    except json.JSONDecodeError as e:
                        return web.Response(status=resp.status, text=await resp.text())
                else:
                    return web.Response(status=resp.status, text=await resp.text())
@server.PromptServer.instance.routes.post("/manager/auth")
async def auth(request):
    return web.json_response({'message': 'success', 'token': ''})
    pass
@server.PromptServer.instance.routes.post("/manager/get_seep")
async def get_seep(request):
    line_json = read_json_file('https://tt.9syun.com/seed.json')
    return web.json_response({'message': 'success', 'data': line_json})
@server.PromptServer.instance.routes.post("/manager/download_fileloadd")
async def download_fileloadd(request):
    json_data = await request.json()
    if (json_data['url']):
        filename = os.path.basename(json_data['url'])
        download_info = await loca_download_image(json_data['url'], filename, 1)
        if download_info['code']:
            file_new_name = download_info['filename']
            return web.Response(status=200, text=json.dumps({
                "code": 1,
                "msg": "文件下载成功",
                "data": {
                    "filename": file_new_name,
                    "subfolder": '',
                    "type": 'input'
                }
            }))
        return web.Response(status=500, text=json.dumps({
            "code": 0,
            "msg": "文件下载失败",
            "data": {
            }
        }))
    else:
        return web.Response(status=500, text=json.dumps({
            "code": 0,
            "msg": "文件下载失败",
            "data": {
            }
        }))
    pass
async def process_download_tasks(yu_load_images):
    
    loop = asyncio.get_event_loop()
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        download_tasks = []
        for image_info in yu_load_images:
            download_tasks.append(loop.run_in_executor(executor, async_download_image, image_info['left_image'], image_info['left_image'], 1))
            download_tasks.append(loop.run_in_executor(executor, async_download_image, image_info['right_image'], image_info['right_image'], 1))
        download_results = await asyncio.gather(*download_tasks)
        index = 0
        for image_info in yu_load_images:
            left_info = download_results[index]
            right_info = download_results[index + 1]
            index += 2
            if left_info['code']:
                image_info['left_image'] = {
                    "filename": left_info['filename'],
                    "subfolder": '',
                    "type": 'input'
                }
            else:
                image_info['left_image'] = ''
            if right_info['code']:
                image_info['right_image'] = {
                    "filename": right_info['filename'],
                    "subfolder": '',
                    "type": 'input'
                }
            else:
                image_info['right_image'] = ''
    return yu_load_images
def process_zhutu(image_info, base_image1, base_image2, base_image3):
    
    if image_info['left_image'] is not '':
        left_image = image_info['left_image'].get('filename', '')
    else:
        left_image = image_info['left_image']
    if image_info['right_image'] is not '':
        right_image = image_info['right_image'].get('filename', '')
    else:
        right_image = image_info['right_image']
    overlay_img = ''
    if left_image != '':
        left_image = folder_paths.get_input_directory() + '/' + left_image
        overlay_img = base_image1
    if right_image != '':
        right_image = folder_paths.get_input_directory() + '/' + right_image
        overlay_img = base_image2
    if left_image != '' and right_image != '':
        overlay_img = base_image3
    zhutu_info = do_zhutu(left_image, right_image, overlay_img)
    if zhutu_info['code'] == 0:
        image_info['result'] = {
            "code": 0,
            "msg": "成功",
            "data": zhutu_info['data'],
            "filename": zhutu_info['filename'],
            'type': zhutu_info['type'],
            'mime_type': 'image/png' if zhutu_info['type'] == 'image' else 'video/mp4',
            'size': zhutu_info['size'],
            'base_size': zhutu_info['base_size']
        }
        return image_info
    return  None
async def process_images_multithread(updated_images, base_image1, base_image2, base_image3):
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        loop = asyncio.get_event_loop()
        tasks = [
            loop.run_in_executor(
                executor,
                process_zhutu,
                image_info,
                base_image1,
                base_image2,
                base_image3
            )
            for image_info in updated_images
        ]
        results = await asyncio.gather(*tasks)
        updated_images = [result for result in results if result is not None]
        return updated_images
@server.PromptServer.instance.routes.post("/manager/download_fileloads")
async def download_fileloads(request):
    yu_load_images = await request.json()
    updated_images = await process_download_tasks(yu_load_images)
    base_image = find_project_bxb() + 'assets/image/bg-image.png'
    base_image1 = find_project_bxb() + 'assets/image/bg-image1.png'
    base_image2 = find_project_bxb() + 'assets/image/bg-image2.png'
    base_image3 = find_project_bxb() + 'assets/image/bg-image3.png'
    processed_images = await process_images_multithread(updated_images, base_image1, base_image2, base_image3)
    return web.Response(status=200, text=json.dumps({
        "code": 1,
        "msg": "文件下载成功",
        "data": processed_images
    }))
@server.PromptServer.instance.routes.post("/manager/image_serialize")
async def image_serialize(request):
    json_data = await request.json()
    out_put_directory = folder_paths.get_output_directory()
    base_serialized = 0
    for index, item in enumerate(json_data):
        if item['info']['subfolder'] != '':
            item['info']['filename'] = item['info']['subfolder'] + '/' + item['info']['filename']
        mine_type, file_type = determine_file_type(out_put_directory + '/' + item['info']['filename'])
        if file_type == 'video':
            width1, height1, size_mb = get_video_dimensions(out_put_directory + '/' + item['info']['filename'])
        else:
            width1, height1, size_mb = get_image_dimensions(out_put_directory + '/' + item['info']['filename'])
        item['width'] = width1
        item['height'] = height1
        item['size'] = size_mb
        item['file_type'] = file_type
        item['mine_type'] = mine_type
        base_serialized = base_serialized + size_mb
    return web.Response(status=200, text=json.dumps({
        "code": 0,
        "msg": "文件类型未知",
        "data": {
            "data": {
                "code": 0,
                "data": {
                    "base_serialized": round(float(base_serialized), 6),
                    "worker_list": json_data,
                    "total": len(json_data)
                },
                "message": "ok",
            }
        }
    }))
@server.PromptServer.instance.routes.post("/manager/save_work")
async def save_work(request):
    json_data = await request.json()
    if 'postData' in json_data and isinstance(json_data['postData'], dict):
        json_data['postData']['subdomain'] = subdomain
    timeout = aiohttp.ClientTimeout(total=60)
    connector = aiohttp.TCPConnector(use_dns_cache=False)
    async with aiohttp.ClientSession(timeout=timeout, connector=connector) as session:
        json_data['version'] = get_version()
        techsid = json_data.get('comfyui_tid', '')
        upload_url = get_base_url() + 'comfyui.apiv2.upload&techsid=we7sid-' + techsid
        output = json_data['postData']['output']
        workflow = json_data['postData']['workflow']
        json_data['postData'].pop('output')
        json_data['postData'].pop('workflow')
        json_data['postData']['auth'] = []
        post_uir_arr = []
        post_file_arr = []
        form_data = aiohttp.FormData()
        try:
            input_dir = folder_paths.get_input_directory()
            def get_full_filename(subfolder, filename):
                return os.path.join(subfolder, filename) if subfolder else filename
            if 'zhutus' in json_data['postData']:
                for item in json_data['postData']['zhutus']:
                    item['filename'] = get_full_filename(item.get('subfolder', ''), item['filename'])
                    with open(os.path.join(input_dir, item['filename']), 'rb') as f:
                        file_content = f.read()
                    form_data.add_field('zhutus[]', file_content, filename=os.path.basename(item['filename']),
                                        content_type='application/octet-stream')
            for index, item in enumerate(json_data['postData']['zhutu_data']):
                if item['url'] == '':
                    item_url_info = {}
                    item_url_file = {}
                    if int(item['upload_type']) == 1:
                        item['file']['filename'] = get_full_filename(item['file'].get('subfolder', ''), item['file']['filename'])
                        item_url_info = {
                            'url': item['mime_type'],
                            'file_type': item['file_type'],
                            'width': item['size_info']['width'],
                            'height': item['size_info']['height'],
                            'ratio': item['size_info']['height'] / item['size_info']['width'],
                            'upload_type': 1,
                            'urls': [],
                            'type': 'zhutu',
                            'index': index
                        }
                        item_url_file = {
                            'url': item['file']['filename'],
                            'upload_type': 1,
                            'urls': [],
                            'type': 'zhutu',
                            'index': index
                        }
                        if item['file_url']['right_image'] == '':
                            item['file_value']['right_image']['filename'] = get_full_filename(item['file_value']['right_image'].get('subfolder', ''), item['file_value']['right_image']['filename'])
                            right_mime_type = item['base_size']['right']['mime_type']
                            right_width = item['base_size']['right']['width']
                            right_height = item['base_size']['right']['height']
                            right_ratio = right_height / right_width
                            item_url_info['urls'].append({
                                'url': right_mime_type,
                                'width': right_width,
                                'height': right_height,
                                'ratio': right_ratio,
                                'type': 'right'
                            })
                            item_url_file['urls'].append({
                                'url': item['file_value']['right_image']['filename'],
                                'type': 'right'
                            })
                    if item['file_url']['left_image'] == '':
                        item['file_value']['left_image']['filename'] = get_full_filename(item['file_value']['left_image'].get('subfolder', ''), item['file_value']['left_image']['filename'])
                        left_mime_type = item['base_size']['left']['mime_type']
                        file_type = item['base_size']['left']['file_type']
                        left_width = item['base_size']['left']['width']
                        left_height = item['base_size']['left']['height']
                        left_ratio = left_height / left_width
                        if 'upload_type' in item_url_info:
                            item_url_info['urls'].append({
                                'url': left_mime_type,
                                'width': left_width,
                                'height': left_height,
                                'ratio': left_ratio,
                                'type': 'left'
                            })
                            item_url_file['urls'].append({
                                'url': item['file_value']['left_image']['filename'],
                                'type': 'left'
                            })
                        else:
                            item_url_info = {
                                'url': left_mime_type,
                                'file_type': file_type,
                                'width': left_width,
                                'height': left_height,
                                'ratio': left_ratio,
                                'upload_type': item['upload_type'],
                                'urls': [],
                                'type': 'zhutu',
                                'index': index
                            }
                            item_url_file = {
                                'url': item['file_value']['left_image']['filename'],
                                'upload_type': item['upload_type'],
                                'urls': [],
                                'type': 'zhutu',
                                'index': index
                            }
                    if 'upload_type' in item_url_info and item_url_info['file_type'] == 'video':
                        frame_contents = extract_frames(os.path.join(input_dir, item_url_file['url']))
                        for frame_content in frame_contents:
                            item_url_info['urls'].append({
                                'url': 'image/png',
                                'width': item_url_info['width'],
                                'height': item_url_info['height'],
                                'ratio': item_url_info['height'] / item_url_info['width'],
                                'type': 'frame'
                            })
                            item_url_file['urls'].append({
                                'url': frame_content,
                                'type': 'frame'
                            })
                    if 'upload_type' in item_url_info:
                        if not is_aspect_ratio_within_limit(item_url_info['width'], item_url_info['height']):
                            return web.Response(status=200, text=json.dumps({
                                "code": 0,
                                "msg": "文件类型未知",
                                "data": {
                                    "data": {
                                        "code": 0,
                                        "data": {
                                            'index': index,
                                            'type': 'zhutu_data',
                                        },
                                        "message": "文件长边不可超过短边4倍",
                                    }
                                }
                            }))
                        post_uir_arr.append(item_url_info)
                        post_file_arr.append(item_url_file)
            if 'check_output_item' in json_data['postData']:
                for index, item in enumerate(json_data['postData']['check_output_item']):
                    if (item['input_type'] in ['image', 'video']) and item['file_defult_value'] == 1 and item['default_value'] == '':
                        item['file_value']['filename'] = get_full_filename(item['file_value'].get('subfolder', ''), item['file_value']['filename'])
                        mine_type, file_type = determine_file_type(os.path.join(input_dir, item['file_value']['filename']))
                        if file_type == 'unknown':
                            return web.Response(status=200, text=json.dumps({
                                "code": 0,
                                "msg": "文件类型未知",
                                "data": {
                                    "data": {
                                        "code": 0,
                                        "message": "文件类型未知",
                                    }
                                }
                            }))
                        if file_type == 'video':
                            width1, height1, size_mb = get_video_dimensions(os.path.join(input_dir, item['file_value']['filename']))
                        else:
                            width1, height1, size_mb = get_image_dimensions(os.path.join(input_dir, item['file_value']['filename']))
                        if not is_aspect_ratio_within_limit(width1, height1):
                            return web.Response(status=200, text=json.dumps({
                                "code": 0,
                                "msg": "文件类型未知",
                                "data": {
                                    "data": {
                                        "code": 0,
                                        "data": {
                                            'index': index,
                                            'type': 'default_value',
                                        },
                                        "message": "文件长边不可超过短边4倍",
                                    }
                                }
                            }))
                        item_url_info = {
                            'url': mine_type,
                            'file_type': file_type,
                            'width': width1,
                            'height': height1,
                            'urls': [],
                            'ratio': height1 / width1,
                            'type': 'output',
                            'index': index
                        }
                        item_url_file = {
                            'url': item['file_value']['filename'],
                            'file_type': file_type,
                            'type': 'output',
                            'urls': [],
                            'index': index
                        }
                        if file_type == 'video':
                            frame_contents = extract_frames(os.path.join(input_dir, item['file_value']['filename']))
                            for frame_content in frame_contents:
                                item_url_info['urls'].append({
                                    'url': 'image/png',
                                    'width': width1,
                                    'height': height1,
                                    'ratio': height1 / width1,
                                    'type': 'frame'
                                })
                                item_url_file['urls'].append({
                                    'url': frame_content,
                                    'type': 'frame'
                                })
                        post_uir_arr.append(item_url_info)
                        post_file_arr.append(item_url_file)
        except Exception as e:
            print_exception_in_chinese(e)
            return web.Response(status=200, text=str(e))
        image_info_list = []
        if len(post_uir_arr) > 0:
            for index, item in enumerate(post_uir_arr):
                if 'file_type' in item and item['file_type'] == 'video':
                    for key, val in enumerate(item['urls']):
                        if val['type'] == 'frame':
                            image_info_list.append({
                                'type': 'binary',
                                'content': post_file_arr[index]['urls'][key]['url']
                            })
                else:
                    image_info_list.append({
                        'type': 'path',
                        'content': folder_paths.get_input_directory() + '/' + post_file_arr[index]['url']
                    })
            binary_data_list = combine_images(image_info_list)
            for binary_data in binary_data_list:
                post_uir_arr.append({
                    'url': 'image/png',
                    'file_type': 'image',
                    'width': '',
                    'height': '',
                    'ratio': 1,
                    'upload_type': 0,
                    'urls': [],
                    'type': 'auth',
                    'index': 0
                })
                post_file_arr.append({
                    'url': binary_data,
                    'upload_type': 0,
                    'urls': [],
                    'type': 'auth',
                    'index': 0
                })
            url_result = await get_upload_url(post_uir_arr, techsid, session)
            if url_result['errno'] == 41009:
                return web.Response(status=200, text=json.dumps(url_result))
            try:
                manager = UploadManager(session, url_result, post_file_arr, post_uir_arr, folder_paths.get_input_directory())
                manager.start_sync()
                json_arr, auth_arr, url_result_data = manager.get()
            except Exception as e:
                print_exception_in_chinese(e)
                return web.Response(status=200, text=json.dumps({
                    "code": 0,
                    "msg": "上传失败",
                    "data": {
                        "data": {
                            "code": 0,
                            "data": {
                            },
                            "message": "资源上传失败了,请重新上传,确保网络状态,如果使用了代理建议关闭代理上传",
                        }
                    }
                }))
            zhutu_data = json_data['postData']['zhutu_data']
            acs_list = url_result_data
            for index, item in enumerate(acs_list):
                if item['type'] == 'zhutu':
                    zhutu_data[item['index']]['url_frame'] = []
                    zhutu_data[item['index']]['url_ratio'] = item['ratio']
                    zhutu_data[item['index']]['url_type'] = item['file_type']
                    zhutu_data[item['index']]['url_fm'] = ''
                    if item['upload_type'] == 2:
                        zhutu_data[item['index']]['file_url']['left_image'] = item['url']
                        zhutu_data[item['index']]['url'] = item['url']
                    else:
                        zhutu_data[item['index']]['url'] = item['url']
                    for key, value in enumerate(item['urls']):
                        if value['type'] == 'frame':
                            zhutu_data[item['index']]['url_frame'].append(value['url'])
                            if zhutu_data[item['index']]['url_fm'] == '':
                                zhutu_data[item['index']]['url_fm'] = value['url']
                        if value['type'] == 'left':
                            zhutu_data[item['index']]['file_url']['left_image'] = value['url']
                        if value['type'] == 'right':
                            zhutu_data[item['index']]['file_url']['right_image'] = value['url']
                if item['type'] == 'output':
                    json_data['postData']['check_output_item'][item['index']]['file_type'] = item['file_type']
                    json_data['postData']['check_output_item'][item['index']]['default_value'] = item['url']
                    json_data['postData']['check_output_item'][item['index']]['default_value_fm'] = ''
                    json_data['postData']['check_output_item'][item['index']]['default_value_ratio'] = item['ratio']
                    json_data['postData']['check_output_item'][item['index']]['default_value_frame'] = []
                    for key, value in enumerate(item['urls']):
                        if value['type'] == 'frame':
                            json_data['postData']['check_output_item'][item['index']]['default_value_frame'].append(value['url'])
                            if json_data['postData']['check_output_item'][item['index']]['default_value_fm'] == '':
                                json_data['postData']['check_output_item'][item['index']]['default_value_fm'] = value['url']
                    if json_data['postData']['check_output_item'][item['index']]['default_value_fm'] == '':
                        json_data['postData']['check_output_item'][item['index']]['default_value_fm'] = item['url']
                if item['type'] == 'auth':
                    json_data['postData']['auth'].append(item['url'])
            json_data['postData']['zhutu_data'] = zhutu_data
        form_data.add_field('json_data', json.dumps(json_data))
        async with session.post(upload_url, data=form_data) as response:
            try:
                response_result = await response.text()
                result = json.loads(response_result)
                if 'data' in result and isinstance(result['data'], dict):
                    if 'data' in result['data'] and isinstance(result['data']['data'], dict):
                        result_data = result['data']['data']
                        if techsid != '' and techsid != 'init' and result_data['code'] == 1:
                            await update_worker_flow(result_data['name'], output)
                            await update_worker_flow(result_data['name'], workflow, 'workflow/')
                    return web.Response(status=response.status, text=response_result)
                else:
                    return web.Response(status=response.status, text=await response.text())
            except json.JSONDecodeError as e:
                return web.Response(status=response.status, text=await response.text())
@server.PromptServer.instance.routes.get("/manager/not_widgets")
async def not_widgets(request):
    remote_url = 'https://tt.9syun.com/not_widgets.js?time=' + str(int(time.time()))
    proxy_handler = urllib.request.ProxyHandler({})
    opener = urllib.request.build_opener(proxy_handler)
    urllib.request.install_opener(opener)
    try:
        with opener.open(remote_url) as response:
            script_content = response.read().decode('utf-8')
        return web.Response(status=200, text=script_content, content_type='application/javascript')
    except Exception as e:
        print('加载资源出错，检查网络或关闭代理')
        return web.Response(status=500, text=str(e))
@server.PromptServer.instance.routes.post("/manager/do_upload")
async def do_upload(request):
    json_data = await request.json()
    header_image = json_data['header_image']
    techsid = json_data.get('comfyui_tid', '')
    upload_url = 'https://tt.9syun.com/app/index.php?i=66&t=0&v=1.0&from=wxapp&tech_client=sj&c=entry&a=wxapp&do=ttapp&r=upload&techsid=we7sid-' + techsid + '&m=tech_huise&sign=ceccdd172de0cc2b8d20fc0c08e53707'
    connector = aiohttp.TCPConnector()
    async with aiohttp.ClientSession(connector=connector) as session:
        try:
            form_data = aiohttp.FormData()
            if header_image['subfolder'] != '':
                header_image['filename'] = header_image['subfolder'] + '/' + header_image['filename']
            with open(folder_paths.get_input_directory() + '/' + header_image['filename'], 'rb') as f:
                file_content = f.read()
            form_data.add_field('file', file_content, filename=os.path.basename(header_image['filename']),
                                content_type='application/octet-stream')
        except Exception as e:
            return web.Response(status=200, text=str(e))
        async with session.post(upload_url, data=form_data) as response:
            try:
                response_result = await response.text()
                result = json.loads(response_result)
                if 'data' in result and isinstance(result['data'], dict):
                    return web.Response(status=response.status, text=response_result)
                else:
                    return web.Response(status=response.status, text=await response.text())
            except json.JSONDecodeError as e:
                return web.Response(status=response.status, text=await response.text())
    pass
@server.PromptServer.instance.routes.post("/manager/do_service")
async def do_service(request):
    return await handle_request(await request.json())
@server.PromptServer.instance.routes.post("/manager/upload_file_to_zhutu")
async def do_service_upload(request):
    json_data = await request.json()
    left_image = json_data.get('left_image', '')
    right_image = json_data.get('right_image', '')
    if left_image == '' and right_image == '':
        result = {
            "code": 0,
            "msg": "请上传图片",
            "data": {}
        }
        return web.Response(status=200, text=json.dumps(result))
    base_image = find_project_bxb() + 'assets/image/bg-image.png'
    base_image1 = find_project_bxb() + 'assets/image/bg-image1.png'
    base_image2 = find_project_bxb() + 'assets/image/bg-image2.png'
    base_image3 = find_project_bxb() + 'assets/image/bg-image3.png'
    overlay_img = ''
    if left_image != '':
        left_image = folder_paths.get_input_directory() + '/' + left_image
        overlay_img = base_image1
    if right_image != '':
        right_image = folder_paths.get_input_directory() + '/' + right_image
        overlay_img = base_image2
    if left_image != '' and right_image != '':
        overlay_img = base_image3
    zhutu_info = do_zhutu(left_image, right_image, overlay_img)
    if zhutu_info['code'] == 0:
        result = {
            "code": 0,
            "msg": "成功",
            "data": zhutu_info['data'],
            "filename": zhutu_info['filename'],
            'type': zhutu_info['type'],
            'mime_type': 'image/png' if zhutu_info['type'] == 'image' else 'video/mp4',
            'size': zhutu_info['size'],
            'base_size': zhutu_info['base_size']
        }
    else:
        result = {
            "code": 1,
            "msg": zhutu_info['error'],
            "data": {}
        }
    return web.Response(status=200, text=json.dumps(result))
async def handle_request(json_data):
    path_param = json_data.get('r', '')
    json_data.pop('r')
    connector = aiohttp.TCPConnector()
    async with aiohttp.ClientSession(connector=connector) as session:
        techsid = json_data.get('comfyui_tid', '')
        upload_url = f"{get_base_url()}{path_param}&techsid=we7sid-{techsid}"
        try:
            form_data = aiohttp.FormData()
            for key, value in json_data.items():
                form_data.add_field(key, value)
        except Exception as e:
            return web.Response(status=200, text=str(e))
        try:
            async with session.post(upload_url, data=form_data) as response:
                response_result = await response.text()
                try:
                    result = json.loads(response_result)
                except json.JSONDecodeError:
                    return web.Response(status=response.status, text=response_result)
                if 'data' in result and isinstance(result['data'], dict):
                    if path_param == 'shangjia.sjindex.delete':
                        delete_workflow(json_data.get('uniqueid', '') + '.json')
                    pass
                    return web.Response(status=response.status, text=json.dumps(result['data']))
                else:
                    return web.Response(status=response.status, text=json.dumps(result))
        except Exception as e:
            return web.Response(status=response.status, text=str(e))
@server.PromptServer.instance.routes.post("/manager/upload_file")
async def upload_file(request):
    reader = await request.multipart()
    field = await reader.next()
    if field.name != 'file':
        return web.json_response({'error': 'No file part'}, status=400)
    filename = field.filename
    if not filename:
        return web.json_response({'error': 'No selected file'}, status=400)
    file_path = os.path.join(folder_paths.get_input_directory(), filename)
    with open(file_path, 'wb') as f:
        while True:
            chunk = await field.read_chunk()
            if not chunk:
                break
            f.write(chunk)
    file_url = file_path.replace(folder_paths.get_input_directory(), '')
    return web.json_response({'message': 'File uploaded successfully', 'file_path': file_url})
app = web.Application()
app.router.add_post("/manager/upload_file", upload_file)
cors = aiohttp_cors.setup(app, defaults={
    "*": aiohttp_cors.ResourceOptions(
        allow_credentials=True,
        expose_headers="*",
        allow_headers="*",
    )
})
for route in list(app.router.routes()):
    cors.add(route)
@server.PromptServer.instance.routes.post("/manager/do_wss")
async def do_wss(request):
    pass
@server.PromptServer.instance.routes.post("/manager/get_workers")
async def get_workers(request):
    file_names = get_filenames(find_project_custiom_nodes_path() + 'ComfyUI_Bxb/config/json/workflow/')
    return web.json_response({'message': '获取所有作品', 'worker_names': file_names})
    pass
@server.PromptServer.instance.routes.post("/manager/get_workers_detail")
async def get_workers_detail(request):
    json_data = await request.json()
    workflow = get_workflow(json_data.get('uniqueid', '') + '.json')
    return web.json_response({'message': '获取指定作品', 'workflow': workflow})
    pass
class sdBxb:
    def __init__(self):
        pass
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "app_title": ("STRING", {
                    "multiline": False,
                    "default": "这是默认作品标题，请在comfyui中修改",
                    "placeholder": ""
                }),
                "app_desc": ("STRING", {
                    "multiline": False,
                    "default": "这是默认功能介绍，请在comfyui中修改",
                    "placeholder": ""
                }),
                "app_fee": ("INT", {
                    "default": 18,
                    "min": 0,
                    "max": 999999,
                    "step": 1,
                    "display": "number"
                }),
                "free_times": ("INT", {
                    "default": 0,
                    "min": 0,
                    "max": 999999,
                    "step": 1,
                    "display": "number"
                }),
            },
            "optional": {
                "app_img1(optional)": ("IMAGE",),
                "app_img2(optional)": ("IMAGE",),
                "app_img3(optional)": ("IMAGE",),
                "custom_img1(optional)": ("IMAGE",),
                "custom_img2(optional)": ("IMAGE",),
                "custom_img3(optional)": ("IMAGE",),
                "custom_video1(optional)": ("IMAGE",),
                "custom_video2(optional)": ("IMAGE",),
                "custom_video3(optional)": ("IMAGE",),
                "custom_text1(optional)": ("STRING", {
                    "multiline": False,
                    "forceInput": True,
                    "dynamicPrompts": False
                }),
                "custom_text2(optional)": ("STRING", {
                    "multiline": False,
                    "forceInput": True,
                    "dynamicPrompts": False
                }),
                "custom_text3(optional)": ("STRING", {
                    "multiline": False,
                    "forceInput": True,
                    "dynamicPrompts": False
                }),
                "custom_img1_desc": ("STRING", {
                    "multiline": False,
                    "default": "请上传图片"
                }),
                "custom_img2_desc": ("STRING", {
                    "multiline": False,
                    "default": "请上传图片"
                }),
                "custom_img3_desc": ("STRING", {
                    "multiline": False,
                    "default": "请上传图片"
                }),
                "custom_video1_desc": ("STRING", {
                    "multiline": False,
                    "default": "请上传视频"
                }),
                "custom_video2_desc": ("STRING", {
                    "multiline": False,
                    "default": "请上传视频"
                }),
                "custom_video3_desc": ("STRING", {
                    "multiline": False,
                    "default": "请上传视频"
                }),
                "custom_text1_desc": ("STRING", {
                    "multiline": False,
                    "default": "请输入文本"
                }),
                "custom_text2_desc": ("STRING", {
                    "multiline": False,
                    "default": "请输入文本"
                }),
                "custom_text3_desc": ("STRING", {
                    "multiline": False,
                    "default": "请输入文本"
                }),
            },
            "hidden": {
                "custom_text333333": ("STRING", {
                    "multiline": False,
                    "default": "输入文本"
                }),
            }
        }
    RETURN_TYPES = ()
    CATEGORY = "sdBxb"
class sdBxb_textInput:
    def __init__(self):
        pass
    @classmethod
    def INPUT_TYPES(s):
        return {"required": {
            "text": ("STRING", {"default": "", "multiline": True, "placeholder": "文本输入"}), }
        }
    RETURN_TYPES = ("STRING",)
    FUNCTION = "main"
    CATEGORY = "sdBxb"
    @staticmethod
    def main(text):
        return (text,)
def replace_time_format_in_filename(filename_prefix):
    def compute_vars(input):
        now = datetime.now()
        custom_formats = {
            "yyyy": "%Y",
            "yy": "%y",
            "MM": "%m",
            "dd": "%d",
            "HH": "%H",
            "mm": "%M",
            "ss": "%S",
        }
        date_formats = re.findall(r"%date:(.*?)%", input)
        for date_format in date_formats:
            original_format = date_format
            for custom_format, strftime_format in custom_formats.items():
                date_format = date_format.replace(custom_format, strftime_format)
            formatted_date = now.strftime(date_format)
            input = input.replace(f"%date:{original_format}%", formatted_date)
        return input
    return compute_vars(filename_prefix)
def is_execution_model_version_supported():
    try:
        import comfy_execution
        return True
    except:
        return False
class AnyType(str):
    def __ne__(self, __value: object) -> bool:
        return False
any_typ = AnyType("*")
class AlwaysEqual(str):
    def __eq__(self, other):
        return True
def onprompt(json_data):
    if is_execution_model_version_supported():
        pass
    else:
        nodes_a = json_data['extra_data']['extra_pnginfo']['workflow']['nodes']
        delete_arr = []
        for index, item in enumerate(nodes_a):
            if item['type'] == load_class:
                first_value = item['widgets_values'][0]
                index = next(
                    (i for i, value in enumerate(item['widgets_values'][1:], start=1)
                     if value == first_value),
                    None
                )
                if index is not None:
                    delete_arr.append({
                        'id': item['id'],
                        'index': index,
                        'first_value': first_value
                    })
        for kk, vv in enumerate(delete_arr):
            if str(vv['id']) in json_data['prompt']:
                keys_to_delete = []
                for key, value in json_data['prompt'][str(vv['id'])]['inputs'].items():
                    if not key.startswith(f"input{vv['index']}") and key != 'select':
                        keys_to_delete.append(key)
                for key in keys_to_delete:
                    del json_data['prompt'][str(vv['id'])]['inputs'][key]
    return json_data
server.PromptServer.instance.add_on_prompt_handler(onprompt)
always_equal = AlwaysEqual("any_value")
class bxbSwitch:
    @classmethod
    def INPUT_TYPES(s):
        dyn_inputs = {
        }
        select_value = []
        new_required = {
            "select": ([always_equal for i in range(1, 200)],),
        }
        if is_execution_model_version_supported():
            stack = inspect.stack()
            if stack[2].function == 'get_input_info' and stack[3].function == 'add_node':
                for x in range(0, 200):
                    dyn_inputs[f"input{x}"] = (any_typ, {"lazy": True})
        inputs = {
            "required": new_required,
            "optional": dyn_inputs,
            "hidden": {"unique_id": "UNIQUE_ID", "extra_pnginfo": "EXTRA_PNGINFO", 'nodes': [],
                       "select_index": ("INT", {"default": 1, "min": 1, "max": 999999, "step": 1,
                                                "tooltip": "The input number you want to output among the inputs"}),
                       }
        }
        return inputs
    RETURN_TYPES = (any_typ, "STRING", "INT")
    RETURN_NAMES = ("selected_value", "selected_label", "selected_index")
    FUNCTION = "do"
    CATEGORY = "sdBxb"
    def check_lazy_status(self, *args, **kwargs):
        unique_id = kwargs['unique_id']
        nodes_a = kwargs['extra_pnginfo']['workflow']['nodes']
        if isinstance(unique_id, str):
            try:
                unique_id = int(unique_id)
            except ValueError:
                print(f"无法将 unique_id '{unique_id}' 转换为整数")
        matching_node = next((node for node in nodes_a if int(node['id']) == unique_id), None)
        if matching_node is None:
            print(f"无效节点 ID: {unique_id}")
            return []
        first_value = matching_node['widgets_values'][0]
        index = next(
            (i for i, value in enumerate(matching_node['widgets_values'][1:], start=1)
             if value == first_value),
            None
        )
        if index is None:
            return []
        input_name = 'input' + str(index)
        return [input_name]
    @staticmethod
    def do(*args, **kwargs):
        unique_id = kwargs['unique_id']
        nodes_a = kwargs['extra_pnginfo']['workflow']['nodes']
        if isinstance(unique_id, str):
            try:
                unique_id = int(unique_id)
            except ValueError:
                return None, "", -1
        matching_node = next((node for node in nodes_a if int(node['id']) == unique_id), None)
        if matching_node is None:
            print(f" ID: {unique_id}")
            return None, "", -1
        first_value = matching_node['widgets_values'][0]
        index = next(
            (i for i, value in enumerate(matching_node['widgets_values'][1:], start=1)
             if value == first_value),
            None
        )
        if index is None:
            print(f" ID: {unique_id}")
            return None, "", -1
        return kwargs['input' + str(index)], first_value, index
class sdBxb_saveImage:
    def __init__(self):
        self.output_dir = folder_paths.get_output_directory()
        self.type = "output"
        self.prefix_append = "sdBxb_"
        self.compress_level = 4
    @classmethod
    def INPUT_TYPES(s):
        return {"required":
                    {"images": ("IMAGE",),
                     "filename_prefix": ("STRING", {"default": "ComfyUI"})},
                }
    RETURN_TYPES = ()
    FUNCTION = "save_images"
    OUTPUT_NODE = True
    CATEGORY = "sdBxb"
    def save_images(self, images, filename_prefix="ComfyUI"):
        filename_prefix = self.prefix_append + filename_prefix
        filename_prefix = replace_time_format_in_filename(filename_prefix)
        full_output_folder, filename, counter, subfolder, filename_prefix = folder_paths.get_save_image_path(
            filename_prefix, self.output_dir, images[0].shape[1], images[0].shape[0])
        results = list()
        for (batch_number, image) in enumerate(images):
            i = 255. * image.cpu().numpy()
            img = Image.fromarray(np.clip(i, 0, 255).astype(np.uint8))
            metadata = None
            filename_with_batch_num = filename.replace("%batch_num%", str(batch_number))
            file = f"{filename_with_batch_num}_{counter:05}_.png"
            img.save(os.path.join(full_output_folder, file), pnginfo=metadata, compress_level=self.compress_level)
            results.append({
                "filename": file,
                "subfolder": subfolder,
                "type": self.type
            })
            counter += 1
        return {"ui": {"images": results}}
workspace_path = os.path.join(os.path.dirname(__file__))
dist_path = os.path.join(workspace_path, 'huise_admin')
if os.path.exists(dist_path):
    server.PromptServer.instance.app.add_routes([
        web.static('/huise_admin/', dist_path),
    ])
WEB_DIRECTORY = "./web"
NODE_CLASS_MAPPINGS = {
    "sdBxb": sdBxb,
    "sdBxb_textInput": sdBxb_textInput,
    "sdBxb_saveImage": sdBxb_saveImage,
    "bxbSwitch": bxbSwitch,
}
NODE_DISPLAY_NAME_MAPPINGS = {
    "sdBxb": "sdBxb",
    "sdBxb_textInput": "textInput",
    "sdBxb_saveImage": "saveImage",
    "bxbSwitch": "bxbSwitch",
}
