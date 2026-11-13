"use strict";
/* Explicitly user-activated, DOM-only TikTok LIVE comment reader.
   Never reads login/cookies or bypasses TikTok security/access controls.
   Diagnostics are counts only, not raw HTML or private account data. */
(()=>{
  if(globalThis.__voxweaveTikTokReaderInstalled)return;
  globalThis.__voxweaveTikTokReaderInstalled=true;
  let running=false,observer=null,heartbeat=null,delay=null,started=false,seq=0;
  const known=new Set(), fallback=new WeakMap();
  const idPrefix="xt"+Date.now().toString(36)+"-";
  const ROW_SELECTOR=[
    '[data-e2e="chat-message"]','[data-e2e="live-chat-message"]',
    '[data-e2e="room-chat-message"]',
    '[data-e2e*="chat-message-item"]',
    '[data-e2e*="gift-message"]','[data-e2e*="gift-notification"]',
    '[class*="DivChatMessage"]:not([class*="DivChatMessageList"])',
    '[class*="ChatMessageItem"]','[class*="GiftMessage"]',
  ].join(",");
  const NAME_SELECTOR=[
    '[data-e2e="message-owner-name"]','[data-e2e="chat-message-name"]',
    '[data-e2e*="nickname"]','[class*="SpanUserName"]',
    '[class*="UserName"]','a[href^="/@"]',
  ].join(",");
  const TEXT_SELECTOR=[
    '[data-e2e="message-text"]','[data-e2e="comment-content"]',
    '[data-e2e="chat-message-text"]','[data-e2e*="chat-text"]',
    '[class*="SpanChatMessageText"]','[class*="DivChatMessageText"]',
    '[class*="SpanMessageText"]','[class*="CommentText"]',
  ].join(",");
  function findList(){
    const known=document.querySelector(
      '[class*="DivChatMessageList"],[data-e2e="live-chat-message-list"]'
    ) || document.querySelector(
      '[data-e2e="live-chat-container"] [class*="overflow-y-scroll"]'
    );
    return known || document.querySelector('[data-e2e="live-chat-container"]');
  }
  function isSystemNotice(node){
    const marker=(String(node.className||"")+" "+String(node.getAttribute?.("data-e2e")||"")).toLowerCase();
    // Gifts are legitimate *separate* events; joins/follows/likes/shares
    // remain excluded from the comment/gift feed.
    if(/follow|join|system|notice|pinned|moderator/.test(marker))return true;
    if(/gift/.test(marker))return false;
    if(/\b(liked|shared|joined|followed) the live\b/i.test(node.textContent||""))return true;
    return Boolean(node.querySelector?.('[data-e2e*="follow"],[data-e2e*="join"],'
      +'[class*="SystemMessage"]'));
  }
  function decorations(row,nameNode){
    // Only inspect metadata *near the username*, not text of the comment.
    const parent=nameNode?.parentElement;
    const badgeRoot=parent&&row.contains(parent)?parent:row;
    const labels=[];
    const decorated=badgeRoot.querySelectorAll?.(
      '[data-e2e*="badge"],[data-e2e*="level"],[data-e2e*="rank"],'
      +'[class*="Badge"],[class*="Level"],[class*="Rank"],'
      +'[aria-label*="level"],[aria-label*="rank"],'
      +'[title*="level"],[title*="rank"]'
    )||[];
    for(const element of [...decorated].slice(0,24)){
      if(element===nameNode)continue; // Nested badge icons are metadata, not the username.
      const descriptor=(String(element.className||"")+" "+
        (element.getAttribute?.("data-e2e")||"")+" "+
        (element.getAttribute?.("aria-label")||"")).toLowerCase();
      const raw=(element.getAttribute?.("aria-label")||
        element.getAttribute?.("title")||element.textContent||
        element.querySelector?.("img")?.alt||"").trim().slice(0,48);
      if(raw)labels.push({raw,descriptor});
    }
    let level="",rank="";
    const badges=[];
    for(const {raw,descriptor} of labels){
      const ranking=/\b(?:no\.?|rank|อันดับ)\s*[:.#-]?\s*(\d{1,4})/i.exec(raw);
      const leveled=/\b(?:lv\.?|level|เลเวล)\s*[:.#-]?\s*(\d{1,4})/i.exec(raw);
      if(!rank&&(ranking||/rank|ranking/.test(descriptor)&&/^\d{1,4}$/.test(raw)))
        rank=ranking?ranking[1]:raw;
      else if(!level&&(leveled||/level/.test(descriptor)&&/^\d{1,4}$/.test(raw)))
        level=leveled?leveled[1]:raw;
      else if(!badges.includes(raw) && badges.length<8)badges.push(raw);
    }
    return {level,rank,badges};
  }
  function toRow(nameNode,list){
    // In current LIVE layouts, the comment row may have only generic flex
    // classnames. Start from a visible nickname and find its small wrapper.
    const name=(nameNode.textContent||"").trim();
    let parent=nameNode.parentElement;
    for(let depth=0;parent&&depth<6&&parent!==list;parent=parent.parentElement,depth++){
      const value=(parent.textContent||"").trim();
      if(value.length>name.length+1&&value.length<=550
         &&parent.querySelector?.(NAME_SELECTOR)
         &&!isSystemNotice(parent))return parent;
    }
    return null;
  }
  function collectRows(list){
    const direct=[...list.querySelectorAll(ROW_SELECTOR)].filter(n=>
      !/DivChatMessageList|DivChatMessageText/.test(String(n.className))
      &&!isSystemNotice(n)
    );
    const candidates=direct.filter(n=>
      !direct.some(p=>p!==n&&p.contains(n))
    );
    const nameNodes=[...list.querySelectorAll(NAME_SELECTOR)];
    const authorNodes=nameNodes.length;
    if(!candidates.length){
      const found=new Set();
      for(const name of nameNodes){
        const row=toRow(name,list);
        if(row && !found.has(row)){found.add(row);candidates.push(row);}
      }
      // A wrapper may contain the entire scroller. Keep only small rows,
      // and avoid repeating a parent and its child.
      return {rows:candidates.filter(row=>!candidates.some(other=>
        other!==row&&row.contains(other))),authorNodes,method:"author"};
    }
    return {rows:candidates,authorNodes,method:"structured"};
  }
  function parseRow(node){
    if(isSystemNotice(node))return null;
    const nameNode=node.querySelector(NAME_SELECTOR);
    if(!nameNode)return null;
    // Prefer the textual nickname; nested decorative level/badge elements are
    // not part of the speaker's actual display name.
    const nickname=nameNode.querySelector?.(
      '[data-e2e*="nickname"],[class*="Nickname"],[class*="UserNameText"]'
    )||nameNode;
    // A display-name node may contain injected level/badge elements.
    const isolated=typeof nickname.cloneNode==="function"
      ?nickname.cloneNode(true):null;
    if(isolated){
      for(const badge of isolated.querySelectorAll?.(
        '[data-e2e*="badge"],[data-e2e*="level"],[data-e2e*="rank"],'
        +'[class*="Badge"],[class*="Level"],[class*="Rank"],img,svg'
      )||[])badge.remove?.();
    }
    const author=((isolated||nickname).textContent||"")
      .replace(/\s+/g," ").trim().slice(0,80);
    if(!author)return null;
    const meta=decorations(node,nameNode);
    const textNode=node.querySelector(TEXT_SELECTOR);
    let text=(textNode?.textContent||"").trim();
    if(!text){
      // Leaf-only fallback, excluding badges, ranks, icons and usernames.
      const leaf=[...node.querySelectorAll("span,p")]
        .filter(n=>n!==nameNode&&!nameNode.contains(n)
          && !n.querySelector("span,p")
          && !/badge|level|rank|gifticon/i.test(String(n.className||""))
          && !n.closest?.('[data-e2e*="badge"],[data-e2e*="level"],'
                            +'[data-e2e*="rank"],[data-e2e*="gift-icon"]'))
        .map(n=>(n.textContent||"").trim())
        .filter(value=>value&&value!==author&&value.length<=280);
      if(leaf.length)text=leaf.at(-1);
    }
    if(!text){
      const whole=(node.innerText||node.textContent||"").trim();
      if(whole.startsWith(author))
        text=whole.slice(author.length).replace(/^\s*[:：]\s*/,"").trim();
    }
    if(!text||text===author||text.length>280)return null;
    if(/^(joined|followed|liked|shared|is now following)\b/i.test(text))return null;
    const rowMarker=(String(node.className||"")+" "+
      (node.getAttribute?.("data-e2e")||"")).toLowerCase();
    const giftTagged=/gift/.test(rowMarker)||
      Boolean(node.querySelector?.('[data-e2e*="gift"],[class*="GiftMessage"]'));
    // Gift rows often split "sent <gift>" and "x N" into separate elements;
    // use the scoped row text only for the known gift notification pattern.
    const whole=(node.innerText||node.textContent||"").trim();
    const afterAuthor=whole.startsWith(author)?whole.slice(author.length).trim():whole;
    const giftMatch=/(?:^|\s)sent\s+(.+?)\s+[x×]\s*(\d{1,5})\s*$/i.exec(
      giftTagged?afterAuthor:text
    );
    let kind="comment",gift_name="",gift_count=0;
    if(giftMatch && (giftTagged || node.querySelector?.('img[alt*="gift"],img[class*="Gift"]'))){
      gift_name=giftMatch[1].replace(/[\p{Extended_Pictographic}]/gu,"").trim().slice(0,48);
      gift_count=Number(giftMatch[2]);
      if(!gift_name||gift_count<1)return null;
      kind="gift";
      text=gift_name;
    }else if(giftTagged || /^sent\s+.+\s+[x×]\s*\d+\s*$/i.test(text)){
      // Do not pretend an unrecognized gift notification is a chat comment.
      return null;
    }
    let id=node.getAttribute("data-id")||node.getAttribute("data-message-id")||"";
    if(!/^[a-zA-Z0-9_.:\-]{1,160}$/.test(id)){
      if(!fallback.has(node))fallback.set(node,idPrefix+(++seq));
      id=fallback.get(node);
    }
    return {id,author,text,kind,...meta,
      ...(kind==="gift"?{gift_name,gift_count}:{})};
  }
  // Reloading/unpacking an extension invalidates the previous content
  // script's chrome.runtime, while its DOM observers and timers can survive
  // until the TikTok tab itself is refreshed. Stop the old reader instead of
  // repeatedly raising "Extension context invalidated".
  function isInvalidatedContext(error){
    return /extension context invalidated|context invalidated/i.test(
      String(error?.message||error||"")
    );
  }
  function send(phase,items,diagnostics){
    if(!running)return;
    try{
      // Chrome removes runtime.id from orphaned content-script contexts.
      if(!chrome.runtime?.id){stop();return;}
      chrome.runtime.sendMessage({kind:"vw-chat-batch",phase,items,diagnostics},result=>{
        if(!running)return;
        try{
          const issue=chrome.runtime.lastError;
          if(issue){
            if(isInvalidatedContext(issue))stop();
            return;
          }
          if(result?.ok===false && result.error==="not authorized tab")stop();
        }catch(error){
          // Even reading runtime.lastError may fail on the old context.
          if(isInvalidatedContext(error))stop();
          else stop(); // Unexpected runtime failure; avoid a noisy retry loop.
        }
      });
    }catch(error){
      // sendMessage throws synchronously after extension reload/update.
      // Never keep scanning with a detached runtime.
      if(isInvalidatedContext(error))stop();
      else stop();
    }
  }
  function scan(){
    if(!running)return;
    const input=document.querySelector(
      '[data-e2e="room-chat-input-field"][placeholder],'
      +'[contenteditable][placeholder],textarea[placeholder]'
    );
    const off=/^comments\s+(off|disabled)$/i.test(
      (input?.getAttribute("placeholder")||"").trim());
    const list=findList();
    const diagnostics={list_found:!!list,row_candidates:0,parsed_rows:0,
      fresh_rows:0,author_nodes:0};
    if(off){send("comments_off",[],diagnostics);return;}
    if(!list){send("waiting_chat_dom",[],diagnostics);return;}
    const collected=collectRows(list);
    diagnostics.row_candidates=Math.min(collected.rows.length,10000);
    diagnostics.author_nodes=Math.min(collected.authorNodes,10000);
    const items=[];
    for(const node of collected.rows.slice(-150)){
      const item=parseRow(node);
      if(!item)continue;
      diagnostics.parsed_rows++;
      if(known.has(item.id))continue;
      known.add(item.id);
      if(started && items.length<20)items.push(item);
    }
    diagnostics.fresh_rows=items.length;
    started=true;
    if(known.size>3500){
      const recent=[...known].slice(-1700);
      known.clear();recent.forEach(id=>known.add(id));
    }
    send("ready",items,diagnostics);
  }
  function schedule(){
    if(!running||delay!==null)return;
    delay=setTimeout(()=>{delay=null;scan();},500);
  }
  function start(){
    if(running)return;
    running=true;started=false;known.clear();
    observer=new MutationObserver(schedule);
    observer.observe(document.documentElement,{childList:true,subtree:true,
      characterData:true,attributes:false});
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
