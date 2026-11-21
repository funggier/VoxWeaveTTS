"use strict";
// A timed-out speech job is skipped only when the explicit opt-in is enabled.
// The next LIVE message must begin automatically in both serial/prefetch modes.
const assert=require("node:assert/strict");
const {attach}=require("../web/mode_inputs.js");
const tick=()=>new Promise(resolve=>setImmediate(resolve));
const waitFor=async fn=>{
  for(let i=0;i<160;i++){
    if(fn())return;
    await new Promise(r=>setTimeout(r,20));
  }
  throw new Error("speech timeout recovery did not finish");
};

async function scenario(prefetch,continueOnError){
  const dom=new Map(),states=new Map(),cancelled=[],played=[];
  const get=id=>{
    if(!dom.has(id))dom.set(id,{
      value:"",checked:false,disabled:false,textContent:"",
      style:{},href:"",src:"",paused:true,ended:false,events:{},
      addEventListener(event,cb){this.events[event]=cb;},
      pause(){this.paused=true;},load(){},
      removeAttribute(name){if(name==="src")this.src="";}
    });
    return dom.get(id);
  };
  get("liveFeedAuto").checked=true;
  get("liveFeedPrepareAhead").checked=prefetch;
  get("liveFeedContinueOnTtsError").checked=continueOnError;
  get("liveFeedSpeechTimeoutMinutes").value="1";
  get("liveFeedPrepareQueueLimit").value="1";
  get("liveFeedReadyAudioQueueLimit").value="1";
  const audio=get("liveAudio");
  let now=10_000,submitted=0,skippedTimeAdvance=false;
  const oldDateNow=Date.now,oldFetch=global.fetch;
  Date.now=()=>now;
  global.fetch=async(path,options={})=>{
    if(path==="/v1/jobs"){
      submitted++;
      return {ok:true,async json(){return {speech_id:"job"+submitted,state:"queued"};}};
    }
    if(path.endsWith("/cancel")){
      cancelled.push(path.split("/")[3]);
      return {ok:true,async json(){return {state:"cancelled"};}};
    }
    if(path.endsWith("/tts-preview")||path.endsWith("/tts-inputs")){
      return {ok:true,async json(){return {available:false};}};
    }
    if(path.endsWith("/audio")){
      return {ok:true,async blob(){return new Blob(["RIFF"]);}};
    }
    if(path.endsWith("/ack-audio")){
      return {ok:true,async json(){return {state:"ready"};}};
    }
    if(path.endsWith("/start-render")){
      return {ok:true,async json(){return {state:"queued"};}};
    }
    if(path.startsWith("/v1/jobs/job")){
      const name=path.split("/")[3].split("?")[0];
      if(name==="job1"){
        if(!skippedTimeAdvance){
          skippedTimeAdvance=true;
          // Simulate the rendering step becoming stuck beyond configured 1min.
          now+=61_000;
        }
        return {ok:true,async json(){return {state:"rendering",speech_id:name};}};
      }
      return {ok:true,async json(){return {
        state:"ready",speech_id:name,partial_failure:false,
        audio:{duration_ms:30,segments:[]},
      };}};
    }
    throw new Error("unexpected fetch "+path);
  };
  const ctrl=attach({mode:"live",el:get,report(){},guard:()=>true,
    clockLibrary:{attach(){return{clear(){},setSpeech(){}};}},
    getSpeechPayload:text=>({text}),
    onMessageState:(id,state)=>states.set(id,state),
    async playAudio(player){
      played.push(get("liveText").value);
      player.paused=false;player.ended=false;return true;
    },
    cancelAudio(player){player.paused=true;},
  });
  try{
    assert.equal(ctrl.receiveIncoming({message_id:"first",text:"First"},true),"queued");
    assert.equal(ctrl.receiveIncoming({message_id:"second",text:"Second"},true),"queued");
    await waitFor(()=>continueOnError?played.length===1:ctrl.autoPaused);
    if(continueOnError){
      assert.equal(ctrl.autoPaused,false);
      assert.equal(states.get("first"),"skipped");
      assert.equal(played[0],"Second");
      assert.ok(cancelled.includes("job1"),"timed-out job must be cancelled");
      assert.match(get("liveStatus").textContent,/ข้ามข้อผิดพลาด 1/);
      audio.paused=true;audio.ended=true;
      await audio.events.ended();
      assert.equal(states.get("second"),"read");
      assert.equal(played.length,1,"must not synthesize or play failed first job twice");
    }else{
      assert.equal(played.length,0,"opt-out must pause after timeout");
      assert.equal(states.get("first"),"queued");
      assert.equal(ctrl.autoPaused,true);
    }
  }finally{
    // Any head waiting for explicit retry is stopped before restoring globals.
    ctrl.clearAutoQueue({includeActive:true});
    ctrl.stop({discard:true});
    Date.now=oldDateNow;
    global.fetch=oldFetch;
  }
}

(async()=>{
  for(const prefetch of [false,true]){
    for(const continueOnError of [false,true])
      await scenario(prefetch,continueOnError);
  }
  console.log("PASS: 1-minute serial/prefetch timeout, opt-in auto-skip, disabled pause, no duplicate read");
})().catch(error=>{console.error(error);process.exitCode=1;});
