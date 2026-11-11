// No external credentials or Discord Desktop required: selectable-room UI smoke.
const assert=require("node:assert/strict");
const fs=require("node:fs");
const vm=require("node:vm");
async function main(){
  const html=fs.readFileSync("web/index.html","utf8");
  for(const suffix of ["Text","Submit","Play","Stop","Audio",
    "FeedSourceId","FeedAppId","FeedAppSecret","FeedRedirect","FeedMaxChars",
    "FeedBlocked","FeedAuto","FeedStart","FeedStop","FeedItems","FeedStatus"]){
    assert.ok(html.includes('id="discordClient'+suffix+'"'),"missing room UI "+suffix);
  }
  assert.ok(html.includes('data-mode-target="discord_client"'));
  assert.ok(html.includes('data-mode-view="discord_client"'));
  const known=new Map();
  const mk=(name)=>({
    name,value:"",checked:false,disabled:false,textContent:"",events:{},
    children:[],replaceChildren(){this.children=[]},
    append(...items){this.children.push(...items)},
    appendChild(item){this.children.push(item)},
    addEventListener(event,fn){this.events[event]=fn},
  });
  const el=id=>{
    if(!known.has(id))known.set(id,mk(id));
    return known.get(id);
  };
  const doc={createElement:mk};
  const requests=[],picked=[],audioInput=[];
  let starts=0, failed=false, stopCallbacks=0;
  let active=true, ticker;
  const sandbox={
    window:{},document:doc,JSON,Number,
    setInterval(fn){ticker=fn;return 1},
    clearInterval(){ticker=null},
    async fetch(path,options){
      const payload=JSON.parse(options.body);
      requests.push({path,payload,headers:options.headers});
      if(path==="/v1/sources/start"){
        assert.equal(payload.mode,"discord_client");
        starts++;
        assert.equal(payload.source_id,starts===1?"100000000000000111":"100000000000000222");
        assert.equal(payload.credential.client_id,"100000000000000005");
        assert.equal(payload.credential.client_secret,"secret-for-test-only-123");
        assert.equal(payload.credential.redirect_uri,"http://127.0.0.1:8765/callback");
        return {ok:true,async json(){return {mode:"discord_client",state:"connecting",pending:0}}};
      }
      if(path==="/v1/sources/drain"){
        if(failed)return {ok:true,async json(){return {
          messages:[],status:{state:"error",info:"Discord RPC closed; reconnect",pending:0,received:1},
        }}};
        return {ok:true,async json(){return {
          messages:[{message_id:"100000000000000112",author:"ผู้ใช้",text:"ห้องที่เลือก"}],
          status:{state:"running",received:1,discarded:0,pending:0,next_poll_seconds:1},
        }}};
      }
      if(path==="/v1/sources/stop")
        return {ok:true,async json(){return {state:"stopped",pending:0}}};
      throw Error("bad request "+path);
    }
  };
  vm.createContext(sandbox);
  vm.runInContext(fs.readFileSync("web/source_feed.js","utf8"),sandbox);
  const source=sandbox.window.VoxSourceFeed.attach({
    mode:"discord_client",el,
    credentials:mode=>({mode,mode_token:"a".repeat(32)}),
    guard:()=>active,
    onMessage:(item,auto)=>audioInput.push({item,auto}),
    onPick:item=>picked.push(item),
    onStop:()=>{stopCallbacks++;},
  });
  el("discordClientFeedSourceId").value="100000000000000111";
  el("discordClientFeedAppId").value="100000000000000005";
  el("discordClientFeedAppSecret").value="secret-for-test-only-123";
  el("discordClientFeedRedirect").value="http://127.0.0.1:8765/callback";
  el("discordClientFeedMaxChars").value="240";
  await source.start();
  assert.equal(source.connected,true);
  assert.equal(el("discordClientFeedAppSecret").value,"","do not retain secret in form");
  assert.equal(audioInput.length,1);
  assert.equal(audioInput[0].auto,false,"auto-read must be OFF by default");
  assert.equal(el("discordClientFeedItems").children.length,1);
  assert.equal(el("discordClientFeedItems").children[0].children[1].textContent,"ห้องที่เลือก");
  el("discordClientFeedItems").children[0].children[2].events.click();
  assert.equal(picked[0].text,"ห้องที่เลือก");
  // Selecting a DIFFERENT room must stop the old subscription before
  // activating the newly selected channel, even if it is in same Discord guild.
  el("discordClientFeedSourceId").value="100000000000000222";
  el("discordClientFeedAuto").checked=true;
  el("discordClientFeedAppSecret").value="secret-for-test-only-123";
  await source.start();
  assert.equal(el("discordClientFeedAuto").checked,false,
    "changing Discord rooms must require a new auto-read opt-in");
  assert.equal(starts,2);
  const relevant=requests.filter(x=>["/v1/sources/start","/v1/sources/stop"].includes(x.path));
  assert.deepEqual(relevant.slice(0,3).map(x=>x.path),[
    "/v1/sources/start","/v1/sources/stop","/v1/sources/start",
  ]);
  assert.equal(el("discordClientFeedAppSecret").value,"");
  el("discordClientFeedAuto").checked=true;
  failed=true;
  await source.poll();
  assert.equal(source.connected,false,"terminal RPC error must stop client polling");
  assert.equal(el("discordClientFeedAuto").checked,false,"disable auto-read on RPC error");
  assert.equal(ticker,null,"terminal RPC error must clear the poll timer");
  assert.ok(stopCallbacks>0,"terminal RPC error must clear auto-read queue");
  assert.ok(el("discordClientFeedStatus").textContent.includes("reconnect"));
  active=false;source.suspend();
  assert.equal(source.connected,false);
  assert.equal(ticker,null);
  assert.equal(el("discordClientFeedAuto").checked,false);
  assert.ok(requests.every(x=>!x.payload.user_token&&!x.payload.browser_cookie));
  console.log("PASS: Discord Client selectable Channel ID, consent-based app credential, no saved secret, selected-room message UI, auto-read off and mode suspension");
}
main().catch(e=>{console.error(e);process.exitCode=1;});