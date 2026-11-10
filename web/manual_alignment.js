/* Manual subtitle cue editor — only values from generated public display text.
 * Never calls a model, and never persists a book or audio to disk.
 */
(function(root) {
"use strict";
function attach({el, player, getJobId, onSaved}) {
  let job=null;
  const get=id=>el(id);
  function status(message){get("alignmentStatus").textContent=message;}
  let wave=null;
  if (root.VoxWaveformEditor) {
    try {
      wave=root.VoxWaveformEditor.attach({
        canvas:get("alignmentWaveform"),player,
        zoomInput:get("alignmentZoom"),panInput:get("alignmentPan"),
        startInput:get("alignmentStart"),endInput:get("alignmentEnd"),
        onFeedback:status,
        getSegments:()=>job?.audio?.segments||[],
        getCues:()=>{
          try{
            const all=visibleCues();
            return Array.isArray(all)?all.slice(0,128):[];
          }catch{return [];}
        }
      });
    } catch(error) {
      // A missing canvas renderer must never break the numeric cue editor.
      status("Waveform ไม่พร้อม ใช้ช่องเวลาแบบเดิมได้: "+String(error.message||error));
    }
  }
  function visibleCues(){return JSON.parse(get("alignmentJson").value);}
  function serializeCues(items){return JSON.stringify(items,null,2);}
  function minimal(items) {
    if (!Array.isArray(items)) throw Error("Cues ต้องเป็น JSON Array");
    return items.map(item=>({
      segment_index:item.segment_index,
      start_offset:item.start_offset,end_offset:item.end_offset,
      start_ms:item.start_ms,end_ms:item.end_ms,
    }));
  }
  function selectSegment(){
    if(!job) return;
    const part=job.audio.segments[Number(get("alignmentSegment").value)];
    get("alignmentText").value=part?.display_text||"";
  }
  async function load(){
    const jobId=getJobId();
    if(!jobId) throw Error("กรุณาสร้างงานเสียงใน Speech Queue ก่อน");
    const response=await fetch("/v1/jobs/"+jobId,{cache:"no-store"});
    const found=await response.json();
    if(!response.ok||found.state!=="ready")throw Error(found.error||"งานเสียงยังไม่พร้อม");
    job=found;
    wave?.reset();
    const options=get("alignmentSegment");
    options.replaceChildren();
    found.audio.segments.forEach((part,index)=>{
      if(part.kind!=="speech"||!part.display_text)return;
      const option=document.createElement("option");
      option.value=String(index);
      option.textContent="ช่วง "+(index+1)+" · "+part.start_ms+"–"+part.end_ms+" ms";
      options.append(option);
    });
    if(!options.options.length)throw Error("งานเสียงไม่มีส่วน Speech ให้จัดแนว");
    options.value=options.options[0].value;
    selectSegment();
    get("alignmentJson").value=serializeCues(found.audio.manual_cues||[]);
    status("พร้อมกำหนดเวลา · Revision "+found.alignment_revision+" · เลือกข้อความในกล่องแล้วจับเวลาเสียง");
    if (wave) {
      try { await wave.load(found.speech_id); }
      catch(error) { status("โหลดงานแล้ว แต่ Waveform ไม่พร้อม: "+String(error.message||error)); }
    }
  }
  function mark(id){
    if(!job)throw Error("โหลดงานเสียงที่พร้อมก่อน");
    const time=Math.round(Number(player.currentTime||0)*1000);
    if(!Number.isInteger(time)||time<0)throw Error("ตำแหน่ง Audio ไม่ถูกต้อง");
    get(id).value=String(time);
    wave?.draw();
    status("บันทึกจุดเวลา "+time+" ms (เลือกคำแล้วกดเพิ่มช่วง)");
  }
  function add(){
    if(!job)throw Error("กรุณาโหลดงานเสียงก่อน");
    const box=get("alignmentText"),text=box.value;
    const seg=Number(get("alignmentSegment").value);
    const start=Array.from(text.slice(0,box.selectionStart)).length;
    const end=Array.from(text.slice(0,box.selectionEnd)).length;
    const startMs=Number(get("alignmentStart").value);
    const endMs=Number(get("alignmentEnd").value);
    if(end<=start)throw Error("ไฮไลต์ข้อความที่ต้องการกำหนดเวลาในช่องด้านบน");
    if(!Number.isInteger(startMs)||!Number.isInteger(endMs)||endMs<=startMs)
      throw Error("เวลาเริ่มและเวลาจบต้องเป็นจำนวนเต็มมิลลิวินาทีที่เพิ่มขึ้น");
    const cues=minimal(visibleCues());
    cues.push({segment_index:seg,start_offset:start,end_offset:end,
               start_ms:startMs,end_ms:endMs});
    cues.sort((a,b)=>a.start_ms-b.start_ms);
    get("alignmentJson").value=serializeCues(cues);
    wave?.draw();
    status("เพิ่ม Cue "+JSON.stringify(text.slice(box.selectionStart,box.selectionEnd))+
      " แล้ว · ตรวจรายการก่อนบันทึก");
  }
  async function save(){
    if(!job)throw Error("โหลดงานเสียงก่อน");
    if(!player.paused)throw Error("กรุณาพักเสียงก่อนบันทึก เพื่อให้ Timeline ใหม่เริ่มในรอบเล่นถัดไป");
    const cues=minimal(visibleCues());
    const response=await fetch("/v1/jobs/"+job.speech_id+"/alignment",{
      method:"POST",
      headers:{"Content-Type":"application/json","X-VoxWeaveTTS-Intent":"save-manual-alignment"},
      body:JSON.stringify({cues,expected_revision:job.alignment_revision}),
    });
    const data=await response.json();
    if(!response.ok)throw Error(data.error||"บันทึก Alignment ไม่ได้");
    job=data;
    get("alignmentJson").value=serializeCues(cues);
    wave?.draw();
    onSaved(data);
    status("บันทึก Timecodes ในหน่วยความจำของงานสำเร็จ (Revision "+
      data.alignment_revision+") · กด Play ใหม่แล้วเปิด /overlay?mode=manual");
  }
  function download(){
    const cues=minimal(visibleCues());
    const payload=new Blob([serializeCues(cues)+"\n"],{type:"application/json;charset=utf-8"});
    const url=URL.createObjectURL(payload);
    const a=document.createElement("a");
    a.href=url;a.download="voxweavetts-manual-cues.json";
    document.body.appendChild(a);a.click();a.remove();
    setTimeout(()=>URL.revokeObjectURL(url),1000);
    status("ดาวน์โหลด Cues ลงเครื่องแล้ว (ยังไม่ใช่การบันทึกถาวรในโปรแกรม)");
  }
  async function compare(){
    const candidate=minimal(visibleCues());
    const reference=minimal(JSON.parse(get("alignmentReference").value));
    const response=await fetch("/v1/alignment/evaluate",{
      method:"POST",
      headers:{"Content-Type":"application/json","X-VoxWeaveTTS-Intent":"evaluate-manual-alignment"},
      body:JSON.stringify({candidate,reference}),
    });
    const result=await response.json();
    if(!response.ok)throw Error(result.error||"เปรียบเทียบไม่ได้");
    get("alignmentMetrics").textContent=JSON.stringify(result,null,2);
    status("คำนวณความคลาดเคลื่อนจาก Cue ที่มี segment/offset เหมือนกันแล้ว");
  }
  function bind(id,fn){
    get(id).addEventListener("click",()=>{
      Promise.resolve().then(fn).catch(err=>status(String(err.message||err)));
    });
  }
  get("alignmentSegment").addEventListener("change",()=>{selectSegment();wave?.draw();});
  bind("alignmentLoad",load);
  bind("alignmentMarkStart",()=>mark("alignmentStart"));
  bind("alignmentMarkEnd",()=>mark("alignmentEnd"));
  bind("alignmentAdd",add);
  bind("alignmentFormat",()=>{get("alignmentJson").value=serializeCues(minimal(visibleCues()));wave?.draw();status("จัดรูปแบบ JSON แล้ว");});
  bind("alignmentSave",save);
  bind("alignmentDownload",download);
  bind("alignmentCompare",compare);
  bind("alignmentImport",()=>get("alignmentImportFile").click());
  get("alignmentImportFile").addEventListener("change",async()=>{
    try {
      const input=get("alignmentImportFile"),file=input.files?.[0];
      if(!file)return;
      if(file.size>32768)throw Error("ไฟล์ Alignment ต้องไม่เกิน 32 KiB");
      const raw=new TextDecoder("utf-8",{fatal:true}).decode(await file.arrayBuffer()).replace(/^\uFEFF/,"");
      get("alignmentJson").value=serializeCues(minimal(JSON.parse(raw)));
      wave?.draw();
      status("นำเข้า JSON แล้ว · ตรวจช่วงและกดบันทึกในงานอีกครั้ง");
    }catch(err){status(String(err.message||err));}
    finally{get("alignmentImportFile").value="";}
  });
  return {load,save,add,compare};
}
root.VoxManualAlignment={attach};
if(typeof module!=="undefined"&&module.exports)module.exports={attach};
})(typeof window==="undefined"?globalThis:window);