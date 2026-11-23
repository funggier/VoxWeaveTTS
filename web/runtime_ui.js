/* Browser is the control surface. Core owns Live TTS and Windows audio. */
(function(root){
"use strict";

const el=id=>document.getElementById(id);
const select=el("runtimeExecutionMode");
if(!select)return;
const status=el("runtimeControlStatus");
const sources=el("runtimeSourcesStatus");
const stop=el("runtimeStopComputer");
const resume=el("runtimeResumeComputer");
const replay=el("runtimeReplayComputer");
const output=el("runtimeAudioOutput");
const sampleRate=el("runtimeAudioSampleRate");
const channels=el("runtimeAudioChannels");
const bufferMs=el("runtimeAudioBufferMs");
const saveAudio=el("runtimeAudioSave");
const audioStatus=el("runtimeAudioStatus");
const listenLink=el("runtimeListenLink");
const listenHint=el("runtimeListenHint");
let current="computer"; // Core-first until the authoritative Server state arrives
let busy=false;
let refreshing=false;
const allAudios=()=>document.querySelectorAll("audio");
root.VoxOutputMode={current};

async function api(path,body,intent){
  const response=await fetch(path,{
    method:"POST",
    headers:{"Content-Type":"application/json","X-VoxWeaveTTS-Intent":intent},
    body:JSON.stringify(body),cache:"no-store"
  });
  const result=await response.json();
  if(!response.ok)throw Error(result.error||"Runtime API request failed");
  return result;
}
function number(value){
  return Number(value||0).toLocaleString("th-TH");
}
function apply(data){
  if(!data||!["browser","computer"].includes(data.mode))return;
  const changed=current!==data.mode;
  current=data.mode;
  root.VoxOutputMode.current=current;
  root.VoxLastRuntimeSnapshot=data;
  root.VoxCoreDashboard?.onRuntimeState(data);
  const version=el("appVersion");
  if(version&&data.version)version.textContent="VoxWeaveTTS v"+data.version;
  const global=el("runtimeGlobalStatus");
  if(global){
    const c=data.job_states||{};
    const waiting=Number(c.preparing||0)+Number(c.prepared||0);
    global.textContent=current==="computer"
      ?"Core: ทำงานบนคอม · "+
        (data.playback_paused?"พักคิวตามคำสั่งหยุด"
          :data.audio_state==="playing"
          ?"กำลังอ่าน "+(data.active_workspace||"งานเสียง")
          :"รอรายการ")+
        " · แปล/เตรียม "+waiting+
        " · สร้างเสียง "+Number(c.rendering||0)+
        " · รอเล่น "+Number(c.ready||0)
      :"Browser: การสร้าง/เล่นเสียงอยู่ในแท็บที่เปิด · "+
        "ประวัติงานที่เก็บเฉพาะ Browser อาจหายเมื่อรีเฟรช";
  }
  if(changed&&current==="computer"){
    for(const item of allAudios())item.pause();
  }
  if(document.activeElement!==select)select.value=current;
  const devices=Array.isArray(data.available_outputs)?data.available_outputs:[];
  if(devices.length&&(
    output.options.length!==devices.length||
    [...output.options].some((item,index)=>item.value!==devices[index].id)
  )){
    output.replaceChildren(...devices.map(device=>{
      const item=document.createElement("option");
      const native=device.native_rate?" ("+number(device.native_rate)+" Hz)":"";
      item.value=device.id;
      item.textContent=device.label+native;
      return item;
    }));
  }
  if(document.activeElement!==output)output.value=data.output||"default";
  output.disabled=current!=="computer";
  const audio=data.audio_settings||{};
  for(const [control,value] of [
    [sampleRate,audio.sample_rate],[channels,audio.channels],[bufferMs,audio.buffer_ms]
  ]){
    if(control&&value!==undefined&&document.activeElement!==control)
      control.value=String(value);
  }
  if(audioStatus){
    const requestedRate=audio.sample_rate==="auto"?"Auto":number(audio.sample_rate)+" Hz";
    const requestedChannels=audio.channels==="auto"?"Auto":String(audio.channels);
    const wanted="ตั้งค่า Output: "+requestedRate+" / "+requestedChannels+
      " ช่อง / Buffer "+number(audio.buffer_ms)+" ms";
    const f=data.actual_audio_format;
    audioStatus.textContent=f
      ?wanted+" · เสียงที่เล่นล่าสุด: WAV "+number(f.source_rate)+" Hz → อุปกรณ์ "+
        number(f.sample_rate)+" Hz / "+f.channels+" ช่อง"+
        (f.resampled?" (Resample เพื่อรักษาความเร็วเสียง)":" (ไม่ต้อง Resample)")
      :wanted+" · ยังไม่มีเสียงที่เล่นด้วยค่านี้ (มีผลกับงานเสียงถัดไป)";
  }
  if(data.listen_url){
    listenLink.href=data.listen_url;
    listenLink.hidden=false;
    listenHint.textContent=data.output==="live"
      ?"กำลังส่งเสียงไปยัง Browser · ผู้ฟัง "+number(data.listeners)+" ราย"
      :"เปลี่ยนปลายทางเสียงเป็น Live Broadcast เพื่อใช้การฟังบนโทรศัพท์";
  }else{
    listenLink.hidden=true;
    listenHint.textContent="บริการ Live Listener ยังไม่พร้อม: "+(data.listen_error||"unknown");
  }
  const counts=data.job_states||{};
  const processing=(counts.preparing||0)+(counts.prepared||0);
  const synthesis=(counts.queued||0)+(counts.rendering||0);
  const waiting=(counts.ready||0);
  const cap=number(data.max_outstanding_jobs||0);
  status.textContent=
    (current==="computer"?"Core ประมวลผลเสียงในเครื่อง":"Browser รับผิดชอบการเล่นเสียง")+
    " · "+(data.worker_running?"Worker ทำงาน":"Worker หยุด")+
    " · "+(data.playback_paused?"หยุดเสียงแล้ว · พักคิวจนกดอ่านอัตโนมัติต่อ"
      :data.audio_state==="playing"?"กำลังเล่นเสียง":"ยังไม่ได้เล่นเสียง")+
    " · เตรียม/แปล "+number(processing)+
    " · สร้างเสียง "+number(synthesis)+
    " · พร้อมเล่น "+number(waiting)+
    " · ขีดจำกัด "+cap+
    " · แชทรอดึง "+number(data.pending_source_messages)+
    " · อ่านจบ "+number(data.completed)+
    " · ผิดพลาด "+number(data.failed)+
    (data.last_error?" · ข้อผิดพลาดล่าสุด: "+data.last_error:"");
  const labels={
    live:"YouTube API",youtube_browser:"YouTube Browser",
    tiktok_browser:"TikTok Extension",discord:"Discord",
    discord_client:"Discord Client",tiktok:"TikFinity Core",
    stt_api:"VoxWeaveSTT (API)"
  };
  sources.textContent="แหล่งข้อความ: "+Object.entries(data.sources||{}).map(
    ([key,value])=>(labels[key]||key)+" "+(value.state||"idle")+
      " (รอ "+number(value.pending)+" ข้อความ)"
  ).join(" · ");
  // Surface private-dashboard failures after public status updates; do not
  // silently erase the useful error on every 1.5s status refresh.
  const dashboardError=root.VoxCoreDashboard?.getLastError?.();
  if(current==="computer"&&dashboardError)
    sources.textContent+=" · รายละเอียดคิว Core ไม่พร้อม: "+String(dashboardError).slice(0,180);
  stop.disabled=current!=="computer"||Boolean(data.playback_paused);
  if(resume)resume.disabled=current!=="computer"||!data.playback_paused;
  replay.disabled=current!=="computer"||Boolean(data.playback_paused)||!data.last_completed_speech_id;
}
async function refresh(){
  if(busy||refreshing)return;
  refreshing=true;
  try{
    const response=await fetch("/v1/runtime/state",{cache:"no-store"});
    if(!response.ok)throw Error("HTTP "+response.status);
    apply(await response.json());
  }catch(error){
    status.textContent="อ่านสถานะ Core ไม่สำเร็จ: "+String(error.message||error);
    root.VoxCoreDashboard?.onRuntimeError(error);
    const global=el("runtimeGlobalStatus");
    if(global)global.textContent="Core: ติดต่อ Server ไม่สำเร็จ · ข้อมูลอาจไม่เป็นปัจจุบัน";
  }finally{refreshing=false;}
}
async function setValue(action,body,intent,errorLabel){
  busy=true;
  try{
    apply(await api(action,body,intent));
    return true;
  }catch(error){
    status.textContent=errorLabel+": "+String(error.message||error);
    return false;
  }finally{
    busy=false;
  }
}
select.addEventListener("change",async()=>{
  select.disabled=true;
  const success=await setValue("/v1/runtime/mode",
    {mode:select.value},"set-runtime-mode","เปลี่ยนโหมดไม่สำเร็จ");
  if(!success)select.value=current;
  select.disabled=false;
  await refresh();
});
output.addEventListener("change",async()=>{
  output.disabled=true;
  const requested=output.value;
  const ok=await setValue("/v1/runtime/output",
    {output:requested},"set-runtime-output","เปลี่ยนอุปกรณ์เสียงไม่สำเร็จ");
  if(!ok){
    output.value=root.VoxLastRuntimeSnapshot?.output||"default";
    if(audioStatus)audioStatus.textContent="ไม่สามารถเปลี่ยนอุปกรณ์เสียงได้ · กลับไปใช้อุปกรณ์ที่ Core ยืนยันแล้ว";
  }
  output.disabled=current!=="computer";
  if(ok)await refresh();
});
saveAudio?.addEventListener("click",async()=>{
  saveAudio.disabled=true;
  const options={
    sample_rate:sampleRate.value==="auto"?"auto":Number(sampleRate.value),
    channels:channels.value==="auto"?"auto":Number(channels.value),
    buffer_ms:Number(bufferMs.value),
  };
  const ok=await setValue("/v1/runtime/audio",options,
    "set-runtime-audio","ตั้งค่ารูปแบบเสียงไม่สำเร็จ");
  if(!ok&&audioStatus)audioStatus.textContent="บันทึกไม่สำเร็จ · ตรวจข้อความผิดพลาดด้านบน";
  saveAudio.disabled=false;
  if(ok)await refresh();
});
replay.addEventListener("click",async()=>{
  await setValue("/v1/runtime/replay",{},"replay-computer-audio","เล่นซ้ำไม่สำเร็จ");
  await refresh();
});
stop.addEventListener("click",async()=>{
  await setValue("/v1/runtime/playback",{action:"stop"},
    "control-computer-playback","หยุดเสียงไม่สำเร็จ");
});
resume?.addEventListener("click",async()=>{
  await setValue("/v1/runtime/playback",{action:"resume"},
    "control-computer-playback","อ่านต่อไม่สำเร็จ");
});
document.addEventListener("play",event=>{
  if(current==="computer"&&event.target?.tagName==="AUDIO")
    event.target.pause();
},true);
document.addEventListener("visibilitychange",()=>{
  if(!document.hidden)refresh();
});
root.addEventListener?.("focus",refresh);
refresh();
root.setInterval(refresh,1500);

/* Three distinct connections: browser control, listen-only browser and
 * optional separate Desktop Remote Client API. Never suggest the Remote
 * Client port is required for controlling the Server from a browser.
 */
const node=id=>document.getElementById(id);
const webStatus=node("networkWebState");
const webBind=node("networkWebBind");
const webUsername=node("networkWebUsername");
const webLink=node("networkBrowserUrl");
const webNotice=node("networkBrowserNotice");
const webCopy=node("networkCopyBrowserUrl");
const listenerState=node("networkListenerState");
const remoteState=node("networkRemoteState");
const listenerSaveStatus=node("networkListenerSaveStatus");
const remoteSaveStatus=node("networkStatus");

let lastBrowserUrl="";
function displayOverview(payload){
  const web=payload?.web||{};
  const listener=payload?.listener||{};
  const remote=payload?.remote||{};
  if(web.port&&web.bind_host){
    webBind.textContent=web.bind_host+":"+web.port;
    webUsername.textContent=web.username||"voxweave";
    const local=web.bind_mode==="loopback_only";
    webStatus.textContent=local
      ?"เฉพาะเครื่อง Server — ยังไม่เปิดรับ Browser จาก LAN"
      :web.bind_mode==="all_ipv4"
        ?"เปิดรับบนทุก IPv4 (0.0.0.0)"
        :"เปิดรับบน IPv4 ที่เลือก";
    const suggested=String(web.url||"");
    const hasLanAddress=!local && suggested &&
      !/^http:\/\/127\./.test(suggested);
    lastBrowserUrl=hasLanAddress?suggested:"";
    webLink.hidden=!hasLanAddress;
    webCopy.disabled=!hasLanAddress;
    if(hasLanAddress){
      webLink.href=suggested;
      webLink.textContent=suggested;
    }
    webNotice.textContent=local
      ?"หากต้องการควบคุมผ่าน LAN ให้เปิด VoxWeaveTTS.exe บน Server แล้วเลือก LAN หรือ All IPv4 กำหนด IP/Port และกด Apply & Restart"
      :!hasLanAddress
        ?"Server เปิดรับ IPv4 แล้ว แต่ตรวจ IP ของ LAN ไม่ได้ โปรดดู ipconfig บนเครื่อง Server และเปิด http://<IP ของ Server>:"+web.port+"/ จากอุปกรณ์อื่น"
      :web.url_is_estimate
        ?"URL ด้านบนเป็น IP ที่ระบบประมาณจากเครือข่ายของ Server โปรดตรวจ IP จริงด้วย ipconfig และอนุญาตพอร์ตนี้ใน Windows Firewall"
        :"เปิด URL ด้านบนจากเครื่องอื่นใน LAN แล้วเข้าสู่ระบบด้วย Username และ Password ที่ตั้งใน Launcher (ตรวจ Firewall หากเข้าไม่ได้)";
  }
  listenerState.textContent=listener.running
    ?"Live Audio Listener: เปิดรับที่ "+listener.bind_host+":"+listener.port+
      " (ใช้ลิงก์พร้อมโทเคนด้านบน ไม่ใช่ URL ของ Web Control)"
    :listener.error
      ?"Live Audio Listener เริ่มไม่ได้: "+listener.error
      :"Live Audio Listener: ยังไม่เปิดบริการ";
  remoteState.textContent=remote.enabled
    ?"Remote Desktop Client API: เปิดรับที่ "+remote.bind_host+":"+remote.port+
      " (ไม่ใช่พอร์ตสำหรับเปิด Browser)"
    :remote.error
      ?"Remote Desktop Client API เริ่มไม่ได้: "+remote.error
      :"Remote Desktop Client API: ปิดอยู่ — ไม่กระทบการควบคุมผ่าน Browser";
}
async function readOverview(){
  try{
    const response=await fetch("/v1/network/overview",{cache:"no-store"});
    const data=await response.json();
    if(!response.ok)throw Error(data.error||"HTTP "+response.status);
    displayOverview(data);
  }catch(error){
    webStatus.textContent="ตรวจสถานะการเชื่อมต่อไม่สำเร็จ: "+String(error.message||error);
  }
}
webCopy?.addEventListener("click",async()=>{
  if(!lastBrowserUrl)return;
  try{
    await navigator.clipboard.writeText(lastBrowserUrl);
    webNotice.textContent="คัดลอก URL สำหรับเปิด Browser จากเครื่องอื่นแล้ว: "+lastBrowserUrl;
  }catch{
    webNotice.textContent="คัดลอกอัตโนมัติไม่ได้ กรุณาเลือกข้อความ URL แล้วกด Ctrl+C";
  }
});
const networkFields=[
  ["ListenerHost","listener_host"],["ListenerPort","listener_port"],
  ["RemoteEnabled","remote_enabled"],["ControlHost","control_host"],
  ["ControlPort","control_port"],["Username","username"]
];
function displayNetwork(data){
  for(const [id,key] of networkFields){
    const input=node("network"+id);
    if(!input)continue;
    if(input.type==="checkbox")input.checked=Boolean(data[key]);
    else input.value=data[key]??"";
  }
  remoteSaveStatus.textContent=data.password_configured
    ?"รหัส Remote Client ตั้งค่าแล้ว (เก็บเป็นแฮชบน Server)"
    :"ยังไม่ได้ตั้งรหัส Remote Client — หากจะเปิด Remote API ต้องตั้งรหัสขั้นต่ำ 4 ตัวอักษร";
  listenerSaveStatus.textContent="กำลังแสดงค่าที่บันทึกไว้ หากเพิ่งเปลี่ยนต้องเริ่ม Core ใหม่";
}
async function readNetwork(){
  try{
    const response=await fetch("/v1/network/settings",{cache:"no-store"});
    const data=await response.json();
    if(!response.ok){
      if(response.status===403){
        throw Error("การแก้ค่า Live Listener และ Remote Client ต้องเปิดหน้าเว็บบนเครื่อง Server");
      }
      throw Error(data.error||"HTTP "+response.status);
    }
    displayNetwork(data);
  }catch(error){
    remoteSaveStatus.textContent=String(error.message||error);
    listenerSaveStatus.textContent=String(error.message||error);
    node("networkSave").disabled=true;
    node("networkListenerSave").disabled=true;
  }
}
async function savePartial(body,button,feedback){
  button.disabled=true;
  try{
    await api("/v1/network/settings",body,"save-network-settings");
    await readNetwork();
    feedback.textContent="บันทึกแล้ว — ต้องเริ่ม Core ใหม่จึงจะใช้ IP/Port หรือบัญชีใหม่ได้";
  }catch(error){
    feedback.textContent="บันทึกไม่สำเร็จ: "+String(error.message||error);
  }finally{
    button.disabled=false;
  }
}
node("networkListenerSave")?.addEventListener("click",async()=>{
  await savePartial({
    listener_host:node("networkListenerHost").value.trim(),
    listener_port:Number(node("networkListenerPort").value)
  },node("networkListenerSave"),listenerSaveStatus);
});
node("networkSave")?.addEventListener("click",async()=>{
  const payload={
    remote_enabled:node("networkRemoteEnabled").checked,
    control_host:node("networkControlHost").value.trim(),
    control_port:Number(node("networkControlPort").value),
    username:node("networkUsername").value.trim(),
  };
  const password=node("networkPassword");
  if(password.value)payload.password=password.value;
  await savePartial(payload,node("networkSave"),remoteSaveStatus);
  password.value="";
});
readOverview();
readNetwork();
root.setInterval(readOverview,10000);
})(window);