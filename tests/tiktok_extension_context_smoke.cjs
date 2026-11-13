/* Chrome extension reload: obsolete content-script context must shut down. */
"use strict";
const assert=require("node:assert/strict");
const fs=require("node:fs");
const vm=require("node:vm");

const script=fs.readFileSync("extensions/tiktok-live-connector/content.js","utf8");
const manifest=JSON.parse(fs.readFileSync("extensions/tiktok-live-connector/manifest.json","utf8"));
assert.equal(manifest.version,"0.2.4");
function mount(makeRuntime,extensionId="abcdefghijklmnopabcdefghijklmnop"){
  let messageListener=null, heartbeat=null;
  let sends=0, observerDisconnected=0, intervalsCleared=0, timeoutsCleared=0;
  const runtime={
    id:extensionId,
    onMessage:{addListener(fn){messageListener=fn;}},
    sendMessage(payload,done){
      sends++;
      return makeRuntime(payload,done,runtime);
    },
  };
  const box={
    chrome:{runtime},
    document:{
      documentElement:{},
      querySelector(){return null;},
    },
    Date,WeakMap,Set,Number,
    MutationObserver:class{
      observe(){}
      disconnect(){observerDisconnected++;}
    },
    setInterval(callback){heartbeat=callback;return 123;},
    clearInterval(){intervalsCleared++;},
    setTimeout(){return 456;},
    clearTimeout(){timeoutsCleared++;},
  };
  box.globalThis=box;
  vm.createContext(box);
  vm.runInContext(script,box);
  assert.equal(typeof messageListener,"function");
  return {
    start(){messageListener({kind:"vw-start"});},
    heartbeat(){heartbeat();},
    get sends(){return sends;},
    get observerDisconnected(){return observerDisconnected;},
    get intervalsCleared(){return intervalsCleared;},
    get timeoutsCleared(){return timeoutsCleared;},
  };
}
{
  // A synchronous sendMessage exception is the actual error reported by Chrome.
  const running=mount(()=>{throw Error("Extension context invalidated.");});
  assert.doesNotThrow(()=>running.start());
  assert.equal(running.sends,1);
  assert.equal(running.observerDisconnected,1);
  assert.equal(running.intervalsCleared,1);
  assert.doesNotThrow(()=>running.heartbeat());
  assert.equal(running.sends,1,"must not continue sending from invalid context");
}
{
  // The callback may fire when reading runtime.lastError already throws.
  const running=mount((_payload,callback,runtime)=>{
    Object.defineProperty(runtime,"lastError",{
      get(){throw Error("Extension context invalidated.");},
      configurable:true,
    });
    callback({ok:true});
  });
  assert.doesNotThrow(()=>running.start());
  assert.equal(running.observerDisconnected,1);
  assert.equal(running.intervalsCleared,1);
  assert.doesNotThrow(()=>running.heartbeat());
  assert.equal(running.sends,1);
}
{
  // Authorization errors are also terminal for the obsolete tab reader.
  const running=mount((_payload,callback)=>callback({
    ok:false,error:"not authorized tab",
  }));
  assert.doesNotThrow(()=>running.start());
  assert.equal(running.observerDisconnected,1);
}
{
  const running=mount(()=>{throw Error("Cannot read properties of undefined (reading 'sendMessage')");});
  assert.doesNotThrow(()=>running.start());
  assert.equal(running.observerDisconnected,1);
  assert.equal(running.intervalsCleared,1);
}
{
  const old=mount(()=>{throw Error("unexpected sendMessage");},null);
  assert.doesNotThrow(()=>old.start());
  assert.equal(old.sends,0,"no messages after chrome.runtime.id disappeared");
  assert.equal(old.observerDisconnected,1);
  assert.equal(old.intervalsCleared,1);
}
console.log("PASS: stale Chrome content-script runtime stops polling without uncaught errors");
