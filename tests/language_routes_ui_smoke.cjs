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
  {id:"fastthaig2p-cpu",label:"FastThaiG2P",language:"th",
   supported_languages:["th","en"],assets_ready:true,runtime_ready:true,
   voices:[{id:"thai_som",label:"ThaiSom"}]},
  {id:"vachana-cpu",label:"Vachana",language:"th",
   supported_languages:["th","en"],assets_ready:true,runtime_ready:true,
   voices:[{id:"th_f_1",label:"Female 1"},{id:"th_m_1",label:"Male 1"}]},
  {id:"model-fastthaig2p-thai-som-0_3_0",label:"ThaiSom package",language:"th",
   supported_languages:["th","en"],assets_ready:true,runtime_ready:true,
   voices:[{id:"thai_som",label:"ThaiSom"}]},
  {id:"model-vachana-thai-four-voices-1_0_0",label:"Vachana package",language:"th",
   supported_languages:["th","en"],assets_ready:true,runtime_ready:true,
   voices:[{id:"th_f_1",label:"Female 1"}]},
  {id:"makham-paradee-cpu",label:"MakHam Paradee",language:"th",
   supported_languages:["th","en"],assets_ready:true,runtime_ready:true,
   voices:[{id:"paradee_thai",label:"Paradee"}]},
  {id:"personal-nc-wayu-paxa-edge-cpu",label:"[NC / NonCommercial] Wayu Paxa Edge",
   language:"th",supported_languages:["th","en"],assets_ready:true,runtime_ready:true,
   voices:[{id:"f_young_warm",label:"Warm"},{id:"m_mid_warm",label:"Male"}]},
  {id:engine,label:"Kokoro INT8",language:"multi",assets_ready:true,runtime_ready:true,
   voices:[{id:"af_heart",label:"English"},{id:"ff_siwis",label:"French"},
           {id:"jf_alpha",label:"Japanese"}]},
  {id:"model-supertonic3-multilingual-int8-1_0_0",label:"Supertonic 3",language:"multi",
   assets_ready:true,runtime_ready:true,
   voice_language_map:{"ko_s0":"ko","en_s0":"en"},
   voices:[{id:"ko_s0",label:"Korean"},{id:"en_s0",label:"English"}]},
  {id:"model-melo-chinese-onnx-1_0_0",label:"Melo Chinese",language:"zh",
   supported_languages:["zh","en"],assets_ready:true,runtime_ready:true,
   voices:[{id:"zh_melo",label:"Chinese"}]}
];
let stored={revision:0,routes:{}};
const sent=[],voicePresets=[];
async function fetchMock(url,options={}){
  if(url==="/v1/presets"){
    if(options.method==="POST"){
      assert.equal(options.headers["X-VoxWeaveTTS-Intent"],"save-voice-preset");
      const preset=JSON.parse(options.body);
      voicePresets.push(preset);
      return {ok:true,json:async()=>({preset})};
    }
    return {ok:true,json:async()=>({presets:voicePresets})};
  }
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
      ...stored,languages:{th:"Thai",en:"English",fr:"French",ja:"Japanese",
                           zh:"Chinese",ko:"Korean"}
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
  const details=assigned.children[2];
  assert.equal(details.tagName,"details");
  assert.equal(details.children[0].textContent,"ปรับเสียง");
  const grid=details.children[2];
  assert.equal(grid.children.length,7,"five sliders, formant checkbox and seed field");
  for(let i=0;i<5;i++){
    assert.equal(grid.children[i].children[1].type,"range");
    assert.equal(grid.children[i].children[2].type,"number");
  }
  grid.children[0].children[2].value="1.35";
  grid.children[1].children[2].value="2.50";
  grid.children[2].children[2].value="-1.25";
  grid.children[3].children[2].value="-3.00";
  grid.children[4].children[2].value="2.00";
  grid.children[5].children[0].checked=false;
  grid.children[6].children[1].value="321";
  details.children[3].click();await tick();
  assert.equal(sent.length,2,"per-language Save should persist immediately");
  assert.equal(sent[1].routes.fr.speed,1.35);
  assert.equal(sent[1].routes.fr.seed,321);
  assert.equal(sent[1].routes.fr.voice_controls.pitch_semitones,-1.25);
  assert.equal(sent[1].routes.fr.voice_controls.formant_preserve,false);

  const presetGrid=details.children[5].children[2];
  presetGrid.children[0].children[1].value="French Calm";
  presetGrid.children[1].click();await tick();
  assert.equal(voicePresets.length,1);
  assert.equal(voicePresets[0].name,"French Calm");
  assert.equal(voicePresets[0].voice_id,"ff_siwis");
  assert.equal(voicePresets[0].speed,1.35);
  grid.children[0].children[2].value="2.00";
  presetGrid.children[2].children[1].value="French Calm";
  presetGrid.children[3].click();
  assert.equal(grid.children[0].children[2].value,"1.35",
    "loading a preset restores the language-specific sliders");
  assert.equal(grid.children[6].children[1].value,"321");
  // A second language starts with its own defaults; edits to one language
  // must never alter the first language or its saved preset.
  ids.languageRouteLanguage.value="ja";ids.languageRouteLanguage.change();
  assert.equal(ids.languageRouteVoice.value,"jf_alpha");
  ids.languageRouteSet.click();
  const japanese=ids.languageRouteList.children[1];
  assert.ok(japanese.children[1].textContent.includes("ja"));
  const jaGrid=japanese.children[2].children[2];
  assert.equal(jaGrid.children[0].children[2].value,"1.00");
  jaGrid.children[0].children[2].value="0.85";
  ids.languageRouteSave.click();await tick();
  assert.equal(stored.routes.ja.speed,0.85);
  assert.equal(stored.routes.fr.speed,1.35);
  assert.equal(stored.routes.fr.voice_controls.pitch_semitones,-1.25);

  // Deleting in the same central editor should make the language selectable again.
  assigned.children[0].click();
  assert.equal(ids.languageRouteLanguage.options.filter(o=>o.value==="fr").length,1,
    "deleted language returns to the language picker");
  assert.equal(ids.languageRouteList.children.length,1);
  assert.ok(ids.languageRouteList.children[0].children[1].textContent.includes("ja"));
  ids.languageRouteLanguage.value="fr";ids.languageRouteLanguage.change();
  ids.languageRouteSet.click();
  assert.equal(ids.languageRouteLanguage.options.some(o=>o.value==="fr"),false);
  ids.languageRouteReload.click();await tick();
  assert.equal(ids.languageRouteLanguage.options.some(o=>o.value==="fr"),false,
    "reload retains server-side assignments, not unsaved local removals");
  // The same Supertonic ONNX engine supports multiple languages; do not
  // rely on the first-letter voice ID convention used for Kokoro.
  ids.languageRouteLanguage.value="ko";ids.languageRouteLanguage.change();
  assert.equal(ids.languageRouteEngine.value,"model-supertonic3-multilingual-int8-1_0_0");
  assert.equal(ids.languageRouteVoice.value,"ko_s0");
  ids.languageRouteSet.click();ids.languageRouteSave.click();await tick();
  assert.equal(stored.routes.ko.voice_id,"ko_s0");
  ids.languageRouteLanguage.value="zh";ids.languageRouteLanguage.change();
  assert.equal(ids.languageRouteEngine.value,"model-melo-chinese-onnx-1_0_0");
  assert.equal(ids.languageRouteVoice.value,"zh_melo");
  ids.languageRouteSet.click();ids.languageRouteSave.click();await tick();
  assert.equal(stored.routes.zh.voice_id,"zh_melo");

  // Bilingual Wayu voices must appear independently under Thai and English,
  // never under French, while preserving the non-commercial designation.
  const wayuId="personal-nc-wayu-paxa-edge-cpu";
  const makhamId="makham-paradee-cpu";
  ids.languageRouteLanguage.value="en";ids.languageRouteLanguage.change();
  assert.ok(ids.languageRouteEngine.options.some(o=>o.value===makhamId),
    "MakHam must be available for English as well as Thai");
  ids.languageRouteEngine.value=makhamId;ids.languageRouteEngine.change();
  assert.deepEqual(ids.languageRouteVoice.options.map(o=>o.value),
    ["paradee_thai"]);
  for(const id of ["fastthaig2p-cpu","makham-paradee-cpu","vachana-cpu",
    "model-fastthaig2p-thai-som-0_3_0",
    "model-vachana-thai-four-voices-1_0_0",
    "model-melo-chinese-onnx-1_0_0",engine,
    "model-supertonic3-multilingual-int8-1_0_0"]){
    assert.ok(ids.languageRouteEngine.options.some(o=>o.value===id),
      "English must be selectable on available model: "+id);
  }
  const enWayu=[...ids.languageRouteEngine.options].find(o=>o.value===wayuId);
  assert.ok(enWayu,"bilingual Wayu must be selectable as an English TTS model");
  assert.match(enWayu.textContent,/NC \/ NonCommercial/);
  ids.languageRouteEngine.value=wayuId;ids.languageRouteEngine.change();
  assert.deepEqual(ids.languageRouteVoice.options.map(x=>x.value),
    ["f_young_warm","m_mid_warm"]);
  ids.languageRouteVoice.value="f_young_warm";
  ids.languageRouteSet.click();
  ids.languageRouteLanguage.value="th";ids.languageRouteLanguage.change();
  assert.ok(ids.languageRouteEngine.options.some(x=>x.value===wayuId),
    "Wayu should still be offered for Thai even if assigned to English");
  assert.ok(ids.languageRouteEngine.options.some(x=>x.value===makhamId),
    "MakHam should also be offered for Thai");
  ids.languageRouteEngine.value=wayuId;ids.languageRouteEngine.change();
  ids.languageRouteVoice.value="f_young_warm";
  ids.languageRouteSet.click();
  ids.languageRouteSave.click();await tick();
  assert.equal(stored.routes.en.voice_id,"f_young_warm");
  assert.equal(stored.routes.th.voice_id,"f_young_warm");
  assert.equal(stored.routes.en.engine_id,wayuId);
  assert.equal(stored.routes.th.engine_id,wayuId);
  console.log("PASS: English on all installed engine families, existing per-voice language routing preserved");
})().catch(e=>{console.error(e);process.exitCode=1;});
