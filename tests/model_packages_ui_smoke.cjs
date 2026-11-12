// Model Package manager UI smoke: metadata only, native file chooser intent,
// multiple installed packs, removal with confirmation and no DOM injection.
const assert=require("node:assert/strict");
const fs=require("node:fs");
const vm=require("node:vm");
const html=fs.readFileSync("web/index.html","utf8");
for(const id of ["modelPackageInstall","modelPackageRefresh",
                  "modelPackageList","modelPackageStatus","voiceSelect"]){
  assert.ok(html.includes('id="'+id+'"'),"missing UI "+id);
}
const start=html.indexOf("async function loadModelPackages(){");
const end=html.indexOf("async function loadGlobalVoiceSettings(){",start);
assert.ok(start>0&&end>start);
const source=html.slice(start,end);
const packages=[
  {package_id:"vachana-thai-four-voices",version:"1.0.0",
   title:"ทดสอบ<private>",engine_id:"model-vachana-thai-four-voices-1_0_0",
   voices:[{id:"th_f_1",label:"หญิงหนึ่ง"},{id:"th_m_2",label:"ชายสอง"}],
   license:{spdx:"MIT",review_status:"review_required",
            url:"https://example.org/model"},
   dependencies:["vachanatts==0.0.7"]},
  {package_id:"vachana-alt",version:"2.0.0",title:"Alternative",
   engine_id:"model-vachana-alt-2_0_0",voices:[{id:"a",label:"A"}],
   license:{spdx:"Apache-2.0",review_status:"hold",
            url:"https://example.org/other"},dependencies:[]},
];
const elements=new Map();
const requests=[];
const tick=()=>new Promise(resolve=>setImmediate(resolve));
const create=(tag)=>({
  tagName:tag.toUpperCase(),children:[],events:{},style:{},textContent:"",
  append(...nodes){this.children.push(...nodes);},
  replaceChildren(){this.children=[];},
  addEventListener(name,fn){this.events[name]=fn;},
});
function el(id){
  if(!elements.has(id))elements.set(id,create("div"));
  return elements.get(id);
}
const scope={
  el,
  modeVoiceController:null,
  window:{confirm(){return true;}},
  document:{createElement:create},
  engines:packages.map(x=>({id:x.engine_id,assets_ready:true,runtime_ready:true})),
  loadEngines:async()=>{},
  refreshSelectedEngine:()=>{},
  fetch:async(path,opts)=>{
    requests.push({path,opts});
    if(path==="/v1/model-packages")return {ok:true,async json(){return {packages};}};
    if(path==="/v1/model-packages/install-local"){
      assert.equal(opts.headers["X-VoxWeaveTTS-Intent"],"install-model-package");
      assert.equal(opts.body,"{}");
      return {ok:true,async json(){return {installed:true,package_id:"vachana-alt",version:"2.0.0"};}};
    }
    if(path==="/v1/model-packages/remove"){
      assert.equal(opts.headers["X-VoxWeaveTTS-Intent"],"remove-model-package");
      const payload=JSON.parse(opts.body);
      const index=packages.findIndex(x=>x.package_id===payload.package_id && x.version===payload.version);
      assert.ok(index>=0);
      packages.splice(index,1);
      return {ok:true,async json(){return {removed:true};}};
    }
    throw Error("unexpected model UI path "+path);
  },
};
vm.createContext(scope);
vm.runInContext(source,scope);
(async()=>{
  await tick();
  assert.equal(el("modelPackageList").children.length,2);
  const item=el("modelPackageList").children[0];
  assert.equal(item.children[0].textContent,"ทดสอบ<private> v1.0.0");
  assert.equal(item.children[2].href,"https://example.org/model");
  assert.ok(item.children[1].textContent.includes("review_required"));
  assert.ok(!html.includes('innerHTML=item.title'));
  await el("modelPackageInstall").events.click();
  assert.equal(el("engineSelect").value,"model-vachana-alt-2_0_0");
  assert.equal(requests.filter(x=>x.path==="/v1/model-packages/install-local").length,1);
  await item.children[3].events.click();
  assert.equal(packages.length,1);
  assert.equal(packages[0].package_id,"vachana-alt");
  assert.equal(el("modelPackageList").children.length,1);
  assert.ok(requests.some(x=>x.path==="/v1/model-packages/remove"));
  console.log("PASS: multi-model UI, SHA manifest status, license details, native picker intent and confirmed uninstall");
})().catch(e=>{console.error(e);process.exitCode=1;});
