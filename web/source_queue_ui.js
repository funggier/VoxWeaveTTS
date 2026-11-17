/* Per-mode, non-secret live queue preferences.
 * Never persist credential inputs. Strictly use the server's atomic
 * settings API; do not overwrite changes from another browser tab.
 */
(function(root){
"use strict";
const MODES=("live youtube_browser tiktok_browser tiktok discord discord_client").split(" ");
const prefix={
  youtube_browser:"youtubeBrowser",tiktok_browser:"tiktokBrowser",
  discord_client:"discordClient",
};
const API="/v1/settings/source-queues";

function attach(mode,el){
  if(!MODES.includes(mode))throw Error("invalid source queue mode");
  const id=prefix[mode]||mode;
  const get=key=>el(id+"Feed"+key);
  const save=get("Save"), status=get("SaveStatus");
  if(!save||!status)return null;
  let revision=0;
  let loading=false;
  const ids=["Blocked","MaxChars","KeepRead","Auto","RandomEnable","RandomThreshold","RandomKeep","ContinueOnTtsError"];
  const initial=ids.map(key=>String(get(key)?.type==="checkbox"?Boolean(get(key).checked):get(key)?.value??""));
  const dirty=()=>ids.some((key,index)=>String(get(key)?.type==="checkbox"?Boolean(get(key).checked):get(key)?.value??"")!==initial[index]);

  function read(){
    const int=(key,min,max)=>{
      const raw=String(get(key)?.value??"").trim();
      if(!/^\d{1,6}$/.test(raw))throw Error(key+" ต้องเป็นตัวเลขจำนวนเต็ม");
      const value=Number(raw);
      if(!Number.isInteger(value)||value<min||value>max)
        throw Error(key+" ต้องอยู่ระหว่าง "+min+"–"+max.toLocaleString("en-US"));
      return value;
    };
    const blocked=String(get("Blocked")?.value??"");
    if(blocked.length>2000 || /[\u0000-\u001f\u007f]/.test(blocked))
      throw Error("คำที่ไม่อ่านมีความยาวหรืออักขระไม่ถูกต้อง");
    const settings={
      blocked_words:blocked,
      max_chars:int("MaxChars",20,8000),
      read_history_limit:int("KeepRead",0,100),
      auto_read:get("Auto")?.checked===true,
      random_queue_enabled:get("RandomEnable")?.checked===true,
      random_queue_threshold:int("RandomThreshold",2,100000),
      random_queue_keep:int("RandomKeep",1,99999),
      continue_on_tts_error:get("ContinueOnTtsError")?.checked===true,
    };
    if(settings.random_queue_keep>=settings.random_queue_threshold)
      throw Error("จำนวนข้อความที่สุ่มเก็บต้องน้อยกว่าจำนวนเริ่มสุ่มลบ");
    return settings;
  }
  function apply(value){
    if(!value || typeof value!=="object")return;
    get("Blocked").value=value.blocked_words;
    get("MaxChars").value=String(value.max_chars);
    get("KeepRead").value=String(value.read_history_limit);
    get("Auto").checked=value.auto_read===true;
    get("RandomEnable").checked=value.random_queue_enabled===true;
    get("RandomThreshold").value=String(value.random_queue_threshold);
    get("RandomKeep").value=String(value.random_queue_keep);
    get("ContinueOnTtsError").checked=value.continue_on_tts_error===true;
    // Existing feed keeps its own queue/render semantics; signal input
    // handlers rather than touching the feed's internal data structures.
    get("KeepRead").dispatchEvent?.(new Event("input"));
  }
  async function load(){
    if(loading)return;
    loading=true;
    try{
      const response=await root.fetch(API,{cache:"no-store"});
      const result=await response.json();
      if(!response.ok)throw Error(result.error||"load failed");
      const entry=result.modes?.[mode];
      if(!entry||!Number.isInteger(entry.revision))throw Error("invalid settings response");
      revision=entry.revision;
      if(!dirty()){
        apply(entry.settings);
        status.textContent=revision?"โหลดค่าคิวที่บันทึกไว้แล้ว":"ใช้ค่าเริ่มต้น (ยังไม่ได้บันทึก)";
      }else{
        status.textContent="มีค่าที่กำลังแก้ไข จึงไม่ทับด้วยค่าที่บันทึกไว้";
      }
    }catch{
      status.textContent="ยังโหลดการตั้งค่าคิวไม่ได้ (สามารถบันทึกใหม่หลังเชื่อมต่อเซิร์ฟเวอร์)";
    }finally{loading=false;}
  }
  async function persist(){
    if(loading){
      status.textContent="กำลังโหลดค่าเดิม กรุณาบันทึกอีกครั้ง";
      return;
    }
    let settings;
    try{settings=read();}
    catch(error){status.textContent="ไม่สามารถบันทึก: "+String(error.message||error);return;}
    save.disabled=true;
    status.textContent="กำลังบันทึกการตั้งค่าคิว...";
    try{
      const response=await root.fetch(API,{
        method:"POST",
        headers:{"Content-Type":"application/json",
                 "X-VoxWeaveTTS-Intent":"save-source-queue"},
        body:JSON.stringify({mode,expected_revision:revision,settings}),
      });
      const result=await response.json();
      if(!response.ok){
        if(response.status===409){
          status.textContent="การตั้งค่าถูกแก้ในอีกแท็บ กรุณารีเฟรชหน้าก่อนบันทึกใหม่";
          return;
        }
        throw Error(result.error||"save failed");
      }
      revision=result.modes?.[mode]?.revision??revision;
      status.textContent="บันทึกการตั้งค่าคิวสำเร็จ ✓ · ค่าความยาวและคำกรองมีผลกับการเชื่อมต่อใหม่";
    }catch{
      status.textContent="บันทึกการตั้งค่าคิวไม่สำเร็จ กรุณาตรวจการเชื่อมต่อเซิร์ฟเวอร์";
    }finally{save.disabled=false;}
  }
  save.addEventListener("click",()=>persist());
  load();
  return {load,read,persist,get revision(){return revision;}};
}
root.VoxSourceQueueUI={attach};
if(typeof module!=="undefined"&&module.exports)module.exports={attach};
})(typeof window==="undefined"?globalThis:window);
