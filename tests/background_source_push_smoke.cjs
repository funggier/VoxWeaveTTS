// SSE wake-up must drain chat and feed TTS while the main tab is hidden,
// without executing any throttled setInterval/setTimeout callback.
const assert=require("node:assert/strict");
const fs=require("node:fs");
const vm=require("node:vm");

async function run(){
 const controls=new Map();
 const get=id=>{
   if(!controls.has(id)){
     controls.set(id,{
       value:"",checked:false,disabled:false,textContent:"",
       children:[],events:{},
       addEventListener(name,fn){this.events[name]=fn;},
       appendChild(node){this.children.push(node);},
       replaceChildren(...children){this.children=[...children];},
     });
   }
   return controls.get(id);
 };
 get("youtubeBrowserFeedSourceId").value="abcDefGhI12";
 get("youtubeBrowserFeedMaxChars").value="280";
 get("youtubeBrowserFeedKeepRead").value="20";
 get("youtubeBrowserFeedAuto").checked=true;
 const incoming=[];
 const sourceQueue=[];
 let polls=0, intervalCalls=0, eventSource, lastInterval=null, windowFocus;
 const docEvents={};
 class FakeEventSource {
   constructor(url){
     assert.equal(url,"/v1/sources/stream?mode=all");
     this.readyState=1;
     this.handlers={};
     this.closed=false;
     eventSource=this;
   }
   addEventListener(name,callback){this.handlers[name]=callback;}
   close(){this.closed=true;this.readyState=2;}
   emit(data){this.handlers.source({data:JSON.stringify(data)});}
 }
 const doc={
   hidden:true,
   createElement(tag){return{
     tagName:tag.toUpperCase(),children:[],textContent:"",
     append(...children){this.children.push(...children);},
     addEventListener(){},
   };},
   addEventListener(name,fn){docEvents[name]=fn;},
 };
 const rootWindow={
   EventSource:FakeEventSource,
   addEventListener(name,fn){if(name==="focus")windowFocus=fn;},
 };
 const env={
   window:rootWindow,document:doc,JSON,Number,Promise,
   setInterval(fn,ms){assert.equal(ms,1200);lastInterval=fn;return 10;},
   clearInterval(){lastInterval=null;},
   async fetch(path,options){
     assert.equal(options.method,"POST");
     if(path==="/v1/sources/start")
       return {ok:true,async json(){return{state:"connecting",mode:"youtube_browser",pending:0};}};
     if(path==="/v1/sources/drain"){
       polls++;
       const received=sourceQueue.splice(0,10);
       return {ok:true,async json(){return{
         messages:received,
         status:{mode:"youtube_browser",state:"running",
           connection_phase:"ready",chat_mode:"live",
           page_visibility:"hidden",received:incoming.length+sourceQueue.length,
           pending:sourceQueue.length,discarded:0,next_poll_seconds:0},
       };}};
     }
     if(path==="/v1/sources/stop")
       return {ok:true,async json(){return{state:"stopped"};}};
     throw Error("Unexpected request "+path);
   },
 };
 vm.createContext(env);
 vm.runInContext(fs.readFileSync("web/source_feed.js","utf8"),env);
 const feed=env.window.VoxSourceFeed.attach({
   mode:"youtube_browser",el:get,guard:()=>true,
   credentials:()=>({mode:"youtube_browser",mode_token:"a".repeat(32)}),
   onMessage:(msg,auto)=>{
     assert.equal(auto,true,"hidden tab should retain auto-read");
     incoming.push(msg);
     return "queued";
   },
   onPick(){},onStop(){},
 });
 await feed.start();
 assert.ok(eventSource&&eventSource.readyState===1);
 assert.equal(polls,1);
 lastInterval?.(); // SSE is open, periodic fallback must not call fetch.
 await new Promise(resolve=>setImmediate(resolve));
 assert.equal(polls,1);
 for(let i=0;i<23;i++)sourceQueue.push({
   message_id:"push-"+i,author:"Viewer",text:"ส่งจาก Backend "+i
 });
 eventSource.emit({mode:"all",revision:8,sources:[{mode:"youtube_browser",revision:8,state:"running",pending:23}]});
 for(let i=0;i<15 && incoming.length!==23;i++)
   await new Promise(resolve=>setImmediate(resolve));
 assert.equal(incoming.length,23,"SSE must drain all messages even with hidden timers");
 assert.equal(new Set(incoming.map(x=>x.message_id)).size,23);
 assert.equal(doc.hidden,true);
 assert.equal(lastInterval!==null,true);
 assert.ok(polls>=4 && polls<=5,"SSE should drain batches without spin");
 assert.match(get("youtubeBrowserFeedStatus").textContent,/Live chat/);
 // Browser focus recovery still works after EventSource disconnects.
 eventSource.readyState=0;
 sourceQueue.push({message_id:"focus",author:"Viewer",text:"เมื่อกลับมา"});
 doc.hidden=false;
 docEvents.visibilitychange();
 for(let i=0;i<5 && incoming.length!==24;i++)
   await new Promise(resolve=>setImmediate(resolve));
 assert.equal(incoming.length,24);
 assert.equal(typeof windowFocus,"function");
 await feed.stop();
 assert.equal(eventSource.closed,true,"stop must close event stream");
 assert.equal(lastInterval,null);
 const count=polls;
 eventSource.emit({mode:"all",revision:999,sources:[{mode:"youtube_browser",revision:999,pending:1}]});
 await new Promise(resolve=>setImmediate(resolve));
 assert.equal(polls,count,"stale post-stop SSE must not drain messages");
 console.log("PASS: background-hidden YouTube source SSE drains all 23 messages without timers; focus recovery, token-scoped drain and stop cleanup");
}
run().catch(error=>{console.error(error);process.exitCode=1;});
