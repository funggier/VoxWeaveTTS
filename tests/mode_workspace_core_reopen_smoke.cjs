"use strict";
const assert=require("node:assert/strict");
const fs=require("node:fs");
const vm=require("node:vm");
const source=fs.readFileSync("web/mode_workspace.js","utf8");
const names=["studio","reader","live","youtube_browser","tiktok_browser",
  "tiktok","discord","discord_client","queue","rules","language_routes","settings"];
const views=names.map(name=>({
  hidden:false,getAttribute(key){return key==="data-mode-view"?name:null}
}));
const buttons=names.map(name=>({
  handlers:{},getAttribute(key){return key==="data-mode-target"?name:null},
  setAttribute(){},addEventListener(key,fn){this.handlers[key]=fn}
}));
const nodes=new Map();
function get(id){
  if(!nodes.has(id))nodes.set(id,{textContent:"",addEventListener(){}});
  return nodes.get(id);
}
const document={
  getElementById:get,
  querySelectorAll(selector){
    if(selector==="[data-mode-view]")return views;
    if(selector==="[data-mode-target]")return buttons;
    return [];
  },
  addEventListener(){}
};
const seen=[];
let activations=0;
let revision=3;
const sandbox={
  window:{
    VoxLastRuntimeSnapshot:{mode:"computer",dashboard_cursor:"0:0:0:0"},
    setInterval(){return 1},clearInterval(){},
  },
  document,Promise,JSON,Number,
  fetch:async (route,options={})=>{
    seen.push(route);
    if(route==="/v1/modes/state")return{
      ok:true,json:async()=>({active_mode:"youtube_browser",revision,
                             mode_revisions:{youtube_browser:revision}})};
    if(route==="/v1/modes/activate"){
      activations++;
      return {ok:true,json:async()=>({
        active_mode:JSON.parse(options.body).mode,
        revision:++revision,mode_revisions:{youtube_browser:revision},
        mode_token:"1".repeat(32)
      })};
    }
    throw Error("unexpected GET "+route);
  }
};
vm.createContext(sandbox);
vm.runInContext(source,sandbox);
(async()=>{
  const app=sandbox.window.VoxWorkspaceModes.attach({document});
  app.startMonitor();
  await new Promise(resolve=>setImmediate(resolve));
  assert.equal(app.activeMode,"youtube_browser");
  assert.equal(app.owned,false,"viewing Core state alone must not claim ownership");
  assert.equal(activations,0,"page refresh must not POST /modes/activate");
  assert.deepEqual(seen,["/v1/modes/state"]);
  assert.match(get("modeOwnerStatus").textContent,/Core Server/);
  await app.select("youtube_browser");
  assert.equal(activations,1,"only explicit selection claims the channel");
  assert.equal(app.owned,true);
  app.dispose();
  console.log("PASS: Core mode refresh restores real Server tab read-only; no unexpected activation; explicit click controls");
})().catch(error=>{console.error(error);process.exitCode=1});
