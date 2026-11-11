/* Local Live/Discord read-only connectors.
 * Credentials go via loopback POST to the in-memory Python poller only.
 * Text is rendered with textContent, never HTML. Auto-read defaults on, but
 * never starts a provider connection before the user clicks Connect.
 */
(function(root){
"use strict";
const MAX_UNREAD=12;
const MAX_PASSIVE=25;
const MAX_READ_KEEP=100;
const SETTINGS_FORMAT="voxweavetts.source-settings";
const SETTINGS_VERSION=1;
const MAX_SETTINGS_BYTES=16384;
const SETTINGS_KEYS=new Set(["format","version","mode","source_id",
                             "filters","auto_read","read_history_limit",
                             "credential","client_id","client_secret","redirect_uri"]);
function isRecord(value){
  return value!==null && typeof value==="object" && !Array.isArray(value);
}
function validateSettingsProfile(value,mode){
  // Check structure and size, not connection validity. Partial entries and
  // empty fields are valid for offline drafts; Connect validates separately.
  // Secret fields intentionally round-trip as plaintext by explicit request.
  if(!isRecord(value) || Object.keys(value).some(key=>!SETTINGS_KEYS.has(key))
     || value.format!==SETTINGS_FORMAT || value.version!==SETTINGS_VERSION
     || value.mode!==mode)throw Error("ไฟล์ตั้งค่าไม่ตรงกับโหมดหรือรูปแบบที่รองรับ");
  if(typeof value.source_id!=="string" || value.source_id.length>200
     || /[\u0000-\u001f\u007f]/.test(value.source_id))
    throw Error("Source/Channel ID ในไฟล์ไม่ถูกต้อง");
  if(!isRecord(value.filters) || Object.keys(value.filters).some(k=>!["blocked_words","max_chars"].includes(k))
     || typeof value.filters.blocked_words!=="string" || value.filters.blocked_words.length>2000
     || !(value.filters.max_chars==="" || (Number.isInteger(value.filters.max_chars)
          && value.filters.max_chars>=20 && value.filters.max_chars<=280)))
    throw Error("ตัวกรองหรือจำนวนอักษรในไฟล์ไม่ถูกต้อง");
  if(typeof value.auto_read!=="boolean"
     || !(value.read_history_limit==="" || (Number.isInteger(value.read_history_limit)
          && value.read_history_limit>=0 && value.read_history_limit<=MAX_READ_KEEP)))
    throw Error("ค่าคิวเสียงหรือจำนวนประวัติไม่ถูกต้อง");
  if(mode==="discord_client"){
    if(typeof value.client_id!=="string" || value.client_id.length>200
       || typeof value.client_secret!=="string" || value.client_secret.length>2048
       || typeof value.redirect_uri!=="string" || value.redirect_uri.length>240)
      throw Error("Client ID หรือ OAuth Redirect URI ในไฟล์ไม่ถูกต้อง");
  }else if("client_id" in value || "client_secret" in value || "redirect_uri" in value){
    throw Error("ไฟล์ตั้งค่ามีช่องข้อมูลของแหล่งอื่น");
  }else if(typeof value.credential!=="string" || value.credential.length>4096){
    throw Error("ค่าข้อมูลรับรองของแหล่งข้อความไม่ถูกต้อง");
  }
  if(mode==="discord_client" && "credential" in value)
    throw Error("ไฟล์ตั้งค่ามีช่องข้อมูลของแหล่งอื่น");
  return value;
}
const STATE_LABELS={
  queued:"รออ่าน",preparing:"กำลังสร้างเสียง",reading:"กำลังอ่าน",read:"อ่านแล้ว",
  skipped:"ข้ามการอ่าน",manual:"เลือกอ่านเอง",
};
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
  let visible=[], overflow=0;
  function message(text){get("FeedStatus").textContent=String(text);}
  function buildSettingsProfile(){
    const blocked=get("FeedBlocked").value;
    const max=get("FeedMaxChars").value.trim();
    const keep=get("FeedKeepRead").value.trim();
    const data={
      format:SETTINGS_FORMAT,version:SETTINGS_VERSION,mode,
      source_id:get("FeedSourceId").value,
      filters:{blocked_words:blocked,max_chars:max===""?"":Number(max)},
      auto_read:Boolean(get("FeedAuto").checked),
      read_history_limit:keep===""?"":Number(keep),
    };
    if(mode==="discord_client"){
      data.client_id=get("FeedAppId").value;
      data.client_secret=get("FeedAppSecret").value;
      data.redirect_uri=get("FeedRedirect").value;
    }else data.credential=get("FeedCredential").value;
    return validateSettingsProfile(data,mode);
  }
  function exportSettings(){
    try{
      const data=buildSettingsProfile();
      const safeId=data.source_id.replace(/[^a-zA-Z0-9_-]/g,"_").slice(0,40);
      const a=document.createElement("a");
      a.download="VoxWeaveTTS-"+mode+"-"+safeId+".json";
      a.href="data:application/json;charset=utf-8,"+
             encodeURIComponent(JSON.stringify(data,null,2));
      a.click();
      message("ส่งออกการตั้งค่าทุกช่องแล้ว รวมถึงข้อมูลลับ (JSON ไม่เข้ารหัส · เก็บไฟล์ให้ปลอดภัย)");
      return data;
    }catch(error){
      message("ส่งออกไม่สำเร็จ: "+String(error.message||error));
      return null;
    }
  }
  async function importSettings(file){
    if(!file)return false;
    try{
      if(!Number.isSafeInteger(file.size) || file.size<=0 || file.size>MAX_SETTINGS_BYTES)
        throw Error("ไฟล์ตั้งค่าใหญ่เกินกำหนด (สูงสุด 16 KB)");
      const data=validateSettingsProfile(JSON.parse(await file.text()),mode);
      // All validation is atomic: do not modify a single field on failure.
      if(connected)await stop(); // Import never keeps an old-room session alive.
      get("FeedSourceId").value=data.source_id;
      get("FeedBlocked").value=data.filters.blocked_words;
      get("FeedMaxChars").value=String(data.filters.max_chars);
      get("FeedAuto").checked=data.auto_read;
      get("FeedKeepRead").value=String(data.read_history_limit);
      if(mode==="discord_client"){
        get("FeedAppId").value=data.client_id;
        get("FeedRedirect").value=data.redirect_uri;
        get("FeedAppSecret").value=data.client_secret;
      }else get("FeedCredential").value=data.credential;
      prune();render();
      message("โหลดการตั้งค่าครบทุกช่องแล้ว (รวมข้อมูลลับ) · ยังไม่เชื่อมต่ออัตโนมัติ");
      return true;
    }catch(error){
      // JSON parser errors may quote pieces of the input file, including
      // credentials. Never reflect raw parser exceptions in the UI.
      message("นำเข้าการตั้งค่าไม่สำเร็จ: โปรดตรวจรูปแบบไฟล์ เวอร์ชัน และช่องทางที่เลือก");
      return false;
    }
  }
  function readLimit(){
    const raw=Number(get("FeedKeepRead").value);
    return Number.isInteger(raw) ? Math.max(0,Math.min(MAX_READ_KEEP,raw)) : 20;
  }
  function prune(){
    const keep=readLimit();
    let read=0,passive=0;
    // Newest-first; never prune a queued or currently reading message.
    visible=visible.filter(entry=>{
      if(["queued","preparing","reading"].includes(entry.state))return true;
      if(entry.state==="read")return ++read<=keep;
      return ++passive<=MAX_PASSIVE;
    });
  }
  function renderSummary(){
    const queued=visible.filter(x=>x.state==="queued").length;
    const reading=visible.filter(x=>x.state==="preparing"||x.state==="reading").length;
    const read=visible.filter(x=>x.state==="read").length;
    get("FeedQueueStatus").textContent=
      "คิวรออ่าน "+queued+"/"+MAX_UNREAD+
      " · กำลังเตรียม/อ่าน "+reading+
      " · อ่านแล้วที่เก็บ "+read+"/"+readLimit()+
      " · ข้ามเพราะคิวเต็ม "+overflow;
  }
  function clearMessages(){
    visible=[];overflow=0;
    get("FeedItems").replaceChildren();
    renderSummary();
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
      const state=document.createElement("small");
      state.className="source-message-state";
      state.textContent=STATE_LABELS[data.state]||"เลือกอ่านเอง";
      li.append(details,body,button,state);
      area.appendChild(li);
    }
    renderSummary();
  }
  function setMessageState(messageId,state){
    if(!Object.prototype.hasOwnProperty.call(STATE_LABELS,state))return;
    const entry=visible.find(x=>String(x.message_id)===String(messageId));
    if(!entry)return; // source session already switched or was cleared
    entry.state=state;
    prune();
    render();
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
    if(!Number.isInteger(maxChars) || get("FeedMaxChars").value.trim()==="")
      throw Error("กรุณากำหนดความยาวข้อความสูงสุดก่อนเชื่อมต่อ");
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
          const auto=Boolean(get("FeedAuto").checked);
          const entry={message_id:item.message_id,author:item.author,text:item.text,
                       state:auto?"queued":"manual"};
          visible.unshift(entry);
          const accepted=onMessage(item,auto);
          if(accepted==="skipped"){
            entry.state="skipped";
            overflow++;
          }
          prune();
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
  get("FeedExport").addEventListener("click",exportSettings);
  get("FeedImport").addEventListener("click",()=>get("FeedImportFile").click());
  get("FeedImportFile").addEventListener("change",async()=>{
    const input=get("FeedImportFile");
    const file=input.files?.[0];
    input.value=""; // re-selecting the same file should still trigger change
    await importSettings(file);
  });
  get("FeedStart").addEventListener("click",()=>{
    start().catch(()=>{});
  });
  get("FeedStop").addEventListener("click",()=>stop().catch(()=>{}));
  get("FeedStop").disabled=true;
  get("FeedKeepRead").addEventListener("input",()=>{
    prune();render();
  });
  renderSummary();
  return {start,stop,poll,suspend:localSuspend,setMessageState,exportSettings,importSettings,
          get connected(){return connected;},get visible(){return visible.slice();}};
}
root.VoxSourceFeed={attach};
if(typeof module!=="undefined"&&module.exports)module.exports={attach};
})(typeof window==="undefined"?globalThis:window);