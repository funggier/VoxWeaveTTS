/* Core controls must work after a Browser reload without owning a mode token. */
"use strict";
const assert=require("node:assert/strict");
const fs=require("node:fs");
const vm=require("node:vm");
const code=fs.readFileSync("web/source_feed.js","utf8");
const records=new Map();
function element(id){
  if(!records.has(id))records.set(id,{
    id,value:"",checked:false,disabled:false,textContent:"",children:[],events:{},
    addEventListener(name,callback){this.events[name]=callback},
    appendChild(child){this.children.push(child)},
    replaceChildren(...children){this.children=children},
  });
  return records.get(id);
}
function createElement(name){
  return {tagName:name.toUpperCase(),className:"",textContent:"",children:[],
    appendChild(x){this.children.push(x)},
    append(...xs){this.children.push(...xs)},
    addEventListener(){},replaceChildren(){}};
}
element("liveFeedKeepRead").value="20";
element("liveFeedMaxChars").value="240";
element("liveFeedAuto").checked=true;
let settingsChanged=0,sourceCleared=0,coreStopped=0;
let localResetCount=0,localStopCount=0;
const calls=[];
let sourceConnected=true;
const sandbox={
  window:{VoxOutputMode:{current:"computer"},
    VoxLastRuntimeSnapshot:{mode:"computer",sources:{live:{state:"running"}}}},
  document:{createElement,hidden:false,addEventListener(){}},
  console,Map,Set,JSON,Array,Number,Object,String,Date,Promise,
  setTimeout,clearTimeout,setInterval(){throw Error("Core control must not start browser timer")},
  clearInterval(){},
  fetch:async(path,options)=>{
    calls.push({path,options});
    assert.equal(options.method,"POST");
    const body=JSON.parse(options.body);
    assert.equal(body.mode,"live");
    if(path==="/v1/runtime/source/options"){
      assert.equal(options.headers["X-VoxWeaveTTS-Intent"],"set-core-source-options");
      ++settingsChanged;
      return {ok:true,json:async()=>({runtime_auto_read:body.runtime_auto_read})};
    }
    if(path==="/v1/runtime/source/reset"){
      assert.equal(options.headers["X-VoxWeaveTTS-Intent"],"reset-core-source-queue");
      ++sourceCleared;
      return {ok:true,json:async()=>({cleared:3,connected:true})};
    }
    if(path==="/v1/runtime/source/stop"){
      assert.equal(options.headers["X-VoxWeaveTTS-Intent"],"stop-core-source");
      ++coreStopped;sourceConnected=false;
      return {ok:true,json:async()=>({cancelled_jobs:1})};
    }
    throw Error("Browser refresh must never invoke a token-bound source operation: "+path);
  },
};
vm.runInNewContext(code,sandbox,{filename:"source_feed.js"});
const feed=sandbox.window.VoxSourceFeed.attach({
  mode:"live",el:element,
  credentials(){throw Error("No browser owner token after refresh")},
  guard(){return false},
  onMessage(){},onPick(){},
  onStop(){localStopCount++},
  onReset(){localResetCount++;return {}},
});
(async()=>{
  assert.equal(feed.connected,false);
  element("liveFeedAuto").checked=false;
  await element("liveFeedAuto").events.input();
  assert.equal(settingsChanged,1);
  assert.equal(element("liveFeedAuto").checked,false);
  assert.equal(element("liveFeedAuto").disabled,false);
  element("liveFeedAuto").checked=true;
  await element("liveFeedAuto").events.input();
  assert.equal(settingsChanged,2);
  assert.equal(element("liveFeedAuto").checked,true);
  sandbox.window.VoxLastRuntimeSnapshot.sources.live.state="idle";
  element("liveFeedAuto").checked=false;
  await element("liveFeedAuto").events.input();
  assert.equal(settingsChanged,2,"idle Core source must keep offline draft without sending 409 POST");
  assert.equal(element("liveFeedAuto").checked,false);
  sandbox.window.VoxLastRuntimeSnapshot.sources.live.state="running";
  await element("liveFeedReset").events.click();
  assert.equal(sourceCleared,1);
  assert.equal(localResetCount,0,"Core reset must not clear Browser-only state");
  assert.equal(element("liveFeedReset").disabled,false);
  assert.match(element("liveFeedStatus").textContent,/Core/);
  await feed.stop();
  assert.equal(coreStopped,1);
  assert.equal(localStopCount,1);
  assert.equal(sourceConnected,false);
  assert.equal(calls.length,4);
  console.log("PASS: Core source auto-read, source reset and stop control after Browser refresh without owner token");
})().catch(error=>{console.error(error);process.exitCode=1});
