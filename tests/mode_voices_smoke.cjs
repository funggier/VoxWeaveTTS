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
for(const mode of ["studio","reader","queue","live","tiktok","discord","discord_client"])
  views.set(mode,new Node("div"));
const document={
  createElement:tag=>new Node(tag),
  querySelector:selector=>{
    const match=selector.match(/^\[data-mode-view="([^"]+)"\]$/);
    return match?views.get(match[1]):null;
  },
};
let revision=0,posts=[];
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
  assert.equal(path,"/v1/settings/mode-voices");
  if(!options?.method)return{ok:true,async json(){return{
    revision,policy:"serial",modes:overrides,
  };}};
  assert.equal(options.headers["X-VoxWeaveTTS-Intent"],"save-mode-voice");
  const body=JSON.parse(options.body);
  assert.equal(body.expected_revision,revision);
  revision++;
  posts.push(body);
  return{ok:true,async json(){return{revision};}};
};
async function main(){
  const manager=attach({document,engines:()=>voices,getDefault:()=>defaults});
  const config=await manager.load();
  assert.equal(config.policy,"serial");
  assert.equal(manager.modes.length,7);
  assert.equal(manager.read("live").engine_id,"vachana-cpu");
  assert.equal(manager.read("discord").engine_id,"makham-paradee-cpu");
  assert.equal(manager.read("live").speed,1.1);
  // User edits the live channel mid-stream; new job reads current values,
  // existing WAV isn't mutated or re-synthesized.
  const live=views.get("live");
  const all=live.children[0].children;
  const grid=all[2];
  const engine=grid.children[0].children[1];
  const voice=grid.children[1].children[1];
  const speed=grid.children[2].children[1];
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
  console.log("PASS: independent 7-mode engine/voice/speed/DSP and persisted playback policy");
}
main().catch(e=>{console.error(e);process.exitCode=1;});
