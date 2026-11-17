/* Local-input scaffold for Live and Discord workspaces.
 * Real platform adapters are intentionally not connected; the text area
 * simulates a source message. Each workspace has independent WAV/playback.
 */
(function(root){
"use strict";
function attach({mode,el,clockLibrary,report,getSpeechPayload,guard,onMessageState,
                 onSpeechDiagnostic,onSpeechModelInputs,
                 playAudio=async audio=>{await audio.play();return true;},cancelAudio=()=>{}}){
  if(!["live","youtube_browser","tiktok_browser","discord","discord_client","tiktok"].includes(mode))throw Error("unknown source mode");
  const prefix=mode==="discord_client"?"discordClient":mode==="youtube_browser"?"youtubeBrowser":mode==="tiktok_browser"?"tiktokBrowser":mode;
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
    if(includeActive){
      randomRemoved=0;
      queueEpoch++;
      if(activeIncoming)mark(activeIncoming,"skipped");
      activeIncoming=null;
      autoBusy=false;
      activePartialFailure=false;
    }
  }
  function resetPending(){
    // Queue reset is intentionally NON-disruptive: the one active item can
    // be preparing/translation, synthesizing, playing or paused for a retry.
    // Only messages which have not started processing are discarded.
    const cleared=incoming.length;
    randomRemoved=0;
    for(const item of incoming)mark(item,"skipped");
    incoming.length=0;
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
  function feedback(message){get("Status").textContent=message;}
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
  function pauseAuto(reason,{replayReady=false}={}){
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
      body.source=mode==="live"?"youtube-live":mode==="youtube_browser"?"youtube-live-browser":mode==="tiktok"?"tiktok-live":mode==="tiktok_browser"?"tiktok-live-extension":"discord";
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
      const deadline=Date.now()+240000;
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
      throw Error("งานเสียงยังไม่เสร็จใน 4 นาที กรุณาตรวจคิว");
    }catch(e){
      if(my===generation){
        diagnose("failed",playbackFailure(e));
        if(autoPlay)throw e; // A failed job is NOT a Firefox autoplay denial.
        manualHolding=false;
        feedback(String(e.message||e));
        pumpIncoming();
      }
    }finally{
      if(my===generation)get("Submit").disabled=false;
    }
  }
  async function pumpIncoming(){
    if(autoBusy||autoPaused||manualHolding||!guard(mode)||!get("FeedAuto").checked)return;
    // Wait for the current manual or automatic WAV to finish.
    if(!audio.paused&&!audio.ended)return;
    const next=incoming.shift();
    if(!next)return;
    const ticket=queueEpoch;
    activeIncoming=next;
    autoBusy=true; // remains true until the audio "ended" event
    mark(next,"preparing");
    pickedMessage=null;
    get("Text").value=next.text;
    try{
      const played=await submit({autoPlay:true,messageId:next.message_id});
      if(ticket!==queueEpoch)return; // stop/mode switch cancelled this job
      if(played==="skipped" || played==="all_failed"){
        mark(next,"skipped");
        activeIncoming=null;
        autoBusy=false;
        pumpIncoming();
        return;
      }
      if(!played){
        // Playback was cancelled/not started; keep pending messages and WAV.
        pauseAuto("ยังเริ่มเล่นเสียงไม่ได้ (คิวหรือ Browser ยกเลิกการเล่น)",
          {replayReady:Boolean(lastReady&&wavUrl)});
      }
    }catch(error){
      if(ticket!==queueEpoch)return;
      pauseAuto(playbackFailure(error),
        {replayReady:Boolean(lastReady&&wavUrl)});
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
    reduceQueueIfNeeded();
    pumpIncoming();
    return "queued";
  }
  audio.addEventListener("ended",()=>{
    manualHolding=false;
    const wasPartial=Boolean(activeIncoming)&&activePartialFailure;
    if(activeIncoming)mark(activeIncoming,"read");
    activeIncoming=null;
    activePartialFailure=false;
    autoBusy=false;
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
    // A corrupt/unsupported WAV must be regenerated, not retried indefinitely.
    pauseAuto("ไฟล์เสียงเล่นไม่ได้ใน Browser · ตรวจรูปแบบ WAV แล้วลองอ่านต่อ");
  });
  for(const suffix of ["FeedRandomEnable","FeedRandomThreshold","FeedRandomKeep"]){
    get(suffix)?.addEventListener("change",()=>reduceQueueIfNeeded());
  }
  get("FeedAuto").addEventListener("change",()=>{
    autoPaused=false;
    if(get("FeedAuto").checked)pumpIncoming();
  });
  get("AutoRetry")?.addEventListener("click",async()=>{
    if(!get("FeedAuto").checked){
      feedback("เปิดอ่านอัตโนมัติก่อนกดลองอ่านต่อ");
      return;
    }
    autoPaused=false;
    manualHolding=false;
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
          pauseAuto("ยังเริ่มเล่นเสียงไม่ได้",{replayReady:true});
          return;
        }
        mark(activeIncoming,"reading");
        feedback("กำลังอ่านข้อความอัตโนมัติต่อ...");
      }catch(error){
        if(ticket!==queueEpoch)return;
        pauseAuto(playbackFailure(error),{replayReady:true});
      }
      return;
    }
    if(activeIncoming){
      mark(activeIncoming,"queued");
      incoming.unshift(activeIncoming);
      activeIncoming=null;
    }
    autoBusy=false;
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
    }catch(error){feedback(playbackFailure(error));}
  });
  get("Submit").addEventListener("click",()=>submit().catch(e=>feedback(String(e.message||e))));
  get("Stop").addEventListener("click",()=>{
    manualHolding=false;
    clearAutoQueue({includeActive:true});
    autoPaused=true;
    stop({discard:true});
    feedback("หยุดเสียงของโหมดนี้แล้ว · ค่าอ่านอัตโนมัติยังคงเดิม กดลองอ่านต่อเมื่อพร้อม");
  });
  return {stop,suspend,resume,submit,pickMessage,receiveIncoming,clearAutoQueue,resetPending,
          get autoPaused(){return autoPaused;},
          get pendingAuto(){return incoming.length;},
          get skippedOverflow(){return 0;},
          get randomRemovedCount(){return randomRemoved;},
          get jobId(){return jobId;}};
}
root.VoxModeInputs={attach};
if(typeof module!=="undefined"&&module.exports)module.exports={attach};
})(typeof window==="undefined"?globalThis:window);