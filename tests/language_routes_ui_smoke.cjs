"use strict";
const assert=require("node:assert/strict");
const {attach}=require("../web/language_routes.js");

class Element {
  constructor(tag="div"){this.tagName=tag;this.children=[];this._value="";this.checked=false;this.disabled=false;this.textContent="";this.handlers={};this.style={};}
  get options(){return this.children.filter(x=>x.tagName==="option");}
  get value(){
    if(this.tagName==="select"&&!this.options.some(x=>x.value===this._value))
      return this.options[0]?.value||"";
    return this._value;
  }
  set value(v){this._value=String(v);}
  addEventListener(name,fn){(this.handlers[name]??=[]).push(fn);}
  appendChild(el){this.children.push(el);return el;}
  replaceChildren(...nodes){this.children=nodes;}
  click(){for(const fn of this.handlers.click||[])fn();}
  change(){for(const fn of this.handlers.change||[])fn();}
}
const ids={};
const names=["languageRoutesEnabled","languageRouteLanguage",
  "languageRouteEngine","languageRouteVoice","languageRouteSet",
  "languageRouteSave","languageRouteReload","languageRouteList",
  "languageRouteStatus"];
for(const name of names)ids[name]=new Element(name.includes("Engine")||
  name.includes("Language")||name==="languageRouteVoice"?"select":"div");
const document={
  getElementById:id=>ids[id]||null,
  createElement:name=>new Element(name)
};
const engine="model-kokoro-multilingual-int8-1_0_0";
const engines=[
  {id:"makham-paradee-cpu",label:"Thai",language:"th",assets_ready:true,runtime_ready:true,
   voices:[{id:"paradee_thai",label:"Paradee"}]},
  {id:engine,label:"Kokoro INT8",language:"multi",assets_ready:true,runtime_ready:true,
   voices:[{id:"af_heart",label:"English"},{id:"ff_siwis",label:"French"},
           {id:"jf_alpha",label:"Japanese"}]}
];
let stored={revision:0,enabled:false,routes:{}};
const sent=[];
async function fetchMock(url,options={}){
  if(url==="/v1/engines")return {ok:true,json:async()=>({engines})};
  if(url==="/v1/settings/language-routes"){
    if(options.method==="POST"){
      assert.equal(options.headers["X-VoxWeaveTTS-Intent"],"save-language-routes");
      const req=JSON.parse(options.body);
      assert.equal(req.expected_revision,stored.revision);
      stored={revision:stored.revision+1,enabled:req.enabled,routes:req.routes};
      sent.push(stored);
      return {ok:true,json:async()=>stored};
    }
    return {ok:true,json:async()=>({
      ...stored,languages:{th:"Thai",en:"English",fr:"French",ja:"Japanese"}
    })};
  }
  throw Error("Unexpected request: "+url);
}
async function tick(){for(let i=0;i<30;i++)await Promise.resolve();}
(async()=>{
  const app=attach(document,fetchMock);
  await tick();
  assert.ok(app);
  assert.equal(ids.languageRoutesEnabled.checked,false);
  ids.languageRouteLanguage.value="fr";ids.languageRouteLanguage.change();
  assert.equal(ids.languageRouteEngine.value,engine);
  assert.equal(ids.languageRouteVoice.value,"ff_siwis");
  ids.languageRouteSet.click();
  ids.languageRoutesEnabled.checked=true;
  ids.languageRouteSave.click();
  await tick();
  assert.equal(sent.length,1);
  assert.equal(sent[0].routes.fr.voice_id,"ff_siwis");
  assert.equal(sent[0].enabled,true);
  assert.equal(ids.languageRouteStatus.textContent.includes("บันทึกแล้ว"),true);
  console.log("PASS: multilingual voice routing UI, voice filtering, revision save");
})().catch(e=>{console.error(e);process.exitCode=1;});
