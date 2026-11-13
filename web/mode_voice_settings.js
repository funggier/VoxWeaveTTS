/* Independent, precise voice controls and folder-backed presets for each
 * speech workspace. Changes are sampled when the next TTS job is requested.
 */
(function(root){
"use strict";
const VOICE_MODES=Object.freeze([
  ["studio","สร้างเสียง"],["reader","อ่านเอกสาร"],["queue","คิวและ Subtitle"],
  ["live","YouTube LIVE (API)"],["youtube_browser","YouTube LIVE (Browser)"],["tiktok","TikTok LIVE (TikFinity)"],
  ["tiktok_browser","TikTok LIVE (Browser)"],
  ["discord","Discord"],["discord_client","Discord Client"],
]);
const SENDER_MODES=["live","youtube_browser","tiktok","tiktok_browser","discord","discord_client"];
const TUNING=[
  ["speed","ความเร็วในการอ่าน",0.60,5.00,1,"×"],
  ["gain_db","ความดัง",-18,12,0,"dB"],
  ["pitch_semitones","ระดับเสียง",-4,4,0,"st"],
  ["bass_db","เสียงทุ้ม",-12,12,0,"dB"],
  ["treble_db","เสียงแหลม",-12,12,0,"dB"],
];
function attach({document,engines,getDefault}){
  const controls=new Map();
  let revision=0, serial=Promise.resolve(),presets=[];
  const create=(tag,label)=>{
    const node=document.createElement(tag);
    if(label!==undefined)node.textContent=label;
    return node;
  };
  const installed=()=>engines().filter(e=>e.assets_ready&&e.runtime_ready);
  const two=value=>Number(value).toFixed(2);
  function rebuildVoices(mode,preferred){
    const ui=controls.get(mode);
    const info=engines().find(e=>e.id===ui.engine.value);
    ui.voice.replaceChildren();
    for(const v of info?.voices || (info?[{id:info.voice_id,label:info.voice_id}]:[])){
      const option=create("option",v.label||v.id);option.value=v.id;
      ui.voice.appendChild(option);
    }
    if(preferred&&[...ui.voice.options].some(x=>x.value===preferred))
      ui.voice.value=preferred;
  }
  function refreshEngines(){
    for(const [mode,ui] of controls){
      const oldEngine=ui.engine.value,oldVoice=ui.voice.value;
      ui.engine.replaceChildren();
      for(const info of installed()){
        const option=create("option",info.label||info.id);option.value=info.id;
        ui.engine.appendChild(option);
      }
      if(installed().some(x=>x.id===oldEngine))ui.engine.value=oldEngine;
      rebuildVoices(mode,oldVoice);
    }
    refreshPresetOptions();
  }
  function set(mode,profile){
    const ui=controls.get(mode);
    if(!ui||!profile)return;
    if(installed().some(x=>x.id===profile.engine_id)){
      ui.engine.value=profile.engine_id;
      rebuildVoices(mode,profile.voice_id);
    }else ui.status.textContent="โมเดลที่ตั้งไว้ยังไม่พร้อม · ใช้โมเดลที่ติดตั้งไว้ก่อน";
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
  function read(mode){
    const ui=controls.get(mode);
    if(!ui)return null;
    if(!installed().some(e=>e.id===ui.engine.value))
      throw Error("กรุณาเลือก Engine ที่พร้อมใช้งาน");
    const nums={};
    for(const [name,,min,max] of TUNING){
      const input=ui.numbers[name],str=input.value.trim(),value=Number(str);
      if(!str||!Number.isFinite(value)||value<min||value>max)
        throw Error(name+" ต้องอยู่ระหว่าง "+min+" และ "+max);
      nums[name]=Math.round(value*100)/100;
    }
    const seed=Number(ui.seed.value);
    if(ui.seed.value.trim()===""||!Number.isSafeInteger(seed)||seed<0||seed>2147483647)
      throw Error("Seed ต้องเป็นจำนวนเต็มระหว่าง 0 ถึง 2147483647");
    return {
      engine_id:ui.engine.value,voice_id:ui.voice.value,
      speed:nums.speed,seed,
      voice_controls:{
        gain_db:nums.gain_db,pitch_semitones:nums.pitch_semitones,
        bass_db:nums.bass_db,treble_db:nums.treble_db,
        formant_preserve:ui.formant.checked,
      },
    };
  }
  function refreshPresetOptions(){
    for(const ui of controls.values()){
      const previous=ui.presetSelect.value;
      ui.presetSelect.replaceChildren();
      const placeholder=create("option","เลือก Voice Preset");placeholder.value="";
      ui.presetSelect.appendChild(placeholder);
      for(const preset of presets){
        const ready=installed().some(info=>info.id===preset.engine_id);
        const label=ready?preset.name:preset.name+" (ต้องติดตั้งโมเดล: "+preset.engine_id+")";
        const option=create("option",label);option.value=preset.name;
        ui.presetSelect.appendChild(option);
      }
      if(presets.some(p=>p.name===previous))ui.presetSelect.value=previous;
    }
  }
  async function loadPresets(){
    const response=await fetch("/v1/presets",{cache:"no-store"});
    const body=await response.json();
    if(!response.ok)throw Error(body.error||"โหลด Preset ไม่สำเร็จ");
    presets=Array.isArray(body.presets)?body.presets:[];
    refreshPresetOptions();
    return presets;
  }
  async function savePreset(mode){
    const ui=controls.get(mode);
    try{
      const data=read(mode),name=ui.presetName.value.trim();
      if(!name)throw Error("กรุณากรอกชื่อ Preset");
      const response=await fetch("/v1/presets",{
        method:"POST",
        headers:{"Content-Type":"application/json",
                 "X-VoxWeaveTTS-Intent":"save-voice-preset"},
        body:JSON.stringify({name,...data}),
      });
      const result=await response.json();
      if(!response.ok)throw Error(result.error||"บันทึก Preset ไม่สำเร็จ");
      await loadPresets();
      ui.presetSelect.value=result.preset.name;
      ui.status.textContent="บันทึก Preset "+result.preset.name+
        " ลงโฟลเดอร์ presets/ ของโปรแกรมแล้ว";
    }catch(error){ui.status.textContent=String(error.message||error);}
  }
  function applyPreset(mode){
    const ui=controls.get(mode);
    const preset=presets.find(p=>p.name===ui.presetSelect.value);
    if(!preset){ui.status.textContent="กรุณาเลือก Preset ก่อน";return;}
    if(!installed().some(x=>x.id===preset.engine_id)){
      ui.status.textContent="Engine ของ Preset นี้ยังไม่พร้อม · ติดตั้ง Model Package ก่อน";
      return;
    }
    set(mode,preset);
    ui.presetName.value=preset.name;
    ui.status.textContent="ใช้ Preset "+preset.name+" ในโหมดนี้แล้ว · มีผลกับเสียงที่สร้างใหม่";
  }
  async function save(mode){
    const ui=controls.get(mode);
    ui.save.disabled=true;ui.status.textContent="กำลังบันทึก...";
    try{
      const snapshot=read(mode);
      await (serial=serial.catch(()=>{}).then(async()=>{
        const response=await fetch("/v1/settings/mode-voices",{
          method:"POST",
          headers:{"Content-Type":"application/json",
                   "X-VoxWeaveTTS-Intent":"save-mode-voice"},
          body:JSON.stringify({expected_revision:revision,mode,settings:snapshot}),
        });
        const data=await response.json();
        if(!response.ok)throw Error(data.error||"บันทึกค่าเสียงไม่สำเร็จ");
        revision=data.revision;
      }));
      ui.status.textContent="บันทึกแล้ว · มีผลกับประโยคใหม่";
    }catch(error){ui.status.textContent=String(error.message||error);}
    finally{ui.save.disabled=false;}
  }
  for(const [mode,label] of VOICE_MODES){
    const view=document.querySelector('[data-mode-view="'+mode+'"]');
    if(!view)continue;
    const panel=create("details");panel.className="mode-voice-settings";
    panel.style.margin="12px 0";panel.style.padding="12px";
    panel.style.border="1px solid #40516d";panel.style.borderRadius="10px";
    panel.appendChild(create("summary","ปรับเสียงและโมเดลของ "+label));
    const desc=create("p",
      "การปรับนี้ใช้เฉพาะโหมดนี้ · ความเร็ว ×0.60–×5.00 และ DSP ปรับละเอียด 0.01 · ค่าใหม่ใช้กับประโยคที่ยังไม่เริ่มสร้างเสียง");
    desc.className="small";panel.appendChild(desc);
    const grid=create("div");grid.className="mode-voice-grid";
    const engine=create("select"),voice=create("select");
    for(const [name,element] of [["Engine / Model",engine],["Voice",voice]]){
      const holder=create("div");
      holder.appendChild(create("label",name));holder.appendChild(element);
      grid.appendChild(holder);
    }
    const numbers={},sliders={};
    for(const [name,label,min,max,fallback,unit] of TUNING){
      const holder=create("div");holder.className="voice-row";
      const labelEl=create("label",label);
      const slider=create("input"),number=create("input");
      slider.type="range";slider.min=String(min);slider.max=String(max);
      slider.step="0.01";slider.value=String(fallback);
      number.type="number";number.min=String(min);number.max=String(max);
      number.step="0.01";number.value=two(fallback);
      const suffix=create("span",unit);suffix.className="small";
      slider.addEventListener("input",()=>{number.value=two(slider.value);});
      number.addEventListener("input",()=>{
        if(number.value.trim()!=="")slider.value=number.value;
      });
      number.addEventListener("change",()=>{
        const n=Number(number.value);
        if(Number.isFinite(n)&&n>=min&&n<=max)number.value=two(n);
      });
      holder.append(labelEl,slider,number,suffix);
      grid.appendChild(holder);
      numbers[name]=number;sliders[name]=slider;
    }
    const formant=create("input");formant.type="checkbox";formant.checked=true;
    const formantLabel=create("label"," รักษา Formant ขณะปรับ Pitch");
    formantLabel.prepend(formant);grid.appendChild(formantLabel);
    const seed=create("input");seed.type="number";seed.min="0";
    seed.max="2147483647";seed.step="1";seed.value="100";
    const seedHolder=create("div");
    seedHolder.appendChild(create("label","Seed (จำนวนเต็ม)"));
    seedHolder.appendChild(seed);grid.appendChild(seedHolder);
    panel.appendChild(grid);
    const saveButton=create("button","บันทึกเสียงของช่องทางนี้");
    saveButton.type="button";
    const status=create("span","ค่าที่ปรับมีผลกับเสียงใหม่ทันที · กดบันทึกเพื่อใช้ครั้งถัดไป");
    status.className="small";status.style.marginLeft="10px";
    panel.append(saveButton,status);
    const presetArea=create("div");presetArea.style.marginTop="14px";
    presetArea.appendChild(create("h3","Voice Presets (โฟลเดอร์ presets/)"));
    const hint=create("p","คัดลอกไฟล์ .json ลงในโฟลเดอร์ presets ของโปรแกรม แล้วกดรีเฟรชเพื่อใช้ Preset ในแต่ละช่องทางได้");
    hint.className="small";presetArea.appendChild(hint);
    const presetGrid=create("div");presetGrid.className="voice-grid";
    const presetName=create("input"),presetSelect=create("select");
    presetName.type="text";presetName.maxLength=50;
    presetName.placeholder="ชื่อ Preset เช่น นิยายเสียงนุ่ม";
    const nameHolder=create("div");
    nameHolder.appendChild(create("label","ชื่อ Preset"));
    nameHolder.appendChild(presetName);
    const selectHolder=create("div");
    selectHolder.appendChild(create("label","Preset ที่บันทึกไว้"));
    selectHolder.appendChild(presetSelect);
    const savePresetButton=create("button","บันทึก Preset");
    const applyPresetButton=create("button","ใช้ Preset");
    const refreshPresetButton=create("button","รีเฟรช Preset");
    for(const button of [savePresetButton,applyPresetButton,refreshPresetButton])
      button.type="button";
    presetGrid.append(nameHolder,savePresetButton,selectHolder,applyPresetButton,refreshPresetButton);
    presetArea.appendChild(presetGrid);panel.appendChild(presetArea);
    view.insertBefore(panel,view.firstChild);
    const ui={engine,voice,numbers,sliders,formant,seed,save:saveButton,status,
              presetName,presetSelect};
    controls.set(mode,ui);
    engine.addEventListener("change",()=>rebuildVoices(mode));
    saveButton.addEventListener("click",()=>save(mode));
    savePresetButton.addEventListener("click",()=>savePreset(mode));
    applyPresetButton.addEventListener("click",()=>applyPreset(mode));
    refreshPresetButton.addEventListener("click",()=>{
      loadPresets().then(()=>{status.textContent="รีเฟรช Preset แล้ว ("+presets.length+" รายการ)";})
        .catch(e=>{status.textContent=String(e.message||e);});
    });
    panel.addEventListener("toggle",()=>{
      if(panel.open)loadPresets().catch(e=>{status.textContent=String(e.message||e);});
    });
  }
  refreshEngines();refreshPresetOptions();
  async function load(){
    const response=await fetch("/v1/settings/mode-voices",{cache:"no-store"});
    const data=await response.json();
    if(!response.ok)throw Error(data.error||"ไม่สามารถโหลดค่าเสียงของช่องทางได้");
    revision=data.revision;
    refreshEngines();
    for(const [mode] of controls)
      set(mode,data.modes?.[mode]||getDefault());
    for(const mode of SENDER_MODES){
      const prefix=mode==="discord_client"?"discordClient":mode==="youtube_browser"?"youtubeBrowser":mode==="tiktok_browser"?"tiktokBrowser":mode;
      const checkbox=document.getElementById?.(prefix+"FeedReadSender");
      if(checkbox)checkbox.checked=data.sender_names?.[mode]===true;
    }
    await loadPresets();
    return data;
  }
  async function saveSenderName(mode,enabled){
    if(!SENDER_MODES.includes(mode)||typeof enabled!=="boolean")
      throw Error("Invalid sender-name preference");
    await (serial=serial.catch(()=>{}).then(async()=>{
      const response=await fetch("/v1/settings/mode-voices",{
        method:"POST",
        headers:{"Content-Type":"application/json",
                 "X-VoxWeaveTTS-Intent":"save-mode-voice"},
        body:JSON.stringify({
          expected_revision:revision,mode:"__sender__",
          settings:{source_mode:mode,enabled},
        }),
      });
      const data=await response.json();
      if(!response.ok)throw Error(data.error||"Could not save sender-name preference");
      revision=data.revision;
    }));
  }
  for(const mode of SENDER_MODES){
    const prefix=mode==="discord_client"?"discordClient":mode;
    const checkbox=document.getElementById?.(prefix+"FeedReadSender");
    const status=document.getElementById?.(prefix+"FeedReadSenderStatus");
    checkbox?.addEventListener("change",async()=>{
      const desired=checkbox.checked;
      if(status)status.textContent="กำลังบันทึก...";
      try{
        await saveSenderName(mode,desired);
        if(status)status.textContent="บันทึกแล้ว";
      }catch{
        if(status)status.textContent="บันทึกไม่สำเร็จ · ค่ายังมีผลในหน้านี้";
      }
    });
  }
  async function savePolicy(policy){
    await (serial=serial.catch(()=>{}).then(async()=>{
      const response=await fetch("/v1/settings/mode-voices",{
        method:"POST",
        headers:{"Content-Type":"application/json",
                 "X-VoxWeaveTTS-Intent":"save-mode-voice"},
        body:JSON.stringify({expected_revision:revision,mode:"__policy__",settings:policy}),
      });
      const data=await response.json();
      if(!response.ok)throw Error(data.error||"บันทึกคิวเสียงไม่สำเร็จ");
      revision=data.revision;
    }));
  }
  return {load,read,save,savePolicy,saveSenderName,loadPresets,refreshEngines,
          settingsFor:mode=>read(mode),
          get modes(){return [...controls.keys()];}};
}
root.VoxModeVoiceSettings={attach};
if(typeof module!=="undefined"&&module.exports)module.exports={attach,VOICE_MODES};
})(typeof window==="undefined"?globalThis:window);
