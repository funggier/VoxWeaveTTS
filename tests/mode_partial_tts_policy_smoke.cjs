// Live auto-read policy when TTS has partially/fully failed.
const assert=require("node:assert/strict");
const fs=require("node:fs");
const vm=require("node:vm");
const source=fs.readFileSync("web/mode_inputs.js","utf8");
const html=fs.readFileSync("web/index.html","utf8");
const tick=()=>new Promise(resolve=>setImmediate(resolve));
for(const prefix of ["live","youtubeBrowser","tiktokBrowser","tiktok",
                     "discord","discordClient"])
  assert.ok(html.includes('id="'+prefix+'FeedContinueOnTtsError"'),
            "new per-mode option "+prefix);
assert.ok(html.includes("อ่านต่อเมื่อเกิดความผิดพลาด"));

async function scenario({continued,firstFailure,attempts=["partial","ready"]}){
  const fields=new Map();
  function el(id){
    if(!fields.has(id))
      fields.set(id,{
        value:"",checked:false,disabled:false,paused:true,ended:false,
        currentTime:0,style:{display:"none"},textContent:"",
        events:{},src:"",
        addEventListener(name,cb){this.events[name]=cb;},
        pause(){this.paused=true;},
        removeAttribute(){this.src="";},
        load(){},
      });
    return fields.get(id);
  }
  el("liveFeedAuto").checked=true;
  el("liveFeedContinueOnTtsError").checked=continued;
  el("liveFeedReadSender").checked=false;
  el("liveFeedRandomThreshold").value="20";
  el("liveFeedRandomKeep").value="5";
  el("liveFeedReadComments").checked=true;
  const statuses=[];
  let requests=0;
  const calls=[];
  let urlcount=0;
  const browser={};
  const sandbox={
    window:browser,Blob,document:{hidden:false},
    URL:{createObjectURL(){return "blob:"+ ++urlcount;},revokeObjectURL(){}},
    async fetch(path,options={}){
      if(path==="/v1/jobs"){
        const payload=JSON.parse(options.body);
        requests++;
        calls.push(payload.text);
        return {ok:true,async json(){return {speech_id:String(requests).repeat(32)};}};
      }
      if(path.endsWith("/tts-inputs"))
        return {ok:true,async json(){return {
          available:true,state:"ready",speech_id:path.split("/")[3],inputs:[]
        };}};
      if(path.endsWith("/audio"))
        return {ok:true,async blob(){return new Blob(["RIFF"]);}};
      if(path.endsWith("/cancel"))
        return {ok:true,async json(){return{state:"cancelled"};}};
      if(path.startsWith("/v1/jobs/")){
        const type=attempts[Math.min(requests-1,attempts.length-1)];
        const state=type==="all_failed"?"failed":"ready";
        return {ok:true,async json(){return {
          state,speech_id:String(requests).repeat(32),
          error:state==="failed"?"all_tts_chunks_failed":undefined,
          partial_failure:type==="partial",
          failed_chunks:type==="partial"?1:state==="failed"?2:0,
          successful_chunks:state==="failed"?0:2,
          audio:{duration_ms:200,segments:[]},
        };}};
      }
      throw Error("unknown URL "+path);
    },
  };
  vm.createContext(sandbox);
  vm.runInContext(source,sandbox);
  const input=browser.VoxModeInputs.attach({
    mode:"live",el,
    clockLibrary:{attach(){return{clear(){},setSpeech(){}};}},
    report(){},guard:()=>true,
    getSpeechPayload:text=>({text,engine_id:"makham-paradee-cpu"}),
    playAudio:async audio=>{audio.paused=false;audio.ended=false;return true;},
    onMessageState:(id,state)=>statuses.push({id,state}),
  });
  input.receiveIncoming({message_id:"m1",author:"a",text:"first"},true);
  input.receiveIncoming({message_id:"m2",author:"b",text:"second"},true);
  for(let i=0;i<14;i++)await tick();
  assert.equal(requests,firstFailure==="all_failed"&&continued?2:1,
               "first message starts before the next accepted item");
  if(firstFailure==="partial"){
    assert.equal(input.pendingAuto,1);
    assert.equal(input.autoPaused,false,"partial WAV should play before pause");
    const audio=el("liveAudio");
    audio.paused=true; audio.ended=true;
    audio.events.ended();
    for(let i=0;i<14;i++)await tick();
    assert.ok(statuses.some(s=>s.id==="m1"&&s.state==="read"),"partial first completed");
    assert.equal(input.autoPaused,!continued);
    assert.equal(requests,continued?2:1,
                 "continue on partial only when switch enabled");
    if(!continued){
      assert.equal(input.pendingAuto,1,"the next message remains FIFO");
      await el("liveAutoRetry").events.click();
      for(let i=0;i<14;i++)await tick();
      assert.equal(requests,2,"resumes next, not re-synthesizing m1");
    }
  }else{
    assert.ok(statuses.some(s=>s.id==="m1"&&s.state==="skipped")===continued);
    assert.equal(input.autoPaused,!continued);
    assert.equal(requests,continued?2:1,
                 "all chunks fail skips without pause iff switch enabled");
    if(!continued){
      assert.equal(input.pendingAuto,2,"failed m1 is held for retry");
    }
  }
  return {requests,input,el,statuses,calls};
}

(async()=>{
  await scenario({continued:false,firstFailure:"partial"});
  await scenario({continued:true,firstFailure:"partial"});
  await scenario({continued:false,firstFailure:"all_failed",
                  attempts:["all_failed","ready"]});
  await scenario({continued:true,firstFailure:"all_failed",
                  attempts:["all_failed","ready"]});
  console.log("PASS: partial failure OFF pauses after WAV; ON continues; all failure OFF retries; ON skips and continues");
})().catch(error=>{console.error(error);process.exitCode=1;});
