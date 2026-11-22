"use strict";
const assert=require("node:assert/strict");
const fs=require("node:fs");
const vm=require("node:vm");
const source=fs.readFileSync("web/source_feed.js","utf8");
const nodes=new Map();
function el(id){
  if(!nodes.has(id))nodes.set(id,{
    value:"",checked:false,disabled:false,textContent:"",events:{},
    children:[],files:[],addEventListener(type,fn){this.events[type]=fn;},
    replaceChildren(){this.children=[]},
    appendChild(node){this.children.push(node)}
  });
  return nodes.get(id);
}
el("tiktokFeedSourceId").value="ws://localhost:21213/";
el("tiktokFeedMaxChars").value="240";
el("tiktokFeedKeepRead").value="20";
el("tiktokFeedAuto").checked=true;
let sockets=0,timers=0,started=0,stopped=0,deliveries=0;
const requests=[];
const win={
  VoxOutputMode:{current:"computer"},
  WebSocket:class{constructor(){sockets++}},
  addEventListener(){},
};
const sandbox={
  window:win,JSON,Number,Promise,console,
  document:{hidden:false,addEventListener(){},
    createElement(tag){return{className:"",textContent:"",children:[],
      appendChild(x){this.children.push(x)},append(...xs){this.children.push(...xs)}}}},
  async fetch(url,options={}){
    const body=options.body?JSON.parse(options.body):undefined;
    requests.push({url,method:options.method||"GET",body});
    if(url==="/v1/sources/start"){
      assert.equal(body.mode,"tiktok");
      assert.equal(body.source_id,"ws://localhost:21213/");
      started++;
      return {ok:true,json:async()=>({state:"connecting",mode:"tiktok"})};
    }
    if(url==="/v1/sources/status?mode=tiktok")
      return {ok:true,json:async()=>({
        state:"running",mode:"tiktok",source_id:"ws://localhost:21213/",
        received:2,discarded:0,pending:1
      })};
    if(url==="/v1/runtime/source/stop"){
      assert.equal(options.headers["X-VoxWeaveTTS-Intent"],"stop-core-source");
      assert.equal(body.mode,"tiktok");
      stopped++;
      return {ok:true,json:async()=>({
        state:"stopped",mode:"tiktok",cancelled_jobs:1
      })};
    }
    throw Error("unexpected route "+url);
  },
  setInterval(){timers++;throw Error("TikFinity Core UI must not create timers")},
  clearInterval(){},
};
vm.createContext(sandbox);
vm.runInContext(source,sandbox);
const feed=win.VoxSourceFeed.attach({
  mode:"tiktok",el,credentials:()=>({mode:"tiktok",mode_token:"owner"}),
  guard:()=>true,onConnect:async()=>{},
  onMessage(){deliveries++},onStop(){},
});
(async()=>{
  await feed.start();
  assert.equal(started,1);
  assert.equal(feed.connected,true);
  assert.equal(sockets,0,"Browser must not connect local WebSocket in Core mode");
  assert.equal(timers,0,"no Browser-side TikFinity poll loop");
  assert.equal(deliveries,0,"the Core consumes pending chats");
  assert(requests.some(x=>x.url==="/v1/sources/status?mode=tiktok"));
  assert(requests.every(x=>x.url!=="/v1/sources/drain"));
  await feed.stop();
  assert.equal(stopped,1);
  assert.equal(feed.connected,false);
  assert.equal(sockets,0);
  console.log("PASS: TikFinity WebSocket/Core source ownership; Browser only starts, observes and stops; zero duplicate WS/timers/drains");
})().catch(error=>{console.error(error);process.exitCode=1});
