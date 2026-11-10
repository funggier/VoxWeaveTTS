// No-browser dependency regression: single mode owns playback and OBS.
const assert=require("node:assert/strict");
const fs=require("node:fs");
const vm=require("node:vm");

async function test(){
  const source=fs.readFileSync("web/mode_workspace.js","utf8");
  const html=fs.readFileSync("web/index.html","utf8");
  const modes=["studio","reader","live","discord","queue","rules","settings"];
  for(const name of modes){
    assert.match(html,new RegExp('data-mode-view="'+name+'"'));
    assert.match(html,new RegExp('data-mode-target="'+name+'"'));
  }
  for(const id of ["message","readerChunkPreview","liveText","discordText","queueText","rulesTestText"])
    assert.match(html,new RegExp('id="'+id+'"'));
  assert.equal((html.match(/id="engineSelect"/g)||[]).length,1);
  assert.equal((html.match(/id="voiceSelect"/g)||[]).length,1);
  assert.equal((html.match(/id="rule"/g)||[]).length,1);
  assert.equal((html.match(/id="pron"/g)||[]).length,1);
  const views=modes.map(mode=>({
    attrs:{"data-mode-view":mode},hidden:false,
    getAttribute(id){return this.attrs[id]},
  }));
  const buttons=modes.map(mode=>({
    attrs:{"data-mode-target":mode},events:{},
    getAttribute(id){return this.attrs[id]},
    setAttribute(id,value){this.attrs[id]=value},
    addEventListener(event,fn){this.events[event]=fn},
  }));
  const nodes=new Map();
  const get=id=>{
    if(!nodes.has(id))nodes.set(id,{
      textContent:"",events:{},
      addEventListener(name,fn){this.events[name]=fn},
    });
    return nodes.get(id);
  };
  const handlers={};
  const document={
    getElementById:get,
    querySelectorAll(query){
      if(query==="[data-mode-view]")return views;
      if(query==="[data-mode-target]")return buttons;
      if(query==="audio")return[];
      throw Error("invalid selector "+query);
    },
    addEventListener(event,fn){handlers[event]=fn;},
  };
  let epoch=0, active="studio", resets=0;
  const pushed=[];
  class Channel {
    constructor(name){assert.match(name,/workspace/);this.handlers={};}
    addEventListener(name,fn){this.handlers[name]=fn;}
    postMessage(msg){pushed.push({...msg});}
    receive(msg){this.handlers.message({data:msg});}
    close(){}
  }
  let channel, timer;
  const sandbox={
    window:{
      BroadcastChannel:class extends Channel{
        constructor(name){super(name);channel=this;}
      },
      setInterval(fn,ms){assert.equal(ms,1200);timer=fn;return 1;},
      clearInterval(){},
    },
    document,Promise,Number,JSON,
    async fetch(path,options){
      if(path==="/v1/modes/state")return{
        ok:true,async json(){return {revision:epoch,active_mode:active};},
      };
      assert.equal(path,"/v1/modes/activate");
      assert.equal(options.headers["X-VoxWeaveTTS-Intent"],"activate-mode");
      const mode=JSON.parse(options.body).mode;
      epoch++;
      active=mode;
      return{ok:true,async json(){return{
        active_mode:mode,revision:epoch,mode_token:String(epoch).repeat(32),
      };}};
    }
  };
  vm.createContext(sandbox);
  vm.runInContext(source,sandbox);
  const app=sandbox.window.VoxWorkspaceModes.attach({
    document,stopLocal(){resets++},
    onError(e){throw Error(e)},
  });
  app.startMonitor();
  // Initial activation is queued in a microtask.
  await new Promise(resolve=>setImmediate(resolve));
  assert.equal(app.activeMode,"studio");
  assert.equal(app.owned,true);
  assert.equal(app.revision,1);
  assert.ok(app.guard("studio"));
  assert.equal(app.credentials("studio").mode,"studio");
  assert.throws(()=>app.credentials("reader"),/inactive/);
  assert.ok(views[0].hidden===false);
  assert.ok(views[1].hidden===true);
  const prior=resets;
  const change=app.select("reader");
  // Stop is synchronous, before POST to the server.
  assert.ok(resets>prior);
  assert.equal(app.owned,false);
  assert.equal(views[0].hidden,true);
  assert.equal(views[1].hidden,false);
  await change;
  assert.equal(app.owned,true);
  assert.equal(active,"reader");
  assert.equal(app.revision,2);
  assert.ok(pushed.length>=2);
  // Another browser tab takes ownership of the same overlay.
  epoch=3;active="discord";
  channel.receive({revision:epoch,active_mode:"discord"});
  assert.equal(app.owned,false);
  assert.equal(resets,prior+2);
  assert.match(get("modeOwnerStatus").textContent,/อีกแท็บ/);
  await app.select("live");
  assert.equal(active,"live");
  assert.ok(app.guard("live"));
  await app.select("discord");
  assert.equal(active,"discord");
  assert.equal(app.owned,true);
  assert.equal(buttons[3].attrs["aria-pressed"],"true");
  // A stale tab that didn't receive BroadcastChannel is caught by polling.
  epoch+=1;active="studio";
  await timer();
  assert.equal(app.owned,false);
  await app.select("settings");
  assert.equal(active,"settings");
  assert.ok(app.guard("settings"));
  app.dispose();
  assert.equal(app.owned,false);
  console.log("PASS: 7 isolated text workspaces, shared global controls, immediate audio suspension, server ownership, stale-tab broadcast/poll and exclusive OBS");
}
test().catch(e=>{console.error(e);process.exitCode=1;});
