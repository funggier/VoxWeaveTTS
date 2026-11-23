// No network or browser dependency: source connector UI and consent semantics.
const assert=require("node:assert/strict");
const fs=require("node:fs");
const vm=require("node:vm");
async function main(){
 const html=fs.readFileSync("web/index.html","utf8");
 for(const mode of ["live","discord"]){
   for(const suffix of ["FeedStart","FeedStop","FeedSourceId",
     "FeedCredential","FeedBlocked","FeedMaxChars","FeedAuto",
     "FeedStatus","FeedItems"]){
       assert.match(html,new RegExp('id="'+mode+suffix+'"'));
   }
 }
 assert.match(html,/src="\/source_feed\.js"/);
 const records=new Map();
 const createTag=tag=>({
   tagName:tag.toUpperCase(),children:[],textContent:"",events:{},
   append(...nodes){this.children.push(...nodes);},
   replaceChildren(){this.children=[];},
   addEventListener(event,fn){this.events[event]=fn;},
 });
 const el=id=>{
   if(!records.has(id)){
     records.set(id,{
       value:"",checked:false,textContent:"",disabled:false,children:[],
       events:{},replaceChildren(){this.children=[];},
       appendChild(child){this.children.push(child);},
       addEventListener(event,fn){this.events[event]=fn;},
     });
   }
   return records.get(id);
 };
 el("liveFeedSourceId").value="Cg0K-live-test";
 el("liveFeedCredential").value="temporary-token-never-persist";
 el("liveFeedBlocked").value="สแปม, ลบ";
 el("liveFeedMaxChars").value="240";
 el("liveFeedAuto").checked=true;
 let active=true;
 let timer=null,claims=0,resets=0,clearDrains=false,deferDrain=false,releaseDrain=null;
 let localToken="a".repeat(32),serverToken="stale-backend-token";
 const requested=[],selected=[],received=[],stopped=[];
 const sandbox={
   window:{},document:{createElement:createTag},JSON,Number,
   setInterval(fn,ms){assert.equal(ms,1200);timer=fn;return 3;},
   clearInterval(){timer=null;},
   async fetch(path,options){
     assert.equal(options.method,"POST");
     const payload=JSON.parse(options.body);
     requested.push({path,payload,headers:options.headers});
     if(path==="/v1/sources/start"){
       clearDrains=false;
       if(payload.mode_token!==serverToken)
         return{ok:false,status:409,async json(){return{error:"source monitor requires the active mode owner token"};}};
       return{ok:true,async json(){return{
         mode:"live",state:"connecting",source_id:payload.source_id,pending:0,
       };}};
     }
     if(path==="/v1/sources/drain"){
       // Capture the batch at request time: this is essential to verify that
       // an in-flight response from BEFORE the queue reset is ignored.
       const messages=clearDrains?[]:[
         {message_id:"x1",author:"คุณA",text:"สวัสดีครับ"},
         {message_id:"x2",author:"คุณB",text:"<img src=x onerror=alert(1)>"},
       ];
       if(deferDrain){
         deferDrain=false;
         await new Promise(resolve=>{releaseDrain=resolve;});
       }
       return {ok:true,async json(){return{
         messages,status:{state:"running",pending:0,received:2,
                          discarded:0,next_poll_seconds:5},
       };}};
     }
     if(path==="/v1/sources/reset"){
       assert.equal(options.headers["X-VoxWeaveTTS-Intent"],"reset-live-source-queue");
       assert.equal(payload.mode_token,serverToken);
       clearDrains=true;
       return{ok:true,async json(){return{state:"reset",cleared:4,pending:0,connected:true};}};
     }
     if(path==="/v1/sources/stop")
       return{ok:true,async json(){return{state:"stopped",pending:0};}};
     throw Error("unexpected API "+path);
   }
 };
 vm.createContext(sandbox);
 vm.runInContext(fs.readFileSync("web/source_feed.js","utf8"),sandbox);
 const feed=sandbox.window.VoxSourceFeed.attach({
   mode:"live",el,
   credentials:mode=>({mode,mode_token:localToken}),
   async onConnect(mode){
     assert.equal(mode,"live");
     ++claims;
     localToken=claims.toString(16).padStart(32,"0");
     serverToken=localToken;
   },
   guard:()=>active,
   onMessage:(message,auto)=>received.push({message,auto}),
   onPick:message=>selected.push(message),
   onStop:()=>stopped.push(true),
   onReset:()=>{resets++;return{active_message_id:"x2",cleared:1};},
 });
 await feed.start();
 assert.equal(feed.connected,true);
 assert.equal(claims,1,"explicit first Connect must refresh stale browser token");
 assert.equal(el("liveFeedCredential").value,"","credential removed from DOM");
 assert.equal(requested[0].payload.credential,"temporary-token-never-persist");
 assert.equal(requested[0].headers["X-VoxWeaveTTS-Intent"],"start-live-source");
 assert.equal(requested[1].headers["X-VoxWeaveTTS-Intent"],"drain-live-source");
 assert.equal(received.length,2);
 assert.ok(received.every(x=>x.auto),"auto-read starts after user clicks Connect");
 assert.equal(el("liveFeedItems").children.length,2);
 const latest=el("liveFeedItems").children[0];
 assert.equal(latest.children[1].textContent,"<img src=x onerror=alert(1)>");
 latest.children[2].events.click();
 assert.equal(selected.length,1);
 assert.equal(selected[0].message_id,"x2");
 deferDrain=true;
 timer(); // Hold a stale /drain response while reset is in progress.
 assert.ok(releaseDrain,"stale drain must have started before reset");
 await el("liveFeedReset").events.click();
 assert.match(el("liveFeedStatus").textContent,/ข้อความที่กำลังแปล\/สร้างเสียง\/อ่าน จะทำต่อจนจบ/);
 releaseDrain();
 await new Promise(resolve=>setImmediate(resolve));
 assert.equal(received.length,2,"stale pre-reset /drain must not re-enqueue old chat");
 assert.equal(resets,1);
 assert.equal(feed.connected,true,"queue reset must keep the live source connected");
 assert.equal(feed.visible.length,1,"only the currently playing item remains");
 assert.equal(feed.visible[0].message_id,"x2");
 // Text-only processing shows the Core/AI result instead of original chat,
 // without adding a fake TTS/model history entry.
 el("liveFeedKeepRead").value="20";
 feed.setSpeechDiagnostic({message_id:"x2",stage:"displayed",text:"สวัสดี แปลแล้ว",error:""});
 feed.setMessageState("x2","displayed");
 assert.equal(feed.visible[0].state,"displayed");
 assert.equal(feed.visible[0].processed_text,"สวัสดี แปลแล้ว");
 assert.equal(el("liveFeedItems").children[0].children[1].textContent,"สวัสดี แปลแล้ว");
 assert.match(el("liveFeedReadItems").children[0].textContent,/สวัสดี แปลแล้ว/);
 assert.equal(el("liveFeedTtsReadItems").children.length,0,"no fake TTS history");
 assert.ok(requested.some(x=>x.path==="/v1/sources/reset"),
   "reset must clear the authenticated server-side pending queue");
 active=false;
 feed.suspend();
 assert.equal(feed.connected,false);
 assert.equal(timer,null);
 assert.equal(el("liveFeedAuto").checked,true,"tab suspension stops source but preserves auto-read preference");
 assert.ok(stopped.length>=2);
 assert.ok(!JSON.stringify(feed.visible).includes("temporary-token-never-persist"));
 active=true;
 serverToken="simulated-server-restart";
 el("liveFeedAuto").checked=false;
 await feed.start();
 assert.equal(claims,2,"explicit reconnect after server restart must renew token");
 assert.equal(feed.connected,true);
 assert.ok(received.slice(-2).every(x=>!x.auto));
 await feed.stop();
 assert.equal(requested.at(-1).path,"/v1/sources/stop");
 assert.equal(requested.at(-1).headers["X-VoxWeaveTTS-Intent"],"stop-live-source");
 console.log("PASS: live source manual Connect, temporary credential clearing, owner checks, safe rendering and default-on auto-read with manual opt-out");
}
main().catch(error=>{console.error(error);process.exitCode=1;});