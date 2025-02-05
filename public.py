import hashlib
import os
import numpy as np
import aiohttp
import folder_paths
from PIL import Image
import traceback
import json
import sys
import uuid
from io import StringIO, BytesIO
import re
import requests
from comfy.cli_args import parser
import urllib
import urllib.request
import urllib.parse
import filetype
args = parser.parse_args()
if args and args.listen:
    pass
else:
    args = parser.parse_args([])
import time
import random
from urllib.parse import urlparse
try:
    resample_filter = Image.Resampling.LANCZOS
except AttributeError:
    resample_filter = Image.ANTIALIAS
def get_address():
    return args.listen if '0.0.0.0' not in args.listen else '127.0.0.1'
def get_port():
    return args.port
VERSION = '2.0.0'
def write_key_value(key, value, string_io=None):
    
    if string_io is None:
        string_io = StringIO()
        json.dump({key: value}, string_io)
    else:
        string_io.seek(0)
        data = json.load(string_io)
        data[key] = value
        string_io.seek(0)
        string_io.truncate()
        json.dump(data, string_io)
    return string_io
def get_value_by_key(key, string_io):
    
    string_io.seek(0)
    data = json.load(string_io)
    return data.get(key)
def delete_key(key, string_io):
    
    string_io.seek(0)
    data = json.load(string_io)
    if key in data:
        del data[key]
    string_io.seek(0)
    string_io.truncate()
    json.dump(data, string_io)
    return string_io
def read_json_from_file(name, path='json/', type_1='json'):
    base_url = find_project_custiom_nodes_path() + 'ComfyUI_Bxb/config/' + path
    if not os.path.exists(base_url + name):
        return None
    with open(base_url + name, 'r') as f:
        data = f.read()
        if data == '':
            return None
        if type_1 == 'json':
            try:
                data = json.loads(data)
                return data
            except ValueError as e:
                return None
        if type_1 == 'str':
            return data
def write_json_to_file(data, name, path='json/', type_1='str'):
    
    base_url = find_project_custiom_nodes_path() + 'ComfyUI_Bxb/config/' + path
    if not os.path.exists(base_url):
        os.makedirs(base_url)
    if type_1 == 'str':
        str_data = str(data)
        with open(base_url + name, 'w') as f:
            f.write(str_data)
    elif type_1 == 'json':
        with open(base_url + name, 'w') as f:
            json.dump(data, f, indent=2)
def get_output(uniqueid, path='json/api/'):
    output = read_json_from_file(uniqueid, path, 'json')
    if output is not None:
        return output
    return None
def get_workflow(uniqueid, path='json/workflow/'):
    workflow = read_json_from_file(uniqueid, path, 'json')
    if workflow is not None:
        return {
            'extra_data': {
                'extra_pnginfo': {
                    'workflow': workflow
                }
            }
        }
    return None
def delete_workflow(uniqueid):
    root_path = find_project_custiom_nodes_path() + 'ComfyUI_Bxb/config/json/'
    if os.path.exists(root_path + 'workflow/' + uniqueid + '.json'):
        os.remove(root_path + 'workflow/' + uniqueid + '.json')
    if os.path.exists(root_path + 'api/' + uniqueid + '.json'):
        os.remove(root_path + 'api/' + uniqueid + '.json')
def get_token():
    techsid = read_json_from_file('techsid' + str(get_port_from_cmdline()) + '.txt', 'hash/', 'str')
    if techsid is not None:
        return techsid
    else:
        return 'init'
    pass
def set_token(token):
    write_json_to_file(token, 'techsid' + str(get_port_from_cmdline()) + '.txt', 'hash/')
def set_openid(token):
    write_json_to_file(token, 'openid' + str(get_port_from_cmdline()) + '.txt', 'hash/')
def get_openid():
    openid = read_json_from_file('openid' + str(get_port_from_cmdline()) + '.txt', 'hash/', 'str')
    if openid is not None:
        return openid
    else:
        return 'init'
    pass
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
    return 8188
def get_version():
    return VERSION
def get_mac_address():
    mac = uuid.getnode()
    return ':'.join(('%012X' % mac)[i:i + 2] for i in range(0, 12, 2))
def generate_unique_client_id(port):
    unique_key = f"{get_mac_address()}:{port}"
    hash_object = hashlib.sha256(unique_key.encode())
    subdomain = hash_object.hexdigest()[:12]
    return subdomain
def find_project_root():
    absolute_path = folder_paths.base_path
    if not absolute_path.endswith(os.sep):
        absolute_path += os.sep
    return absolute_path
def find_project_custiom_nodes_path():
    absolute_path = folder_paths.folder_names_and_paths["custom_nodes"][0][0]
    if not absolute_path.endswith(os.sep):
        absolute_path += os.sep
    return absolute_path
def find_project_bxb():
    script_directory = os.path.dirname(os.path.abspath(__file__))
    absolute_path = os.path.abspath(script_directory)
    if not absolute_path.endswith(os.sep):
        absolute_path += os.sep
    return absolute_path
def get_base_url():
    return 'https://tt.9syun.com/app/index.php?i=66&t=0&v=1.0&from=wxapp&tech_client=sj&c=entry&a=wxapp&do=ttapp&m=tech_huise&r='
def get_filenames(directory):
    if os.path.exists(directory):
        all_entries = os.listdir(directory)
        all_entries = [name for name in all_entries if os.path.isfile(os.path.join(directory, name))]
        all_entries = [name.split('.')[0] for name in all_entries]
        return all_entries
    else:
        return []
def read_json_file(url):
    try:
        session = requests.Session()
        session.trust_env = False
        session.proxies = {'http': None, 'https': None}
        response = session.get(url)
        response.raise_for_status()
        response.encoding = 'utf-8'
        json_text = response.text.strip().lstrip('\ufeff')
        json_content = json.loads(json_text)
        return json_content
    except requests.exceptions.RequestException as e:
        return None
    except json.JSONDecodeError as e:
        return None
def generate_md5_uid_timestamp_filename(original_filename, name_type=0):
    
    timestamp = str(time.time())
    random_number = str(generate_large_random_number(32))
    combined_string = original_filename + timestamp + random_number
    md5_hash = hashlib.md5(combined_string.encode('utf-8')).hexdigest()
    file_extension = os.path.splitext(original_filename)[1]
    if name_type == 1:
        filename = hashlib.md5(original_filename.encode('utf-8')).hexdigest() + file_extension
    else:
        filename = md5_hash + file_extension
    return filename
def generate_md5_uid_timestamp(original_filename):
    
    timestamp = str(time.time())
    random_number = str(generate_large_random_number(32))
    combined_string = original_filename + timestamp + random_number
    md5_hash = hashlib.md5(combined_string.encode('utf-8')).hexdigest()
    filename = md5_hash
    return filename
def generate_large_random_number(num_bits):
    
    return random.getrandbits(num_bits)
def async_download_image(url, filename, name_type=0):
    
    dir_name = folder_paths.get_input_directory()
    no_proxy_handler = urllib.request.ProxyHandler({})
    opener = urllib.request.build_opener(no_proxy_handler)
    if name_type != 0:
        file_new_name = generate_md5_uid_timestamp_filename(filename, 1)
    else:
        file_new_name = generate_md5_uid_timestamp_filename(filename)
    try:
        full_path = os.path.join(dir_name, file_new_name)
        if os.path.exists(full_path):
            return {
                'code': True,
                'filename': file_new_name,
            }
        response = opener.open(url)
        if response.getcode() == 200:
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
async def loca_download_image(url, filename, name_type=0):
    
    dir_name = folder_paths.get_input_directory()
    no_proxy_handler = urllib.request.ProxyHandler({})
    opener = urllib.request.build_opener(no_proxy_handler)
    if name_type != 0:
        file_new_name = generate_md5_uid_timestamp_filename(filename, 1)
    else:
        file_new_name = generate_md5_uid_timestamp_filename(filename)
    try:
        full_path = os.path.join(dir_name, file_new_name)
        if os.path.exists(full_path):
            return {
                'code': True,
                'filename': file_new_name,
            }
        response = opener.open(url)
        if response.getcode() == 200:
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
def determine_file_type(file_path):
    kind = filetype.guess(file_path)
    if kind:
        mime_type = kind.mime
        if mime_type.startswith('video/'):
            return mime_type, 'video'
        elif mime_type.startswith('image/'):
            return mime_type, 'image'
        else:
            return mime_type, 'unknown'
    return False, 'unknown'
def print_exception_in_chinese(e):
    
    tb = traceback.extract_tb(e.__traceback__)
    if tb:
        filename, line_number, function_name, text = tb[-1]
        for i, (fn, ln, func, txt) in enumerate(tb, 1):
            print(f"    {txt.strip()}")
        traceback.print_exception(type(e), e, e.__traceback__)
    else:
        pass
def remove_query_parameters(url):
    parsed_url = urlparse(url)
    url_without_params = parsed_url._replace(query="").geturl()
    return url_without_params
def load_image(image_info):
    
    if image_info['type'] == 'path':
        return Image.open(image_info['content'])
    elif image_info['type'] == 'binary':
        return Image.open(BytesIO(image_info['content']))
    else:
        raise ValueError("Unknown image type. Supported types are 'path' and 'binary'.")
def resize_image(image, target_width):
    
    width_percent = (target_width / float(image.size[0]))
    height_size = int((float(image.size[1]) * float(width_percent)))
    return image.resize((target_width, height_size), resample_filter)
def resize_images(image_info_list, target_width=600):
    
    return [resize_image(load_image(img_info), target_width) for img_info in image_info_list]
def calculate_canvas_size_for_single_canvas(layouts):
    
    max_width = 0
    total_height = 0
    for _, (x, y), img in layouts:
        img_width, img_height = img.size
        max_width = max(max_width, img_width + x)
        total_height = max(total_height, img_height + y)
    return max_width, total_height
def calculate_layout(images, target_width=1200):
    
    layouts = []
    current_canvas_index = 0
    quadrant_positions = [
        (target_width, 0),
        (0, 0),
        (0, target_width),
        (target_width, target_width)
    ]
    quadrant_used = [False, False, False, False]
    remaining_images = images[:]
    ii = 0
    while remaining_images:
        ii = ii + 1
        img = remaining_images.pop(0)
        img_width, img_height = img.size
        placed = False
        if ii > 100:
            break;
        for i in range(4):
            if not quadrant_used[i]:
                x, y = quadrant_positions[i]
                if img_height <= target_width:
                    layouts.append((current_canvas_index, (x, y), img))
                    quadrant_used[i] = True
                    placed = True
                    break
                else:
                    if i in [0, 3] and quadrant_used[0] == False and quadrant_used[3] == False:
                        quadrant_used[0] = True
                        quadrant_used[3] = True
                        placed = True
                    elif i in [1, 2] and quadrant_used[1] == False and quadrant_used[2] == False:
                        quadrant_used[1] = True
                        quadrant_used[2] = True
                        placed = True
        if not placed:
            remaining_images.append(img)
            if all(quadrant_used):
                current_canvas_index += 1
                quadrant_used = [False, False, False, False]
    return layouts, current_canvas_index + 1
def group_images_by_height(images):
    
    sorted_images = sorted(images, key=lambda img: img.size[1], reverse=True)
    groups = []
    if len(sorted_images) % 2 != 0:
        groups.append((sorted_images.pop(0),))
    while len(sorted_images) > 1:
        groups.append((sorted_images.pop(0), sorted_images.pop(-1)))
    return groups
def draw_final_groups(final_groups):
    
    binary_resources = []
    for group_list in final_groups:
        total_width = sum(group['canvas_width'] for group in group_list)
        max_height = max(group['canvas_height'] for group in group_list)
        canvas = Image.new('RGB', (total_width, max_height), (255, 255, 255))
        current_x = 0
        for group in group_list:
            images = group['images']
            canvas_width = group['canvas_width']
            canvas_height = group['canvas_height']
            if len(images) == 3:
                img1, img2, img3 = images
                combined_width = max(img1.size[0], img2.size[0], img3.size[0])
                combined_height = img1.size[1] + img2.size[1] + img3.size[1]
                combined_canvas = Image.new('RGB', (combined_width, combined_height), (255, 255, 255))
                combined_canvas.paste(img1, (0, 0))
                combined_canvas.paste(img2, (0, img1.size[1]))
                combined_canvas.paste(img3, (0, img1.size[1] + img2.size[1]))
                canvas.paste(combined_canvas, (current_x, 0))
            elif len(images) == 2:
                img1, img2 = images
                combined_height = img1.size[1] + img2.size[1]
                combined_canvas = Image.new('RGB', (canvas_width, combined_height), (255, 255, 255))
                combined_canvas.paste(img1, (0, 0))
                combined_canvas.paste(img2, (0, img1.size[1]))
                canvas.paste(combined_canvas, (current_x, 0))
            elif len(images) == 1:
                img = images[0]
                if isinstance(img, tuple) and len(img) == 2:
                    img1, img2 = img
                    combined_height = img1.size[1] + img2.size[1]
                    combined_canvas = Image.new('RGB', (canvas_width, combined_height), (255, 255, 255))
                    combined_canvas.paste(img1, (0, 0))
                    combined_canvas.paste(img2, (0, img1.size[1]))
                    canvas.paste(combined_canvas, (current_x, 0))
                else:
                    canvas.paste(img, (current_x, 0))
            current_x += canvas_width
        img_byte_arr = BytesIO()
        canvas.save(img_byte_arr, format='JPEG', quality=70)
        img_byte_arr = img_byte_arr.getvalue()
        binary_resources.append(img_byte_arr)
    return binary_resources
def combine_images(image_info_list, target_width=600, _format='PNG'):
    images = resize_images(image_info_list, target_width)
    grouped_images = group_images_by_height(images)
    groups = grouped_images[:]
    final_groups = []
    final_group = None
    if len(groups) % 3 != 0:
        final_group = groups[-(len(groups) % 3):]
        groups_p = groups[:-(len(groups) % 3)]
    else:
        groups_p = groups
    final_groups_arr = [{'images': groups_p[i:i + 3]} for i in range(0, len(groups_p), 3)]
    for key, group2 in enumerate(final_groups_arr):
        canvas_info = []
        for index, group in enumerate(group2['images']):
            max_height = []
            for img in group:
                img_width, img_height = img.size
                max_height.append(img_height)
            canvas_info.append({
                'canvas_width': 600,
                'canvas_height': sum(max_height),
                'images': group,
            })
        final_groups.append(canvas_info)
    if final_group:
        canvas_info = []
        for index, group in enumerate(final_group):
            max_height = []
            max_width = 0
            for img in group:
                max_width += 1
                img_width, img_height = img.size
                max_height.append(img_height)
            canvas_info.append({
                'canvas_width': 600,
                'canvas_height': sum(max_height),
                'images': group,
            })
        final_groups.append(canvas_info)
    binary_canvases = draw_final_groups(final_groups)
    return binary_canvases
def is_aspect_ratio_within_limit(width, height, limit=4):
    
    long_side = max(width, height)
    short_side = min(width, height)
    return (long_side / short_side) <= limit
async def get_upload_url(data, techsid, session, path=1):
    form_data = aiohttp.FormData()
    form_data.add_field('json_data', json.dumps(data))
    if path == 1:
        upload_url = get_base_url() + 'upload.tencent.generateSignedUrl&techsid=we7sid-' + techsid
    else:
        upload_url = get_base_url() + 'upload.tencent.getPresign&cid=' + techsid
    async with session.post(upload_url, data=form_data) as response:
        try:
            response_result = await response.text()
            result = json.loads(response_result)
            return result
        except json.JSONDecodeError as e:
            return None
async def send_binary_data(session, upload_url, file_path, is_binary=False, mime_type='image/png'):
    headers = {
        'Content-Type': mime_type,
    }
    if is_binary:
        binary_data = file_path
    else:
        with open(file_path, 'rb') as file:
            binary_data = file.read()
    async with session.put(upload_url, data=binary_data, headers=headers) as response:
        if response.status == 200:
            return True
        else:
            return False
def send_binary_data_async(upload_url, file_path, is_binary=False, mime_type='image/png'):
    headers = {
        'Content-Type': mime_type,
    }
    try:
        if is_binary:
            binary_data = file_path
        else:
            with open(file_path, 'rb') as file:
                binary_data = file.read()
        session = requests.Session()
        session.trust_env = False
        session.proxies = {'http': None, 'https': None}
        response = session.put(upload_url, data=binary_data, headers=headers)
        if response.status_code == 200:
            return True, ''
        else:
            error_message = f"Error uploading file. Status code: {response.status_code}, Reason: {response.reason}, Response text: {response.text}"
            return False, error_message
    except Exception as e:
        error_message = f"An error occurred while uploading the file: {str(e)}"
        return False, error_message
def merge_alpha_channels(a_img_path, b_img_path):
    a_img = Image.open(a_img_path).convert("RGBA")
    b_img = Image.open(b_img_path).convert("RGBA")
    b_a_channel = np.array(b_img)[:, :, 3]
    a_img = a_img.resize(b_img.size, resample_filter)
    a_img_data = np.array(a_img)
    a_img_data[:, :, 3] = np.where(b_a_channel == 255, 0, a_img_data[:, :, 3])
    base_name = os.path.basename(a_img_path)
    c_img_path = os.path.join(os.path.dirname(a_img_path), f"new_{base_name}.png")
    new_a_img = Image.fromarray(a_img_data)
    new_a_img.save(c_img_path, format="PNG")
    return c_img_path
