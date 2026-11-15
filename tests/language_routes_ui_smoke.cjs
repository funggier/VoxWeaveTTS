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
const names=["languageRouteLanguage",
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
let stored={revision:0,routes:{}};
const sent=[];
async function fetchMock(url,options={}){
  if(url==="/v1/engines")return {ok:true,json:async()=>({engines})};
  if(url==="/v1/settings/language-routes"){
    if(options.method==="POST"){
      assert.equal(options.headers["X-VoxWeaveTTS-Intent"],"save-language-routes");
      const req=JSON.parse(options.body);
      assert.equal(req.expected_revision,stored.revision);
      stored={revision:stored.revision+1,routes:req.routes};
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
  ids.languageRouteLanguage.value="fr";ids.languageRouteLanguage.change();
  assert.equal(ids.languageRouteEngine.value,engine);
  assert.equal(ids.languageRouteVoice.value,"ff_siwis");
  ids.languageRouteSet.click();
  assert.equal(ids.languageRouteLanguage.options.some(o=>o.value==="fr"),false,
    "an assigned language should disappear immediately from Add dropdown");
  assert.equal(ids.languageRouteList.children.length,1);
  const assigned=ids.languageRouteList.children[0];
  assert.equal(assigned.children[0].tagName,"button",
    "Delete button must appear BEFORE route description");
  assert.equal(assigned.children[0].textContent,"ลบ");
  assert.equal(assigned.children[1].style.marginLeft,"14px",
    "route description needs a visible gap after its Delete button");
  assert.ok(assigned.children[1].textContent.includes("fr"));
  assert.notEqual(ids.languageRouteLanguage.value,"fr");
  ids.languageRouteSave.click();
  await tick();
  assert.equal(sent.length,1);
  assert.equal(sent[0].routes.fr.voice_id,"ff_siwis");
  assert.equal(Object.hasOwn(sent[0],"enabled"),false);
  assert.equal(ids.languageRouteStatus.textContent.includes("บันทึกแล้ว"),true);
  // Deleting in the same central editor should make the language selectable again.
  assigned.children[0].click();
  assert.equal(ids.languageRouteLanguage.options.filter(o=>o.value==="fr").length,1,
    "deleted language returns to the language picker");
  assert.equal(ids.languageRouteList.children[0].textContent.includes("ยังไม่มี"),true);
  ids.languageRouteLanguage.value="fr";ids.languageRouteLanguage.change();
  ids.languageRouteSet.click();
  assert.equal(ids.languageRouteLanguage.options.some(o=>o.value==="fr"),false);
  ids.languageRouteReload.click();await tick();
  assert.equal(ids.languageRouteLanguage.options.some(o=>o.value==="fr"),false,
    "reload retains server-side assignments, not unsaved local removals");
  console.log("PASS: single-assignment language picker, delete-before-description, restore, revision save");
})().catch(e=>{console.error(e);process.exitCode=1;});
