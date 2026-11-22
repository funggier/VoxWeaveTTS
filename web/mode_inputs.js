/* Local-input scaffold for Live and Discord workspaces.
 * Real platform adapters are intentionally not connected; the text area
 * simulates a source message. Each workspace has independent WAV/playback.
 */
(function(root){
"use strict";
// One connection per page for all Live modes. The stream carries job IDs
// only; fetch the current snapshot on a change or after a reconnect.
const stagedListeners=new Map();
let stagedStream=null;
function watchStagedJob(id){
  if(typeof root.EventSource!=="function")return null;
  if(!stagedStream){
    try{
      const stream=new root.EventSource("/v1/jobs/staged/stream");
      const wakeAll=()=>{for(const listeners of stagedListeners.values())listeners.forEach(wake=>wake());};
      stream.addEventListener("open",wakeAll);
      stream.addEventListener("error",wakeAll);
      stream.addEventListener("staged",event=>{
        let message;
        try{message=JSON.parse(event.data);}catch{return;}
        if(stagedStream!==stream||!Array.isArray(message?.jobs))return;
        if(message.resync)wakeAll();
        else for(const id of message.jobs)stagedListeners.get(id)?.forEach(wake=>wake());
      });
      stagedStream=stream;
    }catch{return null;}
  }

  let revision=0,finish=null;
  const wake=()=>{revision++;finish?.();};
  let listeners=stagedListeners.get(id);
  if(!listeners){listeners=new Set();stagedListeners.set(id,listeners);}
  listeners.add(wake);

  return {
    get revision(){return revision;},
    get connected(){return stagedStream?.readyState===1;},
    wake,
    wait(after,millis){
      if(revision!==after)return Promise.resolve();
      return new Promise(resolve=>{
        const timer=millis===undefined?null:setTimeout(()=>finish?.(),millis);
        finish=()=>{
          if(timer!==null)clearTimeout(timer);
          finish=null;
          resolve();
        };
      });
    },
    close(){
      wake();
      listeners.delete(wake);
      if(!listeners.size)stagedListeners.delete(id);
      if(!stagedListeners.size){stagedStream?.close();stagedStream=null;}
    },
  };
}
function attach({mode,el,clockLibrary,report,getSpeechPayload,guard,onMessageState,
                 onSpeechDiagnostic,onSpeechModelInputs,onPipelineState,
                 playAudio=async audio=>{await audio.play();return true;},cancelAudio=()=>{}}){
  if(!["live","youtube_browser","tiktok_browser","discord","discord_client","tiktok","stt_api"].includes(mode))throw Error("unknown source mode");
  const prefix=mode==="discord_client"?"discordClient":mode==="youtube_browser"?"youtubeBrowser":mode==="tiktok_browser"?"tiktokBrowser":mode==="stt_api"?"sttApi":mode;
  const get=id=>el(prefix+id);
  const Emoji=root.VoxEmojiPronunciation ||
    (typeof require==="function"?require("./emoji_pronunciation.js"):null);
  const audio=get("Audio");
  let generation=0, jobId=null, lastReady=null, wavUrl=null;
  // Each source owns its pending messages; shared scheduler controls whether
  // the resulting WAVs play serially across modes or may overlap.
  // Never drop accepted live messages just because speech is slower than chat.
  // Pending items remain FIFO until spoken, explicitly reset or stopped.
  const incoming=[];
  let autoBusy=false, activeIncoming=null, queueEpoch=0, randomRemoved=0;
  const prefetched=[]; // FIFO jobs preparing/rendering while another WAV plays
  let activePreparedTask=null;
  let submissionTail=Promise.resolve(); // preserves HTTP enqueue order
  let renderSubmissionTail=Promise.resolve(); // preserves TTS enqueue order
  let prefetchSequence=0; // distinct source key for an explicit failed-job retry
  let sourceOverview={state:"disconnected",connected:false,received:null,
                      discarded:null,pending:null,phase:""};
  let completedReads=0, importantNotice="";
  let manualSynthesizing=false;
  let errorSkipped=0, browserBlockedSkipped=0;
  // Browser permission failures are separate from translation/TTS errors.
  // Users may explicitly choose to discard every blocked WAV indefinitely.
  let pausedAutoplayError=null;
  const continueOnError=()=>get("FeedContinueOnTtsError")?.checked===true;
  const forceAutoplayContinue=()=>get("FeedForceAutoplay")?.checked===true;
  function jobTimeoutMinutes(){
    const n=Number(get("FeedSpeechTimeoutMinutes")?.value);
    return Number.isInteger(n)&&n>=1&&n<=60?n:4;
  }
  const jobTimeoutMs=()=>jobTimeoutMinutes()*60000;
  function timeoutError(kind){
    const error=new Error(kind+"รอนานเกิน "+jobTimeoutMinutes()+" นาที");
    error.code="speech_timeout";
    return error;
  }
  function blockedAutoplay(error){
    return ["NotAllowedError","SecurityError"].includes(String(error?.name||""));
  }
  function cancelSpeechJob(id){
    if(!id)return;
    fetch("/v1/jobs/"+id+"/cancel",{
      method:"POST",headers:{"X-VoxWeaveTTS-Intent":"cancel-speech-job"}
    }).catch(()=>{});
  }
  // LIVE status is a snapshot, not the last log message. In particular,
  // connection, AI, TTS and audio playback cannot overwrite each other.
  function setSourceStatus(snapshot){
    if(!snapshot||typeof snapshot!=="object")return;
    if(typeof snapshot.state==="string"){
      const previous=sourceOverview.state;
      sourceOverview.state=snapshot.state.slice(0,40);
      // A new connection supersedes a previous manual stop notice.
      if(previous==="stopped"&&sourceOverview.state==="connecting"&&
         importantNotice.startsWith("หยุดเสียง"))importantNotice="";
    }
    if(typeof snapshot.connected==="boolean")
      sourceOverview.connected=snapshot.connected;
    if(typeof snapshot.phase==="string")
      sourceOverview.phase=snapshot.phase.slice(0,48);
    for(const field of ["received","discarded","pending"])
      if(Number.isSafeInteger(snapshot[field]) && snapshot[field]>=0)
        sourceOverview[field]=snapshot[field];
    renderBottomStatus();
  }
  function renderBottomStatus(){
    const source=sourceOverview;
    const sourceStage=source.state==="error"?"เชื่อมต่อขัดข้อง"
      :source.state==="retrying"?"กำลังลองเชื่อมต่อใหม่"
      :source.state==="ended"?"ไลฟ์สิ้นสุด"
      :source.state==="extension_disconnected"?"Extension ขาดการเชื่อมต่อ"
      :source.phase==="comments_off"?"คอมเมนต์ถูกปิด/ไม่ปรากฏ"
      :source.connected&&source.phase==="waiting_extension_pair"?"รอจับคู่ Extension"
      :source.connected&&source.phase==="waiting_chat_dom"?"รอข้อมูลแชท"
      :source.state==="connecting"?"กำลังเชื่อมต่อ"
      :source.connected?"กำลังรับแชท"
      :source.state==="stopped"?"หยุดรับแชท":"ยังไม่เชื่อมต่อ";
    const jobs=[...(activePreparedTask?[activePreparedTask]:[]),...prefetched]
      .filter(task=>!task.cancelled);
    const count=state=>jobs.filter(task=>task.stage===state).length;
    const activity=autoPaused?"พักคิวอ่าน"
      :manualSynthesizing?"กำลังสร้างเสียงทดลอง"
      :!audio.paused&&!audio.ended?"กำลังเล่นเสียง"
      :activePreparedTask?.stage==="preparing"?"กำลังแปล/แยกข้อความ"
      :activePreparedTask?.stage==="prepared"?"รอสร้างเสียง"
      :activePreparedTask?.stage==="rendering"?"กำลังสร้างเสียง"
      :activeIncoming||autoBusy?"กำลังเตรียม/สร้างเสียง"
      :manualHolding?"รอข้อความที่เลือกอ่าน"
      :lastReady&&wavUrl?"เสียงพร้อมเล่น":"รอข้อความใหม่";
    const counts=source.received===null?""
      :" · รับแล้ว "+source.received+" · กรอง "+(source.discarded??0)+
       " · รอรับจากต้นทาง "+(source.pending??0);
    const lines=[
      "รับข้อความ: "+sourceStage+counts,
      "การอ่าน: "+activity+" · "+(get("FeedPrepareAhead")?.checked
        ?"เปิดเตรียมเสียงล่วงหน้า":"ไม่เตรียมเสียงล่วงหน้า"),
      "คิว: แชทดิบ "+incoming.length+
      " · กำลังแปล/แยก "+count("preparing")+
      " · เตรียมแล้ว "+count("prepared")+
      " · กำลังสร้างเสียง "+count("rendering")+
      " · เสียงรอเล่น "+count("ready")+
      " · อ่านจบ "+completedReads+
      " · สุ่มลบ "+randomRemoved+
      " · ข้ามข้อผิดพลาด "+errorSkipped+
      " · ข้ามเสียงที่ Browser บล็อก "+browserBlockedSkipped,
    ];
    if(importantNotice)lines.push("แจ้งเตือน: "+importantNotice);
    get("Status").textContent=lines.join("\n");
  }
  let autoPaused=false; // temporary playback error; never alters user preference
  let activePartialFailure=false; // pause decision applies only after the WAV actually ends
  let manualHolding=false; // manual preview may preempt, but must not erase FIFO
  let pickedMessage=null; // manual pick retains its author until text is edited
  function mark(item,state){
    if(item?.message_id != null)onMessageState?.(String(item.message_id),state);
  }
  function clearAutoQueue({includeActive=false}={}){
    for(const item of incoming)mark(item,"skipped");
    incoming.length=0;
    for(const task of prefetched){mark(task.item,"skipped");cancelPrefetched(task);}
    prefetched.length=0;
    if(includeActive&&activePreparedTask){
      cancelPrefetched(activePreparedTask);
      activePreparedTask=null;
    }
    showPipeline();
    if(includeActive){
      randomRemoved=0;
      queueEpoch++;
      if(activeIncoming)mark(activeIncoming,"skipped");
      activeIncoming=null;
      autoBusy=false;
      activePartialFailure=false;
    }
    renderBottomStatus();
  }
  function resetPending(){
    // Queue reset is intentionally NON-disruptive: the one active item can
    // be preparing/translation, synthesizing, playing or paused for a retry.
    // Only messages which have not started processing are discarded.
    const cleared=incoming.length+prefetched.length;
    randomRemoved=0;
    for(const item of incoming)mark(item,"skipped");
    incoming.length=0;
    for(const task of prefetched){mark(task.item,"skipped");cancelPrefetched(task);}
    prefetched.length=0;
    showPipeline();
    return {
      cleared,
      active_message_id:activeIncoming?.message_id == null
        ?null:String(activeIncoming.message_id),
    };
  }
  const clock=clockLibrary.attach(audio,payload=>report(payload,mode),
    state=>{
      get("Subtitle").textContent=state.text;
    }
  );
  function feedback(message){
    const text=String(message||"").slice(0,280);
    // Retain actionable failures/stop messages, not stale "WAV ready" logs.
    importantNotice=/พักคิว|พักชั่วคราว|หยุดเสียง|ไม่ได้|ล้มเหลว|ผิดพลาด|ไม่สำเร็จ|บล็อก|กรุณา|ไม่พร้อม|ข้ามข้อความ|ยกเลิกการเล่น/.test(text)
      ?text:"";
    renderBottomStatus();
  }
  function playbackFailure(error){
    const name=String(error?.name||"");
    const detail=String(error?.message||error||"ไม่ทราบสาเหตุ").slice(0,200);
    if(name==="NotAllowedError"||name==="SecurityError")
      return "Firefox/Browser บล็อก Auto-play ("+name+
        ") · อนุญาตให้เว็บไซต์นี้เล่นเสียงอัตโนมัติ แล้วกดอ่านอัตโนมัติต่อ";
    if(name==="NotSupportedError")
      return "Browser ไม่รองรับหรืออ่านไฟล์ WAV นี้ไม่ได้ ("+name+")";
    if(name==="AbortError")
      return "Browser ยกเลิกการเริ่มเล่นเสียง ("+name+")";
    return "งานเสียงหรือการเล่นเสียงล้มเหลว: "+detail+(name?" ("+name+")":"");
  }
  function pauseAuto(reason,{replayReady=false,blockedError=null}={}){
    pausedAutoplayError=blockedError;
    autoPaused=true;
    autoBusy=false;
    if(activeIncoming){
      // Keep a generated WAV for a user-gesture retry; failed generation
      // or invalid media must instead be synthesized again on retry.
      mark(activeIncoming,"queued");
      if(!replayReady){
        incoming.unshift(activeIncoming);
        activeIncoming=null;
      }
    }
    feedback("อ่านอัตโนมัติพักชั่วคราว · "+reason+
      " · กด 'อ่านอัตโนมัติต่อ' หลังแก้ไข");
  }
  function skipFailedJob(error,task,{browserBlocked=false}={}){
    // An explicit opt-in may discard every autoplay-blocked WAV. This does
    // not grant playback permission: a permanently blocked browser may
    // discard the entire LIVE backlog, exactly as the user requested.
    pausedAutoplayError=null;
    autoPaused=false;
    const reason=playbackFailure(error);
    if(task)cancelPrefetched(task);
    else cancelSpeechJob(jobId);
    activePartialFailure=false;
    lastReady=null;
    jobId=null;
    releaseAudio();
    if(activeIncoming)mark(activeIncoming,"skipped");
    onSpeechDiagnostic?.({
      message_id:activeIncoming?.message_id??null,stage:"failed",
      text:task?.composedText||String(get("Text").value||"").slice(0,9000),
      error:reason,
    });
    errorSkipped++;
    if(browserBlocked)browserBlockedSkipped++;
    feedback((browserBlocked?"ข้ามเสียงที่ Browser บล็อกแล้ว":"ข้ามข้อความที่ผิดพลาดแล้ว")+
      " · "+reason+" · อ่านคิวถัดไป");
    activeIncoming=null;
    activePreparedTask=null;
    autoBusy=false;
    showPipeline();
    fillPrefetched();
    // Prevent synchronous stack growth on multiple failures in a row.
    Promise.resolve().then(()=>pumpIncoming());
  }
  function readOptions(){
    const pick=key=>{
      const control=get("FeedFormat"+key);
      return control?.type==="checkbox"?control.checked:undefined;
    };
    const phrase=(field,fallback)=>{
      const input=get("Feed"+field);
      return input?.type==="text"?String(input.value||"").trim().slice(0,60):fallback;
    };
    const readEmojis=pick("read_emojis")===true;
    let dictionary={};
    if(readEmojis&&Emoji){
      try{dictionary=Emoji.parseEditor(String(get("FeedEmojiMappings")?.value||""));}
      catch{/* Ignore invalid unsaved edits rather than interrupting LIVE speech. */}
    }
    return {
      sender_prefix:phrase("SenderPrefix","คุณ"),
      separator:phrase("Separator","พิมพ์ว่า"),
      read_comments:pick("read_comments")!==false,
      read_name_at:pick("read_name_at")===true,
      read_emojis:readEmojis,emoji_dictionary:dictionary,
    };
  }
  function speechParts(item,plainText){
    const opts=readOptions();
    const speakEmoji=value=>opts.read_emojis&&Emoji
      ?Emoji.replace(value,opts.emoji_dictionary):value;
    if(!item)return {content:speakEmoji(plainText),sender_prefix_text:""};
    const clean=value=>typeof value==="string"
      ?value.replace(/[\u0000-\u001f\u007f]/g," ").replace(/\s+/g," ").trim()
      :"";
    let author=get("FeedReadSender")?.checked?clean(item.author).slice(0,80):"";
    // A YouTube handle can start with @. Remove that marker only from the
    // speaker's name. Never substitute @ in the actual viewer comment.
    if(author&&(mode==="live"||mode==="youtube_browser")&&!opts.read_name_at)
      author=author.replace(/^@+/,"").trim();
    // TikTok display names sometimes contain decorative emojis; keep their
    // visible Unicode names, but do not inject level/rank/badge metadata.
    const salutation=author&&opts.sender_prefix&&!author.startsWith(opts.sender_prefix)
      ?opts.sender_prefix:"";
    const named=author?[salutation,speakEmoji(author)].filter(Boolean).join(" "):"";
    return {
      content:speakEmoji(plainText),
      sender_prefix_text:[named,named?opts.separator:""].filter(Boolean).join(" ")
    };
  }
  function pickMessage(item){
    if(!item || typeof item.text!=="string")return;
    pickedMessage={...item};
    get("Text").value=item.text;
  }
  get("Text").addEventListener?.("input",()=>{pickedMessage=null;});
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
    cancelAudio(audio);
    generation++;
    manualSynthesizing=false;
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
      activePartialFailure=false;
      releaseAudio();
      lastReady=null;
      jobId=null;
      get("Download").style.display="none";
    }
    get("Submit").disabled=false;
    if(old)feedback("หยุดเสียงของโหมดนี้แล้ว · ข้อความยังอยู่");
    renderBottomStatus();
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
    // A manual preview can interrupt the current WAV, but it must NOT
    // silently discard accepted LIVE backlog. Requeue the interrupted item
    // at the front; only explicit Reset/Stop can delete waiting messages.
    if(!autoPlay){
      // Hold the manual preview only if an existing Live backlog was
      // interrupted; otherwise a new LIVE feed can start normally.
      // A manual preview invalidates jobs prepared for the old stream.
      // Restore their original FIFO order before using the legacy manual path.
      if(activePreparedTask||prefetched.length){
        const tasks=[...(activePreparedTask?[activePreparedTask]:[]),...prefetched];
        tasks.forEach(task=>{
          cancelPrefetched(task);
          mark(task.item,"queued");
        });
        incoming.unshift(...tasks.map(task=>task.item));
        if(activePreparedTask){activeIncoming=null;autoBusy=false;}
        activePreparedTask=null;prefetched.length=0;
        queueEpoch++;
        showPipeline();
      }
      manualHolding=Boolean(activeIncoming||incoming.length);
      if(activeIncoming){
        mark(activeIncoming,"queued");
        incoming.unshift(activeIncoming);
        activeIncoming=null;
        autoBusy=false;
        queueEpoch++; // invalidate the superseded auto submit callback
      }
    }
    stop({discard:true});
    const my=++generation;
    let diagnosticText=text;
    let diagnosticId=messageId;
    const diagnose=(stage,error="")=>onSpeechDiagnostic?.({
      message_id:diagnosticId,stage,text:diagnosticText,error
    });
    lastReady=null;
    get("Submit").disabled=true;
    if(!autoPlay)manualSynthesizing=true;
    feedback("กำลังสร้างเสียงของโหมด "+mode+"...");
    try{
      const body=getSpeechPayload(text,mode);
      // The checkbox is read at synthesis time, so pending messages use the
      // latest choice. Source history / editable message text remain untouched.
      const sender=autoPlay ? activeIncoming
        : (pickedMessage?.text===text ? pickedMessage : null);
      const parts=speechParts(sender,text);
      // Preserve legacy merged payload for older clients/tests, but provide
      // content separately so AI/shared rules never touch the sender header.
      body.text=[parts.sender_prefix_text,parts.content].filter(Boolean).join(" ");
      body.content_text=parts.content;
      body.sender_prefix_text=parts.sender_prefix_text;
      diagnosticText=body.text;
      diagnosticId=sender?.message_id??messageId;
      diagnose("preparing");
      body.source=mode==="live"?"youtube-live":mode==="youtube_browser"?"youtube-live-browser":mode==="tiktok"?"tiktok-live":mode==="tiktok_browser"?"tiktok-live-extension":mode==="stt_api"?"voxweave-stt":"discord";
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
      activePartialFailure=false;
      // The server waits on its speech-job condition (up to 10s) and wakes
      // the browser via a network response. A hidden tab may throttle timers
      // to 60s or longer, so no setTimeout drives Live TTS progression.
      const deadline=Date.now()+jobTimeoutMs();
      while(Date.now()<deadline){
        if(my!==generation||!guard(mode))return;
        const r=await fetch("/v1/jobs/"+created.speech_id+"?wait=1",{
          cache:"no-store"
        });
        const job=await r.json();
        if(!r.ok)throw Error(job.error||"ไม่สามารถอ่านสถานะงานเสียง");
        if(job.state==="ready"){
          activePartialFailure=autoPlay && job.partial_failure===true;
          const partialNotice=job.partial_failure===true
            ?"TTS ข้ามช่วงที่สร้างเสียงล้มเหลว "+Number(job.failed_chunks||0)+" ช่วง":"";
          // Separate, explicit same-origin inspection: ordinary job status
          // and subtitle events must never expose post-translation TTS text.
          // Fetch only after a ready WAV; never substitute source chat text.
          try{
            const inspected=await fetch(
              "/v1/jobs/"+created.speech_id+"/tts-inputs",{
                method:"POST",cache:"no-store",
                headers:{"Content-Type":"application/json",
                         "X-VoxWeaveTTS-Intent":"inspect-tts-inputs"},
                body:"{}",
              });
            if(inspected.ok){
              const detail=await inspected.json();
              if(my===generation && guard(mode)
                 && detail.speech_id===created.speech_id
                 && detail.state==="ready" && detail.available===true
                 && Array.isArray(detail.inputs)){
                onSpeechModelInputs?.(diagnosticId,detail.inputs);
              }
            }
          }catch{/* TTS audio may still be played if optional inspection fails. */}
          if(my!==generation||!guard(mode))return;
          const downloaded=await fetch("/v1/jobs/"+created.speech_id+"/audio");
          if(!downloaded.ok)throw Error("WAV ไม่พร้อม");
          const wav=await downloaded.blob();
          if(my!==generation||!guard(mode))return;
          wavUrl=URL.createObjectURL(wav);
          lastReady=job;
          diagnose("ready",partialNotice);
          clock.setSpeech(job.speech_id,job.audio);
          audio.src=wavUrl;
          audio.style.display="block";
          get("Download").href=wavUrl;
          get("Download").style.display="inline-block";
          feedback("เสียงพร้อม · กด Play เพื่ออ่านข้อความของโหมดนี้");
          if(autoPlay){
            // Let the caller distinguish a Firefox NotAllowedError from a
            // failed TTS job, WAV decode error or scheduler cancellation.
            const started=await playAudio(audio);
            if(!started)return false;
            if(activeIncoming && activeIncoming.message_id===messageId)
              mark(activeIncoming,"reading");
            diagnose("reading",partialNotice);
          }
          return true;
        }
        if(job.state==="skipped"){
          diagnose("skipped");
          feedback("ข้ามข้อความนี้ตามกฎกรองหรือการตั้งค่า AI · ไม่ส่งเข้า TTS");
          return "skipped";
        }
        if(job.state==="failed" && job.error==="all_tts_chunks_failed"
           && autoPlay && get("FeedContinueOnTtsError")?.checked===true){
          diagnose("failed","ทุกช่วงสร้างเสียงไม่สำเร็จ — ข้ามข้อความนี้แล้วอ่านคิวถัดไป");
          return "all_failed";
        }
        if(["failed","cancelled"].includes(job.state))
          throw Error("งานเสียง "+job.state+(job.error?" · "+String(job.error).slice(0,200):""));
        // No client-side timer: immediately request the next bounded wait.
      }
      throw timeoutError("งานเสียง");
    }catch(e){
      if(my===generation){
        diagnose("failed",playbackFailure(e));
        if(autoPlay)throw e; // A failed job is NOT a Firefox autoplay denial.
        manualHolding=false;
        feedback(String(e.message||e));
        pumpIncoming();
      }
    }finally{
      if(my===generation){
        manualSynthesizing=false;
        get("Submit").disabled=false;
        renderBottomStatus();
      }
    }
  }
  // The backend already has distinct AI-preparation and TTS workers. Submit
  // future jobs in FIFO order while the current WAV is playing. The browser
  // owns playback ordering: a completed future job never plays out of turn.
  function showPipeline(){
    renderBottomStatus();
    const tasks=[...(activePreparedTask?[activePreparedTask]:[]),...prefetched];
    onPipelineState?.(tasks.filter(task=>!task.cancelled).map(task=>({
      stage:task.stage,author:task.item.author||"",inputs:task.inputs||[],
    })));
  }
  function cancelPrefetched(task){
    task.cancelled=true;
    task.wakeStatus?.();
    if(task.jobId)fetch("/v1/jobs/"+task.jobId+"/cancel",{
      method:"POST",headers:{"X-VoxWeaveTTS-Intent":"cancel-speech-job"},
    }).catch(()=>{});
  }
  function makePrefetchPayload(item,sequence=null){
    const payload=getSpeechPayload(item.text,mode);
    const parts=speechParts(item,item.text);
    payload.text=[parts.sender_prefix_text,parts.content].filter(Boolean).join(" ");
    payload.content_text=parts.content;
    payload.sender_prefix_text=parts.sender_prefix_text;
    payload.source=mode==="live"?"youtube-live":mode==="youtube_browser"
      ?"youtube-live-browser":mode==="tiktok"?"tiktok-live"
      :mode==="tiktok_browser"?"tiktok-live-extension":mode==="stt_api"?"voxweave-stt":"discord";
    if(item.message_id!=null)
      payload.source_message_id=mode+"-"+String(item.message_id).slice(0,90)+
        (sequence===null?"":"-p"+sequence);
    return payload;
  }
  async function inspectPrefetched(task,finished=false){
    if(task.cancelled)return;
    try{
      const response=await fetch("/v1/jobs/"+task.jobId+
        (finished?"/tts-inputs":"/tts-preview"),{
          method:"POST",cache:"no-store",
          headers:{"Content-Type":"application/json",
                   "X-VoxWeaveTTS-Intent":finished
                     ?"inspect-tts-inputs":"inspect-tts-preview"},
          body:"{}",
        });
      if(!response.ok)return;
      const result=await response.json();
      if(task.cancelled||result.speech_id!==task.jobId
         ||result.available!==true||!Array.isArray(result.inputs))return;
      task.inputs=result.inputs;
      showPipeline();
    }catch{/* Diagnostics are optional; do not stall audio or leak chat text. */}
  }
  function queueLimits(){
    const limit=(id,fallback,maximum)=>{
      const raw=Number(get(id)?.value);
      return Number.isInteger(raw)&&raw>=1&&raw<=maximum?raw:fallback;
    };
    return {prepared:limit("FeedPrepareQueueLimit",3,100),
            ready:limit("FeedReadyAudioQueueLimit",2,20)};
  }
  function requestRender(task){
    if(task.cancelled||task.stage!=="prepared"||!task.jobId)return;
    // Reserve the slot before the asynchronous POST, preventing bursts.
    task.stage="rendering";
    mark(task.item,"rendering");
    showPipeline();
    const request=renderSubmissionTail.then(async()=>{
      if(task.cancelled)return;
      const response=await fetch("/v1/jobs/"+task.jobId+"/start-render",{
        method:"POST",
        headers:{"Content-Type":"application/json",
                 "X-VoxWeaveTTS-Intent":"start-staged-speech-render"},
        body:"{}",
      });
      if(!response.ok)throw Error("ไม่สามารถเริ่มสร้างเสียงจากคิวที่เตรียมไว้");
      return response.json();
    });
    task.renderRequest=request.catch(error=>{task.renderError=error;task.wakeStatus?.();});
    task.wakeStatus?.();
    renderSubmissionTail=task.renderRequest;
  }
  function scheduleRenders(){
    if(autoPaused||manualHolding||!guard(mode))return;
    // Current FIFO head is exempt from the *waiting-audio* quota: it must
    // begin rendering even when all permitted future WAV slots are filled.
    if(activePreparedTask?.stage==="preparing"&&!activePreparedTask.cancelled)return;
    if(activePreparedTask?.stage==="prepared")requestRender(activePreparedTask);
    const max=queueLimits().ready;
    let reserved=prefetched.filter(t=>!t.cancelled&&
      (t.stage==="rendering"||t.stage==="ready")).length;
    for(const task of prefetched){
      if(reserved>=max)break;
      if(task.cancelled)continue;
      // A later translation may finish first. Only admit the ready FIFO prefix.
      if(task.stage==="preparing")break;
      if(task.stage!=="prepared")continue;
      requestRender(task);
      reserved++;
    }
  }
  async function followPrefetched(task){
    const limit=jobTimeoutMs();
    let processingElapsed=0,lastTick=Date.now(),wasProcessing=true;
    const watcher=watchStagedJob(task.jobId);
    task.wakeStatus=watcher?.wake;
    try{
      while(!task.cancelled){
        const observed=watcher?.revision;
        const now=Date.now();
        if(wasProcessing)processingElapsed+=Math.max(0,now-lastTick);
        lastTick=now;
        if(task.renderError)throw task.renderError;
        // Immediate snapshot, not ?wait=1: a staged job intentionally stays
        // prepared until the browser grants a free audio-render slot.
        const response=await fetch("/v1/jobs/"+task.jobId,{cache:"no-store"});
        if(!response.ok)throw Error("ไม่สามารถตรวจสถานะงานเสียงล่วงหน้า");
        const job=await response.json();
        if(task.cancelled)return null;
        // An intentionally held "prepared" job waits for a WAV render slot.
        // That wait must not be mistaken for a slow AI/TTS computation.
        if(job.state==="prepared"){
          if(!task.inputs)await inspectPrefetched(task);
          if(task.cancelled)return null;
          if(task.stage!=="rendering"){
            task.stage="prepared";
            mark(task.item,"prepared");
            showPipeline();
            scheduleRenders();
          }
        }else if(job.state==="queued"||job.state==="rendering"){
          if(!task.inputs)await inspectPrefetched(task);
          if(task.cancelled)return null;
          task.stage="rendering";
          mark(task.item,"rendering");
          showPipeline();
        }else if(job.state==="ready"){
          task.stage="ready";task.job=job;
          await inspectPrefetched(task,true);
          if(task.cancelled)return null;
          mark(task.item,"ready");
          showPipeline();
          fillPrefetched();
          scheduleRenders();
          return job;
        }else if(["skipped","failed","cancelled"].includes(job.state)){
          task.stage=job.state;task.job=job;
          showPipeline();
          scheduleRenders();
          return job;
        }
        wasProcessing=job.state!=="prepared"||task.stage==="rendering";
        if(wasProcessing&&processingElapsed>=limit)throw timeoutError("งานเสียงล่วงหน้า");
        if(watcher?.connected){
          // A timeout wakes the error path only. Job progress comes from the server.
          await watcher.wait(observed,wasProcessing?limit-processingElapsed:undefined);
        }else{
          // Older servers and unavailable streams retain bounded status polling.
          const interval=task===activePreparedTask||task===prefetched[0]?150:
            Math.min(8000,1000+Math.ceil(prefetched.length/10)*500);
          if(watcher)await watcher.wait(observed,interval);
          else await new Promise(resolve=>setTimeout(resolve,interval));
        }
      }
      return null;
    }finally{
      delete task.wakeStatus;
      watcher?.close();
    }
  }
  function startPrefetched(item){
    const task={item,stage:"preparing",inputs:null,job:null,
                jobId:null,cancelled:false,promise:null,renderError:null,
                sequence:++prefetchSequence,composedText:""};
    mark(item,"preparing");
    // Serialize admissions, not AI: server has separate preparation/TTS
    // workers and will hold each job after translation until start-render.
    const admit=submissionTail.then(async()=>{
      if(task.cancelled)return false;
      const payload=makePrefetchPayload(item,task.sequence);
      payload.hold_for_render=true;
      task.composedText=payload.text;
      let response,created;
      const deadline=Date.now()+jobTimeoutMs();
      while(!task.cancelled){
        response=await fetch("/v1/jobs",{
          method:"POST",
          headers:{"Content-Type":"application/json",
                   "X-VoxWeaveTTS-Intent":"queue-speech"},
          body:JSON.stringify(payload),
        });
        if(response.status!==429)break;
        if(Date.now()>=deadline)throw timeoutError("คิวงานเสียงกลาง");
        await new Promise(resolve=>setTimeout(resolve,600));
      }
      if(task.cancelled&&!response?.ok)return false;
      created=await response.json();
      if(!response.ok)throw Error(created.error||"สร้างงานเสียงล่วงหน้าไม่สำเร็จ");
      task.jobId=created.speech_id;
      if(task.cancelled){cancelPrefetched(task);return false;}
      return true;
    });
    submissionTail=admit.then(()=>{},()=>{});
    task.promise=admit.then(ok=>ok?followPrefetched(task):null);
    task.promise.catch(()=>{}); // future jobs are observed when their turn arrives
    return task;
  }
  function fillPrefetched(){
    if(!get("FeedPrepareAhead")?.checked||autoPaused||manualHolding
       ||!get("FeedAuto").checked||!guard(mode))return;
    const limits=queueLimits();
    // Only source items in incoming remain subject to opt-in random deletion.
    // Once claimed, a message is guaranteed to stay in FIFO, except Reset.
    const pending=()=>prefetched.filter(t=>!t.cancelled&&
      ["preparing","prepared"].includes(t.stage)).length;
    while(incoming.length&&pending()<limits.prepared
      &&prefetched.length<limits.prepared+limits.ready){
      prefetched.push(startPrefetched(incoming.shift()));
    }
    showPipeline();
    scheduleRenders();
  }
  async function consumePrefetched(task,ticket){
    const item=task.item;
    const job=await task.promise;
    if(task.cancelled||ticket!==queueEpoch||!guard(mode))return false;
    if(!job)return false;
    if(job.state==="skipped")return "skipped";
    if(job.state==="failed"&&job.error==="all_tts_chunks_failed"
        &&get("FeedContinueOnTtsError")?.checked===true)return "all_failed";
    if(job.state!=="ready")
      throw Error("งานเสียง "+job.state+(job.error?" · "+String(job.error).slice(0,120):""));
    // All preprocessing, language routing and WAV synthesis already finished.
    // Only fetch the ready WAV when its turn to play arrives.
    releaseAudio();
    const response=await fetch("/v1/jobs/"+task.jobId+"/audio");
    if(!response.ok)throw Error("WAV ของคิวล่วงหน้าไม่พร้อม");
    const wav=await response.blob();
    if(task.cancelled||ticket!==queueEpoch||!guard(mode))return false;
    // The browser now owns the WAV, so the global job registry may evict
    // the server copy without discarding unplayed future audio.
    fetch("/v1/jobs/"+task.jobId+"/ack-audio",{
      method:"POST",
      headers:{"Content-Type":"application/json",
               "X-VoxWeaveTTS-Intent":"ack-staged-wav"},
      body:"{}",
    }).catch(()=>{});
    wavUrl=URL.createObjectURL(wav);
    jobId=task.jobId;
    lastReady=job;
    activePartialFailure=job.partial_failure===true;
    clock.setSpeech(job.speech_id,job.audio);
    audio.src=wavUrl;
    audio.style.display="block";
    get("Download").href=wavUrl;
    get("Download").style.display="inline-block";
    onSpeechModelInputs?.(item.message_id,task.inputs||[]);
    onSpeechDiagnostic?.({message_id:item.message_id,stage:"ready",
       text:task.composedText,error:""});
    // Start in strict arrival order. No playback awaits any other future job.
    const started=await playAudio(audio);
    if(!started)return false;
    if(task.cancelled||ticket!==queueEpoch)return false;
    task.stage="reading";
    pausedAutoplayError=null;
    mark(item,"reading");
    onSpeechDiagnostic?.({message_id:item.message_id,stage:"reading",
       text:task.composedText,error:""});
    showPipeline();
    return true;
  }
  async function pumpIncoming(){
    if(autoBusy||autoPaused||manualHolding||!guard(mode)||!get("FeedAuto").checked)return;
    // Wait for the current manual or automatic WAV to finish.
    if(!audio.paused&&!audio.ended)return;
    fillPrefetched();
    const task=prefetched.shift()||null;
    const next=task?task.item:incoming.shift();
    if(!next)return;
    const ticket=queueEpoch;
    activeIncoming=next;
    activePreparedTask=task;
    if(task?.stage==="prepared")requestRender(task);
    autoBusy=true; // remains true until the audio "ended" event
    mark(next,task?task.stage:"preparing");
    showPipeline();
    fillPrefetched(); // keep future preparation independent of the active job
    pickedMessage=null;
    get("Text").value=next.text;
    if(task){
      // Do not allow Firefox Retry to replay the prior message's WAV if
      // the current staged translation or TTS fails before audio download.
      releaseAudio();
      lastReady=null;
      jobId=null;
    }
    try{
      const played=task?await consumePrefetched(task,ticket)
        :await submit({autoPlay:true,messageId:next.message_id});
      if(ticket!==queueEpoch)return; // stop/mode switch cancelled this job
      if(played==="skipped" || played==="all_failed"){
        if(played==="all_failed")errorSkipped++;
        mark(next,"skipped");
        activeIncoming=null;
        activePreparedTask=null;
        showPipeline();
        autoBusy=false;
        pumpIncoming();
        return;
      }
      if(!played){
        const failure=new Error("ยังเริ่มเล่นเสียงไม่ได้ (คิวหรือ Browser ยกเลิกการเล่น)");
        if(forceAutoplayContinue())skipFailedJob(failure,task,{browserBlocked:true});
        else if(continueOnError())skipFailedJob(failure,task);
        else{
          // Preserve generated WAV and message when error skipping is off.
          activePreparedTask=null;
          showPipeline();
          pauseAuto(failure.message,{replayReady:Boolean(lastReady&&wavUrl)});
        }
      }
    }catch(error){
      if(ticket!==queueEpoch)return;
      if(blockedAutoplay(error) && forceAutoplayContinue()){
        skipFailedJob(error,task,{browserBlocked:true});
        return;
      }
      if(continueOnError()&&!blockedAutoplay(error)){
        skipFailedJob(error,task);
        return;
      }
      activePreparedTask=null;
      showPipeline();
      pauseAuto(playbackFailure(error),{
        replayReady:Boolean(lastReady&&wavUrl),
        blockedError:blockedAutoplay(error)?error:null,
      });
    }
  }
  function randomQueuePolicy(){
    if(!get("FeedRandomEnable")?.checked)return null;
    const threshold=Number(get("FeedRandomThreshold")?.value);
    const keep=Number(get("FeedRandomKeep")?.value);
    if(!Number.isInteger(threshold)||threshold<2||threshold>100000
       ||!Number.isInteger(keep)||keep<1||keep>=threshold)return null;
    return {threshold,keep};
  }
  function reduceQueueIfNeeded(){
    const policy=randomQueuePolicy();
    if(!policy||incoming.length<=policy.threshold)return 0;
    // Reservoir sampling: choose a uniform random subset, then retain its
    // original ordering. The active translation/voice is never in incoming.
    const selected=[];
    for(let i=0;i<incoming.length;i++){
      if(i<policy.keep)selected.push(i);
      else{
        const chosen=Math.floor(Math.random()*(i+1));
        if(chosen<policy.keep)selected[chosen]=i;
      }
    }
    const chosenIndices=new Set(selected);
    const keep=[],discard=[];
    for(let i=0;i<incoming.length;i++){
      (chosenIndices.has(i)?keep:discard).push(incoming[i]);
    }
    incoming.splice(0,incoming.length,...keep);
    randomRemoved+=discard.length;
    for(const item of discard)mark(item,"random_removed");
    return discard.length;
  }
  function receiveIncoming(msg,autoRead){
    // Temporary Firefox autoplay pauses must not turn incoming LIVE chat
    // into manual-only messages. Retain all accepted items until retry.
    if(!autoRead||!guard(mode)||typeof msg?.text!=="string")
      return "manual";
    const opts=readOptions();
    // Gift events are intentionally unsupported; never enqueue them as chat.
    if(msg.kind==="gift")return "skipped";
    if(!opts.read_comments)return "manual";
    incoming.push(msg);
    if(!autoPaused)importantNotice="";
    reduceQueueIfNeeded();
    fillPrefetched();
    pumpIncoming();
    renderBottomStatus();
    return "queued";
  }
  // Browser audio controls can start/pause independently of the TTS queue.
  // Update the operational summary from media events as well as queue events.
  for(const event of ["play","pause"])
    audio.addEventListener(event,renderBottomStatus);
  audio.addEventListener("ended",()=>{
    manualHolding=false;
    const wasReadingItem=Boolean(activeIncoming);
    const wasPartial=wasReadingItem&&activePartialFailure;
    if(activeIncoming)mark(activeIncoming,"read");
    activeIncoming=null;
    activePreparedTask=null;
    showPipeline();
    activePartialFailure=false;
    autoBusy=false;
    if(wasReadingItem)completedReads++;
    renderBottomStatus();
    if(wasPartial && get("FeedContinueOnTtsError")?.checked!==true){
      // Do NOT requeue a partially spoken message. Pause *after* its
      // successful WAV has played, then resume at the next FIFO item.
      autoPaused=true;
      feedback("สร้างเสียงบางช่วงไม่สำเร็จ เล่นส่วนที่สำเร็จจบแล้ว — พักคิว · กด 'อ่านอัตโนมัติต่อ' เพื่ออ่านข้อความถัดไป");
      return;
    }
    pumpIncoming();
  });
  audio.addEventListener("error",()=>{
    if(!activeIncoming)return;
    // A corrupt/unsupported WAV cannot be replayed. Skip when requested;
    // otherwise pause so users can investigate without losing the message.
    const error=new Error("ไฟล์เสียงเล่นไม่ได้ใน Browser · ตรวจรูปแบบ WAV");
    if(continueOnError())skipFailedJob(error,activePreparedTask);
    else pauseAuto(error.message+" แล้วลองอ่านต่อ");
  });
  for(const suffix of ["FeedRandomEnable","FeedRandomThreshold","FeedRandomKeep"]){
    get(suffix)?.addEventListener("change",()=>{
      reduceQueueIfNeeded();
      renderBottomStatus();
    });
  }
  get("FeedAuto").addEventListener("change",()=>{
    autoPaused=false;
    importantNotice="";
    renderBottomStatus();
    if(get("FeedAuto").checked){fillPrefetched();pumpIncoming();}
  });
  for(const setting of ["FeedPrepareQueueLimit","FeedReadyAudioQueueLimit"]){
    get(setting)?.addEventListener("change",()=>{
      fillPrefetched();scheduleRenders();showPipeline();
    });
  }
  get("FeedPrepareAhead")?.addEventListener("change",()=>{
    // Existing admitted work stays FIFO even when switched off; only
    // future admission stops. Never discard user messages on toggling.
    if(get("FeedPrepareAhead").checked){fillPrefetched();pumpIncoming();}
    showPipeline();
  });
  get("FeedForceAutoplay")?.addEventListener("change",()=>{
    // When enabling the option *after* Firefox denied autoplay, immediately
    // skip that retained WAV and continue the queue. Do not unpause manual
    // stops or unrelated speech/translation errors.
    if(forceAutoplayContinue()&&autoPaused&&pausedAutoplayError&&activeIncoming
       &&get("FeedAuto").checked&&guard(mode)){
      const blocked=pausedAutoplayError;
      skipFailedJob(blocked,activePreparedTask,{browserBlocked:true});
    }
    renderBottomStatus();
  });
  get("AutoRetry")?.addEventListener("click",async()=>{
    if(!get("FeedAuto").checked){
      feedback("เปิดอ่านอัตโนมัติก่อนกดลองอ่านต่อ");
      return;
    }
    autoPaused=false;
    pausedAutoplayError=null;
    manualHolding=false;
    importantNotice="";
    feedback("กำลังลองอ่านข้อความอัตโนมัติต่อ...");
    if(activeIncoming && lastReady && wavUrl){
      // Must call play directly in the click handler, preserving Firefox's
      // user activation. Do not synthesize and drop the already-ready WAV.
      const ticket=queueEpoch;
      autoBusy=true;
      try{
        const started=await playAudio(audio);
        if(ticket!==queueEpoch)return;
        if(!started){
          const failure=new Error("ยังเริ่มเล่นเสียงไม่ได้");
          if(forceAutoplayContinue())skipFailedJob(failure,activePreparedTask,{browserBlocked:true});
          else pauseAuto(failure.message,{replayReady:true});
          return;
        }
        pausedAutoplayError=null;
        mark(activeIncoming,"reading");
        feedback("กำลังอ่านข้อความอัตโนมัติต่อ...");
      }catch(error){
        if(ticket!==queueEpoch)return;
        if(blockedAutoplay(error)&&forceAutoplayContinue())
          skipFailedJob(error,activePreparedTask,{browserBlocked:true});
        else pauseAuto(playbackFailure(error),{
          replayReady:true,blockedError:blockedAutoplay(error)?error:null,
        });
      }
      return;
    }
    if(activeIncoming){
      mark(activeIncoming,"queued");
      incoming.unshift(activeIncoming);
      activeIncoming=null;
    }
    autoBusy=false;
    fillPrefetched();
    pumpIncoming();
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
    try{
      const started=await playAudio(audio);
      if(started&&manualHolding)manualHolding=false;
      if(started&&autoPaused&&activeIncoming){
        autoPaused=false;
        autoBusy=true;
        mark(activeIncoming,"reading");
        feedback("กำลังอ่านข้อความที่พักไว้...");
      }
      renderBottomStatus();
    }catch(error){feedback(playbackFailure(error));}
  });
  get("Submit").addEventListener("click",()=>submit().catch(e=>feedback(String(e.message||e))));
  get("Stop").addEventListener("click",()=>{
    pausedAutoplayError=null;
    manualHolding=false;
    clearAutoQueue({includeActive:true});
    autoPaused=true;
    stop({discard:true});
    feedback("หยุดเสียงของโหมดนี้แล้ว · ค่าอ่านอัตโนมัติยังคงเดิม กดลองอ่านต่อเมื่อพร้อม");
  });
  renderBottomStatus();
  return {stop,suspend,resume,submit,pickMessage,receiveIncoming,clearAutoQueue,resetPending,
          setSourceStatus,
          get autoPaused(){return autoPaused;},
          get pendingAuto(){return incoming.length;},
          get skippedOverflow(){return 0;},
          get randomRemovedCount(){return randomRemoved;},
          get pipelineCount(){return prefetched.length+(activePreparedTask?1:0);},
          get jobId(){return jobId;}};
}
root.VoxModeInputs={attach};
if(typeof module!=="undefined"&&module.exports)module.exports={attach};
})(typeof window==="undefined"?globalThis:window);