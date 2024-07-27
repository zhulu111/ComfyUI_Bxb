import asyncio
import json
import re
import subprocess
import time
import aiohttp
import server
from aiohttp import web
from collections import deque
from .install import *
import os
import uuid
import hashlib
import platform
import stat
import urllib.request
import numpy as np
from .wss import thread_run, update_worker_flow
from .public import get_port_from_cmdline, set_token, get_token, get_version, \
    set_openid, get_openid, find_project_root, args
import threading
import folder_paths
from PIL import Image
input_directory = args.input_directory if args.input_directory else find_project_root() + 'input'
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
        print(f"File downloaded successfully: {dest_path}")
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
        # 生成 sdc.toml 文件
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
                print("SDC executable not found, downloading...")
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
                if verify_image_exists(input_directory + '/' + image_path):
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
    async with aiohttp.ClientSession() as session:
        json_data['version'] = get_version()
        techsid = get_token()
        upload_url = 'https://tt.9syun.com/app/index.php?i=66&t=0&v=1.0&from=wxapp&tech_client=wx&c=entry&a=wxapp&tech_client=sj&do=ttapp&m=tech_huise&r=' + \
                     json_data['r'] + '&techsid=we7sid-' + techsid
        if json_data['r'] == 'comfyui.apiv2.upload':
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
                        with open(input_directory + '/' + item, 'rb') as f:
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
                        result_data = result['data']
                        if isinstance(result_data, dict) and json_data[
                            'r'] == 'comfyui.apiv2.code' and 'data' in result_data and 'techsid' in result_data['data'][
                            'data']:
                            if len(result_data['data']['data']['techsid']) > len('12345'):
                                set_token(result_data['data']['data']['techsid'])
                            pass
                        return web.json_response(result)
                    except json.JSONDecodeError as e:
                        return web.Response(status=resp.status, text=await resp.text())
                else:
                    return web.Response(status=resp.status, text=await resp.text())
@server.PromptServer.instance.routes.post("/manager/do_wss")
async def do_wss(request):
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
class sdBxb_saveImage:
    def __init__(self):
        self.output_dir = folder_paths.get_output_directory()
        self.type = "output"
        self.prefix_append = ""
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
    def save_images(self, images, filename_prefix="sdBxb"):
        filename_prefix += self.prefix_append
        full_output_folder, filename, counter, subfolder, filename_prefix = folder_paths.get_save_image_path(
            filename_prefix, self.output_dir, images[0].shape[1], images[0].shape[0])
        results = list()
        for (batch_number, image) in enumerate(images):
            i = 255. * image.cpu().numpy()
            img = Image.fromarray(np.clip(i, 0, 255).astype(np.uint8))
            metadata = None
            filename_with_batch_num = filename.replace("%batch_num%", str(batch_number))
            file = f"sdBxb_{filename_with_batch_num}_{counter:05}_.png"
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
}
NODE_DISPLAY_NAME_MAPPINGS = {
    "sdBxb": "sdBxb",
    "sdBxb_textInput": "textInput",
    "sdBxb_saveImage": "saveImage",
}
