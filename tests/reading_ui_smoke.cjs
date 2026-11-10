// Dependency-free reader UI state machine smoke (Windows/Node).
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');

async function run(){
  const html=fs.readFileSync('web/index.html','utf8');
  const start=html.indexOf('let readerText = null;');
  const end=html.indexOf('const buildSpeechPayload = () =>',start);
  assert.ok(start>0&&end>start,"reader code block exists");
  const nodes=new Map();
  function el(id){
    if(!nodes.has(id)){
      const n={
        value:'',textContent:'',disabled:false,style:{},checked:false,
        listeners:{},options:[],paused:true,
        addEventListener(name,fn){this.listeners[name]=fn;},
        replaceChildren(){this.options=[];this.value='';},
        append(option){this.options.push(option);},
        pause(){this.paused=true;},
        load(){},removeAttribute(){},focus(){},
        async play(){this.paused=false;return;},
        click(){return this.listeners.click?.();},
      };
      nodes.set(id,n);
    }
    return nodes.get(id);
  }
  const contents=["ตอนแรก 👩🏽‍💻","55555 และ «ฮ่า»","บทที่สอง จบแล้ว"];
  const id='f'.repeat(64);
  let position={chunk_chars:350,chunk_total:3,next_chunk:1,updated_at:'2026-11-10'};
  let revision='1'.repeat(64);
  let saved=0,cancelled=0,jobs=0,played=0;
  const document={
    schema_version:1,document_id:id,title:'My novel',
    format:'txt',chunk_chars:350,chunk_total:3,chapter_total:2,
    page_index:0,page_size:15,has_next:false,
    chapters:[{index:0,title:'บทที่ 1',chunk_start:0,chunk_end:2},
              {index:1,title:'บทที่ 2',chunk_start:2,chunk_end:3}],
    chunks:contents.map((text,index)=>({
      index,chapter_index:index<2?0:1,chapter_title:index<2?'บทที่ 1':'บทที่ 2',
      start:index*20,end:index*20+text.length,text,
      boundary_quality:index===1?"unicode_only_fallback":"whitespace",
      start_boundary_quality:index===1?"thai_preposed_vowel_hint":"whitespace",
    })),
  };
  let blockAutoPlay=false;
  el('readerChunkChars').value='350';
  el('readerAutoNext').checked=false;
  const fetched=[];
  const sandbox={
    el,window:{confirm:()=>true},console,TextDecoder,
    VoxPlaybackClock:{attach:()=>({setSpeech(){},clear(){},update(){}})},
    setTimeout:(fn)=>{queueMicrotask(fn);return 1;},
    URL:{createObjectURL:()=> 'blob:test',revokeObjectURL:()=>{}},
    buildSpeechPayload:()=>({engine_id:"makham-paradee-cpu",voice_id:"paradee_thai",
                             rules:[],pronunciations:{},speed:1}),
    document:{createElement:()=>({value:'',textContent:''})},
    async fetch(url,opts={}){
      fetched.push(url);
      const body=opts.body?JSON.parse(opts.body):null;
      if(url==="/v1/documents/preview")return {
        ok:true,async json(){return {...document,page_index:body.page_index};}
      };
      if(url.startsWith("/v1/reading/progress?"))return{
        ok:true,async json(){return {
          document_id:id,revision,progress:position,
        };}
      };
      if(url==="/v1/reading/progress"){
        if(body.expected_revision!==revision)return{
          ok:false,status:409,async json(){return {error:"conflict"};}
        };
        assert.equal(body.document_id,id);
        assert.equal(body.chunk_chars,350);
        saved++;
        position={chunk_chars:350,chunk_total:3,next_chunk:body.next_chunk,
                  updated_at:"2026-11-10"};
        revision=String(saved+1).repeat(64);
        return{ok:true,async json(){return {
          document_id:id,progress:position,revision,
        };}};
      }
      if(url==="/v1/reading/progress/clear"){
        position=null;revision='a'.repeat(64);
        return{ok:true,async json(){return {progress:null,revision};}};
      }
      if(url==="/v1/jobs"&&opts.method==="POST"){
        jobs++;
        assert.equal(body.source,"document");
        assert.ok(contents.includes(body.text));
        return{ok:true,async json(){return{speech_id:'job'+jobs,state:"queued"};}};
      }
      if(url.startsWith("/v1/jobs/")&&url.endsWith("/cancel")){
        cancelled++;
        return{ok:true,async json(){return{state:"cancelled"};}};
      }
      if(url.startsWith("/v1/jobs/")&&url.endsWith("/audio")){
        return{ok:true,async blob(){return new Blob(["RIFFsample"]);}};
      }
      if(url.startsWith("/v1/jobs/")){
        return{ok:true,async json(){return{state:"ready"};}};
      }
      throw new Error("Unexpected fetch "+url);
    },
  };
  vm.createContext(sandbox);
  vm.runInContext(html.slice(start,end),sandbox);
  // Open file without its binary source; the state is supplied by the preview API.
  vm.runInContext('readerText="บทที่ 1\\nข้อความ";readerFormat="txt";readerTitle="My novel";',sandbox);
  await vm.runInContext('loadReaderPage(0)',sandbox);
  await vm.runInContext('fetchReaderProgress()',sandbox);
  assert.equal(el('readerResume').disabled,false);
  assert.match(el('readerProgressStatus').textContent,/2/);
  await el('readerResume').listeners.click();
  assert.match(el('readerBoundaryWarning').textContent,/หมายเหตุ/);
  assert.equal(el('readerChunk').value,'1');
  assert.equal(el('readerChunkPreview').value,contents[1]);
  // Resume at second chunk and complete playback.
  await vm.runInContext('readerBegin(1)',sandbox);
  assert.equal(jobs,1);
  assert.equal(el('readerAudio').paused,false);
  await el('readerAudio').listeners.ended();
  assert.equal(saved,1);
  assert.equal(position.next_chunk,2);
  // Enable auto-follow; it submits one chunk only after prior audio ended.
  el('readerAutoNext').checked=true;
  await vm.runInContext('readerBegin(2)',sandbox);
  assert.equal(jobs,2);
  await el('readerAudio').listeners.ended();
  assert.equal(saved,2);
  assert.equal(position.next_chunk,3);
  assert.equal(jobs,2,"must not queue beyond end");
  assert.equal(el('readerResume').disabled,true);
  // Rewind to first chunk manually and cancel; position must not skip ahead.
  await vm.runInContext('readerBegin(0)',sandbox);
  assert.equal(jobs,3);
  await el('readerStop').listeners.click();
  assert.equal(position.next_chunk,3);
  assert.equal(cancelled,1);
  assert.equal(el('readerStop').disabled,true);
  assert.ok(fetched.some(url=>url.includes('/v1/reading/progress')));
  console.log('PASS: reader restore, resume, one-at-a-time playback, ended-only bookmark, end-of-document, stop without skipping');
}
run().catch(error=>{console.error(error);process.exitCode=1;});