// Browser tab: source profile is credential-free and feeds existing voice queue.
const assert=require("node:assert/strict");
const fs=require("node:fs");
const vm=require("node:vm");

async function main(){
  const html=fs.readFileSync("web/index.html","utf8");
  const prefix="tiktokBrowser";
  for(const suffix of ["Text","Submit","Play","Stop","Audio","Subtitle","Download",
                       "FeedSourceId","FeedBlocked","FeedMaxChars","FeedKeepRead",
                       "FeedAuto","FeedReadSender","FeedStart","FeedStop",
                       "FeedStatus","FeedItems","FeedExport","FeedImport"])
    assert.ok(html.includes('id="'+prefix+suffix+'"'),"missing browser field "+suffix);
  assert.match(html,/id="tiktokBrowserFeedStart">เชื่อมต่อ<\/button>/);
  assert.match(html,/id="tiktokBrowserFeedProgress"/);
  assert.match(html,/for\(const mode of \["live","youtube_browser","tiktok_browser","discord","discord_client","tiktok"\]\)\{\s*const inputMode=/);
  assert.ok(!html.includes('id="'+prefix+'FeedCredential"'),
            "Browser must not request an API key");
  const records=new Map();
  function el(id){
    if(!records.has(id))records.set(id,{
      value:"",checked:false,disabled:false,textContent:"",children:[],events:{},
      replaceChildren(...items){this.children=items;},
      appendChild(item){this.children.push(item);},
      addEventListener(name,fn){this.events[name]=fn;},
    });
    return records.get(id);
  }
  function createElement(tag){return{
    tagName:tag.toUpperCase(),children:[],events:{},
    append(...items){this.children.push(...items);},
    addEventListener(name,fn){this.events[name]=fn;},
  };}
  el(prefix+"FeedSourceId").value="https://www.tiktok.com/@test.stream_42/live";
  el(prefix+"FeedBlocked").value="สแปม";
  el(prefix+"FeedMaxChars").value="240";
  el(prefix+"FeedKeepRead").value="20";
  el(prefix+"FeedAuto").checked=true;
  let owner="a".repeat(32);
  const requests=[],received=[],picked=[];
  const sandbox={window:{},JSON,Number,document:{createElement},
    setInterval(fn,ms){assert.equal(ms,1200);return 1;},
    clearInterval(){},
    async fetch(path,options){
      const payload=JSON.parse(options.body);
      requests.push({path,payload});
      if(path.endsWith("/start"))return{ok:true,async json(){return{
        mode:"tiktok_browser",state:"connecting",pending:0,
      };}};
      if(path.endsWith("/drain"))return{ok:true,async json(){return{
        messages:[{message_id:"a1",author:"Tester",text:"สวัสดีครับ"}],
        status:{mode:"tiktok_browser",state:"running",connection_phase:"ready",transport:"browser-dom",
                received:1,discarded:0,pending:0,next_poll_seconds:1.5},
      };}};
      if(path.endsWith("/stop"))return{ok:true,async json(){return{state:"stopped"};}};
      throw Error("unexpected URL: "+path);
    },
  };
  vm.createContext(sandbox);
  vm.runInContext(fs.readFileSync("web/source_feed.js","utf8"),sandbox);
  const feed=sandbox.window.VoxSourceFeed.attach({
    mode:"tiktok_browser",el,credentials:mode=>({mode,mode_token:owner}),
    guard:()=>true,
    async onConnect(){owner="b".repeat(32);},
    onMessage:(msg,auto)=>{received.push({msg,auto});return "queued";},
    onPick:item=>picked.push(item),
    onStop(){},
  });
  await el(prefix+"FeedStart").events.click();
  for(let i=0;i<15&&!feed.connected;i++)await new Promise(resolve=>setImmediate(resolve));
  assert.equal(feed.connected,true);
  assert.equal(requests[0].payload.source_id,el(prefix+"FeedSourceId").value);
  assert.equal(requests[0].payload.mode,"tiktok_browser");
  assert.equal(requests[0].payload.credential,"");
  assert.equal(received[0].msg.text,"สวัสดีครับ");
  assert.equal(received[0].auto,true);
  assert.match(el(prefix+"FeedStatus").textContent,/เชื่อมต่อสำเร็จ/);
  assert.match(el(prefix+"FeedStatus").textContent,/รับ 1/);
  assert.ok(el(prefix+"FeedProgress").children.length>=3,"progress stages should render");
  assert.equal(el(prefix+"FeedItems").children.length,1);
  el(prefix+"FeedItems").children[0].children[2].events.click();
  assert.equal(picked[0].message_id,"a1");
  await feed.stop();
  assert.equal(feed.connected,false);
  console.log("PASS: TikTok Browser mode UI, no API key, separate source, safe message feed");
}
main().catch(e=>{console.error(e);process.exitCode=1;});