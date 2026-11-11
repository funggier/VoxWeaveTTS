/* Engine-neutral workspace modes. One local owner may report audio to the
 * single OBS overlay. Tabs have separate draft text, queue and playback UI;
 * engine/voice/rules/DSP are shared, not copied per mode.
 */
(function(root){
"use strict";
const MODES = Object.freeze([
  {id:"studio",label:"สร้างเสียง"},
  {id:"reader",label:"อ่านเอกสาร"},
  {id:"live",label:"อ่านไลฟ์สด"},
  {id:"discord",label:"Discord"},
  {id:"discord_client",label:"Discord Client"},
  {id:"queue",label:"คิวและ Subtitle"},
  {id:"rules",label:"คำอ่านและกฎ"},
  {id:"settings",label:"ตั้งค่ากลาง"},
]);
function attach({document, stopLocal, onActive, onError, pollMs=1200}){
  if(!document || typeof stopLocal!=="function")throw Error("Mode workspace callbacks required");
  const valid=new Set(MODES.map(x=>x.id));
  const get=id=>document.getElementById(id);
  let active="studio", token=null, revision=0, serial=Promise.resolve(), sequence=0;
  let channel=null, monitor=null, modeStream=null;
  const broadcastName="VoxWeaveTTS-workspace-owner-v1";
  const reportError=(error)=>{
    const info=String(error?.message||error);
    if(get("modeOwnerStatus"))get("modeOwnerStatus").textContent=info;
    onError?.(info);
  };
  function render(){
    for(const view of document.querySelectorAll("[data-mode-view]")){
      const yes=view.getAttribute("data-mode-view")===active;
      view.hidden=!yes;
    }
    for(const button of document.querySelectorAll("[data-mode-target]")){
      const yes=button.getAttribute("data-mode-target")===active;
      button.setAttribute("aria-pressed",yes?"true":"false");
    }
    get("modeTitle").textContent=MODES.find(x=>x.id===active)?.label||active;
    get("modeOwnerStatus").textContent=token
      ? "โหมดนี้ควบคุมเสียงและ OBS อยู่"
      : "ยังไม่ได้สิทธิ์เล่นเสียง · เลือกโหมดอีกครั้งเพื่อรับสิทธิ์";
  }
  function suspend(message){
    // Synchronously stop media before any server or cross-tab request.
    token=null;
    stopLocal();
    render();
    if(message)get("modeOwnerStatus").textContent=message;
  }
  function acceptOwnership(snapshot){
    token=snapshot.mode_token;
    revision=snapshot.revision;
    render();
    onActive?.(active);
    channel?.postMessage({revision,active_mode:active});
  }
  async function issueActivation(mode,at){
    const response=await fetch("/v1/modes/activate",{
      method:"POST",
      headers:{"Content-Type":"application/json","X-VoxWeaveTTS-Intent":"activate-mode"},
      body:JSON.stringify({mode}),
      cache:"no-store",
    });
    const json=await response.json();
    if(!response.ok)throw Error(json.error||"Cannot activate workspace");
    if(at===sequence && active===mode)acceptOwnership(json);
    return json;
  }
  function select(mode){
    if(!valid.has(mode))return Promise.reject(Error("Invalid workspace mode"));
    const at=++sequence;
    suspend();
    active=mode;
    render();
    serial=serial.catch(()=>{}).then(()=>issueActivation(mode,at));
    return serial.catch(error=>{if(at===sequence)reportError(error);throw error;});
  }
  function guard(mode){
    return Boolean(token && active===mode);
  }
  function credentials(mode){
    if(!guard(mode))throw Error("Playback belongs to an inactive workspace");
    return {mode,mode_token:token};
  }
  function loseRemoteOwner(info){
    if(token && info.revision>revision){
      revision=info.revision;
      suspend("อีกแท็บหรือโหมดหนึ่งรับสิทธิ์เล่นเสียงแล้ว · กดโหมดนี้อีกครั้งเพื่อกลับมาทำงาน");
    }else if(!token && info.revision>revision)revision=info.revision;
  }
  function startMonitor(){
    if(typeof root.BroadcastChannel==="function"){
      channel=new root.BroadcastChannel(broadcastName);
      channel.addEventListener("message",event=>{
        const incoming=event.data;
        if(incoming && Number.isInteger(incoming.revision))
          loseRemoteOwner(incoming);
      });
    }
    if(typeof root.EventSource==="function"){
      modeStream=new root.EventSource("/v1/modes/stream");
      modeStream.addEventListener("workspace",event=>{
        try{
          const incoming=JSON.parse(event.data);
          if(incoming && Number.isInteger(incoming.revision))
            loseRemoteOwner(incoming);
        }catch{/* malformed stream frames cannot take audio ownership */}
      });
    }
    if(typeof root.setInterval==="function"){
      monitor=root.setInterval(async()=>{
        if(!token)return;
        try {
          const r=await fetch("/v1/modes/state",{cache:"no-store"});
          if(!r.ok)return;
          loseRemoteOwner(await r.json());
        }catch{/* best-effort: server still rejects stale playback tokens */}
      },pollMs);
    }
    document.addEventListener("play",event=>{
      const audio=event.target;
      if(audio?.tagName!=="AUDIO")return;
      const view=audio.closest?.("[data-mode-view]");
      const mode=view?.getAttribute?.("data-mode-view");
      if(!mode || !guard(mode)){
        audio.pause();
        return;
      }
      // Never play two output devices/sources simultaneously.
      for(const other of document.querySelectorAll("audio")){
        if(other!==audio && !other.paused)other.pause();
      }
    },true);
    for(const button of document.querySelectorAll("[data-mode-target]")){
      button.addEventListener("click",()=>{
        select(button.getAttribute("data-mode-target")).catch(()=>{});
      });
    }
    get("modeGlobalSettings").addEventListener("click",()=>select("settings").catch(()=>{}));
    render();
    select("studio").catch(()=>{});
  }
  function dispose(){
    if(monitor!==null)root.clearInterval?.(monitor);
    channel?.close();
    modeStream?.close();
    suspend();
  }
  return {startMonitor,dispose,select,credentials,guard,get activeMode(){return active;},
          get revision(){return revision;},get owned(){return Boolean(token)}};
}
root.VoxWorkspaceModes={attach,MODES};
if(typeof module!=="undefined"&&module.exports)module.exports={attach,MODES};
})(typeof window==="undefined"?globalThis:window);