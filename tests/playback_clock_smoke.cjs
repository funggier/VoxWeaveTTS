// Browser media-currentTime reporting, cue selection and terminal cleanup.
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');

async function main(){
  const source=fs.readFileSync('web/playback_clock.js','utf8');
  const handlers={};
  let tick=null;
  const media={
    paused:true,ended:false,currentTime:0,
    addEventListener(type,fn){handlers[type]=fn;},
    play(){this.paused=false;this.ended=false;handlers.play?.();return Promise.resolve();},
    pause(){this.paused=true;handlers.pause?.();},
    seek(value){this.currentTime=value;handlers.seeked?.();},
    end(){this.currentTime=2.1;this.paused=true;this.ended=true;handlers.ended?.();},
  };
  const sent=[];
  const updates=[];
  const sandbox={
    window:{console:{warn(){}}},
    setInterval(fn,milliseconds){
      assert.equal(milliseconds,250);
      tick=fn;return 1;
    },
    clearInterval(){tick=null;},
    Promise,Number,console,
  };
  vm.createContext(sandbox);
  vm.runInContext(source,sandbox);
  const library=sandbox.window.VoxPlaybackClock;
  assert.equal(library.cueAt([{kind:'speech',start_ms:0,end_ms:900,display_text:'พูด'}],1),'พูด');
  assert.equal(library.cueAt([{kind:'silence',start_ms:0,end_ms:900,display_text:'hidden'}],100),'');
  const timeline={duration_ms:2100,segments:[
    {kind:'speech',start_ms:0,end_ms:900,display_text:'เซียนผู้นี้'},
    {kind:'silence',start_ms:900,end_ms:1200,display_text:'PRIVATE'},
    {kind:'speech',start_ms:1200,end_ms:2100,display_text:'ฮ่าฮ่า 🐱'},
  ]};
  const client=library.attach(media,payload=>{
    sent.push({...payload});
    return Promise.resolve({ok:true});
  },cue=>{updates.push({...cue});},()=> 'b'.repeat(32));
  client.setSpeech('a'.repeat(32),timeline);
  assert.equal(updates.at(-1).text,'');
  await media.play();
  await new Promise(resolve=>setImmediate(resolve));
  assert.equal(sent[0].event,'start');
  assert.equal(sent[0].position_ms,0);
  assert.equal(sent[0].sequence,1);
  assert.equal(updates.at(-1).text,'เซียนผู้นี้');
  media.currentTime=0.97;
  handlers.timeupdate?.();
  assert.equal(updates.at(-1).text,'');
  tick?.();
  await new Promise(resolve=>setImmediate(resolve));
  assert.equal(sent.at(-1).event,'progress');
  assert.equal(sent.at(-1).position_ms,970);
  media.seek(1.5);
  handlers.timeupdate?.();
  assert.equal(updates.at(-1).text,'ฮ่าฮ่า 🐱');
  await new Promise(resolve=>setImmediate(resolve));
  assert.equal(sent.at(-1).event,'seeked');
  media.pause();
  await new Promise(resolve=>setImmediate(resolve));
  assert.equal(sent.at(-1).event,'paused');
  assert.equal(updates.at(-1).text,'');
  assert.equal(tick,null);
  await media.play();
  await new Promise(resolve=>setImmediate(resolve));
  assert.equal(sent.at(-1).event,'resumed');
  media.end();
  await new Promise(resolve=>setImmediate(resolve));
  assert.equal(sent.at(-1).event,'ended');
  assert.equal(updates.at(-1).text,'');
  const count=sent.length;
  client.clear(); // Ended audio should not emit stopped AFTER ended.
  await new Promise(resolve=>setImmediate(resolve));
  assert.equal(sent.length,count);
  assert.equal(updates.at(-1).state,'idle');
  client.setSpeech('a'.repeat(32),timeline);
  media.currentTime=0;
  await media.play();
  await new Promise(resolve=>setImmediate(resolve));
  client.clear();
  await new Promise(resolve=>setImmediate(resolve));
  assert.equal(sent.at(-1).event,'stopped');
  assert.equal(sent.at(-1).session_id,'b'.repeat(32));
  assert.deepEqual(sent.map(e=>e.sequence).slice(0,6),[1,2,3,4,5,6]);
  console.log('PASS: play/currentTime, silence cue, seek, pause/resume, ended, stop and monotonic report sequence');
}
main().catch(err=>{console.error(err);process.exitCode=1;});
