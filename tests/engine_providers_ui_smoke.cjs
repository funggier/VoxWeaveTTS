// Engine Provider UI: isolated runtime install is user-triggered and same-origin.
const assert=require("node:assert/strict");
const fs=require("node:fs");
const vm=require("node:vm");
const html=fs.readFileSync("web/index.html","utf8");
for(const id of ["engineProviderRefresh","engineProviderStatus","engineProviderList"]){
  assert.ok(html.includes('id="'+id+'"'),"missing "+id);
}
const start=html.indexOf("let engineProviderPolling=null;");
const end=html.indexOf("async function loadModelPackages(){",start);
assert.ok(start>=0&&end>start);
const source=html.slice(start,end);
const elements=new Map();
const create=(tag)=>({
  tagName:tag.toUpperCase(),children:[],events:{},style:{},textContent:"",
  append(...items){this.children.push(...items);},
  replaceChildren(){this.children=[];},
  addEventListener(event,fn){this.events[event]=fn;}
});
function el(id){
  if(!elements.has(id))elements.set(id,create("div"));
  return elements.get(id);
}
const requests=[];
let state="not_installed";
const scope={
  el, document:{createElement:create},
  modeVoiceController:null,loadEngines:async()=>{},
  clearTimeout(){},setTimeout(){return 1;},
  fetch:async(path,opts)=>{
    requests.push({path,opts});
    if(path==="/v1/engine-providers"){
      return {ok:true,async json(){return {providers:[{
        id:"vachana",backend:"vachana-v1",engines:["vachana-cpu"],
        install:{id:"vachana",state,error:null}
      }]};}};
    }
    if(path==="/v1/engine-providers/install"){
      assert.equal(opts.headers["X-VoxWeaveTTS-Intent"],"install-engine-provider");
      assert.deepEqual(JSON.parse(opts.body),{provider_id:"vachana"});
      state="ready";
      return {ok:true,async json(){return {install:{id:"vachana",state,error:null}};}};
    }
    throw Error("unexpected "+path);
  }
};
vm.createContext(scope);
vm.runInContext(source,scope);
(async()=>{
  await new Promise(resolve=>setImmediate(resolve));
  assert.equal(el("engineProviderList").children.length,1);
  const item=el("engineProviderList").children[0];
  assert.ok(item.children[0].textContent.includes("not_installed"));
  const button=item.children[2];
  assert.ok(!button.disabled);
  await button.events.click();
  assert.ok(requests.some(x=>x.path==="/v1/engine-providers/install"));
  assert.equal(el("engineProviderList").children[0].children[2].disabled,true);
  console.log("PASS Engine Provider install UI: trusted ID, local runtime status, opt-in action");
})().catch(e=>{console.error(e);process.exitCode=1;});
