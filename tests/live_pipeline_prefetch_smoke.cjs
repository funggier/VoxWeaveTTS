"use strict";
/* Parallel live pipeline: actual browser controller, mocked server jobs.
 * Confirm TTS admission while audio plays, FIFO output and opt-in/off/reset.
 */
const assert=require("node:assert/strict");
const {attach}=require("../web/mode_inputs.js");
const tick=()=>new Promise(r=>setImmediate(r));
const waitFor=async(fn,description)=>{
  for(let i=0;i<110;i++){
    if(fn())return;
    await new Promise(r=>setTimeout(r,20));
  }
  throw Error("Timed out: "+description);
};

async function run(){
  const elements=new Map(),states=new Map(),submitted=[],played=[],cancelled=[];
  const snapshots=[];
  function el(id){
    if(!elements.has(id)){
      elements.set(id,{
        value:"",checked:false,disabled:false,style:{},href:"",src:"",
        textContent:"",paused:true,ended:false,events:{},
        addEventListener(name,fn){this.events[name]=fn;},
        pause(){this.paused=true;},load(){},
        removeAttribute(name){if(name==="src")this.src="";},
      });
    }
    return elements.get(id);
  }
  el("liveFeedAuto").checked=true;
  el("liveFeedPrepareAhead").checked=true;
  el("liveFeedPrepareQueueLimit").value="2";
  el("liveFeedReadyAudioQueueLimit").value="1";
  const audio=el("liveAudio");
  const jobs=new Map();
  const prior=global.fetch;
  global.fetch=async(path,options={})=>{
    if(path==="/v1/jobs"&&options.method==="POST"){
      const body=JSON.parse(options.body);
      const id="job"+String(submitted.length+1);
      submitted.push(body);
      jobs.set(id,{body,renderStarted:body.hold_for_render!==true});
      return {ok:true,async json(){return {speech_id:id,state:"preparing"};}};
    }
    const m=path.match(/^\/v1\/jobs\/(job\d+)(.*)$/);
    assert.ok(m,"unknown API path: "+path);
    const [whole,id,suffix]=m;
    if(suffix==="/ack-audio"){
      assert.equal(options.headers["X-VoxWeaveTTS-Intent"],"ack-staged-wav");
      return {ok:true,async json(){return{speech_id:id,state:"ready"};}};
    }
    if(suffix==="/start-render"){
      assert.equal(options.method,"POST");
      assert.equal(options.headers["X-VoxWeaveTTS-Intent"],"start-staged-speech-render");
      jobs.get(id).renderStarted=true;
      return {ok:true,async json(){return{speech_id:id,state:"queued"};}};
    }
    if(suffix==="/cancel"){
      cancelled.push(id);
      return {ok:true,async json(){return {state:"cancelled"};}};
    }
    if(suffix==="/audio")return {ok:true,async blob(){return new Blob(["WAVE"]);}};
    if(suffix==="/tts-preview"||suffix==="/tts-inputs"){
      assert.equal(options.method,"POST");
      assert.equal(options.headers["X-VoxWeaveTTS-Intent"],suffix==="/tts-preview"?
        "inspect-tts-preview":"inspect-tts-inputs");
      return {ok:true,async json(){return{
        speech_id:id,available:true,state:suffix==="/tts-inputs"?"ready":"rendering",
        inputs:[{text:"แปลแล้ว: "+jobs.get(id).body.text,language:"th",engine_id:"mock",voice_id:"voice",success:true}],
      };}};
    }
    if(suffix==="?wait=1")return {ok:true,async json(){return{speech_id:id,state:"ready",audio:{duration_ms:250,segments:[]}};}};
    if(suffix==="")return {ok:true,async json(){return{
      speech_id:id,state:jobs.get(id).renderStarted?"ready":"prepared",
      audio:jobs.get(id).renderStarted?{duration_ms:250,segments:[]}:undefined,
    };}};
    throw Error("Unexpected path suffix "+path);
  };
  const ctrl=attach({
    mode:"live",el,report(){},guard:()=>true,
    clockLibrary:{attach(){return {clear(){},setSpeech(){}};}},
    getSpeechPayload:text=>({text,engine_id:"mock",voice_id:"voice"}),
    onMessageState:(id,state)=>states.set(id,state),
    onPipelineState:items=>snapshots.push(items),
    onSpeechModelInputs(){},onSpeechDiagnostic(){},
    async playAudio(player){
      const text=jobs.get(ctrl.jobId)?.body.text;
      assert.ok(text,"playing must have a valid ready job id");
      played.push(text);player.paused=false;player.ended=false;
      return true;
    },
    cancelAudio(player){player.paused=true;},
  });
  const end=async()=>{
    audio.paused=true;audio.ended=true;
    await audio.events.ended();
    await tick();await tick();await tick();
  };
  try{
    for(let i=1;i<=6;i++)
      assert.equal(ctrl.receiveIncoming({
        message_id:"item"+i,author:"viewer",text:"text"+i},true),"queued");
    await waitFor(()=>played.length===1,"first WAV starts");
    assert.deepEqual(submitted.slice(0,3).map(x=>x.text),["text1","text2","text3"],
      "one active WAV + two future speech jobs may be admitted");
    assert.deepEqual(played,["text1"],"only first audio may play");
    assert.ok(ctrl.pendingAuto>=2,"later chat stays in raw random-prunable queue");
    const snapshot=snapshots.at(-1);
    assert.ok(snapshot.filter(x=>x.stage==="ready").length<=1,
      "configured audio-ready cap is enforced");
    assert.ok(snapshot.filter(x=>x.stage==="preparing"||x.stage==="prepared").length<=2,
      "configured prepare cap is enforced");
    assert.ok(snapshots.some(s=>s.some(x=>x.stage==="ready"&&
      x.inputs.some(y=>y.text.startsWith("แปลแล้ว:")))),
      "private post-translation text must be visible in the correct pipeline");
    assert.ok(["preparing","prepared","ready","rendering"].includes(states.get("item3")));
    // Turning the feature OFF does not discard or reorder admitted jobs.
    el("liveFeedPrepareAhead").checked=false;
    el("liveFeedPrepareAhead").events.change();
    await end();
    await waitFor(()=>played.length===2,"second FIFO WAV starts");
    const submittedWhenOff=submitted.length;
    assert.deepEqual(played,["text1","text2"]);
    assert.ok(submittedWhenOff>=3);
    assert.ok(submittedWhenOff<=5);
    await end();await waitFor(()=>played.length===3,"third FIFO WAV starts");
    assert.deepEqual(played,["text1","text2","text3"]);
    assert.equal(submitted.length,submittedWhenOff,"OFF stops new look-ahead admission");
    await end();
    await waitFor(()=>played.length===4,"fourth FIFO WAV starts");
    assert.equal(played.at(-1),"text4");
    await end();await waitFor(()=>played.length===5,"fifth WAV");
    await end();await waitFor(()=>played.length===6,"sixth WAV");
    await end();
    assert.deepEqual(played,["text1","text2","text3","text4","text5","text6"],
      "audio must always follow accepted chat order");
    assert.equal(ctrl.pendingAuto,0);
    for(let i=1;i<=6;i++)assert.equal(states.get("item"+i),"read");
    // Reset must retain currently playing audio but clear future prepared
    // jobs AND raw chat. No prepared audio may leak into a later session.
    el("liveFeedPrepareAhead").checked=true;
  el("liveFeedPrepareQueueLimit").value="2";
  el("liveFeedReadyAudioQueueLimit").value="1";
    for(let i=7;i<=11;i++)ctrl.receiveIncoming({
      message_id:"item"+i,author:"viewer",text:"text"+i},true);
    await waitFor(()=>played.length===7,"seventh WAV");
    assert.deepEqual(submitted.slice(6,9).map(x=>x.text),["text7","text8","text9"]);
    assert.equal(played.at(-1),"text7");
    const cleared=ctrl.resetPending();
    assert.equal(cleared.active_message_id,"item7");
    assert.equal(cleared.cleared,4);
    await waitFor(()=>cancelled.includes("job8")&&cancelled.includes("job9"),"cancel staged future jobs");
    assert.ok(cancelled.includes("job8")&&cancelled.includes("job9"),
      "ready prepared jobs must be cancelled on reset");
    assert.equal(states.get("item8"),"skipped");
    assert.equal(states.get("item9"),"skipped");
    await end();
    assert.equal(played.at(-1),"text7");
    assert.equal(played.length,7);
    console.log("PASS: ahead ON/OFF, two staged jobs, private translated view, FIFO, reset, no duplicate WAV playback");
  }finally{global.fetch=prior;}
}
run().catch(err=>{console.error(err);process.exitCode=1;});
