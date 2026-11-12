/* Voice settings per workspace. Live values are used by the NEXT TTS job.
 * Existing queued/rendered audio keeps its immutable request snapshot.
 * "Save" persists independently to the portable app's local JSON storage.
 */
(function(root){
"use strict";
const VOICE_MODES=Object.freeze([
  ["studio","สร้างเสียง"],["reader","อ่านเอกสาร"],["queue","คิวและ Subtitle"],
  ["live","YouTube LIVE"],["tiktok","TikTok LIVE"],
  ["discord","Discord"],["discord_client","Discord Client"],
]);
const TUNING=[
  ["speed","ความเร็ว",0.6,1.5,0.05,1],
  ["gain_db","ความดัง (dB)",-18,12,0.5,0],
  ["pitch_semitones","Pitch (st)",-4,4,0.25,0],
  ["bass_db","Bass (dB)",-12,12,0.5,0],
  ["treble_db","Treble (dB)",-12,12,0.5,0],
];
function attach({document,engines,getDefault}){
  const panels=new Map(),controls=new Map();
  let revision=0, serial=Promise.resolve();
  const create=(tag,text)=>{
    const element=document.createElement(tag);
    if(text)element.textContent=text;
    return element;
  };
  const installed=()=>engines().filter(x=>x.assets_ready&&x.runtime_ready);
  function rebuildVoices(mode,preferred){
    const ui=controls.get(mode);
    const engine=engines().find(x=>x.id===ui.engine.value);
    ui.voice.replaceChildren();
    for(const v of engine?.voices || (engine?[{id:engine.voice_id,label:engine.voice_id}]:[])){
      const option=create("option",v.label||v.id);option.value=v.id;
      ui.voice.appendChild(option);
    }
    if(preferred && [...ui.voice.options].some(v=>v.value===preferred))
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
  }
  function set(mode,profile){
    const ui=controls.get(mode);
    if(!ui||!profile)return;
    if(installed().some(x=>x.id===profile.engine_id)){
      ui.engine.value=profile.engine_id;
      rebuildVoices(mode,profile.voice_id);
    }else ui.status.textContent="Engine เดิมยังไม่พร้อม ใช้ตัวสำรองชั่วคราว";
    for(const [name,,min,max,,fallback] of TUNING){
      const value=name==="speed"?profile.speed:profile.voice_controls?.[name];
      ui.numbers[name].value=typeof value==="number"&&Number.isFinite(value)
        &&value>=min&&value<=max?String(value):String(fallback);
    }
    ui.formant.checked=profile.voice_controls?.formant_preserve!==false;
  }
  function read(mode){
    const ui=controls.get(mode);
    if(!ui)return null;
    const engine=engines().find(x=>x.id===ui.engine.value);
    if(!engine)return null;
    const numbers={};
    for(const [name,,min,max,,fallback] of TUNING){
      const value=Number(ui.numbers[name].value);
      numbers[name]=Number.isFinite(value)&&value>=min&&value<=max?value:fallback;
    }
    return {
      engine_id:ui.engine.value,voice_id:ui.voice.value,
      speed:numbers.speed,
      voice_controls:{
        gain_db:numbers.gain_db,
        pitch_semitones:numbers.pitch_semitones,
        bass_db:numbers.bass_db,treble_db:numbers.treble_db,
        formant_preserve:ui.formant.checked,
      },
    };
  }
  async function save(mode){
    const ui=controls.get(mode);
    ui.save.disabled=true;
    ui.status.textContent="กำลังบันทึก...";
    try{
      const payload=read(mode);
      if(!payload)throw Error("Engine ไม่พร้อม");
      // Prevent two modes racing on the persisted revision.
      await (serial=serial.catch(()=>{}).then(async()=>{
        const response=await fetch("/v1/settings/mode-voices",{
          method:"POST",
          headers:{"Content-Type":"application/json","X-VoxWeaveTTS-Intent":"save-mode-voice"},
          body:JSON.stringify({
            expected_revision:revision,mode,settings:payload,
          }),
        });
        const result=await response.json();
        if(!response.ok)throw Error(result.error||"ไม่สามารถบันทึกเสียงของช่องทางได้");
        revision=result.revision;
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
    const summary=create("summary","เสียงเฉพาะช่องทาง: "+label);
    panel.appendChild(summary);
    const desc=create("p","ตั้งค่าที่นี่เป็นอิสระจากช่องทางอื่น และมีผลกับข้อความใหม่ที่ยังไม่เริ่มสร้างเสียง");
    desc.className="small";panel.appendChild(desc);
    const grid=create("div");grid.className="voice-grid";
    const engine=create("select"),voice=create("select");
    for(const [name,element] of [["Engine / Model",engine],["Voice",voice]]){
      const holder=create("div");
      holder.appendChild(create("label",name));holder.appendChild(element);
      grid.appendChild(holder);
    }
    const numbers={};
    for(const [name,label,min,max,step,fallback] of TUNING){
      const holder=create("div"),number=create("input");
      number.type="number";number.min=String(min);number.max=String(max);
      number.step=String(step);number.value=String(fallback);
      holder.appendChild(create("label",label));holder.appendChild(number);
      grid.appendChild(holder);numbers[name]=number;
    }
    const formant=create("input");formant.type="checkbox";formant.checked=true;
    const holder=create("label"," รักษา Formant เมื่อปรับ Pitch");
    holder.prepend(formant);grid.appendChild(holder);
    panel.appendChild(grid);
    const saveButton=create("button","บันทึกเสียงของช่องทางนี้");
    saveButton.type="button";
    const status=create("span","ยังไม่ได้บันทึกค่าช่องทางนี้");
    status.className="small";status.style.marginLeft="10px";
    panel.append(saveButton,status);
    view.insertBefore(panel,view.firstChild);
    controls.set(mode,{engine,voice,numbers,formant,save:saveButton,status});
    panels.set(mode,panel);
    engine.addEventListener("change",()=>rebuildVoices(mode));
    saveButton.addEventListener("click",()=>save(mode));
  }
  refreshEngines();
  async function load(){
    const response=await fetch("/v1/settings/mode-voices",{cache:"no-store"});
    const data=await response.json();
    if(!response.ok)throw Error(data.error||"Cannot load workspace voices");
    revision=data.revision;
    refreshEngines();
    for(const [mode] of controls){
      const value=data.modes?.[mode] || getDefault();
      set(mode,value);
    }
    return data;
  }
  async function savePolicy(policy){
    await (serial=serial.catch(()=>{}).then(async()=>{
      const response=await fetch("/v1/settings/mode-voices",{
        method:"POST",
        headers:{"Content-Type":"application/json","X-VoxWeaveTTS-Intent":"save-mode-voice"},
        body:JSON.stringify({expected_revision:revision,mode:"__policy__",settings:policy}),
      });
      const data=await response.json();
      if(!response.ok)throw Error(data.error||"Cannot save playback policy");
      revision=data.revision;
    }));
  }
  return {load,read,save,savePolicy,refreshEngines,settingsFor:mode=>read(mode),
          get modes(){return [...controls.keys()];}};
}
root.VoxModeVoiceSettings={attach};
if(typeof module!=="undefined"&&module.exports)module.exports={attach,VOICE_MODES};
})(typeof window==="undefined"?globalThis:window);
