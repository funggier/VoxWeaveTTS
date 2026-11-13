/* Concurrent workspaces: changing the visible tab does not disconnect other
 * Live/Discord sources or stop their audio. One ephemeral token per workspace.
 * Reclaiming the SAME workspace from another browser tab revokes only that
 * workspace, not all other ones.
 */
(function(root){
"use strict";
const MODES=Object.freeze([
  {id:"studio",label:"สร้างเสียง"},
  {id:"reader",label:"อ่านเอกสาร"},
  {id:"tiktok",label:"TikTok LIVE"},
  {id:"live",label:"YouTube LIVE (API)"},
  {id:"youtube_browser",label:"YouTube LIVE (Browser)"},
  {id:"discord",label:"Discord"},
  {id:"discord_client",label:"Discord Client"},
  {id:"queue",label:"คิวและ Subtitle"},
  {id:"rules",label:"คำอ่านและกฎ"},
  {id:"settings",label:"ตั้งค่ากลาง"},
]);
function attach({document,stopLocal,onLostMode,onActive,onError,onAudioPlay,pollMs=1200}){
  if(!document)throw Error("Mode workspace requires a document");
  const valid=new Set(MODES.map(x=>x.id));
  const get=id=>document.getElementById(id);
  const owners=new Map(), ownedRevisions=new Map();
  let active="studio", revision=0, serial=Promise.resolve(), stopped=false;
  let channel=null, monitor=null, modeStream=null;
  const broadcastName="VoxWeaveTTS-workspace-owner-v1";

  function render(){
    for(const view of document.querySelectorAll("[data-mode-view]"))
      view.hidden=view.getAttribute("data-mode-view")!==active;
    for(const button of document.querySelectorAll("[data-mode-target]"))
      button.setAttribute("aria-pressed",
        button.getAttribute("data-mode-target")===active?"true":"false");
    get("modeTitle").textContent=MODES.find(x=>x.id===active)?.label||active;
    get("modeOwnerStatus").textContent=owners.has(active)
      ?"ช่องทางต่าง ๆ ทำงานพร้อมกันได้ · เปลี่ยนแท็บไม่ตัดการเชื่อมต่อ"
      :"กำลังเปิดพื้นที่ทำงานนี้...";
  }
  function reportError(error){
    const message=String(error?.message||error);
    get("modeOwnerStatus").textContent=message;
    onError?.(message);
  }
  function revokeMode(mode){
    if(!owners.has(mode))return;
    owners.delete(mode);
    ownedRevisions.delete(mode);
    onLostMode?.(mode);
    if(mode===active)render();
  }
  function observe(incoming){
    if(!incoming || !Number.isInteger(incoming.revision) || incoming.revision<=revision)return;
    revision=incoming.revision;
    const changed=incoming.mode_revisions;
    if(changed && typeof changed==="object"){
      for(const [mode,localRevision] of ownedRevisions){
        if(Number.isInteger(changed[mode]) && changed[mode]>localRevision)
          revokeMode(mode);
      }
    }
  }
  function accept(mode,snapshot){
    // A response can arrive after navigation. Keep that mode's capability
    // because it belongs to this tab, even when another mode is now visible.
    owners.set(mode,snapshot.mode_token);
    ownedRevisions.set(mode,snapshot.revision);
    revision=Math.max(revision,snapshot.revision);
    channel?.postMessage({
      revision:snapshot.revision,
      mode_revisions:snapshot.mode_revisions,
    });
    if(active===mode){render();onActive?.(mode);}
  }
  async function issueActivation(mode){
    const response=await fetch("/v1/modes/activate",{
      method:"POST",
      headers:{"Content-Type":"application/json",
               "X-VoxWeaveTTS-Intent":"activate-mode"},
      body:JSON.stringify({mode}),cache:"no-store",
    });
    const snapshot=await response.json();
    if(!response.ok)throw Error(snapshot.error||"Cannot activate workspace");
    if(!stopped)accept(mode,snapshot);
    return snapshot;
  }
  function select(mode){
    if(!valid.has(mode))return Promise.reject(Error("Invalid workspace mode"));
    active=mode;
    render();
    if(owners.has(mode)){onActive?.(mode);return Promise.resolve();}
    serial=serial.catch(()=>{}).then(()=>issueActivation(mode));
    return serial.catch(error=>{if(active===mode)reportError(error);throw error;});
  }
  function reclaim(mode){
    if(!valid.has(mode))return Promise.reject(Error("Invalid workspace mode"));
    if(active!==mode)return Promise.reject(Error("Select this workspace before connecting"));
    // Only an explicit Connect action calls this: a browser may be holding
    // a locally cached token from before server restart or another tab claim.
    // Refreshing only the requested workspace intentionally revokes its
    // former source, never unrelated connected channels.
    serial=serial.catch(()=>{}).then(()=>issueActivation(mode));
    return serial.then(()=>credentials(mode));
  }
  function guard(mode){return owners.has(mode);}
  function credentials(mode){
    const token=owners.get(mode);
    if(!token)throw Error("This workspace is not connected to the local server");
    return {mode,mode_token:token};
  }
  function startMonitor(){
    if(typeof root.BroadcastChannel==="function"){
      channel=new root.BroadcastChannel(broadcastName);
      channel.addEventListener("message",event=>observe(event.data));
    }
    if(typeof root.EventSource==="function"){
      modeStream=new root.EventSource("/v1/modes/stream");
      modeStream.addEventListener("workspace",event=>{
        try{observe(JSON.parse(event.data));}catch{/* ignore bad SSE frame */}
      });
    }
    if(typeof root.setInterval==="function"){
      monitor=root.setInterval(async()=>{
        if(owners.size===0)return;
        try{
          const r=await fetch("/v1/modes/state",{cache:"no-store"});
          if(r.ok)observe(await r.json());
        }catch{/* server checks ownership when a source reports */}
      },pollMs);
    }
    document.addEventListener("play",event=>{
      const audio=event.target;
      if(audio?.tagName!=="AUDIO")return;
      const view=audio.closest?.("[data-mode-view]");
      const mode=view?.getAttribute?.("data-mode-view");
      if(mode && !guard(mode)){audio.pause();return;}
      onAudioPlay?.(audio);
    },true);
    for(const button of document.querySelectorAll("[data-mode-target]"))
      button.addEventListener("click",()=>select(
        button.getAttribute("data-mode-target")).catch(()=>{}));
    get("modeGlobalSettings")?.addEventListener("click",
      ()=>select("settings").catch(()=>{}));
    render();
    select("studio").catch(()=>{});
  }
  function dispose(){
    stopped=true;
    if(monitor!==null)root.clearInterval?.(monitor);
    channel?.close();modeStream?.close();
    for(const mode of [...owners.keys()])revokeMode(mode);
    stopLocal?.();
  }
  return {
    startMonitor,dispose,select,reclaim,credentials,guard,
    get activeMode(){return active;},
    get revision(){return revision;},
    get owned(){return owners.has(active);},
    get ownedModes(){return [...owners.keys()];},
  };
}
root.VoxWorkspaceModes={attach,MODES};
if(typeof module!=="undefined"&&module.exports)module.exports={attach,MODES};
})(typeof window==="undefined"?globalThis:window);
