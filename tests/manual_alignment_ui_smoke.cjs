// No-browser-dependency UI test for user-marked WAV/Unicode manual timecodes.
const assert=require("node:assert/strict");
const fs=require("node:fs");
const vm=require("node:vm");
async function main(){
  const listeners=new Map();
  function el(id){
    if(!listeners.has(id)){
      listeners.set(id,{
        value:"",textContent:"",disabled:false,files:[],options:[],
        selectionStart:0,selectionEnd:0,
        addEventListener(type,fn){this[type]=fn;},
        replaceChildren(){this.options=[];},
        append(option){this.options.push(option);},
        click(){return this.click?.();},
      });
    }
    return listeners.get(id);
  }
  const id="a".repeat(32),text="นิรันดร์ 🧑🏽‍💻 ฮ่า";
  const server={
    speech_id:id,state:"ready",alignment_revision:0,
    audio:{segments:[{kind:"speech",display_text:text,start_ms:0,end_ms:1600}],
           manual_cues:[]},
  };
  let playbackReset=0;
  const waveformActions={loads:[],resets:0,draws:0};
  const waveform={
    load:async id=>{waveformActions.loads.push(id);},
    reset:()=>{waveformActions.resets++;},
    draw:()=>{waveformActions.draws++;},
  };
  const player={currentTime:0,paused:true};
  const posts=[];
  const downloaded=[];
  const sandbox={
    window:{VoxWaveformEditor:{attach:()=>waveform}},Blob,TextDecoder,Promise,JSON,Array,Number,URL:{
      createObjectURL:()=> "blob:manual",revokeObjectURL:()=>{},
    },
    setTimeout:(fn)=>fn(),
    document:{
      createElement:(tag)=>tag==="option"?{value:"",textContent:""}:{
        href:"",download:"",remove(){},click(){downloaded.push(this.download);}
      },
      body:{appendChild(){}},
    },
    async fetch(path,opts={}){
      if(path==="/v1/jobs/"+id)return{
        ok:true,async json(){return JSON.parse(JSON.stringify(server));}
      };
      if(path==="/v1/jobs/"+id+"/alignment"){
        const payload=JSON.parse(opts.body);posts.push(payload);
        if(payload.expected_revision!==server.alignment_revision)
          return{ok:false,async json(){return {error:"stale revision"};}};
        server.alignment_revision++;
        server.audio.manual_cues=payload.cues.map(item=>({
          ...item,display_text:Array.from(text).slice(item.start_offset,item.end_offset).join("")
        }));
        return{ok:true,async json(){return JSON.parse(JSON.stringify(server));}};
      }
      if(path==="/v1/alignment/evaluate"){
        const body=JSON.parse(opts.body);
        return{ok:true,async json(){return{
          matched_cues:body.candidate.length,reference_coverage_percent:100,
          mean_absolute_boundary_error_ms:0,
        };}};
      }
      throw Error("unhandled request "+path);
    },
  };
  vm.createContext(sandbox);
  vm.runInContext(fs.readFileSync("web/manual_alignment.js","utf8"),sandbox);
  const editor=sandbox.window.VoxManualAlignment.attach({
    el,player,getJobId:()=>id,onSaved:()=>{playbackReset++;}
  });
  await editor.load();
  assert.deepEqual(waveformActions.loads,[id]);
  assert.equal(waveformActions.resets,1);
  assert.equal(el("alignmentSegment").options.length,1);
  assert.equal(el("alignmentText").value,text);
  // Highlight the first Thai grapheme, using JS UTF-16 offsets.
  el("alignmentText").selectionStart=0;
  el("alignmentText").selectionEnd=2;
  player.currentTime=0.11;
  el("alignmentMarkStart").click();
  await Promise.resolve();
  player.currentTime=0.35;
  el("alignmentMarkEnd").click();
  await Promise.resolve();
  await editor.add();
  let cues=JSON.parse(el("alignmentJson").value);
  assert.equal(cues[0].start_offset,0);
  assert.equal(cues[0].end_offset,2);
  assert.equal(cues[0].start_ms,110);
  assert.equal(cues[0].end_ms,350);
  // Highlight the entire 5-codepoint emoji as a UTF-16 selection.
  const offsetUtf16=text.indexOf("🧑");
  el("alignmentText").selectionStart=offsetUtf16;
  el("alignmentText").selectionEnd=offsetUtf16+"🧑🏽‍💻".length;
  el("alignmentStart").value="410";
  el("alignmentEnd").value="990";
  await editor.add();
  cues=JSON.parse(el("alignmentJson").value);
  assert.equal(cues.length,2);
  assert.equal(cues[1].start_offset,9);
  assert.equal(cues[1].end_offset,13);
  await editor.save();
  assert.equal(playbackReset,1);
  assert.equal(posts[0].expected_revision,0);
  assert.equal(posts[0].cues[1].start_offset,9);
  assert.equal(server.alignment_revision,1);
  player.paused=false;
  await assert.rejects(editor.save(),/พักเสียง/);
  player.paused=true;
  el("alignmentReference").value=JSON.stringify(cues);
  await editor.compare();
  assert.match(el("alignmentMetrics").textContent,/matched_cues/);
  el("alignmentDownload").click();
  await Promise.resolve();
  assert.deepEqual(downloaded,["voxweavetts-manual-cues.json"]);
  assert.ok(waveformActions.draws>=3,"Manual editor changes should refresh waveform");
  // If Canvas 2D is unsupported, manual editing must remain usable.
  sandbox.window.VoxWaveformEditor.attach=()=>{throw Error("Canvas 2D unavailable");};
  const numericOnly=sandbox.window.VoxManualAlignment.attach({
    el,player,getJobId:()=>id,onSaved:()=>{}
  });
  await numericOnly.load();
  assert.equal(el("alignmentText").value,text);
  assert.equal(el("alignmentSegment").options.length,1);
  console.log("PASS: manual cue selection with Thai/emoji offsets, WAV marks, save revision, playback guard, metrics and JSON export");
}
main().catch(error=>{console.error(error);process.exitCode=1;});