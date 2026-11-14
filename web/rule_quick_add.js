/* Quick Rules editor contract shared by the UI and offline regression tests.
 * Mirrors src/voxweavetts/processing.py Rule.parse. No arbitrary regex.
 */
(function(root){
"use strict";
const SOURCE_OPTIONS=Object.freeze([
  {value:"manual",label:"ข้อความทั่วไป / API (manual)"},
  {value:"document",label:"เอกสาร (document)"},
  {value:"youtube-live",label:"YouTube LIVE (API)"},
  {value:"youtube-live-browser",label:"YouTube LIVE (Browser)"},
  {value:"tiktok-live",label:"TikTok LIVE (TikFinity)"},
  {value:"tiktok-live-extension",label:"TikTok LIVE (Extension)"},
  {value:"discord",label:"Discord (Bot / Client)"},
]);
const MATCH_MODES=Object.freeze(["literal","five_run"]);
const ACTIONS=Object.freeze(["replace","skip","silence"]);
function fail(message){throw new Error(message);}
function sourceList(checked=[],extra=""){
  if(!Array.isArray(checked)||typeof extra!=="string")
    fail("รายการแหล่งข้อความไม่ถูกต้อง");
  const additional=extra.trim()
    ?extra.split(",").map(s=>s.trim()):[];
  const sources=[...checked,...additional];
  if(sources.some(x=>typeof x!=="string" || !x || x.length>64))
    fail("ชื่อแหล่งข้อความต้องไม่ว่างและยาวไม่เกิน 64 ตัวอักษร");
  const unique=[...new Set(sources)];
  if(unique.length>32)fail("เลือกแหล่งข้อความได้สูงสุด 32 รายการ");
  return unique;
}
function build(options){
  if(!options||typeof options!=="object")fail("ข้อมูลกฎไม่ถูกต้อง");
  const match_mode=options.match_mode||"literal";
  if(!MATCH_MODES.includes(match_mode))
    fail("รูปแบบค้นหาต้องเป็นข้อความตรงตัวหรือเลข 5 ต่อเนื่อง");
  const match=match_mode==="five_run"?"555":options.match;
  if(typeof match!=="string"||!match.trim()||match.length>200)
    fail("ข้อความที่ค้นหาต้องไม่ว่างและยาวไม่เกิน 200 ตัวอักษร");
  const mode=options.mode||"replace";
  if(!ACTIONS.includes(mode))fail("เลือกการทำงานของกฎ");
  const stage=options.stage||"post_ai";
  if(!["pre_ai","post_ai"].includes(stage))fail("เลือกช่วงกฎก่อน AI หรือหลัง AI");
  if(stage==="pre_ai"&&mode==="silence")fail("หยุดเสียงได้หลัง AI เท่านั้น เพราะการแปลจะทำให้เวลาหยุดเสียงสูญหาย");
  const rule={match,mode};
  if(stage==="pre_ai")rule.stage=stage;
  if(match_mode==="five_run")rule.match_mode=match_mode;
  if(mode==="replace"){
    const spoken=options.spoken??"";
    if(typeof spoken!=="string"||spoken.length>500)
      fail("คำอ่านแทนยาวได้สูงสุด 500 ตัวอักษร");
    if(spoken!=="")rule.spoken=spoken;
  }
  const display=options.display??"";
  if(typeof display!=="string"||display.length>500)
    fail("ข้อความที่แสดงยาวได้สูงสุด 500 ตัวอักษร");
  if(display!=="")rule.display=display;
  if(mode==="silence"){
    const duration=options.silence_ms??400;
    // Inputs are strings, but no decimals/scientific formats are accepted.
    if(!((typeof duration==="string"&&/^\d+$/.test(duration))
       ||(typeof duration==="number"&&Number.isInteger(duration))))
      fail("เวลาหยุดเสียงต้องเป็นจำนวนเต็ม 0–10000 มิลลิวินาที");
    const ms=Number(duration);
    if(ms<0||ms>10000)fail("เวลาหยุดเสียงต้องอยู่ระหว่าง 0–10000 มิลลิวินาที");
    rule.silence_ms=ms;
  }
  const sources=sourceList(options.sources||[],options.extra_sources||"");
  if(sources.length)rule.sources=sources;
  return rule;
}
function append(rules,options){
  if(!Array.isArray(rules))fail("Rules ต้องเป็น JSON Array");
  if(rules.length>=128)fail("Rules เพิ่มได้สูงสุด 128 กฎ");
  const rule=build(options);
  // Reject only an identical rule. The engine allows intentionally
  // overlapping rules: earliest match, then longest, then array order.
  if(rules.some(item=>JSON.stringify(item)===JSON.stringify(rule)))
    fail("มีกฎเดียวกันใน JSON อยู่แล้ว");
  return [...rules,rule];
}
const api={SOURCE_OPTIONS,MATCH_MODES,ACTIONS,sourceList,build,append};
root.VoxRuleQuickAdd=api;
if(typeof module!=="undefined"&&module.exports)module.exports=api;
})(typeof window==="undefined"?globalThis:window);
