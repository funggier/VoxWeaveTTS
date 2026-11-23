/* Read-only, server-authoritative Computer Live dashboard.
 * One existing /v1/runtime/state poll is the wake-up source. No new timer,
 * EventSource, drain, synthesizer, or audio player is created by this module.
 * Private message/model text is obtained only by an intent-gated same-origin POST.
 */
(function(root){
"use strict";
const MODES=Object.freeze({
  live:"live",
  youtube_browser:"youtubeBrowser",
  tiktok_browser:"tiktokBrowser",
  tiktok:"tiktok",
  discord:"discord",
  discord_client:"discordClient",
  stt_api:"sttApi"
});
const labels=Object.freeze({
  queued:"รอเข้า TTS",preparing:"กำลังเตรียมข้อความ/แปล",
  prepared:"แปล/แยกแล้ว · รอสร้างเสียง",rendering:"กำลังสร้างเสียง",
  ready:"มีไฟล์เสียง · รอเล่น",reading:"กำลังเล่นเสียงจาก Core",
  read:"อ่านจบแล้ว",failed:"ผิดพลาด",skipped:"ข้ามข้อความ",
  stopped:"หยุดก่อนอ่านจบ",cleared:"ล้างออกจากคิวก่อนประมวลผล"
});
let feeds={},enabled=false,loadedCursor=null,inFlight=false,pendingCursor=null;
let lastError="",lastUpdate=0,lastFailureAt=0;
const node=id=>root.document?.getElementById(id);
const safe=v=>String(v??"");
const count=v=>Number.isFinite(Number(v))?Math.max(0,Number(v)):0;
const headline=v=>(labels[v]||safe(v)||"รอประมวลผล");
function row(text,parent){
  const li=root.document.createElement("li");
  li.className="source-message";
  li.textContent=safe(text);
  parent.appendChild(li);
  return li;
}
function fillList(id,entries,empty){
  const parent=node(id);
  if(!parent)return;
  parent.replaceChildren();
  for(const text of entries)row(text,parent);
  if(!entries.length && empty)row(empty,parent);
}
function jobLines(job){
  const inputs=Array.isArray(job?.inputs)?job.inputs:[];
  if(!inputs.length)
    return [headline(job?.state)+" · "+(job?.state==="preparing"
      ?"รอผลการแปลและการแยกภาษา"
      :"ยังไม่มีหลักฐานข้อความจริงที่ส่งเข้าโมเดล")+
      (job?.error?" · "+safe(job.error):"")];
  return inputs.map(part=>
    "["+safe(part.language||"default")+" · "+
      safe(part.engine_id||"-")+" / "+safe(part.voice_id||"-")+"] "+
      safe(part.text)+(part.truncated?" (แสดงเพียงบางส่วน)":"")
  );
}
function renderSource(mode,prefix,source,server){
  if(!source)return;
  const counts=source.counts||{},state=source.status||{};
  const readLimitElement=node(prefix+"FeedKeepRead");
  const readLimitValue=Number(readLimitElement?.value);
  const readLimit=Number.isInteger(readLimitValue)
    ?Math.max(0,Math.min(100,readLimitValue)):20;
  const seen=source.recent||[];
  const stageList=source.pipeline||[];
  const waiting=stageList.filter(x=>
    ["preparing","prepared","rendering","queued"].includes(x.state));
  const ready=stageList.filter(x=>x.state==="ready");
  const active=stageList.find(x=>x.state==="reading")
    ||stageList.find(x=>x.state==="rendering")
    ||stageList.find(x=>x.state==="preparing")
    ||stageList.find(x=>x.state==="prepared")
    ||stageList.find(x=>x.state==="ready")
    ||stageList.find(x=>x.state==="queued");
  const failed=seen.find(x=>x.state==="failed");
  const live=["running","connecting","retrying"].includes(state.state);
  const startButton=node(prefix+"FeedStart");
  if(startButton)startButton.disabled=live;
  const autoRead=node(prefix+"FeedAuto");
  if(autoRead){
    if(live&&typeof state.runtime_auto_read==="boolean"&&
       root.document?.activeElement!==autoRead)
      autoRead.checked=state.runtime_auto_read;
    // Keep offline choice editable: it is applied on the next explicit Connect.
    // A connected source is synchronized and updated via Core option API.
    autoRead.disabled=false;
  }
  // Connected inputs belong to the Core; keep edit drafts intact while the
  // user focuses a field, and do not bring credentials into the Web UI.
  if(live&&typeof state.source_id==="string"){
    let target=state.source_id;
    if(mode==="stt_api"){
      try{
        const url=new URL(target);
        const port=node(prefix+"FeedPort"),secure=node(prefix+"FeedSecure");
        target=url.hostname;
        if(port&&root.document?.activeElement!==port)
          port.value=url.port|| (url.protocol==="https:"?"443":"80");
        if(secure&&root.document?.activeElement!==secure)
          secure.checked=url.protocol==="https:";
      }catch{ /* display state below still reflects the Core */ }
    }
    const sourceId=node(prefix+"FeedSourceId");
    if(sourceId&&root.document?.activeElement!==sourceId)sourceId.value=target;
  }
  const resetButton=node(prefix+"FeedReset");
  if(resetButton)resetButton.disabled=!count(source.source_pending)&&!count(source.buffered_count);
  const stopButton=node(prefix+"FeedStop");
  if(stopButton){
    const live=["running","connecting","retrying"].includes(state.state);
    stopButton.disabled=!live&&!source.buffered_count&&
      !["preparing","prepared","queued","rendering","ready","reading"]
        .some(stage=>count(counts[stage])>0);
  }
  const sourceStatus=node(prefix+"FeedStatus");
  if(sourceStatus){
    sourceStatus.textContent="Core Server · "+
      (server?.playback_paused?"คิวเสียงถูกพัก · ":"")+
      safe(state.state||"idle")+
      " · รับแล้ว "+count(state.received)+" · กรอง "+count(state.discarded)+
      " · รอรับจากต้นทาง "+count(source.source_pending)+
      (live?" · อ่านอัตโนมัติ "+(state.runtime_auto_read?"เปิด":"ปิด"):"")+
      (state.info&&state.state==="error"?" · "+safe(state.info):"");
  }
  const messageStatus=node(prefix+"FeedQueueStatus");
  if(messageStatus){
    messageStatus.textContent="Core Server · คิวรออ่าน "+count(counts.queued)+
      " · กำลังแปล/เตรียม "+(count(counts.preparing)+count(counts.prepared))+
      " · สร้างเสียง "+count(counts.rendering)+
      " · เสียงรอเล่น "+count(counts.ready)+
      " · อ่านจบ "+count(counts.read)+"/"+readLimit+
      " (ประวัติใน RAM ของ Core) · ผิดพลาด "+count(counts.failed);
  }
  const incoming=[];
  for(const item of (source.source_pending_items||[])){
    incoming.push("[รอรับจากต้นทาง] "+
      (item.author?safe(item.author)+": ":"")+safe(item.text));
  }
  const bufferedIds=new Set((source.buffered||[]).map(x=>safe(x.message_id)));
  for(const item of seen.slice(0,80)){
    incoming.push("["+headline(item.state)+"] "+
      (item.author?safe(item.author)+": ":"")+safe(item.text));
  }
  fillList(prefix+"FeedItems",incoming,
    "ยังไม่มีข้อความที่ Core รับไว้ (ข้อมูลที่แสดงเป็นประวัติชั่วคราวใน Server)");
  fillList(prefix+"FeedPreparedItems",waiting.flatMap(job=>
    jobLines(job).map(line=>headline(job.state)+" · "+line)),
    "ไม่มีข้อความกำลังแปลหรือรอสร้างเสียงใน Core");
  fillList(prefix+"FeedReadyAudioItems",ready.flatMap(job=>
    jobLines(job).map(line=>"พร้อมเล่น · "+line)),
    "ไม่มีเสียงพร้อมเล่นที่รอคิวใน Core");
  const preparedStatus=node(prefix+"FeedPreparedStatus");
  if(preparedStatus)preparedStatus.textContent=
    "Core Server · เตรียม/แปล "+count(counts.preparing)+
    " · แปลแล้ว "+count(counts.prepared)+
    " · กำลังสร้างเสียง "+count(counts.rendering);
  const readyStatus=node(prefix+"FeedReadyAudioStatus");
  if(readyStatus)readyStatus.textContent="Core Server · เสียงรอเล่น "+
    count(counts.ready)+" ข้อความ · กำลังเล่น "+count(counts.reading);
  const currentStatus=node(prefix+"FeedCurrentStatus");
  if(currentStatus){
    currentStatus.textContent=server?.playback_paused
      ?"Core Server · หยุดเสียงแล้ว · พักคิวจนกดอ่านอัตโนมัติต่อ"
      :active
      ?"Core Server · "+headline(active.state)
      :failed?"Core Server · ข้อผิดพลาดล่าสุด: "+safe(failed.error||"การสร้างเสียงผิดพลาด")
      :"Core Server · ยังไม่มีงานสร้างเสียงที่กำลังดำเนินการ";
  }
  const currentText=node(prefix+"FeedCurrentText");
  if(currentText){
    currentText.textContent=active?
      (active.inputs?.length?jobLines(active).join("\n")
       :active.state==="preparing"
         ?"ต้นฉบับที่ Core กำลังเตรียม/แปล (ยังไม่ใช่ผลแปล): "+
           (active.author?safe(active.author)+": ":"")+safe(active.text)
         :"Core ยังไม่ยืนยันข้อความที่จะส่งเข้าโมเดล · "+headline(active.state)):
      "";
  }
  const finished=(source.read_history||[]).slice(0,readLimit);
  fillList(prefix+"FeedReadItems",finished.map(item=>
    (item.author?safe(item.author)+": ":"")+safe(item.text)),
    "ยังไม่มีข้อความที่ Core ยืนยันว่าเล่นเสียงจบ");
  const history=(source.model_history||[]).slice(0,readLimit);
  fillList(prefix+"FeedTtsReadItems",history.map(item=>{
    const inputs=Array.isArray(item.inputs)?item.inputs:[];
    return inputs.length?jobLines(item).join("\n"):
      "ไม่พบหลักฐานข้อความที่ส่งเข้าโมเดลของงานนี้";
  }),"ยังไม่มีประวัติข้อความที่ส่งเข้าโมเดลและอ่านจบ");
}
function renderDashboard(payload){
  if(!enabled||payload?.mode!=="computer")return;
  for(const [mode,prefix] of Object.entries(MODES))
    renderSource(mode,prefix,payload.sources?.[mode],payload);
  // TikFinity now connects to localhost:21213 from Core in computer mode.
  // The Browser WebSocket is retained only for explicit Browser fallback.
  lastUpdate=Date.now();
}
async function inspect(cursor){
  if(!enabled||inFlight)return;
  inFlight=true;
  try{
    const response=await root.fetch("/v1/runtime/dashboard",{
      method:"POST",cache:"no-store",
      headers:{"Content-Type":"application/json",
               "X-VoxWeaveTTS-Intent":"inspect-runtime-dashboard"},
      body:"{}"
    });
    if(!response.ok)throw Error("Dashboard HTTP "+response.status);
    const data=await response.json();
    if(!enabled)return;
    if(data.mode==="computer"){
      renderDashboard(data);
      loadedCursor=cursor;
      lastError="";
      lastFailureAt=0;
    }
  }catch(error){
    loadedCursor=null; // retry on next existing runtime-state signal
    lastError=safe(error?.message||error);
    lastFailureAt=Date.now();
    const area=node("runtimeSourcesStatus");
    if(area)area.textContent="อ่านคิวจริงจาก Core ไม่สำเร็จ: "+lastError+
      (lastUpdate?" · คงภาพข้อมูลล่าสุดไว้":"");
  }finally{
    inFlight=false;
    if(enabled&&pendingCursor!==null){
      const next=pendingCursor;
      pendingCursor=null;
      if(next!==loadedCursor&&!lastFailureAt)inspect(next);
    }
  }
}
function onRuntimeState(data){
  if(!data)return;
  if(data.mode!=="computer"){
    const switching=enabled;
    enabled=false;
    pendingCursor=null;
    loadedCursor=null;
    if(switching)
      for(const feed of Object.values(feeds))feed?.refreshBrowserView?.();
    return;
  }
  enabled=true;
  const cursor=safe(data.dashboard_cursor||data.revision);
  if(!cursor||root.document?.hidden)return;
  // Never retry an unavailable private endpoint in a rapid failure loop.
  // The existing Runtime status refresh retries only after five seconds.
  if(lastFailureAt&&Date.now()-lastFailureAt<5000)return;
  if(inFlight){
    if(cursor!==loadedCursor)pendingCursor=cursor;
  }else if(cursor!==loadedCursor){
    inspect(cursor);
  }
}
function onRuntimeError(error){
  if(!enabled)return;
  const area=node("runtimeSourcesStatus");
  if(area)area.textContent="สถานะ Core ล่าสุดอาจล้าสมัย · "+safe(error?.message||error);
}
function init(value){
  feeds=value?.feeds||{};
  const state=root.VoxLastRuntimeSnapshot;
  if(state)onRuntimeState(state);
}
root.VoxCoreDashboard={init,onRuntimeState,onRuntimeError,
  getLastError:()=>lastError};
})(typeof window==="undefined"?globalThis:window);
