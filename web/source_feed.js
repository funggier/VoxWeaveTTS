/* Local Live/Discord read-only connectors.
 * Credentials go via loopback POST to the in-memory Python poller only.
 * Text is rendered with textContent, never HTML. Auto-read defaults on, but
 * never starts a provider connection before the user clicks Connect.
 */
(function(root){
"use strict";
// History/DOM display limits are NOT queue limits. Never drop unread work.
const MAX_RENDERED=120;
const MAX_PASSIVE=25;
const MAX_READ_KEEP=100;
const SETTINGS_FORMAT="voxweavetts.source-settings";
const SETTINGS_VERSION=1;
const MAX_SETTINGS_BYTES=16384;
const SETTINGS_KEYS=new Set(["format","version","mode","source_id",
                             "filters","auto_read","read_sender_name","read_history_limit",
                             "credential","client_id","client_secret","redirect_uri",
                             "random_queue_enabled","random_queue_threshold","random_queue_keep"]);
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
          && value.filters.max_chars>=20 && value.filters.max_chars<=8000)))
    throw Error("ตัวกรองหรือจำนวนอักษรในไฟล์ไม่ถูกต้อง");
  const randomThreshold="random_queue_threshold" in value?value.random_queue_threshold:20;
  const randomKeep="random_queue_keep" in value?value.random_queue_keep:5;
  if(("random_queue_enabled" in value && typeof value.random_queue_enabled!=="boolean")
     || !Number.isInteger(randomThreshold)||randomThreshold<2||randomThreshold>100000
     || !Number.isInteger(randomKeep)||randomKeep<1||randomKeep>=randomThreshold)
    throw Error("ค่าการสุ่มลดคิวไม่ถูกต้อง");
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
  ready:"กำลังรับข้อความ",
  comments_off:"ส่วนเสริมพบ Comments off ในแท็บ TikTok ที่เลือก · ตรวจสอบว่าเปิด LIVE ที่แสดงคอมเมนต์ได้",
  extension_disconnected:"ส่วนเสริมขาดการเชื่อมต่อ · กดสร้างรหัสจับคู่ใหม่ใน VoxWeaveTTS แล้วเชื่อมส่วนเสริมอีกครั้ง",
  retrying:"ช่องทางส่วนเสริมขัดข้อง · ตรวจการเชื่อมต่อกับโปรแกรมในเครื่อง",
  error:"เชื่อมต่อไม่สำเร็จ",
  ended:"หยุดรับข้อความแล้ว",
  stopped:"หยุดรับข้อความแล้ว",
});
const STATE_LABELS={
  queued:"รอประมวลผล",preparing:"กำลังแปล/แยก",prepared:"แปล/แยกแล้ว",rendering:"กำลังสร้างเสียง",ready:"เสียงพร้อมรอเล่น",reading:"กำลังอ่าน",read:"อ่านแล้ว",
  skipped:"ข้ามการอ่าน",random_removed:"สุ่มลบจากคิว",manual:"เลือกอ่านเอง",
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
  ready:"กำลังรับข้อความ",
  comments_off:"TikTok ใน Browser นี้แสดง Comments off · ไม่ได้แปลว่าเจ้าของไลฟ์ปิดคอมเมนต์ ตรวจสอบสิทธิ์การเข้าถึงในหน้าต่างนี้",
  comments_off_login_prompt:"TikTok ใน Browser ที่โปรแกรมควบคุมแสดง Comments off และ Log in · แต่ LIVE อาจมีคอมเมนต์ปกติใน Chrome ธรรมดา อย่าลองเข้าสู่ระบบซ้ำหากระบบจำกัดจำนวนครั้ง",
  login_prompt:"TikTok แสดง Log in และยังไม่พบ DOM แชท · ไม่ได้แปลว่าต้องเข้าสู่ระบบจึงจะดูคอมเมนต์ได้",
  login_rate_limited:"TikTok จำกัดจำนวนครั้งในการเข้าสู่ระบบ · หยุดลองเข้าสู่ระบบหรือเชื่อมต่อ Browser ซ้ำ และใช้ TikTok LIVE (TikFinity) แทนชั่วคราว",
  retrying:"การเชื่อมต่อขัดข้อง · กำลังรอลองเชื่อมต่อใหม่",
  error:"เชื่อมต่อไม่สำเร็จ",
  ended:"ไลฟ์สิ้นสุดหรือหน้าต่าง Chat ปิดแล้ว",
  stopped:"หยุดรับข้อความจาก Browser แล้ว",
});
// One SSE socket for ALL connected source modes. Browsers typically allow only
// a few simultaneous HTTP/1.1 connections per origin; a separate EventSource
// for every channel could exhaust them and block the actual POST /drain.
let sharedSourceStream=null;
const sourceListeners=new Map();
function subscribeSource(mode,wake){
  if(typeof root.EventSource!=="function")return null;
  sourceListeners.set(mode,{wake,revision:null,lastWake:0});
  if(!sharedSourceStream){
    try{
      const stream=new root.EventSource("/v1/sources/stream?mode=all");
      sharedSourceStream=stream;
      stream.addEventListener("source",event=>{
        let data;
        try{data=JSON.parse(event.data);}catch{return;}
        if(data?.mode!=="all"||!Array.isArray(data.sources)||data.sources.length>5)return;
        const now=Date.now();
        for(const signal of data.sources){
          const listener=sourceListeners.get(signal?.mode);
          if(!listener||!Number.isInteger(signal?.revision))continue;
          // Ignore changes to other modes; still retry a possibly failed
          // drain on the server's periodic (~6s) snapshot.
          if(listener.revision!==signal.revision||now-listener.lastWake>=5000){
            listener.revision=signal.revision;
            listener.lastWake=now;
            listener.wake();
          }
        }
      });
    }catch{
      sourceListeners.delete(mode);
      sharedSourceStream=null;
      return null;
    }
  }
  const owned=sharedSourceStream;
  return ()=>{
    sourceListeners.delete(mode);
    if(!sourceListeners.size&&sharedSourceStream===owned){
      sharedSourceStream.close();
      sharedSourceStream=null;
    }
  };
}

function attach({mode,el,credentials,guard,onMessage,onPick,onStop,onReset,onSenderPreference,onConnect,onStatus}){
  if(!["live","youtube_browser","tiktok_browser","discord","discord_client","tiktok"].includes(mode))throw Error("invalid source mode");
  const prefix=mode==="discord_client"?"discordClient":mode==="youtube_browser"?"youtubeBrowser":mode==="tiktok_browser"?"tiktokBrowser":mode;
  const get=id=>el(prefix+id);
  let timer=null, generation=0, connected=false, inFlight=false;
  let resetEpoch=0, resetting=false;
  let streamSubscription=null, pendingWake=false;
  let socket=null, wsMessages=0, wsRejected=0, wsSequence=0;
  const seen=new Set();
  let visible=[], overflow=0, randomRemoved=0;
  let spokenHistory=[], modelHistory=[], currentSpeech=null;
  let pipelineQueues=[];
  const pendingModelInputs=new Map();
  const browserMode=mode==="youtube_browser"||mode==="tiktok_browser";
  const extensionMode=mode==="tiktok_browser";
  const platform=mode==="tiktok_browser"?"TikTok":"YouTube";
  let browserStageName="",browserStageLog=[];
  // The speech footer receives a structured connection snapshot. Keep the
  // compact FeedStatus for connector instructions/errors unchanged.
  function reportSource(state,more={}){
    onStatus?.({state,connected,...more});
  }
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
    // Operational counters already live in FeedQueueStatus. Avoid repeating
    // provider/Extension labels and diagnostics in the ready status line.
    message(phase==="ready"?"กำลังรับข้อความ":desc+(extra?" · "+extra:""));
    reportSource(phase==="error"?"error":phase==="retrying"?"retrying"
      :["stopped","ended","extension_disconnected"].includes(phase)?phase
      :phase==="ready"?"running":"connecting",{phase});
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
      random_queue_enabled:Boolean(get("FeedRandomEnable")?.checked),
      random_queue_threshold:String(get("FeedRandomThreshold")?.value??"").trim()===""
        ?20:Number(get("FeedRandomThreshold").value),
      random_queue_keep:String(get("FeedRandomKeep")?.value??"").trim()===""
        ?5:Number(get("FeedRandomKeep").value),
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
      get("FeedRandomEnable").checked=data.random_queue_enabled===true;
      get("FeedRandomThreshold").value=String(data.random_queue_threshold??20);
      get("FeedRandomKeep").value=String(data.random_queue_keep??5);
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
      if(["queued","preparing","prepared","rendering","ready","reading"].includes(entry.state))return true;
      if(entry.state==="read")return ++read<=keep;
      return ++passive<=MAX_PASSIVE;
    });
  }
  function renderSummary(){
    const queued=visible.filter(x=>x.state==="queued").length;
    const reading=visible.filter(x=>["preparing","prepared","rendering","ready","reading"].includes(x.state)).length;
    const read=visible.filter(x=>x.state==="read").length;
    get("FeedQueueStatus").textContent=
      "คิวรออ่าน "+queued+
      " · กำลังเตรียม/อ่าน "+reading+
      " · อ่านแล้วที่เก็บ "+read+"/"+readLimit()+
      " · ข้าม/กรอง "+overflow+
      " · สุ่มลบคิว "+randomRemoved;
  }
  function clearMessages(){
    visible=[];overflow=0;randomRemoved=0;
    spokenHistory=[];modelHistory=[];currentSpeech=null;
    pendingModelInputs.clear();
    setPipelineQueues([]);
    renderSpokenHistory();renderModelHistory();
    if(get("FeedCurrentStatus"))get("FeedCurrentStatus").textContent="ยังไม่มีงานสร้างเสียง";
    if(get("FeedCurrentText"))get("FeedCurrentText").textContent="";
    get("FeedItems").replaceChildren();
    renderSummary();
  }
  function render(){
    const area=get("FeedItems");
    area.replaceChildren();
    // Keep the entire pending queue in memory, but draw a small window.
    // Otherwise a slow TTS model can create thousands of DOM nodes per tick.
    const shown=visible.slice(0,MAX_RENDERED);
    for(const active of visible.slice(MAX_RENDERED)){
      if(["preparing","prepared","rendering","ready","reading"].includes(active.state))shown.push(active);
    }
    for(const data of shown){
      const li=document.createElement("li");
      li.className="source-message";
      const details=document.createElement("span");
      details.className="source-author";
      details.textContent=(data.author||"ไม่ระบุชื่อ")+": ";
      const body=document.createElement("span");
      body.textContent=data.text;
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
  function renderSpokenHistory(){
    const area=get("FeedReadItems");
    if(!area)return;
    area.replaceChildren();
    for(const entry of spokenHistory){
      const li=document.createElement("li");
      li.className="source-message";
      li.textContent=(entry.author?entry.author+": ":"")+entry.text;
      area.appendChild(li);
    }
  }
  function trimSpokenHistory(){
    spokenHistory=spokenHistory.slice(0,readLimit());
    renderSpokenHistory();
  }
  function renderModelHistory(){
    const area=get("FeedTtsReadItems");
    if(!area)return;
    area.replaceChildren();
    for(const record of modelHistory){
      const li=document.createElement("li");
      li.className="source-message";
      if(li.style){
        li.style.whiteSpace="pre-wrap";
        li.style.overflowWrap="anywhere";
      }
      // One top-level history item per COMPLETED speech job; retain all
      // individual model calls and mixed-language routes within it.
      if(record.items.length){
        record.items.forEach(chunk=>{
          const line=document.createElement("div");
          const language=chunk.language?"["+chunk.language+" · ":"[";
          const heading=document.createElement("small");
          heading.className="source-message-state";
          const result=chunk.success===false?"ข้าม (สร้างเสียงล้มเหลว) · "
            :chunk.success===true?"สำเร็จ · ":"";
          heading.textContent=language+result+chunk.engine_id+" / "+chunk.voice_id+"] ";
          const text=document.createElement("span");
          text.textContent=chunk.text;
          line.append(heading,text);
          li.appendChild(line);
        });
      }else{
        // Never substitute unprocessed chat text for missing TTS evidence.
        li.textContent="ไม่พบข้อมูลข้อความหลังแปลจากโมเดล (ไม่ได้แสดงข้อความต้นทางแทน)";
      }
      area.appendChild(li);
    }
  }
  function trimModelHistory(){
    modelHistory=modelHistory.slice(0,readLimit());
    renderModelHistory();
  }
  function setSpeechModelInputs(messageId, modelInputs){
    if(messageId==null)return;
    const id=String(messageId);
    // Keep only metadata from a current, currently visible source item.
    if(!visible.some(entry=>String(entry.message_id)===id))return;
    if(!Array.isArray(modelInputs)||modelInputs.length>1024)return;
    const clean=[];
    for(const part of modelInputs){
      if(!part || typeof part!=="object"
         || typeof part.text!=="string" || part.text.length>12000
         || typeof part.engine_id!=="string" || part.engine_id.length>80
         || typeof part.voice_id!=="string" || part.voice_id.length>80
         || typeof part.language!=="string" || part.language.length>16)
        return;
      clean.push({text:part.text,engine_id:part.engine_id,
                  voice_id:part.voice_id,language:part.language,
                  success:typeof part.success==="boolean"?part.success:null});
    }
    pendingModelInputs.set(id,clean);
  }
  // This display is independent of the original incoming-chat list. The
  // text is the actual composed speech request (including sender header),
  // never just whatever happens to be in the latest chat input at this time.
  function setSpeechDiagnostic(record){
    if(!record||typeof record!=="object")return;
    if(!["preparing","ready","reading","failed","skipped","read"].includes(record.stage))return;
    const text=String(record.text||"").slice(0,9000);
    const error=String(record.error||"").slice(0,240);
    currentSpeech={message_id:record.message_id==null?null:String(record.message_id),
                   text,stage:record.stage,error};
    // A retried speech job must not reuse the model-input data from an
    // earlier failed attempt that may have used a different translation.
    if(record.stage==="preparing" && record.message_id!=null)
      pendingModelInputs.delete(String(record.message_id));
    const status=get("FeedCurrentStatus");
    const body=get("FeedCurrentText");
    if(status){
      const labels={preparing:"กำลังแปลงข้อความเป็นเสียง",ready:"สร้างเสียงเสร็จแล้ว",
                    reading:"กำลังอ่านออกเสียง",read:"อ่านสำเร็จแล้ว",
                    skipped:"ข้ามข้อความ",failed:"สร้างเสียง/เล่นเสียงผิดพลาด"};
      status.textContent=(labels[record.stage]||record.stage)+(error?" · "+error:"");
    }
    if(body)body.textContent=text;
  }
  // Explicit local pipeline view. Never show raw incoming chat as the
  // *translated* text: that field is populated only by private TTS inspection.
  function setPipelineQueues(snapshot){
    if(!Array.isArray(snapshot))return;
    pipelineQueues=snapshot.slice(0,5).map(item=>({
      stage:String(item.stage||"").slice(0,20),
      author:String(item.author||"").slice(0,80),
      inputs:Array.isArray(item.inputs)?item.inputs.slice(0,96).map(x=>({
        language:String(x.language||"").slice(0,16),
        text:String(x.text||"").slice(0,8000),
        engine_id:String(x.engine_id||"").slice(0,100),
      })):[],
    }));
    const prepared=get("FeedPreparedItems"),ready=get("FeedReadyAudioItems");
    if(!prepared||!ready)return;
    prepared.replaceChildren();ready.replaceChildren();
    let pending=0,audio=0;
    for(const item of pipelineQueues){
      if(item.stage==="reading")continue;
      const produced=item.stage==="ready";
      const area=produced?ready:prepared;
      const li=document.createElement("li");
      li.className="source-message";
      const header=document.createElement("small");
      header.className="source-message-state";
      header.textContent=(item.author?item.author+" · ":"")+
        (produced?"เสียงพร้อมรอเล่น":item.stage==="preparing"
          ?"กำลังแปล/แยกข้อความ":item.stage==="rendering"
          ?"กำลังสร้างเสียง":"รอสร้างเสียง");
      li.appendChild(header);
      if(item.inputs.length){
        for(const chunk of item.inputs){
          const line=document.createElement("div");
          const tag=document.createElement("small");
          tag.className="source-message-state";
          tag.textContent="["+(chunk.language||"default")+" · "+chunk.engine_id+"] ";
          const text=document.createElement("span");
          text.textContent=chunk.text;
          line.append(tag,text);li.appendChild(line);
        }
      }else{
        const hint=document.createElement("span");
        hint.textContent="รอผลข้อความหลังแปลและแยกภาษา…";
        li.appendChild(hint);
      }
      area.appendChild(li);
      if(produced)audio++;else pending++;
    }
    get("FeedPreparedStatus").textContent="รอสร้างเสียง "+pending+" ข้อความ";
    get("FeedReadyAudioStatus").textContent="มีเสียงพร้อมรออ่าน "+audio+" ข้อความ";
  }
  function setMessageState(messageId,state){
    if(!Object.prototype.hasOwnProperty.call(STATE_LABELS,state))return;
    const entry=visible.find(x=>String(x.message_id)===String(messageId));
    if(!entry)return; // source session already switched or was cleared
    if(state==="random_removed"&&entry.state!=="random_removed")randomRemoved++;
    if(state==="skipped"||state==="random_removed")
      pendingModelInputs.delete(String(messageId));
    if(state==="read"&&entry.state!=="read"){
      const spoken=currentSpeech?.message_id===String(messageId)
        ?currentSpeech.text:entry.text;
      spokenHistory.unshift({text:spoken,author:entry.author||""});
      const modelItems=pendingModelInputs.get(String(messageId))||[];
      pendingModelInputs.delete(String(messageId));
      modelHistory.unshift({message_id:String(messageId),items:modelItems});
      trimSpokenHistory();
      trimModelHistory();
      if(currentSpeech?.message_id===String(messageId))
        setSpeechDiagnostic({...currentSpeech,stage:"read",error:currentSpeech.error||""});
    }
    if((state==="preparing"||state==="reading")
       && currentSpeech?.message_id===String(messageId)){
      setSpeechDiagnostic({...currentSpeech,stage:state,error:""});
    }
    entry.state=state;
    prune();
    render();
  }
  async function api(operation,body){
    const response=await fetch("/v1/sources/"+operation,{
      method:"POST",
      headers:{"Content-Type":"application/json","X-VoxWeaveTTS-Intent":{
        start:"start-live-source",stop:"stop-live-source",
        drain:"drain-live-source",reset:"reset-live-source-queue",
      }[operation]},
      body:JSON.stringify(body),
    });
    const result=await response.json();
    if(!response.ok)throw Error(result.error||"source operation failed");
    return result;
  }
  function wake(){
    if(!connected||!guard(mode))return;
    // A push arriving during a pending POST /drain must not be lost.
    if(inFlight){pendingWake=true;return;}
    poll().catch(error=>message(String(error.message||error)));
  }
  function openSourceStream(ticket){
    streamSubscription=subscribeSource(mode,()=>{
      if(ticket===generation&&connected&&guard(mode))wake();
    });
    // The single EventSource automatically reconnects and receives
    // source snapshots for every connected mode without exhausting sockets.
  }
  function closeSourceStream(){
    streamSubscription?.();
    streamSubscription=null;
  }
  function localSuspend(){
    generation++;
    resetEpoch++;
    resetting=false;
    connected=false;
    inFlight=false;
    pendingWake=false;
    closeSourceStream();
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
    reportSource("stopped",{phase:"stopped",pending:0});
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
    // Ignore all TikFinity non-chat events, including gift, follow and share.
    if(frame?.event!=="chat"||!isRecord(frame.data))return;
    const data=frame.data;
    const incoming=data.comment;
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
      messageId=String(rawId);
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
    const item={message_id:messageId,author,text:value,kind:"comment",...props};
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
    reportSource(connected?"running":"stopped",{
      phase:connected?"ready":"stopped",received:wsMessages,
      discarded:wsRejected,pending:0,
    });
    message("TikFinity: connected · รับ "+wsMessages+" · กรอง/ซ้ำ "+wsRejected+
            " · คิวเสียง "+visible.filter(e=>e.state==="queued").length+
            " · ล้นคิว "+overflow);
  }
  function startTikTok(){
    const endpoint=tikTokURL(get("FeedSourceId").value);
    const max=Number(get("FeedMaxChars").value);
    if(get("FeedMaxChars").value.trim()===""||!Number.isInteger(max)||max<20||max>8000)
      throw Error("กรุณากำหนดความยาวข้อความสูงสุด 20–8,000 ก่อนเชื่อมต่อ");
    if(typeof root.WebSocket!=="function")throw Error("Browser ไม่รองรับ WebSocket");
    localSuspend();
    clearMessages();
    reportSource("connecting",{phase:"starting_worker",received:0,discarded:0,pending:0});
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
      // EventSource delivers backend wake-ups while ordinary timers in a
      // hidden tab are throttled. Keep polling only as a disconnected fallback.
      openSourceStream(ticket);
      timer=setInterval(()=>{
        if(!streamSubscription||!sharedSourceStream||sharedSourceStream.readyState!==1)wake();
      },1200);
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
    if(!connected||!guard(mode))return;
    if(inFlight){pendingWake=true;return;}
    const ticket=generation;
    const drainEpoch=resetEpoch;
    inFlight=true;
    try{
      const result=await api("drain",{...credentials(mode),limit:10});
      if(ticket!==generation||drainEpoch!==resetEpoch||resetting||!guard(mode))return;
      const status=result.status;
      reportSource(status.state||"running",{
        phase:status.connection_phase||status.state||"",
        received:status.received,discarded:status.discarded,
        pending:status.pending,
      });
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
        }
      }
      prune();
      render();
      // A source may be producing faster than a single 10-message drain.
      // Continue immediately without waiting for a throttled timer or SSE.
      if(status.pending>0)pendingWake=true;
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
        const ytMode=!extensionMode && status.chat_mode
          ? " · โหมดแชท "+({live:"Live chat ✓",top:"Top chat (ยังกรองข้อความ)",
              unknown:"ยืนยันไม่ได้"}[status.chat_mode]||"ไม่ทราบ")
          : "";
        const ytVisibility=!extensionMode && status.page_visibility
          ? " · หน้าต่าง "+({visible:"แสดงอยู่",hidden:"เบื้องหลัง",prerender:"กำลังเริ่มแสดง"}[status.page_visibility]||"ไม่ทราบ")
          : "";
        const delivery=streamSubscription&&sharedSourceStream?.readyState===1
          ? " · รับข้อความแบบ Server Push"
          : " · ใช้ Polling สำรอง (Push กำลังเชื่อมต่อ)";
        browserStage(browserPhase,statistics+note+retry+ytMode+ytVisibility+delivery);
        if(extensionMode){
          const diag=status.dom_diagnostics;
          let desc="DOM: รอส่วนเสริมส่งผลตรวจหน้า LIVE";
          if(diag && typeof diag==="object"){
            desc="DOM: กล่องแชท "+(diag.list_found?"พบ":"ไม่พบ")
              +" · แถวคอมเมนต์ "+(diag.row_candidates||0)
              +" · แยกข้อความได้ "+(diag.parsed_rows||0)
              +" · ข้อความใหม่รอบล่าสุด "+(diag.fresh_rows||0)
              +" · จุดชื่อผู้ส่ง "+(diag.author_nodes||0);
            if(typeof diag.tab_visible==="boolean"){
              desc+=" · แท็บ "+(diag.tab_visible?"แสดงอยู่":"อยู่เบื้องหลัง");
              desc+=" · โฟกัส "+(diag.tab_focused?"อยู่ในแท็บ":"อยู่นอกแท็บ");
              if(Number.isInteger(diag.chat_change_age_seconds))
                desc+=" · DOM แชทไม่เปลี่ยนมา "+diag.chat_change_age_seconds+" วินาที";
            }
            if(!diag.list_found)desc+=" · หน้า TikTok อาจเปลี่ยนโครงสร้าง หรือยังโหลดแชทไม่เสร็จ";
            else if(diag.row_candidates===0)desc+=" · พบกล่องแชท แต่ยังไม่พบแถวข้อความ";
            else if(diag.parsed_rows===0)desc+=" · พบแถวข้อความ แต่ตัวอ่านยังแยกชื่อผู้ส่ง/เนื้อหาไม่ได้";
            if(diag.tab_visible===false &&
               Number.isInteger(diag.chat_change_age_seconds) &&
               diag.chat_change_age_seconds>=30)
              desc+=" · TikTok หรือ Chrome อาจพักการอัปเดตแชทเบื้องหลัง";
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
      if((status.state==="ended"||status.state==="error") && !(status.pending>0)){
        connected=false;
        if(timer!==null){clearInterval(timer);timer=null;}
        closeSourceStream();
        pendingWake=false;
        get("FeedStart").disabled=false;
        get("FeedStop").disabled=true;
        // A source that ends or fails must not cancel accepted queued speech.
        // Users can explicitly reset the queue or press Stop Audio.
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
    }finally{
      if(ticket===generation){
        inFlight=false;
        if(pendingWake && connected){
          pendingWake=false;
          // Microtask/fetch progression is not a browser background timer.
          Promise.resolve().then(()=>wake());
        }
      }
    }
  }
  async function resetPending(){
    if(resetting)return;
    resetting=true;
    resetEpoch++; // Ignore any pre-reset /drain response still in flight.
    const ticket=generation;
    const keep=onReset?.()||{};
    const activeId=keep.active_message_id==null
      ?null:String(keep.active_message_id);
    const cleared=Number.isInteger(keep.cleared)?keep.cleared:0;
    const resetButton=get("FeedReset");
    resetButton.disabled=true;
    // Preserve the single active translation/render/playback job and its
    // displayed row. Remove queued and historical rows, not the current job.
    visible=visible.filter(item=>activeId!==null&&
      String(item.message_id)===activeId);
    overflow=0;
    randomRemoved=0;
    render();
    try{
      let backend=0;
      if(mode!=="tiktok"&&connected&&guard(mode)){
        const result=await api("reset",credentials(mode));
        backend=Number.isInteger(result.cleared)?result.cleared:0;
      }
      if(ticket===generation){
        message("รีเซ็ตคิวแล้ว · ล้างข้อความที่รอ "+(cleared+backend)+
          " รายการ · "+(activeId!==null
            ?"ข้อความที่กำลังแปล/สร้างเสียง/อ่าน จะทำต่อจนจบ"
            :"พร้อมรับข้อความใหม่")+(connected?" · ยังเชื่อมต่อ LIVE อยู่":" · ยังไม่ได้เชื่อมต่อ LIVE"));
      }
    }catch(error){
      if(ticket===generation)
        message("ล้างคิวใน Browser แล้ว แต่ล้างคิวต้นทางไม่สำเร็จ: "+
          String(error.message||error));
    }finally{
      if(ticket===generation){
        resetting=false;
        resetButton.disabled=false;
        if(connected&&guard(mode))wake();
      }
    }
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
  get("FeedReset").addEventListener("click",()=>resetPending());
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
  // React immediately when a hidden tab becomes visible again. This also
  // catches up if a browser temporarily suspended the entire page runtime.
  root.addEventListener?.("focus",wake);
  root.addEventListener?.("pageshow",wake);
  document.addEventListener?.("visibilitychange",()=>{
    if(!document.hidden)wake();
  });
  get("FeedStop").disabled=true;
  get("FeedKeepRead").addEventListener("input",()=>{
    prune();render();trimSpokenHistory();trimModelHistory();
  });
  root.VoxSourceQueueUI?.attach(mode,el);
  renderSummary();
  return {start,stop,poll,resetPending,suspend:localSuspend,setMessageState,setPipelineQueues,setSpeechDiagnostic,setSpeechModelInputs,exportSettings,importSettings,
          get connected(){return connected;},get visible(){return visible.slice();}};
}
root.VoxSourceFeed={attach};
if(typeof module!=="undefined"&&module.exports)module.exports={attach};
})(typeof window==="undefined"?globalThis:window);