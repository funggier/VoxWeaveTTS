// Engine-neutral Live/Discord simulator: independent sources and player state.
const assert=require("node:assert/strict");
const fs=require("node:fs");
const vm=require("node:vm");
async function main(){
  const code=fs.readFileSync("web/mode_inputs.js","utf8");
  const elements=new Map();
  const get=id=>{
    if(!elements.has(id)){
      elements.set(id,{
        value:"",textContent:"",disabled:false,
        type:id.includes("FeedFormat")?"checkbox":(/Feed(?:SenderPrefix|GiftSeparator|Separator)$/.test(id)?"text":""),
        style:{display:"none"},src:"",paused:true,events:{},
        addEventListener(name,fn){this.events[name]=fn},
        pause(){this.paused=true},async play(){this.paused=false},removeAttribute(name){if(name==="src")this.src=""},
        load(){},
      });
    }
    return elements.get(id);
  };
  const reports=[],payloads=[],created=[],clockCalls=[],cancelled=[];
  let current="live", renderCount=0;
  const voiceByMode={live:"youtube-voice-model",discord:"discord-voice-v1",tiktok:"tiktok-voice"};
  const blobUrl=new Set();
  const sandbox={
    window:{},JSON,URL:{
      createObjectURL(blob){assert.ok(blob instanceof Blob);const u="blob:"+blobUrl.size;blobUrl.add(u);return u;},
      revokeObjectURL(url){blobUrl.delete(url);},
    },Blob,Promise,Number,
    setTimeout(fn){queueMicrotask(fn);return 1;},
    async fetch(path,opts={}){
      if(path==="/v1/jobs"&&opts.method==="POST"){
        const body=JSON.parse(opts.body);
        payloads.push(body);
        const id=String(payloads.length).repeat(32);
        created.push(id);
        return{ok:true,async json(){return{speech_id:id,state:"queued"};}};
      }
      if(path.endsWith("/cancel")){
        cancelled.push(path);
        return{ok:true,async json(){return{state:"cancelled"};}};
      }
      if(path.endsWith("/audio"))
        return{ok:true,async blob(){return new Blob(["RIFF-test"]);}};
      if(path.startsWith("/v1/jobs/"))
        return{ok:true,async json(){return{
          speech_id:path.split("/").at(-1),state:"ready",audio:{
            duration_ms:1000,segments:[{kind:"speech",display_text:"ทดสอบ",
            start_ms:0,end_ms:1000}]},
        };}};
      throw Error("Unexpected URL "+path);
    },
  };
  const library={
    attach(audio,report,onState){
      clockCalls.push(audio);
      return{
        setSpeech(id,audioInfo){
          renderCount++;
          assert.ok(audioInfo.duration_ms);
          onState({text:"ทดสอบ"});
        },
        clear(){onState({text:""});},
      };
    },
  };
  vm.createContext(sandbox);
  vm.runInContext(fs.readFileSync("web/emoji_pronunciation.js","utf8"),sandbox);
  vm.runInContext(code,sandbox);
  const attach=mode=>sandbox.window.VoxModeInputs.attach({
    mode,el:get,clockLibrary:library,
    report:(payload,m)=>reports.push({payload,mode:m}),
    getSpeechPayload:(text,selectedMode)=>({text,engine_id:voiceByMode[selectedMode]}),
    guard:mode=>mode===current,
  });
  const live=attach("live");
  const discord=attach("discord");
  get("liveText").value="ข้อความจากไลฟ์";
  get("discordText").value="ข้อความจาก Discord";
  await live.submit();
  assert.equal(payloads[0].text,"ข้อความจากไลฟ์");
  assert.equal(payloads[0].source,"youtube-live");
  assert.equal(payloads[0].engine_id,"youtube-voice-model");
  assert.equal(get("liveAudio").style.display,"block");
  assert.equal(get("liveSubtitle").textContent,"ทดสอบ");
  await get("livePlay").events.click();
  assert.equal(get("liveAudio").paused,false,"explicit play button should start audio");
  const first=live.jobId;
  current="discord";
  live.suspend();
  assert.equal(get("liveAudio").paused,true);
  assert.equal(get("liveSubtitle").textContent,"");
  assert.equal(get("liveText").value,"ข้อความจากไลฟ์",
    "mode switch preserves its own editable text");
  live.resume();
  assert.equal(renderCount,2,"a ready WAV can be restored on return");
  await discord.submit();
  assert.equal(payloads[1].text,"ข้อความจาก Discord");
  assert.equal(payloads[1].source,"discord");
  assert.equal(discord.jobId,created[1]);
  assert.notEqual(live.jobId,discord.jobId);
  assert.equal(get("liveText").value,"ข้อความจากไลฟ์");
  assert.equal(get("discordText").value,"ข้อความจาก Discord");
  // Official feed auto-read is opt-in and serial, never interrupts a WAV.
  get("discordFeedAuto").checked=true;
  get("discordAudio").paused=true;
  discord.receiveIncoming({message_id:"m1",text:"ข้อความใหม่หนึ่ง"},true);
  discord.receiveIncoming({message_id:"m2",text:"ข้อความใหม่สอง"},true);
  await new Promise(resolve=>setImmediate(resolve));
  assert.equal(payloads[2].text,"ข้อความใหม่หนึ่ง");
  assert.equal(payloads[2].source_message_id,"discord-m1");
  assert.equal(payloads[2].engine_id,"discord-voice-v1");
  assert.equal(payloads.length,3,"only one auto job starts before playback ends");
  voiceByMode.discord="discord-voice-v2"; // updated while m2 is still queued
  get("discordAudio").paused=true;
  get("discordAudio").events.ended();
  await new Promise(resolve=>setImmediate(resolve));
  assert.equal(payloads[3].engine_id,"discord-voice-v2");
  assert.equal(payloads[3].text,"ข้อความใหม่สอง");
  get("discordAudio").paused=true;
  get("discordAudio").events.ended();
  discord.receiveIncoming({message_id:"m3",text:"ห้ามอ่านต่อ"},false);
  await new Promise(resolve=>setImmediate(resolve));
  assert.equal(payloads.length,4,"unchecked auto-read must never queue speech");
  discord.clearAutoQueue();
  discord.stop({discard:true});
  assert.equal(get("discordAudio").style.display,"none");
  assert.equal(discord.jobId,null);
  assert.equal(get("discordText").value,"ข้อความใหม่สอง");
  assert.ok(blobUrl.size<=1);
  // TikTok uses the same serial audio queue but is a distinct playback
  // owner and source, not a Discord/YouTube voice type.
  current="tiktok";
  const tiktok=attach("tiktok");
  get("tiktokFeedAuto").checked=true;
  const firstTik=tiktok.receiveIncoming({message_id:"tt1",text:"ข้อความ TikTok หนึ่ง"},true);
  const secondTik=tiktok.receiveIncoming({message_id:"tt2",text:"ข้อความ TikTok สอง"},true);
  assert.equal(firstTik,"queued");
  assert.equal(secondTik,"queued");
  await new Promise(resolve=>setImmediate(resolve));
  assert.equal(payloads.at(-1).source,"tiktok-live");
  assert.equal(payloads.at(-1).text,"ข้อความ TikTok หนึ่ง");
  assert.equal(payloads.at(-1).source_message_id,"tiktok-tt1");
  assert.equal(tiktok.pendingAuto,1);
  get("tiktokAudio").paused=true;
  get("tiktokAudio").events.ended();
  await new Promise(resolve=>setImmediate(resolve));
  assert.equal(payloads.at(-1).text,"ข้อความ TikTok สอง");
  assert.equal(tiktok.pendingAuto,0);
  tiktok.suspend();
  assert.equal(get("tiktokAudio").paused,true);
  // Playback failures and Stop MUST NOT silently change the user's stored
  // preference. They pause the automatic reader until explicit retry.
  current="discord";
  get("discordFeedAuto").checked=true;
  assert.equal(discord.receiveIncoming({message_id:"err1",text:"Error candidate"},true),"queued");
  await new Promise(resolve=>setImmediate(resolve));
  get("discordAudio").events.error();
  assert.equal(discord.autoPaused,true);
  assert.equal(get("discordFeedAuto").checked,true,
    "audio error must not mutate auto-read checkbox");
  assert.equal(discord.receiveIncoming({message_id:"err2",text:"While paused"},true),"manual");
  get("discordAutoRetry").events.click();
  assert.equal(discord.autoPaused,false);
  assert.equal(get("discordFeedAuto").checked,true);
  assert.equal(discord.receiveIncoming({message_id:"err3",text:"After retry"},true),"queued");
  await new Promise(resolve=>setImmediate(resolve));
  get("discordStop").events.click();
  assert.equal(discord.autoPaused,true);
  assert.equal(get("discordFeedAuto").checked,true,
    "Stop pauses source speech but preserves automatic reader preference");
  // TikTok Extension is an independent voice/source, not an alias of TikFinity.
  current="tiktok_browser";
  voiceByMode.tiktok_browser="tiktok-browser-voice";
  const browser=attach("tiktok_browser");
  get("tiktokBrowserFeedAuto").checked=true;
  assert.equal(browser.receiveIncoming({message_id:"dom1",text:"ข้อความจาก TikTok Browser"},true),"queued");
  await new Promise(resolve=>setImmediate(resolve));
  assert.equal(payloads.at(-1).source,"tiktok-live-extension");
  assert.equal(payloads.at(-1).source_message_id,"tiktok_browser-dom1");
  assert.equal(payloads.at(-1).engine_id,"tiktok-browser-voice");
  assert.equal(payloads.at(-1).text,"ข้อความจาก TikTok Browser");
  // Simplified mode-local speech preferences: sender prefix and name,
  // comments and gifts. Level/rank/badge metadata is never spoken.
  get("tiktokBrowserAudio").paused=true;
  get("tiktokBrowserAudio").events.ended();
  get("tiktokBrowserFeedReadSender").checked=true;
  get("tiktokBrowserFeedSenderPrefix").value="ท่าน";
  get("tiktokBrowserFeedSeparator").value="กล่าวข้อความว่า";
  get("tiktokBrowserFeedFormatread_comments").checked=true;
  const comment={message_id:"dom2",kind:"comment",author:"🥒Sprite Pam🥒",
    level:"25",rank:"3",badges:["InvT"],text:"สวัสดีครับ"};
  assert.equal(browser.receiveIncoming(comment,true),"queued");
  await new Promise(resolve=>setImmediate(resolve));
  assert.equal(payloads.at(-1).text,"ท่าน 🥒Sprite Pam🥒 กล่าวข้อความว่า สวัสดีครับ");
  get("tiktokBrowserAudio").paused=true;
  get("tiktokBrowserAudio").events.ended();
  // No gift events should enter the speech queue, including from an older
  // Extension that has not yet been reloaded.
  const gift={message_id:"gift1",kind:"gift",author:"Sprite Pam",
    text:"Heart Me",gift_name:"Heart Me",gift_count:2};
  const beforeGift=payloads.length;
  assert.equal(browser.receiveIncoming(gift,true),"skipped");
  assert.equal(payloads.length,beforeGift,"gift events are never spoken");
  get("tiktokBrowserAudio").paused=true;
  get("tiktokBrowserAudio").events.ended();
  // User may disable sender name without removing the custom prefix value.
  get("tiktokBrowserFeedReadSender").checked=false;
  assert.equal(browser.receiveIncoming({...comment,message_id:"dom-no-name"},true),"queued");
  await new Promise(resolve=>setImmediate(resolve));
  assert.equal(payloads.at(-1).text,"สวัสดีครับ");
  get("tiktokBrowserAudio").paused=true;
  get("tiktokBrowserAudio").events.ended();
  get("tiktokBrowserFeedFormatread_comments").checked=false;
  assert.equal(browser.receiveIncoming({...comment,message_id:"dom3"},true),"manual");
  browser.suspend();
  // YouTube API and YouTube Browser must use a speaker-specific prefix,
  // not a global @ replacement that would corrupt viewer comments.
  current="live";
  get("liveFeedAuto").checked=true;
  get("liveFeedReadSender").checked=true;
  get("liveFeedSenderPrefix").value="คุณ";
  get("liveFeedSeparator").value="บอกว่า";
  get("liveAudio").paused=true;
  assert.equal(live.receiveIncoming({
    message_id:"yt-phrase",author:"@ผู้ชม",text:"สวัสดี @เพื่อน"
  },true),"queued");
  await new Promise(resolve=>setImmediate(resolve));
  assert.equal(payloads.at(-1).text,"คุณ ผู้ชม บอกว่า สวัสดี @เพื่อน");
  get("liveAudio").paused=true;
  get("liveAudio").events.ended();
  get("liveFeedFormatread_name_at").checked=true;
  assert.equal(live.receiveIncoming({
    message_id:"yt-at-on",author:"@ผู้ชม",text:"ทัก @เพื่อน"
  },true),"queued");
  await new Promise(resolve=>setImmediate(resolve));
  assert.equal(payloads.at(-1).text,"คุณ @ผู้ชม บอกว่า ทัก @เพื่อน",
    "enabled sender @ must not mutate @ in the chat body");
  get("liveAudio").paused=true;
  get("liveAudio").events.ended();
  // The Browser variant has its own sender-@ preference.
  current="youtube_browser";
  voiceByMode.youtube_browser="youtube-browser-voice";
  const youtubeBrowser=attach("youtube_browser");
  get("youtubeBrowserFeedAuto").checked=true;
  get("youtubeBrowserFeedReadSender").checked=true;
  get("youtubeBrowserFeedSenderPrefix").value="ท่าน";
  get("youtubeBrowserFeedSeparator").value="พิมพ์ว่า";
  get("youtubeBrowserFeedFormatread_name_at").checked=false;
  assert.equal(youtubeBrowser.receiveIncoming({
    message_id:"yb-at-off",author:"@เพื่อน",text:"ตอบ @ผม ได้เลย"
  },true),"queued");
  await new Promise(resolve=>setImmediate(resolve));
  assert.equal(payloads.at(-1).text,"ท่าน เพื่อน พิมพ์ว่า ตอบ @ผม ได้เลย");
  get("youtubeBrowserAudio").paused=true;
  get("youtubeBrowserAudio").events.ended();
  get("youtubeBrowserFeedFormatread_name_at").checked=true;
  assert.equal(youtubeBrowser.receiveIncoming({
    message_id:"yb-at-on",author:"@เพื่อน",text:"ตอบ @ผม ได้เลย"
  },true),"queued");
  await new Promise(resolve=>setImmediate(resolve));
  assert.equal(payloads.at(-1).text,"ท่าน @เพื่อน พิมพ์ว่า ตอบ @ผม ได้เลย");
  get("youtubeBrowserAudio").paused=true;
  get("youtubeBrowserAudio").events.ended();
  get("youtubeBrowserFeedFormatread_emojis").checked=true;
  get("youtubeBrowserFeedEmojiMappings").value="😂 = หัวเราะ\n❤️ = หัวใจ";
  assert.equal(youtubeBrowser.receiveIncoming({
    message_id:"yb-emoji",author:"@เพื่อน❤️",text:"สวัสดี 😂❤️ @ทุกคน 🥳"
  },true),"queued");
  await new Promise(resolve=>setImmediate(resolve));
  assert.equal(payloads.at(-1).text,
    "ท่าน @เพื่อน หัวใจ พิมพ์ว่า สวัสดี หัวเราะ หัวใจ @ทุกคน 🥳");
  assert.equal(get("youtubeBrowserText").value,"สวัสดี 😂❤️ @ทุกคน 🥳",
    "original source comment remains untouched in editable input");
  get("youtubeBrowserAudio").paused=true;
  get("youtubeBrowserAudio").events.ended();
  get("youtubeBrowserFeedFormatread_emojis").checked=false;
  assert.equal(youtubeBrowser.receiveIncoming({
    message_id:"yb-emoji-off",author:"@เพื่อน❤️",text:"สวัสดี 😂❤️"
  },true),"queued");
  await new Promise(resolve=>setImmediate(resolve));
  assert.equal(payloads.at(-1).text,"ท่าน @เพื่อน❤️ พิมพ์ว่า สวัสดี 😂❤️");

  current="discord";
  get("discordAutoRetry").events.click();
  get("discordAudio").paused=true;
  get("discordAudio").events.ended();
  get("discordFeedAuto").checked=true;
  get("discordFeedReadSender").checked=true;
  get("discordFeedSenderPrefix").value="คุณ";
  get("discordFeedSeparator").value="พิมพ์ว่า";
  get("discordFeedFormatread_emojis").checked=true;
  get("discordFeedEmojiMappings").value=":party_parrot: = นกเต้น\n👍🏽 = เยี่ยมมาก";
  assert.equal(discord.receiveIncoming({
    message_id:"discord-emoji",author:"ผู้ชม",text:"เยี่ยม 👍🏽 <a:party_parrot:123456789012345678>"
  },true),"queued");
  await new Promise(resolve=>setImmediate(resolve));
  assert.equal(payloads.at(-1).text,"คุณ ผู้ชม พิมพ์ว่า เยี่ยม เยี่ยมมาก นกเต้น");
  assert.equal(get("discordText").value,"เยี่ยม 👍🏽 <a:party_parrot:123456789012345678>");
  get("discordAudio").paused=true;get("discordAudio").events.ended();

  current="discord_client";
  voiceByMode.discord_client="discord-client-voice";
  const discordClient=attach("discord_client");
  get("discordClientFeedAuto").checked=true;
  get("discordClientFeedReadSender").checked=true;
  get("discordClientFeedSenderPrefix").value="คุณ";
  get("discordClientFeedSeparator").value="พิมพ์ว่า";
  get("discordClientFeedEmojiMappings").value="😂 = ขำ";
  get("discordClientFeedFormatread_emojis").checked=true;
  assert.equal(discordClient.receiveIncoming({
    message_id:"client-emoji",author:"เพื่อน",text:"😂 👍🏽"
  },true),"queued");
  await new Promise(resolve=>setImmediate(resolve));
  assert.equal(payloads.at(-1).text,"คุณ เพื่อน พิมพ์ว่า ขำ 👍🏽",
    "Discord Client emoji rules are independent of Discord Bot");
  console.log("PASS: YouTube/Discord emoji speech mapping and sender-only @, original chat preserved");
}
main().catch(error=>{console.error(error);process.exitCode=1;});