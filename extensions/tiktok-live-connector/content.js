"use strict";
/* Explicitly user-activated, DOM-only TikTok LIVE comment reader.
   Never reads login/cookies or bypasses TikTok security/access controls.
   Diagnostics are counts only, not raw HTML or private account data. */
(()=>{
  if(globalThis.__voxweaveTikTokReaderInstalled)return;
  globalThis.__voxweaveTikTokReaderInstalled=true;
  let running=false,observer=null,heartbeat=null,scheduled=false,started=false,seq=0;
  let lastChatMutation=Date.now();
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
    // A LIVE row may use generic flex wrappers. The *nearest* username
    // parent often contains only levels/badges, not the comment. Walk up to
    // the last bounded ancestor containing this single message instead.
    const name=(nameNode.textContent||"").trim();
    let parent=nameNode.parentElement,best=null;
    for(let depth=0;parent&&depth<7&&parent!==list;parent=parent.parentElement,depth++){
      const value=(parent.textContent||"").trim();
      if(value.length>550)break;
      const names=parent.querySelectorAll?.(NAME_SELECTOR);
      if(names && [...names].filter(n=>n===nameNode||!nameNode.contains?.(n)).length>1)
        break; // Do not join several viewers into one message.
      if(value.length>name.length+1
         &&parent.querySelector?.(NAME_SELECTOR)
         &&!isSystemNotice(parent))best=parent;
    }
    return best;
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
    // Generic class selectors can accidentally capture a container with
    // several comments. Never parse multiple viewers as one event.
    const singleAuthorRows=candidates.filter(row=>{
      const nodes=[...(row.querySelectorAll?.(NAME_SELECTOR)||[])];
      // Some simple rows expose the nickname only through querySelector.
      // Real DOMs expose both; never accept a row with multiple names.
      if(!nodes.length)return Boolean(row.querySelector?.(NAME_SELECTOR));
      return nodes.filter(n=>!nodes.some(other=>other!==n&&other.contains?.(n))).length===1;
    });
    if(!singleAuthorRows.length){
      const found=new Set();
      for(const name of nameNodes){
        const row=toRow(name,list);
        if(row && !found.has(row)){found.add(row);singleAuthorRows.push(row);}
      }
      // A wrapper may contain the entire scroller. Keep only small rows,
      // and avoid repeating a parent and its child.
      return {rows:singleAuthorRows.filter(row=>!singleAuthorRows.some(other=>
        other!==row&&row.contains(other))),authorNodes,method:"author"};
    }
    return {rows:singleAuthorRows,authorNodes,method:"structured"};
  }
  function commentTail(node,nameNode,author){
    // Prefer the end of the *single message row*. In TikTok's two-line
    // layout the first line holds level, badges and display name; the
    // remaining line(s) are the user's comment, even when badge elements
    // have classes that look like a comment selector.
    const rawLines=(node.innerText||"").split(/\r?\n/)
      .map(s=>s.replace(/\s+/g," ").trim()).filter(Boolean);
    const authorLine=rawLines.findIndex(line=>line.includes(author));
    if(authorLine>=0 && authorLine<rawLines.length-1){
      const tail=rawLines.slice(authorLine+1).join(" ").trim();
      if(tail && tail.length<=280)return tail;
    }
    // One-line/inline LIVE rows: choose the LAST explicit message element,
    // and never use an element nested inside the nickname/badge header.
    const messageNodes=[...(node.querySelectorAll?.(TEXT_SELECTOR)||[])];
    if(!messageNodes.length){
      const direct=node.querySelector?.(TEXT_SELECTOR);
      if(direct)messageNodes.push(direct);
    }
    for(const element of messageNodes.reverse()){
      if(element===nameNode||nameNode.contains?.(element))continue;
      if(element.closest?.('[data-e2e*="badge"],[data-e2e*="level"],'
                           +'[data-e2e*="rank"],[class*="Badge"],'
                           +'[class*="Level"],[class*="Rank"]'))continue;
      const text=(element.textContent||"").replace(/\s+/g," ").trim();
      if(text&&text!==author&&text.length<=280)return text;
    }
    // When there is no dedicated text selector, use the final text leaf of
    // the row, not its combined textContent (which includes header badges).
    const leaves=[...(node.querySelectorAll?.("span,p,div")||[])];
    for(const element of leaves.reverse()){
      if(element===nameNode||nameNode.contains?.(element))continue;
      if(element.querySelector?.("span,p,div"))continue;
      if(/badge|level|rank|icon/i.test(String(element.className||"")))continue;
      if(element.closest?.('[data-e2e*="badge"],[data-e2e*="level"],'
                           +'[data-e2e*="rank"],[class*="Badge"],'
                           +'[class*="Level"],[class*="Rank"]'))continue;
      const text=(element.textContent||"").replace(/\s+/g," ").trim();
      if(text&&text!==author&&text.length<=280)return text;
    }
    return "";
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
    let text=commentTail(node,nameNode,author);
    if(!text||text===author||text.length>280)return null;
    if(/^(joined|followed|liked|shared|is now following)\b/i.test(text))return null;
    const rowMarker=(String(node.className||"")+" "+
      (node.getAttribute?.("data-e2e")||"")).toLowerCase();
    const giftTagged=/gift/.test(rowMarker)||
      Boolean(node.querySelector?.('[data-e2e*="gift"],[class*="GiftMessage"]'));
    // Gift rows often split "sent <gift>" and "x N" into separate elements;
    // use the scoped row text only for the known gift notification pattern.
    const whole=(node.innerText||node.textContent||"")
      .replace(/\s+/g," ").trim();
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
      // TikTok sometimes recycles the SAME DOM element for a new comment.
      // One permanent ID per element would silently drop later comments.
      // Gift counts can change within a streak; keep that event's ID stable.
      const signature=kind==="gift"
        ?kind+"|"+author+"|"+gift_name
        :kind+"|"+author+"|"+text;
      let record=fallback.get(node);
      if(!record||record.signature!==signature){
        record={id:idPrefix+(++seq),signature};
        fallback.set(node,record);
      }
      id=record.id;
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
      fresh_rows:0,author_nodes:0,
      tab_visible:document.visibilityState!=="hidden",
      tab_focused:typeof document.hasFocus==="function"
        ?Boolean(document.hasFocus()):true,
      chat_change_age_seconds:Math.min(86400,
        Math.max(0,Math.floor((Date.now()-lastChatMutation)/1000)))};
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
  function schedule(mutations){
    if(!running)return;
    // Chrome throttles setTimeout / setInterval in background tabs. DOM
    // mutation delivery is event-driven; a microtask is not gated by a
    // 500-ms background timer. It also coalesces adjacent mutations.
    if(Array.isArray(mutations) && mutations.some(m=>{
      const list=findList();
      return Boolean(list && (list===m.target||list.contains?.(m.target)));
    })) lastChatMutation=Date.now();
    if(scheduled)return;
    scheduled=true;
    const run=()=>{
      scheduled=false;
      if(running)scan();
    };
    if(typeof queueMicrotask==="function")queueMicrotask(run);
    else Promise.resolve().then(run);
  }
  function onVisibilityChange(){
    if(!running)return;
    // Catch up with any DOM updates when a background tab resumes. This
    // cannot recover comments TikTok never rendered while it was hidden.
    schedule();
  }
  function start(){
    if(running)return;
    running=true;started=false;known.clear();lastChatMutation=Date.now();
    observer=new MutationObserver(schedule);
    observer.observe(document.documentElement,{childList:true,subtree:true,
      characterData:true,attributes:false});
    document.addEventListener?.("visibilitychange",onVisibilityChange);
    globalThis.addEventListener?.("pageshow",onVisibilityChange);
    globalThis.addEventListener?.("focus",onVisibilityChange);
    // Timer is a fallback, not the primary capture mechanism.
    heartbeat=setInterval(scan,3500);
    scan();
  }
  function stop(){
    running=false;started=false;known.clear();scheduled=false;
    if(observer){observer.disconnect();observer=null;}
    document.removeEventListener?.("visibilitychange",onVisibilityChange);
    globalThis.removeEventListener?.("pageshow",onVisibilityChange);
    globalThis.removeEventListener?.("focus",onVisibilityChange);
    if(heartbeat!==null){clearInterval(heartbeat);heartbeat=null;}
  }
  chrome.runtime.onMessage.addListener(message=>{
    if(message?.kind==="vw-start"){start();return;}
    if(message?.kind==="vw-stop")stop();
  });
})();
