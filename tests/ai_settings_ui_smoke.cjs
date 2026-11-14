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
  fallback:"filtered",allow_context_files:false,context_files:[],
  tool_calling_enabled:false,tool_web_lookup:false,tool_file_read:false,
  tool_general_web_search:false,tool_search_provider:"wikipedia",
  tool_searxng_url:"http://127.0.0.1:8080",tool_max_calls:2
};
const calls=[];
let storedKey="";
let keys={ollama:false,tavily:false};
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
  if(url==="/v1/ai/search-credentials"){
    if(options.method==="POST"){
      assert.equal(options.headers["X-VoxWeaveTTS-Intent"],"save-ai-search-key");
      const req=JSON.parse(options.body);
      if(req.action==="save"){storedKey=req.key;keys[req.provider]=true;}
      else {storedKey="";keys[req.provider]=false;}
      return response({configured:{...keys}});
    }
    return response({configured:{...keys}});
  }
  if(url==="/v1/ai/search/test"){
    assert.equal(options.headers["X-VoxWeaveTTS-Intent"],"test-ai-search-provider");
    return response({provider:settings.tool_search_provider,results:[{title:"Bangkok",snippet:"Capital",source:"https://example.org/bangkok"}]});
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
  el("aiEnabled").checked=true;
  el("aiEngine").value="ollama";
  el("aiOperation").value="translate";
  el("aiTarget").value="unspecified";
  el("aiPrompt").value="Translate all messages to Japanese";
  el("aiTarget").change();
  assert.match(el("aiLanguageHint").textContent,/Priority Instructions|Custom Prompt/);
  assert.equal(el("aiAutoDetect").disabled,true);
  assert.equal(el("aiTranslationMode").disabled,true);
  el("aiSave").click();
  await tick();
  assert.equal(settings.target_language,"unspecified");
  assert.equal(settings.custom_prompt,"Translate all messages to Japanese");
  el("aiEngine").value="m2m100";
  el("aiEngine").change();
  assert.equal(el("aiTarget").value,"unspecified");
  assert.match(el("aiLanguageHint").textContent,/M2M100.*ข้ามการแปล/);
  el("aiPrompt").value="";
  el("aiPriority").value="";
  el("aiSave").click();
  await tick();
  assert.equal(settings.engine,"m2m100");
  assert.equal(settings.target_language,"unspecified");
  assert.equal(settings.custom_prompt,"");
  // Tool Calling must stay off unless enabled explicitly by the user.
  assert.equal(settings.tool_calling_enabled,false);
  el("aiEngine").value="ollama";
  el("aiEngine").change();
  el("aiOperation").value="custom";
  el("aiOperation").change();
  el("aiToolsEnabled").checked=true;
  el("aiWebLookup").checked=true;
  el("aiToolMaxCalls").value="2";
  el("aiToolsEnabled").change();
  assert.match(el("aiToolHint").textContent,/Wikipedia/);
  el("aiSave").click();
  await tick();
  assert.equal(settings.tool_calling_enabled,true);
  assert.equal(settings.tool_web_lookup,true);
  assert.equal(settings.tool_file_read,false);
  assert.equal(settings.tool_max_calls,2);
  el("aiToolsEnabled").checked=false;
  el("aiSave").click();
  await tick();
  assert.equal(settings.tool_calling_enabled,false);
  // Search provider profiles never contain API keys or save automatically.
  el("aiSearchProvider").value="searxng";
  el("aiSearchProvider").change();
  assert.equal(el("aiSearxngFields").hidden,false);
  el("aiSearxngUrl").value="http://192.168.0.10:8080";
  const exported=app.searchProfile();
  assert.equal(exported.provider,"searxng");
  assert.equal(exported.searxng_url,"http://192.168.0.10:8080");
  assert.equal(JSON.stringify(exported).includes("api_key"),false);
  assert.equal(JSON.stringify(exported).includes("token"),false);
  const before=calls.filter(c=>c.url==="/v1/settings/ai"&&c.options.method==="POST").length;
  app.importSearchProfile({format:"voxweavetts-ai-search-profile",version:1,
    provider:"tavily",searxng_url:"http://127.0.0.1:8080",enabled:true});
  assert.equal(el("aiSearchProvider").value,"tavily");
  assert.equal(el("aiSearchApiFields").hidden,false);
  assert.equal(calls.filter(c=>c.url==="/v1/settings/ai"&&c.options.method==="POST").length,before);
  assert.throws(()=>app.importSearchProfile({format:"voxweavetts-ai-search-profile",
    version:1,provider:"tavily",searxng_url:"http://127.0.0.1:8080",
    enabled:true,api_key:"should-not-import"}));
  el("aiSearchApiKey").value="example-key-not-real";
  el("aiSearchKeySave").click();
  await tick();
  assert.equal(keys.tavily,true);
  assert.equal(storedKey,"example-key-not-real");
  assert.equal(el("aiSearchApiKey").value,"");
  assert.equal(JSON.stringify(app.searchProfile()).includes("example-key-not-real"),false);
  globalThis.confirm=()=>true;
  el("aiSearchKeyClear").click();
  await tick();
  assert.equal(keys.tavily,false);
  el("aiSave").click();
  await tick();
  assert.equal(settings.tool_search_provider,"tavily");
  assert.equal(settings.tool_general_web_search,true);
  assert.equal(settings.tool_searxng_url,"http://127.0.0.1:8080");
  el("aiSearchTestQuery").value="Bangkok";
  el("aiSearchTest").click();
  await tick();
  assert.match(el("aiSearchTestResult").textContent,/Bangkok/);
  assert.equal(calls.filter(c=>c.url==="/v1/ai/search/test").length,1);
  console.log("PASS: provider dropdown, direct search testing, encrypted-key controls and profile import/export");
})().catch(e=>{console.error(e);process.exitCode=1;});