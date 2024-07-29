import asyncio
import hashlib
import json
import os
import queue
import random
import time
import traceback
import urllib
import uuid
import aiohttp
import urllib.request
import urllib.parse
import collections
from concurrent.futures import ThreadPoolExecutor
from threading import Lock, Condition
import websockets
import threading
from .public import get_output, write_json_to_file, read_json_from_file, get_address, get_port, \
    generate_unique_client_id, get_port_from_cmdline, args, find_project_root, get_token,get_workflow
os.environ['http_proxy'] = ''
os.environ['https_proxy'] = ''
os.environ['no_proxy'] = '*'
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
executor = MonitoredThreadPoolExecutor(max_workers=20)
def print_exception_in_chinese(e):
    
    tb = traceback.extract_tb(e.__traceback__)
    if tb:
        filename, line_number, function_name, text = tb[-1]
        traceback.print_exception(type(e), e, e.__traceback__)
    else:
        pass
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
        if websocket_conn2 is not None and websocket_conn2.open:
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
    try:
        if prompt_id in result:
            result = result[prompt_id]
            status = result.get('status', {})
            if status.get('completed', False):
                result_data.append({"type": "str", "k": 'ok', "v": '1'})
                for output in result.get('outputs', {}).values():
                    for media in ['images', 'gifs', 'videos']:
                        if media in output:
                            for item in output[media]:
                                if 'filename' in item:
                                    if item['subfolder'] is not '':
                                        item['filename'] =  item['subfolder'] + '/' + item['filename']
                                    result_data.append({"type": 'images', "k": 'file', "v": (
                                                                                                args.output_directory if args.output_directory else find_project_root() + 'output') + '/' +
                                                                                            item['filename']})
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
    submit_url = 'https://tt.9syun.com/app/index.php?i=66&t=0&v=1.0&from=wxapp&tech_client=tt&tech_scene=990001&c=entry&a=wxapp&do=ttapp&r=comfyui.resultv2.formSubmitForComfyUi&m=tech_huise'
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
            if prompt_id and websocket_conn1 is not None and websocket_conn1.open == True:
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
            executor.submit(run_async_task, output, prompt_data, workflow,jilu_id)
        else:
            if websocket.open:
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
            task_queue_2.put({
                'type': 'send',
                'prompt_id': message_json['data']['prompt_id'],
            })
            pass
        if message_type == 'progress':
            pass
        if message_type == 'execution_cached' and 'prompt_id' in message_json['data']:
            task_queue_2.put({
                'type': 'send',
                'prompt_id': message_json['data']['prompt_id'],
            })
async def receive_messages(websocket, conn_identifier):
    
    if websocket.open:
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
            if websocket_conn1 is not None and websocket_conn1.open == True and websocket_conn2 is not None and websocket_conn2.open == True:
                await send_heartbeat_to_server2()
                pass
        except Exception as e:
            print_exception_in_chinese(e)
        finally:
            await asyncio.sleep(10)
def get_history():
    global last_get_history_time
    try:
        if websocket_conn2 is not None and websocket_conn2.open == True:
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
def get_filenames(directory):
    if os.path.exists(directory):
        all_entries = os.listdir(directory)
        all_entries = [name for name in all_entries if os.path.isfile(os.path.join(directory, name))]
        all_entries = [name.split('.')[0] for name in all_entries]
        return all_entries
    else:
        return []
send_time = '0'
def get_time():
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
async def send_heartbeat_to_server2():
    running, pending = optimized_process_history_data(history_data)
    try:
        file_names = get_filenames(find_project_root() + 'custom_nodes/ComfyUI_Bxb/config/json/api/')
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
                    if websocket_conn3 is not None and websocket_conn3.open and websocket_conn1 is not None and websocket_conn1.open:
                        websocket_info['data']['zhu_client_id'] = new_client_w_id
                        if websocket_info['conn_identifier'] == 1:
                            await websocket_conn3.send(json.dumps(websocket_info['data']))
            else:
                loop_num = loop_num + 1
                if loop_num > 100:
                    loop_num = 0
                    await websocket_conn3.send(json.dumps({
                        'time': get_time(),
                    }))
        except Exception as e:
            break
        finally:
            await asyncio.sleep(0.02)
def generate_md5_uid_timestamp_filename(original_filename):
    
    timestamp = str(time.time())
    random_number = str(generate_large_random_number(32))
    combined_string = original_filename + timestamp + random_number
    md5_hash = hashlib.md5(combined_string.encode('utf-8')).hexdigest()
    file_extension = os.path.splitext(original_filename)[1]
    filename = md5_hash + file_extension
    return filename
async def loca_download_image(url, filename):
    
    dir_name = find_project_root() + 'input'
    no_proxy_handler = urllib.request.ProxyHandler({})
    opener = urllib.request.build_opener(no_proxy_handler)
    file_new_name = generate_md5_uid_timestamp_filename(filename)
    try:
        response = opener.open(url)
        if response.getcode() == 200:
            full_path = os.path.join(dir_name, file_new_name)
            if os.path.exists(full_path):
                return {
                    'code': True,
                    'filename': file_new_name,
                }
            with open(full_path, 'wb') as f:
                f.write(response.read())
            return {
                'code': True,
                'filename': file_new_name,
            }
        else:
            return {
                'code': False,
                'filename': file_new_name,
            }
    except Exception as e:
        return {
            'code': False,
            'filename': file_new_name,
        }
def generate_large_random_number(num_bits):
    
    return random.getrandbits(num_bits)
def queue_prompt(prompt,workflow, new_client_id):
    try:
        if websocket_conn2 is not None and websocket_conn2.open:
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
async def process_json_elements(json_data, prompt_data,workflow, jilu_id):
    global websocket_conn1
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
    async def print_item(key, value):
        try:
            if value['class_type'] == 'KSampler' and 'inputs' in json_data[key]:
                json_data[key]['inputs']['seed'] = generate_large_random_number(15)
            if value['class_type'] == 'VHS_VideoCombine' and 'inputs' in json_data[key] and 'crf' in json_data[key][
                'inputs']:
                if json_data[key]['inputs']['crf'] == 0:
                    json_data[key]['inputs']['crf'] = 1
        except Exception as e:
            print_exception_in_chinese(e)
            websocket_queue.appendleft({
                "conn_identifier": 1,
                "data": {
                    'type': 'crystools.prompt_error',
                    'data': {
                        'jilu_id': jilu_id,
                        'msg': '发送指令失败3'
                    }
                },
            })
    tasks = [print_item(key, value) for key, value in json_data.items()]
    await asyncio.gather(*tasks)
    try:
        result = queue_prompt(json_data,workflow, new_client_w_id)
        if 'node_errors' in result:
            if result['node_errors']:
                raise Exception('发送指令失败')
        try:
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
        except Exception as e:
            print_exception_in_chinese(e)
        task_queue_3[result['prompt_id']] = {
            'jilu_id': jilu_id
        }
        return {
            'code': 1,
            'prompt_id': result['prompt_id']
        }
    except Exception as e:
        print_exception_in_chinese(e)
        websocket_queue.appendleft({
            "conn_identifier": 1,
            "data": {
                'type': 'crystools.prompt_error',
                'data': {
                    'jilu_id': jilu_id,
                    'msg': '发送指令失败3'
                }
            },
        })
        return {
            'code': 0,
            'prompt_id': jilu_id
        }
def run_async_task(json_data, prompt_data,workflow, jilu_id):
    return asyncio.run(process_json_elements(json_data, prompt_data, workflow,jilu_id))
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
    write_json_to_file(data, uniqueid + '.json', 'json/'+flow_type, 'json')
