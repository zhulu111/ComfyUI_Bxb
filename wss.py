import asyncio
import json
import os
import queue
import time
import urllib
import uuid
import aiohttp
import urllib.request
import urllib.parse
import collections
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock, Condition
import websockets
WEBSOCKETS_VERSION = tuple(map(int, websockets.__version__.split('.')))
def is_websocket_connected(websocket_conn):
    
    if websocket_conn is None:
        return False
    if WEBSOCKETS_VERSION < (14, 0):
        return websocket_conn.open
    else:
        return websocket_conn.state == 1
import threading
from .public import (get_output, write_json_to_file, get_address, get_port, get_port_from_cmdline, args, \
                     find_project_root, get_workflow, get_base_url, get_filenames, read_json_file,merge_alpha_channels,
                     generate_large_random_number, generate_md5_uid_timestamp_filename, loca_download_image, print_exception_in_chinese, determine_file_type, get_upload_url, send_binary_data, remove_query_parameters, combine_images, send_binary_data_async, find_project_custiom_nodes_path)
from .utils import get_video_dimensions, get_image_dimensions, extract_frames
import folder_paths
output_directory = folder_paths.get_output_directory()
SERVER_1_URI = "wss://tt.9syun.com/wss"
ADDRESS = get_address()
PORT = get_port_from_cmdline()
HTTP_ADDRESS = "http://{}:{}/".format(ADDRESS, PORT)
new_client_w_id = f"{str(uuid.uuid4())}:{get_port()}"
SERVER_2_URI = "ws://{}:{}/ws?clientId={}".format(ADDRESS, PORT, new_client_w_id)
RECONNECT_DELAY = 1
MAX_RECONNECT_DELAY = 3
task_queue_1 = queue.Queue()
task_queue_2 = queue.Queue()
task_queue_3 = {}
websocket_queue = collections.deque()
websocket_conn1 = None
websocket_conn2 = None
websocket_conn3 = None
history_data = {
    'queue_running': [],
    'queue_pending': []
}
history_prompt_ids = []
class MonitoredThreadPoolExecutor(ThreadPoolExecutor):
    def __init__(self, max_workers=None, thread_name_prefix=''):
        super().__init__(max_workers=max_workers, thread_name_prefix=thread_name_prefix)
        self._lock = Lock()
        self._condition = Condition(self._lock)
        self._active_tasks = 0
        self._max_workers = max_workers
    def submit(self, fn, *args, **kwargs):
        with self._lock:
            while self._active_tasks >= self._max_workers:
                self._condition.wait()
            self._active_tasks += 1
        future = super().submit(self._wrap_task(fn), *args, **kwargs)
        return future
    def _wrap_task(self, fn):
        def wrapped_fn(*args, **kwargs):
            try:
                return fn(*args, **kwargs)
            finally:
                with self._lock:
                    self._active_tasks -= 1
                    self._condition.notify_all()
        return wrapped_fn
    def active_tasks(self):
        with self._lock:
            return self._active_tasks
executor = MonitoredThreadPoolExecutor(max_workers=40)
class UploadManager:
    def __init__(self, session, url_result, post_file_arr, post_uir_arr, base_url):
        self.session = session
        self.url_result = url_result
        self.post_file_arr = post_file_arr
        self.post_uir_arr = post_uir_arr
        self.binary_arr = ['frame', 'auth']
        self.base_url = base_url
        self.json_arr = []
        self.auth_arr = []
    def prepare_tasks(self):
        tasks = []
        for index, item1 in enumerate(self.url_result['data']['data']):
            main_url = item1['url']
            main_post_file = self.post_file_arr[index]['url']
            main_post_uir = self.post_uir_arr[index]['url']
            is_binary = item1['type'] in self.binary_arr
            mime_type = self.post_uir_arr[index]['url']
            if not is_binary:
                main_post_file = f"{self.base_url}/{main_post_file}"
            tasks.append((main_url, main_post_file, is_binary, mime_type, index, False, 0))
            for key, value in enumerate(item1.get('urls', [])):
                url = value['url']
                post_file = self.post_file_arr[index]['urls'][key]['url']
                post_uir = self.post_uir_arr[index]['urls'][key]['url']
                file_type = self.post_uir_arr[index]['urls'][key]['type']
                is_binary = file_type in self.binary_arr
                if not is_binary:
                    post_file = f"{self.base_url}/{post_file}"
                tasks.append((url, post_file, is_binary, post_uir, index, True, key))
        return tasks
    def upload_task(self, *args):
        import time
        start_time = time.time()
        upload_url, post_file, is_binary, mime_type, index, is_sub_url, key = args
        upload_status, upload_meaage = send_binary_data_async(upload_url, post_file, is_binary, mime_type)
        if not upload_status:
            time.sleep(0.5)
            upload_status, upload_meaage = send_binary_data_async(upload_url, post_file, is_binary, mime_type)
            if not upload_status:
                raise Exception(upload_meaage)
        cleaned_url = remove_query_parameters(upload_url)
        elapsed_time = time.time() - start_time
        return cleaned_url, index, is_sub_url, key, elapsed_time, is_binary
    def start_sync(self):
        tasks = self.prepare_tasks()
        results = []
        with ThreadPoolExecutor(max_workers=15) as executor1:
            futures = {executor1.submit(self.upload_task, *task): task for task in tasks}
            for future in as_completed(futures):
                try:
                    cleaned_url, index, is_sub_url, key, elapsed_time, is_binary = future.result()
                    if is_sub_url:
                        self.url_result['data']['data'][index]['urls'][key]['url'] = cleaned_url
                    else:
                        self.url_result['data']['data'][index]['url'] = cleaned_url
                    results.append((cleaned_url, index, is_sub_url, key))
                except Exception as e:
                    raise Exception(str(e)+cleaned_url)
                    pass
        return results
    def get(self):
        for index, item1 in enumerate(self.url_result['data']['data']):
            if item1['type'] == 'auth':
                self.auth_arr.append(item1)
            else:
                self.json_arr.append(item1)
        return self.json_arr, self.auth_arr, self.url_result['data']['data']
async def websocket_connect(uri, conn_identifier):
    global websocket_conn1, websocket_conn2, send_time
    reconnect_delay = RECONNECT_DELAY
    while True:
        try:
            async with websockets.connect(uri) as websocket:
                print(f"{conn_identifier} 连接成功")
                if conn_identifier == 1:
                    websocket_conn1 = websocket
                else:
                    websocket_conn2 = websocket
                    for key, val in task_queue_3.items():
                        is_set = key in history_prompt_ids
                        if is_set:
                            pass
                        else:
                            task_queue_2.put({
                                'type': 'send',
                                'prompt_id': key,
                            })
                reconnect_delay = RECONNECT_DELAY
                tasks = [
                    asyncio.create_task(receive_messages(websocket, conn_identifier)),
                    asyncio.create_task(send_heartbeat())
                ]
                await asyncio.gather(*tasks)
        except websockets.ConnectionClosedError as e:
            print_exception_in_chinese(e)
            await asyncio.sleep(reconnect_delay)
        except websockets.ConnectionClosedOK as e:
            print_exception_in_chinese(e)
            await asyncio.sleep(reconnect_delay)
        except Exception as e:
            await asyncio.sleep(reconnect_delay)
        reconnect_delay = min(reconnect_delay * 2, MAX_RECONNECT_DELAY)
def get_history_prompt(prompt_id):
    try:
        if is_websocket_connected(websocket_conn2):
            with urllib.request.urlopen(HTTP_ADDRESS + 'history' + '/' + prompt_id) as response:
                return json.loads(response.read())
        else:
            return {}
    except Exception as e:
        print(f"\033[91m 服务正在连接中{get_time()}  \033[0m")
        return {}
async def getHistoryPrompt(prompt_id, type_a=''):
    result_data = [{"type": "str", "k": 'prompt_id', "v": prompt_id}]
    result = get_history_prompt(prompt_id)
    response_status = None
    post_uir_arr = []
    post_file_arr = []
    image_info_list = []
    try:
        if prompt_id in result:
            result = result[prompt_id]
            status = result.get('status', {})
            if status.get('completed', False):
                file_num = 0
                result_data.append({"type": "str", "k": 'ok', "v": '1'})
                for index, output in enumerate(result.get('outputs', {}).values()):
                    for media in ['images', 'gifs', 'videos']:
                        if media in output:
                            for item in output[media]:
                                if 'filename' in item and item['type'] == 'output':
                                    if item['subfolder'] != '':
                                        item['filename'] = item['subfolder'] + '/' + item['filename']
                                    file_num += 1
                                    item_url_info = {}
                                    mine_type, file_type = determine_file_type(folder_paths.get_output_directory() + '/' + item['filename'])
                                    if file_type == 'video':
                                        width1, height1, size_mb = get_video_dimensions(folder_paths.get_output_directory() + '/' + item['filename'])
                                    else:
                                        width1, height1, size_mb = get_image_dimensions(folder_paths.get_output_directory() + '/' + item['filename'], {'TIMESTAMP': str(time.time()), 'PROMPTID': str(prompt_id)})
                                    item_url_info = {
                                        'url': mine_type,
                                        'file_type': file_type,
                                        'width': width1,
                                        'height': height1,
                                        'ratio': height1 / width1,
                                        'urls': [],
                                        'type': 'result'
                                    }
                                    item_url_file = {
                                        'url': item['filename'],
                                        'urls': [],
                                        'type': 'result'
                                    }
                                    if file_type == 'video':
                                        frame_contents = extract_frames(folder_paths.get_output_directory() + '/' + item['filename'])
                                        for k, frame_content in enumerate(frame_contents):
                                            image_info_list.append({
                                                'type': 'binary',
                                                'content': frame_content
                                            })
                                            if k == 0:
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
                                    else:
                                        image_info_list.append({
                                            'type': 'path',
                                            'content': folder_paths.get_output_directory() + '/' + item['filename']
                                        })
                                    post_uir_arr.append(item_url_info)
                                    post_file_arr.append(item_url_file)
                if file_num == 0:
                    return
                    pass
            else:
                result_data.append({"type": "str", "k": 'ok', "v": '0', 'text': 'completed状态不对'})
        else:
            is_set = prompt_id in history_prompt_ids
            if is_set:
                return
            result_data.append({"type": "str", "k": 'ok', "v": '0', 'text': 'prompt_id没有找到'})
        response_status = 200
    except Exception as e:
        print_exception_in_chinese(e)
        result_data.append({"type": "str", "k": 'ok', "v": '0', 'text': '异常的信息'})
        response_status = 500
    if len(image_info_list) > 0:
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
    submit_url = get_base_url() + 'comfyui.resultv2.formSubmitForComfyUi&m=tech_huise'
    connector = aiohttp.TCPConnector()
    async with aiohttp.ClientSession(connector=connector) as session:
        try:
            url_result = await get_upload_url(post_uir_arr, new_client_w_id, session, 2)
            manager = UploadManager(session, url_result, post_file_arr, post_uir_arr, folder_paths.get_output_directory())
            manager.start_sync()
            json_arr, auth_arr, post_arr = manager.get()
            result_data.append({"type": "str", "k": 'images', "v": json.dumps(json_arr)})
            result_data.append({"type": "str", "k": 'auth', "v": json.dumps(auth_arr)})
            form_res_data = await send_form_data(session, submit_url, result_data, prompt_id)
        except json.JSONDecodeError as e:
            print_exception_in_chinese(e)
            result_data.append({"type": "str", "k": 'ok', "v": '0', 'text': str(e)})
            result_data.append({"type": "str", "k": 'error', "v": str(e)})
            response_status = 400
            form_res_data = await send_form_data(session, submit_url, result_data, prompt_id)
        except Exception as e:
            print_exception_in_chinese(e)
            result_data.append({"type": "str", "k": 'ok', "v": '0', 'text': 'upload_url:'+str(e)})
            result_data.append({"type": "str", "k": 'error', "v": 'upload_url:'+str(e)})
            response_status = 500
            form_res_data = await send_form_data(session, submit_url, result_data, prompt_id)
        finally:
            if 'session' in locals():
                await session.close()
        return {'status': response_status,
                'message': '操作完成.' if response_status == 200 else '发生错误.'}
async def send_form_data(session, url, data, prompt_id=None):
    global websocket_conn1
    form_data = aiohttp.FormData()
    try:
        for item in data:
            if item['type'] == 'str':
                form_data.add_field(item['k'], item['v'])
            if item['type'] == 'images' or item['type'] == 'gifs' or item['type'] == 'videos' or item[
                'type'] == 'files':
                if os.path.exists(item['v']):
                    with open(item['v'], 'rb') as f:
                        file_content = f.read()
                    form_data.add_field(item['k'] + '[]', file_content, filename=os.path.basename(item['v']),
                                        content_type='application/octet-stream')
                    pass
                else:
                    pass
            if item['type'] == 'file':
                if os.path.exists(item['v']):
                    with open(item['v'], 'rb') as f:
                        file_content = f.read()
                    form_data.add_field(item['k'], file_content, filename=os.path.basename(item['v']),
                                        content_type='application/octet-stream')
                else:
                    pass
    except Exception as e:
        print_exception_in_chinese(e)
    async with session.post(url, data=form_data) as response:
        if response.status == 200:
            resp_text = await response.text()
            if prompt_id and is_websocket_connected(websocket_conn1):
                websocket_queue.append({
                    "conn_identifier": 1,
                    "data": {
                        'type': 'crystools.executed_success',
                        'data': {
                            'prompt_id': prompt_id
                        }
                    },
                })
            return resp_text
        else:
            return None
            pass
async def server1_receive_messages(websocket, message_type, message_json):
    if message_type == 'init':
        await websocket.send(json.dumps({
            'type': 'crystools.bind',
            'data': {
                "client_id": new_client_w_id,
            }
        }))
        pass
    if message_type == 'prompt':
        prompt_data = message_json['data']
        jilu_id = prompt_data['jilu_id']
        uniqueid = message_json['uniqueid']
        output = get_output(uniqueid + '.json')
        workflow = get_workflow(uniqueid + '.json')
        if output:
            executor.submit(run_async_task, output, prompt_data, workflow, jilu_id)
        else:
            if  is_websocket_connected(websocket):
                websocket_queue.append({
                    "conn_identifier": 1,
                    "data": {
                        'type': 'crystools.prompt_error',
                        'data': {
                            'jilu_id': jilu_id,
                            'msg': '作品工作流找不到了'
                        }
                    },
                })
        pass
def optimized_process_history_data(history_data_1):
    running = []
    pending = []
    if history_data_1:
        queue_running = history_data_1.get('queue_running', [])
        if queue_running:
            running.append(queue_running[0][1])
        queue_pending = history_data_1.get('queue_pending', [])
        if queue_pending:
            pending = sorted(queue_pending, key=lambda x: int(x[0]))
            pending = [item[1] for item in pending]
    return running, pending
async def getMessageHistoryPrompt(result, prompt_id):
    result_data = [{"type": "str", "k": 'prompt_id', "v": prompt_id}]
    response_status = None
    if 'output' not in result:
        return
    if result['output'] is None:
        return
    try:
        file_num = 0
        result_data.append({"type": "str", "k": 'ok', "v": '1'})
        for media in ['images', 'gifs', 'videos']:
            if media in result['output']:
                for item in result['output'][media]:
                    if 'filename' in item and item['type'] == 'output':
                        if item['subfolder'] != '':
                            item['filename'] = item['subfolder'] + '/' + item['filename']
                        file_num += 1
                        result_data.append({"type": 'images', "k": 'file', "v": folder_paths.get_output_directory() + '/' + item['filename']})
        if file_num == 0:
            return
            pass
    except Exception as e:
        print_exception_in_chinese(e)
        result_data.append({"type": "str", "k": 'ok', "v": '0', 'text': '异常的信息'})
        response_status = 500
    submit_url = get_base_url() + 'comfyui.resultv2.formSubmitForComfyUi&m=tech_huise'
    connector = aiohttp.TCPConnector()
    async with aiohttp.ClientSession(connector=connector) as session:
        try:
            form_res_data = await send_form_data(session, submit_url, result_data, prompt_id)
        except json.JSONDecodeError as e:
            print_exception_in_chinese(e)
            result_data.append({"type": "str", "k": 'ok', "v": '0', 'text': 'json异常的信息'})
            response_status = 400
        except Exception as e:
            print_exception_in_chinese(e)
            result_data.append({"type": "str", "k": 'ok', "v": '0', 'text': 'aiohttpException异常的信息'})
            response_status = 500
        finally:
            if 'session' in locals():
                await session.close()
        return {'status': response_status,
                'message': '操作完成.' if response_status == 200 else '发生错误.'}
async def server2_receive_messages(websocket, message_type, message_json):
    global send_time
    if message_type and message_type != 'crystools.monitor':
        if message_type == 'status' and message_json['data']['status']['exec_info']:
            websocket_queue.append({
                "conn_identifier": 1,
                "data": {
                    'type': 'crystools.queue',
                    'data': {
                        "client_id": new_client_w_id,
                        'queue_remaining': message_json['data']['status']['exec_info'][
                            'queue_remaining']
                    }
                },
            })
            await send_heartbeat_to_server2()
        if message_type == 'execution_start':
            pass
        if message_type == 'executing':
            pass
        if message_type == 'execution_error':
            task_queue_2.put({
                'type': 'send',
                'prompt_id': message_json['data']['prompt_id'],
            })
            pass
        if message_type == 'executed':
            time.sleep(1)
            task_queue_2.put({
                'type': 'send',
                'prompt_id': message_json['data']['prompt_id'],
            })
            pass
        if message_type == 'progress':
            pass
        if message_type == 'execution_cached' and 'prompt_id' in message_json['data']:
            time.sleep(1)
            task_queue_2.put({
                'type': 'send',
                'prompt_id': message_json['data']['prompt_id'],
            })
            pass
async def receive_messages(websocket, conn_identifier):
    
    if is_websocket_connected(websocket):
        try:
            async for message in websocket:
                if type(message) != bytes:
                    message_dict = json.loads(message)
                    message_type = message_dict.get("type")
                    if conn_identifier == 1:
                        await server1_receive_messages(websocket, message_type, message_dict)
                    elif conn_identifier == 2:
                        await server2_receive_messages(websocket, message_type, message_dict)
        except json.JSONDecodeError as e:
            print_exception_in_chinese(e)
        finally:
            await asyncio.sleep(.5)
async def send_heartbeat():
    
    while True:
        try:
            if is_websocket_connected(websocket_conn1) and is_websocket_connected(websocket_conn2):
                await send_heartbeat_to_server2()
                pass
        except Exception as e:
            print_exception_in_chinese(e)
        finally:
            await asyncio.sleep(10)
def get_history():
    global last_get_history_time
    try:
        if is_websocket_connected(websocket_conn2):
            last_get_history_time = time.time()
            with urllib.request.urlopen(HTTP_ADDRESS + 'queue') as response:
                return json.loads(response.read())
        else:
            return {
                'queue_running': [],
                'queue_pending': [],
            }
    except Exception as e:
        return {
            'queue_running': [],
            'queue_pending': [],
        }
send_time = '0'
def get_time():
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
async def send_heartbeat_to_server2():
    running, pending = optimized_process_history_data(history_data)
    try:
        file_names = get_filenames(find_project_custiom_nodes_path() + 'ComfyUI_Bxb/config/json/api/')
        websocket_queue.append({
            "conn_identifier": 1,
            "data": {
                'type': 'crystools.monitor',
                'data': {
                    "files": file_names,
                    "running": running,
                    "pending": pending,
                    "client_id": new_client_w_id,
                }
            },
        })
    except Exception as e:
        print_exception_in_chinese(e)
    pass
def run_task_in_loop(task, *args, **kwargs):
    
    while True:
        task(*args, **kwargs)
        time.sleep(1)
loop_num = 0
async def run_websocket_task_in_loop():
    global loop_num
    while True:
        try:
            if len(websocket_queue) > 0:
                websocket_info = websocket_queue.popleft()
                if 'conn_identifier' in websocket_info:
                    if is_websocket_connected(websocket_conn3)  and is_websocket_connected(websocket_conn1):
                        websocket_info['data']['zhu_client_id'] = new_client_w_id
                        if websocket_info['conn_identifier'] == 1:
                            await websocket_conn3.send(json.dumps(websocket_info['data']))
            else:
                loop_num = loop_num + 1
                if loop_num > 1000:
                    loop_num = 0
                    await websocket_conn3.send(json.dumps({
                        'time': get_time(),
                        'type': 'crystools.line',
                        'data': {
                            'client_id': new_client_w_id,
                        }
                    }))
        except Exception as e:
            break
        finally:
            await asyncio.sleep(0.02)
def queue_prompt(prompt, workflow, new_client_id):
    try:
        if is_websocket_connected(websocket_conn2):
            p = {
                "prompt": prompt,
                "client_id": new_client_id,
                'extra_data': workflow['extra_data'],
            }
            data = json.dumps(p).encode('utf-8')
            req = urllib.request.Request(HTTP_ADDRESS + 'prompt', data=data)
            return json.loads(urllib.request.urlopen(req).read())
        else:
            return {}
    except Exception as e:
        print_exception_in_chinese(e)
        return {}
def find_element_by_key(array, key):
    key_int = key
    if ":" not in key_int:
        key_int = int(key_int)
    for index, element in enumerate(array):
        if element.get('id') == key_int:
            return element, index
    return None, -1
async def process_json_elements(json_data, prompt_data, workflow, jilu_id):
    global websocket_conn1
    line_json = read_json_file('https://tt.9syun.com/seed.json')
    try:
        if 'cs_imgs' in prompt_data and prompt_data['cs_imgs']:
            for item in prompt_data['cs_imgs']:
                filename = os.path.basename(item['upImage'])
                download_info = await loca_download_image(item['upImage'], filename)
                download_status = download_info['code']
                file_new_name = download_info['filename']
                if download_status == False:
                    raise Exception('图片下载失败')
                if str(item['node']) in json_data and 'inputs' in json_data[str(item['node'])] and 'image' in \
                        json_data[str(item['node'])]['inputs']:
                    json_data[str(item['node'])]['inputs']['image'] = file_new_name
        if 'cs_videos' in prompt_data and prompt_data['cs_videos']:
            for item in prompt_data['cs_videos']:
                filename = os.path.basename(item['upImage'])
                download_info = await loca_download_image(item['upImage'], filename)
                download_status = download_info['code']
                file_new_name = download_info['filename']
                if download_status == False:
                    raise Exception('视频下载失败')
                if str(item['node']) in json_data and 'inputs' in json_data[str(item['node'])] and 'video' in \
                        json_data[str(item['node'])]['inputs']:
                    json_data[str(item['node'])]['inputs']['video'] = file_new_name
        if 'cs_texts' in prompt_data and prompt_data['cs_texts']:
            for item in prompt_data['cs_texts']:
                json_data[str(item['node'])]['inputs']['text'] = item['value']
        if 'check_output_item' in prompt_data and prompt_data['check_output_item']:
            check_output_item = prompt_data['check_output_item']
            for index, item in enumerate(check_output_item):
                class_type_name = f"{item['options']['class_type']}.{item['options']['name']}"
                if class_type_name in line_json['video_load'] or class_type_name in line_json['image_load']:
                    if item['custom_value']:
                        filename = os.path.basename(item['custom_value'])
                        download_info = await loca_download_image(item['custom_value'], filename)
                        download_status = download_info['code']
                        file_new_name = download_info['filename']
                        if not download_status:
                            raise Exception('图片下载失败')
                        json_data[item['options']['node']]['inputs'][item['options']['name']] = file_new_name
                        if item.get('mask_value',''):
                            mask_value_filename = os.path.basename(item['mask_value'])
                            mask_value_download_info = await loca_download_image(item['mask_value'], mask_value_filename)
                            mask_value_download_status = mask_value_download_info['code']
                            mask_value_file_new_name = mask_value_download_info['filename']
                            if not mask_value_download_status:
                                raise Exception('图片下载失败')
                            json_data[item['options']['node']]['inputs'][item['options']['name']] = merge_alpha_channels(folder_paths.get_input_directory()+ '/' +file_new_name,folder_paths.get_input_directory()+ '/' + mask_value_file_new_name)
                else:
                    json_data[item['options']['node']]['inputs'][item['options']['name']] = item['custom_value']
            pass
    except KeyError as e:
        print_exception_in_chinese(e)
        websocket_queue.appendleft({
            "conn_identifier": 1,
            "data": {
                'type': 'crystools.prompt_error',
                'data': {
                    'jilu_id': jilu_id,
                    'msg': '发送指令失败1'
                }
            },
        })
        return {
            'code': 0,
            'jilu_id': jilu_id
        }
    except Exception as e:
        print_exception_in_chinese(e)
        websocket_queue.appendleft({
            "conn_identifier": 1,
            "data": {
                'type': 'crystools.prompt_error',
                'data': {
                    'jilu_id': jilu_id,
                    'msg': '发送指令失败2'
                }
            },
        })
        return {
            'code': 0,
            'jilu_id': jilu_id
        }
    async def print_item(now_index, key, value):
        try:
            workflow_node = workflow['extra_data']['extra_pnginfo']['workflow']['nodes']
            if value['class_type'] in line_json['switch_name']:
                workflow_node_info, workflow_node_info_index = find_element_by_key(workflow_node, key)
                workflow['extra_data']['extra_pnginfo']['workflow']['nodes'][workflow_node_info_index]['widgets_values'][0] = value['inputs']['select']
            if value['class_type'] in line_json['seed'] and line_json['seed'][value['class_type']]:
                check_value = line_json['seed'][value['class_type']]
                workflow_node_info, workflow_node_info_index = find_element_by_key(workflow_node, key)
                try:
                    if workflow_node_info:
                        default_seed_value = json_data[key]['inputs'][check_value['seed']]
                        if type(default_seed_value) == int or type(default_seed_value) == float or type(
                                default_seed_value) == str:
                            default_seed_value = float(default_seed_value)
                            check_value_type = check_value['values'][
                                workflow_node_info['widgets_values'][check_value['widgets_index']]]
                            if check_value_type == '+':
                                default_seed_value = default_seed_value + check_value['step']
                            if check_value_type == '-':
                                default_seed_value = default_seed_value - check_value['step']
                            if check_value_type == '*':
                                default_seed_value = generate_large_random_number(15)
                            json_data[key]['inputs'][check_value['seed']] = default_seed_value
                except (KeyError, IndexError, TypeError) as e:
                    print_exception_in_chinese(e)
                    pass
            if value['class_type'] in line_json['crf'] and line_json['crf'][value['class_type']]:
                if line_json['crf'][value['class_type']] in json_data[key]['inputs'] and json_data[key]['inputs'][line_json['crf'][value['class_type']]] == 0:
                    json_data[key]['inputs'][line_json['crf'][value['class_type']]] = 1
        except Exception as e:
            print_exception_in_chinese(e)
            websocket_queue.appendleft({
                "conn_identifier": 1,
                "data": {
                    'type': 'crystools.prompt_error',
                    'data': {
                        'jilu_id': jilu_id,
                        'msg': '发送指令失败'
                    }
                },
            })
    tasks = [print_item(index, key, value) for index, (key, value) in enumerate(json_data.items())]
    await asyncio.gather(*tasks)
    try:
        result = queue_prompt(json_data, workflow, new_client_w_id)
        if 'prompt_id' in result:
            websocket_queue.appendleft({
                "conn_identifier": 1,
                "data": {
                    'type': 'crystools.prompt_ok',
                    'data': {
                        'prompt_id': result['prompt_id'],
                        'jilu_id': jilu_id,
                        'msg': '发送指令成功'
                    }
                },
            })
            task_queue_3[result['prompt_id']] = {
                'jilu_id': jilu_id
            }
            return {
                'code': 1,
                'prompt_id': result['prompt_id']
            }
        else:
            raise Exception('发送指令失败')
    except Exception as e:
        print_exception_in_chinese(e)
        websocket_queue.appendleft({
            "conn_identifier": 1,
            "data": {
                'type': 'crystools.prompt_error',
                'data': {
                    'jilu_id': jilu_id,
                    'msg': '发送指令失败'
                }
            },
        })
        return {
            'code': 0,
            'prompt_id': jilu_id
        }
def run_async_task(json_data, prompt_data, workflow, jilu_id):
    return asyncio.run(process_json_elements(json_data, prompt_data, workflow, jilu_id))
def run_async_task2(prompt_id):
    asyncio.run(getHistoryPrompt(prompt_id))
def task_3():
    
    while True:
        try:
            task_info = task_queue_1.get()
            output = get_output(task_info['uniqueid'] + '.json')
            if output:
                executor.submit(run_async_task, output, task_info['prompt_data'], task_info['jilu_id'])
            task_queue_1.task_done()
        except Exception as e:
            print_exception_in_chinese(e)
        finally:
            time.sleep(1)
def task_4():
    global history_data
    
    while True:
        try:
            task_info = task_queue_2.get()
            if 'prompt_id' in task_info:
                history_data = get_history()
                preprocess_history_data(history_data)
                task_queue_3.pop(task_info['prompt_id'], None)
                executor.submit(run_async_task2, task_info['prompt_id'])
                task_queue_2.task_done()
        except Exception as e:
            print_exception_in_chinese(e)
        finally:
            time.sleep(0.1)
def print_thread_status():
    
    while True:
        print("\n当前活动线程:")
        for thread in threading.enumerate():
            print(f"线程名: {thread.name}, 线程ID: {thread.ident}, 活动状态: {thread.is_alive()}")
        time.sleep(5)
def main_task():
    
    for i in range(10):
        time.sleep(1)
def websocket_thread(uri, conn_identifier):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(websocket_connect(uri, conn_identifier))
def websocket_thread_fu(uri, conn_identifier):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(websocket_connect_fu(uri, conn_identifier))
def preprocess_history_data(history_data):
    global history_prompt_ids
    
    prompt_ids = set()
    if history_data is None:
        history_prompt_ids = prompt_ids
        return
    for queue in ['queue_running', 'queue_pending']:
        for item in history_data.get(queue, []):
            prompt_ids.add(item[1])
    history_prompt_ids = prompt_ids
last_get_history_time = 0
async def task5():
    global history_data
    while True:
        try:
            history_data = get_history()
            preprocess_history_data(history_data)
        except Exception as e:
            print_exception_in_chinese(e)
        await asyncio.sleep(1)
def task5_thread():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(task5())
def start_async_task_in_thread(async_func):
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(async_func())
async def websocket_connect_fu(uri, conn_identifier):
    global websocket_conn3
    reconnect_delay = RECONNECT_DELAY
    while True:
        try:
            async with websockets.connect(uri) as websocket:
                print(f"{conn_identifier} 连接成功")
                websocket_conn3 = websocket
                await websocket_conn3.send(json.dumps({
                    'type': 'crystools.bind',
                    'data': {
                        "client_id": new_client_w_id + '_fu',
                    }
                }))
                reconnect_delay = RECONNECT_DELAY
                tasks = [
                    asyncio.create_task(run_websocket_task_in_loop()),
                ]
                await asyncio.gather(*tasks)
        except websockets.ConnectionClosedError as e:
            print(f"\033[91m 3 服务正在连接中{get_time()}  \033[0m")
            await asyncio.sleep(reconnect_delay)
        except websockets.ConnectionClosedOK as e:
            await asyncio.sleep(reconnect_delay)
        except Exception as e:
            await asyncio.sleep(reconnect_delay)
        reconnect_delay = min(reconnect_delay * 2, MAX_RECONNECT_DELAY)
def thread_run():
    threading.Thread(target=websocket_thread, args=(SERVER_1_URI, 1), daemon=True).start()
    threading.Thread(target=websocket_thread, args=(SERVER_2_URI, 2), daemon=True).start()
    threading.Thread(target=websocket_thread_fu, args=(SERVER_1_URI, 3), daemon=True).start()
    threading.Thread(target=task5_thread).start()
    executor.submit(run_task_in_loop, task_4)
async def update_worker_flow(uniqueid, data, flow_type='api/'):
    write_json_to_file(data, uniqueid + '.json', 'json/' + flow_type, 'json')
