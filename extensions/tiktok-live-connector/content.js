"use strict";
/* User-initiated, DOM-only TikTok LIVE comment reader.
   No login, network interception, script injection into page world, or
   attempt to alter the site's playback / access restrictions. */
(()=>{
  if(globalThis.__voxweaveTikTokReaderInstalled)return;
  globalThis.__voxweaveTikTokReaderInstalled=true;
  let running=false,observer=null,heartbeat=null,delay=null,started=false,seq=0;
  const known=new Set(), fallback=new WeakMap();
  const idPrefix="xt"+Date.now().toString(36)+"-";
  function chatList(){
    return document.querySelector(
      '[class*="DivChatMessageList"],[data-e2e="live-chat-message-list"]'
    ) || document.querySelector(
      '[data-e2e="live-chat-container"] [class*="overflow-y-scroll"]'
    );
  }
  function rows(list){
    const candidates=[...list.querySelectorAll(
      '[data-e2e="chat-message"],[data-e2e="live-chat-message"],'
      +'[data-e2e="room-chat-message"],div[class*="DivChatMessage"]'
    )].filter(n=>n!==list&&!/DivChatMessageList|DivChatMessageText/.test(String(n.className)));
    return candidates.filter(n=>!candidates.some(p=>p!==n&&p.contains(n))).slice(-100);
  }
  function parseRow(node){
    if(node.querySelector('[data-e2e*="gift"],[data-e2e*="follow"],[data-e2e*="join"]'))return null;
    const textNode=node.querySelector(
      '[data-e2e="message-text"],[data-e2e="comment-content"],'
      +'[data-e2e="chat-message-text"],[class*="SpanChatMessageText"],'
      +'[class*="DivChatMessageText"],[class*="SpanMessageText"]'
    );
    if(!textNode)return null;
    const text=(textNode.textContent||"").trim().slice(0,280);
    if(!text)return null;
    const name=node.querySelector(
      '[data-e2e="message-owner-name"],[data-e2e="chat-message-name"],'
      +'[class*="SpanUserName"],a[href^="/@"]'
    );
    let id=node.getAttribute("data-id")||node.getAttribute("data-message-id")||"";
    if(!/^[a-zA-Z0-9_.:\-]{1,160}$/.test(id)){
      if(!fallback.has(node))fallback.set(node,idPrefix+(++seq));
      id=fallback.get(node);
    }
    return {id,author:(name?.textContent||"").trim().slice(0,80),text};
  }
  function send(phase,items){
    if(!running)return;
    chrome.runtime.sendMessage({kind:"vw-chat-batch",phase,items},result=>{
      if(chrome.runtime.lastError || result?.ok===false){
        // Do not retry the login, open new windows or make direct API calls.
        // Stop only if the local bridge is no longer authorized.
        if(result?.error==="not authorized tab")stop();
      }
    });
  }
  function scan(){
    if(!running)return;
    const input=document.querySelector(
      '[data-e2e="room-chat-input-field"][placeholder],'
      +'[contenteditable][placeholder],textarea[placeholder]'
    );
    const off=/^comments\s+(off|disabled)$/i.test((input?.getAttribute("placeholder")||"").trim());
    const list=chatList();
    if(off){send("comments_off",[]);return;}
    if(!list){send("waiting_chat_dom",[]);return;}
    const items=[];
    for(const node of rows(list)){
      const item=parseRow(node);
      if(!item||known.has(item.id))continue;
      known.add(item.id);
      if(started && items.length<20)items.push(item);
    }
    started=true;
    if(known.size>3500){
      // Preserve a bounded last-seen map when the LIVE lasts for hours.
      const recent=[...known].slice(-1700);
      known.clear();recent.forEach(id=>known.add(id));
    }
    send("ready",items);
  }
  function schedule(){
    if(!running||delay!==null)return;
    delay=setTimeout(()=>{delay=null;scan();},500);
  }
  function start(){
    if(running)return;
    running=true;started=false;known.clear();
    observer=new MutationObserver(schedule);
    observer.observe(document.documentElement,{childList:true,subtree:true,attributes:false});
    heartbeat=setInterval(scan,3500);
    scan();
  }
  function stop(){
    running=false;started=false;known.clear();
    if(observer){observer.disconnect();observer=null;}
    if(heartbeat!==null){clearInterval(heartbeat);heartbeat=null;}
    if(delay!==null){clearTimeout(delay);delay=null;}
  }
  chrome.runtime.onMessage.addListener(message=>{
    if(message?.kind==="vw-start"){start();return;}
    if(message?.kind==="vw-stop")stop();
  });
})();
