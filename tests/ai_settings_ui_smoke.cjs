"use strict";
const assert=require("node:assert/strict");
const {attach}=require("../web/ai_settings.js");

class Element {
  constructor(id=""){this.id=id;this.value="";this.checked=false;this.disabled=false;this.hidden=false;this.textContent="";this.children=[];this.handlers={};this.type="text";}
  addEventListener(event,handler){(this.handlers[event]||=[]).push(handler);}
  appendChild(node){this.children.push(node);return node;}
  querySelectorAll(){return [];}
  click(){for(const fn of this.handlers.click||[])fn();}
  change(){for(const fn of this.handlers.change||[])fn();}
  input(){for(const fn of this.handlers.input||[])fn();}
}
const nodes=new Map();
const doc={
  getElementById(id){if(!nodes.has(id))nodes.set(id,new Element(id));return nodes.get(id);},
  createElement(tag){return new Element(tag);}
};
const el=id=>doc.getElementById(id);
const settings={
  enabled:false, engine:"ollama", ollama_base_url:"http://127.0.0.1:11434",
  model:"", operation:"translate",
  source_language:"auto",target_language:"th",translation_mode:"whole_message",
  auto_detect:true,priority_instructions:"",custom_prompt:"",
  display_mode:"processed",timeout_seconds:10,keep_alive_minutes:360,
  fallback:"filtered",allow_context_files:false,context_files:[]
};
const calls=[];
function response(body){return {ok:true,async json(){return body;}};}
async function fetchMock(url,options={}){
  calls.push({url,options});
  if(url==="/v1/ai/engines")return response({engines:[
    {id:"ollama",label:"Ollama",ready:true,assets_ready:true,runtime_ready:true,
     supports_prompt:true,installation:"Local Ollama"},
    {id:"m2m100",label:"M2M100",ready:false,assets_ready:false,runtime_ready:false,
     supports_prompt:false,installation:"Not installed"}
  ]});
  if(url==="/v1/settings/ai"){
    if(options.method==="POST"){
      assert.equal(options.headers["X-VoxWeaveTTS-Intent"],"save-ai-settings");
      Object.assign(settings,JSON.parse(options.body).settings);
      return response({settings:{...settings},revision:"r2"});
    }
    return response({settings:{...settings},revision:"r1",saved:false});
  }
  if(url==="/v1/ai/packages")return response({packages:[]});
  if(url.startsWith("/v1/ollama/models"))return response({
    server_running:true,loaded_status_available:true,
    installed_models:[{name:"qwen3.5:4b",size_bytes:2500000000}],
    loaded_models:[],selected:{name:"qwen3.5:4b",installed:true,in_memory:false}
  });
  if(url==="/v1/ollama/preload"){
    assert.equal(options.headers["X-VoxWeaveTTS-Intent"],"preload-ollama-model");
    assert.deepEqual(JSON.parse(options.body),{
      model:"qwen3.5:4b",keep_alive_minutes:120
    });
    return response({model:"qwen3.5:4b",in_memory:true,keep_alive_minutes:120});
  }
  if(url==="/v1/text/process")return response({spoken_text:"ok",display_text:"ok",processing:{}});
  throw Error("unexpected API: "+url);
}
const tick=async()=>{for(let n=0;n<10;n++)await Promise.resolve();};
(async()=>{
  const app=attach(doc,fetchMock);
  assert.ok(app);
  await tick();
  assert.equal(el("aiEnabled").checked,false);
  assert.equal(el("aiEngine").value,"ollama");
  assert.equal(calls.some(c=>c.options.method==="POST"),false,
     "loading settings must not automatically install or preload anything");
  el("aiModel").value="qwen3.5:4b";
  el("aiKeepAlive").value="120";
  el("aiOllamaCheck").click();
  await tick();
  assert.match(el("aiOllamaStatus").textContent,/ติดตั้งแล้ว/);
  assert.equal(el("aiOllamaModels").children[0].value,"qwen3.5:4b");
  assert.equal(calls.some(c=>c.options.method==="POST"),false);
  el("aiOllamaPreload").click();
  await tick();
  assert.match(el("aiOllamaStatus").textContent,/เข้าหน่วยความจำแล้ว/);
  assert.equal(calls.filter(c=>c.url==="/v1/ollama/preload").length,1);
  assert.equal(calls.some(c=>/\/api\/pull|\/api\/create|\/install/.test(c.url)),false,
    "no install/download endpoints are used");
  el("aiOperation").value="none";
  el("aiContextFiles").value="T:\\Games\\Glossary.md, T:\\Games\\Names.json";
  el("aiOllamaBaseUrl").value="http://192.168.1.25:11434";
  el("aiSave").click();
  await tick();
  assert.equal(settings.operation,"none");
  assert.equal(settings.model,"qwen3.5:4b");
  assert.equal(settings.keep_alive_minutes,120);
  assert.equal(settings.ollama_base_url,"http://192.168.1.25:11434");
  assert.deepEqual(settings.context_files,["T:\\Games\\Glossary.md","T:\\Games\\Names.json"]);
  console.log("PASS: Ollama discovery, explicit RAM preload, no download/install, and global AI settings");
})().catch(e=>{console.error(e);process.exitCode=1;});
