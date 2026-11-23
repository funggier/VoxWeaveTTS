/* A text-only Live route completes in strict FIFO without ever requesting WAV. */
"use strict";
const assert=require("node:assert/strict");
const fs=require("node:fs");
const vm=require("node:vm");

function testDocument(){
  const elements=new Map();
  function get(id){
    if(!elements.has(id))elements.set(id,{
      value:"",checked:false,disabled:false,textContent:"",style:{display:"none"},
      type:"text",src:"",paused:true,ended:false,events:{},
      addEventListener(event,callback){this.events[event]=callback;},
      pause(){this.paused=true;},
      play(){throw Error("No audio should be played");},
      removeAttribute(name){if(name==="src")this.src="";},
      load(){},
    });
    return elements.get(id);
  }
  get("discordFeedAuto").checked=true;
  get("discordFeedPrepareAhead").checked=false;
  get("discordFeedSpeechTimeoutMinutes").value="1";
  get("discordFeedPrepareQueueLimit").value="2";
  get("discordFeedReadyAudioQueueLimit").value="2";
  return {get,elements};
}
async function run(prepareAhead){
  const {get}=testDocument();
  get("discordFeedPrepareAhead").checked=prepareAhead;
  const statuses=[],diagnostics=[],requested=[];
  let deliveries=0,audioAttempts=0,playAttempts=0;
  const sandbox={window:{},console,Number,Array,String,Object,Boolean,Map,Set,JSON,
    Date,Promise,Math,URL:{revokeObjectURL(){throw Error("No WAV blobs")}},
    setTimeout,clearTimeout,
    fetch:async(url,options={})=>{
      requested.push(url);
      if(url==="/v1/jobs"&&options.method==="POST"){
        ++deliveries;
        const body=JSON.parse(options.body);
        assert.equal(body.source,"discord");
        return {ok:true,json:async()=>({
          speech_id:String(deliveries).repeat(32),state:"preparing"
        })};
      }
      if(url.startsWith("/v1/jobs/")&&!url.endsWith("/cancel")){
        assert(!url.includes("/audio"),"Text-only must never download audio");
        assert(!url.includes("/start-render"),"Text-only must never start a TTS render");
        const id=url.slice("/v1/jobs/".length).split("?")[0];
        return {ok:true,json:async()=>({
          speech_id:id,state:"displayed",
          display_text:"Translated "+Number(id[0])
        })};
      }
      if(url.endsWith("/cancel"))
        return {ok:true,json:async()=>({state:"cancelled"})};
      throw Error("Unexpected API request "+url);
    },
  };
  vm.createContext(sandbox);
  vm.runInContext(fs.readFileSync("web/emoji_pronunciation.js","utf8"),sandbox);
  vm.runInContext(fs.readFileSync("web/mode_inputs.js","utf8"),sandbox);
  const feed=sandbox.window.VoxModeInputs.attach({
    mode:"discord",el:get,
    clockLibrary:{attach(){return {
      setSpeech(){audioAttempts++;},
      clear(){},setDuration(){},
    }}},
    report(){throw Error("Text-only must never produce a playback event");},
    getSpeechPayload:(text,mode)=>({text,mode}),
    guard:mode=>mode==="discord",
    playAudio:async()=>{playAttempts++;throw Error("No audio!");},
    cancelAudio(){},
    onMessageState:(id,state)=>statuses.push([id,state]),
    onSpeechDiagnostic:entry=>diagnostics.push(entry),
    onPipelineState(){},
    onSpeechModelInputs(){throw Error("No model inputs without voice");},
  });
  for(let id=1;id<=3;id++)
    feed.receiveIncoming({message_id:String(id),text:"hello "+id,author:"Guest"},true);
  const deadline=Date.now()+6000;
  while(Date.now()<deadline && statuses.filter(x=>x[1]==="displayed").length<3)
    await new Promise(resolve=>setTimeout(resolve,25));
  assert.deepEqual(statuses.filter(x=>x[1]==="displayed").map(x=>x[0]),["1","2","3"]);
  assert.deepEqual(diagnostics.filter(x=>x.stage==="displayed").map(x=>x.text),
    ["Translated 1","Translated 2","Translated 3"]);
  assert.equal(audioAttempts,0);
  assert.equal(playAttempts,0);
  assert.equal(deliveries,3);
  assert.equal(feed.pendingAuto,0);
  assert.equal(feed.pipelineCount,0);
  assert(!requested.some(x=>x.includes("/audio")||x.includes("/start-render")));
}
(async()=>{
  await run(false);
  await run(true);
  console.log("PASS: Browser Live no-speech mode, prefetch/direct FIFO and 0 audio/render requests");
})().catch(error=>{console.error(error);process.exitCode=1});
