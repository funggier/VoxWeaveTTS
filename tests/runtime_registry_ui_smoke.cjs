/* Runtime cleanup: referenced backends cannot be deleted; only orphaned
 * environments may be removed after explicit confirmation. */
const assert=require("node:assert/strict");
const fs=require("node:fs");
const vm=require("node:vm");
const html=fs.readFileSync("web/index.html","utf8");
const js=fs.readFileSync("web/runtime_registry.js","utf8");
for(const id of ["runtimeRegistryPanel","runtimeRegistryRefresh",
                 "runtimeRegistryStatus","runtimeRegistryList"]){
  assert.ok(html.includes('id="'+id+'"'),"missing runtime UI "+id);
}
assert.ok(html.includes('src="/runtime_registry.js"'));
assert.ok(!js.includes("innerHTML"));
const elements=new Map();
const created=()=>({
  children:[],events:{},style:{},textContent:"",disabled:false,
  append(...nodes){this.children.push(...nodes);},
  replaceChildren(){this.children=[];},
  addEventListener(name,fn){this.events[name]=fn;},
});
const get=id=>{
  if(!elements.has(id))elements.set(id,created());
  return elements.get(id);
};
const records=[
  {id:"sherpa",kind:"tts",driver:"legacy",installed:true,ready:true,
   consumers:["supertonic@1.0.0","melo@1.0.0"],reference_count:2,can_uninstall:false,
   runtime_fingerprint:"a".repeat(64),relative_path:"runtime/engine-envs/sherpa"},
  {id:"m2m100",kind:"translation",driver:"trusted-python-worker",
   installed:true,ready:true,consumers:[],reference_count:0,
   can_uninstall:true,runtime_fingerprint:"b".repeat(64),
   relative_path:"runtime/ai-envs/m2m100"},
];
const requests=[];
let confirmed=true;
const fakeWindow={
  document:{getElementById:get,createElement:created},
  confirm(){return confirmed;},
  async fetch(path,options){
    requests.push({path,options});
    if(path==="/v1/runtimes")
      return {ok:true,async json(){return {runtimes:records};}};
    if(path==="/v1/runtimes/remove"){
      assert.equal(options.method,"POST");
      assert.equal(options.headers["X-VoxWeaveTTS-Intent"],"remove-unused-runtime");
      const body=JSON.parse(options.body);
      assert.deepEqual(body,{id:"m2m100",confirm_uninstall:true,
                             expected_fingerprint:"b".repeat(64)});
      records[1].installed=false;
      records[1].ready=false;
      return {ok:true,async json(){return {removed:true};}};
    }
    if(path==="/v1/runtimes/repair"){
      assert.equal(options.method,"POST");
      assert.equal(options.headers["X-VoxWeaveTTS-Intent"],"repair-runtime-offline");
      const body=JSON.parse(options.body);
      assert.deepEqual(body,{id:"vachana",confirm_repair:true,
                             expected_fingerprint:"c".repeat(64)});
      records[2].repair={state:"repairing",error:null};
      return {ok:true,async json(){return {repair:records[2].repair};}};
    }
    throw Error("unknown runtime URL "+path);
  },
};
vm.runInNewContext(js,{window:fakeWindow,document:fakeWindow.document});
const tick=()=>new Promise(resolve=>setImmediate(resolve));
(async()=>{
  await tick();
  await tick();
  const list=get("runtimeRegistryList");
  assert.equal(list.children.length,2);
  const shared=list.children[0];
  assert.equal(shared.children[4].disabled,true);
  assert.match(shared.children[2].textContent,/supertonic/);
  const remove=list.children[1].children[4];
  assert.equal(remove.disabled,false);
  confirmed=false;
  await remove.events.click();
  assert.equal(requests.filter(x=>x.path==="/v1/runtimes/remove").length,0);
  confirmed=true;
  await remove.events.click();
  assert.equal(requests.filter(x=>x.path==="/v1/runtimes/remove").length,1);
  assert.equal(get("runtimeRegistryList").children[1].children.length,4);
  assert.match(get("runtimeRegistryStatus").textContent,/m2m100/);
  records.push({id:"vachana",kind:"tts",driver:"managed",
    installed:true,ready:false,repair_required:true,health_state:"relocated",
    repair:{state:"not_started",error:null},
    consumers:["v2:vachana@1.0.0"],reference_count:1,can_uninstall:false,
    runtime_fingerprint:"c".repeat(64),
    relative_path:"runtime/engine-envs/vachana"});
  await fakeWindow.VoxRuntimeRegistry.refresh();
  const node=get("runtimeRegistryList").children[2];
  assert.match(node.children[1].textContent,/ย้ายโฟลเดอร์/);
  assert.equal(node.children[4].disabled,true);
  assert.equal(node.children[5].disabled,false);
  confirmed=false;
  await node.children[5].events.click();
  assert.equal(requests.filter(x=>x.path==="/v1/runtimes/repair").length,0);
  confirmed=true;
  await node.children[5].events.click();
  assert.equal(requests.filter(x=>x.path==="/v1/runtimes/repair").length,1);
  assert.equal(records[2].repair.state,"repairing");
  console.log("PASS: runtime references, guarded uninstall, health status, opt-in offline repair, same-origin intent");
})().catch(err=>{console.error(err);process.exitCode=1;});
