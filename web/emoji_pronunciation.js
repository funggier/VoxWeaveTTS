/* Source-local, opt-in emoji dictionary for LIVE TTS.
 * Exact Unicode sequences and Discord <:name:id>/<a:name:id> shortcodes.
 * Changes affect only text sent for synthesis, not the source message.
 */
(function(root){
"use strict";
const MAX_RULES=64, MAX_EDITOR=8192;
const DISCORD_SHORT=/^:[A-Za-z0-9_-]{2,48}:$/;
const DISCORD_FULL=/^<a?:[A-Za-z0-9_]{2,32}:[0-9]{5,22}>$/;
const DISCORD_TOKEN=/^<a?:([A-Za-z0-9_]{2,32}):[0-9]{5,22}>/;
const EMOJI=/[\p{Extended_Pictographic}\p{Regional_Indicator}\u20E3]/u;
function validKey(key){
  return typeof key==="string" && key.length>0 &&
    [...key].length<=48 && !/[\u0000-\u001f\u007f\s]/u.test(key) &&
    (DISCORD_SHORT.test(key)||DISCORD_FULL.test(key)||EMOJI.test(key));
}
function validate(dictionary){
  if(!dictionary || typeof dictionary!=="object"||Array.isArray(dictionary))
    throw Error("พจนานุกรมอีโมจิไม่ถูกต้อง");
  const entries=Object.entries(dictionary);
  if(entries.length>MAX_RULES)throw Error("กำหนดคำอ่านอีโมจิได้สูงสุด 64 รายการต่อโหมด");
  const result={};
  for(const [key,value] of entries){
    if(!validKey(key))throw Error("รายการไม่ใช่อีโมจิหรือรหัสอีโมจิ Discord: "+key.slice(0,40));
    if(typeof value!=="string" || !value.trim() || [...value].length>60 ||
       /[\u0000-\u001f\u007f]/.test(value))
      throw Error("คำอ่านต้องมีข้อความและยาวไม่เกิน 60 ตัวอักษร");
    result[key]=value.trim();
  }
  return result;
}
function parseEditor(source){
  if(typeof source!=="string"||source.length>MAX_EDITOR)
    throw Error("พจนานุกรมอีโมจิยาวเกิน 8,192 ตัวอักษร");
  const dictionary={};
  for(const raw of source.split(/\r?\n/)){
    const line=raw.trim();
    if(!line)continue;
    const split=line.indexOf("=");
    if(split<1)throw Error("แต่ละบรรทัดต้องเป็น อีโมจิ = คำอ่าน");
    const key=line.slice(0,split).trim();
    const value=line.slice(split+1).trim();
    if(Object.prototype.hasOwnProperty.call(dictionary,key))
      throw Error("มีอีโมจิซ้ำในรายการ: "+key);
    Object.defineProperty(dictionary,key,{value,writable:true,enumerable:true,configurable:true});
  }
  return validate(dictionary);
}
function formatEditor(dictionary){
  return Object.entries(validate(dictionary)).map(([key,value])=>key+" = "+value).join("\n");
}
function replace(text,dictionary){
  if(typeof text!=="string"||!dictionary||!Object.keys(dictionary).length)return text;
  // Work on the ORIGINAL string, not serial replaceAll (avoids cascades).
  const entries=Object.entries(dictionary).sort((a,b)=>b[0].length-a[0].length);
  let result="",i=0;
  while(i<text.length){
    let matched=null;
    for(const [key,value] of entries){
      if(text.startsWith(key,i)){matched={length:key.length,value};break;}
    }
    // Discord custom emojis contain a volatile ID. An optional :name:
    // dictionary entry handles both static and animated versions.
    if(!matched){
      const discord=DISCORD_TOKEN.exec(text.slice(i));
      if(discord){
        const name=":"+discord[1]+":";
        if(Object.prototype.hasOwnProperty.call(dictionary,name))
          matched={length:discord[0].length,value:dictionary[name]};
      }
    }
    if(matched){
      result+=" "+matched.value+" ";
      i+=matched.length;
    }else{
      const cp=text.codePointAt(i);
      result+=String.fromCodePoint(cp);
      i+=cp>65535?2:1;
    }
  }
  return result.replace(/\s+/gu," ").trim();
}
const api={validate,parseEditor,formatEditor,replace,validKey,MAX_RULES};
root.VoxEmojiPronunciation=api;
if(typeof module!=="undefined"&&module.exports)module.exports=api;
})(typeof window==="undefined"?globalThis:window);
