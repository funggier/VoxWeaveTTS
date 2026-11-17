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
    model:"aiModel", operation:"aiOperation", custom_task:"aiCustomTask",
    source_language:"aiSourceLanguage", target_language:"aiTarget",
    translation_mode:"aiTranslationMode", auto_detect:"aiAutoDetect",
    translation_bypass_validation:"aiTranslationBypassValidation",
    priority_instructions:"aiPriority", custom_prompt:"aiPrompt",
    display_mode:"aiDisplay", timeout_seconds:"aiTimeout",
    keep_alive_minutes:"aiKeepAlive",
    fallback:"aiFallback", allow_context_files:"aiAllowFiles",
    context_files:"aiContextFiles",
    tool_calling_enabled:"aiToolsEnabled", tool_web_lookup:"aiWebLookup",
    tool_general_web_search:"aiGeneralWebSearch",
    tool_search_provider:"aiSearchProvider", tool_searxng_url:"aiSearxngUrl",
    tool_file_read:"aiToolFileRead", tool_max_calls:"aiToolMaxCalls"
  };
  const booleanKeys=new Set(["enabled","auto_detect","translation_bypass_validation","allow_context_files",
    "tool_calling_enabled","tool_web_lookup","tool_general_web_search","tool_file_read"]);
  let revision=null, lastLoaded=null, engines=[], packages=[];
  let credentials={ollama:false,tavily:false};
  let priorProvider=null;
  const status=text=>{get("aiSettingsStatus").textContent=text;};
  function readFields(){
    const data={};
    for(const [name,id] of Object.entries(fields)){
      const element=get(id);
      if(name==="context_files"){
        data[name]=String(element.value||"").split(/[,\r\n]+/).map(x=>x.trim()).filter(Boolean);
      }else if(name==="timeout_seconds"||name==="keep_alive_minutes"||name==="tool_max_calls"){
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
        ?"Priority Instructions สำคัญกว่า Custom Prompt; ข้อความ Live เป็นข้อมูลสำหรับวิเคราะห์/แปล/ตอบตาม Prompt เท่านั้น ไม่ใช่คำสั่งควบคุม AI"
        :"M2M100 ทดลอง: ไม่รองรับ Priority/Custom Prompt และความหมายของคำแปลอาจผิดได้ · ควรทดสอบก่อนใช้ Live";
    }
    get("aiOllamaControls").hidden=get("aiEngine").value!=="ollama";
    get("aiModel").disabled=false;
    const toolMode=get("aiEngine").value==="ollama"&&get("aiOperation").value==="custom";
    updateSearchProvider();
    get("aiToolHint").textContent=!toolMode
      ?"AI Tool Calling ใช้ได้เฉพาะ Ollama + โหมด AI ตาม Custom Prompt · เลือกโหมดนี้ก่อนเปิดใช้งาน"
      :get("aiToolsEnabled").checked
      ?"เปิดเฉพาะเครื่องมือที่ติ๊กอนุญาตไว้ · Wikipedia และ Ollama Web Search ส่งคำค้นออกอินเทอร์เน็ต · เครื่องมืออ่านไฟล์ใช้เฉพาะ Allowlist"
      :"AI Tool Calling ปิดอยู่ · ไม่มีการส่งคำค้นออกอินเทอร์เน็ตหรือเรียกใช้ไฟล์เป็นเครื่องมือ";
    get("aiModelLabel").textContent=get("aiEngine").value==="m2m100"
      ?"M2M100 Package (เลือกจากรายการที่ติดตั้งด้านล่าง)"
      :"ชื่อโมเดล Ollama ที่ติดตั้งไว้";
    get("aiOperation").querySelectorAll?.("option").forEach(o=>{
      if(o.value==="custom")o.disabled=Boolean(engine && !engine.supports_prompt);
    });
    if(get("aiEngine").value==="m2m100"&&get("aiOperation").value==="custom")
      get("aiOperation").value="translate";
    const operation=get("aiOperation").value;
    get("aiCustomTaskPanel").hidden=operation!=="custom";
    get("aiCustomTask").disabled=operation!=="custom";
    const unspecified=get("aiTarget").value==="unspecified";
    get("aiTarget").disabled=operation==="none";
    get("aiTranslationMode").disabled=operation!=="translate"||unspecified;
    get("aiAutoDetect").disabled=operation!=="translate"||unspecified;
    get("aiTranslationBypassValidation").disabled=operation!=="translate";
    const languageNames={th:"ภาษาไทย",en:"ภาษาอังกฤษ",ja:"ภาษาญี่ปุ่น",zh:"ภาษาจีน",ko:"ภาษาเกาหลี",es:"ภาษาสเปน",fr:"ภาษาฝรั่งเศส",hi:"ภาษาฮินดี",it:"ภาษาอิตาลี",pt:"ภาษาโปรตุเกส",de:"ภาษาเยอรมัน",ru:"ภาษารัสเซีย"};
    const customTasks={unspecified:"ไม่ระบุ",translate_only:"แปลอย่างเดียว",answer_questions:"ตอบคำถามแทนการแปล",translate_question_and_answer:"แปลคำถามและตอบต่อท้าย"};
    const selectedTask=customTasks[get("aiCustomTask").value]||customTasks.unspecified;
    get("aiLanguageHint").textContent=operation==="none"
      ?"ไม่แปล / ไม่เรียก AI; กฎก่อนและหลัง AI ยังคงทำงาน"
      :operation==="custom"
      ?unspecified
        ?"โหมดทำตามพรอมต์ · รูปแบบ: "+selectedTask+" · Priority Instructions สำคัญกว่า Custom Prompt · ไม่ระบุภาษาผลลัพธ์ · ข้อความแชทเป็นข้อมูลวิเคราะห์ ไม่ใช่คำสั่ง"
        :"โหมดทำตามพรอมต์: ผลลัพธ์ต้องเป็น"+(languageNames[get("aiTarget").value]||"ภาษาที่เลือก")+
          " · รูปแบบ: "+selectedTask+" · Priority Instructions สำคัญกว่า Custom Prompt · ข้อความแชทเป็นข้อมูลสำหรับวิเคราะห์ ไม่ใช่คำสั่ง"
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
    if(result.legacy_m2m){
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
      const remove=document.createElement("button");
      remove.type="button";remove.textContent="ถอน M2M100 รุ่นเดิม";
      remove.addEventListener("click",async()=>{
        if(!root.confirm("ถอนการติดตั้ง M2M100 จาก models/ai/m2m100_418m ?"))return;
        remove.disabled=true;
        try{
          const result=await requestJson("/v1/ai/packages/remove-legacy",{
            method:"POST",headers:{"Content-Type":"application/json",
              "X-VoxWeaveTTS-Intent":"remove-legacy-ai-model"},
            body:"{}"
          });
          status(result.removed?"ถอน M2M100 รุ่นเดิมแล้ว":"ไม่พบ M2M100 รุ่นเดิม");
          await loadPackages();
        }catch(e){status("ถอนโมเดลไม่สำเร็จ: "+String(e.message||e));}
        finally{remove.disabled=false;}
      });
      local.appendChild(remove);
      list.appendChild(local);
    }
    if(!packages.length&&!result.legacy_m2m){
      const line=document.createElement("li");
      line.textContent="ยังไม่พบ AI Model Package หรือโมเดล M2M100 ในโฟลเดอร์ที่รองรับ";
      list.appendChild(line);
    }
    for(const item of packages){
      const line=document.createElement("li");
      const title=document.createElement("span");
      const runtimeLabels={
        ready:"พร้อมใช้งาน",
        "adapter-not-approved":"ไม่มี Adapter ที่อนุมัติ",
        "runtime-not-installed":"ยังไม่ติดตั้ง Runtime",
        "runtime-recipe-pending":"รออนุมัติ Runtime",
        "platform-incompatible":"ระบบปฏิบัติการไม่รองรับ",
        "python-abi-mismatch":"Python Runtime ไม่ตรง"
      };
      title.textContent=item.title+" ("+item.key+") · "+
        (runtimeLabels[item.runtime_state]||item.runtime_state||"ต้องตรวจสอบ Runtime")+" ";
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
      const remove=document.createElement("button");
      remove.type="button";remove.textContent="ถอนการติดตั้ง";
      remove.addEventListener("click",async()=>{
        if(!root.confirm("ถอน AI Model Package "+item.title+" ("+item.key+") ?"))return;
        remove.disabled=true;
        try{
          const result=await requestJson("/v1/ai/packages/remove",{
            method:"POST",headers:{"Content-Type":"application/json",
              "X-VoxWeaveTTS-Intent":"remove-ai-model-package"},
            body:JSON.stringify({package_id:item.package_id,version:item.version})
          });
          if(!result.removed)throw Error("model not found");
          status("ถอนการติดตั้ง "+item.title+" สำเร็จ");
          await loadPackages();
        }catch(e){status("ถอนโมเดลไม่สำเร็จ: "+String(e.message||e));}
        finally{remove.disabled=false;}
      });
      line.appendChild(remove);
      list.appendChild(line);
    }
    get("aiPackageStatus").textContent="ติดตั้งแล้ว "+packages.length+" แพ็กเกจ";
    return packages;
  }
  get("aiPackageRefresh").addEventListener("click",()=>{
    loadPackages().catch(e=>get("aiPackageStatus").textContent=String(e.message||e));
  });
  get("aiPackageInstall").addEventListener("click",async()=>{
    const button=get("aiPackageInstall");button.disabled=true;
    get("aiPackageStatus").textContent="เลือกไฟล์ M2M100 .vwmodel · หลังเลือกต้องตรวจสอบข้อมูลเกือบ 2 GB อาจใช้เวลานาน กรุณารอจนระบบแจ้งผล";
    try{
      const installed=await requestJson("/v1/ai/packages/install-local",{
        method:"POST",headers:{"Content-Type":"application/json",
          "X-VoxWeaveTTS-Intent":"install-ai-model-package"},
        body:"{}"
      });
      if(installed.installed)status("ติดตั้ง AI Model Package สำเร็จ");
      const result=await requestJson("/v1/ai/engines",{cache:"no-store"});
      engines=Array.isArray(result.engines)?result.engines:[];
      await loadPackages();
      updateAvailability();
    }catch(e){status("ติดตั้ง AI Model Package ไม่สำเร็จ: "+String(e.message||e));}
    finally{button.disabled=false;}
  });
  async function loadM2MRuntimeStatus(){
    const line=get("aiM2MRuntimeStatus");
    if(!line)return;
    try{
      const result=await requestJson("/v1/ai/m2m-runtime",{cache:"no-store"});
      const state=result.runtime||{};
      const names={
        ready:"ติดตั้ง Runtime M2M100 แบบแยก Environment แล้ว · พร้อมใช้งาน",
        installing:"กำลังติดตั้ง PyTorch/Transformers ใน Environment แยก · ตรวจสถานะอีกครั้งได้",
        not_installed:"ยังไม่ได้ติดตั้ง Runtime M2M100 · ต้องมี uv และอินเทอร์เน็ตครั้งแรก",
        failed:"ติดตั้ง Runtime ไม่สำเร็จ · ดู logs/ai-runtime/install-m2m100.log"
      };
      line.textContent=names[state.state]||"ไม่ทราบสถานะ Runtime";
      if(state.error)line.textContent+=" · "+String(state.error);
      const install=get("aiM2MInstallRuntime");
      if(install)install.disabled=state.state==="installing";
      const resultEngines=await requestJson("/v1/ai/engines",{cache:"no-store"});
      engines=Array.isArray(resultEngines.engines)?resultEngines.engines:engines;
      updateAvailability();
    }catch(error){line.textContent="ตรวจสอบ Runtime ไม่สำเร็จ: "+String(error.message||error);}
  }
  get("aiM2MRuntimeCheck")?.addEventListener("click",()=>{
    loadM2MRuntimeStatus().catch(error=>status(String(error.message||error)));
  });
  get("aiM2MInstallRuntime")?.addEventListener("click",async()=>{
    const button=get("aiM2MInstallRuntime");
    button.disabled=true;
    get("aiM2MRuntimeStatus").textContent="กำลังเริ่มติดตั้ง M2M100 Runtime ใน Environment แยก...";
    try{
      await requestJson("/v1/ai/m2m-runtime/install",{
        method:"POST",
        headers:{"Content-Type":"application/json",
                 "X-VoxWeaveTTS-Intent":"install-m2m-runtime"},
        body:"{}"
      });
      await loadM2MRuntimeStatus();
    }catch(error){
      get("aiM2MRuntimeStatus").textContent="ติดตั้ง Runtime ไม่สำเร็จ: "+String(error.message||error);
    }finally{button.disabled=false;}
  });
  if(get("aiM2MRuntimeStatus"))loadM2MRuntimeStatus().catch(()=>{});
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

  const supportedProviders=new Set(["wikipedia","searxng","ollama","tavily"]);
  function updateSearchProvider(){
    const provider=get("aiSearchProvider").value;
    const needsKey=provider==="ollama"||provider==="tavily";
    get("aiSearxngFields").hidden=provider!=="searxng";
    get("aiSearchApiFields").hidden=!needsKey;
    if(priorProvider!==provider)get("aiSearchApiKey").value="";
    priorProvider=provider;
    const info={
      wikipedia:"Wikipedia ใช้ฟรีโดยไม่ต้องใช้ API Key; ค้นเฉพาะสารานุกรม",
      searxng:"SearXNG ต้องมีเซิร์ฟเวอร์ที่คุณดูแลและเปิด JSON API (/search?format=json)",
      ollama:"Ollama Web Search ใช้บัญชี/โควตา Ollama และส่งคำค้นไป ollama.com",
      tavily:"Tavily ใช้บัญชี/เครดิตตามผู้ให้บริการ และส่งคำค้นไป api.tavily.com"
    };
    get("aiSearchProviderStatus").textContent=info[provider]+(
      needsKey ? (credentials[provider]?" · มี API Key เก็บไว้แล้ว":" · ยังไม่พบ API Key ที่บันทึก") : ""
    );
  }
  async function refreshCredentials(){
    const response=await requestJson("/v1/ai/search-credentials",{cache:"no-store"});
    credentials=response.configured||{ollama:false,tavily:false};
    updateSearchProvider();
  }
  async function changeSearchKey(action){
    const provider=get("aiSearchProvider").value;
    if(!["ollama","tavily"].includes(provider))throw Error("ผู้ให้บริการนี้ไม่ต้องใช้ API Key");
    const input=get("aiSearchApiKey");
    const key=action==="save"?input.value.trim():"";
    if(action==="save"&&!key)throw Error("กรุณากรอก API Key");
    if(action==="clear"&&!root.confirm("ลบ API Key ที่บันทึกไว้สำหรับ "+provider+" ใช่หรือไม่?"))return;
    const result=await requestJson("/v1/ai/search-credentials",{
      method:"POST",
      headers:{"Content-Type":"application/json","X-VoxWeaveTTS-Intent":"save-ai-search-key"},
      body:JSON.stringify({provider,action,key})
    });
    input.value="";
    credentials=result.configured;
    updateSearchProvider();
    status(action==="save"?"บันทึก API Key แบบเข้ารหัสในเครื่องแล้ว":"ลบ API Key ที่บันทึกแล้ว");
  }
  get("aiSearchProvider").addEventListener("change",updateSearchProvider);
  get("aiSearchTest").addEventListener("click",async()=>{
    const display=get("aiSearchTestResult");
    const stored=lastLoaded?JSON.parse(lastLoaded):null;
    if(!stored||stored.tool_search_provider!==get("aiSearchProvider").value||
        stored.tool_searxng_url!==get("aiSearxngUrl").value){
      display.textContent="กรุณาบันทึก AI Settings ก่อนทดลอง Provider ที่เลือก";
      return;
    }
    const query=String(get("aiSearchTestQuery").value||"").trim();
    if(query.length<2||query.length>160){
      display.textContent="คำค้นต้องมี 2–160 ตัวอักษร";return;
    }
    const button=get("aiSearchTest");
    button.disabled=true;
    display.textContent="กำลังค้นจากผู้ให้บริการ...";
    try{
      const result=await requestJson("/v1/ai/search/test",{
        method:"POST",
        headers:{"Content-Type":"application/json","X-VoxWeaveTTS-Intent":"test-ai-search-provider"},
        body:JSON.stringify({query})
      });
      const hits=(result.results||[]).slice(0,3).map(x=>({
        title:x.title,snippet:x.snippet,source:x.source
      }));
      display.textContent=JSON.stringify({provider:result.provider,results:hits},null,2);
    }catch(e){display.textContent="ค้นหาไม่ได้: "+String(e.message||e);}
    finally{button.disabled=false;}
  });
  get("aiSearchKeySave").addEventListener("click",()=>{
    changeSearchKey("save").catch(e=>status("บันทึกคีย์ไม่ได้: "+String(e.message||e)));
  });
  get("aiSearchKeyClear").addEventListener("click",()=>{
    changeSearchKey("clear").catch(e=>status("ลบคีย์ไม่ได้: "+String(e.message||e)));
  });
  function searchProfile(){
    const data=readFields();
    return {format:"voxweavetts-ai-search-profile",version:1,
      provider:data.tool_search_provider,searxng_url:data.tool_searxng_url,
      enabled:data.tool_general_web_search};
  }
  function importSearchProfile(record){
    if(!record||typeof record!=="object"||Array.isArray(record)||
       Object.keys(record).sort().join(",")!=="enabled,format,provider,searxng_url,version"||
       record.format!=="voxweavetts-ai-search-profile"||record.version!==1||
       !supportedProviders.has(record.provider)||typeof record.enabled!=="boolean"||
       typeof record.searxng_url!=="string"||record.searxng_url.length>110||
       !/^http:\/\/(?:localhost|127\.0\.0\.1|10\.\d{1,3}\.\d{1,3}\.\d{1,3}|192\.168\.\d{1,3}\.\d{1,3}|172\.(?:1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3}):\d{1,5}$/.test(record.searxng_url))
       throw Error("โปรไฟล์ค้นหาไม่ถูกต้อง หรือที่อยู่เซิร์ฟเวอร์ไม่ใช่ Private LAN");
    get("aiSearchProvider").value=record.provider;
    get("aiSearxngUrl").value=record.searxng_url;
    get("aiGeneralWebSearch").checked=record.enabled;
    updateSearchProvider();
    status("นำเข้าโปรไฟล์ค้นหาแล้ว · ตรวจค่าก่อนกดบันทึก AI Settings · API Key ไม่ถูกนำเข้า");
  }
  get("aiSearchProfileExport").addEventListener("click",()=>{
    const content=JSON.stringify(searchProfile(),null,2)+"\n";
    const url=root.URL.createObjectURL(new Blob([content],{type:"application/json"}));
    const link=document.createElement("a");
    link.href=url;
    link.download="VoxWeaveTTS-AISearchProfile.json";
    link.click();
    root.URL.revokeObjectURL(url);
    status("ส่งออกโปรไฟล์ค้นหาโดยไม่รวม API Key แล้ว");
  });
  get("aiSearchProfileImport").addEventListener("change",async()=>{
    const file=get("aiSearchProfileImport").files?.[0];
    if(!file)return;
    try{
      if(file.size>4096)throw Error("ไฟล์โปรไฟล์ต้องไม่เกิน 4 KiB");
      importSearchProfile(JSON.parse(await file.text()));
    }catch(e){status("นำเข้าไม่ได้: "+String(e.message||e));}
    finally{get("aiSearchProfileImport").value="";}
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
    get("aiSearchApiKey").value="";
    applyFields(stored.settings);
    refreshCredentials().catch(e=>get("aiSearchProviderStatus").textContent="ตรวจ API Key ไม่ได้: "+String(e.message||e));
    // Read-only discovery. Do not pull, install or preload on page load.
    loadPackages().catch(e=>get("aiPackageStatus").textContent=String(e.message||e));
    if(get("aiEngine").value==="ollama")
      checkOllama().catch(e=>get("aiOllamaStatus").textContent=String(e.message||e));
    status(stored.saved?"โหลด AI Settings แล้ว":"ยังไม่มีไฟล์ตั้งค่า AI; เริ่มต้นปิด");
  }
  async function save(){
    if(revision===null)throw Error("ยังไม่โหลดการตั้งค่าจาก Backend");
    const value=readFields();
    if(value.tool_calling_enabled && (value.engine!=="ollama"||value.operation!=="custom"))
      throw Error("AI Tool Calling ต้องเลือก Ollama และโหมด Custom Prompt");
    if(value.tool_calling_enabled && !(value.tool_web_lookup || value.tool_general_web_search || value.tool_file_read))
      throw Error("กรุณาเลือกเครื่องมือที่ต้องการอนุญาตอย่างน้อยหนึ่งรายการ");
    if(value.tool_calling_enabled && value.tool_file_read &&
       (!value.allow_context_files||!value.context_files.length))
      throw Error("ต้องอนุญาตและระบุไฟล์อ้างอิงก่อนเปิดเครื่องมืออ่านไฟล์");
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
  get("aiToolsEnabled").addEventListener("change",updateAvailability);
  get("aiOperation").addEventListener("change",updateAvailability);
  get("aiCustomTask").addEventListener("change",updateAvailability);
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
  return {readFields,applyFields,updateAvailability,load,save,searchProfile,importSearchProfile};
}
root.VoxAISettings={attach};
if(typeof module!=="undefined"&&module.exports)module.exports={attach};
if(typeof document!=="undefined"&&document.getElementById("aiEnabled"))
  attach(document,root.fetch.bind(root));
})(typeof window==="undefined"?globalThis:window);