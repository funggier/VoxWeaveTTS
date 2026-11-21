"use strict";
// Browser read-ahead capacity: 100 text preps and 20 WAV-ready future jobs.
const assert=require("node:assert/strict");
const {attach}=require("../web/mode_inputs.js");
const waitFor=async(fn,label)=>{
  for(let i=0;i<350;i++){
    if(fn())return;
    await new Promise(resolve=>setTimeout(resolve,30));
  }
  throw new Error("Timed out while checking "+label);
};
async function run(){
  const dom=new Map(),jobs=new Map(),snapshots=[],played=[];
  const el=id=>{
    if(!dom.has(id))dom.set(id,{
      value:"",checked:false,disabled:false,style:{},href:"",
      src:"",textContent:"",paused:true,ended:false,events:{},
      addEventListener(event,fn){this.events[event]=fn;},
      pause(){this.paused=true;},load(){},
      removeAttribute(name){if(name==="src")this.src="";}
    });
    return dom.get(id);
  };
  const audio=el("liveAudio");
  el("liveFeedAuto").checked=true;
  el("liveFeedPrepareAhead").checked=true;
  el("liveFeedPrepareQueueLimit").value="100";
  el("liveFeedReadyAudioQueueLimit").value="20";
  el("liveFeedContinueOnTtsError").checked=true;
  let count=0;
  const oldFetch=global.fetch;
  global.fetch=async(path,options={})=>{
    if(path==="/v1/jobs"){
      const id="job"+(++count);
      jobs.set(id,{render:false,cancelled:false,
        text:JSON.parse(options.body).text});
      return {ok:true,async json(){return{speech_id:id,state:"preparing"};}};
    }
    const parts=path.match(/^\/v1\/jobs\/(job\d+)(.*)$/);
    assert.ok(parts,"unexpected job path "+path);
    const id=parts[1],suffix=parts[2],job=jobs.get(id);
    assert.ok(job,"missing job "+id);
    if(suffix==="/start-render"){
      job.render=true;
      return {ok:true,async json(){return {state:"queued"};}};
    }
    if(suffix==="/cancel"){
      job.cancelled=true;
      return {ok:true,async json(){return {state:"cancelled"};}};
    }
    if(suffix==="/ack-audio"){
      return {ok:true,async json(){return {state:"ready"};}};
    }
    if(suffix==="/tts-inputs"||suffix==="/tts-preview"){
      return {ok:true,async json(){return{available:false};}};
    }
    if(suffix==="/audio"){
      return {ok:true,async blob(){return new Blob(["RIFF"]);}};
    }
    if(suffix===""){
      return {ok:true,async json(){return {
        speech_id:id,state:job.render?"ready":"prepared",
        audio:job.render?{duration_ms:250,segments:[]}:undefined,
      };}};
    }
    throw new Error("unexpected job suffix "+suffix);
  };
  const ctrl=attach({mode:"live",el,report(){},guard:()=>true,
    clockLibrary:{attach(){return{clear(){},setSpeech(){}};}},
    getSpeechPayload:text=>({text}),
    onPipelineState:snapshot=>snapshots.push(snapshot),
    async playAudio(player){
      played.push(el("liveText").value);
      player.paused=false;player.ended=false;return true;
    },
    cancelAudio(player){player.paused=true;},
  });
  try{
    for(let i=0;i<151;i++)
      ctrl.receiveIncoming({message_id:"m"+i,text:"text"+i},true);
    await waitFor(()=>played.length===1,"active WAV");
    await waitFor(()=>count>=121,"admission of 121 jobs");
    await waitFor(()=>snapshots.some(snapshot=>
      snapshot.filter(t=>t.stage==="ready").length===20),"20 future WAV jobs");
    const snapshot=snapshots.at(-1);
    assert.equal(played.length,1,"only one active WAV plays at a time");
    assert.equal(snapshot.filter(t=>t.stage==="ready").length,20);
    assert.ok(snapshot.filter(t=>["preparing","prepared"].includes(t.stage)).length<=100);
    assert.ok(snapshot.filter(t=>t.stage!=="reading").length<=120,
      "never admit more than 100+20 future jobs (active playback excluded)");
    assert.equal(ctrl.pendingAuto,30);
    assert.match(el("liveStatus").textContent,/เสียงรอเล่น 20/);
    console.log("PASS: 100 prepared text plans + 20 WAV-ready slots, FIFO head, bounded audio and raw queue");
  }finally{
    ctrl.clearAutoQueue({includeActive:true});
    ctrl.stop({discard:true});
    global.fetch=oldFetch;
  }
}
run().catch(error=>{console.error(error);process.exitCode=1;});
