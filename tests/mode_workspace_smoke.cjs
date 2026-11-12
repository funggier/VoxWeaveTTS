// Concurrent workspaces: navigation does not stop sources or revoke their
// mode-specific credentials. A different tab may reclaim one mode only.
const assert=require("node:assert/strict");
const fs=require("node:fs");
const vm=require("node:vm");
const source=fs.readFileSync("web/mode_workspace.js","utf8");
const html=fs.readFileSync("web/index.html","utf8");
const names=["studio","reader","live","tiktok","discord","discord_client","queue","rules","settings"];
const views=names.map(mode=>({
  attrs:{"data-mode-view":mode},hidden:false,
  getAttribute(name){return this.attrs[name];},
}));
const buttons=names.map(mode=>({
  attrs:{"data-mode-target":mode},handlers:{},
  getAttribute(name){return this.attrs[name];},
  setAttribute(name,value){this.attrs[name]=value;},
  addEventListener(name,fn){this.handlers[name]=fn;},
}));
const nodes=new Map();
function get(id){
  if(!nodes.has(id))nodes.set(id,{
    textContent:"",handlers:{},
    addEventListener(name,fn){this.handlers[name]=fn;},
  });
  return nodes.get(id);
}
const document={
  getElementById:get,
  querySelectorAll(query){
    if(query==="[data-mode-view]")return views;
    if(query==="[data-mode-target]")return buttons;
    if(query==="audio")return[];
    throw Error("unexpected selector "+query);
  },
  addEventListener(){},
};
let revision=0,active="studio",stopped=0,activations=[],revoked=[];
const modeRevisions={};
let channel,timer;
class Channel{
  constructor(name){assert.match(name,/workspace/);channel=this;this.handlers={};}
  addEventListener(key,fn){this.handlers[key]=fn;}
  postMessage(){}
  receive(payload){this.handlers.message({data:payload});}
  close(){}
}
const sandbox={
  window:{
    BroadcastChannel:Channel,
    setInterval(fn,ms){assert.equal(ms,1200);timer=fn;return 2;},
    clearInterval(){},
  },
  document,Promise,JSON,Number,
  async fetch(path,options){
    if(path==="/v1/modes/state")return{
      ok:true,async json(){return {revision,mode_revisions:modeRevisions,active_mode:active};},
    };
    assert.equal(path,"/v1/modes/activate");
    assert.equal(options.headers["X-VoxWeaveTTS-Intent"],"activate-mode");
    const mode=JSON.parse(options.body).mode;
    activations.push(mode);
    revision++;active=mode;modeRevisions[mode]=revision;
    return {ok:true,async json(){return{
      revision,active_mode:mode,
      mode_revisions:{...modeRevisions},
      mode_token:String(revision).padStart(32,"0"),
    };}};
  },
};
vm.createContext(sandbox);
vm.runInContext(source,sandbox);
async function test(){
  assert.match(html,/data-mode-target="live"[^>]*>YouTube LIVE/);
  assert.match(html,/<h2>YouTube LIVE<\/h2>/);
  const modes=sandbox.window.VoxWorkspaceModes.MODES;
  assert.equal(modes.length,9);
  const app=sandbox.window.VoxWorkspaceModes.attach({
    document,stopLocal(){stopped++;},onLostMode(mode){revoked.push(mode);},
  });
  app.startMonitor();
  await new Promise(resolve=>setImmediate(resolve));
  const first=app.credentials("studio");
  await app.select("live");
  const youTube=app.credentials("live");
  await app.select("discord");
  const discord=app.credentials("discord");
  assert.ok(app.guard("live"),"background live must stay authorized");
  assert.ok(app.guard("studio"),"manual speech must stay authorized");
  assert.equal(app.credentials("live").mode_token,youTube.mode_token);
  assert.equal(stopped,0,"tabs never stop other workspaces");
  await app.select("live");
  assert.equal(activations.filter(x=>x==="live").length,1,
               "returning to live must not disconnect/reconnect the provider");
  assert.equal(app.credentials("studio").mode_token,first.mode_token);
  const fresh=await app.reclaim("live");
  assert.equal(activations.filter(x=>x==="live").length,2,
               "explicit Connect must renew even when local owner exists");
  assert.notEqual(fresh.mode_token,youTube.mode_token);
  assert.equal(app.credentials("discord").mode_token,discord.mode_token,
               "reclaiming YouTube must not change Discord owner");
  await app.select("tiktok");
  assert.ok(app.guard("discord"));
  assert.ok(app.guard("tiktok"));

  // A second tab reclaims Discord; YouTube and TikTok continue.
  revision++;modeRevisions.discord=revision;active="discord";
  channel.receive({revision,mode_revisions:{...modeRevisions}});
  assert.ok(!app.guard("discord"));
  assert.deepEqual(revoked,["discord"]);
  assert.ok(app.guard("live"));
  assert.ok(app.guard("tiktok"));
  await app.select("discord");
  assert.ok(app.guard("discord"));
  // Polling catches a takeover that missed BroadcastChannel.
  revision++;modeRevisions.live=revision;active="live";
  await timer();
  assert.ok(!app.guard("live"));
  assert.ok(app.guard("discord"));
  assert.deepEqual(revoked,["discord","live"]);
  app.dispose();
  assert.equal(stopped,1);
  console.log("PASS: YouTube LIVE naming, concurrent source tokens, no switch-stop, mode-local takeover");
}
test().catch(error=>{console.error(error);process.exitCode=1;});
