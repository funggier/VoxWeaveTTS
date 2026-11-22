/* Distinct Browser/LAN, Live Listener and optional Remote Desktop API. */
"use strict";
const assert=require("node:assert/strict");
const fs=require("node:fs");
const vm=require("node:vm");
const path=require("node:path");
const root=path.resolve(__dirname,"..");
const html=fs.readFileSync(path.join(root,"web/index.html"),"utf8");
const js=fs.readFileSync(path.join(root,"web/runtime_ui.js"),"utf8");
for(const name of [
  "networkBrowserSection","networkWebState","networkWebBind",
  "networkWebUsername","networkBrowserUrl","networkCopyBrowserUrl",
  "networkListenSection","runtimeListenLink","networkListenerState",
  "networkListenerSave","networkRemoteSection","networkRemoteEnabled",
  "networkControlPort","networkListenerPort","networkSave"
]){
  assert.equal(html.split('id="'+name+'"').length-1,1,name+" must be unique");
}
assert(html.includes("ควบคุม Server ผ่าน Browser ใน LAN"));
assert(html.includes("Remote Desktop Client API — ตัวเลือกขั้นสูง"));
assert(html.includes("ไม่ต้องเปิด Remote Desktop Client API"));
assert(!html.includes('id="networkApiPort"'),"Core port must not be editable via Remote settings");

const nodes=new Map();
function makeNode(id=""){
  const handlers={};
  return {
    id, textContent:"",value:"",href:"",hidden:false,disabled:false,
    options:[], checked:false, type:"text", handlers,
    addEventListener(type,fn){handlers[type]=fn},
    replaceChildren(...items){this.options=items},
  };
}
const get=id=>{
  if(!nodes.has(id))nodes.set(id,makeNode(id));
  return nodes.get(id);
};
for(const key of ["networkRemoteEnabled"])get(key).type="checkbox";
for(const key of ["networkListenerPort","networkControlPort"])get(key).type="number";
get("runtimeAudioOutput").options=[];

const docs={
  "/v1/runtime/state":{
    mode:"computer",output:"default",worker_running:true,available_outputs:[
      {id:"default",label:"Windows default output"}
    ],
    audio_settings:{sample_rate:"auto",channels:"auto",buffer_ms:50},
    sources:{},job_states:{},pending_source_messages:0,
    max_outstanding_jobs:14,completed:0,failed:0
  },
  "/v1/network/overview":{
    web:{bind_host:"0.0.0.0",port:8775,bind_mode:"all_ipv4",username:"voxweave",
      lan_enabled:true,url:"http://192.168.1.165:8775/",url_is_estimate:true},
    listener:{running:true,bind_host:"0.0.0.0",port:8766,error:null},
    remote:{enabled:false,port:null,bind_host:null,error:null},
  },
  "/v1/network/settings":{
    username:"voxweave",control_host:"0.0.0.0",control_port:8776,
    remote_enabled:false,listener_host:"0.0.0.0",listener_port:8766,
    api_port:8775,password_configured:false
  },
};
const posts=[];
const copied=[];
const fetch=async(url,options={})=>{
  if(options.method==="POST"){
    const body=JSON.parse(options.body);
    posts.push({url,body,intent:options.headers["X-VoxWeaveTTS-Intent"]});
    if(url==="/v1/network/settings"){
      Object.assign(docs[url],body);
      return {ok:true,json:async()=>({restart_required:true})};
    }
    return {ok:true,json:async()=>docs["/v1/runtime/state"]};
  }
  return {ok:true,json:async()=>docs[url]};
};
const document={
  getElementById:get,activeElement:null,
  createElement(){return makeNode()},
  querySelectorAll(){return []},
  addEventListener(){},
};
const window={
  setInterval(){return 1},
  addEventListener(){},
};
vm.runInNewContext(js,{
  window,document,fetch,
  navigator:{clipboard:{writeText:async x=>copied.push(x)}},
  console,Number,String,Boolean,Object,Array,
},{filename:"runtime_ui.js"});
const tick=()=>new Promise(resolve=>setTimeout(resolve,35));
(async()=>{
  await tick();
  assert.equal(get("networkWebBind").textContent,"0.0.0.0:8775");
  assert.equal(get("networkWebUsername").textContent,"voxweave");
  assert.equal(get("networkBrowserUrl").href,"http://192.168.1.165:8775/");
  assert.equal(get("networkBrowserUrl").hidden,false);
  assert.equal(get("networkCopyBrowserUrl").disabled,false);
  assert.match(get("networkRemoteState").textContent,/ไม่กระทบการควบคุมผ่าน Browser/);
  assert.match(get("networkListenerState").textContent,/8766/);
  await get("networkCopyBrowserUrl").handlers.click();
  assert.deepEqual(copied,["http://192.168.1.165:8775/"]);
  get("networkListenerPort").value="9886";
  await get("networkListenerSave").handlers.click();
  assert.equal(posts[0].url,"/v1/network/settings");
  assert.equal(posts[0].body.listener_port,9886);
  assert(!("remote_enabled" in posts[0].body));
  assert(!("api_port" in posts[0].body));
  assert.match(get("networkListenerSaveStatus").textContent,/เริ่ม Core ใหม่/);
  get("networkRemoteEnabled").checked=true;
  get("networkControlPort").value="9887";
  get("networkPassword").value="1234";
  await get("networkSave").handlers.click();
  assert.equal(posts[1].body.control_port,9887);
  assert.equal(posts[1].body.password,"1234");
  assert(!("listener_port" in posts[1].body));
  assert(!("api_port" in posts[1].body));
  assert.equal(get("networkPassword").value,"");
  console.log("PASS: Browser LAN Web Control URL, distinct Listener and Remote Client, split save actions, no port mixing");
})().catch(error=>{console.error(error);process.exitCode=1});
