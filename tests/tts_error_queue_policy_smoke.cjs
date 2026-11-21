/* Live TTS failure switch: per-mode FIFO and three error outcomes.
 * Run across all six source modes without network or installed voices.
 */
"use strict";
const assert=require("node:assert/strict");
const {attach}=require("../web/mode_inputs.js");
const tick=()=>new Promise(resolve=>setImmediate(resolve));
const modes=["live","youtube_browser","tiktok","tiktok_browser","discord","discord_client"];

async function scenario(mode,first,continueOnError){
  const prefix=mode==="youtube_browser"?"youtubeBrowser":
    mode==="tiktok_browser"?"tiktokBrowser":
    mode==="discord_client"?"discordClient":mode;
  const elements=new Map(),states=new Map(),diagnostics=[],spoken=[];
  let calls=0,playCount=0;
  const get=id=>{
    if(!elements.has(id))elements.set(id,{
      value:"",checked:false,disabled:false,textContent:"",
      style:{},src:"",href:"",paused:true,ended:false,events:{},
      addEventListener(event,cb){this.events[event]=cb;},
      pause(){this.paused=true;},
      load(){},removeAttribute(){},
      fire(event){return this.events[event]?.();}
    });
    return elements.get(id);
  };
  get(prefix+"FeedAuto").checked=true;
  get(prefix+"FeedContinueOnTtsError").checked=continueOnError;
  const audio=get(prefix+"Audio");
  const oldFetch=global.fetch;
  global.fetch=async(path,options={})=>{
    if(path==="/v1/jobs"){
      const payload=JSON.parse(options.body);
      assert.ok(payload.text);
      const id="job-"+(++calls);
      return {ok:true,async json(){return {speech_id:id,state:"queued"};}};
    }
    if(path.endsWith("/tts-inputs")){
      assert.equal(options.headers["X-VoxWeaveTTS-Intent"],"inspect-tts-inputs");
      return {ok:true,async json(){return {
        state:"ready",speech_id:path.split("/")[3],available:true,
        inputs:[
          {language:"th",engine_id:"a",voice_id:"v",text:"เสียงสำเร็จ",success:true},
          {language:"en",engine_id:"b",voice_id:"w",text:"failed",success:false},
        ]
      };}};
    }
    if(path.endsWith("/audio"))
      return {ok:true,async blob(){return new Blob(["WAV"]);}};
    if(path.endsWith("/cancel"))
      return {ok:true,async json(){return {state:"cancelled"};}};
    if(path.startsWith("/v1/jobs/")){
      assert.match(path,/\?wait=1$/);
      const result=calls===1?first:"success";
      return {ok:true,async json(){
        if(result==="all")return {state:"failed",error:"all_tts_chunks_failed",
          successful_chunks:0,failed_chunks:2};
        if(result==="generic")return {state:"failed",error:"speech rendering failed"};
        return {
          state:"ready",speech_id:path.split("/")[3],
          partial_failure:result==="partial",successful_chunks:result==="partial"?1:2,
          failed_chunks:result==="partial"?1:0,
          audio:{duration_ms:10,segments:[]}
        };
      }};
    }
    throw Error("Unexpected path "+path);
  };
  const api=attach({
    mode,el:get,report(){},guard:()=>true,clockLibrary:{attach(){return{
      clear(){},setSpeech(){}
    };}},
    getSpeechPayload:text=>({text,mode}),
    onMessageState:(id,state)=>states.set(id,state),
    onSpeechDiagnostic:record=>diagnostics.push(record),
    onSpeechModelInputs:(id,parts)=>spoken.push({id,parts}),
    async playAudio(player){playCount++;player.paused=false;player.ended=false;return true;}
  });
  const finish=async()=>{
    audio.paused=true;audio.ended=true;
    await audio.fire("ended");await tick();await tick();
  };
  try{
    assert.equal(api.receiveIncoming({message_id:"first",text:"first"},true),"queued");
    assert.equal(api.receiveIncoming({message_id:"second",text:"second"},true),"queued");
    for(let i=0;i<6;i++)await tick();
    assert.equal(calls,["all","generic"].includes(first)&&continueOnError?2:1);
    if(first==="partial"){
      assert.equal(playCount,1);
      assert.equal(states.get("first"),"reading");
      assert.equal(spoken.length,1);
      assert.deepEqual(spoken[0].parts.map(part=>part.success),[true,false]);
      assert.equal(api.pendingAuto,1);
      await finish();
      assert.equal(states.get("first"),"read");
      assert.equal(api.autoPaused,!continueOnError);
      assert.equal(calls,continueOnError?2:1);
      if(!continueOnError){
        assert.equal(api.pendingAuto,1);
        assert.match(get(prefix+"Status").textContent,/อ่านอัตโนมัติต่อ/);
        await get(prefix+"AutoRetry").fire("click");
        for(let i=0;i<5;i++)await tick();
        assert.equal(calls,2);
        assert.equal(api.autoPaused,false);
      }
      assert.equal(states.get("second"),"reading");
      await finish();
      assert.equal(states.get("second"),"read");
      assert.equal(api.autoPaused,false);
      assert.equal(calls,2,"must not repeat partially spoken job");
    }else if(first==="all"){
      assert.equal(playCount,continueOnError?1:0);
      assert.equal(api.autoPaused,!continueOnError);
      assert.equal(states.get("first"),continueOnError?"skipped":"queued");
      assert.equal(api.pendingAuto,continueOnError?0:2);
      assert.equal(calls,continueOnError?2:1);
      assert.equal(diagnostics.findLast(x=>x.stage==="failed")?.message_id,"first");
      if(continueOnError){
        assert.equal(states.get("second"),"reading");
        await finish();
        assert.equal(states.get("second"),"read");
        assert.equal(api.autoPaused,false);
        assert.equal(calls,2);
      }
    }else if(first==="generic"){
      assert.equal(api.autoPaused,!continueOnError);
      assert.equal(api.pendingAuto,continueOnError?0:2);
      assert.equal(playCount,continueOnError?1:0);
      assert.equal(states.get("first"),continueOnError?"skipped":"queued");
      if(continueOnError){
        assert.equal(states.get("second"),"reading");
        await finish();
        assert.equal(states.get("second"),"read");
        assert.equal(api.autoPaused,false);
      }
    }
    return {mode,first,continueOnError,calls,playCount};
  }finally{global.fetch=oldFetch;}
}
(async()=>{
  for(const mode of modes){
    for(const first of ["partial","all","generic"]){
      for(const option of [false,true]){
        await scenario(mode,first,option);
      }
    }
  }
  console.log("PASS: six modes x 6 partial/all/generic TTS failure cases, auto-continue vs pause, FIFO and no duplicate playback");
})().catch(e=>{console.error(e);process.exitCode=1;});
