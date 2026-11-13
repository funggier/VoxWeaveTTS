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
                             "filters","auto_read","read_sender_name","read_history_limit",
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
  if(typeof value.source_id!=="string" || value.source_id.length>(["youtube_browser","tiktok_browser"].includes(mode)?600:200)
     || /[\u0000-\u001f\u007f]/.test(value.source_id))
    throw Error("Source/Channel ID ในไฟล์ไม่ถูกต้อง");
  if(!isRecord(value.filters) || Object.keys(value.filters).some(k=>!["blocked_words","max_chars"].includes(k))
     || typeof value.filters.blocked_words!=="string" || value.filters.blocked_words.length>2000
     || !(value.filters.max_chars==="" || (Number.isInteger(value.filters.max_chars)
          && value.filters.max_chars>=20 && value.filters.max_chars<=280)))
    throw Error("ตัวกรองหรือจำนวนอักษรในไฟล์ไม่ถูกต้อง");
  if(typeof value.auto_read!=="boolean"
     || ("read_sender_name" in value && typeof value.read_sender_name!=="boolean")
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
  }else if(mode==="tiktok"||mode==="youtube_browser"||mode==="tiktok_browser"){
    if("credential" in value)throw Error("ไฟล์ Browser/TikTok ไม่ต้องมี Credential");
  }else if(typeof value.credential!=="string" || value.credential.length>4096){
    throw Error("ค่าข้อมูลรับรองของแหล่งข้อความไม่ถูกต้อง");
  }
  if(mode==="discord_client" && "credential" in value)
    throw Error("ไฟล์ตั้งค่ามีช่องข้อมูลของแหล่งอื่น");
  return value;
}
const EXTENSION_PHASE_NAMES=Object.freeze({
  checking_input:"ขั้นตอน 1/4 · ตรวจสอบชื่อ TikTok LIVE และตัวกรอง",
  claiming_owner:"ขั้นตอน 2/4 · เตรียมสิทธิ์ของโหมดรับข้อความ",
  starting_worker:"ขั้นตอน 2/4 · สร้างรหัสจับคู่สำหรับส่วนเสริม",
  waiting_extension_pair:"ขั้นตอน 3/4 · รอกรอกรหัสจับคู่ในส่วนเสริม Chrome (ใช้ได้ 5 นาที)",
  waiting_chat_dom:"ขั้นตอน 4/4 · ส่วนเสริมเชื่อมต่อแล้ว · รอข้อความใหม่ในแท็บ TikTok LIVE",
  ready:"เชื่อมต่อสำเร็จ · รับคอมเมนต์จาก TikTok Extension ได้แล้ว",
  comments_off:"ส่วนเสริมพบ Comments off ในแท็บ TikTok ที่เลือก · ตรวจสอบว่าเปิด LIVE ที่แสดงคอมเมนต์ได้",
  extension_disconnected:"ส่วนเสริมขาดการเชื่อมต่อ · กดสร้างรหัสจับคู่ใหม่ใน VoxWeaveTTS แล้วเชื่อมส่วนเสริมอีกครั้ง",
  retrying:"ช่องทางส่วนเสริมขัดข้อง · ตรวจการเชื่อมต่อกับโปรแกรมในเครื่อง",
  error:"เชื่อมต่อไม่สำเร็จ",
  ended:"หยุดรับข้อความจาก TikTok Extension แล้ว",
  stopped:"หยุดรับข้อความจาก TikTok Extension แล้ว",
});
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
const BROWSER_PHASE_NAMES=Object.freeze({
  checking_input:"ขั้นตอน 1/5 · ตรวจสอบ Video ID หรือ URL และตัวกรอง",
  claiming_owner:"ขั้นตอน 2/5 · เตรียมพื้นที่ทำงานและขอสิทธิ์ควบคุมช่องทาง",
  starting_worker:"ขั้นตอน 2/5 · ส่งคำขอเปิด Browser ไปยังโปรแกรมในเครื่อง",
  preparing:"ขั้นตอน 3/5 · เตรียมตัวรับข้อความจาก Browser",
  locating_browser:"ขั้นตอน 3/5 · ค้นหา Google Chrome หรือ Microsoft Edge",
  starting_browser:"ขั้นตอน 3/5 · กำลังเปิดหน้าต่าง YouTube Chat-only",
  waiting_debugger:"ขั้นตอน 3/5 · รอ Browser เปิดพอร์ตควบคุมเฉพาะในเครื่อง",
  finding_chat_page:"ขั้นตอน 4/5 · ค้นหาหน้า YouTube Live Chat ใน Browser",
  connecting_dom:"ขั้นตอน 4/5 · เชื่อมระบบควบคุม DOM ของ Browser",
  reading_dom:"ขั้นตอน 5/5 · ตรวจสอบองค์ประกอบข้อความในหน้า Chat",
  waiting_chat_dom:"ขั้นตอน 5/5 · รอให้หน้า Live Chat โหลดหรือเปิดแชท",
  ready:"เชื่อมต่อสำเร็จ · พร้อมอ่านข้อความใหม่จาก YouTube Live Chat",
  comments_off:"TikTok ใน Browser นี้แสดง Comments off · ไม่ได้แปลว่าเจ้าของไลฟ์ปิดคอมเมนต์ ตรวจสอบสิทธิ์การเข้าถึงในหน้าต่างนี้",
  comments_off_login_prompt:"TikTok ใน Browser ที่โปรแกรมควบคุมแสดง Comments off และ Log in · แต่ LIVE อาจมีคอมเมนต์ปกติใน Chrome ธรรมดา อย่าลองเข้าสู่ระบบซ้ำหากระบบจำกัดจำนวนครั้ง",
  login_prompt:"TikTok แสดง Log in และยังไม่พบ DOM แชท · ไม่ได้แปลว่าต้องเข้าสู่ระบบจึงจะดูคอมเมนต์ได้",
  login_rate_limited:"TikTok จำกัดจำนวนครั้งในการเข้าสู่ระบบ · หยุดลองเข้าสู่ระบบหรือเชื่อมต่อ Browser ซ้ำ และใช้ TikTok LIVE (TikFinity) แทนชั่วคราว",
  retrying:"การเชื่อมต่อขัดข้อง · กำลังรอลองเชื่อมต่อใหม่",
  error:"เชื่อมต่อไม่สำเร็จ",
  ended:"ไลฟ์สิ้นสุดหรือหน้าต่าง Chat ปิดแล้ว",
  stopped:"หยุดรับข้อความจาก Browser แล้ว",
});
function attach({mode,el,credentials,guard,onMessage,onPick,onStop,onSenderPreference,onConnect}){
  if(!["live","youtube_browser","tiktok_browser","discord","discord_client","tiktok"].includes(mode))throw Error("invalid source mode");
  const prefix=mode==="discord_client"?"discordClient":mode==="youtube_browser"?"youtubeBrowser":mode==="tiktok_browser"?"tiktokBrowser":mode;
  const get=id=>el(prefix+id);
  let timer=null, generation=0, connected=false, inFlight=false;
  let socket=null, wsMessages=0, wsRejected=0, wsSequence=0;
  const seen=new Set();
  let visible=[], overflow=0;
  const browserMode=mode==="youtube_browser"||mode==="tiktok_browser";
  const extensionMode=mode==="tiktok_browser";
  const platform=mode==="tiktok_browser"?"TikTok":"YouTube";
  let browserStageName="",browserStageLog=[];
  function message(text){get("FeedStatus").textContent=String(text);}
  function clearBrowserProgress(){
    if(!browserMode)return;
    browserStageName="";browserStageLog=[];
    get("FeedProgress")?.replaceChildren();
  }
  function browserStage(phase,extra=""){
    if(!browserMode)return;
    const desc=extensionMode
      ? (EXTENSION_PHASE_NAMES[phase]||"กำลังตรวจสอบการเชื่อมต่อ TikTok Extension")
      : (BROWSER_PHASE_NAMES[phase]||"กำลังตรวจสอบการเชื่อมต่อ Browser")
          .replaceAll("YouTube",platform);
    if(browserStageName!==phase){
      browserStageName=phase;
      const item=document.createElement("li");
      item.textContent=desc;
      browserStageLog.push(item);
      if(browserStageLog.length>12)browserStageLog.shift();
      get("FeedProgress")?.replaceChildren(...browserStageLog);
    }
    message(desc+(extra?" · "+extra:""));
  }
  function buildSettingsProfile(){
    const blocked=get("FeedBlocked").value;
    const max=get("FeedMaxChars").value.trim();
    const keep=get("FeedKeepRead").value.trim();
    const data={
      format:SETTINGS_FORMAT,version:SETTINGS_VERSION,mode,
      source_id:get("FeedSourceId").value,
      filters:{blocked_words:blocked,max_chars:max===""?"":Number(max)},
      auto_read:Boolean(get("FeedAuto").checked),
      read_sender_name:Boolean(get("FeedReadSender")?.checked),
      read_history_limit:keep===""?"":Number(keep),
    };
    if(mode==="discord_client"){
      data.client_id=get("FeedAppId").value;
      data.client_secret=get("FeedAppSecret").value;
      data.redirect_uri=get("FeedRedirect").value;
    }else if(mode!=="tiktok"&&!browserMode)data.credential=get("FeedCredential").value;
    return validateSettingsProfile(data,mode);
  }
  async function exportSettings(){
    try{
      const data=buildSettingsProfile();
      const safeId=data.source_id.replace(/[^a-zA-Z0-9_-]/g,"_").slice(0,40)||"settings";
      const filename="VoxWeaveTTS-"+mode+"-"+safeId+".json";
      const content=JSON.stringify(data,null,2)+"\n";
      if(typeof root.showSaveFilePicker==="function"){
        // Chrome: true browser Save As, with native path/filename selection.
        // Invoke the picker before the first await, preserving user activation.
        const file=await root.showSaveFilePicker({
          suggestedName:filename,
          types:[{description:"VoxWeaveTTS JSON",accept:{"application/json":[".json"]}}],
        });
        const stream=await file.createWritable();
        try{
          await stream.write(content);
          await stream.close();
        }catch{
          try{await stream.abort?.();}catch{/* no partial write on cancel */}
          throw Error("file write failed");
        }
      }else{
        // Firefox does not implement showSaveFilePicker. Ask the loopback-only
        // desktop app to open a Windows Save As dialog. No path is provided by
        // the web page: the user chooses the destination in the native UI.
        const response=await fetch("/v1/sources/save-profile",{
          method:"POST",
          headers:{"Content-Type":"application/json",
                   "X-VoxWeaveTTS-Intent":"choose-source-profile-file"},
          body:JSON.stringify({filename,profile:data}),
        });
        const status=await response.json();
        if(!response.ok){
          if(response.status===503)
            throw Error("เปิดหน้าต่าง Save As ของ Windows ไม่ได้");
          throw Error("เปิดหน้าต่างบันทึกไฟล์ไม่สำเร็จ");
        }
        if(status.cancelled){
          message("ยกเลิกการบันทึกไฟล์");
          return null;
        }
        if(!status.saved)throw Error("ไม่ได้รับผลยืนยันการบันทึกไฟล์");
      }
      message("บันทึกไฟล์การตั้งค่าแล้ว (มีข้อมูลลับที่ไม่เข้ารหัส · เก็บไฟล์อย่างปลอดภัย)");
      return data;
    }catch(error){
      if(error?.name==="AbortError"){
        message("ยกเลิกการบันทึกไฟล์");
      }else{
        // Never reflect browser/OS error messages that could contain file
        // paths or secret-bearing payloads.
        message("ส่งออกไม่สำเร็จ · ตรวจสิทธิ์บันทึกไฟล์ หรือเปิด Save As ของ Windows");
      }
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
      if("read_sender_name" in data){
        get("FeedReadSender").checked=data.read_sender_name;
        // An imported profile updates the portable per-channel setting too.
        try{await onSenderPreference?.(mode,data.read_sender_name);}catch{
          get("FeedReadSenderStatus").textContent="ไม่สามารถบันทึกค่าอ่านชื่อผู้ส่งได้";
        }
      }
      get("FeedKeepRead").value=String(data.read_history_limit);
      if(mode==="discord_client"){
        get("FeedAppId").value=data.client_id;
        get("FeedRedirect").value=data.redirect_uri;
        get("FeedAppSecret").value=data.client_secret;
      }else if(mode!=="tiktok"&&!browserMode)get("FeedCredential").value=data.credential;
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
      details.textContent=(data.kind==="gift"?"🎁 ":"")+(data.author||"ไม่ระบุชื่อ")+": ";
      const body=document.createElement("span");
      body.textContent=data.kind==="gift"
        ? (data.gift_name||data.text)+" × "+(data.gift_count||1)
        : data.text;
      if(data.level||data.rank||data.badges?.length){
        const meta=document.createElement("small");
        meta.className="source-message-state";
        meta.textContent=[
          data.level?"Lv."+data.level:"",
          data.rank?"No."+data.rank:"",
          ...(Array.isArray(data.badges)?data.badges:[]),
        ].filter(Boolean).join(" · ");
        li.appendChild(meta);
      }
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
    if(socket){
      const former=socket;socket=null;
      former.onmessage=null;former.onopen=null;former.onclose=null;former.onerror=null;
      former.close();
    }
    get("FeedStart").disabled=false;
    get("FeedStop").disabled=true;
    // Preserve the user-selected checkbox across reconnects and tab changes.
    // Suspension still cancels the source worker and drops queued speech.
    onStop?.();
    // Keep displayed messages as a temporary read-only history in this tab,
    // but never continue polling/autoreading after it loses mode ownership.
    message("หยุดรับข้อความแล้วเมื่อเปลี่ยนโหมด · เชื่อมต่อใหม่เพื่อรับข้อความล่าสุด");
  }
  function tikTokURL(value){
    // TikFinity documents this local endpoint. Never allow a user-supplied
    // source profile to create outbound WebSocket connections off the PC.
    const url=value.trim();
    if(!/^ws:\/\/(?:localhost|127\.0\.0\.1):21213\/?$/.test(url))
      throw Error("กรุณาระบุ TikFinity WebSocket บนเครื่องนี้ (ws://localhost:21213/)");
    return url;
  }
  function handleTikTokEvent(raw){
    if(!connected||!guard(mode)||typeof raw!=="string"||raw.length>16384)return;
    let frame;
    try{frame=JSON.parse(raw);}catch{return;}
    if(!["chat","gift"].includes(frame?.event)||!isRecord(frame.data))return;
    const data=frame.data;
    const gift=frame.event==="gift";
    // TikFinity sends gift streak updates; read only the final streak once.
    if(gift && data.repeatEnd===false)return; // Streak is still in progress.
    const giftCount=Number.isSafeInteger(data.repeatCount)
      ?Math.max(1,Math.min(99999,data.repeatCount)):1;
    const incoming=gift?data.giftName:data.comment;
    if(typeof incoming!=="string")return;
    const value=incoming.replace(/[\u0000-\u001f\u007f]/g," ").replace(/\s+/g," ").trim();
    const max=Number(get("FeedMaxChars").value);
    const blocked=get("FeedBlocked").value.split(",").map(w=>w.trim().toLowerCase()).filter(Boolean);
    if(!value||value.length>max||!Number.isInteger(max)
       || /^[/!\\]/.test(value)||/(?:https?:\/\/|www\.)/i.test(value)
       || blocked.some(word=>value.toLowerCase().includes(word))){
      wsRejected++;
      updateTikTokStatus();
      return;
    }
    const rawId=data.messageUuid??data.msgId??data.id;
    let messageId;
    if((typeof rawId==="string"||typeof rawId==="number")
        && /^[a-zA-Z0-9_-]{1,100}$/.test(String(rawId))){
      messageId=(gift?"gift-":"")+String(rawId);
      if(seen.has(messageId)){wsRejected++;updateTikTokStatus();return;}
      seen.add(messageId);
      if(seen.size>256)seen.delete(seen.values().next().value);
    }else messageId="tiktok-"+generation+"-"+(++wsSequence);
    const user=isRecord(data.user)?data.user:{};
    const rawAuthor=[data.nickname,user.nickname,data.uniqueId,user.uniqueId]
      .find(value=>typeof value==="string"&&value.trim())||"";
    const author=rawAuthor.replace(/[\u0000-\u001f\u007f]/g," ").slice(0,80);
    const props={};
    const level=user.level??data.level;
    const rank=user.topGifterRank??data.topGifterRank;
    if((typeof level==="number"||typeof level==="string")
       && /^\d{1,4}$/.test(String(level)))props.level=String(level);
    if((typeof rank==="number"||typeof rank==="string")
       && /^\d{1,4}$/.test(String(rank))&&Number(rank)>0)props.rank=String(rank);
    const badges=Array.isArray(user.badges)?user.badges:[];
    props.badges=badges.slice(0,8).map(b=>typeof b==="string"?b:
      (isRecord(b)?(b.name||b.label||""):""))
      .filter(b=>typeof b==="string"&&b.length<=48);
    const item={message_id:messageId,author,text:value,kind:gift?"gift":"comment",
      ...props,...(gift?{gift_name:value,gift_count:giftCount}:{})};
    wsMessages++;
    const auto=Boolean(get("FeedAuto").checked);
    const entry={...item,state:auto?"queued":"manual"};
    visible.unshift(entry);
    const accepted=onMessage(item,auto);
    if(accepted==="manual")entry.state="manual";
    if(accepted==="skipped"){entry.state="skipped";overflow++;}
    prune();render();
    updateTikTokStatus();
  }
  function updateTikTokStatus(){
    message("TikFinity: connected · รับ "+wsMessages+" · กรอง/ซ้ำ "+wsRejected+
            " · คิวเสียง "+visible.filter(e=>e.state==="queued").length+
            " · ล้นคิว "+overflow);
  }
  function startTikTok(){
    const endpoint=tikTokURL(get("FeedSourceId").value);
    const max=Number(get("FeedMaxChars").value);
    if(get("FeedMaxChars").value.trim()===""||!Number.isInteger(max)||max<20||max>280)
      throw Error("กรุณากำหนดความยาวข้อความสูงสุด 20–280 ก่อนเชื่อมต่อ");
    if(typeof root.WebSocket!=="function")throw Error("Browser ไม่รองรับ WebSocket");
    localSuspend();
    clearMessages();
    wsMessages=0;wsRejected=0;wsSequence=0;seen.clear();
    const ticket=++generation;
    get("FeedStart").disabled=true;
    message("กำลังเชื่อม TikFinity Desktop บนเครื่องนี้...");
    try{
      const client=new root.WebSocket(endpoint);
      socket=client;
      client.onopen=()=>{
        if(ticket!==generation||!guard(mode)){client.close();return;}
        connected=true;
        get("FeedStop").disabled=false;
        updateTikTokStatus();
      };
      client.onmessage=event=>{
        if(ticket!==generation||!guard(mode))return;
        handleTikTokEvent(event.data);
      };
      client.onerror=()=>{
        if(ticket===generation)message("เชื่อม TikFinity ไม่สำเร็จ · ตรวจสอบว่า TikFinity Desktop เปิดและเชื่อม LIVE แล้ว");
      };
      client.onclose=()=>{
        if(ticket!==generation)return;
        localSuspend();
        message("TikFinity WebSocket ตัดการเชื่อมต่อแล้ว · เปิด TikFinity และกดเชื่อมอีกครั้ง");
      };
      return {state:"connecting",mode};
    }catch{
      localSuspend();
      message("เปิด TikFinity WebSocket ไม่สำเร็จ");
      throw Error("เชื่อม TikFinity ไม่สำเร็จ");
    }
  }
  async function start(){
    if(browserMode){
      if(extensionMode)get("FeedPairingCode").value="";
      clearBrowserProgress();
      browserStage("checking_input");
    }
    if(!guard(mode) && (mode==="tiktok" || !onConnect))
      throw Error("กรุณาเปิดโหมดนี้ก่อนเชื่อมต่อ");
    if(mode==="tiktok")return startTikTok();
    const channelId=get("FeedSourceId").value.trim();
    if(browserMode&&!channelId)
      throw Error("กรุณาใส่ "+(mode==="tiktok_browser"?"TikTok Username หรือ URL ของ LIVE":"YouTube Video ID หรือ URL ของ LIVE")+" ก่อนกดเชื่อมต่อ");
    const temporaryCredential=mode==="discord_client" ? {
      client_id:get("FeedAppId").value.trim(),
      client_secret:get("FeedAppSecret").value.trim(),
      redirect_uri:get("FeedRedirect").value.trim(),
    } : browserMode?"":get("FeedCredential").value.trim();
    const blocked=get("FeedBlocked").value.split(",").map(x=>x.trim()).filter(Boolean);
    const maxChars=Number(get("FeedMaxChars").value);
    if(!Number.isInteger(maxChars) || get("FeedMaxChars").value.trim()==="")
      throw Error("กรุณากำหนดความยาวข้อความสูงสุดก่อนเชื่อมต่อ");
    // Switch room without leaving the previous source running if the new
    // room/credentials fail: unsubscribe/stop before trying the new room.
    const previousOwner=connected?credentials(mode):null;
    localSuspend();
    // Explicit Connect will replace this source's ownership token. Do not
    // attempt to stop using a stale token after a restart/another tab claim.
    if(!onConnect && previousOwner){
      try{await api("stop",previousOwner);}
      catch{/* stale owner; backend will reject it safely */}
    }
    clearMessages();
    const ticket=++generation;
    get("FeedStart").disabled=true;
    if(browserMode)browserStage("claiming_owner");
    else message("กำลังตรวจสอบสิทธิ์ช่องทางและเชื่อมต่อ API...");
    try{
      if(onConnect)await onConnect(mode);
      if(ticket!==generation||!guard(mode))return;
      if(browserMode)browserStage("starting_worker");
      const result=await api("start",{
        ...credentials(mode),source_id:channelId,
        credential:temporaryCredential,
        filters:{blocked_words:blocked,max_chars:maxChars},
      });
      if(mode==="discord_client")get("FeedAppSecret").value="";
      else if(!browserMode)get("FeedCredential").value=""; // clear DOM secret as soon as accepted
      if(ticket!==generation||!guard(mode))return;
      connected=true;
      if(extensionMode){
        get("FeedPairingCode").value=result.pairing_code||"";
      }
      get("FeedStop").disabled=false;
      if(browserMode)browserStage(result.connection_phase
        ||(extensionMode?"waiting_extension_pair":"preparing"));
      else message("เริ่มกระบวนการเชื่อมต่อแล้ว · รอตรวจสอบสิทธิ์และสมัครรับข้อความจากผู้ให้บริการ");
      timer=setInterval(()=>poll().catch(error=>message(String(error.message||error))),1200);
      await poll();
      return result;
    }catch(error){
      if(ticket===generation){
        connected=false;
        get("FeedStart").disabled=false;
        if(browserMode)browserStage("error",String(error.message||error));
        else message("เชื่อมต่อไม่สำเร็จ: "+String(error.message||error));
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
          // Retain structured metadata in the visible history as well as
          // in the auto-read callback. Manual selection must preserve gift
          // kind, count, ranks, and badges for the eventual TTS job.
          const entry={...item,state:auto?"queued":"manual"};
          visible.unshift(entry);
          const accepted=onMessage(item,auto);
          if(accepted==="manual")entry.state="manual";
          if(accepted==="skipped"){
            entry.state="skipped";
            overflow++;
          }
          prune();
        }
      }
      render();
      if(browserMode){
        const browserPhase=status.state==="error"?"error"
          :status.state==="retrying"?"retrying"
          :status.state==="ended"?"ended"
          :(status.connection_phase||"preparing");
        const statistics="รับ "+(status.received||0)+
          " · กรอง/ล้นคิว "+(status.discarded||0)+
          " · รออ่าน "+(status.pending||0);
        const note=["error","retrying"].includes(status.state)
          ? " · สาเหตุ: "+(status.info||"ไม่สามารถเชื่อมต่อ Browser")
          : extensionMode && browserPhase==="waiting_extension_pair"
            ? " · คัดลอกรหัสด้านบนไปยังส่วนเสริม Chrome ที่แท็บ TikTok LIVE ที่เปิดเอง"
          : extensionMode && browserPhase==="comments_off"
            ? " · ตัวอ่านจะไม่สร้างข้อความเองและจะตรวจซ้ำเมื่อคอมเมนต์กลับมา"
          : ["comments_off","comments_off_login_prompt","login_prompt"].includes(browserPhase)
            ? " · Chrome ที่โปรแกรมควบคุมอาจได้รับการตอบสนองต่างจาก Chrome ปกติ · โปรแกรมจะตรวจซ้ำเมื่อสถานะเปลี่ยน"
          : browserPhase==="waiting_chat_dom"
            ? " · หากรอนาน ให้ตรวจว่า LIVE เปิด Chat และหน้า Browser โหลดสำเร็จ"
            : "";
        const retry=status.state==="retrying"
          ? " · ลองใหม่ใน "+Math.round(status.next_poll_seconds||0)+" วินาที":"";
        browserStage(browserPhase,statistics+note+retry);
        if(extensionMode){
          const diag=status.dom_diagnostics;
          let desc="DOM: รอส่วนเสริมส่งผลตรวจหน้า LIVE";
          if(diag && typeof diag==="object"){
            desc="DOM: กล่องแชท "+(diag.list_found?"พบ":"ไม่พบ")
              +" · แถวคอมเมนต์ "+(diag.row_candidates||0)
              +" · แยกข้อความได้ "+(diag.parsed_rows||0)
              +" · ข้อความใหม่รอบล่าสุด "+(diag.fresh_rows||0)
              +" · จุดชื่อผู้ส่ง "+(diag.author_nodes||0);
            if(!diag.list_found)desc+=" · หน้า TikTok อาจเปลี่ยนโครงสร้าง หรือยังโหลดแชทไม่เสร็จ";
            else if(diag.row_candidates===0)desc+=" · พบกล่องแชท แต่ยังไม่พบแถวข้อความ";
            else if(diag.parsed_rows===0)desc+=" · พบแถวข้อความ แต่ตัวอ่านยังแยกชื่อผู้ส่ง/เนื้อหาไม่ได้";
          }
          get("FeedDomDiagnostics").textContent=desc;
        }
      }else{
      const phase=status.failed_phase && status.state==="error"
        ? " · ผิดพลาดที่ "+(RPC_PHASE_NAMES[status.failed_phase]||"ขั้นตอน Discord RPC")
        : status.connection_phase ? " · "+(RPC_PHASE_NAMES[status.connection_phase]||"กำลังตรวจสอบสถานะ Discord RPC") : "";
      message(
        (browserMode?"Browser: ":"API: ")+status.state+phase+
        " · รับ "+(status.received||0)+
        " · กรอง/ล้นคิว "+(status.discarded||0)+
        " · รออ่าน "+(status.pending||0)+
        (status.transport==="streamList"?" · YouTube streamList":status.transport==="polling"?" · YouTube REST":status.transport==="browser-dom"?" · Chat DOM": "")+
        " · รอบถัดไป "+Math.round(status.next_poll_seconds||0)+"s"+
        (["error","connecting","retrying"].includes(status.state) ? " · "+status.info : "")
      );
      }
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
    if(mode==="tiktok"){
      localSuspend();
      message("หยุดรับคอมเมนต์ TikTok LIVE แล้ว");
      return;
    }
    if(!guard(mode)){
      localSuspend();
      return;
    }
    // Capture before clearing the UI; client will no longer drain.
    const authorization=credentials(mode);
    localSuspend();
    try { await api("stop",authorization); }
    catch(error){message("หยุดรับใน Browser แล้ว ("+String(error.message||error)+")");}
    if(browserMode)browserStage("stopped");
    if(extensionMode)get("FeedPairingCode").value="";
  }
  get("FeedExport").addEventListener("click",()=>exportSettings());
  get("FeedImport").addEventListener("click",()=>get("FeedImportFile").click());
  get("FeedImportFile").addEventListener("change",async()=>{
    const input=get("FeedImportFile");
    const file=input.files?.[0];
    input.value=""; // re-selecting the same file should still trigger change
    await importSettings(file);
  });
  get("FeedStart").addEventListener("click",()=>{
    start().catch(error=>{
      // Errors before the backend request (such as an empty video URL) must
      // still be visible rather than silently swallowed by the click handler.
      if(browserMode)browserStage("error",String(error.message||error));
    });
  });
  get("FeedStop").addEventListener("click",()=>stop().catch(()=>{}));
  if(extensionMode)get("FeedCopyDiagnostics").addEventListener("click",async()=>{
    const text="TikTok LIVE (Extension)\n"+
      get("FeedStatus").textContent+"\n"+
      get("FeedDomDiagnostics").textContent;
    try{
      await navigator.clipboard.writeText(text);
      message("คัดลอกสถานะการตรวจจับแล้ว · ส่งข้อความที่คัดลอกมาเพื่อวิเคราะห์ได้");
    }catch{
      message("คัดลอกอัตโนมัติไม่ได้ · เลือกข้อความสถานะบนหน้าจอแล้วกด Ctrl+C");
    }
  });
  if(extensionMode)get("FeedCopyCode").addEventListener("click",async()=>{
    const value=get("FeedPairingCode").value;
    if(!value){message("โปรดสร้างรหัสจับคู่ก่อน");return;}
    try{
      await navigator.clipboard.writeText(value);
      message("คัดลอกรหัสจับคู่แล้ว · วางในส่วนเสริมที่แท็บ TikTok LIVE");
    }catch{
      get("FeedPairingCode").focus();
      get("FeedPairingCode").select();
      message("เลือกข้อความรหัสจับคู่ให้แล้ว · กด Ctrl+C เพื่อคัดลอก");
    }
  });
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