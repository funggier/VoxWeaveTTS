// Local opt-in consent is mandatory per held provider and never implies rights.
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
  checked:false,disabled:false,
  append(...items){this.children.push(...items);},
  replaceChildren(){this.children=[];},
  addEventListener(event,fn){this.events[event]=fn;}
});
function el(id){
  if(!elements.has(id))elements.set(id,create("div"));
  return elements.get(id);
}
const reviews={
  "vachana":{description:"Vachana license review <script>alert(1)</script>",
    commercial_status:"review-required",local_install:{
      consent_required:true,terms_version:1,
      noncommercial_acknowledgment_required:false}},
  "wayu-nc":{description:"Wayu NC weights CC BY-NC 4.0",
    commercial_status:"noncommercial-only",local_install:{
      consent_required:true,terms_version:1,
      noncommercial_acknowledgment_required:true}},
  "sherpa":{local_install:{consent_required:false}}
};
const values={"vachana":"not_installed","wayu-nc":"not_installed",
              "sherpa":"not_installed"};
const requests=[];
let confirmed=true;
const scope={
  el,
  document:{createElement:create,createTextNode:s=>({tagName:"#TEXT",textContent:s})},
  window:{confirm:()=>confirmed},
  modeVoiceController:null,loadEngines:async()=>{},
  clearTimeout(){},setTimeout(){return 1;},
  fetch:async(path,opts)=>{
    requests.push({path,opts});
    if(path==="/v1/engine-providers"){
      return {ok:true,async json(){return {providers:
        Object.keys(values).map(id=>({
          id,backend:id+"-v1",engines:[id+"-cpu"],
          rights_review:reviews[id],
          install:{id,state:values[id],error:null}
        }))};}};
    }
    if(path==="/v1/engine-providers/install"){
      assert.equal(opts.headers["X-VoxWeaveTTS-Intent"],"install-engine-provider");
      const body=JSON.parse(opts.body);
      assert.ok(Object.hasOwn(values,body.provider_id));
      if(body.provider_id==="wayu-nc"){
        assert.deepEqual(body,{
          provider_id:"wayu-nc",accepted_terms_version:1,
          acknowledged_noncommercial:true});
      }else if(body.provider_id==="vachana"){
        assert.deepEqual(body,{
          provider_id:"vachana",accepted_terms_version:1,
          acknowledged_noncommercial:false});
      }else{
        assert.deepEqual(body,{provider_id:"sherpa"});
      }
      values[body.provider_id]="ready";
      return {ok:true,async json(){return {install:{
        id:body.provider_id,state:"ready",error:null}};}};
    }
    throw Error("unexpected "+path);
  }
};
vm.createContext(scope);
vm.runInContext(source,scope);
const tick=()=>new Promise(resolve=>setImmediate(resolve));
const installCount=()=>requests.filter(x=>x.path==="/v1/engine-providers/install").length;
const ui=(id)=>{
  const row=el("engineProviderList").children[Object.keys(values).indexOf(id)];
  const button=row.children.find(x=>x.tagName==="BUTTON");
  const checks=row.children.filter(x=>x.tagName==="LABEL").map(x=>
    x.children.find(c=>c.tagName==="INPUT"));
  return {row,button,checks};
};
(async()=>{
  await tick();await tick();
  assert.equal(el("engineProviderList").children.length,3);
  let {row,button,checks}=ui("vachana");
  assert.equal(checks.length,1);
  assert.equal(button.disabled,true);
  await button.events.click();
  assert.equal(installCount(),0,"button must not install without consent");
  assert.ok(row.children.some(x=>
    String(x.textContent).includes("<script>alert(1)</script>")),
    "license is shown as inert text, never HTML");

  checks[0].checked=true;
  checks[0].events.change();
  assert.equal(button.disabled,false);
  confirmed=false;
  await button.events.click();
  assert.equal(installCount(),0,"refused confirmation must not install");
  confirmed=true;
  await button.events.click();
  assert.equal(installCount(),1);
  assert.equal(ui("vachana").button.disabled,true);

  ({button,checks}=ui("wayu-nc"));
  assert.equal(checks.length,2);
  assert.equal(button.disabled,true);
  checks[0].checked=true;checks[0].events.change();
  assert.equal(button.disabled,true,"Wayu must separately acknowledge NC");
  checks[1].checked=true;checks[1].events.change();
  assert.equal(button.disabled,false);
  await button.events.click();
  assert.equal(installCount(),2);
  assert.equal(ui("wayu-nc").button.disabled,true);

  ({button,checks}=ui("sherpa"));
  assert.equal(checks.length,0);
  assert.equal(button.disabled,false);
  await button.events.click();
  assert.equal(installCount(),3);
  assert.equal(ui("sherpa").button.disabled,true);
  console.log("PASS Engine Providers: explicit per-provider install consent, Wayu NC double opt-in, same-origin intent, inert license text");
})().catch(e=>{console.error(e);process.exitCode=1;});
