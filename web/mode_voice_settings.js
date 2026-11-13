/* Independent, precise voice controls and folder-backed presets for each
 * speech workspace. Changes are sampled when the next TTS job is requested.
 */
(function(root){
"use strict";
const VOICE_MODES=Object.freeze([
  ["studio","สร้างเสียง"],["reader","อ่านเอกสาร"],["queue","คิวและ Subtitle"],
  ["live","YouTube LIVE (API)"],["youtube_browser","YouTube LIVE (Browser)"],["tiktok","TikTok LIVE (TikFinity)"],
  ["tiktok_browser","TikTok LIVE (Extension)"],
  ["discord","Discord"],["discord_client","Discord Client"],
]);
const SENDER_MODES=["live","youtube_browser","tiktok","tiktok_browser","discord","discord_client"];
const Emoji=root.VoxEmojiPronunciation ||
  (typeof require==="function"?require("./emoji_pronunciation.js"):null);
const DEFAULT_FORMAT=Object.freeze({
  sender_prefix:"คุณ",separator:"พิมพ์ว่า",
  read_comments:true,
  read_levels:false,read_ranks:false,read_badges:false,read_gift_count:true,
  read_name_emojis:false,read_name_at:false,
  read_emojis:false,emoji_dictionary:{},
});
const FORMAT_BOOL_LABELS=[
  ["read_comments","อ่านข้อความแชท"],
];
function sourcePrefix(mode){
  return mode==="discord_client"?"discordClient":
    mode==="youtube_browser"?"youtubeBrowser":
    mode==="tiktok_browser"?"tiktokBrowser":mode;
}
const TUNING=[
  ["speed","ความเร็วในการอ่าน",0.60,5.00,1,"×"],
  ["gain_db","ความดัง",-18,12,0,"dB"],
  ["pitch_semitones","ระดับเสียง",-4,4,0,"st"],
  ["bass_db","เสียงทุ้ม",-12,12,0,"dB"],
  ["treble_db","เสียงแหลม",-12,12,0,"dB"],
];
function attach({document,engines,getDefault}){
  const controls=new Map();
  const speechControls=new Map();
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
  // One independent speech composition panel for every source. Controls
  // are sampled at speech-queue time, so neither current audio nor chat
  // history is rewritten. The plain text is persisted in portable settings.
  for(const mode of SENDER_MODES){
    const view=document.querySelector('[data-mode-view="'+mode+'"]');
    if(!view)continue;
    const prefix=sourcePrefix(mode);
    const panel=create("details");
    panel.className="source-format-settings";
    panel.style.margin="12px 0";
    panel.style.padding="12px";
    panel.style.border="1px solid #40516d";
    panel.style.borderRadius="10px";
    panel.appendChild(create("summary","กำหนดการอ่านข้อความและข้อมูลพิเศษ"));
    const help=create("p","เลือกประเภทข้อมูลและคำเชื่อมสำหรับโหมดนี้โดยเฉพาะ · ค่าใหม่ใช้กับข้อความที่สร้างเสียงครั้งถัดไป");
    help.className="small";panel.appendChild(help);
    // Move the original live controls rather than cloning them. Existing
    // listeners, checkbox values and mode-ownership behavior are preserved.
    for(const suffix of ["FeedAuto","FeedReadSender"]){
      const control=document.getElementById?.(prefix+suffix);
      const label=control?.closest?.("label")||control?.parentElement;
      if(label){
        const holder=create("div");holder.style.margin="6px 0";
        holder.appendChild(label);
        panel.appendChild(holder);
      }
      if(suffix==="FeedReadSender"){
        const status=document.getElementById?.(prefix+"FeedReadSenderStatus");
        if(status)panel.appendChild(status);
      }
    }
    const fields={};
    const addPhrase=(field,label,description)=>{
      const holder=create("div");
      const caption=create("label",label);
      const input=create("input");input.type="text";
      const suffix={sender_prefix:"SenderPrefix",separator:"Separator"}[field];
      input.id=prefix+"Feed"+suffix;
      input.maxLength=60;input.value=DEFAULT_FORMAT[field];
      const desc=create("small",description);desc.className="small";
      holder.append(caption,input,desc);
      panel.appendChild(holder);fields[field]=input;
    };
    addPhrase("sender_prefix","คำนำหน้าชื่อผู้ส่ง เช่น คุณ",
      "ใส่คำว่า คุณ หรือคำอื่นได้ · เว้นว่างเพื่ออ่านเฉพาะชื่อ · ไม่เปลี่ยน @ ในข้อความแชท");
    addPhrase("separator","คำเชื่อมหลังชื่อผู้ส่งก่อนข้อความ เช่น พิมพ์ว่า",
      "เว้นว่างเพื่อให้อ่านชื่อแล้วตามด้วยข้อความโดยไม่มีคำเชื่อม");
    for(const [field,label] of FORMAT_BOOL_LABELS){
      const holder=create("label");holder.style.display="flex";
      holder.style.gap="8px";holder.style.alignItems="center";
      const box=create("input");box.type="checkbox";
      box.id=prefix+"FeedFormat"+field;
      box.checked=DEFAULT_FORMAT[field];
      holder.append(box,create("span",label));panel.appendChild(holder);
      fields[field]=box;
    }
    if(mode==="live"||mode==="youtube_browser"){
      const holder=create("label");holder.style.display="flex";
      holder.style.gap="8px";holder.style.alignItems="center";
      const box=create("input");box.type="checkbox";
      box.id=prefix+"FeedFormatread_name_at";
      box.checked=DEFAULT_FORMAT.read_name_at;
      holder.append(box,create("span",
        "อ่าน @ ที่นำหน้าชื่อผู้ส่ง (ไม่เกี่ยวกับ @ ในข้อความคอมเมนต์)"));
      panel.appendChild(holder);
      const note=create("small",
        "ถ้าเคยตั้งกฎแทน @ → คุณ ในแท็บกฎข้อความ ให้ปิดกฎเดิมนั้นด้วย เพราะกฎส่วนกลางยังมีผลกับเนื้อหาคอมเมนต์");
      note.className="small";panel.appendChild(note);
      fields.read_name_at=box;
    }
    // Unicode and Discord emoji dictionary is editable only in YouTube
    // (API/Browser) and Discord (Bot/Client), independently per source.
    const emojiEnabled=["live","youtube_browser","discord","discord_client"].includes(mode);
    let emojiEditor=null;
    if(emojiEnabled){
      const holder=create("div");holder.style.marginTop="12px";
      const label=create("label");label.style.display="flex";
      label.style.alignItems="center";label.style.gap="8px";
      const toggle=create("input");toggle.type="checkbox";
      toggle.id=prefix+"FeedFormatread_emojis";
      toggle.checked=false;
      label.append(toggle,create("span","อ่านอีโมจิด้วยคำที่กำหนดเอง"));
      holder.appendChild(label);
      const caption=create("label","พจนานุกรมคำอ่านอีโมจิ (บรรทัดละหนึ่งรายการ)");
      emojiEditor=create("textarea");
      emojiEditor.id=prefix+"FeedEmojiMappings";
      emojiEditor.rows=5;emojiEditor.maxLength=8192;
      emojiEditor.placeholder="😂 = หัวเราะ\n❤️ = หัวใจ\nGGWP = เก่งมาก\n:party_parrot: = นกเต้น";
      const note=create("small",
        "ใส่ อีโมจิหรือชื่ออีโมจิ = คำอ่าน · สูงสุด 64 รายการ · เช่น 😂, GGWP, :party_parrot: · คำที่ไม่ได้ตั้งค่าจะคงเดิม");
      note.className="small";
      holder.append(caption,emojiEditor,note);
      panel.appendChild(holder);
      fields.read_emojis=toggle;
    }
    const preview=create("p");
    preview.className="small";preview.style.marginTop="8px";
    const refreshPreview=()=>{
      const options={...DEFAULT_FORMAT};
      for(const [field,input] of Object.entries(fields))
        options[field]=["sender_prefix","separator"].includes(field)
          ?String(input.value??"").trim():Boolean(input.checked);
      const withName=document.getElementById?.(prefix+"FeedReadSender")?.checked;
      const displayName=(mode==="live"||mode==="youtube_browser")
        ?(options.read_name_at?"@ผู้ชมตัวอย่าง":"ผู้ชมตัวอย่าง"):"ผู้ชมตัวอย่าง";
      const front=withName
        ?[options.sender_prefix,displayName].filter(Boolean).join(" "):"";
      const comment=options.read_comments
        ?[front,front?options.separator:"","สวัสดีครับ"].filter(Boolean).join(" ")
        :"(ปิดการอ่านคอมเมนต์)";
      let shown=comment;
      if(emojiEditor&&options.read_emojis){
        try{
          const dictionary=Emoji.parseEditor(emojiEditor.value);
          shown=Emoji.replace(shown+" 😂❤️ GGWP",dictionary);
        }catch(error){
          preview.textContent="พจนานุกรมอีโมจิ: "+error.message;
          return;
        }
      }
      preview.textContent="ตัวอย่างแชท: "+shown;
    };
    for(const input of Object.values(fields)){
      input.addEventListener("input",refreshPreview);
      input.addEventListener("change",refreshPreview);
    }
    emojiEditor?.addEventListener("input",refreshPreview);
    document.getElementById?.(prefix+"FeedReadSender")
      ?.addEventListener("change",refreshPreview);
    const button=create("button","บันทึกรูปแบบการอ่าน");
    button.type="button";
    const state=create("span","ค่าเริ่มต้น: อ่านเฉพาะคอมเมนต์");
    state.className="small";state.style.marginLeft="8px";
    panel.append(preview,button,state);
    speechControls.set(mode,{fields,button,state,refreshPreview,emojiEditor});
    view.insertBefore(panel,view.firstChild);
    refreshPreview();
  }
  function readSpeechFormat(mode){
    const ui=speechControls.get(mode);
    const fields=ui?.fields;
    const config={...DEFAULT_FORMAT,emoji_dictionary:{}};
    if(!fields)return config;
    for(const [key,input] of Object.entries(fields)){
      config[key]=["sender_prefix","separator"].includes(key)
        ?String(input.value??"").trim():Boolean(input.checked);
    }
    if(ui.emojiEditor)
      config.emoji_dictionary=root.VoxEmojiPronunciation.parseEditor(ui.emojiEditor.value);
    return config;
  }
  async function saveSpeechFormat(mode){
    const ui=speechControls.get(mode);
    if(!ui)return;
    let format;
    try{format=readSpeechFormat(mode);}
    catch(error){ui.state.textContent=String(error.message||error);return;}
    if(["sender_prefix","separator"].some(key=>
      format[key].length>60||/[\u0000-\u001f\u007f]/.test(format[key]))){
      ui.state.textContent="คำเชื่อมไม่ถูกต้อง (สูงสุด 60 ตัวอักษร)";
      return;
    }
    ui.button.disabled=true;ui.state.textContent="กำลังบันทึก...";
    try{
      await (serial=serial.catch(()=>{}).then(async()=>{
        const response=await fetch("/v1/settings/mode-voices",{
          method:"POST",
          headers:{"Content-Type":"application/json",
                   "X-VoxWeaveTTS-Intent":"save-mode-voice"},
          body:JSON.stringify({expected_revision:revision,mode:"__speech_format__",
            settings:{source_mode:mode,format}}),
        });
        const data=await response.json();
        if(!response.ok)throw Error(data.error||"ไม่สามารถบันทึกรูปแบบการอ่าน");
        revision=data.revision;
      }));
      ui.state.textContent="บันทึกแล้ว · ใช้กับข้อความใหม่";
    }catch(error){ui.state.textContent=String(error.message||error);}
    finally{ui.button.disabled=false;}
  }
  for(const [mode,ui] of speechControls){
    ui.button.addEventListener("click",()=>saveSpeechFormat(mode));
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
      const prefix=sourcePrefix(mode);
      const checkbox=document.getElementById?.(prefix+"FeedReadSender");
      if(checkbox)checkbox.checked=data.sender_names?.[mode]===true;
      const ui=speechControls.get(mode);
      if(ui){
        const settings={...DEFAULT_FORMAT,...(data.speech_formats?.[mode]||{})};
        for(const [field,input] of Object.entries(ui.fields)){
          if(["sender_prefix","separator"].includes(field))
            input.value=settings[field];
          else input.checked=Boolean(settings[field]);
        }
        if(ui.emojiEditor)
          ui.emojiEditor.value=Emoji.formatEditor(
            settings.emoji_dictionary||{});
        ui.refreshPreview();
      }
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
    const prefix=sourcePrefix(mode);
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
  return {load,read,save,savePolicy,saveSenderName,saveSpeechFormat,readSpeechFormat,
          loadPresets,refreshEngines,
          settingsFor:mode=>read(mode),
          get modes(){return [...controls.keys()];}};
}
root.VoxModeVoiceSettings={attach};
if(typeof module!=="undefined"&&module.exports)module.exports={attach,VOICE_MODES};
})(typeof window==="undefined"?globalThis:window);
