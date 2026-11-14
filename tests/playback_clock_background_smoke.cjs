// Media timeupdate keeps OBS progress current when hidden-tab timers are stopped.
const assert=require("node:assert/strict");
const fs=require("node:fs");
const vm=require("node:vm");
async function main(){
  let now=0,timer=null;
  const handlers={},events=[];
  const media={
    currentTime:0,paused:true,ended:false,
    addEventListener(event,fn){handlers[event]=fn;},
    play(){this.paused=false;handlers.play();return Promise.resolve();},
    end(){this.paused=true;this.ended=true;handlers.ended();},
  };
  const env={
    window:{console:{warn(){}}},Promise,Number,
    Date:{now:()=>now},
    setInterval(fn){timer=fn;return 1;},
    clearInterval(){timer=null;},
  };
  vm.createContext(env);
  vm.runInContext(fs.readFileSync("web/playback_clock.js","utf8"),env);
  const clock=env.window.VoxPlaybackClock.attach(
    media,packet=>{events.push({...packet});return Promise.resolve();},
    ()=>{},()=> "b".repeat(32)
  );
  clock.setSpeech("a".repeat(32),{
    duration_ms:3000,segments:[{kind:"speech",display_text:"สวัสดี",
      start_ms:0,end_ms:3000}]
  });
  await media.play();
  await new Promise(resolve=>setImmediate(resolve));
  assert.equal(events.at(-1).event,"start");
  assert.equal(typeof timer,"function");
  now=400;media.currentTime=.4;handlers.timeupdate();
  await new Promise(resolve=>setImmediate(resolve));
  assert.equal(events.at(-1).event,"progress");
  assert.equal(events.at(-1).position_ms,400);
  const count=events.length;
  now=420;media.currentTime=.42;handlers.timeupdate();
  await new Promise(resolve=>setImmediate(resolve));
  assert.equal(events.length,count,"timeupdate progress is rate-limited");
  now=810;media.currentTime=.81;handlers.timeupdate();
  await new Promise(resolve=>setImmediate(resolve));
  assert.equal(events.at(-1).position_ms,810);
  assert.equal(events.length,count+1);
  assert.equal(media.paused,false);
  media.end();
  await new Promise(resolve=>setImmediate(resolve));
  assert.equal(events.at(-1).event,"ended");
  console.log("PASS: media timeupdate reports actual playback clock in hidden tab without running setInterval");
}
main().catch(error=>{console.error(error);process.exitCode=1;});
