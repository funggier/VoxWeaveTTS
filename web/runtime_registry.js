/* Runtime inventory and explicit orphan-cleanup actions.
 * No model data, paths or commands from the browser are used to select files.
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

async function refresh(){
  status.textContent="กำลังตรวจสอบ Runtime และจำนวนโมเดลที่ใช้งาน...";
  const response=await root.fetch("/v1/runtimes",{cache:"no-store"});
  const data=await response.json();
  if(!response.ok||!Array.isArray(data.runtimes))throw Error(data.error||"ไม่สามารถโหลด Runtime Registry");
  list.replaceChildren();
  for(const info of data.runtimes){
    const li=doc.createElement("li");
    const title=doc.createElement("strong");
    title.textContent=String(info.id)+" · "+String(info.kind);
    const details=doc.createElement("small");
    details.style.display="block";
    details.textContent=
      "สถานะ: "+(info.ready?"พร้อมใช้งาน":info.installed?"ยังไม่พร้อม / ติดตั้งไม่ครบ":"ยังไม่ได้ติดตั้ง")+
      " · ใช้ร่วมกับโมเดล "+Number(info.reference_count||0)+" รายการ";
    const models=doc.createElement("small");
    models.style.display="block";
    models.textContent=(Array.isArray(info.consumers)&&info.consumers.length)
      ?info.consumers.map(String).join(", "):"ไม่มีโมเดลที่ใช้งาน Runtime นี้";
    const path=doc.createElement("small");
    path.style.display="block";
    path.textContent="Runtime: "+String(info.relative_path||"-");
    li.append(title,details,models,path);
    if(info.installed){
      const remove=doc.createElement("button");
      remove.type="button";
      remove.style.marginLeft="8px";
      remove.textContent=info.can_uninstall?"ถอน Runtime ที่ไม่ใช้งาน":"กำลังใช้งานร่วมกัน · ถอนไม่ได้";
      remove.disabled=!info.can_uninstall;
      remove.addEventListener("click",async()=>{
        const name=String(info.id);
        if(!root.confirm("ถอน Runtime "+name+" ? ระบบจะลบเฉพาะ Environment นี้และไม่ลบข้อมูลโมเดล/Presets/Settings"))return;
        remove.disabled=true;
        try{
          const result=await root.fetch("/v1/runtimes/remove",{
            method:"POST",
            headers:{"Content-Type":"application/json",
                     "X-VoxWeaveTTS-Intent":"remove-unused-runtime"},
            body:JSON.stringify({id:info.id,
                                 expected_fingerprint:info.runtime_fingerprint,
                                 confirm_uninstall:true})
          });
          const data=await result.json();
          if(!result.ok||!data.removed)throw Error(data.error||"Runtime ยังไม่สามารถถอนได้");
          await refresh();
          status.textContent="ถอน Runtime "+name+" สำเร็จ; โมเดลและการตั้งค่าเดิมยังอยู่";
        }catch(error){
          status.textContent="ถอน Runtime ไม่สำเร็จ: "+String(error.message||error);
          remove.disabled=false;
        }
      });
      li.append(remove);
    }
    list.append(li);
  }
  if(!data.runtimes.length)status.textContent="ยังไม่มี Runtime ที่ลงทะเบียนไว้";
  else status.textContent="Runtime ทั้งหมด "+data.runtimes.length+
    " · พร้อมใช้ "+data.runtimes.filter(x=>x.ready).length+
    " · ถอนได้ "+data.runtimes.filter(x=>x.can_uninstall).length;
}
button.addEventListener("click",()=>refresh().catch(error=>{
  status.textContent=String(error.message||error);
}));
refresh().catch(error=>{status.textContent=String(error.message||error);});
root.VoxRuntimeRegistry={refresh};
})(typeof window!=="undefined"?window:this);
