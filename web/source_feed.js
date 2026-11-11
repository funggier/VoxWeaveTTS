/* Local Live/Discord read-only connectors.
 * Credentials go via loopback POST to the in-memory Python poller only.
 * Text is rendered with textContent, never HTML. Auto-read defaults on, but
 * never starts a provider connection before the user clicks Connect.
 */
(function(root){
"use strict";
const MAX_VISIBLE=25;
const RPC_PHASE_NAMES={
  not_connected:"ยังไม่ได้เชื่อม",
  opening_discord_pipe:"กำลังค้นหา Discord Desktop",
  handshake:"กำลังเริ่ม RPC Handshake",
  awaiting_discord_consent:"รอยืนยันสิทธิ์จากหน้าต่าง Discord Desktop",
  exchanging_oauth_code:"กำลังแลก OAuth Code",
  authenticating:"กำลังตรวจสิทธิ์ OAuth",
  subscribing_channel:"กำลังสมัครรับข้อความจากห้องที่เลือก",
  subscribed:"สมัครรับข้อความจากห้องสำเร็จ",
  disconnected:"ตัดการเชื่อมต่อแล้ว",
};
function attach({mode,el,credentials,guard,onMessage,onPick,onStop}){
  if(!["live","discord","discord_client"].includes(mode))throw Error("invalid source mode");
  const prefix=mode==="discord_client"?"discordClient":mode;
  const get=id=>el(prefix+id);
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
  function localSuspend(){
    generation++;
    connected=false;
    inFlight=false;
    if(timer!==null){clearInterval(timer);timer=null;}
    get("FeedStart").disabled=false;
    get("FeedStop").disabled=true;
    // Preserve the user-selected checkbox across reconnects and tab changes.
    // Suspension still cancels the source worker and drops queued speech.
    onStop?.();
    // Keep displayed messages as a temporary read-only history in this tab,
    // but never continue polling/autoreading after it loses mode ownership.
    message("หยุดรับข้อความแล้วเมื่อเปลี่ยนโหมด · เชื่อมต่อใหม่เพื่อรับข้อความล่าสุด");
  }
  async function start(){
    if(!guard(mode))throw Error("กรุณาเปิดโหมดนี้ก่อนเชื่อมต่อ");
    const channelId=get("FeedSourceId").value.trim();
    const temporaryCredential=mode==="discord_client" ? {
      client_id:get("FeedAppId").value.trim(),
      client_secret:get("FeedAppSecret").value.trim(),
      redirect_uri:get("FeedRedirect").value.trim(),
    } : get("FeedCredential").value.trim();
    const blocked=get("FeedBlocked").value.split(",").map(x=>x.trim()).filter(Boolean);
    const maxChars=Number(get("FeedMaxChars").value);
    if(!Number.isInteger(maxChars))throw Error("ความยาวข้อความต้องเป็นตัวเลขจำนวนเต็ม");
    // Switch room without leaving the previous source running if the new
    // room/credentials fail: unsubscribe/stop before trying the new room.
    const previousOwner=connected?credentials(mode):null;
    localSuspend();
    if(previousOwner){
      try{await api("stop",previousOwner);}
      catch{/* stale-owner server activation will also stop the old source */}
    }
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
      if(mode==="discord_client")get("FeedAppSecret").value="";
      else get("FeedCredential").value=""; // clear DOM secret as soon as accepted
      if(ticket!==generation||!guard(mode))return;
      connected=true;
      get("FeedStop").disabled=false;
      message("เริ่มกระบวนการเชื่อมต่อแล้ว · รอตรวจสอบสิทธิ์และสมัครรับข้อความจากผู้ให้บริการ");
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
      const phase=status.failed_phase && status.state==="error"
        ? " · ผิดพลาดที่ "+(RPC_PHASE_NAMES[status.failed_phase]||"ขั้นตอน Discord RPC")
        : status.connection_phase ? " · "+(RPC_PHASE_NAMES[status.connection_phase]||"กำลังตรวจสอบสถานะ Discord RPC") : "";
      message(
        "API: "+status.state+phase+
        " · รับ "+(status.received||0)+
        " · กรอง/ล้นคิว "+(status.discarded||0)+
        " · รออ่าน "+(status.pending||0)+
        " · รอบถัดไป "+Math.round(status.next_poll_seconds||0)+"s"+
        (["error","connecting","retrying"].includes(status.state) ? " · "+status.info : "")
      );
      if(status.state==="ended"||status.state==="error"){
        connected=false;
        if(timer!==null){clearInterval(timer);timer=null;}
        get("FeedStart").disabled=false;
        get("FeedStop").disabled=true;
        // Clear pending speech after an authorization or transport failure.
        // Preserve the checkbox choice for the next explicit connection.
        onStop?.();
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