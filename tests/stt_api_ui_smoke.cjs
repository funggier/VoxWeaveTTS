// VoxWeaveSTT API workspace uses separate IP/Port and existing source feed.
const assert=require("node:assert/strict");
const fs=require("node:fs");
const vm=require("node:vm");
async function main(){
  const html=fs.readFileSync("web/index.html","utf8");
  assert.match(html,/data-mode-target="stt_api"[^>]*>VoxWeaveSTT \(API\)/);
  for(const id of ["FeedSourceId","FeedPort","FeedSecure","FeedFingerprint",
    "FeedCredential","FeedStart","FeedStop","FeedStatus","FeedItems"]){
    assert.ok(html.includes('id="sttApi'+id+'"'),"Missing STT field "+id);
  }
  const nodes=new Map();
  const createElement=tag=>({
    tagName:tag.toUpperCase(),children:[],textContent:"",events:{},
    append(...elements){this.children.push(...elements);},
    replaceChildren(){this.children=[];},
    addEventListener(event,cb){this.events[event]=cb;},
  });
  const el=id=>{
    if(!nodes.has(id)){
      nodes.set(id,{value:"",checked:false,disabled:false,textContent:"",
        children:[],events:{},
        appendChild(n){this.children.push(n);},
        replaceChildren(...n){this.children=n;},
        addEventListener(evt,fn){this.events[evt]=fn;},
      });
    }
    return nodes.get(id);
  };
  el("sttApiFeedSourceId").value="127.0.0.1";
  el("sttApiFeedPort").value="8766";
  el("sttApiFeedMaxChars").value="8000";
  el("sttApiFeedAuto").checked=true;
  el("sttApiFeedKeepRead").value="20";
  const received=[],requests=[];
  let claims=0,token="a".repeat(32);
  const sandbox={
    window:{},document:{createElement},JSON,Number,
    setInterval(fn){return 1;},clearInterval(){},
    async fetch(path,options){
      const body=JSON.parse(options.body);
      requests.push({path,body});
      if(path==="/v1/sources/start")return{ok:true,async json(){return{state:"connecting"};}};
      if(path==="/v1/sources/drain")return{ok:true,async json(){return{
        messages:[{message_id:"s1:part1:0",text:"ทดสอบรับข้อความ STT",author:""}],
        status:{state:"running",received:1,discarded:0,pending:0,connection_phase:"ready",next_poll_seconds:0.6},
      };}};
      if(path==="/v1/sources/stop")return{ok:true,async json(){return{state:"stopped"};}};
      throw Error("Unexpected path "+path);
    },
  };
  vm.createContext(sandbox);
  vm.runInContext(fs.readFileSync("web/source_feed.js","utf8"),sandbox);
  const feed=sandbox.window.VoxSourceFeed.attach({
    mode:"stt_api",el,
    credentials:mode=>({mode,mode_token:token}),
    async onConnect(mode){assert.equal(mode,"stt_api");claims++;token=String(claims).padStart(32,"0");},
    guard:()=>true,
    onMessage:(message,auto)=>received.push({message,auto}),
    onPick(){},onStop(){},onReset(){},
  });
  await feed.start();
  assert.equal(requests[0].body.source_id,"http://127.0.0.1:8766");
  assert.equal(requests[0].body.mode,"stt_api");
  assert.equal(requests[0].body.credential,"");
  assert.equal(received[0].message.text,"ทดสอบรับข้อความ STT");
  assert.equal(received[0].auto,true);
  await feed.stop();
  el("sttApiFeedSourceId").value="192.168.1.165";
  el("sttApiFeedPort").value="8768";
  el("sttApiFeedSecure").checked=true;
  el("sttApiFeedCredential").value="12345678";
  el("sttApiFeedFingerprint").value="b".repeat(64);
  await feed.start();
  const secure=requests.filter(x=>x.path==="/v1/sources/start").at(-1).body;
  assert.equal(secure.source_id,"https://192.168.1.165:8768");
  assert.equal(secure.credential.pin,"12345678");
  assert.equal(secure.credential.fingerprint,"b".repeat(64));
  assert.equal(el("sttApiFeedCredential").value,"","PIN cleared after connection");
  await feed.stop();
  console.log("PASS: VoxWeaveSTT API IP/Port local and paired LAN payloads, Final -> source queue");
}
main().catch(error=>{console.error(error);process.exitCode=1;});
