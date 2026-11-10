// Test the OBS transparent overlay: SSE first, safe caption text, reconnect, poll fallback.
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');

async function main(){
  const html=fs.readFileSync('web/overlay.html','utf8');
  const match=html.match(/<script>([\s\S]*?)<\/script>/);
  assert.ok(match,'overlay script present');
  assert.match(html,/background:transparent/);
  const target={textContent:''};
  let stream, pollTick, fallbackCount=0;
  const ctx={
    document:{getElementById(name){assert.equal(name,'subtitle');return target;}},
    location:{search:'?mode=estimated'},
    URLSearchParams,
    JSON,Number,
    EventSource:class{
      constructor(url){assert.equal(url,'/v1/playback/stream?mode=estimated');this.handlers={};stream=this;}
      addEventListener(name,fn){this.handlers[name]=fn;}
      push(state){this.handlers.playback({data:JSON.stringify(state)});}
    },
    setInterval(fn,delay){assert.equal(delay,1000);pollTick=fn;return 123;},
    async fetch(url){
      fallbackCount++;
      assert.equal(url,'/v1/playback/state?mode=estimated');
      return {ok:true,async json(){return {
        revision:9,state:'playing',subtitle:'จาก fallback',stale:false
      };}};
    }
  };
  vm.createContext(ctx);
  vm.runInContext(match[1],ctx);
  await new Promise(resolve=>setImmediate(resolve));
  assert.equal(target.textContent,'จาก fallback','fallback read-only query');
  stream.onopen();
  stream.push({revision:1,state:'playing',subtitle:'เซียน 🐈‍⬛ <span>ไม่เป็น HTML</span>',stale:false});
  assert.equal(target.textContent,'เซียน 🐈‍⬛ <span>ไม่เป็น HTML</span>');
  stream.push({revision:0,state:'playing',subtitle:'old message',stale:false});
  assert.notEqual(target.textContent,'old message','out of order must not show');
  stream.push({revision:2,state:'paused',subtitle:'this must hide',stale:false});
  assert.equal(target.textContent,'');
  stream.onerror();
  await pollTick();
  assert.equal(target.textContent,'จาก fallback');
  stream.onopen(); // New server may have lower revision.
  stream.push({revision:0,state:'playing',subtitle:'เริ่มระบบใหม่',stale:false});
  assert.equal(target.textContent,'เริ่มระบบใหม่');
  stream.push({revision:1,state:'stale',subtitle:'old speech',stale:true});
  assert.equal(target.textContent,'');
  console.log('PASS: EventSource estimated-mode captions, no HTML injection, stale/paused hiding, reconnect revision reset and HTTP fallback');
}
main().catch(err=>{console.error(err);process.exitCode=1;});
