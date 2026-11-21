// Universal v4 offline install: ordered file selection, partial failure,
// final status in both panels, NC rights shown, and safe removal.
const assert=require("node:assert/strict");
const fs=require("node:fs");
const vm=require("node:vm");
const html=fs.readFileSync("web/index.html","utf8");
for(const id of ["modelPackageInstall","modelPackageRefresh","modelPackageList",
                 "modelPackageStatus","modelPackageInstallStatus","aiPackageInstall",
                 "aiPackageInstallStatus","voiceSelect","engineSelect"]){
  assert.ok(html.includes('id="'+id+'"'),"missing UI "+id);
}
const start=html.indexOf("async function loadModelPackages(){");
const end=html.indexOf("async function loadGlobalVoiceSettings(){",start);
assert.ok(start>0&&end>start);
const source=html.slice(start,end);
assert.ok(!source.includes("????"),"untranslated v4 status placeholder");
const packages=[
  {package_id:"vachana-thai-four-voices",version:"1.0.0",
   title:"ทดสอบ<private>",format_version:4,model_kind:"tts",
   engine_id:"model-vachana-thai-four-voices-1_0_0",runtime_state:"ready",
   runtime_source:"bundled-wheels",adapter_trusted:true,
   voices:[{id:"th_f_1",label:"หญิงหนึ่ง"},{id:"th_m_2",label:"ชายสอง"}],
   license:{spdx:"MIT",review_status:"review_required",url:"https://example.org/model"},
   dependencies:[]},
  {package_id:"vachana-alt",version:"2.0.0",title:"Alternative",
   format_version:4,model_kind:"tts",runtime_state:"ready",runtime_source:"offline-bundled-wheels",
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
  click(){return this.events.click?.();}
});
function el(id){if(!elements.has(id))elements.set(id,create("div"));return elements.get(id);}
let confirmReplies=[];
let selection=[
  {name:"alternative.vwmodel",license:"Apache-2.0",engine:packages[1].engine_id},
];
const attempted=[];
let engineRefreshes=0,aiRefreshes=0;
el("aiPackageRefresh").addEventListener("click",()=>aiRefreshes++);
const scope={
  el,modeVoiceController:null,
  window:{confirm(message){confirmNotices.push(message);return confirmReplies.length?confirmReplies.shift():true;}},
  document:{createElement:create},
  engines:packages.map(x=>({id:x.engine_id,assets_ready:true,runtime_ready:true})),
  loadEngines:async()=>{engineRefreshes++;},refreshSelectedEngine:()=>{},
  fetch:async(path,opts)=>{
    requests.push({path,opts});
    if(path==="/v1/model-packages")return {ok:true,async json(){return {packages};}};
    if(path==="/v1/model-packages/inspect-local"){
      assert.equal(opts.headers["X-VoxWeaveTTS-Intent"],"inspect-model-package");
      const body=JSON.parse(opts.body);
      if(body.multiple){
        assert.deepEqual(body,{multiple:true});
        return {ok:true,async json(){return selection.length
          ?{cancelled:false,selection_token:"native-selection",files:selection.map(x=>x.name)}
          :{cancelled:true};}};
      }
      assert.deepEqual(body,{selection_token:"native-selection",index:body.index});
      const item=selection[body.index];
      attempted.push("inspect "+item.name);
      assert.equal(el("modelPackageInstall").disabled,true);
      assert.equal(el("aiPackageInstall").disabled,true);
      if(item.invalid)return {ok:false,async json(){return {error:"bad package"};}};
      return {ok:true,async json(){return {
        token:"install-"+body.index,contains_executable_plugin:true,license:{spdx:item.license},
      };}};
    }
    if(path==="/v1/model-packages/install-confirmed"){
      assert.equal(opts.headers["X-VoxWeaveTTS-Intent"],"install-model-package");
      const body=JSON.parse(opts.body);
      const index=Number(body.token.replace("install-",""));
      const item=selection[index];
      attempted.push("install "+item.name);
      assert.deepEqual(body,{
        token:"install-"+index,
        accepted_rights:true,
        acknowledged_noncommercial:/BY-NC|NONCOMMERCIAL/i.test(item.license),
      });
      if(item.failure)return {ok:false,async json(){return {error:"offline runtime unavailable"};}};
      return {ok:true,async json(){return {installed:true,engine_id:item.engine};}};
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
  assert.ok(item.children[0].textContent.includes("Universal v4"));
  assert.ok(item.children[0].textContent.includes("ทดสอบ<private>"));
  assert.equal(item.children[2].href,"https://example.org/model");
  assert.ok(item.children[1].textContent.includes("พร้อมใช้งาน"));
  assert.ok(!html.includes("innerHTML=item.title"));

  const installStatus=el("modelPackageInstallStatus");
  await el("modelPackageInstall").click();
  assert.equal(el("engineSelect").value,packages[1].engine_id);
  assert.ok(installStatus.textContent.includes("ติดตั้งสำเร็จครบ 1 ไฟล์"));
  assert.ok(installStatus.textContent.includes("Apache-2.0"));
  assert.equal(confirmNotices.length,0,"install must not show a second confirmation");

  selection=[
    {name:"z-first.vwmodel",license:"CC-BY-NC-4.0",engine:packages[1].engine_id},
    {name:"a-broken.vwmodel",invalid:true},
    {name:"c-duplicate.vwmodel",failure:true},
    {name:"m-last.vwmodel",license:"MIT",engine:packages[0].engine_id},
  ];
  attempted.length=0;
  await el("aiPackageInstall").click();
  assert.deepEqual(attempted,[
    "inspect z-first.vwmodel","install z-first.vwmodel",
    "inspect a-broken.vwmodel",
    "inspect c-duplicate.vwmodel","install c-duplicate.vwmodel",
    "inspect m-last.vwmodel","install m-last.vwmodel",
  ]);
  assert.match(installStatus.textContent,/ติดตั้งสำเร็จ 2 · ติดตั้งไม่สำเร็จ 2/);
  assert.match(installStatus.textContent,/a-broken\.vwmodel: bad package/);
  assert.match(installStatus.textContent,/c-duplicate\.vwmodel: offline runtime unavailable/);
  assert.equal(el("aiPackageInstallStatus").textContent,installStatus.textContent);
  assert.equal(el("engineSelect").value,packages[0].engine_id);
  assert.equal(engineRefreshes,2,"refresh engines once per successful selection");
  assert.equal(aiRefreshes,2,"refresh installed AI models once per successful selection");

  selection=[{name:"unreadable.vwmodel",invalid:true}];
  await el("modelPackageInstall").click();
  assert.match(installStatus.textContent,/ติดตั้งสำเร็จ 0 · ติดตั้งไม่สำเร็จ 1/);
  assert.equal(engineRefreshes,2);

  selection=[];
  await el("modelPackageInstall").click();
  assert.equal(installStatus.textContent,"ยกเลิกการเลือกไฟล์");
  assert.equal(el("modelPackageInstall").disabled,false);
  assert.equal(el("aiPackageInstall").disabled,false);

  await item.children[3].events.click();
  assert.equal(packages.length,1);
  assert.equal(packages[0].package_id,"vachana-alt");
  assert.equal(el("modelPackageList").children.length,1);
  assert.ok(requests.some(x=>x.path==="/v1/model-packages/remove"));
  assert.equal(confirmNotices.length,1,"only destructive uninstall asks confirmation");
  console.log("PASS: v4 sequential batch install, partial failure, NC rights, cancel and safe removal");
})().catch(e=>{console.error(e);process.exitCode=1;});
