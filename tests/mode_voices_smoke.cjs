// Voice preferences are independent and read live for the NEXT speech job.
const assert=require("node:assert/strict");
const {attach}=require("../web/mode_voice_settings.js");
class Node{
  constructor(tag){
    this.tagName=tag.toUpperCase();this.children=[];this.handlers={};
    this.style={};this.type="";this.value="";this.textContent="";
    this.checked=false;this.disabled=false;this.firstChild=null;
  }
  appendChild(child){
    this.children.push(child);
    if(this.tagName==="SELECT"&&this.children.length===1)this.value=child.value;
    return child;
  }
  append(...nodes){for(const n of nodes)this.appendChild(n);}
  prepend(node){this.children.unshift(node);}
  insertBefore(node){this.children.unshift(node);}
  replaceChildren(){this.children=[];if(this.tagName==="SELECT")this.value="";}
  addEventListener(event,handler){this.handlers[event]=handler;}
  get options(){return this.children;}
}
const views=new Map();
for(const mode of ["studio","reader","queue","live","youtube_browser","tiktok","tiktok_browser","discord","discord_client"])
  views.set(mode,new Node("div"));
const senderFields=new Map();
const document={
  createElement:tag=>new Node(tag),
  getElementById:id=>{
    if(!senderFields.has(id))senderFields.set(id,new Node("input"));
    return senderFields.get(id);
  },
  querySelector:selector=>{
    const match=selector.match(/^\[data-mode-view="([^"]+)"\]$/);
    return match?views.get(match[1]):null;
  },
};
let revision=0,posts=[],speechFormats={};
let presetData=[];
const voices=[
  {id:"makham-paradee-cpu",label:"MakHam",voice_id:"paradee_thai",
   voices:[{id:"paradee_thai",label:"Paradee"}],assets_ready:true,runtime_ready:true},
  {id:"vachana-cpu",label:"Vachana",voice_id:"th_f_1",
   voices:[{id:"th_f_1",label:"หญิงหนึ่ง"},{id:"th_m_2",label:"ชายสอง"}],
   assets_ready:true,runtime_ready:true},
];
const defaults={
  engine_id:"makham-paradee-cpu",voice_id:"paradee_thai",speed:1,
  voice_controls:{pitch_semitones:0,gain_db:0,bass_db:0,treble_db:0,formant_preserve:true},
};
const overrides={
  live:{...defaults,engine_id:"vachana-cpu",voice_id:"th_f_1",speed:1.1},
};
global.fetch=async(path,options)=>{
  if(path==="/v1/presets")return{ok:true,async json(){return{presets:presetData};}};
  assert.equal(path,"/v1/settings/mode-voices");
  if(!options?.method)return{ok:true,async json(){return{
    revision,policy:"serial",modes:overrides,
    sender_names:{live:true,discord_client:true},speech_formats:speechFormats,
  };}};
  assert.equal(options.headers["X-VoxWeaveTTS-Intent"],"save-mode-voice");
  const body=JSON.parse(options.body);
  assert.equal(body.expected_revision,revision);
  revision++;
  posts.push(body);
  if(body.mode==="__speech_format__")
    speechFormats[body.settings.source_mode]=body.settings.format;
  return{ok:true,async json(){return{revision};}};
};
async function main(){
  const manager=attach({document,engines:()=>voices,getDefault:()=>defaults});
  const config=await manager.load();
  assert.equal(config.policy,"serial");
  assert.equal(manager.modes.length,9);
  assert.equal(document.getElementById("liveFeedReadSender").checked,true);
  assert.equal(document.getElementById("discordFeedReadSender").checked,false);
  assert.equal(document.getElementById("tiktokFeedReadSender").checked,false);
  assert.equal(document.getElementById("discordClientFeedReadSender").checked,true);
  assert.equal(manager.read("live").engine_id,"vachana-cpu");
  assert.equal(manager.read("discord").engine_id,"makham-paradee-cpu");
  assert.equal(manager.read("live").speed,1.1);
  // User edits the live channel mid-stream; new job reads current values,
  // existing WAV isn't mutated or re-synthesized.
  const live=views.get("live");
  const all=live.children.find(node=>node.className==="mode-voice-settings").children;
  const grid=all[2];
  const engine=grid.children[0].children[1];
  const voice=grid.children[1].children[1];
  const speed=grid.children[2].children[2];
  assert.equal(engine.value,"vachana-cpu");
  voice.value="th_m_2";speed.value="1.35";
  const next=manager.read("live");
  assert.equal(next.voice_id,"th_m_2");
  assert.equal(next.speed,1.35);
  assert.equal(manager.read("discord").speed,1);
  await manager.save("live");
  assert.equal(posts[0].mode,"live");
  assert.equal(posts[0].settings.voice_id,"th_m_2");
  await manager.savePolicy("overlap");
  assert.equal(posts[1].mode,"__policy__");
  assert.equal(posts[1].settings,"overlap");
  assert.equal(revision,2);
  const discordName=document.getElementById("discordFeedReadSender");
  discordName.checked=true;
  await discordName.handlers.change();
  assert.equal(posts[2].mode,"__sender__");
  assert.equal(posts[2].settings.source_mode,"discord");
  assert.equal(posts[2].settings.enabled,true);
  await manager.saveSenderName("tiktok",false);
  assert.equal(posts[3].settings.source_mode,"tiktok");
  assert.equal(posts[3].settings.enabled,false);
  assert.equal(revision,4);
  assert.equal(document.getElementById("liveFeedReadSender").checked,true,
    "changing Discord must not affect YouTube");
  function elementById(mode,id){
    const visit=node=>{
      if(node.id===id)return node;
      for(const child of node.children){
        const found=visit(child);if(found)return found;
      }
      return null;
    };
    return visit(views.get(mode));
  }
  const liveSeparator=elementById("live","liveFeedSeparator");
  const livePrefix=elementById("live","liveFeedSenderPrefix");
  const browserPrefix=elementById("youtube_browser","youtubeBrowserFeedSenderPrefix");
  const liveReadAt=elementById("live","liveFeedFormatread_name_at");
  const browserReadAt=elementById("youtube_browser","youtubeBrowserFeedFormatread_name_at");
  assert.ok(liveSeparator&&livePrefix&&browserPrefix&&liveReadAt&&browserReadAt,
    "both YouTube modes must have independent sender-prefix and @ controls");
  assert.equal(liveReadAt.checked,false,"default skips @ only in sender name");
  assert.equal(browserReadAt.checked,false);
  liveSeparator.value="บอกว่า";
  livePrefix.value="คุณ";
  await manager.saveSpeechFormat("live");
  assert.equal(posts[4].mode,"__speech_format__");
  assert.equal(posts[4].settings.source_mode,"live");
  assert.equal(posts[4].settings.format.separator,"บอกว่า");
  assert.equal(posts[4].settings.format.sender_prefix,"คุณ");
  assert.equal(posts[4].settings.format.read_name_at,false);
  const tiktokPhrase=elementById("tiktok_browser","tiktokBrowserFeedSeparator");
  const tiktokPrefix=elementById("tiktok_browser","tiktokBrowserFeedSenderPrefix");
  const giftToggle=elementById("tiktok_browser","tiktokBrowserFeedFormatread_gifts");
  const giftPhrase=elementById("tiktok_browser","tiktokBrowserFeedGiftSeparator");
  assert.ok(tiktokPhrase&&tiktokPrefix);
  assert.equal(giftToggle,null,"gift reading is no longer a UI option");
  assert.equal(giftPhrase,null,"gift phrase is removed");
  tiktokPrefix.value="ท่าน";
  tiktokPhrase.value="พูดว่า";
  await manager.saveSpeechFormat("tiktok_browser");
  assert.equal(posts[5].settings.source_mode,"tiktok_browser");
  assert.equal(posts[5].settings.format.read_gifts,undefined);
  assert.equal(posts[5].settings.format.sender_prefix,"ท่าน");
  assert.equal(posts[5].settings.format.gift_separator,undefined);
  assert.equal(manager.readSpeechFormat("live").sender_prefix,"คุณ");
  browserReadAt.checked=true;
  await manager.saveSpeechFormat("youtube_browser");
  assert.equal(posts[6].settings.source_mode,"youtube_browser");
  assert.equal(posts[6].settings.format.read_name_at,true);
  assert.equal(manager.readSpeechFormat("live").read_name_at,false,
    "changing Browser @ does not change API @");
  assert.equal(manager.readSpeechFormat("tiktok_browser").sender_prefix,"ท่าน");
  assert.equal(manager.readSpeechFormat("tiktok").read_gifts,undefined);
  for(const mode of ["live","youtube_browser","tiktok","tiktok_browser",
                      "discord","discord_client"]){
    const prefix=mode==="youtube_browser"?"youtubeBrowser":
      mode==="discord_client"?"discordClient":
      mode==="tiktok_browser"?"tiktokBrowser":mode;
    const enabled=elementById(mode,prefix+"FeedFormatread_emojis");
    const editor=elementById(mode,prefix+"FeedEmojiMappings");
    assert.ok(enabled&&editor,"emoji editor must exist for "+mode);
    assert.equal(enabled.checked,false,"default emoji setting must not alter existing speech");
  }
  const tikFinityMapping=elementById("tiktok","tiktokFeedEmojiMappings");
  const tikExtensionMapping=elementById("tiktok_browser","tiktokBrowserFeedEmojiMappings");
  tikFinityMapping.value="😂 = ขำ TikFinity";
  elementById("tiktok","tiktokFeedFormatread_emojis").checked=true;
  await manager.saveSpeechFormat("tiktok");
  assert.equal(manager.readSpeechFormat("tiktok").read_emojis,true);
  assert.equal(manager.readSpeechFormat("tiktok").emoji_dictionary["😂"],"ขำ TikFinity");
  assert.equal(manager.readSpeechFormat("tiktok_browser").read_emojis,false,
    "TikTok Extension does not inherit TikFinity rules");
  tikExtensionMapping.value="😂 = ขำ Extension\nGGWP = เก่ง";
  elementById("tiktok_browser","tiktokBrowserFeedFormatread_emojis").checked=true;
  await manager.saveSpeechFormat("tiktok_browser");
  assert.equal(manager.readSpeechFormat("tiktok_browser").emoji_dictionary["😂"],
    "ขำ Extension");
  assert.equal(manager.readSpeechFormat("tiktok_browser").emoji_dictionary.GGWP,"เก่ง");
  assert.equal(manager.readSpeechFormat("tiktok").emoji_dictionary["😂"],"ขำ TikFinity");
  assert.equal(manager.readSpeechFormat("tiktok_browser").read_gifts,undefined,
    "Emoji reading must not re-enable removed gifts");
  const apiEmoji=elementById("live","liveFeedEmojiMappings");
  elementById("live","liveFeedFormatread_emojis").checked=true;
  apiEmoji.value="😂 = หัวเราะ\n❤️ = หัวใจ\nGGWP = เก่งมาก";
  await manager.saveSpeechFormat("live");
  assert.equal(posts.at(-1).settings.source_mode,"live");
  assert.equal(posts.at(-1).settings.format.read_emojis,true);
  assert.deepEqual(posts.at(-1).settings.format.emoji_dictionary,
    {"😂":"หัวเราะ","❤️":"หัวใจ","GGWP":"เก่งมาก"});
  assert.equal(manager.readSpeechFormat("youtube_browser").read_emojis,false,
    "YouTube Browser must not inherit API mappings");
  const discordEmoji=elementById("discord","discordFeedEmojiMappings");
  discordEmoji.value=":party_parrot: = นกเต้น";
  elementById("discord","discordFeedFormatread_emojis").checked=true;
  await manager.saveSpeechFormat("discord");
  assert.equal(manager.readSpeechFormat("discord").emoji_dictionary[":party_parrot:"],"นกเต้น");
  assert.equal(manager.readSpeechFormat("discord_client").read_emojis,false);
  await manager.load();
  assert.equal(elementById("live","liveFeedEmojiMappings").value,apiEmoji.value);
  assert.equal(elementById("discord","discordFeedEmojiMappings").value,discordEmoji.value);
  assert.equal(elementById("live","liveFeedFormatread_emojis").checked,true);
  assert.equal(elementById("discord","discordFeedFormatread_emojis").checked,true);
  assert.equal(elementById("tiktok","tiktokFeedEmojiMappings").value,
    tikFinityMapping.value);
  assert.equal(elementById("tiktok_browser","tiktokBrowserFeedEmojiMappings").value,
    tikExtensionMapping.value);
  assert.equal(elementById("tiktok","tiktokFeedFormatread_emojis").checked,true);
  assert.equal(elementById("tiktok_browser","tiktokBrowserFeedFormatread_emojis").checked,true);
  // Bad editor input is rejected without saving anything.
  const count=posts.length;
  apiEmoji.value="@ = เปลี่ยนทั้งข้อความ";
  await manager.saveSpeechFormat("live");
  assert.equal(posts.length,count,"invalid emoji mapping must not be persisted");
  apiEmoji.value="😂 = หัวเราะ\\n❤️ = หัวใจ";
  // Presets copied from a different machine stay visible even before their
  // optional model pack has been installed.
  const pendingModel="model-optional-thai-1_0_0";
  presetData=[{
    name:"Portable Voice",engine_id:pendingModel,voice_id:"speaker_f",
    speed:1.25,seed:100,voice_controls:defaults.voice_controls,
  }];
  await manager.loadPresets();
  const presetArea=all[5];
  const presetGrid=presetArea.children[2];
  const presetSelect=presetGrid.children[2].children[1];
  const applyButton=presetGrid.children[3];
  assert.equal(presetSelect.options[1].value,"Portable Voice");
  assert.match(presetSelect.options[1].textContent,/model-optional-thai/);
  presetSelect.value="Portable Voice";
  applyButton.handlers.click();
  assert.match(all[4].textContent,/Model Package/);
  assert.equal(manager.read("live").engine_id,"vachana-cpu",
    "an unavailable model cannot overwrite the current voice");
  voices.push({
    id:pendingModel,label:"Optional Thai",voice_id:"speaker_f",
    voices:[{id:"speaker_f",label:"Speaker F"}],
    assets_ready:true,runtime_ready:true,
  });
  manager.refreshEngines();
  assert.equal(presetSelect.options[1].textContent,"Portable Voice");
  presetSelect.value="Portable Voice";
  applyButton.handlers.click();
  assert.equal(manager.read("live").engine_id,pendingModel);
  assert.equal(manager.read("live").voice_id,"speaker_f");
  console.log("PASS: independent voices, portable presets with missing models, model activation and serial/overlap policy");
}
main().catch(e=>{console.error(e);process.exitCode=1;});
