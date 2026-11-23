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
assert.match(html,/id="sttApiFeedCurrentText"/);
assert.match(html,/id="sttApiFeedPreparedItems"/);
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
    live:{status:{state:"running",received:5,discarded:1,
      runtime_auto_read:false,source_id:"youtube-live-actual-id"},counts:{
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
      {state:"reading",inputs:[{text:"ประโยคที่ Core กำลังเล่นจริง",language:"th",
        engine_id:"E",voice_id:"V"}]},
    ],
    read_history:[{text:"อ่านแล้วจริง",author:"C"}],
    model_history:[{inputs:[{text:"อินพุตโมเดลจริง",language:"th",
      engine_id:"E",voice_id:"V"}]}],
    },
    stt_api:{status:{state:"running",received:1,discarded:0,
      runtime_auto_read:true,source_id:"https://192.168.1.165:8768/"},counts:{
      queued:0,preparing:0,prepared:0,rendering:1,ready:0,reading:0,
      read:0,failed:0},source_pending:0,source_pending_items:[],
      buffered:[],recent:[{text:"คำถอดเสียง STT",author:"STT",state:"rendering"}],
      pipeline:[{state:"rendering",inputs:[{text:"ข้อความ STT เข้าสู่โมเดล TTS จริง",
        language:"th",engine_id:"E",voice_id:"V"}]}],
      read_history:[],model_history:[]}
  },
});
let activeDashboard=makeDashboard();
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
    return {ok:true,json:async()=>activeDashboard};
  },
};
vm.runInNewContext(code,{window,document,Number,Object,Array,String,console,Date,URL},
                  {filename:"computer_dashboard.js"});
window.VoxCoreDashboard.init({feeds});
const pause=()=>new Promise(resolve=>setTimeout(resolve,20));
(async()=>{
  await pause();
  assert.equal(requests,1,"first page load must immediately hydrate Core state");
  assert.equal(intervals,0,"dashboard must not create polling interval");
  assert.equal(document.getElementById("liveFeedStart").disabled,true);
  assert.equal(document.getElementById("liveFeedStop").disabled,false);
  assert.equal(document.getElementById("liveFeedAuto").checked,false);
  assert.equal(document.getElementById("liveFeedAuto").disabled,false);
  assert.equal(document.getElementById("liveFeedReset").disabled,false);
  assert.equal(document.getElementById("liveFeedSourceId").value,"youtube-live-actual-id");
  assert.equal(document.getElementById("sttApiFeedAuto").checked,true);
  assert.equal(document.getElementById("sttApiFeedPort").value,"8768");
  assert.equal(document.getElementById("sttApiFeedSecure").checked,true);
  assert.equal(document.getElementById("sttApiFeedSourceId").value,"192.168.1.165");
  const status=document.getElementById("liveFeedQueueStatus").textContent;
  assert.match(status,/Core Server/);
  assert.match(status,/คิวรออ่าน 2/);
  assert.match(document.getElementById("liveFeedPreparedStatus").textContent,/เตรียม\/แปล 1/);
  assert.match(document.getElementById("liveFeedReadyAudioItems").children[0].textContent,/เสียงที่สร้างจริง/);
  assert.match(document.getElementById("liveFeedTtsReadItems").children[0].textContent,/อินพุตโมเดลจริง/);
  assert.match(document.getElementById("liveFeedReadItems").children[0].textContent,/อ่านแล้วจริง/);
  assert.match(document.getElementById("liveFeedCurrentStatus").textContent,/กำลังเล่นเสียง/);
  assert.match(document.getElementById("liveFeedCurrentText").textContent,/ประโยคที่ Core กำลังเล่นจริง/);
  assert.match(document.getElementById("sttApiFeedCurrentText").textContent,/ข้อความ STT เข้าสู่โมเดล TTS จริง/);

  window.VoxCoreDashboard.onRuntimeState({mode:"computer",dashboard_cursor:"1:1:1:1"});
  await pause();
  assert.equal(requests,1,"unchanged state must not re-fetch data");
  activeDashboard=makeDashboard();
  activeDashboard.sources.live.pipeline=[{state:"preparing",
    text:"ต้นฉบับกำลังแปลจริง",author:"ผู้ชม",inputs:[]}];
  window.VoxCoreDashboard.onRuntimeState({mode:"computer",dashboard_cursor:"2:1:1:1"});
  await pause();
  assert.equal(requests,2,"changed Core state triggers exactly one update");
  assert.match(document.getElementById("liveFeedCurrentText").textContent,
    /ต้นฉบับที่ Core กำลังเตรียม\/แปล.*ต้นฉบับกำลังแปลจริง/);
  assert.doesNotMatch(document.getElementById("liveFeedCurrentText").textContent,/เสียงที่สร้างจริง/);
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
  activeDashboard=makeDashboard();
  activeDashboard.sources.live.status={state:"idle",received:5,discarded:0};
  activeDashboard.sources.live.counts={};
  activeDashboard.sources.live.source_pending=0;
  activeDashboard.sources.live.pipeline=[];
  activeDashboard.sources.live.buffered_count=0;
  window.VoxCoreDashboard.onRuntimeState({mode:"computer",dashboard_cursor:"5:1:1:1"});
  await pause();
  assert.equal(requests,4,"returning to Computer mode inspects Core once");
  assert.equal(document.getElementById("liveFeedStart").disabled,false,
    "disconnected source must offer explicit Connect");
  assert.equal(document.getElementById("liveFeedStop").disabled,true,
    "disconnected source cannot claim a stop is possible");
  assert.equal(document.getElementById("liveFeedAuto").disabled,false,
    "offline auto-read setting remains editable for next Connect");
  assert.equal(document.getElementById("liveFeedReset").disabled,true,
    "empty source input queue has nothing to reset");
  console.log("PASS: computer dashboard hydrate/refresh, truthful stages/history, Core controls after reconnect/disconnect, zero new loops");
})().catch(error=>{console.error(error);process.exitCode=1});
