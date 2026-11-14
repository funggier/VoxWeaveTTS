/* Shared AI Processing settings. No external resources are fetched by this UI.
 * All controls read/write a single revision-guarded config in Portable data/.
 */
(function(root){
"use strict";
function attach(document, fetcher){
  const get=id=>document.getElementById(id);
  if(!get("aiEnabled"))return null;
  const fields={
    enabled:"aiEnabled", engine:"aiEngine", ollama_base_url:"aiOllamaBaseUrl",
    model:"aiModel", operation:"aiOperation",
    source_language:"aiSourceLanguage", target_language:"aiTarget",
    translation_mode:"aiTranslationMode", auto_detect:"aiAutoDetect",
    priority_instructions:"aiPriority", custom_prompt:"aiPrompt",
    display_mode:"aiDisplay", timeout_seconds:"aiTimeout",
    keep_alive_minutes:"aiKeepAlive",
    fallback:"aiFallback", allow_context_files:"aiAllowFiles",
    context_files:"aiContextFiles"
  };
  const booleanKeys=new Set(["enabled","auto_detect","allow_context_files"]);
  let revision=null, lastLoaded=null, engines=[], packages=[];
  const status=text=>{get("aiSettingsStatus").textContent=text;};
  function readFields(){
    const data={};
    for(const [name,id] of Object.entries(fields)){
      const element=get(id);
      if(name==="context_files"){
        data[name]=String(element.value||"").split(/[,\r\n]+/).map(x=>x.trim()).filter(Boolean);
      }else if(name==="timeout_seconds"||name==="keep_alive_minutes"){
        data[name]=Number(element.value);
      }else if(booleanKeys.has(name)){
        data[name]=Boolean(element.checked);
      }else{
        data[name]=String(element.value);
      }
    }
    return data;
  }
  function applyFields(data){
    for(const [name,id] of Object.entries(fields)){
      const element=get(id);
      if(name==="context_files")element.value=(data[name]||[]).join(", ");
      else if(booleanKeys.has(name))element.checked=Boolean(data[name]);
      else element.value=String(data[name]);
    }
    updateAvailability();
  }
  function updateAvailability(){
    const engine=engines.find(x=>x.id===get("aiEngine").value);
    if(engine){
      const ready=engine.ready?"Runtime / โมเดลพร้อมตามการตรวจไฟล์":
        "ยังไม่พร้อม — "+(engine.assets_ready?"มีโมเดลแล้ว":"ต้องติดตั้งโมเดล")+
        (engine.runtime_ready?"":" และ Dependencies");
      get("aiEngineStatus").textContent=engine.id==="ollama"
        ?"Ollama · ตรวจสถานะและรายชื่อโมเดลจากที่อยู่ IP/Port ที่ตั้งค่าไว้ด้านล่าง"
        :engine.label+" · "+ready+" · "+engine.installation+
          (engine.id==="m2m100"?" · ใช้โมเดลใน models/ai/m2m100_418m ได้โดยไม่ต้องกดติดตั้ง":"");
      const prompt=engine.supports_prompt;
      get("aiPriority").disabled=!prompt;
      get("aiPrompt").disabled=!prompt;
      get("aiPromptHint").textContent=prompt
        ?"Priority Instructions สำคัญกว่า Custom Prompt; ข้อความ Live เป็นข้อมูลเท่านั้น"
        :"M2M100 ทดลอง: ไม่รองรับ Priority/Custom Prompt และความหมายของคำแปลอาจผิดได้ · ควรทดสอบก่อนใช้ Live";
    }
    get("aiOllamaControls").hidden=get("aiEngine").value!=="ollama";
    get("aiModel").disabled=false;
    get("aiModelLabel").textContent=get("aiEngine").value==="m2m100"
      ?"M2M100 Package (เลือกจากรายการที่ติดตั้งด้านล่าง)"
      :"ชื่อโมเดล Ollama ที่ติดตั้งไว้";
    get("aiOperation").querySelectorAll?.("option").forEach(o=>{
      if(o.value==="custom")o.disabled=Boolean(engine && !engine.supports_prompt);
    });
    if(get("aiEngine").value==="m2m100"&&get("aiOperation").value==="custom")
      get("aiOperation").value="translate";
    const operation=get("aiOperation").value;
    const unspecified=get("aiTarget").value==="unspecified";
    get("aiTarget").disabled=operation!=="translate";
    get("aiTranslationMode").disabled=operation!=="translate"||unspecified;
    get("aiAutoDetect").disabled=operation!=="translate"||unspecified;
    const languageNames={th:"ภาษาไทย",en:"ภาษาอังกฤษ",ja:"ภาษาญี่ปุ่น",zh:"ภาษาจีน",ko:"ภาษาเกาหลี"};
    get("aiLanguageHint").textContent=operation==="none"
      ?"ไม่แปล / ไม่เรียก AI; กฎก่อนและหลัง AI ยังคงทำงาน"
      :operation==="custom"
      ?"โหมด Custom: ให้ Priority Instructions และ Custom Prompt กำหนดงานและภาษาตอบเอง (ไม่บังคับภาษาปลายทาง)"
      :unspecified&&get("aiEngine").value==="m2m100"
      ?"M2M100 + ไม่ระบุภาษา: ข้ามการแปลโดยไม่เรียกโมเดล และยังใช้กฎก่อน/หลัง AI ตามปกติ"
      :unspecified
      ?"Ollama + ไม่ระบุภาษา: ต้องกำหนดภาษาใน Priority Instructions หรือ Custom Prompt · ไม่ใช้ตรวจจับอักษรเพื่อข้ามแปล"
      :"บังคับแปลเป็น"+(languageNames[get("aiTarget").value]||"ภาษาที่เลือก")+
        "ตาม Settings แม้ Prompt จะระบุภาษาอื่น; Prompt ใช้ควบคุมสำนวนและเงื่อนไขเพิ่มเติม";
  }
  async function requestJson(url,options){
    const response=await fetcher(url,options);
    const data=await response.json();
    if(!response.ok)throw Error(data.error||"การเรียก API ไม่สำเร็จ");
    return data;
  }
  async function loadPackages(){
    const result=await requestJson("/v1/ai/packages",{cache:"no-store"});
    packages=Array.isArray(result.packages)?result.packages:[];
    const list=get("aiPackageList");
    list.textContent="";
    const m2m=engines.find(e=>e.id==="m2m100");
    if(m2m?.assets_ready){
      const local=document.createElement("li");
      const title=document.createElement("span");
      title.textContent="M2M100 418M — พบไฟล์โมเดลที่ติดตั้งในเครื่อง · ทดลอง";
      local.appendChild(title);
      const select=document.createElement("button");
      select.type="button";select.textContent="เลือก M2M100 ในเครื่อง";
      select.addEventListener("click",()=>{
        get("aiEngine").value="m2m100";
        get("aiModel").value="";
        get("aiOperation").value="translate";
        updateAvailability();
        status("เลือก M2M100 local แล้ว · กดบันทึก AI Settings; ควรทดลองตรวจความหมายก่อน Live");
      });
      local.appendChild(select);
      list.appendChild(local);
    }
    if(!packages.length&&!m2m?.assets_ready){
      const line=document.createElement("li");
      line.textContent="ยังไม่พบ AI Model Package หรือโมเดล M2M100 ในโฟลเดอร์ที่รองรับ";
      list.appendChild(line);
    }
    for(const item of packages){
      const line=document.createElement("li");
      const title=document.createElement("span");
      title.textContent=item.title+" ("+item.key+") ";
      line.appendChild(title);
      const choose=document.createElement("button");
      choose.type="button";choose.textContent="เลือกใช้";
      choose.addEventListener("click",()=>{
        get("aiEngine").value="m2m100";
        get("aiModel").value=item.key;
        get("aiOperation").value="translate";
        updateAvailability();
        status("เลือกโมเดล "+item.key+" แล้ว · กดบันทึก AI Settings เพื่อใช้จริง");
      });
      line.appendChild(choose);
      list.appendChild(line);
    }
    get("aiPackageStatus").textContent="ติดตั้งแล้ว "+packages.length+" แพ็กเกจ";
    return packages;
  }
  get("aiPackageRefresh").addEventListener("click",()=>{
    loadPackages().catch(e=>get("aiPackageStatus").textContent=String(e.message||e));
  });
  function serverAddressNeedsSave(){
    return lastLoaded!==null &&
      get("aiOllamaBaseUrl").value.trim()!==JSON.parse(lastLoaded).ollama_base_url;
  }
  async function checkOllama(){
    if(get("aiEngine").value!=="ollama")return null;
    if(serverAddressNeedsSave()){
      get("aiOllamaStatus").textContent="กรุณาบันทึก AI Settings ก่อนตรวจ Ollama ที่อยู่ใหม่";
      return null;
    }
    const model=String(get("aiModel").value||"").trim();
    const response=await requestJson("/v1/ollama/models"+
      (model?"?model="+encodeURIComponent(model):""),{cache:"no-store"});
    const dataList=get("aiOllamaModels");dataList.textContent="";
    for(const entry of response.installed_models||[]){
      const option=document.createElement("option");
      option.value=entry.name;
      dataList.appendChild(option);
    }
    const state=response.selected;
    get("aiOllamaStatus").textContent=!response.server_running
      ?"Ollama ยังไม่ทำงานที่ "+(response.base_url||get("aiOllamaBaseUrl").value)
      :!model
      ?"Ollama พร้อม · พบโมเดลที่ติดตั้ง "+response.installed_models.length+
        " รายการ · พิมพ์ชื่อหรือเลือกจากรายการ"
      :state?.in_memory
      ?"โมเดล "+model+" ติดตั้งแล้วและอยู่ในหน่วยความจำ"
      :state?.installed
      ?"โมเดล "+model+" ติดตั้งแล้ว แต่ยังไม่ได้โหลดเข้าหน่วยความจำ"
      :"ไม่พบโมเดล "+model+" ใน Ollama ที่ทำงานอยู่ · ไม่มีการดาวน์โหลดอัตโนมัติ";
    return response;
  }
  get("aiOllamaCheck").addEventListener("click",()=>{
    checkOllama().catch(e=>get("aiOllamaStatus").textContent=
      "ตรวจสอบไม่สำเร็จ: "+String(e.message||e));
  });
  get("aiOllamaBaseUrl").addEventListener("input",()=>{
    if(serverAddressNeedsSave())
      get("aiOllamaStatus").textContent="เปลี่ยนที่อยู่ Ollama แล้ว · กดบันทึก AI Settings ก่อนตรวจสอบ";
  });
  get("aiModel").addEventListener("change",()=>{
    if(get("aiEngine").value==="ollama")
      checkOllama().catch(e=>get("aiOllamaStatus").textContent=String(e.message||e));
  });
  get("aiOllamaPreload").addEventListener("click",async()=>{
    const model=String(get("aiModel").value||"").trim();
    const minutes=Number(get("aiKeepAlive").value);
    const output=get("aiOllamaStatus");
    if(!model){output.textContent="กรุณาพิมพ์ชื่อโมเดลก่อน";return;}
    if(serverAddressNeedsSave()){
      output.textContent="กรุณาบันทึก AI Settings ก่อนโหลดโมเดลจาก Ollama ที่อยู่ใหม่";return;
    }
    const button=get("aiOllamaPreload");
    button.disabled=true;
    output.textContent="กำลังโหลดโมเดล "+model+" เข้าหน่วยความจำ (ไม่ดาวน์โหลดโมเดล)...";
    try{
      const result=await requestJson("/v1/ollama/preload",{
        method:"POST",
        headers:{"Content-Type":"application/json",
                 "X-VoxWeaveTTS-Intent":"preload-ollama-model"},
        body:JSON.stringify({model,keep_alive_minutes:minutes})
      });
      output.textContent=result.in_memory
        ?"โหลด "+model+" เข้าหน่วยความจำแล้ว · Keep Alive "+minutes+" นาที"
        :"ส่งคำสั่งเตรียมโมเดลแล้ว แต่ยังยืนยันสถานะในหน่วยความจำไม่ได้";
    }catch(e){
      output.textContent="โหลดโมเดลไม่ได้: "+String(e.message||e);
    }finally{button.disabled=false;}
  });

  async function load(){
    const [available,stored]=await Promise.all([
      requestJson("/v1/ai/engines",{cache:"no-store"}),
      requestJson("/v1/settings/ai",{cache:"no-store"})
    ]);
    engines=Array.isArray(available.engines)?available.engines:[];
    const select=get("aiEngine");
    select.textContent="";
    for(const info of engines){
      const option=document.createElement("option");
      option.value=info.id;
      option.textContent=info.label+(info.ready?"":" (ยังไม่พร้อม)");
      select.appendChild(option);
    }
    revision=stored.revision;
    lastLoaded=JSON.stringify(stored.settings);
    applyFields(stored.settings);
    // Read-only discovery. Do not pull, install or preload on page load.
    loadPackages().catch(e=>get("aiPackageStatus").textContent=String(e.message||e));
    if(get("aiEngine").value==="ollama")
      checkOllama().catch(e=>get("aiOllamaStatus").textContent=String(e.message||e));
    status(stored.saved?"โหลด AI Settings แล้ว":"ยังไม่มีไฟล์ตั้งค่า AI; เริ่มต้นปิด");
  }
  async function save(){
    if(revision===null)throw Error("ยังไม่โหลดการตั้งค่าจาก Backend");
    const value=readFields();
    if(value.enabled&&value.operation==="translate"&&value.engine==="ollama"&&
       value.target_language==="unspecified"&&
       !value.priority_instructions.trim()&&!value.custom_prompt.trim())
      throw Error("เมื่อเลือกไม่ระบุภาษา กรุณาเขียนภาษาที่ต้องการใน Priority Instructions หรือ Custom Prompt");
    const data=await requestJson("/v1/settings/ai",{
      method:"POST",
      headers:{"Content-Type":"application/json","X-VoxWeaveTTS-Intent":"save-ai-settings"},
      body:JSON.stringify({settings:value,expected_revision:revision})
    });
    revision=data.revision;
    lastLoaded=JSON.stringify(data.settings);
    status("บันทึกการตั้งค่า AI ส่วนกลางแล้ว; มีผลกับงานเสียงใหม่");
    if(value.engine==="ollama")
      checkOllama().catch(e=>get("aiOllamaStatus").textContent=String(e.message||e));
  }
  get("aiSave").addEventListener("click",()=>{
    save().catch(e=>status("บันทึกไม่ได้: "+String(e.message||e)));
  });
  get("aiReload").addEventListener("click",()=>{
    if(lastLoaded!==null&&JSON.stringify(readFields())!==lastLoaded&&
      !root.confirm("มีการแก้ไขที่ยังไม่บันทึก ต้องการโหลดค่าที่บันทึกจริงทับหรือไม่?"))return;
    load().catch(e=>status("โหลดไม่ได้: "+String(e.message||e)));
  });
  get("aiOperation").addEventListener("change",updateAvailability);
  get("aiTarget").addEventListener("change",updateAvailability);
  get("aiEngine").addEventListener("change",()=>{
    updateAvailability();
    if(get("aiEngine").value==="ollama")
      checkOllama().catch(e=>get("aiOllamaStatus").textContent=String(e.message||e));
  });
  get("aiTest").addEventListener("click",async()=>{
    const output=get("aiTestResult");output.textContent="กำลังประมวลผล...";
    try{
      const data=await requestJson("/v1/text/process",{
        method:"POST",headers:{"Content-Type":"application/json"},
        body:JSON.stringify({text:get("aiTestText").value,source:"manual"})
      });
      const detail=data.processing||{};
      output.textContent=JSON.stringify({
        original:detail.original_text,
        before_ai:detail.pre_ai_text,
        ai_result:detail.ai_result_text,
        after_ai:detail.post_ai_text,
        ai_status:detail.ai_status,
        warning:detail.warning||null,
        spoken_text:data.spoken_text,display_text:data.display_text
      },null,2);
    }catch(e){output.textContent="ไม่สำเร็จ: "+String(e.message||e);}
  });
  for(const id of Object.values(fields)){
    const element=get(id);
    element?.addEventListener?.("input",()=>{status("มีการแก้ไขที่ยังไม่ได้บันทึก");});
  }
  load().catch(e=>status("โหลดไม่ได้: "+String(e.message||e)));
  return {readFields,applyFields,updateAvailability,load,save};
}
root.VoxAISettings={attach};
if(typeof module!=="undefined"&&module.exports)module.exports={attach};
if(typeof document!=="undefined"&&document.getElementById("aiEnabled"))
  attach(document,root.fetch.bind(root));
})(typeof window==="undefined"?globalThis:window);