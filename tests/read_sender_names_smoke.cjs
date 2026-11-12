// TTS sender-name option: four isolated sources, auto queue and manual pick.
const assert=require("node:assert/strict");
const fs=require("node:fs");
const vm=require("node:vm");
const source=fs.readFileSync("web/mode_inputs.js","utf8");
const html=fs.readFileSync("web/index.html","utf8");
for(const prefix of ["live","tiktok","discord","discordClient"]){
  assert.ok(html.includes('id="'+prefix+'FeedReadSender"'));
}
const nodes=new Map();
function el(id){
  if(!nodes.has(id))nodes.set(id,{
    value:"",checked:false,paused:true,ended:false,events:{},
    textContent:"",style:{display:"none"},
    addEventListener(type,callback){this.events[type]=callback;},
    async play(){this.paused=false;this.ended=false;},
    pause(){this.paused=true;},
    removeAttribute(){},load(){},
  });
  return nodes.get(id);
}
let idIndex=0,latest=[];
const context={
  window:{},JSON,Blob,URL:{
    createObjectURL:()=> "blob:fixture",revokeObjectURL:()=>{},
  },
  Promise,Number,
  setTimeout:fn=>{queueMicrotask(fn);return 1;},
  async fetch(path,options={}){
    if(path==="/v1/jobs"&&options.method==="POST"){
      const payload=JSON.parse(options.body);
      latest.push(payload);
      const id=String(++idIndex).padStart(32,"0");
      return{ok:true,async json(){return{speech_id:id};}};
    }
    if(path.endsWith("/cancel"))return{ok:true,async json(){return{};}};
    if(path.endsWith("/audio"))return{ok:true,async blob(){return new Blob(["RIFF-fixture"])}};
    if(path.startsWith("/v1/jobs/"))return{ok:true,async json(){return{
      state:"ready",speech_id:path.split("/").at(-1),audio:{
        duration_ms:800,segments:[{kind:"speech",start_ms:0,end_ms:800,display_text:"ข้อความ"}],
      },
    }}};
    throw Error("Unexpected fetch "+path);
  },
};
const clock={attach(audio,report,onState){return{
  setSpeech(){onState({text:"พูดอยู่"});},
  clear(){onState({text:""});},
}}};
vm.createContext(context);
vm.runInContext(source,context);
const tick=()=>new Promise(resolve=>setImmediate(resolve));
async function test(){
  const instances=new Map();
  for(const mode of ["live","tiktok","discord","discord_client"]){
    const prefix=mode==="discord_client"?"discordClient":mode;
    const reader=context.window.VoxModeInputs.attach({
      mode,el,clockLibrary:clock,report:()=>{},
      getSpeechPayload:(text,m)=>({text,engine_id:"engine-"+m}),
      guard:()=>true,
    });
    instances.set(mode,reader);
    const checkbox=el(prefix+"FeedReadSender");
    checkbox.checked=true;
    el(prefix+"FeedAuto").checked=true;
    assert.equal(reader.receiveIncoming({
      message_id:mode+"-1",author:"คุณทดสอบ",text:"สวัสดีครับ",
    },true),"queued");
    await tick();
    let payload=latest.at(-1);
    assert.equal(payload.text,"คุณทดสอบ พิมพ์ว่า สวัสดีครับ");
    assert.equal(payload.engine_id,"engine-"+mode);
    assert.equal(el(prefix+"Text").value,"สวัสดีครับ","editable draft remains plain");
    // User switches the setting while the next message waits in this
    // source's FIFO. The next TTS job should use the latest checkbox value.
    reader.receiveIncoming({message_id:mode+"-2",author:"สมชาย",text:"ข้อความที่สอง"},true);
    checkbox.checked=false;
    el(prefix+"Audio").paused=true;
    el(prefix+"Audio").events.ended();
    await tick();
    payload=latest.at(-1);
    assert.equal(payload.text,"ข้อความที่สอง","disabled mode must not speak name");
    checkbox.checked=true;
    reader.receiveIncoming({message_id:mode+"-3",text:"ไม่มีชื่อ"},true);
    el(prefix+"Audio").paused=true;
    el(prefix+"Audio").events.ended();
    await tick();
    assert.equal(latest.at(-1).text,"ไม่มีชื่อ","missing sender must not be invented");
    el(prefix+"Audio").paused=true;
    el(prefix+"Audio").events.ended();
    reader.pickMessage({message_id:"picked",author:"เพื่อน",text:"ข้อความเลือกเอง"});
    assert.equal(el(prefix+"Text").value,"ข้อความเลือกเอง");
    await reader.submit();
    assert.equal(latest.at(-1).text,"เพื่อน พิมพ์ว่า ข้อความเลือกเอง");
    el(prefix+"Text").value="ข้อความที่แก้ไขด้วยมือ";
    el(prefix+"Text").events.input();
    await reader.submit();
    assert.equal(latest.at(-1).text,"ข้อความที่แก้ไขด้วยมือ",
      "manual edits must not retain someone else's sender");
    reader.stop({discard:true});
  }
  assert.equal(instances.size,4);
  console.log("PASS: YouTube/TikTok/Discord/Discord Client independent sender reading, queued toggle, manual selection and missing names");
}
test().catch(e=>{console.error(e);process.exitCode=1;});
