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
  // Keep the same tuning schema and preset store as each workspace's
  // "ปรับเสียงและโมเดล" panel. Every language has an independent editor.
  const TUNING=[
    ["speed","ความเร็วในการอ่าน",0.60,5.00,1,"×"],
    ["gain_db","ความดัง",-18,12,0,"dB"],
    ["pitch_semitones","ระดับเสียง",-4,4,0,"st"],
    ["bass_db","เสียงทุ้ม",-12,12,0,"dB"],
    ["treble_db","เสียงแหลม",-12,12,0,"dB"],
  ];
  const routeRows=new Map(),routeEditors=new Map();
  let presets=[];
  let saveQueue=Promise.resolve();
  const create=(tag,label)=>{
    const node=document.createElement(tag);
    if(label!==undefined)node.textContent=label;
    return node;
  };
  const two=n=>Number(n).toFixed(2);

  async function saveAllRoutes(){
    // Serialize both the top-level save and individual language saves so
    // revisions cannot race and overwrite another language's settings.
    const snapshot=JSON.parse(JSON.stringify(routes));
    return saveQueue=saveQueue.catch(()=>{}).then(async()=>{
      const saved=await request("/v1/settings/language-routes",{
        method:"POST",
        headers:{"Content-Type":"application/json",
                 "X-VoxWeaveTTS-Intent":"save-language-routes"},
        body:JSON.stringify({expected_revision:revision,routes:snapshot})
      });
      revision=saved.revision;
      return saved;
    });
  }
  function readTuning(ui){
    const values={};
    for(const [name,,min,max] of TUNING){
      const raw=String(ui.numbers[name].value??"").trim();
      const value=Number(raw);
      if(!raw||!Number.isFinite(value)||value<min||value>max)
        throw Error(name+" ต้องอยู่ระหว่าง "+min+" ถึง "+max);
      values[name]=Math.round(value*100)/100;
    }
    const rawSeed=String(ui.seed.value??"").trim();
    const seed=Number(rawSeed);
    if(!rawSeed||!Number.isSafeInteger(seed)||seed<0||seed>2147483647)
      throw Error("Seed ต้องเป็นจำนวนเต็ม 0 ถึง 2147483647");
    return {
      speed:values.speed,seed,
      voice_controls:{
        gain_db:values.gain_db,pitch_semitones:values.pitch_semitones,
        bass_db:values.bass_db,treble_db:values.treble_db,
        formant_preserve:ui.formant.checked,
      }
    };
  }
  function setTuning(ui,profile){
    for(const [name,,min,max,fallback] of TUNING){
      const raw=name==="speed"?profile.speed:profile.voice_controls?.[name];
      const value=typeof raw==="number"&&Number.isFinite(raw)
        &&raw>=min&&raw<=max?raw:fallback;
      ui.numbers[name].value=two(value);
      ui.sliders[name].value=String(value);
    }
    ui.formant.checked=profile.voice_controls?.formant_preserve!==false;
    ui.seed.value=String(profile.seed??100);
  }
  function populatePresets(){
    for(const ui of routeEditors.values()){
      const previous=ui.presetSelect.value;
      ui.presetSelect.replaceChildren();
      const placeholder=create("option","เลือก Voice Preset");
      placeholder.value="";ui.presetSelect.appendChild(placeholder);
      for(const item of presets){
        const option=create("option",item.name);
        option.value=item.name;
        ui.presetSelect.appendChild(option);
      }
      if(presets.some(p=>p.name===previous))ui.presetSelect.value=previous;
    }
  }
  async function loadPresets(){
    const data=await request("/v1/presets");
    presets=Array.isArray(data.presets)?data.presets:[];
    populatePresets();
  }
  function voiceEditor(language){
    const route=routes[language];
    const details=create("details");
    details.className="mode-voice-settings";
    details.style.margin="10px 0 18px";
    details.style.padding="12px";
    details.style.border="1px solid #40516d";
    details.style.borderRadius="10px";
    details.appendChild(create("summary","ปรับเสียง"));
    const help=create("p",
      "ค่าปรับนี้ใช้เฉพาะภาษา "+(languages[language]||language)+
      " · แยกจาก Default Engine / Model ของแต่ละโหมด · มีผลกับประโยคใหม่หลังบันทึก");
    help.className="small";details.appendChild(help);
    const grid=create("div");grid.className="mode-voice-grid";
    const ui={numbers:{},sliders:{},status:null};
    for(const [name,label,min,max,fallback,unit] of TUNING){
      const holder=create("div");holder.className="voice-row";
      const caption=create("label",label);
      const slider=create("input");slider.type="range";
      slider.min=String(min);slider.max=String(max);slider.step="0.01";
      const number=create("input");number.type="number";
      number.min=String(min);number.max=String(max);number.step="0.01";
      slider.value=String(fallback);number.value=two(fallback);
      slider.addEventListener("input",()=>{number.value=two(slider.value);});
      number.addEventListener("input",()=>{
        if(String(number.value).trim()!=="")slider.value=String(number.value);
      });
      number.addEventListener("change",()=>{
        const n=Number(number.value);
        if(Number.isFinite(n)&&n>=min&&n<=max)number.value=two(n);
      });
      holder.appendChild(caption);holder.appendChild(slider);
      holder.appendChild(number);holder.appendChild(create("span",unit));
      grid.appendChild(holder);
      ui.numbers[name]=number;ui.sliders[name]=slider;
    }
    const formantLabel=create("label");
    ui.formant=create("input");ui.formant.type="checkbox";
    formantLabel.appendChild(ui.formant);
    formantLabel.appendChild(create("span"," รักษา Formant ขณะปรับ Pitch"));
    grid.appendChild(formantLabel);
    const seedHolder=create("div");
    seedHolder.appendChild(create("label","Seed (จำนวนเต็ม)"));
    ui.seed=create("input");ui.seed.type="number";
    ui.seed.min="0";ui.seed.max="2147483647";ui.seed.step="1";
    seedHolder.appendChild(ui.seed);grid.appendChild(seedHolder);
    details.appendChild(grid);
    const save=create("button","บันทึกเสียงของภาษานี้");
    save.type="button";
    ui.status=create("span","ค่าที่ปรับยังไม่บันทึก");
    ui.status.className="small";ui.status.style.marginLeft="10px";
    details.appendChild(save);details.appendChild(ui.status);

    const presetArea=create("div");presetArea.style.marginTop="14px";
    presetArea.appendChild(create("h3","Voice Presets (โฟลเดอร์ presets/)"));
    const note=create("p","ใช้ Preset ร่วมกับโหมดอื่นได้ โดยคง Engine และเสียงของภาษานี้ไว้");
    note.className="small";presetArea.appendChild(note);
    const presetGrid=create("div");presetGrid.className="voice-grid";
    const nameHolder=create("div");
    nameHolder.appendChild(create("label","ชื่อ Preset"));
    ui.presetName=create("input");ui.presetName.type="text";
    ui.presetName.maxLength=50;ui.presetName.placeholder="ชื่อ Preset เช่น เสียงอ่านช้า";
    nameHolder.appendChild(ui.presetName);
    const selectHolder=create("div");
    selectHolder.appendChild(create("label","Preset ที่บันทึกไว้"));
    ui.presetSelect=create("select");
    selectHolder.appendChild(ui.presetSelect);
    const presetSave=create("button","บันทึก Preset");
    const presetApply=create("button","ใช้ Preset");
    const presetRefresh=create("button","รีเฟรช Preset");
    for(const button of [presetSave,presetApply,presetRefresh])button.type="button";
    for(const node of [nameHolder,presetSave,selectHolder,presetApply,presetRefresh])
      presetGrid.appendChild(node);
    presetArea.appendChild(presetGrid);details.appendChild(presetArea);
    routeEditors.set(language,ui);
    setTuning(ui,route);
    populatePresets();

    save.addEventListener("click",async()=>{
      save.disabled=true;
      try{
        const profile=readTuning(ui);
        routes[language]={...routes[language],...profile};
        await saveAllRoutes();
        ui.status.textContent="บันทึกเสียงของภาษา "+language+" แล้ว · ใช้กับประโยคใหม่";
        status("บันทึกการตั้งค่าเสียงของภาษา "+language+" แล้ว");
      }catch(error){ui.status.textContent="บันทึกไม่สำเร็จ: "+String(error.message||error);}
      finally{save.disabled=false;}
    });
    presetSave.addEventListener("click",async()=>{
      presetSave.disabled=true;
      try{
        const name=String(ui.presetName.value??"").trim();
        if(!name)throw Error("กรุณากรอกชื่อ Preset");
        const profile=readTuning(ui);
        const result=await request("/v1/presets",{
          method:"POST",
          headers:{"Content-Type":"application/json",
                   "X-VoxWeaveTTS-Intent":"save-voice-preset"},
          body:JSON.stringify({name,
            engine_id:routes[language].engine_id,voice_id:routes[language].voice_id,
            ...profile})
        });
        await loadPresets();
        ui.presetSelect.value=result.preset.name;
        ui.status.textContent="บันทึก Preset "+result.preset.name+" ใน presets/ แล้ว";
      }catch(error){ui.status.textContent="บันทึก Preset ไม่สำเร็จ: "+String(error.message||error);}
      finally{presetSave.disabled=false;}
    });
    presetApply.addEventListener("click",()=>{
      const preset=presets.find(p=>p.name===ui.presetSelect.value);
      if(!preset){ui.status.textContent="กรุณาเลือก Voice Preset";return;}
      setTuning(ui,preset);
      ui.presetName.value=preset.name;
      ui.status.textContent="โหลด Preset "+preset.name+
        " แล้ว (คง Engine และ Voice ของภาษา "+language+") · กดบันทึกเสียงของภาษานี้";
    });
    presetRefresh.addEventListener("click",()=>{
      loadPresets().then(()=>{ui.status.textContent="รีเฟรช Preset แล้ว ("+presets.length+" รายการ)";})
        .catch(error=>{ui.status.textContent=String(error.message||error);});
    });
    details.addEventListener("toggle",()=>{
      if(details.open)loadPresets().catch(error=>{
        ui.status.textContent="โหลด Preset ไม่สำเร็จ: "+String(error.message||error);
      });
    });
    return details;
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
      let row=routeRows.get(language);
      if(!row){
        const info=engines.find(e=>e.id===route.engine_id);
        const name=languages[language]||language;
        const ready=info?.assets_ready&&info?.runtime_ready;
        row=create("li");
        const title=create("span");
        title.style.marginLeft="14px";
        title.textContent=name+" ("+language+") : "+(info?.label||route.engine_id)+
          " / "+route.voice_id+(ready?"":" [โมเดลยังไม่พร้อม]");
        const remove=create("button","ลบ");
        remove.type="button";
        remove.addEventListener("click",()=>{
          delete routes[language];
          routeRows.delete(language);routeEditors.delete(language);
          refreshLanguageChoices();drawRoutes();
          status("ยังไม่ได้บันทึก: ลบการกำหนดภาษา "+language+" แล้ว");
        });
        row.appendChild(remove);
        row.appendChild(title);
        row.appendChild(voiceEditor(language));
        routeRows.set(language,row);
      }
      list.appendChild(row);
    }
    if(!Object.keys(routes).length){
      const row=create("li","ยังไม่มีการกำหนดภาษา; จะใช้ Engine ตามโหมด");
      list.appendChild(row);
    }
  }
  async function load(){
    const [config,registry]=await Promise.all([
      request("/v1/settings/language-routes"),
      request("/v1/engines"),
    ]);
    revision=config.revision;routes={...config.routes};
    routeRows.clear();routeEditors.clear();
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
      // The global Save button also commits edits made in expanded voice panels.
      for(const [language,ui] of routeEditors)
        if(routes[language])routes[language]={...routes[language],...readTuning(ui)};
      await saveAllRoutes();
      status("บันทึกแล้ว · โมเดลและค่าปรับเสียงตามภาษาใช้กับประโยคใหม่");
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
