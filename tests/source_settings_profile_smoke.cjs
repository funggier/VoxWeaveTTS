// Offline profile export/import: all source fields, including secrets and blanks.
const assert=require("node:assert/strict");
const fs=require("node:fs");
const vm=require("node:vm");
const code=fs.readFileSync("web/source_feed.js","utf8");
const html=fs.readFileSync("web/index.html","utf8");
const FORMAT="voxweavetts.source-settings";
const asFile=profile=>{
  const text=typeof profile==="string"?profile:JSON.stringify(profile);
  return {size:Buffer.byteLength(text,"utf8"),async text(){return text;}};
};

async function verify(mode){
  const prefix=mode==="discord_client"?"discordClient":mode;
  const elements=new Map(),pickerWrites=[],requests=[],senderImports=[];
  const browserDownloads=[],revoked=[];
  let pendingDownload=null;
  const browser={
    location:{hostname:"127.0.0.1"},
    URL:{
      createObjectURL(blob){pendingDownload=blob;return "blob:test-profile";},
      revokeObjectURL(url){revoked.push(url);},
    },
    async showSaveFilePicker(options){
      if(browser.cancelSave){
        const error=new Error("user cancelled");
        error.name="AbortError";
        throw error;
      }
      assert.ok(options.suggestedName.endsWith(".json"));
      assert.equal(options.types[0].accept["application/json"][0],".json");
      return {async createWritable(){
        return {
          async write(contents){pickerWrites.push({filename:options.suggestedName,contents});},
          async close(){},
        };
      }};
    },
  };
  for(const suffix of ["FeedExport","FeedImport","FeedImportFile"]){
    assert.ok(html.includes('id="'+prefix+suffix+'"'),suffix+" absent from "+mode);
  }
  function el(id){
    if(!elements.has(id))elements.set(id,{
      value:"",checked:false,disabled:false,textContent:"",children:[],files:[],
      events:{},clicks:0,click(){this.clicks++;},
      appendChild(item){this.children.push(item);},
      replaceChildren(){this.children=[];},
      addEventListener(event,fn){this.events[event]=fn;},
    });
    return elements.get(id);
  }
  const sandbox={
    window:browser,Number,JSON,encodeURIComponent,Blob,
    document:{body:{appendChild(){}},createElement(tag){
      if(tag==="a")return {
        click(){browserDownloads.push({filename:this.download,blob:pendingDownload});},
        remove(){},
      };
      return {textContent:"",className:"",children:[],events:{},
        append(...nodes){this.children.push(...nodes);},
        addEventListener(event,fn){this.events[event]=fn;}};
    }},
    setTimeout(callback){callback();},
    setInterval(){return 23;},
    clearInterval(){},
    async fetch(path,options){
      requests.push({path,options});
      if(path==="/v1/sources/save-profile"){
        assert.equal(options.headers["X-VoxWeaveTTS-Intent"],"choose-source-profile-file");
        assert.equal(options.method,"POST");
        const body=JSON.parse(options.body);
        assert.equal(body.profile.mode,mode);
        assert.ok(body.filename.endsWith(".json"));
        if(browser.nativeUnavailable)return {ok:false,status:503};
        return {ok:true,async json(){return {saved:!browser.cancelNative,cancelled:Boolean(browser.cancelNative)};}};
      }
      if(path==="/v1/sources/start")return {ok:true,async json(){return {mode,state:"connecting"};}};
      if(path==="/v1/sources/drain")return {ok:true,async json(){return {messages:[],status:{state:"running",next_poll_seconds:5}};}};
      if(path==="/v1/sources/stop"){
        return {ok:true,async json(){return {state:"stopped",pending:0};}};
      }
      throw Error("Unexpected network request "+path);
    },
  };
  vm.createContext(sandbox);
  vm.runInContext(code,sandbox);
  const feed=sandbox.window.VoxSourceFeed.attach({
    mode,el,guard:()=>true,onStop(){},onMessage(){},
    credentials:()=>({mode,mode_token:"a".repeat(32)}),onPick(){},
    async onSenderPreference(sourceMode,enabled){senderImports.push({sourceMode,enabled});},
  });
  const fields={
    FeedSourceId:mode==="live"?"  live-video-id ":"100000000000000001",
    FeedBlocked:"สแปม ,  ข้าม  ",
    FeedMaxChars:"245",FeedKeepRead:"17",
    FeedCredential:"FAKE_TOKEN_DO_NOT_USE",
    FeedAppId:"100000000000000005",
    FeedAppSecret:"FAKE_SECRET_DO_NOT_USE",
    FeedRedirect:"http://127.0.0.1:8765",
  };
  for(const [suffix,value] of Object.entries(fields))el(prefix+suffix).value=value;
  el(prefix+"FeedAuto").checked=false;
  el(prefix+"FeedRandomEnable").checked=true;
  el(prefix+"FeedRandomThreshold").value="20";
  el(prefix+"FeedRandomKeep").value="5";
  el(prefix+"FeedReadSender").checked=true;
  const original=await feed.exportSettings();
  assert.ok(original,"Export should support all fields");
  assert.equal(requests.length,0,"Export must not send credentials via HTTP");
  assert.equal(pickerWrites.length,1);
  assert.ok(pickerWrites[0].filename.endsWith(".json"));
  const decoded=JSON.parse(pickerWrites[0].contents);
  assert.equal(decoded.format,FORMAT);
  assert.equal(decoded.mode,mode);
  assert.equal(decoded.source_id,fields.FeedSourceId);
  assert.equal(decoded.filters.blocked_words,fields.FeedBlocked);
  assert.equal(decoded.filters.max_chars,245);
  assert.equal(decoded.auto_read,false);
  assert.equal(decoded.read_sender_name,true);
  assert.equal(decoded.read_history_limit,17);
  assert.equal(decoded.random_queue_enabled,true);
  assert.equal(decoded.random_queue_threshold,20);
  assert.equal(decoded.random_queue_keep,5);
  if(mode==="discord_client"){
    assert.equal(decoded.client_id,fields.FeedAppId);
    assert.equal(decoded.client_secret,fields.FeedAppSecret);
    assert.equal(decoded.redirect_uri,fields.FeedRedirect);
    assert.ok(!("credential" in decoded));
  }else{
    assert.equal(decoded.credential,fields.FeedCredential);
    assert.ok(!("client_secret" in decoded));
  }
  for(const key of Object.keys(fields))el(prefix+key).value="";
  el(prefix+"FeedAuto").checked=true;
  el(prefix+"FeedRandomEnable").checked=false;
  el(prefix+"FeedRandomThreshold").value="44";
  el(prefix+"FeedRandomKeep").value="12";
  el(prefix+"FeedReadSender").checked=false;
  assert.equal(await feed.importSettings(asFile(decoded)),true);
  assert.equal(el(prefix+"FeedReadSender").checked,true);
  assert.deepEqual(senderImports.at(-1),{sourceMode:mode,enabled:true});
  assert.equal(requests.length,0,"Import must never auto-connect");
  assert.equal(feed.connected,false);
  assert.equal(el(prefix+"FeedSourceId").value,fields.FeedSourceId);
  assert.equal(el(prefix+"FeedBlocked").value,fields.FeedBlocked);
  assert.equal(el(prefix+"FeedMaxChars").value,"245");
  assert.equal(el(prefix+"FeedKeepRead").value,"17");
  assert.equal(el(prefix+"FeedAuto").checked,false);
  assert.equal(el(prefix+"FeedRandomEnable").checked,true);
  assert.equal(el(prefix+"FeedRandomThreshold").value,"20");
  assert.equal(el(prefix+"FeedRandomKeep").value,"5");
  if(mode==="discord_client"){
    assert.equal(el(prefix+"FeedAppId").value,fields.FeedAppId);
    assert.equal(el(prefix+"FeedAppSecret").value,fields.FeedAppSecret);
    assert.equal(el(prefix+"FeedRedirect").value,fields.FeedRedirect);
  }else assert.equal(el(prefix+"FeedCredential").value,fields.FeedCredential);

  // Old exported source files have no sender field. They must import without
  // silently changing the current, locally saved sender setting.
  const legacy={...decoded};
  delete legacy.read_sender_name;
  delete legacy.random_queue_enabled;
  delete legacy.random_queue_threshold;
  delete legacy.random_queue_keep;
  el(prefix+"FeedReadSender").checked=false;
  const previousSenderWrites=senderImports.length;
  assert.equal(await feed.importSettings(asFile(legacy)),true);
  assert.equal(el(prefix+"FeedReadSender").checked,false);
  assert.equal(senderImports.length,previousSenderWrites);
  assert.equal(el(prefix+"FeedRandomEnable").checked,false,
    "legacy profiles must use default-off random reduction");
  assert.equal(el(prefix+"FeedRandomThreshold").value,"20");
  assert.equal(el(prefix+"FeedRandomKeep").value,"5");
  // Every editable field may be blank in an unfinished draft.
  for(const [key] of Object.entries(fields))el(prefix+key).value="";
  el(prefix+"FeedAuto").checked=true;
  const blanks=await feed.exportSettings();
  assert.ok(blanks);
  assert.equal(blanks.source_id,"");
  assert.equal(blanks.filters.blocked_words,"");
  assert.equal(blanks.filters.max_chars,"");
  assert.equal(blanks.read_history_limit,"");
  if(mode==="discord_client"){
    assert.equal(blanks.client_id,"");
    assert.equal(blanks.client_secret,"");
    assert.equal(blanks.redirect_uri,"");
  }else assert.equal(blanks.credential,"");
  for(const key of Object.keys(fields))el(prefix+key).value="UNRELATED_DRAFT";
  assert.equal(await feed.importSettings(asFile(blanks)),true);
  assert.equal(el(prefix+"FeedSourceId").value,"");
  assert.equal(el(prefix+"FeedBlocked").value,"");
  assert.equal(el(prefix+"FeedMaxChars").value,"");
  assert.equal(el(prefix+"FeedKeepRead").value,"");
  assert.equal(el(prefix+"FeedAuto").checked,true);
  if(mode==="discord_client")assert.equal(el(prefix+"FeedAppSecret").value,"");
  else assert.equal(el(prefix+"FeedCredential").value,"");

  // Reject wrong-mode files, extra fields, oversized input, invalid types
  // atomically and without spilling supplied secrets into UI errors.
  const bad=[
    {...decoded,mode:"different"},
    {...decoded,arbitrary_secret:"DO_NOT_ECHO"},
    {...decoded,filters:{blocked_words:[],max_chars:240}},
    {...decoded,auto_read:"true"},
    {...decoded,read_sender_name:"true"},
    {...decoded,random_queue_enabled:"true"},
    {...decoded,random_queue_threshold:1},
    {...decoded,random_queue_keep:20},
    {...decoded,random_queue_keep:0},
    {...decoded,random_queue_threshold:null},
    {...decoded,random_queue_keep:null},
    "{bad-json-private-DO_NOT_ECHO",
    "a".repeat(16385),
  ];
  for(const item of bad){
    el(prefix+"FeedSourceId").value="UNCHANGED";
    const prev=requests.length;
    assert.equal(await feed.importSettings(asFile(item)),false);
    assert.equal(el(prefix+"FeedSourceId").value,"UNCHANGED");
    assert.equal(requests.length,prev);
    assert.ok(!el(prefix+"FeedStatus").textContent.includes("DO_NOT_ECHO"));
  }
  // Button wiring: exporting downloads locally, importing picks a file.
  const count=pickerWrites.length;
  await el(prefix+"FeedExport").events.click();
  assert.equal(pickerWrites.length,count+1);
  el(prefix+"FeedImport").events.click();
  assert.equal(el(prefix+"FeedImportFile").clicks,1);
  el(prefix+"FeedImportFile").files=[asFile(decoded)];
  await el(prefix+"FeedImportFile").events.change();
  assert.equal(el(prefix+"FeedImportFile").value,"");
  assert.equal(el(prefix+"FeedSourceId").value,fields.FeedSourceId);
  assert.equal(requests.length,0);
  // Chrome cancellation must never write a partial file.
  browser.cancelSave=true;
  assert.equal(await feed.exportSettings(),null);
  assert.equal(pickerWrites.length,count+1);
  browser.cancelSave=false;
  // Firefox: showSaveFilePicker is unavailable. Use the Windows Save As
  // picker through the explicitly authorized same-origin local endpoint.
  delete browser.showSaveFilePicker;
  const native=await feed.exportSettings();
  assert.ok(native);
  assert.deepEqual(requests.map(x=>x.path),["/v1/sources/save-profile"]);
  browser.cancelNative=true;
  assert.equal(await feed.exportSettings(),null);
  assert.ok(el(prefix+"FeedStatus").textContent.includes("ยกเลิก"));
  browser.cancelNative=false;
  assert.equal(pickerWrites.length,count+1,
               "Firefox must not silently download to the default folder");
  assert.equal(browserDownloads.length,0);
  browser.nativeUnavailable=true;
  const saved=await feed.exportSettings();
  assert.ok(saved);
  assert.equal(browserDownloads.length,1);
  assert.deepEqual(JSON.parse(await browserDownloads[0].blob.text()),JSON.parse(JSON.stringify(saved)));
  browser.nativeUnavailable=false;
  const lastRequestCount=requests.length;
  for(const hostname of ["192.168.1.20","100.84.6.5"]){
    browser.location.hostname=hostname;
    await feed.exportSettings();
    const downloaded=browserDownloads.at(-1);
    assert.ok(downloaded.filename.endsWith(".json"));
    assert.deepEqual(JSON.parse(await downloaded.blob.text()),JSON.parse(JSON.stringify(saved)));
    assert.ok(el(prefix+"FeedStatus").textContent.includes("เบราว์เซอร์"));
  }
  assert.equal(requests.length,lastRequestCount,"LAN and Tailnet downloads stay in the browser");
  assert.equal(revoked.length,3);
  // If a user imports while connected, the previous feed is disconnected
  // before replacing its credential fields, without reconnecting the feed.
  await feed.start();
  assert.equal(feed.connected,true);
  assert.deepEqual(requests.map(item=>item.path).filter(x=>x!=="/v1/sources/save-profile"),[
    "/v1/sources/start","/v1/sources/drain",
  ]);
  assert.equal(await feed.importSettings(asFile(decoded)),true);
  assert.equal(feed.connected,false);
  assert.deepEqual(requests.map(item=>item.path).filter(x=>x!=="/v1/sources/save-profile"),[
    "/v1/sources/start","/v1/sources/drain","/v1/sources/stop",
  ]);
  if(mode==="discord_client")assert.equal(el(prefix+"FeedAppSecret").value,fields.FeedAppSecret);
  else assert.equal(el(prefix+"FeedCredential").value,fields.FeedCredential);
  console.log("PASS:",mode,"Chrome and Firefox Save As, cancellation, secrets/blanks and import isolation");
}
(async()=>{
  for(const mode of ["live","discord","discord_client"])await verify(mode);
})().catch(error=>{console.error(error);process.exitCode=1;});
