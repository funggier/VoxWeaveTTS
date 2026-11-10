/* Consent-first local Live/Discord read-only connectors.
 * Credentials go via loopback POST to the in-memory Python poller only.
 * Text is rendered with textContent, never HTML. Auto-read is opt-in.
 */
(function(root){
"use strict";
const MAX_VISIBLE=25;
function attach({mode,el,credentials,guard,onMessage,onPick,onStop}){
  if(!["live","discord"].includes(mode))throw Error("invalid source mode");
  const get=id=>el(mode+id);
  let timer=null, generation=0, connected=false, inFlight=false;
  let visible=[];
  function message(text){get("FeedStatus").textContent=String(text);}
  function clearMessages(){
    visible=[];
    get("FeedItems").replaceChildren();
  }
  function render(){
    const area=get("FeedItems");
    area.replaceChildren();
    for(const data of visible){
      const li=document.createElement("li");
      li.className="source-message";
      const details=document.createElement("span");
      details.className="source-author";
      details.textContent=(data.author||"ไม่ระบุชื่อ")+": ";
      const body=document.createElement("span");
      body.textContent=data.text;
      const button=document.createElement("button");
      button.type="button";
      button.className="small-button";
      button.textContent="เลือกข้อความนี้";
      button.addEventListener("click",()=>{
        if(!guard(mode)){
          message("กรุณาเปิดโหมดนี้ก่อนเลือกข้อความ");
          return;
        }
        onPick(data);
      });
      li.append(details,body,button);
      area.appendChild(li);
    }
  }
  async function api(operation,body){
    const response=await fetch("/v1/sources/"+operation,{
      method:"POST",
      headers:{"Content-Type":"application/json","X-VoxWeaveTTS-Intent":{
        start:"start-live-source",stop:"stop-live-source",
        drain:"drain-live-source",
      }[operation]},
      body:JSON.stringify(body),
    });
    const result=await response.json();
    if(!response.ok)throw Error(result.error||"source operation failed");
    return result;
  }
  function localSuspend({clearAuto=true}={}){
    generation++;
    connected=false;
    inFlight=false;
    if(timer!==null){clearInterval(timer);timer=null;}
    get("FeedStart").disabled=false;
    get("FeedStop").disabled=true;
    if(clearAuto)get("FeedAuto").checked=false;
    onStop?.();
    // Keep displayed messages as a temporary read-only history in this tab,
    // but never continue polling/autoreading after it loses mode ownership.
    message("หยุดรับข้อความแล้วเมื่อเปลี่ยนโหมด · เชื่อมต่อใหม่เพื่อรับข้อความล่าสุด");
  }
  async function start(){
    if(!guard(mode))throw Error("กรุณาเปิดโหมดนี้ก่อนเชื่อมต่อ");
    const channelId=get("FeedSourceId").value.trim();
    const temporaryCredential=get("FeedCredential").value.trim();
    const blocked=get("FeedBlocked").value.split(",").map(x=>x.trim()).filter(Boolean);
    const maxChars=Number(get("FeedMaxChars").value);
    if(!Number.isInteger(maxChars))throw Error("ความยาวข้อความต้องเป็นตัวเลขจำนวนเต็ม");
    localSuspend({clearAuto:false});
    clearMessages();
    const ticket=++generation;
    get("FeedStart").disabled=true;
    message("กำลังเชื่อมต่อ Official API แบบอ่านอย่างเดียว...");
    try{
      const result=await api("start",{
        ...credentials(mode),source_id:channelId,
        credential:temporaryCredential,
        filters:{blocked_words:blocked,max_chars:maxChars},
      });
      get("FeedCredential").value=""; // do not retain secrets in DOM inputs
      if(ticket!==generation||!guard(mode))return;
      connected=true;
      get("FeedStop").disabled=false;
      message("เชื่อมต่อแล้ว · ข้อความเก่าก่อนเริ่มเชื่อมต่อจะไม่ถูกอ่าน");
      timer=setInterval(()=>poll().catch(error=>message(String(error.message||error))),1200);
      await poll();
      return result;
    }catch(error){
      if(ticket===generation){
        connected=false;
        get("FeedStart").disabled=false;
        message("เชื่อมต่อไม่สำเร็จ: "+String(error.message||error));
      }
      throw error;
    }
  }
  async function poll(){
    if(!connected||inFlight||!guard(mode))return;
    const ticket=generation;
    inFlight=true;
    try{
      const result=await api("drain",{...credentials(mode),limit:10});
      if(ticket!==generation||!guard(mode))return;
      const status=result.status;
      if(Array.isArray(result.messages)){
        for(const item of result.messages){
          if(!item || typeof item.text!=="string")continue;
          visible.unshift({message_id:item.message_id,author:item.author,text:item.text});
          if(visible.length>MAX_VISIBLE)visible.pop();
          onMessage(item,Boolean(get("FeedAuto").checked));
        }
      }
      render();
      message(
        "API: "+status.state+
        " · รับ "+(status.received||0)+
        " · กรอง/ล้นคิว "+(status.discarded||0)+
        " · รออ่าน "+(status.pending||0)+
        " · รอบถัดไป "+Math.round(status.next_poll_seconds||0)+"s"+
        (status.state==="error" ? " · "+status.info : "")
      );
      if(status.state==="ended"||status.state==="error"){
        connected=false;
        if(timer!==null){clearInterval(timer);timer=null;}
        get("FeedStart").disabled=false;
        get("FeedStop").disabled=true;
      }
    }catch(error){
      if(ticket===generation){
        if(/owner|not running|inactive|revoked|active mode/i.test(String(error.message||error))){
          localSuspend();
        }else{
          // API errors are sanitized by the backend. No secret in thrown text.
          message(String(error.message||error));
        }
      }
    }finally{if(ticket===generation)inFlight=false;}
  }
  async function stop(){
    if(!guard(mode)){
      localSuspend();
      return;
    }
    // Capture before clearing the UI; client will no longer drain.
    const authorization=credentials(mode);
    localSuspend();
    try { await api("stop",authorization); }
    catch(error){message("หยุดรับใน Browser แล้ว ("+String(error.message||error)+")");}
  }
  get("FeedStart").addEventListener("click",()=>{
    start().catch(()=>{});
  });
  get("FeedStop").addEventListener("click",()=>stop().catch(()=>{}));
  get("FeedStop").disabled=true;
  return {start,stop,poll,suspend:localSuspend,
          get connected(){return connected;},get visible(){return visible.slice();}};
}
root.VoxSourceFeed={attach};
if(typeof module!=="undefined"&&module.exports)module.exports={attach};
})(typeof window==="undefined"?globalThis:window);