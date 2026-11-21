// Source queue controls persist per mode, with max 8,000 and no credentials.
const assert=require("node:assert/strict");
const fs=require("node:fs");
const vm=require("node:vm");
const html=fs.readFileSync("web/index.html","utf8");
const code=fs.readFileSync("web/source_queue_ui.js","utf8");
const modes=[
  ["live","live"],["youtube_browser","youtubeBrowser"],
  ["tiktok_browser","tiktokBrowser"],["tiktok","tiktok"],
  ["discord","discord"],["discord_client","discordClient"],
];
const tick=()=>new Promise(r=>setImmediate(r));
const root={
  modes:Object.fromEntries(modes.map(([m])=>[m,{revision:1,settings:{
    blocked_words:"",max_chars:8000,auto_read:true,
    read_history_limit:2,random_queue_enabled:true,
    random_queue_threshold:30,random_queue_keep:5,
    continue_on_tts_error:true,prepare_ahead:true,
    prepare_queue_limit:3,ready_audio_queue_limit:2,
  }}])),
};
const sent=[];
const dom=new Map();
function el(id){
  if(!dom.has(id)){
    dom.set(id,{value:"240",checked:true,type:"text",disabled:false,
      textContent:"",events:{},
      addEventListener(n,cb){this.events[n]=cb;},
      dispatchEvent(){}});
  }
  return dom.get(id);
}
const browser={
  async fetch(path,options={}){
    assert.equal(path,"/v1/settings/source-queues");
    if(options.method==="POST"){
      assert.equal(options.headers["X-VoxWeaveTTS-Intent"],"save-source-queue");
      const payload=JSON.parse(options.body);
      assert.equal(Object.keys(payload).sort().join(","),
                   "expected_revision,mode,settings");
      assert.equal(payload.settings.max_chars<=8000,true);
      assert.equal("credential" in payload.settings,false);
      sent.push(payload);
      const record=root.modes[payload.mode];
      if(payload.expected_revision!==record.revision)
        return {ok:false,status:409,async json(){return{error:"conflict"};}};
      record.revision++;
      record.settings=payload.settings;
    }
    return {ok:true,async json(){return JSON.parse(JSON.stringify(root));}};
  }
};
const sandbox={window:browser,console};
vm.runInNewContext(code,sandbox);
const controllers={};
(async()=>{
  for(const [mode,prefix] of modes){
    for(const suffix of ["MaxChars","KeepRead","Save","SaveStatus",
                          "Auto","RandomEnable","RandomThreshold",
                          "RandomKeep","Blocked","ContinueOnTtsError","PrepareAhead",
                           "PrepareQueueLimit","ReadyAudioQueueLimit"]){
      assert.ok(html.includes('id="'+prefix+"Feed"+suffix+'"'),"missing "+mode+"/"+suffix);
    }
    assert.match(html,new RegExp('id="'+prefix+'FeedMaxChars"[^>]*max="8000"'));
    el(prefix+"FeedMaxChars").value="240";
    el(prefix+"FeedKeepRead").value="20";
    el(prefix+"FeedRandomThreshold").value="20";
    el(prefix+"FeedRandomKeep").value="5";
    for(const name of ["Auto","RandomEnable","ContinueOnTtsError","PrepareAhead"])
      el(prefix+"Feed"+name).type="checkbox";
    controllers[mode]=browser.VoxSourceQueueUI.attach(mode,el);
  }
  await tick();await tick();
  for(const [mode,prefix] of modes){
    assert.equal(el(prefix+"FeedMaxChars").value,"8000","load "+mode);
    assert.equal(el(prefix+"FeedKeepRead").value,"2","load history "+mode);
    assert.equal(el(prefix+"FeedContinueOnTtsError").checked,true,"load error setting "+mode);
    assert.equal(el(prefix+"FeedPrepareAhead").checked,true,"load pipeline "+mode);
    assert.equal(el(prefix+"FeedPrepareQueueLimit").value,"3");
    assert.equal(el(prefix+"FeedReadyAudioQueueLimit").value,"2");
    el(prefix+"FeedKeepRead").value="3";
    if(mode==="youtube_browser"){
      el(prefix+"FeedPrepareQueueLimit").value="4";
      el(prefix+"FeedReadyAudioQueueLimit").value="5";
    }
    await el(prefix+"FeedSave").events.click();
  }
  assert.equal(sent.length,6);
  for(const [mode] of modes){
    assert.equal(root.modes[mode].revision,2);
    assert.equal(root.modes[mode].settings.read_history_limit,3);
    assert.equal(root.modes[mode].settings.max_chars,8000);
    assert.equal(root.modes[mode].settings.continue_on_tts_error,true);
    assert.equal(root.modes[mode].settings.prepare_ahead,true);
    assert.equal(root.modes[mode].settings.prepare_queue_limit,
      mode==="youtube_browser"?4:3);
    assert.equal(root.modes[mode].settings.ready_audio_queue_limit,
      mode==="youtube_browser"?5:2);
  }
  // Reject beyond 8,000 *before* sending a POST; no secret inputs are serialized.
  const pref="live";
  el(pref+"FeedMaxChars").value="8001";
  await el(pref+"FeedSave").events.click();
  assert.equal(sent.length,6);
  assert.match(el(pref+"FeedSaveStatus").textContent,/8,000/);
  el(pref+"FeedMaxChars").value="8000";
  el(pref+"FeedPrepareQueueLimit").value="8";
  el(pref+"FeedReadyAudioQueueLimit").value="8";
  await el(pref+"FeedSave").events.click();
  assert.equal(sent.length,6,"pipeline caps exceeding 10 must reject locally");
  assert.match(el(pref+"FeedSaveStatus").textContent,/10/);
  el(pref+"FeedPrepareQueueLimit").value="3";
  el(pref+"FeedReadyAudioQueueLimit").value="2";
  root.modes.live.revision=3; // simulated other tab save
  await el(pref+"FeedSave").events.click();
  assert.equal(sent.length,7);
  assert.match(el(pref+"FeedSaveStatus").textContent,/อีกแท็บ/);
  assert.equal(root.modes.live.revision,3);
  console.log("PASS: 6 mode queue save buttons, independent load/save, 8,000 limit, no secrets, revision conflict");
})().catch(e=>{console.error(e);process.exitCode=1;});
