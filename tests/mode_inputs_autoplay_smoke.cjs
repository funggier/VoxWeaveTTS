// Regression: Firefox autoplay denial is not interchangeable with a failed
// TTS job, cancelled scheduler playback, or a malformed WAV. Pending messages
// and already-rendered audio survive the Pause / Retry flow.
"use strict";
const assert=require("node:assert/strict");
const {attach}=require("../web/mode_inputs.js");

const tick=()=>new Promise(resolve=>setImmediate(resolve));
const blocked=()=>Object.assign(new Error("play() was blocked by the browser"),
  {name:"NotAllowedError"});

function createHarness({failFirstJob=false,denyFirstPlay=false,denyFirstNPlays=0,
  cancelFirstPlay=false,holdFirstJob=false}={}){
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
      if((denyFirstPlay&&playAttempts===1)||playAttempts<=denyFirstNPlays)
        throw blocked();
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

async function testFirefoxPermissionStillPausesWithErrorContinuationEnabled(){
  const t=createHarness({denyFirstPlay:true});
  try{
    t.get("liveFeedContinueOnTtsError").checked=true;
    t.api.receiveIncoming({message_id:"blocked",text:"เสียงที่หนึ่ง"},true);
    t.api.receiveIncoming({message_id:"pending",text:"เสียงที่สอง"},true);
    await tick();
    assert.equal(t.api.autoPaused,true,
      "Browser NotAllowedError requires a gesture; do not skip every LIVE chat");
    assert.equal(t.states.get("blocked"),"queued");
    assert.equal(t.api.pendingAuto,1);
    assert.match(t.get("liveStatus").textContent,/NotAllowedError/);
    await t.get("liveAutoRetry").fire("click");
    assert.equal(t.api.autoPaused,false);
    assert.equal(t.states.get("blocked"),"reading");
  }finally{t.cleanup();}
}

async function testUnlimitedAutoplaySkipAfterManyBlocks(){
  const t=createHarness({denyFirstNPlays:7});
  try{
    t.get("liveFeedForceAutoplay").checked=true;
    for(let i=1;i<=8;i++)
      t.api.receiveIncoming({message_id:"blocked-"+i,text:"ข้อความ"+i},true);
    for(let i=0;i<50 && t.states.get("blocked-8")!=="reading";i++)
      await tick();
    assert.equal(t.api.autoPaused,false,
      "opt-in allows unlimited skips without auto-pausing");
    assert.equal(t.playAttempts,8,
      "the eighth message must be attempted after seven Browser denials");
    assert.equal(t.synthesisAttempts,8,
      "each failed WAV is discarded and the next message rendered");
    for(let i=1;i<=7;i++)
      assert.equal(t.states.get("blocked-"+i),"skipped");
    assert.equal(t.states.get("blocked-8"),"reading");
    assert.match(t.get("liveStatus").textContent,/ข้ามเสียงที่ Browser บล็อก 7/);
    t.audio.paused=true;
    await t.audio.fire("ended");
    await tick();
    assert.equal(t.states.get("blocked-8"),"read");
    assert.equal(t.api.pendingAuto,0);
  }finally{t.cleanup();}
}
async function testAllBrowserBlockedItemsMayBeDiscarded(){
  const t=createHarness({denyFirstNPlays:99});
  try{
    t.get("liveFeedForceAutoplay").checked=true;
    for(let i=1;i<=9;i++)
      t.api.receiveIncoming({message_id:"all-blocked-"+i,text:"ข้อความ"+i},true);
    for(let i=0;i<60 && t.states.get("all-blocked-9")!=="skipped";i++)
      await tick();
    assert.equal(t.playAttempts,9,"try every message, no three-skip cap");
    assert.equal(t.synthesisAttempts,9);
    assert.equal(t.api.pendingAuto,0);
    assert.equal(t.api.autoPaused,false,"queue remains live after all WAVs are blocked");
    for(let i=1;i<=9;i++)
      assert.equal(t.states.get("all-blocked-"+i),"skipped");
    assert.match(t.get("liveStatus").textContent,/ข้ามเสียงที่ Browser บล็อก 9/);
  }finally{t.cleanup();}
}
async function testTurningOnForceAutoplaySkipsAlreadyBlockedWav(){
  const t=createHarness({denyFirstPlay:true});
  try{
    t.api.receiveIncoming({message_id:"held",text:"ถูกบล็อก"},true);
    t.api.receiveIncoming({message_id:"later",text:"อ่านต่อ"},true);
    await tick();
    assert.equal(t.api.autoPaused,true);
    assert.equal(t.states.get("held"),"queued");
    t.get("liveFeedForceAutoplay").checked=true;
    await t.get("liveFeedForceAutoplay").fire("change");
    for(let i=0;i<30 && t.states.get("later")!=="reading";i++)
      await tick();
    assert.equal(t.api.autoPaused,false);
    assert.equal(t.states.get("held"),"skipped");
    assert.equal(t.states.get("later"),"reading");
    assert.equal(t.playAttempts,2);
    assert.match(t.get("liveStatus").textContent,/ข้ามเสียงที่ Browser บล็อก 1/);
  }finally{t.cleanup();}
}
async function testForceAutoplayIsIndependentFromSpeechErrorPolicy(){
  const t=createHarness({failFirstJob:true});
  try{
    t.get("liveFeedForceAutoplay").checked=true;
    t.get("liveFeedContinueOnTtsError").checked=false;
    t.api.receiveIncoming({message_id:"failed-synthesis",text:"ไม่มี WAV"},true);
    t.api.receiveIncoming({message_id:"next",text:"ยังรอ"},true);
    await tick();
    assert.equal(t.api.autoPaused,true,
      "browser playback policy must not hide a TTS model failure");
    assert.equal(t.states.get("failed-synthesis"),"queued");
    assert.equal(t.playAttempts,0);
  }finally{t.cleanup();}
}

async function testIncomingMessagesQueueWhileFirefoxAutoplayPaused(){
  const t=createHarness({denyFirstPlay:true});
  try{
    t.api.receiveIncoming({message_id:"blocked",text:"งานแรก"},true);
    await tick();
    assert.equal(t.api.autoPaused,true);
    assert.equal(t.api.receiveIncoming({message_id:"while-paused",text:"ข้อความใหม่"},true),
      "queued","new LIVE messages should remain pending while Firefox blocks playback");
    assert.equal(t.api.pendingAuto,1);
    await t.get("liveAutoRetry").fire("click");
    assert.equal(t.states.get("blocked"),"reading");
    t.audio.paused=true;await t.audio.fire("ended");await tick();
    assert.equal(t.states.get("while-paused"),"reading");
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

async function testManualPreviewPreservesAllUnreadMessages(){
  const t=createHarness();
  try{
    for(let i=0;i<3;i++)
      t.api.receiveIncoming({message_id:"auto-"+i,text:"คิว "+i},true);
    await tick();await tick();
    assert.equal(t.states.get("auto-0"),"reading");
    assert.equal(t.api.pendingAuto,2);
    t.get("liveText").value="เสียงทดลอง";
    await t.get("liveSubmit").fire("click");
    await tick();await tick();
    assert.equal(t.api.pendingAuto,3,
      "manual Preview must requeue interrupted speech, not discard backlog");
    assert.equal(t.states.get("auto-0"),"queued");
    assert.equal(t.payloads.length,2,
      "manual Preview renders once after the interrupted auto job");
    t.api.receiveIncoming({message_id:"auto-3",text:"คิว 3"},true);
    assert.equal(t.api.pendingAuto,4);
    assert.equal(t.payloads.length,2,
      "new chat cannot overwrite manually generated WAV before it is played");
    await t.get("livePlay").fire("click");
    for(let i=0;i<5;i++){
      t.audio.paused=true;t.audio.ended=true;
      await t.audio.fire("ended");await tick();await tick();
    }
    assert.equal(t.api.pendingAuto,0);
    assert.deepEqual(t.payloads.map(x=>x.text),[
      "คิว 0","เสียงทดลอง","คิว 0","คิว 1","คิว 2","คิว 3",
    ]);
    for(let i=0;i<4;i++)assert.equal(t.states.get("auto-"+i),"read");
    assert.equal(t.api.randomRemovedCount,0);
  }finally{t.cleanup();}
}

async function testRandomQueueReductionPreservesActiveAndSurvivorOrder(){
  const t=createHarness();
  const oldRandom=Math.random;
  Math.random=()=>0.37; // deterministic reservoir sample
  try{
    t.get("liveFeedRandomEnable").checked=true;
    t.get("liveFeedRandomThreshold").value="20";
    t.get("liveFeedRandomKeep").value="5";
    t.api.receiveIncoming({message_id:"msg-0",text:"ข้อความ 0"},true);
    for(let i=1;i<=21;i++)
      t.api.receiveIncoming({message_id:"msg-"+i,text:"ข้อความ "+i},true);
    await tick();await tick();
    assert.equal(t.states.get("msg-0"),"reading",
      "active speech is never part of random queue reduction");
    assert.equal(t.api.pendingAuto,5,
      "pending count 21 must be reduced to the configured 5");
    assert.equal(t.api.randomRemovedCount,16);
    const survivors=Array.from({length:21},(_,i)=>i+1)
      .filter(i=>t.states.get("msg-"+i)!=="random_removed");
    assert.equal(survivors.length,5);
    assert.equal([...t.states.values()].filter(s=>s==="random_removed").length,16);
    for(let i=0;i<6;i++){
      t.audio.paused=true;t.audio.ended=true;
      await t.audio.fire("ended");await tick();await tick();
    }
    assert.equal(t.api.pendingAuto,0);
    assert.deepEqual(t.payloads.map(x=>Number(x.text.split(" ").at(-1))),
      [0,...survivors],"random survivors must be read in FIFO order");
    assert.equal(t.states.get("msg-0"),"read");
    for(const index of survivors)
      assert.equal(t.states.get("msg-"+index),"read");
    t.api.resetPending();
    assert.equal(t.api.randomRemovedCount,0,
      "explicit reset restarts random-removal statistics");
  }finally{
    Math.random=oldRandom;t.cleanup();
  }
}

async function testQueueReductionIsOptInAndAppliesWhenEnabledLater(){
  const t=createHarness();
  const oldRandom=Math.random;
  Math.random=()=>0.7;
  try{
    for(let i=0;i<60;i++)
      t.api.receiveIncoming({message_id:"later-"+i,text:"ลำดับ "+i},true);
    await tick();
    assert.equal(t.api.pendingAuto,59);
    assert.equal(t.api.randomRemovedCount,0,
      "default-off must never discard backlog");
    t.get("liveFeedRandomThreshold").value="20";
    t.get("liveFeedRandomKeep").value="5";
    t.get("liveFeedRandomEnable").checked=true;
    t.get("liveFeedRandomEnable").events.change();
    assert.equal(t.api.pendingAuto,5,
      "enabling random reduction on an existing backlog applies immediately");
    assert.equal(t.api.randomRemovedCount,54);
    assert.equal(t.states.get("later-0"),"reading");
    t.get("liveFeedRandomEnable").checked=false;
    t.get("liveFeedRandomEnable").events.change();
    for(let i=60;i<120;i++)
      t.api.receiveIncoming({message_id:"later-"+i,text:"ลำดับ "+i},true);
    assert.equal(t.api.pendingAuto,65,
      "disabled reduction must resume keeping every new pending message");
    assert.equal(t.api.randomRemovedCount,54);
  }finally{Math.random=oldRandom;t.cleanup();}
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
  await testFirefoxPermissionStillPausesWithErrorContinuationEnabled();
  await testUnlimitedAutoplaySkipAfterManyBlocks();
  await testAllBrowserBlockedItemsMayBeDiscarded();
  await testTurningOnForceAutoplaySkipsAlreadyBlockedWav();
  await testForceAutoplayIsIndependentFromSpeechErrorPolicy();
  await testIncomingMessagesQueueWhileFirefoxAutoplayPaused();
  await testSpeechJobFailureIsNotAutoplay();
  await testSchedulerCancelledPlayback();
  await testManualPlayRestoresPendingAutoQueue();
  await testManualPreviewPreservesAllUnreadMessages();
  await testRandomQueueReductionPreservesActiveAndSurvivorOrder();
  await testQueueReductionIsOptInAndAppliesWhenEnabledLater();
  console.log("PASS: Firefox retry, retained FIFO queue, opt-in random pruning to 5, active speech preservation and read-order tests");
})().catch(e=>{console.error(e);process.exitCode=1;});
