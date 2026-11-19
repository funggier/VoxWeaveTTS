// Universal v3 model manager UI: offline preview, per-file rights confirmation,
// no arbitrary path in HTTP, engine refresh, and safe removal.
const assert=require("node:assert/strict");
const fs=require("node:fs");
const vm=require("node:vm");
const html=fs.readFileSync("web/index.html","utf8");
for(const id of ["modelPackageInstall","modelPackageRefresh","modelPackageList",
                 "modelPackageStatus","voiceSelect","engineSelect"]){
  assert.ok(html.includes('id="'+id+'"'),"missing UI "+id);
}
const start=html.indexOf("async function loadModelPackages(){");
const end=html.indexOf("async function loadGlobalVoiceSettings(){",start);
assert.ok(start>0&&end>start);
const source=html.slice(start,end);
assert.ok(!source.includes("????"),"untranslated v3 status placeholder");
const packages=[
  {package_id:"vachana-thai-four-voices",version:"1.0.0",
   title:"ทดสอบ<private>",format_version:3,model_kind:"tts",
   engine_id:"model-vachana-thai-four-voices-1_0_0",runtime_state:"ready",
   runtime_source:"bundled-wheels",adapter_trusted:true,
   voices:[{id:"th_f_1",label:"หญิงหนึ่ง"},{id:"th_m_2",label:"ชายสอง"}],
   license:{spdx:"MIT",review_status:"review_required",url:"https://example.org/model"},
   dependencies:[]},
  {package_id:"vachana-alt",version:"2.0.0",title:"Alternative",
   format_version:3,model_kind:"tts",runtime_state:"ready",runtime_source:"bundled-wheels",
   adapter_trusted:true,engine_id:"model-vachana-alt-2_0_0",voices:[{id:"a",label:"A"}],
   license:{spdx:"Apache-2.0",review_status:"hold",url:"https://example.org/other"},
   dependencies:[]},
];
const elements=new Map(),requests=[],confirmNotices=[];
const tick=()=>new Promise(resolve=>setImmediate(resolve));
const create=(tag)=>({
  tagName:tag.toUpperCase(),children:[],events:{},style:{},textContent:"",
  append(...nodes){this.children.push(...nodes);},
  replaceChildren(){this.children=[];},
  addEventListener(name,fn){this.events[name]=fn;},
});
function el(id){if(!elements.has(id))elements.set(id,create("div"));return elements.get(id);}
let confirmReplies=[];
let previewLicense="Apache-2.0";
let previewCancelled=false;
const scope={
  el,modeVoiceController:null,
  window:{confirm(message){confirmNotices.push(message);return confirmReplies.length?confirmReplies.shift():true;}},
  document:{createElement:create},
  engines:packages.map(x=>({id:x.engine_id,assets_ready:true,runtime_ready:true})),
  loadEngines:async()=>{},refreshSelectedEngine:()=>{},
  fetch:async(path,opts)=>{
    requests.push({path,opts});
    if(path==="/v1/model-packages")return {ok:true,async json(){return {packages};}};
    if(path==="/v1/model-packages/inspect-local"){
      assert.equal(opts.headers["X-VoxWeaveTTS-Intent"],"inspect-model-package");
      assert.equal(opts.body,"{}");
      return {ok:true,async json(){return previewCancelled?{cancelled:true}:{
        cancelled:false,token:"one-time-token",offline:true,
        package:{id:"vachana-alt",title:"Alternative",version:"2.0.0"},
        license:{spdx:previewLicense,attribution:"Fixture model",review_status:"hold"},
      };}};
    }
    if(path==="/v1/model-packages/install-confirmed"){
      assert.equal(opts.headers["X-VoxWeaveTTS-Intent"],"install-model-package");
      const body=JSON.parse(opts.body);
      assert.equal(body.token,"one-time-token");
      assert.equal(body.accepted_rights,true);
      assert.equal(body.acknowledged_noncommercial,/BY-NC|NONCOMMERCIAL/i.test(previewLicense));
      assert.equal(Object.hasOwn(body,"path"),false);
      return {ok:true,async json(){return {installed:true,package_id:"vachana-alt",
          engine_id:"model-vachana-alt-2_0_0",version:"2.0.0"};}};
    }
    if(path==="/v1/model-packages/remove"){
      assert.equal(opts.headers["X-VoxWeaveTTS-Intent"],"remove-model-package");
      const body=JSON.parse(opts.body);
      const index=packages.findIndex(x=>x.package_id===body.package_id&&x.version===body.version);
      assert.ok(index>=0);
      assert.equal(Object.hasOwn(body,"path"),false);
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
  assert.ok(item.children[0].textContent.includes("Universal v3"));
  assert.ok(item.children[0].textContent.includes("ทดสอบ<private>"));
  assert.equal(item.children[2].href,"https://example.org/model");
  assert.ok(item.children[1].textContent.includes("พร้อมใช้งาน"));
  assert.ok(!html.includes("innerHTML=item.title"));

  await el("modelPackageInstall").events.click();
  assert.equal(el("engineSelect").value,"model-vachana-alt-2_0_0");
  assert.equal(requests.filter(x=>x.path.endsWith("/inspect-local")).length,1);
  assert.equal(requests.filter(x=>x.path.endsWith("/install-confirmed")).length,1);
  assert.ok(confirmNotices[0].includes("Attribution: Fixture model"));
  assert.ok(confirmNotices[0].includes("Apache-2.0"));

  previewLicense="CC-BY-NC-4.0";
  confirmReplies=[true,false];
  const installedBefore=requests.filter(x=>x.path.endsWith("/install-confirmed")).length;
  await el("modelPackageInstall").events.click();
  assert.equal(requests.filter(x=>x.path.endsWith("/install-confirmed")).length,installedBefore);
  assert.ok(el("modelPackageStatus").textContent.includes("NC"));

  confirmReplies=[true,true];
  await el("modelPackageInstall").events.click();
  assert.equal(requests.filter(x=>x.path.endsWith("/install-confirmed")).length,installedBefore+1);

  previewCancelled=true;
  await el("modelPackageInstall").events.click();
  assert.ok(el("modelPackageStatus").textContent.includes("ยกเลิก"));
  assert.equal(requests.filter(x=>x.path.endsWith("/install-confirmed")).length,installedBefore+1);

  await item.children[3].events.click();
  assert.equal(packages.length,1);
  assert.equal(packages[0].package_id,"vachana-alt");
  assert.equal(el("modelPackageList").children.length,1);
  assert.ok(requests.some(x=>x.path==="/v1/model-packages/remove"));
  console.log("PASS: Universal v3 UI, offline preview + rights, NC confirmation, cancel, engine selection and safe uninstall");
})().catch(e=>{console.error(e);process.exitCode=1;});
