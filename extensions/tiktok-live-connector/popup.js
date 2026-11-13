"use strict";
const $=id=>document.getElementById(id);
const render=msg=>$("status").textContent=msg;
function diagnosis(scan){
  if(!scan?.diagnostics)return "กำลังรอการตรวจ DOM จากแท็บ TikTok";
  const d=scan.diagnostics;
  return "DOM กล่องแชท: "+(d.list_found?"พบ":"ไม่พบ")
    +" | แถว: "+d.row_candidates
    +" | แยกคอมเมนต์: "+d.parsed_rows
    +" | ข้อความใหม่ล่าสุด: "+d.fresh_rows
    +" | Backend รับรอบล่าสุด: "+(scan.accepted||0)
    +(typeof d.tab_visible==="boolean"
      ?"\nแท็บ: "+(d.tab_visible?"แสดงอยู่":"เบื้องหลัง")
       +" | โฟกัส: "+(d.tab_focused?"อยู่ในแท็บ":"อยู่นอกแท็บ")
       +" | DOM แชทไม่เปลี่ยนมา: "+(d.chat_change_age_seconds||0)+" วินาที"
      :"");
}
function send(data){
  return new Promise((resolve,reject)=>{
    chrome.runtime.sendMessage(data,result=>{
      const issue=chrome.runtime.lastError;
      if(issue)reject(Error(issue.message));
      else if(!result?.ok)reject(Error(result?.error||"ไม่สามารถเชื่อมต่อได้"));
      else resolve(result);
    });
  });
}
async function refresh(){
  try{
    const result=await send({type:"vw-status"});
    render(result.connected?"เชื่อมต่อ VoxWeaveTTS แล้ว\n"+diagnosis(result.scan)
      :"ยังไม่เชื่อมต่อ");
  }catch(error){render("ตรวจสถานะไม่ได้: "+error.message);}
}
$("connect").addEventListener("click",async()=>{
  const port=Number($("port").value);
  const code=$("code").value.trim();
  if(!Number.isInteger(port)||port<1||port>65535||!code){render("กรุณากรอก Port และรหัสจับคู่");return;}
  $("connect").disabled=true;
  render("กำลังตรวจแท็บ TikTok LIVE และจับคู่กับโปรแกรม...");
  try{
    await send({type:"vw-start",port,code});
    $("code").value="";
    render("เชื่อมต่อสำเร็จ · รอข้อความคอมเมนต์ใหม่จากแท็บนี้");
  }catch(error){render("เชื่อมต่อไม่สำเร็จ: "+error.message);}
  finally{$("connect").disabled=false;}
});
$("stop").addEventListener("click",async()=>{
  try{await send({type:"vw-stop"});render("หยุดรับคอมเมนต์แล้ว");}
  catch(error){render("หยุดไม่สำเร็จ: "+error.message);}
});
refresh();
setInterval(refresh,3500);
