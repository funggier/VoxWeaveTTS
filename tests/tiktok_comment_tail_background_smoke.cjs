/* TikTok reader: variable badge sets, trailing comments, background DOM events,
   and recyclable message containers. No TikTok account/network is accessed. */
"use strict";
const assert=require("node:assert/strict");
const fs=require("node:fs");
const vm=require("node:vm");

const script=fs.readFileSync("extensions/tiktok-live-connector/content.js","utf8");
function makeRow(data){
  const name={
    textContent:data.author,
    contains(node){return node===this;},
    querySelector(){return null;},
    className:"SpanUserName",
    parentElement:null,
  };
  const metadata=()=>{
    const result=[];
    if(data.level)result.push({className:"BadgeLevel",textContent:String(data.level),
      getAttribute(){return null;}});
    if(data.rank)result.push({className:"BadgeRank",textContent:"No."+data.rank,
      getAttribute(){return null;}});
    if(data.badge)result.push({className:"BadgeMember",textContent:data.badge,
      getAttribute(){return null;}});
    return result;
  };
  const header={querySelectorAll(){return metadata();}};
  name.parentElement=header;
  const tail={
    get textContent(){return data.comment;},
    className:"comment-body",
    querySelector(){return null;},
    closest(){return null;},
  };
  const row={
    className:"DivChatMessageItem",
    get textContent(){return name.textContent+" "+data.comment;},
    get innerText(){
      const headerTokens=[data.level?"Lv."+data.level:"",
        data.rank?"No."+data.rank:"",data.badge||"",data.author].filter(Boolean);
      if(data.rankAfterAuthor){
        const rankLine="No. "+data.rank;
        return data.author+"\n"+rankLine+
          (data.rankInline?" ":"\n")+data.comment;
      }
      return headerTokens.join(" ") + (data.inline?" ":"\n") + data.comment;
    },
    contains(node){return node===name||node===header||node===tail||node===this;},
    getAttribute(key){return key==="data-id"?(data.id||null):null;},
    querySelector(selector){
      if(selector.includes("follow")||selector.includes("join"))return null;
      if(selector.includes("message-owner-name"))return name;
      if(selector.includes("message-text"))
        return data.noMessageElement?null:tail;
      return null;
    },
    querySelectorAll(selector){
      if(selector.includes("message-owner-name"))return [name];
      if(selector.includes("message-text"))
        return data.noMessageElement?[]:[tail];
      if(selector.includes('[data-e2e*="badge"]'))return metadata();
      if(selector==="span,p,div")
        return data.noMessageElement&&data.noLeaves?[]:[name,...metadata(),tail];
      return [];
    },
  };
  return row;
}
async function run(){
  const sends=[],events={};
  let background=false,focused=true;
  let tick=()=>{},mutation=()=>{},observed=false;
  const rows=[makeRow({id:"old",author:"A",comment:"ข้อความก่อนเชื่อมต่อ",level:12})];
  const list={
    querySelectorAll(selector){
      if(selector.includes("chat-message"))return rows;
      if(selector.includes("message-owner-name"))
        return rows.map(row=>row.querySelector(selector));
      return[];
    },
  };
  const document={
    documentElement:{},
    get visibilityState(){return background?"hidden":"visible";},
    hasFocus(){return focused;},
    querySelector(selector){
      if(selector.includes("room-chat-input-field"))return null;
      if(selector.includes("DivChatMessageList"))return list;
      return null;
    },
    addEventListener(key,fn){events[key]=fn;},
    removeEventListener(key){delete events[key];},
  };
  let listener;
  const chrome={runtime:{
    id:"abcdefghijklmnopabcdefghijklmnop",
    onMessage:{addListener(fn){listener=fn;}},
    sendMessage(message,done){sends.push(message);done?.({ok:true});},
  }};
  const ctx={document,chrome,Date,Number,WeakMap,Set,Promise,
    MutationObserver:class{
      constructor(fn){mutation=fn;}
      observe(){observed=true;}
      disconnect(){observed=false;}
    },
    setInterval(fn){tick=fn;return 1;},clearInterval(){},
    queueMicrotask:fn=>Promise.resolve().then(fn),
    setTimeout(){throw Error("DOM notification must not rely on timeout");},
    clearTimeout(){},
    addEventListener(key,fn){events["window:"+key]=fn;},
    removeEventListener(key){delete events["window:"+key];},
  };
  ctx.globalThis=ctx;
  vm.createContext(ctx);
  vm.runInContext(script,ctx);
  listener({kind:"vw-start"});
  assert.equal(sends.at(-1).items.length,0);
  assert.equal(observed,true);
  // A user with rank only; no artificial level or membership badge.
  rows.push(makeRow({id:"rank-only",author:"Tong Baisome",rank:2,
    comment:"สวนแชทเท่าๆ"}));
  // A user with no badges/level/rank.
  rows.push(makeRow({id:"plain",author:"Riskies",comment:"แม่ง"}));
  // A level-only user, with a different number of header elements.
  rows.push(makeRow({id:"level-only",author:"บริหาร",level:10,
    comment:"ไม่เก่งเองใช่ไหม ใจเดียวก็ไม่เจอเงิน"}));
  // A single-line comment has the username and message inline.
  rows.push(makeRow({id:"inline",author:"Guest",inline:true,comment:"คำมา"}));
  // Real TikTok sometimes renders the rank *after* the username in
  // innerText, even though it appears on the same visual header line.
  rows.push(makeRow({id:"rank-after-name",author:"maitreewongthawik",
    rank:2,rankAfterAuthor:true,comment:"Trum up Trum up!! 😮"}));
  rows.push(makeRow({id:"rank-inline",author:"PorchJoy Kabsee",rank:2,
    rankAfterAuthor:true,rankInline:true,noMessageElement:true,noLeaves:true,
    comment:"แพ้ใจ"}));
  rows.push(makeRow({id:"rank-separate",author:"Tester",rank:3,
    rankAfterAuthor:true,noMessageElement:true,noLeaves:true,
    comment:"No. 2 ในความเห็นนี้คือเนื้อหาจริง"}));
  rows.push(makeRow({id:"legit-no",author:"Riskies",noMessageElement:true,
    noLeaves:true,comment:"No. 2 เป็นชื่อเพลงที่ชอบ"}));
  rows.push(makeRow({id:"rank2-genuine-no",author:"ExactRank",rank:2,
    rankAfterAuthor:true,comment:"No. 2 หมายถึงอันดับที่ฉันพูดถึง"}));
  background=true;focused=false;
  mutation([{target:list}]);
  await Promise.resolve();
  assert.equal(observed,true);
  const snapshot=sends.at(-1);
  assert.equal(snapshot.phase,"ready");
  assert.equal(snapshot.diagnostics.tab_visible,false);
  assert.equal(snapshot.diagnostics.tab_focused,false);
  assert.equal(snapshot.items.length,9,"background DOM updates must be captured");
  const ranks=snapshot.items.find(x=>x.id==="rank-only");
  assert.equal(ranks.text,"สวนแชทเท่าๆ");
  assert.equal(ranks.rank,"2");
  assert.equal(ranks.level,"");
  assert.deepEqual(Array.from(ranks.badges),[]);
  const plain=snapshot.items.find(x=>x.id==="plain");
  assert.equal(plain.text,"แม่ง");
  assert.equal(plain.level,"");
  assert.equal(plain.rank,"");
  const level=snapshot.items.find(x=>x.id==="level-only");
  assert.equal(level.level,"10");
  assert.equal(level.rank,"");
  assert.equal(level.text,"ไม่เก่งเองใช่ไหม ใจเดียวก็ไม่เจอเงิน");
  assert.equal(snapshot.items.find(x=>x.id==="inline").text,"คำมา");
  assert.equal(snapshot.items.find(x=>x.id==="rank-after-name").text,
    "Trum up Trum up!! 😮","rank badge must not leak into comment body");
  assert.equal(snapshot.items.find(x=>x.id==="rank-inline").text,"แพ้ใจ",
    "inline header rank prefix is not a comment");
  assert.equal(snapshot.items.find(x=>x.id==="rank-separate").text,
    "No. 2 ในความเห็นนี้คือเนื้อหาจริง",
    "strip only the rank badge line, not a user's rank-like message");
  assert.equal(snapshot.items.find(x=>x.id==="legit-no").text,
    "No. 2 เป็นชื่อเพลงที่ชอบ",
    "no badge => do not alter a legitimate No. 2 comment");
  assert.equal(snapshot.items.find(x=>x.id==="rank2-genuine-no").text,
    "No. 2 หมายถึงอันดับที่ฉันพูดถึง",
    "an explicit comment body is authoritative, even with matching No. 2 badge");
  const before=sends.length;
  tick();
  assert.equal(sends.at(-1).items.length,0,"unchanged items not duplicated");
  // When a React row is reused without a durable id, its content changes.
  const recycledData={id:"",author:"Guest",comment:"คอมเมนต์แรก"};
  const recycled=makeRow(recycledData);
  rows.push(recycled);
  mutation([{target:list}]);
  await Promise.resolve();
  assert.equal(sends.at(-1).items.length,1);
  assert.equal(sends.at(-1).items[0].text,"คอมเมนต์แรก");
  const oldId=sends.at(-1).items[0].id;
  recycledData.comment="คอมเมนต์ใหม่ในแถวเดิม";
  mutation([{target:list}]);
  await Promise.resolve();
  assert.equal(sends.at(-1).items.length,1);
  assert.equal(sends.at(-1).items[0].text,"คอมเมนต์ใหม่ในแถวเดิม");
  assert.notEqual(sends.at(-1).items[0].id,oldId);
  background=false;focused=true;
  events.visibilitychange();
  await Promise.resolve();
  assert.equal(sends.at(-1).diagnostics.tab_visible,true);
  assert.equal(sends.at(-1).items.length,0);
  listener({kind:"vw-stop"});
  assert.equal(observed,false);
  assert.equal(events.visibilitychange,undefined);
  assert.ok(sends.length>before);
}
run().then(()=>console.log(
  "PASS: trailing comments for all badge variants, background DOM capture, recycled rows"
)).catch(error=>{console.error(error);process.exitCode=1;});
