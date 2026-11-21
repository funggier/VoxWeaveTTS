"use strict";
// Regression: the final Live-mode status must describe connection + work,
// not only the last "กำลังรับข้อความ" or "หยุดเสียง" notification.
const assert=require("node:assert/strict");
const fs=require("node:fs");
const {attach}=require("../web/mode_inputs.js");

for(const mode of ["live","youtube_browser","tiktok_browser","tiktok",
                   "discord","discord_client"]){
  const prefix=mode==="youtube_browser"?"youtubeBrowser":
    mode==="tiktok_browser"?"tiktokBrowser":
    mode==="discord_client"?"discordClient":mode;
  const elements=new Map();
  const get=id=>{
    if(!elements.has(id))elements.set(id,{
      value:"",checked:false,disabled:false,style:{},textContent:"",
      href:"",src:"",paused:true,ended:false,events:{},
      addEventListener(name,fn){this.events[name]=fn;},
      pause(){this.paused=true;},load(){},
      removeAttribute(name){if(name==="src")this.src="";},
    });
    return elements.get(id);
  };
  const audio=get(prefix+"Audio");
  get(prefix+"FeedAuto").checked=true;
  const ctrl=attach({
    mode,el:get,guard:()=>true,report(){},
    clockLibrary:{attach(){return{clear(){},setSpeech(){}};}},
    getSpeechPayload:text=>({text}),
    playAudio:async()=>true,cancelAudio(){audio.paused=true;},
  });
  const status=()=>get(prefix+"Status").textContent;
  assert.match(status(),/รับข้อความ: ยังไม่เชื่อมต่อ/,mode);
  assert.match(status(),/การอ่าน: รอข้อความใหม่/,mode);
  assert.match(status(),/คิว: แชทดิบ 0/,mode);
  assert.match(status(),/เสียงรอเล่น 0 · อ่านจบ 0 · สุ่มลบ 0/,mode);
  // Connection state and transport counters survive changes to speech.
  ctrl.setSourceStatus({state:"connecting",connected:true,
    phase:"waiting_extension_pair",received:0,discarded:0,pending:0});
  assert.match(status(),/รอจับคู่ Extension/,mode);
  ctrl.setSourceStatus({state:"running",connected:true,
    phase:"ready",received:17,discarded:3,pending:2});
  assert.match(status(),/รับข้อความ: กำลังรับแชท · รับแล้ว 17 · กรอง 3 · รอรับจากต้นทาง 2/,mode);
  // Incoming TTS cannot begin while another audio is already playing.
  audio.paused=false;
  assert.equal(ctrl.receiveIncoming({message_id:"r1",text:"คิวหนึ่ง"},true),"queued");
  assert.equal(ctrl.receiveIncoming({message_id:"r2",text:"คิวสอง"},true),"queued");
  assert.match(status(),/การอ่าน: กำลังเล่นเสียง/,mode);
  assert.match(status(),/แชทดิบ 2/,mode);
  assert.match(status(),/รับแล้ว 17/,mode);
  ctrl.setSourceStatus({state:"extension_disconnected",connected:true,
    phase:"extension_disconnected"});
  assert.match(status(),/Extension ขาดการเชื่อมต่อ/,mode);
  get(prefix+"Stop").events.click();
  assert.match(status(),/พักคิวอ่าน/,mode);
  assert.match(status(),/แชทดิบ 0/,mode);
  assert.match(status(),/แจ้งเตือน: หยุดเสียงของโหมดนี้แล้ว/,mode);
  assert.ok(fs.readFileSync("web/index.html","utf8").includes(
    'id="'+prefix+'Status" class="small live-runtime-status"'),
    "runtime status display missing for "+mode);
}
console.log("PASS: six Live footers show connection, actual queue stages/counts, disconnection, stop; no stale one-line status");
