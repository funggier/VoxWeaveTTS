/* Local-input scaffold for Live and Discord workspaces.
 * Real platform adapters are intentionally not connected; the text area
 * simulates a source message. Each workspace has independent WAV/playback.
 */
(function(root){
"use strict";
function attach({mode,el,clockLibrary,report,getSpeechPayload,guard,onMessageState}){
  if(!["live","discord","discord_client","tiktok"].includes(mode))throw Error("unknown source mode");
  const prefix=mode==="discord_client"?"discordClient":mode;
  const get=id=>el(prefix+id);
  const audio=get("Audio");
  let generation=0, jobId=null, lastReady=null, wavUrl=null;
  // One controller is created per source mode. All three provider types use
  // exactly the same serial queue; there is no cross-mode audio overlap.
  const MAX_WAITING=12;
  const incoming=[];
  let autoBusy=false, activeIncoming=null, queueEpoch=0, overflow=0;
  function mark(item,state){
    if(item?.message_id != null)onMessageState?.(String(item.message_id),state);
  }
  function clearAutoQueue({includeActive=false}={}){
    for(const item of incoming)mark(item,"skipped");
    incoming.length=0;
    if(includeActive){
      queueEpoch++;
      if(activeIncoming)mark(activeIncoming,"skipped");
      activeIncoming=null;
      autoBusy=false;
    }
  }
  const clock=clockLibrary.attach(audio,payload=>report(payload,mode),
    state=>{
      get("Subtitle").textContent=state.text;
    }
  );
  function feedback(message){get("Status").textContent=message;}
  function releaseAudio(){
    clock.clear();
    audio.pause();
    audio.removeAttribute("src");
    audio.load?.();
    audio.style.display="none";
    if(wavUrl)URL.revokeObjectURL(wavUrl);
    wavUrl=null;
  }
  function stop({discard=false}={}){
    generation++;
    clock.clear();
    audio.pause();
    const old=jobId;
    if(old && !lastReady){
      // In-flight inference cannot always be interrupted; late results
      // cannot reach a player after the generation changes.
      fetch("/v1/jobs/"+old+"/cancel",{
        method:"POST",headers:{"X-VoxWeaveTTS-Intent":"cancel-speech-job"}
      }).catch(()=>{});
      jobId=null;
    }
    if(discard){
      releaseAudio();
      lastReady=null;
      jobId=null;
      get("Download").style.display="none";
    }
    get("Submit").disabled=false;
    if(old)feedback("หยุดเสียงของโหมดนี้แล้ว · ข้อความยังอยู่");
  }
  function suspend(){
    clearAutoQueue({includeActive:true});
    stop({discard:false});
    // Re-entering a mode should never automatically resume audio.
    if(audio.currentTime>0)audio.currentTime=0;
  }
  async function submit({autoPlay=false,messageId=null}={}){
    if(!guard(mode))throw Error("กรุณาเปิดโหมดนี้ให้เป็นโหมดปัจจุบันก่อน");
    const text=get("Text").value;
    if(!text.trim())throw Error("กรุณาใส่ข้อความทดลอง");
    // A manual request takes precedence over a queued automatic feed.
    if(!autoPlay)clearAutoQueue({includeActive:true});
    stop({discard:true});
    const my=++generation;
    lastReady=null;
    get("Submit").disabled=true;
    feedback("กำลังสร้างเสียงของโหมด "+mode+"...");
    try{
      const body=getSpeechPayload(text);
      body.source=mode==="live"?"youtube-live":mode==="tiktok"?"tiktok-live":"discord";
      if(messageId!==null)body.source_message_id=mode+"-"+String(messageId).slice(0,100);
      const request=await fetch("/v1/jobs",{
        method:"POST",
        headers:{"Content-Type":"application/json","X-VoxWeaveTTS-Intent":"queue-speech"},
        body:JSON.stringify(body)
      });
      const created=await request.json();
      if(!request.ok)throw Error(created.error||"สร้างงานเสียงไม่สำเร็จ");
      if(my!==generation||!guard(mode)){
        // Do not begin polling/playing in the wrong mode.
        fetch("/v1/jobs/"+created.speech_id+"/cancel",{
          method:"POST",headers:{"X-VoxWeaveTTS-Intent":"cancel-speech-job"}
        }).catch(()=>{});
        return;
      }
      jobId=created.speech_id;
      for(let i=0;i<220;i++){
        if(my!==generation||!guard(mode))return;
        const r=await fetch("/v1/jobs/"+created.speech_id,{cache:"no-store"});
        const job=await r.json();
        if(!r.ok)throw Error(job.error||"ไม่สามารถอ่านสถานะงานเสียง");
        if(job.state==="ready"){
          const downloaded=await fetch("/v1/jobs/"+created.speech_id+"/audio");
          if(!downloaded.ok)throw Error("WAV ไม่พร้อม");
          const wav=await downloaded.blob();
          if(my!==generation||!guard(mode))return;
          wavUrl=URL.createObjectURL(wav);
          lastReady=job;
          clock.setSpeech(job.speech_id,job.audio);
          audio.src=wavUrl;
          audio.style.display="block";
          get("Download").href=wavUrl;
          get("Download").style.display="inline-block";
          feedback("เสียงพร้อม · กด Play เพื่ออ่านข้อความของโหมดนี้");
          if(autoPlay){
            try{
              await audio.play();
              if(activeIncoming && activeIncoming.message_id===messageId)
                mark(activeIncoming,"reading");
            }
            catch{
              feedback("Browser ไม่อนุญาต Auto-play · กด Play เองได้");
              return false;
            }
          }
          return true;
        }
        if(["failed","cancelled"].includes(job.state))
          throw Error("งานเสียง "+job.state);
        await new Promise(resolve=>setTimeout(resolve,250));
      }
      throw Error("งานเสียงยังไม่เสร็จตามช่วงทดสอบ กรุณาตรวจคิว");
    }catch(e){
      if(my===generation)feedback(String(e.message||e));
    }finally{
      if(my===generation)get("Submit").disabled=false;
    }
  }
  async function pumpIncoming(){
    if(autoBusy||!guard(mode)||!get("FeedAuto").checked)return;
    // Wait for the current manual or automatic WAV to finish.
    if(!audio.paused&&!audio.ended)return;
    const next=incoming.shift();
    if(!next)return;
    const ticket=queueEpoch;
    activeIncoming=next;
    autoBusy=true; // remains true until the audio "ended" event
    mark(next,"preparing");
    get("Text").value=next.text;
    try{
      const played=await submit({autoPlay:true,messageId:next.message_id});
      if(ticket!==queueEpoch)return; // stop/mode switch cancelled this job
      if(!played){
        // Do not pretend a generated WAV was actually read if autoplay fails.
        clearAutoQueue({includeActive:true});
        get("FeedAuto").checked=false;
        feedback("อ่านอัตโนมัติหยุดชั่วคราว · ตรวจสิทธิ์เล่นเสียงใน Browser แล้วเปิดใหม่");
      }
    }catch(error){
      if(ticket!==queueEpoch)return;
      clearAutoQueue({includeActive:true});
      get("FeedAuto").checked=false;
      feedback(String(error.message||error));
    }
  }
  function receiveIncoming(msg,autoRead){
    if(!autoRead||!guard(mode)||typeof msg?.text!=="string")return "manual";
    if(incoming.length>=MAX_WAITING){
      // Never silently evict an earlier unread message. New overflow is
      // skipped, and the UI marks it as such instead of claiming it was read.
      overflow++;
      return "skipped";
    }
    incoming.push(msg);
    pumpIncoming();
    return "queued";
  }
  audio.addEventListener("ended",()=>{
    if(activeIncoming)mark(activeIncoming,"read");
    activeIncoming=null;
    autoBusy=false;
    pumpIncoming();
  });
  audio.addEventListener("error",()=>{
    if(!activeIncoming)return;
    clearAutoQueue({includeActive:true});
    get("FeedAuto").checked=false;
    feedback("เกิดข้อผิดพลาดขณะเล่นเสียง · หยุดคิวอัตโนมัติแล้ว");
  });
  get("FeedAuto").addEventListener("change",()=>{
    if(get("FeedAuto").checked)pumpIncoming();
  });
  function resume(){
    if(lastReady && wavUrl){
      clock.setSpeech(lastReady.speech_id,lastReady.audio);
      audio.src=wavUrl;
      audio.style.display="block";
    }
  }
  get("Play").addEventListener("click",async()=>{
    if(!guard(mode)){feedback("โหมดนี้ไม่ได้ควบคุมเสียงอยู่ กรุณาเปิดโหมดอีกครั้ง");return;}
    if(!lastReady){feedback("กรุณาสร้าง WAV ก่อนกดเล่น");return;}
    try{await audio.play();}
    catch(error){feedback("Browser เล่นเสียงไม่สำเร็จ: "+String(error.message||error));}
  });
  get("Submit").addEventListener("click",()=>submit().catch(e=>feedback(String(e.message||e))));
  get("Stop").addEventListener("click",()=>{
    clearAutoQueue({includeActive:true});
    get("FeedAuto").checked=false;
    stop({discard:true});
    feedback("หยุดอ่านในโหมดนี้แล้ว · หากต้องการอ่านอัตโนมัติให้เปิดตัวเลือกอีกครั้ง");
  });
  return {stop,suspend,resume,submit,receiveIncoming,clearAutoQueue,
          get pendingAuto(){return incoming.length;},
          get skippedOverflow(){return overflow;},
          get jobId(){return jobId;}};
}
root.VoxModeInputs={attach};
if(typeof module!=="undefined"&&module.exports)module.exports={attach};
})(typeof window==="undefined"?globalThis:window);