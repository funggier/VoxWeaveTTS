// Regression: Firefox autoplay denial is not interchangeable with a failed
// TTS job, cancelled scheduler playback, or a malformed WAV. Pending messages
// and already-rendered audio survive the Pause / Retry flow.
"use strict";
const assert=require("node:assert/strict");
const {attach}=require("../web/mode_inputs.js");

const tick=()=>new Promise(resolve=>setImmediate(resolve));
const blocked=()=>Object.assign(new Error("play() was blocked by the browser"),
  {name:"NotAllowedError"});

function createHarness({failFirstJob=false,denyFirstPlay=false,cancelFirstPlay=false,holdFirstJob=false}={}){
  const elements=new Map(),states=new Map(),payloads=[];
  const get=id=>{
    if(!elements.has(id)){
      elements.set(id,{
        value:"",checked:false,disabled:false,style:{},href:"",src:"",
        textContent:"",paused:true,ended:false,events:{},
        addEventListener(name,fn){this.events[name]=fn;},
        pause(){this.paused=true;},
        removeAttribute(name){if(name==="src")this.src="";},
        load(){},async fire(name){return await this.events[name]?.();}
      });
    }
    return elements.get(id);
  };
  const audio=get("liveAudio");
  get("liveFeedAuto").checked=true;
  const jobs=new Map();
  let synthesisAttempts=0,playAttempts=0;
  let releaseFirstJob=()=>{};
  const waiting=holdFirstJob?new Promise(resolve=>{releaseFirstJob=resolve;}):null;
  const oldFetch=global.fetch;
  global.fetch=async(path,opts={})=>{
    if(path==="/v1/jobs"&&opts.method==="POST"){
      const body=JSON.parse(opts.body);
      payloads.push(body);
      const id="test-job-"+(++synthesisAttempts);
      jobs.set(id,failFirstJob&&synthesisAttempts===1?"failed":"ready");
      return {ok:true,async json(){return{speech_id:id,state:"queued"};}};
    }
    if(path.endsWith("/audio")){
      return {ok:true,async blob(){return new Blob(["RIFF short test audio"]);}};
    }
    if(path.endsWith("/cancel"))
      return {ok:true,async json(){return {state:"cancelled"};}};
    if(path.startsWith("/v1/jobs/")){
      const id=path.split("/")[3].split("?")[0];
      assert.ok(path.endsWith("?wait=1"));
      const state=jobs.get(id);
      if(id==="test-job-1"&&waiting)await waiting;
      return {ok:true,async json(){return {
        state, error:state==="failed"?"model not installed":undefined,
        speech_id:id,
        audio:{duration_ms:300,segments:[{kind:"speech",display_text:"test",
          start_ms:0,end_ms:300}]}
      };}};
    }
    throw new Error("Unexpected API request: "+path);
  };
  const api=attach({
    mode:"live",el:get,clockLibrary:{attach:()=>({
      clear(){},setSpeech(){}
    })},
    report(){},getSpeechPayload:text=>({text,mode:"live"}),guard:()=>true,
    onMessageState:(id,state)=>states.set(id,state),
    async playAudio(player){
      playAttempts++;
      if(denyFirstPlay&&playAttempts===1)throw blocked();
      if(cancelFirstPlay&&playAttempts===1)return false;
      player.paused=false;
      player.ended=false;
      return true;
    },
    cancelAudio(){},
  });
  return {
    api,get,audio,states,payloads,releaseFirstJob,
    get synthesisAttempts(){return synthesisAttempts;},
    get playAttempts(){return playAttempts;},
    cleanup(){global.fetch=oldFetch;}
  };
}

async function testFirefoxDenialAndResume(){
  const t=createHarness({denyFirstPlay:true});
  try{
    assert.equal(t.api.receiveIncoming({message_id:"one",text:"แรก"},true),"queued");
    assert.equal(t.api.receiveIncoming({message_id:"two",text:"สอง"},true),"queued");
    await tick();
    assert.equal(t.api.autoPaused,true);
    assert.equal(t.api.pendingAuto,1,"unread second message must remain queued");
    assert.equal(t.states.get("one"),"queued","blocked speech not marked read or skipped");
    assert.match(t.get("liveStatus").textContent,/Firefox\/Browser.*NotAllowedError/);
    assert.equal(t.synthesisAttempts,1);
    await t.get("liveAutoRetry").fire("click");
    assert.equal(t.api.autoPaused,false);
    assert.equal(t.synthesisAttempts,1,"retry must reuse already-generated WAV");
    assert.equal(t.playAttempts,2);
    assert.equal(t.states.get("one"),"reading");
    t.audio.paused=true;
    await t.audio.fire("ended");
    await tick();
    assert.equal(t.states.get("one"),"read");
    assert.equal(t.synthesisAttempts,2,"next pending message plays after ended");
    assert.equal(t.states.get("two"),"reading");
    t.audio.paused=true;await t.audio.fire("ended");
    await tick();
    assert.equal(t.api.autoPaused,false);
    assert.equal(t.states.get("two"),"read");
  }finally{t.cleanup();}
}

async function testSpeechJobFailureIsNotAutoplay(){
  const t=createHarness({failFirstJob:true});
  try{
    t.api.receiveIncoming({message_id:"fault",text:"โมเดลผิดพลาด"},true);
    t.api.receiveIncoming({message_id:"later",text:"ข้อความถัดมา"},true);
    await tick();
    assert.equal(t.api.autoPaused,true);
    assert.equal(t.api.pendingAuto,2,"failed job and pending chat stay in queue");
    assert.equal(t.states.get("fault"),"queued");
    assert.match(t.get("liveStatus").textContent,/งานเสียง failed.*model not installed/);
    assert.doesNotMatch(t.get("liveStatus").textContent,/บล็อก Auto-play/);
    assert.equal(t.playAttempts,0);
    await t.get("liveAutoRetry").fire("click");
    await tick();
    assert.equal(t.synthesisAttempts,2,"failed speech job is rendered again");
    assert.equal(t.states.get("fault"),"reading");
    t.audio.paused=true;await t.audio.fire("ended");await tick();
    assert.equal(t.states.get("fault"),"read");
    assert.equal(t.synthesisAttempts,3);
  }finally{t.cleanup();}
}

async function testSchedulerCancelledPlayback(){
  const t=createHarness({cancelFirstPlay:true});
  try{
    t.api.receiveIncoming({message_id:"cancelled",text:"หนึ่ง"},true);
    await tick();
    assert.equal(t.api.autoPaused,true);
    assert.match(t.get("liveStatus").textContent,/คิวหรือ Browser ยกเลิกการเล่น/);
    assert.doesNotMatch(t.get("liveStatus").textContent,/NotAllowedError/);
    await t.get("liveAutoRetry").fire("click");
    assert.equal(t.synthesisAttempts,1);
    assert.equal(t.states.get("cancelled"),"reading");
    t.audio.paused=true;await t.audio.fire("ended");
    assert.equal(t.states.get("cancelled"),"read");
  }finally{t.cleanup();}
}

async function testManualPlayRestoresPendingAutoQueue(){
  const t=createHarness({denyFirstPlay:true});
  try{
    t.api.receiveIncoming({message_id:"manual",text:"ทดสอบ"},true);
    await tick();
    assert.equal(t.api.autoPaused,true);
    await t.get("livePlay").fire("click");
    assert.equal(t.api.autoPaused,false,"manual Play resumes paused automatic reader");
    assert.equal(t.states.get("manual"),"reading");
    t.audio.paused=true;await t.audio.fire("ended");
    assert.equal(t.states.get("manual"),"read");
  }finally{t.cleanup();}
}

async function testResetDoesNotInterruptCurrentlyPlaying(){
  const t=createHarness();
  try{
    t.api.receiveIncoming({message_id:"active",text:"งานที่กำลังอ่าน"},true);
    t.api.receiveIncoming({message_id:"old1",text:"ข้อความรอเก่า"},true);
    t.api.receiveIncoming({message_id:"old2",text:"ข้อความรอเก่าอีก"},true);
    await tick();
    assert.equal(t.states.get("active"),"reading");
    const reset=t.api.resetPending();
    assert.deepEqual(reset,{cleared:2,active_message_id:"active"});
    assert.equal(t.api.pendingAuto,0);
    assert.equal(t.states.get("active"),"reading");
    assert.equal(t.states.get("old1"),"skipped");
    assert.equal(t.states.get("old2"),"skipped");
    t.api.receiveIncoming({message_id:"fresh",text:"ข้อความล่าสุด"},true);
    assert.equal(t.api.pendingAuto,1);
    t.audio.paused=true;await t.audio.fire("ended");await tick();
    assert.equal(t.states.get("active"),"read");
    assert.equal(t.states.get("fresh"),"reading");
    assert.equal(t.synthesisAttempts,2);
    t.audio.paused=true;await t.audio.fire("ended");await tick();
    assert.equal(t.states.get("fresh"),"read");
  }finally{t.cleanup();}
}

async function testResetDoesNotInterruptTranslationOrSynthesis(){
  const t=createHarness({holdFirstJob:true});
  try{
    t.api.receiveIncoming({message_id:"preparing",text:"กำลังแปล"},true);
    t.api.receiveIncoming({message_id:"old",text:"รอคิว"},true);
    await tick();
    assert.equal(t.states.get("preparing"),"preparing");
    const reset=t.api.resetPending();
    assert.equal(reset.cleared,1);
    assert.equal(reset.active_message_id,"preparing");
    assert.equal(t.states.get("preparing"),"preparing");
    assert.equal(t.states.get("old"),"skipped");
    t.api.receiveIncoming({message_id:"new",text:"ข้อความใหม่"},true);
    t.releaseFirstJob();
    await tick();
    assert.equal(t.states.get("preparing"),"reading",
      "reset must never cancel an ongoing translation/render wait");
    t.audio.paused=true;await t.audio.fire("ended");await tick();
    assert.equal(t.states.get("preparing"),"read");
    assert.equal(t.states.get("new"),"reading");
  }finally{t.cleanup();}
}

(async()=>{
  await testResetDoesNotInterruptCurrentlyPlaying();
  await testResetDoesNotInterruptTranslationOrSynthesis();
  await testFirefoxDenialAndResume();
  await testSpeechJobFailureIsNotAutoplay();
  await testSchedulerCancelledPlayback();
  await testManualPlayRestoresPendingAutoQueue();
  console.log("PASS: Firefox autoplay permission, accurate failed-job feedback, pending queue retention, user-gesture retry, scheduler cancellation and manual Play recovery");
})().catch(e=>{console.error(e);process.exitCode=1;});
