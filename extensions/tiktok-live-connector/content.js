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
    '[class*="DivChatMessage"]:not([class*="DivChatMessageList"])',
    '[class*="ChatMessageItem"]',
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
    // Only chat comments belong in the TTS feed. Exclude notices,
    // gifts, follow/join/share/like events and all system rows.
    if(/gift|follow|join|system|notice|pinned|moderator/.test(marker))return true;
    const line=(node.innerText||node.textContent||"").replace(/\s+/g," ");
    if(/\b(liked|shared|joined|followed) the live\b/i.test(line))return true;
    return Boolean(node.querySelector?.('[data-e2e*="gift"],[data-e2e*="follow"],'
      +'[data-e2e*="join"],[class*="GiftMessage"],[class*="SystemMessage"]'));
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
  function commentTail(node,nameNode,author,meta){
    // A LIVE header can wrap the nickname + "No. 2" on different DOM lines.
    // Never assume every line AFTER the nickname is part of the comment.
    // Prefer a dedicated message node or the final non-badge leaf, and use
    // innerText only as a last-resort fallback.
    const messageNodes=[...(node.querySelectorAll?.(TEXT_SELECTOR)||[])];
    if(!messageNodes.length){
      const direct=node.querySelector?.(TEXT_SELECTOR);
      if(direct)messageNodes.push(direct);
    }
    const isHeaderOrBadge=element=>
      element===nameNode||nameNode.contains?.(element)
      ||element.contains?.(nameNode)
      ||element.closest?.('[data-e2e*="badge"],[data-e2e*="level"],'
                          +'[data-e2e*="rank"],[class*="Badge"],'
                          +'[class*="Level"],[class*="Rank"]');
    for(const element of messageNodes.reverse()){
      if(isHeaderOrBadge(element))continue;
      const text=(element.textContent||"").replace(/\s+/g," ").trim();
      if(text&&text!==author&&text.length<=280)return text;
    }
    const leaves=[...(node.querySelectorAll?.("span,p,div")||[])];
    for(const element of leaves.reverse()){
      if(isHeaderOrBadge(element))continue;
      if(element.querySelector?.("span,p,div"))continue;
      if(/badge|level|rank|icon/i.test(String(element.className||"")))continue;
      const text=(element.textContent||"").replace(/\s+/g," ").trim();
      if(text&&text!==author&&text.length<=280)return text;
    }

    // Last resort: TikTok can render rank badges between the nickname line
    // and the comment line even though they appear on one visual header.
    const lines=(node.innerText||"").split(/\r?\n/)
      .map(s=>s.replace(/\s+/g," ").trim()).filter(Boolean);
    const authorLine=lines.findIndex(line=>line.includes(author));
    if(authorLine<0||authorLine===lines.length-1)return "";
    const parts=lines.slice(authorLine+1);
    const rankNumber=meta?.rank||"";
    const leadingRank=/^(?:No\.?\s*|อันดับ\s*)(\d{1,4})(?:\s+|$)/i;
    // A whole, stand-alone rank line between the header and the comment
    // is a badge, not speech. Require at least one subsequent line.
    while(parts.length>1 && leadingRank.test(parts[0])){
      const match=parts[0].match(leadingRank);
      if(!match || parts[0].trim()!==match[0].trim())break;
      parts.shift();
    }
    // An inline "No. 2 comment" is ambiguous without DOM metadata.
    // Strip it ONLY if the separately detected rank badge equals No. 2.
    if(rankNumber && parts.length){
      const match=parts[0].match(leadingRank);
      if(match && match[1]===String(rankNumber)
         && parts[0].length>match[0].length)
        parts[0]=parts[0].slice(match[0].length).trim();
    }
    const tail=parts.join(" ").trim();
    return tail.length<=280?tail:"";
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
    const text=commentTail(node,nameNode,author,meta);
    if(!text||text===author||text.length>280)return null;
    if(/^(joined|followed|liked|shared|is now following)\b/i.test(text))return null;
    // A bare gift-like notification is not a viewer comment. A genuine
    // message can still contain the same words in a dedicated chat node.
    if(/^sent\s+.+\s+[×x]\s*\d+\s*$/i.test(text)
       && !node.querySelector?.(TEXT_SELECTOR))return null;
    let id=node.getAttribute("data-id")||node.getAttribute("data-message-id")||"";
    if(!/^[a-zA-Z0-9_.:\-]{1,160}$/.test(id)){
      // TikTok sometimes recycles the SAME DOM element for a new comment.
      // One permanent ID per element would silently drop later comments.
      const signature=author+"|"+text;
      let record=fallback.get(node);
      if(!record||record.signature!==signature){
        record={id:idPrefix+(++seq),signature};
        fallback.set(node,record);
      }
      id=record.id;
    }
    return {id,author,text,kind:"comment",...meta};
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
