// Shared audio scheduler: serial, overlap, native media play, and cancellation.
const assert=require("node:assert/strict");
const {attach}=require("../web/audio_scheduler.js");
class Audio {
  constructor(name){this.name=name;this.paused=true;this.ended=false;this.listeners={};this.starts=0;}
  addEventListener(name,callback){(this.listeners[name]??=[]).push(callback);}
  fire(name){for(const callback of this.listeners[name]||[])callback({target:this});}
  async play(){this.paused=false;this.ended=false;this.starts++;this.fire("play");}
  pause(){if(this.paused)return;this.paused=true;this.fire("pause");}
  finish(){this.ended=true;this.paused=true;this.fire("ended");}
}
async function test(){
  const a=new Audio("YouTube"),b=new Audio("Discord"),c=new Audio("Studio");
  const scheduler=attach({audios:[a,b,c]});
  assert.equal(scheduler.policy,"serial");
  assert.equal(await scheduler.play(a),true);
  let bResolved=false;
  const pending=scheduler.play(b).then(r=>{bResolved=r;});
  await Promise.resolve();
  assert.equal(b.starts,0,"Discord must not overlap YouTube in serial");
  assert.equal(scheduler.pending,1);
  a.finish();
  await pending;
  assert.equal(bResolved,true);
  assert.equal(b.starts,1);
  // Allow manual Studio voice at the same time as the still-playing Discord.
  scheduler.setPolicy("overlap");
  assert.equal(await scheduler.play(c),true);
  assert.equal(scheduler.playing,2);
  // Changing back to serial must not cut currently playing audio, but the
  // next YouTube voice must wait until both Discord and Studio finish.
  scheduler.setPolicy("serial");
  let resumed=false;
  const next=scheduler.play(a).then(ok=>{resumed=ok;});
  b.finish();
  await Promise.resolve();
  assert.equal(a.starts,1);
  c.finish();
  await next;
  assert.equal(resumed,true);
  assert.equal(a.starts,2);
  // Native HTML audio controls are also serialized, not just Auto-read.
  await b.play();
  assert.equal(b.paused,true);
  assert.equal(scheduler.pending,1);
  a.finish();
  await Promise.resolve();
  assert.equal(b.paused,false);
  // Cancel a waiting source without disturbing an already playing one.
  const never=scheduler.play(c);
  scheduler.cancel(c);
  assert.equal(await never,false);
  assert.equal(b.paused,false);
  b.finish();
  console.log("PASS: global serial/overlap audio, native play controls, FIFO, cancellation");
}
test().catch(e=>{console.error(e);process.exitCode=1;});
