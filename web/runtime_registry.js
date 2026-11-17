/* Managed Runtime Pool: inspection, guarded cleanup and opt-in offline repair.
 * Browser input cannot specify dependencies, paths, URLs or executable code.
 */
(function(root){
"use strict";
const doc=root.document;
if(!doc)return;
const get=id=>doc.getElementById(id);
const button=get("runtimeRegistryRefresh");
const list=get("runtimeRegistryList");
const status=get("runtimeRegistryStatus");
if(!button||!list||!status)return;

const healthLabels={
  "ready":"พร้อมใช้งาน · ตรวจสอบตำแหน่งติดตั้งแล้ว",
  "legacy-unpinned":"พร้อมใช้งาน · Runtime เดิมยังไม่มีข้อมูลพาธสำหรับตรวจสอบการย้าย",
  "not-installed":"ยังไม่ได้ติดตั้ง",
  "incomplete":"การติดตั้งไม่สมบูรณ์",
  "relocated":"ตรวจพบการย้ายโฟลเดอร์โปรแกรม ต้องซ่อม Runtime",
  "recipe-changed":"Dependencies Recipe เปลี่ยน ต้องสร้าง Runtime ใหม่",
  "python-abi-mismatch":"เวอร์ชัน Python ไม่ตรงกับ Runtime ที่รองรับ",
  "base-python-missing":"ไม่พบ Python ต้นทางของ Virtual Environment",
  "unsafe-environment":"โฟลเดอร์ Runtime ไม่ปลอดภัยหรือถูกเปลี่ยนเส้นทาง"
};
const fetchJSON=async(path,options)=>{
  const response=await root.fetch(path,options);
  const data=await response.json();
  if(!response.ok)throw Error(data.error||"การดำเนินการ Runtime ไม่สำเร็จ");
  return data;
};
let pollQueued=false;
async function refresh(){
  status.textContent="กำลังตรวจสอบ Runtime...";
  const data=await fetchJSON("/v1/runtimes",{cache:"no-store"});
  if(!Array.isArray(data.runtimes))throw Error("ข้อมูล Runtime Registry ไม่ถูกต้อง");
  list.replaceChildren();
  let repairing=false;
  for(const info of data.runtimes){
    const li=doc.createElement("li");
    const title=doc.createElement("strong");
    title.textContent=String(info.id)+" · "+String(info.kind);
    const details=doc.createElement("small");
    details.style.display="block";
    const state=String(info.health_state||(info.ready?"ready":info.installed?"incomplete":"not-installed"));
    const repair=info.repair||{};
    const name=healthLabels[state]||state;
    details.textContent="สถานะ: "+name+
      " · โมเดลที่อ้างอิง "+Number(info.reference_count||0)+" รายการ";
    const models=doc.createElement("small");
    models.style.display="block";
    models.textContent=(Array.isArray(info.consumers)&&info.consumers.length)
      ?info.consumers.map(String).join(", "):"ไม่มีโมเดลอ้างอิง Runtime นี้";
    const path=doc.createElement("small");
    path.style.display="block";
    path.textContent="Runtime: "+String(info.relative_path||"-");
    li.append(title,details,models,path);
    if(info.installed){
      const remove=doc.createElement("button");
      remove.type="button";
      remove.style.marginLeft="8px";
      remove.textContent=info.can_uninstall?"ถอนการติดตั้ง Runtime":"ใช้งานอยู่ · ถอนไม่ได้";
      remove.disabled=!info.can_uninstall||repair.state==="repairing";
      remove.addEventListener("click",async()=>{
        const selected=String(info.id);
        if(!root.confirm("ถอนการติดตั้ง Runtime "+selected+" ?\nโปรแกรมจะลบเฉพาะ Virtual Environment ที่ไม่มีโมเดลอ้างอิง ไม่ลบโมเดล/Presets/Settings"))return;
        remove.disabled=true;
        try{
          const result=await fetchJSON("/v1/runtimes/remove",{
            method:"POST",
            headers:{"Content-Type":"application/json",
                     "X-VoxWeaveTTS-Intent":"remove-unused-runtime"},
            body:JSON.stringify({id:info.id,
                                 expected_fingerprint:info.runtime_fingerprint,
                                 confirm_uninstall:true})
          });
          if(!result.removed)throw Error("ไม่สามารถถอน Runtime ได้");
          await refresh();
          status.textContent="ถอน Runtime "+selected+" สำเร็จ โดยไม่แตะโมเดลหรือการตั้งค่า";
        }catch(error){
          status.textContent="ถอน Runtime ไม่สำเร็จ: "+String(error.message||error);
          remove.disabled=false;
        }
      });
      li.append(remove);
    }
    if(info.installed&&info.repair_required){
      const action=doc.createElement("button");
      action.type="button";
      action.style.marginLeft="8px";
      action.textContent=repair.state==="repairing"?"กำลังซ่อม Runtime...":"ซ่อมจาก uv cache (Offline)";
      action.disabled=repair.state==="repairing";
      action.addEventListener("click",async()=>{
        const selected=String(info.id);
        if(!root.confirm("ซ่อม Runtime "+selected+" แบบ Offline ?\nโปรแกรมจะสร้าง Virtual Environment ใหม่จาก Recipe และแคชภายในเครื่องเท่านั้น ไม่ดาวน์โหลดข้อมูล ถ้าซ่อมไม่สำเร็จจะคง Runtime เดิมไว้"))return;
        action.disabled=true;
        try{
          const result=await fetchJSON("/v1/runtimes/repair",{
            method:"POST",
            headers:{"Content-Type":"application/json",
                     "X-VoxWeaveTTS-Intent":"repair-runtime-offline"},
            body:JSON.stringify({id:info.id,
                                 expected_fingerprint:info.runtime_fingerprint,
                                 confirm_repair:true})
          });
          if(!result.repair||result.repair.state!=="repairing")
            throw Error("ไม่ได้เริ่มงานซ่อม Runtime");
          await refresh();
        }catch(error){
          status.textContent="เริ่มซ่อม Runtime ไม่สำเร็จ: "+String(error.message||error);
          action.disabled=false;
        }
      });
      li.append(action);
    }
    const wheelhouse=info.wheelhouse||{};
    const wheelMessage=doc.createElement("small");
    wheelMessage.style.display="block";
    const sourceState=String(wheelhouse.state||"not-published");
    wheelMessage.textContent=wheelhouse.ready_to_verify
      ?"Offline Wheelhouse: พบ "+Number(wheelhouse.wheels||0)+
        " wheels (รอตรวจ SHA-256 ก่อนติดตั้ง; สิทธิ์แจกจ่ายตรวจแยก)"
      :sourceState==="recipe-unsupported"
        ?"Offline Wheelhouse: Recipe ยังมีแหล่ง Git/URL ที่ไม่ได้แปลงเป็น Wheel ที่ตรวจสอบแล้ว"
      :"Offline Wheelhouse: ยังไม่มีชุดไฟล์ที่ตรงกับ Trusted Lock";
    li.append(wheelMessage);
    if(wheelhouse.ready_to_verify&&!info.ready){
      const install=doc.createElement("button");
      install.type="button";
      install.style.marginLeft="8px";
      install.textContent=repair.state==="repairing"
        ?"กำลังตรวจสอบหรือติดตั้ง Runtime..."
        :"ติดตั้ง/ซ่อมด้วย Verified Wheelhouse";
      install.disabled=repair.state==="repairing";
      install.addEventListener("click",async()=>{
        const name=String(info.id);
        if(!root.confirm("ติดตั้ง/ซ่อม Runtime "+name+" จาก Offline Wheelhouse ?\\n"+
          "โปรแกรมจะตรวจ SHA-256 ของ Wheel ทุกไฟล์เทียบ Trusted Lock ก่อนติดตั้ง "+
          "ไม่ใช้อินเทอร์เน็ต และจะคืน Runtime เดิมถ้าการติดตั้งไม่สำเร็จ"))return;
        install.disabled=true;
        try{
          const result=await fetchJSON("/v1/runtimes/install-verified",{
            method:"POST",
            headers:{"Content-Type":"application/json",
                     "X-VoxWeaveTTS-Intent":"install-verified-runtime"},
            body:JSON.stringify({id:info.id,
                                 expected_fingerprint:info.runtime_fingerprint,
                                 confirm_install:true})
          });
          if(!result.install||result.install.state!=="repairing")
            throw Error("ไม่สามารถเริ่มติดตั้ง Verified Runtime ได้");
          await refresh();
        }catch(error){
          status.textContent="ติดตั้ง Verified Runtime ไม่สำเร็จ: "+String(error.message||error);
          install.disabled=false;
        }
      });
      li.append(install);
    }
    if(repair.state==="repairing")repairing=true;
    if(repair.state==="failed"&&repair.error){
      const err=doc.createElement("small");
      err.style.display="block";
      err.textContent="ซ่อมไม่สำเร็จ: "+String(repair.error);
      li.append(err);
    }
    list.append(li);
  }
  const unhealthy=data.runtimes.filter(x=>x.repair_required).length;
  status.textContent="Runtime "+data.runtimes.length+" ตัว · ใช้งานได้ "+
    data.runtimes.filter(x=>x.ready).length+" · ต้องซ่อม "+unhealthy+
    (repairing?" · กำลังซ่อม โปรดตรวจสอบสถานะอีกครั้ง":"");
  if(repairing&&!pollQueued&&typeof root.setTimeout==="function"){
    pollQueued=true;
    root.setTimeout(()=>{
      pollQueued=false;
      refresh().catch(error=>{status.textContent=String(error.message||error);});
    },2500);
  }
}
button.addEventListener("click",()=>refresh().catch(error=>{
  status.textContent=String(error.message||error);
}));
refresh().catch(error=>{status.textContent=String(error.message||error);});
root.VoxRuntimeRegistry={refresh};
})(typeof window!=="undefined"?window:this);
