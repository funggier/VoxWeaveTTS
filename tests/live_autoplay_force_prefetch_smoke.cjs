"use strict";
// Browser permission-denied playback: opt-in force continue skips every blocked
// staged WAV, preserves FIFO, and does not corrupt future prepared tasks.
const assert=require("node:assert/strict");
const {attach}=require("../web/mode_inputs.js");
const tick=()=>new Promise(r=>setTimeout(r,25));
async function waitFor(fn,what){
  for(let i=0;i<260;i++){
    if(fn())return;
    await tick();
  }
  throw Error("Timeout waiting for "+what);
}
async function run(){
  const dom=new Map(),states=new Map(),jobs=new Map(),cancelled=[];
  function el(id){
    if(!dom.has(id))dom.set(id,{
      value:"",checked:false,disabled:false,textContent:"",href:"",src:"",
      paused:true,ended:false,style:{},events:{},
      addEventListener(event,cb){this.events[event]=cb;},
      pause(){this.paused=true;},load(){},
      removeAttribute(name){if(name==="src")this.src="";},
    });
    return dom.get(id);
  }
  const audio=el("liveAudio");
  el("liveFeedAuto").checked=true;
  el("liveFeedPrepareAhead").checked=true;
  el("liveFeedForceAutoplay").checked=true;
  el("liveFeedContinueOnTtsError").checked=false;
  el("liveFeedPrepareQueueLimit").value="3";
  el("liveFeedReadyAudioQueueLimit").value="2";
  let submitted=0,playAttempts=0;
  const oldFetch=global.fetch;
  global.fetch=async(path,options={})=>{
    if(path==="/v1/jobs"&&options.method==="POST"){
      const id="job"+(++submitted);
      jobs.set(id,{text:JSON.parse(options.body).text,render:false});
      return {ok:true,async json(){return {speech_id:id,state:"preparing"};}};
    }
    const m=path.match(/^\/v1\/jobs\/(job\d+)(.*)$/);
    assert.ok(m,"Unexpected speech URL "+path);
    const [,id,suffix]=m,job=jobs.get(id);
    assert.ok(job,"No job for "+id);
    if(suffix==="/start-render"){
      job.render=true;
      return {ok:true,async json(){return {state:"queued"};}};
    }
    if(suffix==="/cancel"){
      cancelled.push(id);
      return {ok:true,async json(){return {state:"cancelled"};}};
    }
    if(suffix==="/audio"){
      return {ok:true,async blob(){return new Blob(["RIFF"]);}};
    }
    if(suffix==="/ack-audio")
      return {ok:true,async json(){return {state:"ready"};}};
    if(suffix==="/tts-preview"||suffix==="/tts-inputs")
      return {ok:true,async json(){return {available:false};}};
    if(suffix==="")
      return {ok:true,async json(){return {speech_id:id,
        state:job.render?"ready":"prepared",
        audio:job.render?{duration_ms:180,segments:[]}:undefined,
      };}};
    throw Error("Unexpected suffix "+suffix);
  };
  const heard=[];
  const ctrl=attach({
    mode:"live",el,guard:()=>true,report(){},
    clockLibrary:{attach(){return {clear(){},setSpeech(){}};}},
    getSpeechPayload:text=>({text}),
    onMessageState:(id,state)=>states.set(id,state),
    async playAudio(player){
      playAttempts++;
      if(playAttempts<=5){
        const error=new Error("not permitted");
        error.name="NotAllowedError";
        throw error;
      }
      heard.push(el("liveText").value);
      player.paused=false;player.ended=false;
      return true;
    },
    cancelAudio(player){player.paused=true;},
  });
  try{
    for(let i=1;i<=6;i++)
      ctrl.receiveIncoming({message_id:"m"+i,text:"text"+i},true);
    await waitFor(()=>heard.length===1,"sixth successfully playing WAV");
    assert.equal(playAttempts,6);
    for(let i=1;i<=5;i++)
      assert.equal(states.get("m"+i),"skipped","blocked staged WAV "+i);
    assert.equal(states.get("m6"),"reading");
    assert.deepEqual(heard,["text6"]);
    assert.equal(ctrl.autoPaused,false);
    assert.equal(ctrl.pendingAuto,0);
    assert.match(el("liveStatus").textContent,/ข้ามเสียงที่ Browser บล็อก 5/);
    audio.paused=true;audio.ended=true;
    await audio.events.ended();
    assert.equal(states.get("m6"),"read");
    console.log("PASS: staged WAVs skip five blocked autoplay attempts and play sixth in FIFO order");
  }finally{
    ctrl.clearAutoQueue({includeActive:true});
    ctrl.stop({discard:true});
    global.fetch=oldFetch;
  }
}
run().catch(error=>{console.error(error);process.exitCode=1;});
