// Multiple source tabs share one SSE EventSource to avoid Firefox/Chrome
// per-origin HTTP connection exhaustion; token-guarded drain stays per mode.
const assert=require("node:assert/strict");
const fs=require("node:fs");
const vm=require("node:vm");
async function main(){
  const nodes=new Map(), sessions=new Map(), history=new Map();
  const events={},listeners=[];
  let opened=0,closed=0,sourceStream=null;
  const modes=["youtube_browser","discord"];
  const prefix={youtube_browser:"youtubeBrowser",discord:"discord"};
  const el=id=>{
    if(!nodes.has(id))nodes.set(id,{
      value:"",checked:false,disabled:false,textContent:"",
      children:[],events:{},
      addEventListener(name,fn){this.events[name]=fn;},
      replaceChildren(){this.children=[];},
      appendChild(child){this.children.push(child);},
    });
    return nodes.get(id);
  };
  for(const mode of modes){
    el(prefix[mode]+"FeedAuto").checked=true;
    el(prefix[mode]+"FeedMaxChars").value="280";
    el(prefix[mode]+"FeedSourceId").value=mode==="youtube_browser"?"abcDefGhI12":"123456789012345678";
  }
  const doc={
    hidden:true,addEventListener(name,fn){events[name]=fn;},
    createElement(tag){return{
      tagName:tag.toUpperCase(),textContent:"",children:[],
      append(...children){this.children.push(...children);},addEventListener(){},
    }},
  };
  class EventSource {
    constructor(path){
      assert.equal(path,"/v1/sources/stream?mode=all");
      opened++;this.readyState=1;this.handlers={};sourceStream=this;
    }
    addEventListener(name,fn){this.handlers[name]=fn;}
    close(){closed++;this.readyState=2;}
    push(revisions){
      const sources=modes.map(mode=>({
        mode,revision:revisions[mode]??0,pending:(sessions.get(mode)||[]).length,state:"running",
      }));
      this.handlers.source({data:JSON.stringify({mode:"all",revision:12,sources})});
    }
  }
  const api={
    window:{EventSource,addEventListener(){}},document:doc,
    JSON,Number,Date,Promise,
    setInterval(fn){listeners.push(fn);return listeners.length;},
    clearInterval(){},
    async fetch(url,options={}){
      const req=JSON.parse(options.body);
      const mode=req.mode;
      if(url==="/v1/sources/start"){
        assert.ok(modes.includes(mode));
        return{ok:true,async json(){return{mode,state:"connecting",pending:0}}};
      }
      if(url==="/v1/sources/drain"){
        assert.ok(modes.includes(mode));
        assert.equal(req.mode_token,mode==="discord"?"b".repeat(32):"a".repeat(32));
        history.get(mode).push("drain");
        const messages=sessions.get(mode).splice(0,10);
        return{ok:true,async json(){return{
          messages,status:{mode,state:"running",connection_phase:"ready",
            received:history.get(mode).length,pending:sessions.get(mode).length},
        }}};
      }
      if(url==="/v1/sources/stop")
        return{ok:true,async json(){return{state:"stopped"}}};
      throw Error("unexpected "+url);
    },
  };
  vm.createContext(api);
  vm.runInContext(fs.readFileSync("web/source_feed.js","utf8"),api);
  for(const mode of modes){sessions.set(mode,[]);history.set(mode,[]);}
  const feedFor=mode=>api.window.VoxSourceFeed.attach({
    mode,el,guard:()=>true,
    credentials:()=>({mode,mode_token:mode==="discord"?"b".repeat(32):"a".repeat(32)}),
    onMessage:()=> "queued",onPick(){},onStop(){},
  });
  const youtube=feedFor("youtube_browser"),discord=feedFor("discord");
  await youtube.start();await discord.start();
  assert.equal(opened,1,"two sources must share one socket");
  assert.equal(listeners.length,2,"timers are fallback only");
  assert.equal(history.get("youtube_browser").length,1);
  assert.equal(history.get("discord").length,1);
  // Initial SSE snapshot wakes every subscriber once after reconnection.
  sourceStream.push({youtube_browser:0,discord:0});
  await new Promise(r=>setImmediate(r));
  const ytBaseline=history.get("youtube_browser").length;
  const discordBaseline=history.get("discord").length;
  sessions.get("youtube_browser").push({message_id:"yt1",author:"A",text:"YT"});
  sourceStream.push({youtube_browser:1,discord:0});
  for(let i=0;i<5&&history.get("youtube_browser").length<ytBaseline+1;i++)
    await new Promise(r=>setImmediate(r));
  assert.equal(history.get("youtube_browser").length,ytBaseline+1);
  assert.equal(history.get("discord").length,discordBaseline,"unrelated mode revision should not drain");
  sessions.get("discord").push({message_id:"d1",author:"B",text:"Discord"});
  sourceStream.push({youtube_browser:1,discord:1});
  for(let i=0;i<5&&history.get("discord").length<discordBaseline+1;i++)
    await new Promise(r=>setImmediate(r));
  assert.equal(history.get("discord").length,discordBaseline+1);
  await youtube.stop();
  assert.equal(closed,0,"one source stopping must not tear down the shared SSE");
  await discord.stop();
  assert.equal(closed,1,"last subscriber must close shared EventSource");
  console.log("PASS: two modes share one SSE connection; revisions wake only target source, per-mode owner drain and unsubscribe");
}
main().catch(error=>{console.error(error);process.exitCode=1;});