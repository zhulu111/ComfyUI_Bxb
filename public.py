
import ast
import hashlib
import os
import json
import sys
import uuid
from io import StringIO
import re
from comfy.cli_args import parser
args = parser.parse_args()
if args and args.listen:
    pass
else:
    args = parser.parse_args([])
def get_address():
    return args.listen if args.listen != '0.0.0.0' else '127.0.0.1'
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
    base_url = find_project_root()+'custom_nodes/ComfyUI_Bxb/config/' + path
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
    
    base_url = find_project_root()+'custom_nodes/ComfyUI_Bxb/config/' + path
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
    output = read_json_from_file(uniqueid, path,'json')
    if output is not None:
        return output
    return None
def get_workflow(uniqueid, path='json/workflow/'):
    workflow = read_json_from_file(uniqueid, path,'json')
    if workflow is not None:
        return {
            'extra_data': {
                'extra_pnginfo': {
                    'workflow': workflow
                }
            }
        }
    return None
def get_token():
    techsid = read_json_from_file('techsid' + str(get_port_from_cmdline()) + '.txt', 'hash/','str')
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
    openid = read_json_from_file('openid' + str(get_port_from_cmdline()) + '.txt', 'hash/','str')
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
    script_directory = os.path.dirname(os.path.abspath(__file__))
    return script_directory + '../../../'
