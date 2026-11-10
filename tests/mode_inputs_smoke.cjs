// Engine-neutral Live/Discord simulator: independent sources and player state.
const assert=require("node:assert/strict");
const fs=require("node:fs");
const vm=require("node:vm");
async function main(){
  const code=fs.readFileSync("web/mode_inputs.js","utf8");
  const elements=new Map();
  const get=id=>{
    if(!elements.has(id)){
      elements.set(id,{
        value:"",textContent:"",disabled:false,
        style:{display:"none"},src:"",paused:true,events:{},
        addEventListener(name,fn){this.events[name]=fn},
        pause(){this.paused=true},async play(){this.paused=false},removeAttribute(name){if(name==="src")this.src=""},
        load(){},
      });
    }
    return elements.get(id);
  };
  const reports=[],payloads=[],created=[],clockCalls=[],cancelled=[];
  let current="live", renderCount=0;
  const blobUrl=new Set();
  const sandbox={
    window:{},JSON,URL:{
      createObjectURL(blob){assert.ok(blob instanceof Blob);const u="blob:"+blobUrl.size;blobUrl.add(u);return u;},
      revokeObjectURL(url){blobUrl.delete(url);},
    },Blob,Promise,Number,
    setTimeout(fn){queueMicrotask(fn);return 1;},
    async fetch(path,opts={}){
      if(path==="/v1/jobs"&&opts.method==="POST"){
        const body=JSON.parse(opts.body);
        payloads.push(body);
        const id=String(payloads.length).repeat(32);
        created.push(id);
        return{ok:true,async json(){return{speech_id:id,state:"queued"};}};
      }
      if(path.endsWith("/cancel")){
        cancelled.push(path);
        return{ok:true,async json(){return{state:"cancelled"};}};
      }
      if(path.endsWith("/audio"))
        return{ok:true,async blob(){return new Blob(["RIFF-test"]);}};
      if(path.startsWith("/v1/jobs/"))
        return{ok:true,async json(){return{
          speech_id:path.split("/").at(-1),state:"ready",audio:{
            duration_ms:1000,segments:[{kind:"speech",display_text:"ทดสอบ",
            start_ms:0,end_ms:1000}]},
        };}};
      throw Error("Unexpected URL "+path);
    },
  };
  const library={
    attach(audio,report,onState){
      clockCalls.push(audio);
      return{
        setSpeech(id,audioInfo){
          renderCount++;
          assert.ok(audioInfo.duration_ms);
          onState({text:"ทดสอบ"});
        },
        clear(){onState({text:""});},
      };
    },
  };
  vm.createContext(sandbox);
  vm.runInContext(code,sandbox);
  const attach=mode=>sandbox.window.VoxModeInputs.attach({
    mode,el:get,clockLibrary:library,
    report:(payload,m)=>reports.push({payload,mode:m}),
    getSpeechPayload:text=>({text,engine_id:"shared-engine"}),
    guard:mode=>mode===current,
  });
  const live=attach("live");
  const discord=attach("discord");
  get("liveText").value="ข้อความจากไลฟ์";
  get("discordText").value="ข้อความจาก Discord";
  await live.submit();
  assert.equal(payloads[0].text,"ข้อความจากไลฟ์");
  assert.equal(payloads[0].source,"youtube-live");
  assert.equal(get("liveAudio").style.display,"block");
  assert.equal(get("liveSubtitle").textContent,"ทดสอบ");
  await get("livePlay").events.click();
  assert.equal(get("liveAudio").paused,false,"explicit play button should start audio");
  const first=live.jobId;
  current="discord";
  live.suspend();
  assert.equal(get("liveAudio").paused,true);
  assert.equal(get("liveSubtitle").textContent,"");
  assert.equal(get("liveText").value,"ข้อความจากไลฟ์",
    "mode switch preserves its own editable text");
  live.resume();
  assert.equal(renderCount,2,"a ready WAV can be restored on return");
  await discord.submit();
  assert.equal(payloads[1].text,"ข้อความจาก Discord");
  assert.equal(payloads[1].source,"discord");
  assert.equal(discord.jobId,created[1]);
  assert.notEqual(live.jobId,discord.jobId);
  assert.equal(get("liveText").value,"ข้อความจากไลฟ์");
  assert.equal(get("discordText").value,"ข้อความจาก Discord");
  discord.stop({discard:true});
  assert.equal(get("discordAudio").style.display,"none");
  assert.equal(discord.jobId,null);
  assert.equal(get("discordText").value,"ข้อความจาก Discord");
  assert.ok(blobUrl.size<=1);
  console.log("PASS: independent Live/Discord drafts, global engine payload, own audio clock, stop-on-switch and no live connector claims");
}
main().catch(error=>{console.error(error);process.exitCode=1;});