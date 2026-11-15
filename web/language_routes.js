/* Language -> Engine -> Voice routing. No model files or paths from the browser. */
(function(root){
"use strict";
function attach(document, fetcher){
  const el=id=>document.getElementById(id);
  if(!el("languageRouteLanguage"))return null;
  let revision=0, routes={}, languages={}, engines=[];
  const voiceLanguage=voice=>{
    const family=String(voice||"")[0];
    return ({a:"en",b:"en",e:"es",f:"fr",h:"hi",i:"it",j:"ja",p:"pt"})[family]||"";
  };
  const supports=(engine,voice,language)=>
    engine.language==="multi"?voiceLanguage(voice)===language:
    engine.language===language;
  function status(message){el("languageRouteStatus").textContent=message;}
  async function request(url,options){
    const response=await fetcher(url,options||{cache:"no-store"});
    const data=await response.json();
    if(!response.ok)throw Error(data.error||"ไม่สามารถเชื่อมต่อการตั้งค่าได้");
    return data;
  }
  function voices(engine){
    return Array.isArray(engine?.voices)?engine.voices:[];
  }
  function updateEngineChoices(){
    const language=el("languageRouteLanguage").value;
    const selected=el("languageRouteEngine").value;
    const select=el("languageRouteEngine");
    select.replaceChildren();
    for(const info of engines){
      if(!info.assets_ready||!info.runtime_ready)continue;
      if(!voices(info).some(v=>supports(info,v.id,language)))continue;
      const option=document.createElement("option");
      option.value=info.id; option.textContent=info.label;
      select.appendChild(option);
    }
    if([...select.options].some(o=>o.value===selected))select.value=selected;
    updateVoiceChoices();
  }
  function updateVoiceChoices(){
    const language=el("languageRouteLanguage").value;
    const info=engines.find(e=>e.id===el("languageRouteEngine").value);
    const select=el("languageRouteVoice");
    const selected=select.value;
    select.replaceChildren();
    for(const voice of voices(info)){
      if(!supports(info,voice.id,language))continue;
      const option=document.createElement("option");
      option.value=voice.id;option.textContent=voice.label||voice.id;
      select.appendChild(option);
    }
    if([...select.options].some(o=>o.value===selected))select.value=selected;
  }
  function refreshLanguageChoices(){
    const select=el("languageRouteLanguage");
    const previous=select.value;
    select.replaceChildren();
    for(const [code,label] of Object.entries(languages)){
      if(Object.hasOwn(routes,code))continue;
      const option=document.createElement("option");
      option.value=code;
      option.textContent=label+" ("+code+")";
      select.appendChild(option);
    }
    if([...select.options].some(option=>option.value===previous))
      select.value=previous;
    const hasAvailable=select.options.length>0;
    select.disabled=!hasAvailable;
    el("languageRouteSet").disabled=!hasAvailable;
    selectLanguage();
  }
  function selectLanguage(){
    updateEngineChoices();
    const language=el("languageRouteLanguage").value;
    const saved=routes[language];
    if(saved&&[...el("languageRouteEngine").options].some(o=>o.value===saved.engine_id)){
      el("languageRouteEngine").value=saved.engine_id;
      updateVoiceChoices();
      if([...el("languageRouteVoice").options].some(o=>o.value===saved.voice_id))
        el("languageRouteVoice").value=saved.voice_id;
    }
  }
  function drawRoutes(){
    const list=el("languageRouteList");
    list.replaceChildren();
    for(const [language,route] of Object.entries(routes)){
      const info=engines.find(e=>e.id===route.engine_id);
      const name=languages[language]||language;
      const ready=info?.assets_ready&&info?.runtime_ready;
      const row=document.createElement("li");
      const title=document.createElement("span");
      title.textContent=name+" ("+language+") : "+(info?.label||route.engine_id)+
        " / "+route.voice_id+(ready?"":" [โมเดลยังไม่พร้อม]");
      const remove=document.createElement("button");
      remove.type="button";remove.textContent="ลบ";
      remove.addEventListener("click",()=>{
        delete routes[language];refreshLanguageChoices();drawRoutes();
        status("ยังไม่ได้บันทึก: ลบการกำหนดภาษา "+language+" แล้ว");
      });
      row.appendChild(remove);row.appendChild(title);list.appendChild(row);
    }
    if(!Object.keys(routes).length){
      const row=document.createElement("li");
      row.textContent="ยังไม่มีการกำหนดภาษา; จะใช้ Engine ตามโหมด";
      list.appendChild(row);
    }
  }
  async function load(){
    const [config,registry]=await Promise.all([
      request("/v1/settings/language-routes"),
      request("/v1/engines"),
    ]);
    revision=config.revision;routes={...config.routes};
    languages=config.languages||{};
    engines=registry.engines||[];

    refreshLanguageChoices();drawRoutes();
    status("โหลดรายการภาษาและโมเดลแล้ว; การตั้งค่ามีผลกับงานเสียงใหม่");
  }
  el("languageRouteLanguage").addEventListener("change",selectLanguage);
  el("languageRouteEngine").addEventListener("change",updateVoiceChoices);
  el("languageRouteSet").addEventListener("click",()=>{
    const language=el("languageRouteLanguage").value;
    const engine_id=el("languageRouteEngine").value;
    const voice_id=el("languageRouteVoice").value;
    if(!language||!engine_id||!voice_id){
      status("ไม่มี Engine/เสียงที่พร้อมสำหรับภาษานี้");return;
    }
    const engine=engines.find(e=>e.id===engine_id);
    if(!engine||!supports(engine,voice_id,language)){
      status("ไม่สามารถกำหนดเสียงนี้ให้ภาษาที่เลือก");return;
    }
    routes[language]={engine_id,voice_id};
    refreshLanguageChoices();drawRoutes();status("กำหนดแล้ว โปรดกดบันทึกการตั้งค่า");
  });
  el("languageRouteSave").addEventListener("click",async()=>{
    const button=el("languageRouteSave");button.disabled=true;
    try{
      const saved=await request("/v1/settings/language-routes",{
        method:"POST",
        headers:{"Content-Type":"application/json",
                 "X-VoxWeaveTTS-Intent":"save-language-routes"},
        body:JSON.stringify({expected_revision:revision,
          routes})
      });
      revision=saved.revision;
      status("บันทึกแล้ว; งานอ่านเสียงถัดไปจะเลือกโมเดลตามภาษา");
    }catch(e){status("บันทึกไม่สำเร็จ: "+String(e.message||e));}
    finally{button.disabled=false;}
  });
  el("languageRouteReload").addEventListener("click",()=>{
    load().catch(e=>status(String(e.message||e)));
  });

  load().catch(e=>status(String(e.message||e)));
  return {load};
}
root.VoxLanguageRoutes={attach};
if(typeof module!=="undefined"&&module.exports)module.exports={attach};
if(typeof document!=="undefined"&&document.getElementById("languageRouteLanguage"))
  attach(document,root.fetch.bind(root));
})(typeof window==="undefined"?globalThis:window);
