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
    if(path==="/v1/runtimes/install-verified"){
      assert.equal(options.method,"POST");
      assert.equal(options.headers["X-VoxWeaveTTS-Intent"],
                   "install-verified-runtime");
      const body=JSON.parse(options.body);
      assert.deepEqual(body,{id:"kokoro",expected_fingerprint:"d".repeat(64),
                             confirm_install:true});
      records[3].repair={state:"repairing",source:"wheelhouse",error:null};
      return {ok:true,async json(){return {install:records[3].repair};}};
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
  assert.equal(get("runtimeRegistryList").children[1].children.length,5);
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
  records.push({id:"kokoro",kind:"tts",installed:false,ready:false,
    health_state:"not-installed",repair:{state:"not_started",error:null},
    wheelhouse:{state:"present-unverified",ready_to_verify:true,wheels:4},
    reference_count:1,consumers:["v2:kokoro@1.0.0"],can_uninstall:false,
    runtime_fingerprint:"d".repeat(64),relative_path:"runtime/engine-envs/kokoro"});
  await fakeWindow.VoxRuntimeRegistry.refresh();
  const candidate=get("runtimeRegistryList").children[3];
  assert.match(candidate.children[4].textContent,/SHA-256/);
  assert.equal(candidate.children[5].disabled,false);
  confirmed=false;
  await candidate.children[5].events.click();
  assert.equal(requests.filter(x=>x.path==="/v1/runtimes/install-verified").length,0);
  confirmed=true;
  await candidate.children[5].events.click();
  assert.equal(requests.filter(x=>x.path==="/v1/runtimes/install-verified").length,1);
  assert.equal(records[3].repair.source,"wheelhouse");
  records.push({
    id:"wayu-nc",kind:"tts",installed:true,ready:true,
    health_state:"ready",repair_required:false,
    consumers:["v2:wayu@1.0.0"],reference_count:1,can_uninstall:false,
    runtime_fingerprint:"e".repeat(64),relative_path:"runtime/engine-envs/wayu-nc",
    rights_review:{
      commercial_status:"noncommercial-only",
      publication_state:"hold",
      legal_clearance:false,
      reasons:["wayu-weight-noncommercial-license","<img src=x onerror=alert(1)>"]
    }
  });
  await fakeWindow.VoxRuntimeRegistry.refresh();
  const wayu=get("runtimeRegistryList").children[4];
  const notices=wayu.children.filter(node=>String(node.textContent||"").includes("สิทธิ์ Runtime (Rights):"));
  assert.equal(notices.length,1,"NC rights must be shown even with runtime ready");
  assert.match(notices[0].textContent,/HOLD/);
  assert.match(notices[0].textContent,/Commercial: noncommercial-only/);
  assert.match(notices[0].textContent,/ไม่ใช่การรับรองสิทธิ์/);
  assert.match(notices[0].textContent,/<img src=x/);
  console.log("PASS: guarded runtime lifecycle and clear NC/HOLD license warning");
})().catch(err=>{console.error(err);process.exitCode=1;});
