/* Central playback policy shared by all workspace players.
 * "serial" waits for earlier playing audio to finish; "overlap" allows
 * simultaneous playback. Rendering jobs may proceed while audio is waiting.
 */
(function(root){
"use strict";
function attach({audios=[],policy="serial",onPolicyChange}={}){
  if(!["serial","overlap"].includes(policy))throw Error("invalid audio policy");
  let current=policy;
  const playing=new Set(),reserved=new Set(),waiting=[];
  const watched=new Set();
  function busy(other){
    return [...playing].some(a=>a!==other&&!a.paused) ||
           [...reserved].some(a=>a!==other);
  }
  function clear(audio){
    playing.delete(audio);reserved.delete(audio);
    drain();
  }
  function removeWaiter(audio){
    for(let i=waiting.length-1;i>=0;i--){
      if(waiting[i].audio===audio){
        const item=waiting.splice(i,1)[0];
        item.resolve(false);
      }
    }
  }
  function watch(audio){
    if(watched.has(audio))return;
    watched.add(audio);
    audio.addEventListener("ended",()=>clear(audio));
    audio.addEventListener("pause",()=>clear(audio));
    audio.addEventListener("error",()=>clear(audio));
    audio.addEventListener("play",()=>{
      if(current==="serial" && busy(audio)){
        // User pressed native media controls while another mode was playing.
        // Pause this player and enqueue it rather than interrupting the other.
        audio.pause();
        if(!waiting.some(item=>item.audio===audio))
          waiting.push({audio,resolve:()=>{}});
        return;
      }
      playing.add(audio);
    });
  }
  async function start(audio){
    reserved.add(audio);
    try{
      await audio.play();
      playing.add(audio);
      return true;
    }finally{
      reserved.delete(audio);
      if(audio.paused)clear(audio);
    }
  }
  function drain(){
    if(current==="overlap"){
      for(const item of waiting.splice(0)){
        start(item.audio).then(item.resolve,item.reject);
      }
      return;
    }
    if([...playing].some(a=>!a.paused)||reserved.size)
      return;
    const item=waiting.shift();
    if(item)start(item.audio).then(item.resolve,item.reject);
  }
  function play(audio){
    watch(audio);
    if(current==="overlap"||!busy(audio))
      return start(audio);
    return new Promise((resolve,reject)=>{
      if(!waiting.some(item=>item.audio===audio))
        waiting.push({audio,resolve,reject});
      else resolve(false);
    });
  }
  function cancel(audio){
    removeWaiter(audio);
    if(audio && !audio.paused)audio.pause();
    clear(audio);
  }
  function setPolicy(value){
    if(!["serial","overlap"].includes(value))throw Error("unknown audio policy");
    current=value;
    onPolicyChange?.(value);
    drain();
  }
  for(const audio of audios)watch(audio);
  return {
    play,cancel,watch,setPolicy,
    get policy(){return current;},
    get pending(){return waiting.length;},
    get playing(){return [...playing].filter(a=>!a.paused).length;},
  };
}
root.VoxAudioScheduler={attach};
if(typeof module!=="undefined"&&module.exports)module.exports={attach};
})(typeof window==="undefined"?globalThis:window);
