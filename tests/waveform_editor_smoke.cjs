// Deterministic browser-free PCM16 waveform editor test, no external packages.
const assert=require("node:assert/strict");
const fs=require("node:fs");
const vm=require("node:vm");

function pcmWav({sampleRate=24000,channels=1,frames=24000,format=1,withJunk=false}={}){
  const data=Buffer.alloc(frames*channels*2);
  for(let i=0;i<frames;i++){
    const value=i<frames/4?0:(i<frames/2?Math.round(16000*Math.sin(i/3)):-14000);
    for(let c=0;c<channels;c++)data.writeInt16LE(c===1?-value:value,(i*channels+c)*2);
  }
  const junk=withJunk?Buffer.from([74,85,78,75,3,0,0,0,65,66,67,0]):Buffer.alloc(0);
  const buffer=Buffer.alloc(12+8+16+junk.length+8+data.length);
  buffer.write("RIFF",0);
  buffer.writeUInt32LE(buffer.length-8,4);
  buffer.write("WAVE",8);
  buffer.write("fmt ",12);
  buffer.writeUInt32LE(16,16);
  buffer.writeUInt16LE(format,20);
  buffer.writeUInt16LE(channels,22);
  buffer.writeUInt32LE(sampleRate,24);
  buffer.writeUInt32LE(sampleRate*channels*2,28);
  buffer.writeUInt16LE(channels*2,32);
  buffer.writeUInt16LE(16,34);
  junk.copy(buffer,36);
  const offset=36+junk.length;
  buffer.write("data",offset);
  buffer.writeUInt32LE(data.length,offset+4);
  data.copy(buffer,offset+8);
  return buffer;
}
const arrayBuffer=buf=>buf.buffer.slice(buf.byteOffset,buf.byteOffset+buf.byteLength);

async function main(){
  const code=fs.readFileSync("web/waveform_editor.js","utf8");
  let script, clicked, eventMap={}, waveBounds={left:40,width:800,height:190};
  const drawn={bars:0,filled:0,labels:[]},messages=[];
  const ctx={
    setTransform(){},clearRect(){},
    fillRect(){drawn.filled++;},
    beginPath(){},moveTo(){},lineTo(){drawn.bars++;},stroke(){},
    fillText(s){drawn.labels.push(String(s));},
    measureText(s){return{width:String(s).length*6};},
    set fillStyle(_){},set strokeStyle(_){},set font(_){},
  };
  const canvas={
    width:0,height:0,
    getContext(kind){assert.equal(kind,"2d");return ctx;},
    getBoundingClientRect(){return waveBounds;},
    addEventListener(name,fn){eventMap[name]=fn;},
    setPointerCapture(){},releasePointerCapture(){},
  };
  const makeInput=(value)=>({
    value:String(value),disabled:false,
    events:{},
    addEventListener(name,fn){this.events[name]=fn;},
  });
  const zoom=makeInput(1),pan=makeInput(0),start=makeInput(0),end=makeInput(0);
  const playEvents={};
  const player={currentTime:0,paused:true,
    addEventListener(name,fn){playEvents[name]=fn;}};
  const wav=pcmWav({frames:48000,channels:2,withJunk:true});
  const window={devicePixelRatio:2,addEventListener(){}};
  const sandbox={
    window,DataView,ArrayBuffer,Float32Array,Number,Math,String,Promise,
    async fetch(url){
      assert.equal(url,"/v1/jobs/"+"a".repeat(32)+"/audio");
      return{ok:true,async arrayBuffer(){return arrayBuffer(wav);}};
    },
  };
  vm.createContext(sandbox);
  vm.runInContext(code,sandbox);
  const lib=window.VoxWaveformEditor;
  assert.ok(lib && typeof lib.attach==="function");
  assert.equal(lib.readWaveform(arrayBuffer(wav)).sampleRate,24000);
  assert.equal(lib.readWaveform(arrayBuffer(wav)).channels,2);
  assert.equal(lib.readWaveform(arrayBuffer(wav)).durationMs,2000);
  assert.equal(lib.readWaveform(arrayBuffer(wav)).min.length,Math.ceil(48000/256));
  const peaks=lib.readWaveform(arrayBuffer(wav));
  assert.equal(peaks.min[0],0);
  assert.equal(peaks.max[0],0);
  assert.ok(peaks.max.some(x=>x>0.2));
  assert.ok(peaks.min.some(x=>x<-.2));
  assert.throws(()=>lib.readWaveform(arrayBuffer(pcmWav({format:3}))),/PCM16/);
  assert.throws(()=>lib.readWaveform(arrayBuffer(Buffer.from("not RIFF/WAVE"))));
  const truncated=arrayBuffer(wav.subarray(0,wav.length-1));
  assert.throws(()=>lib.readWaveform(truncated),/Truncated WAV/);
  const view=lib.viewport(10000,4,.5);
  assert.equal(view.startMs,3750);
  assert.equal(view.endMs,6250);
  assert.equal(lib.timeFromX(400,800,view),5000);
  assert.equal(lib.xFromTime(5000,800,view),400);
  assert.equal(lib.timeFromX(-100,800,view),3750);
  assert.equal(lib.timeFromX(900,800,view),6250);

  const widget=lib.attach({
    canvas,player,zoomInput:zoom,panInput:pan,startInput:start,endInput:end,
    onFeedback:x=>messages.push(x),
    getSegments:()=>[
      {kind:"speech",start_ms:0,end_ms:1700},
      {kind:"silence",start_ms:1700,end_ms:2000},
    ],
    getCues:()=>[{start_ms:200,end_ms:600}],
  });
  await widget.load("a".repeat(32));
  assert.equal(widget.durationMs,2000);
  assert.equal(widget.speechId,"a".repeat(32));
  assert.equal(canvas.width,1600,"retina high DPI canvas should use physical pixels");
  assert.equal(pan.disabled,true);
  assert.ok(drawn.filled>2);
  // Drag time selection: 25% to 75% of 2 seconds.
  eventMap.pointerdown({button:0,clientX:240,pointerId:1,preventDefault(){}});
  eventMap.pointermove({clientX:640});
  eventMap.pointerup({clientX:640,pointerId:1});
  assert.equal(Number(start.value),500);
  assert.equal(Number(end.value),1500);
  assert.equal(widget.viewport().startMs,0);
  assert.equal(player.currentTime,0,"drag should not seek player");
  // Click seeks without changing selection.
  eventMap.pointerdown({button:0,clientX:440,pointerId:2,preventDefault(){}});
  eventMap.pointerup({clientX:440,pointerId:2});
  assert.equal(player.currentTime,1);
  assert.equal(Number(start.value),500);
  assert.equal(Number(end.value),1500);
  // Zoom=4, pan=100% => second 1500ms of clip.
  zoom.value="4";zoom.events.input();pan.value="1000";pan.events.input();
  assert.equal(pan.disabled,false);
  assert.equal(widget.viewport().startMs,1500);
  assert.equal(widget.viewport().endMs,2000);
  eventMap.pointerdown({button:0,clientX:40,pointerId:3,preventDefault(){}});
  eventMap.pointerup({clientX:40,pointerId:3});
  assert.equal(player.currentTime,1.5);
  // Arrow nudges playhead by 25ms, Shift by 5ms.
  const evt={key:"ArrowRight",preventDefault(){},shiftKey:false};
  eventMap.keydown(evt);
  assert.equal(player.currentTime,1.525);
  eventMap.keydown({...evt,shiftKey:true});
  assert.equal(player.currentTime,1.5299999999999998);
  zoom.value="1";zoom.events.input();
  assert.equal(pan.disabled,true);
  assert.equal(widget.viewport().startMs,0);
  widget.reset();
  assert.equal(widget.durationMs,0);
  assert.equal(widget.speechId,null);
  assert.ok(messages.some(x=>x.includes("Waveform")));
  console.log("PASS waveform: PCM16 mono/stereo RIFF decoding, odd-sized chunks, peak envelope, retina rendering, drag marks, click seek, zoom/pan, keyboard nudging");
}
main().catch(e=>{console.error(e);process.exitCode=1;});
