"use strict";
/* MV3 extension service worker: least-privilege bridge to the loopback app.
   Requires explicit action on a selected LIVE tab, and one-time pairing. */
const SESSION_KEY="voxweave_tiktok_live_connection";
function liveUsername(raw){
  try{
    const u=new URL(raw);
    if(u.protocol!=="https:" || !["www.tiktok.com","tiktok.com"].includes(u.hostname))return null;
    const m=/^\/@([a-zA-Z0-9_.]{2,24})\/live\/?$/.exec(u.pathname);
    return m?m[1].toLowerCase():null;
  }catch{return null;}
}
async function post(port,action,payload){
  const response=await fetch("http://127.0.0.1:"+port+"/v1/extension/"+action,{
    method:"POST",headers:{"Content-Type":"application/json",
      "X-VoxWeaveTTS-Intent":"tiktok-extension"},
    body:JSON.stringify(payload),cache:"no-store",
  });
  const body=await response.json().catch(()=>({}));
  if(!response.ok)throw Error(body.error||"VoxWeaveTTS ปฏิเสธการเชื่อมต่อ");
  return body;
}
async function getSession(){
  return (await chrome.storage.session.get(SESSION_KEY))[SESSION_KEY]||null;
}
async function stop(){
  const active=await getSession();
  await chrome.storage.session.remove(SESSION_KEY);
  if(!active)return;
  try{await chrome.tabs.sendMessage(active.tabId,{kind:"vw-stop"});}catch{}
  try{await post(active.port,"disconnect",{token:active.token});}catch{}
}
async function start(port,code){
  if(!Number.isInteger(port)||port<1||port>65535
     ||typeof code!=="string"||!code||code.length>160)throw Error("Port หรือรหัสจับคู่ไม่ถูกต้อง");
  const tabs=await chrome.tabs.query({active:true,currentWindow:true});
  const tab=tabs[0];
  if(!tab||!Number.isInteger(tab.id)||!liveUsername(tab.url))
    throw Error("เปิดแท็บ https://www.tiktok.com/@username/live ก่อนกดเชื่อมต่อ");
  // Explicit user click grants activeTab + scripting only for this tab.
  await chrome.scripting.executeScript({target:{tabId:tab.id},files:["content.js"]});
  await stop();
  const paired=await post(port,"pair",{code,url:tab.url});
  if(typeof paired.token!=="string"||paired.token.length<24)
    throw Error("VoxWeaveTTS ตอบกลับการจับคู่ไม่ถูกต้อง");
  const session={tabId:tab.id,port,token:paired.token,url:tab.url,
    username:liveUsername(tab.url)};
  await chrome.storage.session.set({[SESSION_KEY]:session});
  try{
    await chrome.tabs.sendMessage(tab.id,{kind:"vw-start"});
  }catch(error){
    await stop();
    throw Error("ไม่สามารถเริ่มตัวอ่าน DOM ในแท็บ TikTok ได้");
  }
  return {ok:true};
}
async function forward(data,sender){
  const session=await getSession();
  if(!session || !sender.tab || sender.tab.id!==session.tabId
     ||sender.id!==chrome.runtime.id
     ||liveUsername(sender.url)!==session.username)return {ok:false,error:"not authorized tab"};
  const rows=Array.isArray(data.items)?data.items:[];
  if(rows.length>20 || !["ready","waiting_chat_dom","comments_off"].includes(data.phase))
    return {ok:false,error:"invalid chat batch"};
  try{
    const result=await post(session.port,"messages",{
      url:sender.url,token:session.token,phase:data.phase,items:rows,
    });
    return {ok:true,accepted:result.accepted||0};
  }catch(error){
    // A stale app token after restart may no longer be usable.
    if(/connection|expired|authorized|source|invalid/i.test(error.message)){
      await chrome.storage.session.remove(SESSION_KEY);
    }
    return {ok:false,error:"Local bridge unavailable; restart pairing in VoxWeaveTTS"};
  }
}
chrome.runtime.onMessage.addListener((msg,sender,reply)=>{
  if(sender.id!==chrome.runtime.id || !msg || typeof msg!=="object")return false;
  const fromPopup=typeof sender.url==="string"
    && sender.url.startsWith("chrome-extension://"+chrome.runtime.id+"/popup.html");
  let work;
  if(msg.kind==="vw-chat-batch" && sender.tab){
    work=forward(msg,sender);
  }else if(fromPopup && msg.type==="vw-start"){
    work=start(msg.port,msg.code);
  }else if(fromPopup && msg.type==="vw-stop"){
    work=stop().then(()=>({ok:true}));
  }else if(fromPopup && msg.type==="vw-status"){
    work=getSession().then(s=>({ok:true,connected:!!s}));
  }else return false;
  Promise.resolve(work).then(reply,error=>reply({ok:false,error:String(error.message||error)}));
  return true;
});
chrome.tabs.onRemoved.addListener(async tabId=>{
  const session=await getSession();
  if(session && session.tabId===tabId)await stop();
});
