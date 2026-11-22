/* Both the browser and any desktop client control one server-owned runtime.
 * The choice is intentionally exposed only on the Settings page. */
(function(root){
"use strict";
let current="browser", lastRevision=-1, busy=false;
const select=document.getElementById("runtimeExecutionMode");
const status=document.getElementById("runtimeControlStatus");
const sources=document.getElementById("runtimeSourcesStatus");
const stop=document.getElementById("runtimeStopComputer");
const replay=document.getElementById("runtimeReplayComputer");
const output=document.getElementById("runtimeAudioOutput");
const listenLink=document.getElementById("runtimeListenLink");
const listenHint=document.getElementById("runtimeListenHint");
const allAudios=()=>document.querySelectorAll("audio");
const api=async(path,body,intent)=>{
  const response=await fetch(path,{
    method:"POST",headers:{"Content-Type":"application/json",
                          "X-VoxWeaveTTS-Intent":intent},
    body:JSON.stringify(body),cache:"no-store"
  });
  const result=await response.json();
  if(!response.ok)throw Error(result.error||"Runtime API failed");
  return result;
};
function apply(data){
  if(!data||!["browser","computer"].includes(data.mode))return;
  const changed=current!==data.mode;
  current=data.mode;
  root.VoxOutputMode.current=current;
  if(changed && current==="computer"){
    for(const audio of allAudios())audio.pause();
  }
  if(document.activeElement!==select)select.value=current;
  const outputDevices=Array.isArray(data.available_outputs)?data.available_outputs:[];
  if(outputDevices.length && (output.options.length!==outputDevices.length ||
       [...output.options].some((entry,i)=>entry.value!==outputDevices[i].id))){
    output.replaceChildren(...outputDevices.map(device=>{
      const item=document.createElement("option");
      item.value=device.id;item.textContent=device.label;return item;
    }));
  }
  if(document.activeElement!==output)output.value=data.output||"default";
  output.disabled=current!=="computer";
  if(data.listen_url){
    listenLink.href=data.listen_url;
    listenLink.hidden=false;
    listenHint.textContent=data.output==="live"
      ?"· เลือกเปิดรับฟังเสียงสดในโทรศัพท์ · เชื่อมต่อ "+(data.listeners||0)+" เครื่อง"
      :"· เปลี่ยนปลายทางเสียงเป็นถ่ายทอดสดเพื่อฟังในโทรศัพท์";
  }else{
    listenLink.hidden=true;
    listenHint.textContent="· ตัวรับฟัง LAN ไม่พร้อม ("+(data.listen_error||"unknown")+")";
  }
  if(lastRevision!==data.revision || changed){
    lastRevision=data.revision;
  }
  status.textContent=(current==="computer"
    ?"ทำงานบนคอมพิวเตอร์ · ปิดหน้าเว็บได้"
    :"ทำงานผ่านเว็บแบบเดิม · การเล่นเสียงขึ้นกับหน้าเว็บ")+
    " · "+(data.worker_running?"API และ Worker พร้อม":"Worker ไม่ทำงาน")+
    " · "+(data.audio_state==="playing"?"กำลังเล่นเสียง":"ไม่มีเสียงกำลังเล่น")+
    " · รอรับข้อความ "+(data.pending_source_messages||0)+
    " · อ่านจบ "+(data.completed||0)+
    " · ผิดพลาด "+(data.failed||0)+
    (data.last_error?" · "+data.last_error:"");
  const names={live:"YouTube API",youtube_browser:"YouTube Browser",
    tiktok_browser:"TikTok Extension",discord:"Discord",
    discord_client:"Discord Client"};
  sources.textContent="ต้นทาง: "+Object.entries(data.sources||{}).map(([key,value])=>
    (names[key]||key)+" "+(value.state||"idle")+" ("+(value.pending||0)+" รอรับ)"
  ).join(" · ");
  stop.disabled=current!=="computer";
  replay.disabled=current!=="computer" || !data.last_completed_speech_id;
}
async function refresh(){
  if(busy)return;
  try{
    const res=await fetch("/v1/runtime/state",{cache:"no-store"});
    if(!res.ok)throw Error("Cannot read computer runtime state");
    apply(await res.json());
  }catch(error){
    status.textContent="เชื่อมต่อ Runtime API ไม่สำเร็จ: "+String(error.message||error);
  }
}
select.addEventListener("change",async()=>{
  busy=true;select.disabled=true;
  try{
    apply(await api("/v1/runtime/mode",{mode:select.value},"set-runtime-mode"));
  }catch(error){
    status.textContent="เปลี่ยนรูปแบบการทำงานไม่สำเร็จ: "+String(error.message||error);
    select.value=current;
  }finally{busy=false;select.disabled=false;}
});
output.addEventListener("change",async()=>{
  busy=true;output.disabled=true;
  try{
    apply(await api("/v1/runtime/output",{output:output.value},"set-runtime-output"));
    await refresh();
  }catch(error){status.textContent="เลือกปลายทางไม่สำเร็จ: "+String(error.message||error);}
  finally{busy=false;output.disabled=current!=="computer";}
});
replay.addEventListener("click",async()=>{
  try{
    await api("/v1/runtime/replay",{},"replay-computer-audio");
    await refresh();
  }catch(error){status.textContent="เล่นซ้ำไม่สำเร็จ: "+String(error.message||error);}
});
stop.addEventListener("click",async()=>{
  try{apply(await api("/v1/runtime/playback",{action:"stop"},"control-computer-playback"));}
  catch(error){status.textContent=String(error.message||error);}
});
document.addEventListener("play",event=>{
  if(current==="computer"&&event.target?.tagName==="AUDIO")
    event.target.pause();
},true);
root.VoxOutputMode={current};
refresh();
root.setInterval(refresh,1500);
const networkIds=["ApiPort","ListenerHost","ListenerPort","RemoteEnabled","ControlHost",
                  "ControlPort","Username"];
const networkKeys=["api_port","listener_host","listener_port","remote_enabled",
                   "control_host","control_port","username"];
const networkStatus=document.getElementById("networkStatus");
function useNetwork(data){
  for(let i=0;i<networkIds.length;i++){
    const node=document.getElementById("network"+networkIds[i]);
    if(!node)continue;
    if(node.type==="checkbox")node.checked=Boolean(data[networkKeys[i]]);
    else node.value=data[networkKeys[i]]??"";
  }
  if(data.password_configured)
    networkStatus.textContent="ตั้งรหัสผ่านแล้ว · พร้อมเปิด LAN Control เมื่อเริ่ม Core ใหม่";
  else
    networkStatus.textContent="ยังไม่ตั้งรหัสผ่าน · กรุณาตั้งรหัสอย่างน้อย 4 ตัวอักษรก่อนเปิด LAN Control";
}
async function readNetwork(){
  try{
    const res=await fetch("/v1/network/settings",{cache:"no-store"});
    const data=await res.json();
    if(!res.ok)throw Error(data.error||"Unable to read network settings");
    useNetwork(data);
  }catch(err){networkStatus.textContent="อ่านการตั้งค่า LAN ไม่สำเร็จ: "+err.message;}
}
document.getElementById("networkSave").addEventListener("click",async()=>{
  const button=document.getElementById("networkSave");
  const payload={};
  for(let i=0;i<networkIds.length;i++){
    const node=document.getElementById("network"+networkIds[i]);
    payload[networkKeys[i]]=node.type==="checkbox"?node.checked:
      node.type==="number"?Number(node.value):node.value.trim();
  }
  const password=document.getElementById("networkPassword");
  if(password.value)payload.password=password.value;
  button.disabled=true;
  try{
    await api("/v1/network/settings",payload,"save-network-settings");
    password.value="";
    networkStatus.textContent="บันทึกแล้ว · กรุณาปิดและเริ่ม Core ใหม่เพื่อให้ IP / Port / Username / Password มีผล";
  }catch(err){networkStatus.textContent="บันทึกไม่สำเร็จ: "+err.message;}
  finally{button.disabled=false;}
});
readNetwork();
})(window);
