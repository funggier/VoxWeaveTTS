/* Local-input scaffold for Live and Discord workspaces.
 * Real platform adapters are intentionally not connected; the text area
 * simulates a source message. Each workspace has independent WAV/playback.
 */
(function(root){
"use strict";
function attach({mode,el,clockLibrary,report,getSpeechPayload,guard}){
  if(mode!=="live"&&mode!=="discord")throw Error("unknown source mode");
  const get=id=>el(mode+id);
  const audio=get("Audio");
  let generation=0, jobId=null, lastReady=null, wavUrl=null;
  let activeTask=null;
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
    stop({discard:false});
    // Re-entering a mode should never automatically resume audio.
    if(audio.currentTime>0)audio.currentTime=0;
  }
  async function submit(){
    if(!guard(mode))throw Error("กรุณาเปิดโหมดนี้ให้เป็นโหมดปัจจุบันก่อน");
    const text=get("Text").value;
    if(!text.trim())throw Error("กรุณาใส่ข้อความทดลอง");
    stop({discard:true});
    const my=++generation;
    lastReady=null;
    get("Submit").disabled=true;
    feedback("กำลังสร้างเสียงของโหมด "+mode+"...");
    try{
      const body=getSpeechPayload(text);
      body.source=mode==="discord"?"discord":"youtube-live";
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
          feedback("เสียงพร้อม · กด Play เพื่ออ่านจากข้อความทดลองของโหมดนี้");
          return;
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
  get("Stop").addEventListener("click",()=>{stop({discard:true});feedback("หยุดอ่านในโหมดนี้แล้ว");});
  return {stop,suspend,resume,submit,get jobId(){return jobId;}};
}
root.VoxModeInputs={attach};
if(typeof module!=="undefined"&&module.exports)module.exports={attach};
})(typeof window==="undefined"?globalThis:window);