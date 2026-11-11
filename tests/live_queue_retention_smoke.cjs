// Shared Live / Discord Bot / Discord Desktop queue and read-history regression.
// Runs offline with a fake local HTTP server and a fake HTMLAudioElement.
const assert=require("node:assert/strict");
const fs=require("node:fs");
const vm=require("node:vm");
const html=fs.readFileSync("web/index.html","utf8");
const INPUTS=fs.readFileSync("web/mode_inputs.js","utf8");
const FEED=fs.readFileSync("web/source_feed.js","utf8");

const tick=()=>new Promise(resolve=>setImmediate(resolve));

async function exercise(mode){
  const prefix=mode==="discord_client"?"discordClient":mode;
  assert.ok(html.includes('id="'+prefix+'FeedKeepRead"'),"history input missing for "+mode);
  assert.match(html,new RegExp('id="'+prefix+'FeedKeepRead"[^>]*value="20"'));
  assert.ok(html.includes('id="'+prefix+'FeedQueueStatus"'),"summary missing for "+mode);

  const elements=new Map();
  function createElement(tag){
    return {
      tagName:tag.toUpperCase(),className:"",type:"",textContent:"",
      children:[],events:{},
      addEventListener(name,fn){this.events[name]=fn;},
      append(...items){this.children.push(...items);},
      appendChild(item){this.children.push(item);},
      replaceChildren(){this.children=[];},
    };
  }
  function el(id){
    if(!elements.has(id)){
      const element={
        value:"",checked:false,disabled:false,textContent:"",
        style:{display:"none"},src:"",paused:true,ended:false,
        currentTime:0,events:{},children:[],playCalls:0,
        addEventListener(event,fn){this.events[event]=fn;},
        appendChild(child){this.children.push(child);},
        replaceChildren(){this.children=[];},
        pause(){this.paused=true;},
        async play(){this.paused=false;this.ended=false;this.playCalls++;},
        removeAttribute(name){if(name==="src")this.src="";},
        load(){},
      };
      elements.set(id,element);
    }
    return elements.get(id);
  }
  el(prefix+"FeedAuto").checked=true;
  el(prefix+"FeedKeepRead").value="2";
  el(prefix+"FeedMaxChars").value="240";
  el(prefix+"FeedSourceId").value="100000000000000001";
  el(prefix+"FeedCredential").value="fake-provider-credential";
  el(prefix+"FeedAppId").value="100000000000000005";
  el(prefix+"FeedAppSecret").value="fake-client-secret-12345";
  el(prefix+"FeedRedirect").value="http://127.0.0.1:8765";

  const messages=Array.from({length:20},(_,i)=>({
    message_id:"message-"+i,author:"ทดสอบ",text:"ข้อความที่ "+i,
  }));
  const batches=[messages.slice(0,10),messages.slice(10)];
  const speech=[];
  const urls=new Set();
  let timer=null;
  let feed;
  let modeController;
  const sandbox={
    window:{},document:{createElement},JSON,Number,Blob,Promise,
    URL:{
      createObjectURL(data){assert.ok(data instanceof Blob);const name="blob:"+urls.size;urls.add(name);return name;},
      revokeObjectURL(uri){urls.delete(uri);},
    },
    setTimeout(fn){queueMicrotask(fn);return 1;},
    setInterval(fn){timer=fn;return 1;},
    clearInterval(){timer=null;},
    async fetch(path,options={}){
      if(path==="/v1/sources/start")
        return {ok:true,async json(){return {mode,state:"connecting",pending:0};}};
      if(path==="/v1/sources/drain")
        return {ok:true,async json(){return {
          messages:batches.shift()||[],
          status:{state:"running",pending:0,received:20,discarded:0,next_poll_seconds:5},
        };}};
      if(path==="/v1/sources/stop")
        return {ok:true,async json(){return {state:"stopped",pending:0};}};
      if(path==="/v1/jobs"&&options.method==="POST"){
        const body=JSON.parse(options.body);
        speech.push(body);
        return {ok:true,async json(){return {speech_id:String(speech.length).repeat(32),state:"queued"};}};
      }
      if(path.endsWith("/cancel"))
        return {ok:true,async json(){return {state:"cancelled"};}};
      if(path.endsWith("/audio"))
        return {ok:true,async blob(){return new Blob(["WAV"]);}};
      if(path.startsWith("/v1/jobs/"))
        return {ok:true,async json(){return {speech_id:path.split("/").at(-1),
          state:"ready",audio:{duration_ms:100,segments:[]}};}};
      throw Error("Unexpected fake API "+path);
    },
  };
  vm.createContext(sandbox);
  vm.runInContext(INPUTS,sandbox);
  vm.runInContext(FEED,sandbox);
  modeController=sandbox.window.VoxModeInputs.attach({
    mode,el,guard:()=>true,getSpeechPayload:text=>({text,engine_id:"test-engine"}),
    clockLibrary:{attach(){return{clear(){},setSpeech(){}};}},
    report(){},
    onMessageState:(id,state)=>feed?.setMessageState(id,state),
  });
  feed=sandbox.window.VoxSourceFeed.attach({
    mode,el,guard:()=>true,
    credentials:()=>({mode,mode_token:"a".repeat(32)}),
    onMessage:(message,auto)=>modeController.receiveIncoming(message,auto),
    onPick:()=>{},
    onStop:()=>{modeController.clearAutoQueue({includeActive:true});modeController.stop({discard:true});},
  });
  await feed.start();   // first 10 messages
  await feed.poll();    // remaining 10 messages
  await tick();await tick();
  assert.equal(modeController.pendingAuto,12,mode+" must preserve first 12 waiting");
  assert.equal(modeController.skippedOverflow,7,mode+" must drop only 7 new overflow messages");
  assert.equal(speech.length,1,"only one TTS generation may start before audio ends");
  assert.equal(speech[0].text,"ข้อความที่ 0");
  assert.equal(el(prefix+"Audio").playCalls,1);
  assert.equal(feed.visible.length,20);
  assert.equal(feed.visible.find(x=>x.message_id==="message-0").state,"reading");
  assert.equal(feed.visible.find(x=>x.message_id==="message-12").state,"queued");
  assert.equal(feed.visible.find(x=>x.message_id==="message-13").state,"skipped");
  assert.ok(el(prefix+"FeedQueueStatus").textContent.includes("คิวรออ่าน 12/12"));
  assert.ok(el(prefix+"FeedQueueStatus").textContent.includes("ข้ามเพราะคิวเต็ม 7"));

  const endAudio=async()=>{
    const audio=el(prefix+"Audio");
    audio.paused=true;audio.ended=true;
    audio.events.ended();
    await tick();await tick();
  };
  await endAudio();
  assert.equal(speech.length,2);
  assert.equal(speech[1].text,"ข้อความที่ 1");
  await endAudio();
  await endAudio();
  assert.equal(speech.length,4,"audio ended must advance serially");
  assert.equal(speech[3].text,"ข้อความที่ 3");
  assert.equal(feed.visible.filter(x=>x.state==="read").length,2,
               "read history must enforce user limit of 2");
  assert.ok(!feed.visible.some(x=>x.message_id==="message-0"),
            "oldest completed speech should be pruned");
  assert.equal(feed.visible.find(x=>x.message_id==="message-12").state,"queued",
               "queued unread messages cannot be pruned with read history");

  // Changing the read-history limit applies immediately, but never prunes
  // waiting messages. Zero means retain no finished messages.
  el(prefix+"FeedKeepRead").value="0";
  el(prefix+"FeedKeepRead").events.input();
  assert.equal(feed.visible.filter(x=>x.state==="read").length,0);
  assert.ok(feed.visible.some(x=>x.message_id==="message-12"));

  // Turning auto-read off pauses advancement without deleting the backlog.
  el(prefix+"FeedAuto").checked=false;
  await endAudio();
  assert.equal(speech.length,4);
  assert.equal(modeController.pendingAuto,9);
  // Even with a high-volume stream of messages not selected for auto-read,
  // pending audio work must remain visible. Passive/manual history is capped.
  batches.push(Array.from({length:30},(_,i)=>({
    message_id:"manual-"+i,author:"ผู้ชม",text:"ข้อความเลือกเอง "+i,
  })));
  await feed.poll();
  assert.equal(feed.visible.filter(x=>x.state==="manual").length,25);
  assert.equal(feed.visible.filter(x=>x.state==="queued").length,9);
  assert.ok(feed.visible.some(x=>x.message_id==="message-12"));
  el(prefix+"FeedAuto").checked=true;
  el(prefix+"FeedAuto").events.change();
  await tick();await tick();
  assert.equal(speech.length,5,"re-enabling auto-read must resume retained backlog");
  assert.equal(speech[4].text,"ข้อความที่ 4");
  assert.ok(el(prefix+"FeedQueueStatus").textContent.includes("กำลังเตรียม/อ่าน 1"));

  await feed.stop();
  assert.equal(modeController.pendingAuto,0,"stop must cancel the queued backlog");
  assert.equal(feed.visible.filter(x=>["queued","preparing","reading"].includes(x.state)).length,0,
               "stop must mark cancelled items instead of mislabelling them read");
  assert.equal(timer,null);
  assert.equal(el(prefix+"FeedAuto").checked,true,
               "feed stop preserves the user's auto-read preference");
  assert.equal(speech.length,5,"no new speech after feed stop");
  assert.ok(feed.visible.length<=25,
            "passive/skipped history remains bounded even after stop");
  console.log("PASS:",mode,"bounded FIFO queue, read-only history pruning, pause/resume and stop");
}

(async()=>{
  for(const mode of ["live","discord","discord_client"])await exercise(mode);
})().catch(e=>{console.error(e);process.exitCode=1;});
