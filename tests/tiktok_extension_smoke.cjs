/* MV3 TikTok Extension: opt-in active tab, secure local bridge, DOM-only content. */
"use strict";
const assert=require("node:assert/strict");
const fs=require("node:fs");
const vm=require("node:vm");
const extPath="extensions/tiktok-live-connector/";
const manifest=JSON.parse(fs.readFileSync(extPath+"manifest.json","utf8"));
assert.equal(manifest.manifest_version,3);
assert.deepEqual(manifest.permissions,["activeTab","scripting","storage"]);
assert.deepEqual(manifest.host_permissions,["http://127.0.0.1/*"]);
assert.equal(manifest.action.default_popup,"popup.html");
assert.equal(manifest.background.service_worker,"background.js");
assert.equal(manifest.content_scripts,undefined,"must not inject without user click");
assert.equal(manifest.externally_connectable,undefined,"webpages cannot message extension");

async function testWorker(){
  const extId="abcdefghijklmnopabcdefghijklmnop";
  const events=[],requests=[];
  const sessions=new Map();
  let onMessage, onRemoved, selectedUrl="https://www.tiktok.com/@demo_stream/live";
  const tab={id:42,get url(){return selectedUrl}};
  const chrome={
    runtime:{
      id:extId,
      onMessage:{addListener(fn){onMessage=fn;}},
    },
    storage:{session:{
      async get(key){return {[key]:sessions.get(key)};},
      async set(object){for(const [k,v] of Object.entries(object))sessions.set(k,v);},
      async remove(key){(Array.isArray(key)?key:[key]).forEach(k=>sessions.delete(k));}
    }},
    tabs:{
      async query(){return [tab];},
      async sendMessage(tabId,payload){events.push({kind:"tab-message",tabId,payload});},
      onRemoved:{addListener(fn){onRemoved=fn;}}
    },
    scripting:{
      async executeScript(args){events.push({kind:"inject",...args});}
    },
  };
  async function fetch(url,options){
    assert.match(url,/^http:\/\/127\.0\.0\.1:8765\/v1\/extension\//);
    assert.equal(options.headers["X-VoxWeaveTTS-Intent"],"tiktok-extension");
    const data=JSON.parse(options.body);
    requests.push({url,data});
    if(url.endsWith("/pair"))return{ok:true,async json(){return{
      token:"my-session-"+"a".repeat(48),source:"demo_stream"
    };}};
    if(url.endsWith("/messages"))return{ok:true,async json(){return{accepted:data.items.length};}};
    if(url.endsWith("/disconnect"))return{ok:true,async json(){return{ok:true};}};
    throw Error("Unexpected request");
  }
  const box={chrome,fetch,URL,Promise,Number,console};
  vm.createContext(box);
  vm.runInContext(fs.readFileSync(extPath+"background.js","utf8"),box);
  function command(payload,sender){
    return new Promise((resolve,reject)=>{
      let replied=false;
      const keep=onMessage(payload,sender,value=>{replied=true;resolve(value);});
      if(keep!==true&&!replied)reject(Error("message ignored"));
    });
  }
  const popup={id:extId,url:"chrome-extension://"+extId+"/popup.html"};
  const sourceTab={id:extId,url:selectedUrl,tab:{id:42}};
  const invalid=await command({type:"vw-start",port:8765,code:"PAIR"},{
    id:extId,url:"https://www.tiktok.com/live"
  }).catch(()=>null);
  assert.equal(invalid,null,"webpages cannot start bridge");
  selectedUrl="https://www.tiktok.com/@demo_stream/live";
  const start=await command({type:"vw-start",port:8765,code:"PAIRCODE"},popup);
  assert.equal(start.ok,true);
  assert.ok(events.some(e=>e.kind==="inject"&&e.target.tabId===42));
  assert.ok(events.some(e=>e.kind==="tab-message"&&e.payload.kind==="vw-start"));
  assert.equal(requests[0].data.code,"PAIRCODE");
  const status=await command({type:"vw-status"},popup);
  assert.equal(status.connected,true);
  const denied=await command({kind:"vw-chat-batch",phase:"ready",items:[]},{
    id:extId,tab:{id:88},url:sourceTab.url
  });
  assert.equal(denied.ok,false);
  const sample=[{id:"m1",author:"Viewer",text:"สวัสดีครับ"}];
  const diagnostics={list_found:true,row_candidates:1,parsed_rows:1,
    fresh_rows:1,author_nodes:1};
  const forwarded=await command({kind:"vw-chat-batch",phase:"ready",
    items:sample,diagnostics},sourceTab);
  assert.equal(forwarded.ok,true);
  assert.equal(forwarded.accepted,1);
  assert.equal(requests.at(-1).data.items[0].text,"สวัสดีครับ");
  assert.equal(requests.at(-1).data.url,sourceTab.url);
  assert.equal(requests.at(-1).data.diagnostics.parsed_rows,1);
  const report=await command({type:"vw-status"},popup);
  assert.equal(report.scan.diagnostics.parsed_rows,1);
  assert.equal(report.scan.accepted,1);
  assert.equal(report.scan.phase,"ready");
  const stopped=await command({type:"vw-stop"},popup);
  assert.equal(stopped.ok,true);
  assert.equal((await command({type:"vw-status"},popup)).connected,false);
  assert.ok(requests.some(r=>r.url.endsWith("/disconnect")));
  assert.ok(typeof onRemoved==="function");
}

function testContent(){
  const sends=[];
  let listener,interval;
  let current=[
    {id:"old",author:"Viewer1",text:"ก่อนกดเชื่อมต่อ"},
  ];
  function makeRow(data){
    return {
      className:"",
      contains(other){return other===this;},
      getAttribute(name){return name==="data-id"?data.id:null;},
      querySelector(query){
        if(query.includes("gift")||query.includes("follow"))return null;
        if(query.includes("message-text"))return {textContent:data.text};
        if(query.includes("message-owner-name"))return {textContent:data.author};
        return null;
      }
    };
  }
  const chat={
    querySelectorAll(){return current.map(makeRow);}
  };
  const doc={
    documentElement:{},
    querySelector(query){
      if(query.includes("room-chat-input-field"))return null;
      if(query.includes("DivChatMessageList"))return chat;
      return null;
    }
  };
  const chrome={
    runtime:{
      onMessage:{addListener(fn){listener=fn;}},
      sendMessage(data,cb){sends.push(data);cb?.({ok:true});},
    }
  };
  const box={chrome,document:doc,Date,WeakMap,Set,Number,MutationObserver:class{
    observe(){} disconnect(){}
  },setInterval(fn){interval=fn;return 1;},clearInterval(){},setTimeout(){return 1;},clearTimeout(){}};
  box.globalThis=box;
  vm.createContext(box);
  vm.runInContext(fs.readFileSync(extPath+"content.js","utf8"),box);
  listener({kind:"vw-start"});
  assert.equal(sends[0].phase,"ready");
  assert.equal(sends[0].items.length,0,"existing chat history is skipped");
  current=[...current,{id:"new1",author:"Viewer2",text:"ข้อความใหม่"}];
  interval();
  assert.equal(sends.at(-1).items.length,1);
  assert.equal(sends.at(-1).items[0].text,"ข้อความใหม่");
  interval();
  assert.equal(sends.at(-1).items.length,0,"same item is not duplicated");
  listener({kind:"vw-stop"});
  interval();
  assert.equal(sends.at(-1).items.length,0);
}

function testGenericLiveChatRows(){
  // Modern TikTok can use generic flex wrappers without data-e2e chat-message.
  let listener,heartbeat;
  let current=[{id:"old",author:"Guest A",text:"ข้อความก่อนเชื่อมต่อ"}];
  const sent=[];
  const names=()=>{
    return current.map(data=>{
      const name={
        textContent:data.author,parentElement:null,
        querySelector(){return null;},contains(other){return other===this;},
      };
      const message={
        textContent:data.text,querySelector(){return null;},
        closest(){return null;},
      };
      const row={
        className:"flex gap-2",
        textContent:data.author+" "+data.text,
        getAttribute(key){return key==="data-id"?data.id:null;},
        contains(other){return other===this;},
        querySelector(selector){
          if(selector.includes("gift")||selector.includes("follow"))return null;
          if(selector.includes("SpanUserName")||selector.includes("message-owner-name"))
            return name;
          return null;
        },
        querySelectorAll(selector){
          return selector==="span,p"?[name,message]:[];
        },
      };
      name.parentElement=row;
      return {name,row};
    });
  };
  const chat={
    querySelectorAll(selector){
      return selector.includes("SpanUserName")?names().map(x=>x.name):[];
    }
  };
  const chrome={runtime:{
    onMessage:{addListener(fn){listener=fn;}},
    sendMessage(data,cb){sent.push(data);cb?.({ok:true});},
  }};
  const document={
    documentElement:{},
    querySelector(selector){
      if(selector.includes("room-chat-input-field"))return null;
      if(selector.includes("DivChatMessageList"))return chat;
      return null;
    }
  };
  const box={chrome,document,Date,WeakMap,Set,Number,MutationObserver:class{
    observe(){}disconnect(){}
  },setInterval(fn){heartbeat=fn;return 1;},clearInterval(){},
  setTimeout(){return 1;},clearTimeout(){}};
  box.globalThis=box;
  vm.createContext(box);
  vm.runInContext(fs.readFileSync(extPath+"content.js","utf8"),box);
  listener({kind:"vw-start"});
  assert.equal(sent[0].diagnostics.row_candidates,1);
  assert.equal(sent[0].diagnostics.parsed_rows,1);
  assert.equal(sent[0].items.length,0,"do not replay comments already visible");
  current.push({id:"new",author:"Guest B",text:"สวัสดีจากแชทใหม่"});
  heartbeat();
  assert.equal(sent.at(-1).items.length,1);
  assert.equal(sent.at(-1).items[0].author,"Guest B");
  assert.equal(sent.at(-1).items[0].text,"สวัสดีจากแชทใหม่");
  assert.equal(sent.at(-1).diagnostics.fresh_rows,1);
  listener({kind:"vw-stop"});
}
(async()=>{
  await testWorker();
  testContent();
  testGenericLiveChatRows();
  console.log("PASS: MV3 extension explicit activation, pairing, sender isolation, comments-only DOM, stop");
})().catch(error=>{console.error(error);process.exitCode=1;});
