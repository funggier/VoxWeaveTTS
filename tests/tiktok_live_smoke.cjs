// TikFinity Desktop local WebSocket integration for TikTok LIVE.
// Offline exercise of real source_feed controller, no TikTok account required.
const assert=require("node:assert/strict");
const fs=require("node:fs");
const vm=require("node:vm");
const source=fs.readFileSync("web/source_feed.js","utf8");
const html=fs.readFileSync("web/index.html","utf8");

async function test(){
  const needs=["Text","Submit","Play","Stop","Audio","Subtitle","Download",
    "FeedSourceId","FeedBlocked","FeedMaxChars","FeedAuto","FeedKeepRead",
    "FeedStart","FeedStop","FeedStatus","FeedQueueStatus","FeedItems",
    "FeedExport","FeedImport","FeedImportFile"];
  for(const suffix of needs)assert.ok(
    html.includes('id="tiktok'+suffix+'"'),"missing tiktok"+suffix);
  assert.ok(html.includes('data-mode-view="tiktok"'));
  assert.ok(html.includes('data-mode-target="tiktok"'));
  const nodes=new Map();
  function el(id){
    if(!nodes.has(id))nodes.set(id,{
      value:"",checked:false,disabled:false,textContent:"",events:{},
      children:[],files:[],clicks:0,
      click(){this.clicks++;},addEventListener(k,cb){this.events[k]=cb;},
      replaceChildren(){this.children=[];},appendChild(x){this.children.push(x);}
    });
    return nodes.get(id);
  }
  el("tiktokFeedSourceId").value="ws://localhost:21213/";
  el("tiktokFeedMaxChars").value="240";
  el("tiktokFeedKeepRead").value="2";
  el("tiktokFeedBlocked").value="spam, ละเว้น";
  el("tiktokFeedAuto").checked=true;
  let active=true;
  let stopped=0, requests=[], delivered=[], downloads=[];
  const sockets=[];
  class FakeWebSocket {
    constructor(url){this.url=url;this.readyState=0;this.closed=false;sockets.push(this);}
    connect(){this.readyState=1;this.onopen?.({});}
    emit(value){this.onmessage?.({data:typeof value==="string"?value:JSON.stringify(value)});}
    close(){this.closed=true;this.readyState=3;this.onclose?.({code:1000});}
    terminate(){this.readyState=3;this.onclose?.({code:1006});}
  }
  const browser={
    WebSocket:FakeWebSocket,
    async showSaveFilePicker(){
      return {async createWritable(){return{
        async write(raw){downloads.push(raw);}, async close(){},
      };}};
    }
  };
  const sandbox={
    window:browser,Number,JSON,Promise,
    document:{createElement(tag){return {
      className:"",textContent:"",tagName:tag.toUpperCase(),children:[],
      append(...xs){this.children.push(...xs);},appendChild(x){this.children.push(x);},
      addEventListener(k,cb){this["on"+k]=cb;}
    };}},
    fetch(path){requests.push(path);throw Error("TikTok provider must not use backend APIs: "+path);},
    setInterval(){throw Error("TikTok must use WebSocket, not backend polling");},
    clearInterval(){},
  };
  vm.createContext(sandbox);
  vm.runInContext(source,sandbox);
  const feed=sandbox.window.VoxSourceFeed.attach({
    mode:"tiktok",el,credentials:()=>({mode:"tiktok",mode_token:"token"}),
    guard:()=>active,onMessage(entry,auto){delivered.push({entry,auto});return auto?"queued":"manual";},
    onPick:entry=>{el("tiktokText").value=entry.text;},onStop(){stopped++;},
  });
  await feed.start();
  assert.equal(sockets.length,1);
  assert.equal(sockets[0].url,"ws://localhost:21213/");
  assert.equal(feed.connected,false,"only connected after WebSocket open");
  sockets[0].connect();
  assert.equal(feed.connected,true);
  sockets[0].emit({event:"gift",data:{comment:"should not speak"}});
  sockets[0].emit({event:"chat",data:{comment:"hello",user:{nickname:"Alice"},messageUuid:"uuid-1"}});
  sockets[0].emit({event:"chat",data:{comment:"hello",user:{nickname:"Alice"},messageUuid:"uuid-1"}});
  sockets[0].emit({event:"chat",data:{comment:"spam phrase",user:{uniqueId:"spammer"}}});
  sockets[0].emit({event:"chat",data:{comment:"https://example.com",user:{nickname:"link"}}});
  sockets[0].emit({event:"chat",data:{comment:"  สวัสดีครับ  ",user:{nickname:"กานต์"},msgId:"uuid-2"}});
  sockets[0].emit("{broken-json-with-sensitive-token");
  assert.equal(delivered.length,2,"chat-only, dedupe, filtering, no malformed data");
  assert.equal(delivered[0].entry.text,"hello");
  assert.equal(delivered[1].entry.text,"สวัสดีครับ");
  assert.equal(delivered[1].entry.author,"กานต์");
  assert.equal(feed.visible.length,2);
  assert.ok(!el("tiktokFeedItems").children[0].textContent.includes("<script>"));
  assert.ok(el("tiktokFeedStatus").textContent.includes("TikFinity"));
  assert.equal(requests.length,0,"WebSocket data is local; no backend poll");
  assert.ok(el("tiktokFeedQueueStatus").textContent.includes("คิวรออ่าน"));

  // Update completion state, prune only completed messages.
  feed.setMessageState("uuid-1","read");
  feed.setMessageState("uuid-2","read");
  el("tiktokFeedKeepRead").value="1";
  el("tiktokFeedKeepRead").events.input();
  assert.equal(feed.visible.length,1);
  assert.equal(feed.visible[0].message_id,"uuid-2");
  // TikFinity emits gift events distinctly from chat. Do not speak an
  // intermediate gift streak; the final event carries the total quantity.
  const firstCount=delivered.length;
  sockets[0].emit({event:"gift",data:{messageUuid:"gift-streak-1",
    giftName:"Heart Me",repeatCount:2,giftType:1,repeatEnd:false,
    user:{nickname:"Sprite Pam",level:25,badges:[{name:"InvT"}]}}});
  assert.equal(delivered.length,firstCount);
  sockets[0].emit({event:"gift",data:{messageUuid:"gift-streak-1",
    giftName:"Heart Me",repeatCount:2,repeatEnd:false,
    user:{nickname:"Sprite Pam"}}});
  assert.equal(delivered.length,firstCount,
    "in-progress gift streak should not announce even when giftType is absent");
  sockets[0].emit({event:"gift",data:{messageUuid:"gift-streak-1",
    giftName:"Heart Me",repeatCount:2,giftType:1,repeatEnd:true,
    topGifterRank:3,user:{nickname:"Sprite Pam",level:25,
                           badges:[{name:"InvT"}]}}});
  assert.equal(delivered.length,firstCount+1);
  assert.equal(delivered.at(-1).entry.kind,"gift");
  assert.equal(delivered.at(-1).entry.gift_name,"Heart Me");
  assert.equal(delivered.at(-1).entry.gift_count,2);
  assert.equal(delivered.at(-1).entry.level,"25");
  assert.equal(delivered.at(-1).entry.rank,"3");
  assert.equal(delivered.at(-1).entry.badges[0],"InvT");
  assert.ok(el("tiktokFeedItems").children[0].children
    .some(x=>x.textContent.includes("Heart Me × 2")));
  sockets[0].emit({event:"gift",data:{messageUuid:"gift-streak-1",
    giftName:"Heart Me",repeatCount:2,repeatEnd:true,
    user:{nickname:"Sprite Pam"}}});
  assert.equal(delivered.length,firstCount+1,"do not repeat the completed gift streak");


  // Export profile (no credentials for the TikFinity local bridge).
  const saved=await feed.exportSettings();
  assert.equal(saved.mode,"tiktok");
  assert.ok(!("credential" in saved));
  assert.ok(!("client_secret" in saved));
  assert.ok(downloads[0].includes("ws://localhost:21213/"));
  await feed.stop();
  assert.equal(sockets[0].closed,true);
  assert.equal(feed.connected,false);
  assert.ok(stopped>0);
  assert.equal(await feed.importSettings({
    size:Buffer.byteLength(JSON.stringify(saved)),async text(){return JSON.stringify(saved);}
  }),true);
  assert.equal(sockets.length,1,"Import must not connect automatically");

  // No unapproved off-machine sockets / no credential requests.
  el("tiktokFeedSourceId").value="ws://evil.example:21213/";
  await assert.rejects(feed.start(),/TikFinity|localhost|WebSocket/);
  assert.equal(sockets.length,1);

  el("tiktokFeedSourceId").value="ws://127.0.0.1:21213/";
  await feed.start();
  sockets[1].connect();
  sockets[1].terminate();
  assert.equal(feed.connected,false);
  assert.ok(stopped>1,"disconnect cancels queued audio work");
  console.log("PASS: TikTok/TikFinity chat-only local WebSocket, filters, queue, history, profile, stop, disconnect, localhost restriction");
}
test().catch(error=>{console.error(error);process.exitCode=1;});
