/* Computer dashboard reads Core state, never owns speech, and creates no loop. */
"use strict";
const assert=require("node:assert/strict");
const fs=require("node:fs");
const vm=require("node:vm");
const path=require("node:path");
const root=path.resolve(__dirname,"..");
const code=fs.readFileSync(path.join(root,"web","computer_dashboard.js"),"utf8");
const feed=fs.readFileSync(path.join(root,"web","source_feed.js"),"utf8");
const runtime=fs.readFileSync(path.join(root,"web","runtime_ui.js"),"utf8");
const html=fs.readFileSync(path.join(root,"web","index.html"),"utf8");
assert.match(html,/script src="\/computer_dashboard.js"/);
assert.match(runtime,/VoxCoreDashboard\?\.onRuntimeState\(data\)/);
assert.match(feed,/const computerOwned=root.VoxOutputMode\?\.current==="computer"/);
assert.match(feed,/if\(status.pending>0&&!computerOwned\)pendingWake=true/);
assert(!code.includes("setInterval("),"dashboard must reuse existing status refresh");
assert(!code.includes("/v1/sources/drain"),"dashboard must not consume chat");
assert(!code.includes("/start-render"),"dashboard must not synthesize");

function makeNode(){
  return {textContent:"",children:[],value:"20",
    replaceChildren(...args){this.children=args.slice()},
    appendChild(child){this.children.push(child)}};
}
const nodes=new Map(),feeds={live:{refreshBrowserViewCalls:0,refreshBrowserView(){this.refreshBrowserViewCalls++}}};
const document={
  hidden:false,
  getElementById(id){
    if(!nodes.has(id))nodes.set(id,makeNode());
    return nodes.get(id);
  },
  createElement(tag){return {tagName:tag,textContent:"",className:""}},
};
const responses=[];
let requests=0,intervals=0;
const makeDashboard=()=>({
  mode:"computer",
  sources:{
    live:{status:{state:"running",received:5,discarded:1},counts:{
      queued:2,preparing:1,prepared:1,rendering:1,ready:1,reading:1,
      read:1,failed:0
    },
    source_pending:2,source_pending_items:[{author:"A",text:"สวัสดีจากแชท"}],
    buffered:[],recent:[{text:"ใหม่สุด",author:"B",state:"preparing"}],
    pipeline:[
      {state:"preparing",inputs:[]},
      {state:"prepared",inputs:[{text:"ข้อความหลังแปล",language:"th",
          engine_id:"E",voice_id:"V"}]},
      {state:"ready",inputs:[{text:"เสียงที่สร้างจริง",language:"th",engine_id:"E",
          voice_id:"V"}]},
      {state:"reading",inputs:[]},
    ],
    read_history:[{text:"อ่านแล้วจริง",author:"C"}],
    model_history:[{inputs:[{text:"อินพุตโมเดลจริง",language:"th",
      engine_id:"E",voice_id:"V"}]}],
    }},
});
const window={
  document,
  VoxOutputMode:{current:"computer"},
  VoxLastRuntimeSnapshot:{mode:"computer",dashboard_cursor:"1:1:1:1"},
  setInterval(){intervals++},
  fetch:async(uri,options)=>{
    requests++;
    assert.equal(uri,"/v1/runtime/dashboard");
    assert.equal(options.method,"POST");
    assert.equal(options.headers["X-VoxWeaveTTS-Intent"],"inspect-runtime-dashboard");
    assert.equal(options.body,"{}");
    return {ok:true,json:async()=>makeDashboard()};
  },
};
vm.runInNewContext(code,{window,document,Number,Object,Array,String,console,Date},
                  {filename:"computer_dashboard.js"});
window.VoxCoreDashboard.init({feeds});
const pause=()=>new Promise(resolve=>setTimeout(resolve,20));
(async()=>{
  await pause();
  assert.equal(requests,1,"first page load must immediately hydrate Core state");
  assert.equal(intervals,0,"dashboard must not create polling interval");
  const status=document.getElementById("liveFeedQueueStatus").textContent;
  assert.match(status,/Core Server/);
  assert.match(status,/คิวรออ่าน 2/);
  assert.match(document.getElementById("liveFeedPreparedStatus").textContent,/เตรียม\/แปล 1/);
  assert.match(document.getElementById("liveFeedReadyAudioItems").children[0].textContent,/เสียงที่สร้างจริง/);
  assert.match(document.getElementById("liveFeedTtsReadItems").children[0].textContent,/อินพุตโมเดลจริง/);
  assert.match(document.getElementById("liveFeedReadItems").children[0].textContent,/อ่านแล้วจริง/);
  assert.match(document.getElementById("liveFeedCurrentStatus").textContent,/กำลังเล่นเสียง/);

  window.VoxCoreDashboard.onRuntimeState({mode:"computer",dashboard_cursor:"1:1:1:1"});
  await pause();
  assert.equal(requests,1,"unchanged state must not re-fetch data");
  window.VoxCoreDashboard.onRuntimeState({mode:"computer",dashboard_cursor:"2:1:1:1"});
  await pause();
  assert.equal(requests,2,"changed Core state triggers exactly one update");
  document.hidden=true;
  window.VoxCoreDashboard.onRuntimeState({mode:"computer",dashboard_cursor:"3:1:1:1"});
  await pause();
  assert.equal(requests,2,"hidden tab does not need dashboard updates");
  document.hidden=false;
  window.VoxCoreDashboard.onRuntimeState({mode:"computer",dashboard_cursor:"3:1:1:1"});
  await pause();
  assert.equal(requests,3,"visible tab catches up with Core");
  window.VoxCoreDashboard.onRuntimeState({mode:"browser",dashboard_cursor:"4:1:1:1"});
  assert.equal(feeds.live.refreshBrowserViewCalls,1);
  window.VoxCoreDashboard.onRuntimeState({mode:"browser",dashboard_cursor:"4:1:1:1"});
  await pause();
  assert.equal(requests,3,"browser-owned mode never requests Core diagnostic text");
  console.log("PASS: computer dashboard hydrate/refresh, truthful stages/history, on-change only, hidden-tab catch-up, browser restore, zero new loops");
})().catch(error=>{console.error(error);process.exitCode=1});
