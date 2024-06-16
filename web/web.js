import { app } from '../../../scripts/app.js'
import { api } from '../../../scripts/api.js'
import { ComfyWidgets } from '../../../scripts/widgets.js'
import { $el } from '../../../scripts/ui.js'

// 添加样式
const styleElement = document.createElement("style");
const cssCode = `
    #msgDiv{
      width:800px;
      height: 200px;
      text-align: center;
      font-size: 30px;
      display: flex;
      align-items: center;
      justify-content: center;
      padding-bottom: 40px;
      color: var(--fg-color);
    }
    #qrCode{
      display: block;
      width:256px;
      height:256px;
      border-radius: 10px;
    }
    #qrBox{
      display: block;
      text-align: center;
      display:flex;
      flex-wrap: wrap;
      justify-content: center;
      width: 360px;
    }
    #qrDesc{
      display: block;
      text-align: center;
      margin-top: 20px;
      color: #ffffff;
      width: 360px;
    }
    .codeImg {
      // display: block;
      width:256px;
      height:256px;
      border-radius: 10px;
      padding: 10px;
      border: 2px solid #ffffff;
    }
    .codeDesc {
      display: block;
      text-align: center;
      margin-top: 20px;
      color: #ffffff;
      width: 360px;
      font-size: 16px;
    }
    .codeDiv {
      color: #ffffff;
    }
    .codeBox {
      display: flex;
      text-align: center;
    }
    #directions{
      margin-top: 10px;
      width: 100%;
      text-align: left;
      color: #ffffff;
      font-size: 8px;
    }
    .tech_button {
      flex:1;
      height:30px;
      border-radius: 8px;
      border: 2px solid var(--border-color);
      font-size:11px;
      background:var(--comfy-input-bg);
      color:var(--error-text);
      box-shadow:none;
      cursor:pointer;
      width: 1rem;
    }
    #tech_box {
      max-height: 80px;
      display:flex;
      flex-wrap: wrap;
      align-items: flex-start;
    }
    .uniqueid {
      display: none;
    }
    #showMsgDiv {
      width:800px;
      padding: 60px 0;
      text-align: center;
      font-size: 30px;
      color: var(--fg-color);
    }
`
styleElement.innerHTML = cssCode
document.head.appendChild(styleElement);

var techsidkey = 'techsid'+window.location.port;
var loading = false;
const msgBox = $el("div.comfy-modal", { parent: document.body }, []);
const msgDiv = $el('div', {id:'msgDiv'},'');
msgBox.appendChild(msgDiv);
msgBox.style.display = "none";
msgBox.style.zIndex = 10001;

function setCookie(name, value, days=1) {
    var expires = "";
    if (days) {
        var date = new Date();
        date.setTime(date.getTime() + (days * 24 * 60 * 60 * 1000));
        expires = "; expires=" + date.toUTCString();
    }
    document.cookie = name + "=" + (value || "") + expires + "; path=/";
}
function getCookie(name) {
    var nameEQ = name + "=";
    var ca = document.cookie.split(';');
    for(var i = 0; i < ca.length; i++) {
        var c = ca[i];
        while (c.charAt(0) == ' ') c = c.substring(1, c.length);
        if (c.indexOf(nameEQ) == 0) return c.substring(nameEQ.length, c.length);
    }
    return '';
}


function generateTimestampedRandomString() {
    const timestamp = Date.now().toString();
    const randomString = Math.random().toString(36).substring(2, 18);
    const timestampedRandomString = (timestamp + randomString).substring(0, 32);
    return timestampedRandomString;
}


function showLoading(msg='') {
  hideLoading();
  msgDiv.innerText = msg ? msg : '请稍后...';
  msgBox.style.display = "block";
  loading = true;
}

function hideLoading() {
  msgBox.style.display = "none";
  loading = false;
}

function showToast(msg='', t=0) {
  t = t > 0 ? t : 2000;
  msgDiv.innerText = msg ? msg : '谢谢';
  msgBox.style.display = "block";
  setTimeout(()=> {
    msgBox.style.display = "none";
  }, t);
}
var serverUrl = window.location.href;
const qrCode = $el('img',{id:'qrCode',src:``,
          onerror:()=>{
            // console.log('参数错误');
          }
      })
const qrDesc = $el('div',{id:'qrDesc'},'请用微信扫码，验证身份...')
const qrBox = $el('div',{id:'qrBox'},[qrCode, qrDesc])
app.ui.dialog.element.style.zIndex = 10010;

const showMsgDiv = $el('div',{id:'showMsgDiv'},'请稍后...')

function showCodeBox(list) {
  app.ui.dialog.close();
  let listn = [];
  for (let i = 0; i < list.length; i++) {
    listn.push($el('div.codeDiv',{},[$el('img.codeImg',{src:list[i].code}), $el('div.codeDesc',{},list[i].desc)]))
  }
  const codeBox = $el('div.codeBox',{},listn)
  app.ui.dialog.show(codeBox);
}


function showQrBox(img, desc) {
  app.ui.dialog.close();
  qrDesc.innerText = desc;
  qrCode.src = img;
  app.ui.dialog.show(qrBox);
}

function hideCodeBox() {
  app.ui.dialog.close();
}

function showMsg(msg) {
  app.ui.dialog.close();
  showMsgDiv.innerText = msg;
  app.ui.dialog.show(showMsgDiv);
}


function hideMsg() {
  app.ui.dialog.close();
}

function tech_alert(text) {
  loading = false;
  // alert(text);
  showMsg(text);
}

function getPostData(prompt) {
  const output = prompt['output'];
  let HuiseNum = 0;
  let HuiseO = {};
  let HuiseN = {};
  let postData = {};
  let saveImageNodes = [];
  for (const key in output) {
    if(output[key].class_type == 'sdBxb') {
      HuiseO = output[key].inputs;
      HuiseNum++;
    }
    if(output[key].class_type == 'SaveImage') {
      output[key].res_node = key;
      saveImageNodes.push(output[key]);
    }
  }
  if(HuiseNum > 1) {
    return('工作流中只可以存在1个“SD变现宝”节点'); 
  }
  if(saveImageNodes.length < 1) {
    return('请确保工作流中有且仅有1个“SaveImgae”或“保存图像”节点，目前有'+saveImageNodes.length+'个'); 
  } else if(saveImageNodes.length > 1) {
    return('请确保工作流中有且仅有1个“SaveImgae”或“保存图像”节点，目前有'+saveImageNodes.length+'个'); 
  } else {
    postData['res_node'] = saveImageNodes[0].res_node;
  }
  if(HuiseO) {
    HuiseN['zhutu1'] = HuiseO['app_img1(optional)'];
    HuiseN['zhutu2'] = HuiseO['app_img2(optional)'];
    HuiseN['zhutu3'] = HuiseO['app_img3(optional)'];
    HuiseN['cs_img1'] = HuiseO['custom_img1(optional)'];
    HuiseN['cs_img2'] = HuiseO['custom_img2(optional)'];
    HuiseN['cs_img3'] = HuiseO['custom_img3(optional)'];
    HuiseN['cs_text1'] = HuiseO['custom_text1(optional)'];
    HuiseN['cs_text2'] = HuiseO['custom_text2(optional)'];
    HuiseN['cs_text3'] = HuiseO['custom_text3(optional)'];
    HuiseN['title'] = HuiseO['app_title'];
    HuiseN['gn_desc'] = HuiseO['app_desc'];
    HuiseN['sy_desc'] = '作品使用说明';
    HuiseN['server'] = serverUrl;
    HuiseN['fee'] = HuiseO['app_fee'];
    HuiseN['cs_img1_desc'] = HuiseO['custom_img1_desc'];
    HuiseN['cs_img2_desc'] = HuiseO['custom_img2_desc'];
    HuiseN['cs_img3_desc'] = HuiseO['custom_img3_desc'];
    HuiseN['cs_text1_desc'] = HuiseO['custom_text1_desc'];
    HuiseN['cs_text2_desc'] = HuiseO['custom_text2_desc'];
    HuiseN['cs_text3_desc'] = HuiseO['custom_text3_desc'];
    HuiseN['uniqueid'] = HuiseO['uniqueid'];
    postData['zhutus'] = [];
    if(HuiseN['zhutu1']) {
      if(output[HuiseN['zhutu1'][0]].class_type == 'LoadImage') {
        if(output[HuiseN['zhutu1'][0]].inputs.image) {
          postData['zhutus'].push(output[HuiseN['zhutu1'][0]].inputs.image);
        }
      } else {
        return('作品主图只可以连接“加载图像”节点');
      }
    }
    if(HuiseN['zhutu2']) {
      if(output[HuiseN['zhutu2'][0]].class_type == 'LoadImage') {
        if(output[HuiseN['zhutu2'][0]].inputs.image) {
          postData['zhutus'].push(output[HuiseN['zhutu2'][0]].inputs.image);
        }
      } else {
        return('作品主图只可以连接“加载图像”节点');
      }
    }
    if(HuiseN['zhutu3']) {
      if(output[HuiseN['zhutu3'][0]].class_type == 'LoadImage') {
        if(output[HuiseN['zhutu3'][0]].inputs.image) {
          postData['zhutus'].push(output[HuiseN['zhutu3'][0]].inputs.image);
        }
      } else {
        return('作品主图只可以连接“加载图像”节点');
      }
    }

    postData['cs_img_nodes'] = [];
    if(HuiseN['cs_img1']) {
      if(output[HuiseN['cs_img1'][0]].class_type == 'LoadImage') {
        postData['cs_img_nodes'].push({node: HuiseN['cs_img1'][0], desc: HuiseN['cs_img1_desc']});
      } else {
        return('用户自定义图片只可以连接“加载图像”节点');
      }
    }
    if(HuiseN['cs_img2']) {
      if(output[HuiseN['cs_img2'][0]].class_type == 'LoadImage') {
        postData['cs_img_nodes'].push({node: HuiseN['cs_img2'][0], desc: HuiseN['cs_img2_desc']});
      } else {
        return('用户自定义图片只可以连接“加载图像”节点');
      }
    }
    if(HuiseN['cs_img3']) {
      if(output[HuiseN['cs_img3'][0]].class_type == 'LoadImage') {
        postData['cs_img_nodes'].push({node: HuiseN['cs_img3'][0], desc: HuiseN['cs_img3_desc']});
      } else {
        return('用户自定义图片只可以连接“加载图像”节点');
      }
    }

    postData['cs_text_nodes'] = [];
    if(HuiseN['cs_text1']) {
      if(typeof output[HuiseN['cs_text1'][0]].inputs !== 'undefined' && typeof output[HuiseN['cs_text1'][0]].inputs.text !== 'undefined') {
        postData['cs_text_nodes'].push({node: HuiseN['cs_text1'][0], desc: HuiseN['cs_text1_desc']});
      } else {
        return('用户自定义文本只可以连接“文本输入”节点');
      }
    }
    if(HuiseN['cs_text2']) {
      if(typeof output[HuiseN['cs_text2'][0]].inputs !== 'undefined' && typeof output[HuiseN['cs_text2'][0]].inputs.text !== 'undefined') {
        postData['cs_text_nodes'].push({node: HuiseN['cs_text2'][0], desc: HuiseN['cs_text2_desc']});
      } else {
        return('用户自定义文本只可以连接“文本输入”节点');
      }
    }
    if(HuiseN['cs_text3']) {
      if(typeof output[HuiseN['cs_text3'][0]].inputs !== 'undefined' && typeof output[HuiseN['cs_text3'][0]].inputs.text !== 'undefined') {
        postData['cs_text_nodes'].push({node: HuiseN['cs_text3'][0], desc: HuiseN['cs_text3_desc']});
      } else {
        return('用户自定义文本只可以连接“文本输入”节点');
      }
    }
    if(HuiseN['title']) {
      postData['title'] = HuiseN['title'];
    } else {
      return('请填写作品标题');
    }
    if(HuiseN['gn_desc']) {
      postData['gn_desc'] = HuiseN['gn_desc'];
    } else {
      return('请填写作品功能介绍');
    }
    if(HuiseN['sy_desc']) {
      postData['sy_desc'] = HuiseN['sy_desc'];
    } else {
      return('请填写作品使用说明');
    }
    if(HuiseN['server']) {
      postData['server'] = HuiseN['server'];
    } else {
      return('程序运行出错，请联系管理员');
    }
    if(HuiseN['fee'] >= 10) {
      postData['fee'] = HuiseN['fee'];
    } else {
      return('作品服务单价不能小于0.1元');
    }
    postData['uniqueid'] = HuiseN['uniqueid'];
    postData['output'] = output;
    return postData;
  }
}

async function requestExe(r, postData) {
  var techsid = getCookie(techsidkey);
  const response = await api.fetchApi(`/manager/tech_zhulu`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      r: r,
      techsid: techsid,
      postData: postData
    })
  });
  if (!response.ok) {
    setTimeout(()=> {
      showToast('网络连接出错，请保持电脑联网', 3000);
    }, 300);
    return;
  }
  const resdata = await response.json();
  return resdata;
}

async function login(s_key) {
  let res = await requestExe('comfyui.index.code', {s_key: s_key});
  if(app.ui.dialog.element.style.display != 'none') {
    if(res.data.data.techsid.length > 5) {
      return res.data.data.techsid;
    } else {
      await new Promise(resolve => setTimeout(resolve, 800));
      return await login(s_key);
    }
  } else {
    return;
  }}



async function request(r, postData) {
  showLoading('处理中，请稍后...');
  let resdata = await requestExe(r, postData);
  if(resdata.errno == 41009) {
    let resdata = await requestExe('comfyui.index.code', {s_key: ''});
    if(resdata) {
      if (resdata.data.data.code == 1) {
        hideLoading();
        showQrBox(resdata.data.data.data, resdata.data.data.desc);
        let techsid = await login(resdata.data.data.s_key);
        hideCodeBox();
        if(techsid) {
          setCookie(techsidkey, techsid);
          return await request(r, postData);
        } else {
          return;
        }
      } else {
        showToast(resdata.data.data.message);
        return;
      }
    }
  } else {
    hideLoading();
    return resdata;
  }
}

app.registerExtension({
  name: 'sdBxb',
  async beforeRegisterNodeDef (nodeType, nodeData, app) {
    if (nodeData.name === 'sdBxb') {

      const onNodeCreated = nodeType.prototype.onNodeCreated;
      nodeType.prototype.onNodeCreated = function () {
        const r = onNodeCreated ? onNodeCreated?.apply(this, arguments) : undefined;
        const that = this;
        const zhanweiIndex = this.widgets.findIndex((w) => w.name === "zhanwei");
        const tech_button = $el('button.tech_button',{textContent: '点此，工作流转小程序，并获取访问地址',style:{},
          onclick:async ()=>{
            if(loading) return;
            hideCodeBox();
            try {
              const prompt = await app.graphToPrompt()
              let postData = getPostData(prompt);
              if(postData['output']) {
                try {
                  let resdata = await request('comfyui.index.upload', postData);
                  if(resdata) {
                    if (resdata.data.data.code == 1) {
                      showCodeBox(resdata.data.data.list);
                    } else {
                      // showToast(resdata.data.data.message);            
                      showMsg(resdata.data.data.message);
                    }
                  }
                } catch (error) {
                  hideLoading();
                }
              } else {
                tech_alert(postData);
                return;
              }
            } catch (error) {
              tech_alert('获取api数据失败');
              return;
            }
          }}
        )
        const dstr1 = '1、每创建一个新的“SD变现宝”节点，就对应一个新的作品；';
        const dstr2 = '2、如有问题，请加入SD变现宝商家QQ群：967073981';
        const directions = $el('div',{id:'directions'},['特殊说明：',$el('br'),dstr1,$el('br'),dstr2])
        const tech_box = $el('div',{id:'tech_box'},[tech_button, directions])
        this.addDOMWidget('select_styles',"btn", tech_box);

        const inputEl = document.createElement("input");
        inputEl.setAttribute("type", "text");
        inputEl.setAttribute("list", "uedynamiclist");
        inputEl.setAttribute("value", generateTimestampedRandomString());
        inputEl.className = "uniqueid";
        this.addDOMWidget('uniqueid', "input", inputEl, {
            getValue() { return inputEl.value; },
            setValue(v) { inputEl.value = v; },
        });
        setTimeout(() => {
            this.setSize([420, 500]);
            // if(serverUrl) {
            //   this.widgets[3].value = serverUrl;
            // }
            // if(this.widgets[16].value == '.*') {
            //   this.widgets[16].value = generateTimestampedRandomString();
            // }
            // console.log(this.widgets[16].value);
        }, 200)


        return r;
      }
      this.serialize_widgets = true //需要保存参数
    }
  }
})


// app.registerExtension({
//   name: "Huise.menu",
//   async setup() {

//     const menu = document.querySelector(".comfy-menu");
//     const huiseButton = document.createElement("button");
//     huiseButton.textContent = "绘色管理";
//     huiseButton.style.background = "linear-gradient(90deg, #00C9FF 0%, #92FE9D 100%)";
//     huiseButton.style.color = "black";
//     huiseButton.onclick = () => {
//         if(!manager_instance)
//           setManagerInstance(new ManagerMenuDialog());
//         manager_instance.show();
//       }
//     menu.append(huiseButton);

//   },
// });
