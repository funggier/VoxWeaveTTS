// End-to-end source diagnostic: exact attempted text, failed TTS, retry and
// independently limited successfully-spoken history, without mutating chat UI.
const assert=require("node:assert/strict");
const fs=require("node:fs");
const vm=require("node:vm");
const html=fs.readFileSync("web/index.html","utf8");
const scriptInputs=fs.readFileSync("web/mode_inputs.js","utf8");
const scriptFeed=fs.readFileSync("web/source_feed.js","utf8");
for(const id of ["liveFeedCurrentStatus","liveFeedCurrentText","liveFeedReadItems","liveFeedItems"])
  assert.ok(html.includes('id="'+id+'"'),id);
const tick=()=>new Promise(r=>setImmediate(r));
const elements=new Map();
function dom(id){
  if(!elements.has(id)){
    elements.set(id,{
      value:"",checked:false,disabled:false,paused:true,ended:false,
      currentTime:0,textContent:"",style:{display:"none"},
      children:[],events:{},src:"",
      append(...children){this.children.push(...children);},
      appendChild(child){this.children.push(child);},
      replaceChildren(){this.children=[];},
      addEventListener(name,fn){this.events[name]=fn;},
      pause(){this.paused=true;},
      removeAttribute(){this.src="";},
      load(){},
    });
  }
  return elements.get(id);
}
function createElement(tag){
  return {tagName:tag,textContent:"",children:[],events:{},
    append(...children){this.children.push(...children);},
    appendChild(child){this.children.push(child);},
    addEventListener(name,fn){this.events[name]=fn;}};
}
dom("liveFeedAuto").checked=true;
dom("liveFeedKeepRead").value="1";
dom("liveFeedMaxChars").value="8000";
dom("liveFeedSourceId").value="VID12345678";
dom("liveFeedCredential").value="credential-in-memory-only";
dom("liveFeedRandomThreshold").value="20";
dom("liveFeedRandomKeep").value="5";
dom("liveFeedReadSender").checked=true;
const rawText="ข้อความนี้ควรปรากฏในช่องวิเคราะห์ข้อผิดพลาด";
let jobAttempts=0;
let feed=null;
const incoming=[
 {message_id:"failed-once",author:"viewerA",text:rawText},
];
const stored=[];
let blobCount=0;
const sandbox={
  window:{},
  document:{createElement,hidden:false},
  Blob,URL:{
    createObjectURL(){return "blob:"+ ++blobCount;},
    revokeObjectURL(){},
  },
  setTimeout(fn){queueMicrotask(fn);return 1;},
  setInterval(){return 1;},clearInterval(){},
  async fetch(path,opts={}){
    if(path==="/v1/sources/start")
      return {ok:true,async json(){return {mode:"live",state:"running",pending:1};}};
    if(path==="/v1/sources/drain")
      return {ok:true,async json(){return {
        messages:incoming.splice(0),status:{state:"running",pending:0,received:1,discarded:0}
      };}};
    if(path==="/v1/jobs"){
      const body=JSON.parse(opts.body);
      stored.push(body);
      jobAttempts++;
      return {ok:true,async json(){return {speech_id:String(jobAttempts).repeat(32),state:"queued"};}};
    }
    if(path.startsWith("/v1/jobs/")&&path.endsWith("/audio"))
      return {ok:true,async blob(){return new Blob(["WAV"]);}};
    if(path.startsWith("/v1/jobs/")&&path.endsWith("/cancel"))
      return {ok:true,async json(){return {state:"cancelled"};}};
    if(path.startsWith("/v1/jobs/")){
      const current=jobAttempts;
      return {ok:true,async json(){return current===1?
        {state:"failed",error:"worker_inference_failed"}:
        {state:"ready",speech_id:String(current).repeat(32),
         audio:{duration_ms:200,segments:[]}};}};
    }
    throw Error("Unexpected endpoint "+path);
  }
};
vm.createContext(sandbox);
vm.runInContext(scriptInputs,sandbox);
vm.runInContext(scriptFeed,sandbox);
const input=sandbox.window.VoxModeInputs.attach({
  mode:"live",el:dom,guard:()=>true,
  clockLibrary:{attach(){return{clear(){},setSpeech(){}};}},
  report(){},
  getSpeechPayload:text=>({text,engine_id:"makham-paradee-cpu"}),
  playAudio:async audio=>{audio.paused=false;return true;},
  onMessageState:(id,state)=>feed?.setMessageState(id,state),
  onSpeechDiagnostic:item=>feed?.setSpeechDiagnostic(item),
});
feed=sandbox.window.VoxSourceFeed.attach({
  mode:"live",el:dom,guard:()=>true,
  credentials:()=>({mode:"live",mode_token:"a".repeat(32)}),
  onMessage:(item,automatic)=>input.receiveIncoming(item,automatic),
  onPick:entry=>input.pickMessage(entry),
  onStop:()=>input.clearAutoQueue({includeActive:true}),
});
(async()=>{
  await feed.start();
  for(let i=0;i<10;i++)await tick();
  assert.equal(jobAttempts,1);
  assert.match(dom("liveFeedCurrentText").textContent,/ข้อความนี้ควรปรากฏ/);
  assert.match(dom("liveFeedCurrentStatus").textContent,/ผิดพลาด/);
  assert.match(dom("liveFeedCurrentStatus").textContent,/worker_inference_failed/);
  assert.equal(dom("liveFeedReadItems").children.length,0,"failed synth is not read");
  assert.equal(feed.visible.length,1,"original chat row preserved");
  assert.equal(input.pendingAuto,1,"failed message can be retried");
  await dom("liveAutoRetry").events.click();
  for(let i=0;i<10;i++)await tick();
  assert.equal(jobAttempts,2);
  assert.equal(dom("liveFeedReadItems").children.length,0,
               "WAV ready or playing is not yet completed");
  const audio=dom("liveAudio");
  audio.paused=true;audio.ended=true;
  audio.events.ended();
  for(let i=0;i<4;i++)await tick();
  assert.equal(dom("liveFeedReadItems").children.length,1);
  assert.match(dom("liveFeedReadItems").children[0].textContent,/ข้อความนี้ควรปรากฏ/);
  assert.equal(feed.visible.filter(x=>x.state==="read").length,1);
  dom("liveFeedKeepRead").value="0";
  dom("liveFeedKeepRead").events.input();
  assert.equal(dom("liveFeedReadItems").children.length,0);
  assert.equal(feed.visible.filter(x=>x.state==="read").length,0);
  assert.ok(stored[0].text.includes(rawText));
  assert.equal(stored[0].engine_id,"makham-paradee-cpu");
  console.log("PASS: failed TTS shows exact speech text; retry, actual audio ended, separate read history and history limit");
})().catch(e=>{console.error(e);process.exitCode=1;});
