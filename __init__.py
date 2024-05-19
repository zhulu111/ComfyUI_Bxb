
import aiohttp
import server
from aiohttp import web

import subprocess
import os
import time
import threading
from collections import deque
import uuid
import sys
import re
import hashlib
import platform
import stat
import urllib.request

def get_mac_address():
    mac = uuid.getnode()
    return ':'.join(('%012X' % mac)[i:i+2] for i in range(0, 12, 2))

def get_port_from_cmdline():
    for i, arg in enumerate(sys.argv):
        if arg == '--port' and i + 1 < len(sys.argv):
            try:
                return int(sys.argv[i + 1])
            except ValueError:
                pass

        match = re.search(r'--port[=\s]*(\d+)', arg)
        if match:
            try:
                return int(match.group(1))
            except ValueError:
                pass

    # 如果命令行参数中未找到端口号，则返回默认端口号
    return 8188

def generate_unique_subdomain(mac_address, port):
    """根据 MAC 地址和端口号生成唯一的子域名"""
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
    """使用 urllib 下载文件到指定路径"""
    try:
        with urllib.request.urlopen(url) as response, open(dest_path, 'wb') as out_file:
            data = response.read()  # 读取数据
            out_file.write(data)  # 写入文件
        print(f"File downloaded successfully: {dest_path}")
    except Exception as e:
        print(f"Failed to download the file: {e}")

# 获取插件的绝对路径
PLUGIN_DIR = os.path.dirname(os.path.abspath(__file__))

# 设置 sd_client 目录下的文件路径
SD_CLIENT_DIR = os.path.join(PLUGIN_DIR, "sdc")
SDC_EXECUTABLE = os.path.join(SD_CLIENT_DIR, "sdc" if platform.system() != "Windows" else "sdc.exe")
INI_FILE = os.path.join(SD_CLIENT_DIR, "sdc.ini")
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
        """生成 sdc.ini 文件"""
        config_content = f"""
[common]
server_addr = {self.server_addr}
server_port = {self.server_port}
token = {self.token}
login_fail_exit = false

[{subdomain}]
type = http
local_port = {self.local_port}
subdomain = {subdomain}
remote_port = 0
log_file = {LOG_FILE}
log_level = info
"""
        with open(file_path, "w") as config_file:
            config_file.write(config_content)

    def tail_log(self, filename, num_lines=20):
        """获取日志文件的最后几行"""
        try:
            with open(filename, "r") as file:
                return deque(file, num_lines)
        except FileNotFoundError:
            return deque()

    def check_sd_log_for_status(self):
        """检查日志文件中是否包含连接成功或失败的标志性信息"""
        success_keywords = ["login to server success", "start proxy success"]
        failure_keywords = ["connect to server error", "read tcp", "session shutdown"]
        connection_attempt_pattern = re.compile(r"try to connect to server")

        latest_lines = self.tail_log(LOG_FILE, 20)

        connection_attempt_index = None

        # 找到最后一次尝试连接的索引
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
        """启动 SD 客户端"""
        self.check_and_download_executable()  # 检查并下载可执行文件
        self.create_sdc_ini(INI_FILE, self.subdomain)

        # 清空或创建日志文件
        open(LOG_FILE, "w").close()

        # 创建一个环境变量字典，清除代理设置
        env1 = os.environ.copy()
        env1['http_proxy'] = ''
        env1['https_proxy'] = ''
        env1['no_proxy'] = '*'  # 添加无代理配置

        try:
            # 启动 sdc 并重定向输出到日志文件
            with open(LOG_FILE, "a") as log_file:
                self.sd_process = subprocess.Popen([SDC_EXECUTABLE, "-c", INI_FILE], stdout=log_file, stderr=log_file, env=env1)
            print(f"SD client started with PID: {self.sd_process.pid}")

            # 启动监控线程
            self.stop_monitoring = False
            self.monitoring_thread = threading.Thread(target=self.monitor_connection_status, daemon=True)
            self.monitoring_thread.start()

        except FileNotFoundError:
            print(f"Error: '{SDC_EXECUTABLE}' not found。")
        except Exception as e:
            print(f"Error starting SD client: {e}")

    def monitor_connection_status(self):
        """监测 SD 连接状态"""
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
        """停止 SD 客户端并终止监控线程"""
        if self.sd_process and self.sd_process.poll() is None:
            self.sd_process.terminate()
            self.sd_process.wait()
            print("SD client stopped。")
        else:
            print("SD client is not running。")
        self.connected = False
        self.stop_monitoring = True

    def is_connected(self):
        """检查 SD 客户端是否连接成功"""
        return self.connected

    def clear_log(self):
        """清理日志文件"""
        if os.path.exists(LOG_FILE):
            open(LOG_FILE, "w").close()
            print("SD client log cleared。")


subdomain = ""
if platform.system() != "Darwin":
    local_port = get_port_from_cmdline()
    subdomain = generate_unique_subdomain(get_mac_address(), local_port)
    sd_client = SDClient(local_port=local_port, subdomain=subdomain)
    sd_client.start()



@server.PromptServer.instance.routes.post("/manager/tech_zhulu")
async def tech_zhulu(request):
    json_data = await request.json()
    if 'postData' in json_data and isinstance(json_data['postData'], dict):
        json_data['postData']['subdomain'] = subdomain
    async with aiohttp.ClientSession() as session:
        async with session.post('https://tt.9syun.com/app/index.php?i=66&t=0&v=1.0&from=wxapp&tech_client=wx&c=entry&a=wxapp&tech_client=sj&do=ttapp&m=tech_huise&r='+json_data['r']+'&techsid=we7sid-'+json_data['techsid'], json=json_data) as resp:
            # 检查响应的HTTP状态码和内容类型
            if resp.status == 200 and resp.headers.get('Content-Type') == 'application/json':
                try:
                    other_api_data = await resp.json()
                    return web.json_response(other_api_data)
                except aiohttp.ContentTypeError:
                    # 如果响应的内容不是JSON格式，处理错误或进行回退操作
                    error_text = await resp.text()
                    return web.Response(text=error_text, status=400)
            else:
                # 如果状态码不是200或内容类型不是application/json，返回错误信息
                return web.Response(status=resp.status, text=await resp.text())


class sdBxb:

    def __init__(self):
        pass

    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "作品标题": ("STRING", {
                    "multiline": False, 
                    "default": "这是默认作品标题，请在comfyui中修改",
                    "placeholder": ""
                }),
                "作品功能介绍": ("STRING", {
                    "multiline": False, 
                    "default": "这是默认功能介绍，请在comfyui中修改",
                    "placeholder": ""
                }),
                "作品服务单价（分）": ("INT", {
                    "default": 18, 
                    "min": 10, #最小值
                    "max": 999999, #最大值
                    "step": 1, #滑块的步长
                    "display": "number" # 仅限外观：作为“数字”或“滑块”显示
                }),
            },
            "optional": {
                "作品主图1（连接“加载图像”节点，可选）": ("IMAGE",),
                "作品主图2（连接“加载图像”节点，可选）": ("IMAGE",),
                "作品主图3（连接“加载图像”节点，可选）": ("IMAGE",),
                "用户自定义图片1（连接“加载图像”节点，可选）": ("IMAGE",),
                "用户自定义图片2（连接“加载图像”节点，可选）": ("IMAGE",),
                "用户自定义图片3（连接“加载图像”节点，可选）": ("IMAGE",),
                "用户自定义文本1（连接“文本输入”节点，可选）": ("STRING", {
                    "multiline": False, 
                    "forceInput": True,
                    "dynamicPrompts": False
                }),
                "用户自定义文本2（连接“文本输入”节点，可选）": ("STRING", {
                    "multiline": False, 
                    "forceInput": True,
                    "dynamicPrompts": False
                }),
                "用户自定义文本3（连接“文本输入”节点，可选）": ("STRING", {
                    "multiline": False, 
                    "forceInput": True,
                    "dynamicPrompts": False
                }),
                "自定义图片1上传说明": ("STRING", {
                    "multiline": False, 
                    "default": "请上传图片"
                }),
                "自定义图片2上传说明": ("STRING", {
                    "multiline": False, 
                    "default": "请上传图片"
                }),
                "自定义图片3上传说明": ("STRING", {
                    "multiline": False, 
                    "default": "请上传图片"
                }),
                "自定义文本1输入说明": ("STRING", {
                    "multiline": False, 
                    "default": "请输入文本"
                }),
                "自定义文本2输入说明": ("STRING", {
                    "multiline": False, 
                    "default": "请输入文本"
                }),
                "自定义文本3输入说明": ("STRING", {
                    "multiline": False, 
                    "default": "请输入文本"
                }),
            },
            "hidden": {
                "自定义文本3333333": ("STRING", {
                    "multiline": False, 
                    "default": "输入文本"
                }),
            }
        }

    RETURN_TYPES = ()

    CATEGORY = "SD变现宝"


# 文本输入
class sdBxb_textInput:

    def __init__(self):
        pass

    @classmethod
    def INPUT_TYPES(s):
        return {"required": {
            "text": ("STRING", {"default": "", "multiline": True, "placeholder": "文本输入"}),}
        }

    RETURN_TYPES = ("STRING",)
    FUNCTION = "main"

    CATEGORY = "SD变现宝"

    @staticmethod
    def main(text):
        return (text,)


WEB_DIRECTORY = "./web"

NODE_CLASS_MAPPINGS = {
    "sdBxb": sdBxb,
    "sdBxb_textInput": sdBxb_textInput,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "sdBxb": "SD变现宝",
    "sdBxb_textInput": "文本输入"
}
