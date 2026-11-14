"use strict";
const assert=require("node:assert/strict");
const {SOURCE_OPTIONS,build,append,sourceList}=require("../web/rule_quick_add.js");
const actualSources=SOURCE_OPTIONS.map(x=>x.value);
assert.deepEqual(actualSources,[
  "manual","document","youtube-live","youtube-live-browser",
  "tiktok-live","tiktok-live-extension","discord"
]);
const replacement=build({match:"สวัสดี!",mode:"replace",spoken:"สวัสดีครับ",
  display:"ทักทาย",sources:["youtube-live","tiktok-live-extension"],
  extra_sources:"external-api, youtube-live"});
assert.deepEqual(replacement,{
  match:"สวัสดี!",mode:"replace",spoken:"สวัสดีครับ",
  display:"ทักทาย",sources:["youtube-live","tiktok-live-extension","external-api"]
});
assert.deepEqual(build({match:"คำไม่สุภาพ",mode:"skip"}),{
  match:"คำไม่สุภาพ",mode:"skip"
});
assert.deepEqual(build({match:"คำต้องห้าม",mode:"silence",silence_ms:"650",
  display:"[เงียบ]"}),{
  match:"คำต้องห้าม",mode:"silence",display:"[เงียบ]",silence_ms:650
});
assert.deepEqual(build({match_mode:"five_run",match:"ignored",
  mode:"replace",spoken:"ฮ่า ฮ่า ฮ่า"}),{
  match:"555",mode:"replace",match_mode:"five_run",spoken:"ฮ่า ฮ่า ฮ่า"
});
assert.deepEqual(build({match:"aa",mode:"replace",spoken:""}),{
  match:"aa",mode:"replace"
},"empty spoken omits optional value");
assert.deepEqual(build({match:"aa",mode:"skip",spoken:"ignored",
  silence_ms:900}),{match:"aa",mode:"skip"},
  "hidden mode-only values must not leak into saved rules");
assert.equal(build({match:"ab",mode:"silence",silence_ms:"0"}).silence_ms,0);
assert.deepEqual(sourceList(["discord","manual"],"discord,alpha"),[
  "discord","manual","alpha"
]);
const special='ทดสอบ"\\!';
const list=append([{"match":"ก่อนหน้า","mode":"replace"}],{
  match:special,mode:"replace",spoken:"คำใหม่"
});
assert.equal(list.length,2);
assert.equal(list[1].match,special);
assert.equal(list[0].match,"ก่อนหน้า");
assert.throws(()=>append(list,{match:special,mode:"replace",spoken:"คำใหม่"}),/กฎเดียวกัน/);
assert.throws(()=>append(new Array(128).fill({}),{match:"x"}),/128/);
assert.throws(()=>append({}, {match:"x"}),/JSON Array/);
const bad=[
  {match:""},{match:" "},{match:"a".repeat(201)},
  {match:"good",match_mode:"regex"},
  {match:"good",mode:"mask"},{match:"good",spoken:"a".repeat(501)},
  {match:"good",display:"a".repeat(501)},
  {match:"good",mode:"silence",silence_ms:"1.5"},
  {match:"good",mode:"silence",silence_ms:"1e3"},
  {match:"good",mode:"silence",silence_ms:""},
  {match:"good",mode:"silence",silence_ms:-1},
  {match:"good",mode:"silence",silence_ms:10001},
  {match:"good",sources:[""]},
  {match:"good",sources:["x".repeat(65)]},
  {match:"good",sources:new Array(33).fill(0).map((_,i)=>"s"+i)},
  {match:"good",extra_sources:"first,"},
];
for(const input of bad)
  assert.throws(()=>build(input),"invalid quick rule should be rejected: "+JSON.stringify(input).slice(0,90));
assert.equal(Object.prototype.hasOwnProperty.call(
  build({match:"555",mode:"replace"}),"match_mode"),false,
  "literal match needs no nondefault match_mode");
console.log("PASS: Rules quick add covers backend schema, all modes, five_run, sources, bounds and duplicates");
