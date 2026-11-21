/* Source-local, opt-in emoji dictionary for LIVE TTS.
 * Exact Unicode sequences and Discord <:name:id>/<a:name:id> shortcodes.
 * Changes affect only text sent for synthesis, not the source message.
 */
(function(root){
"use strict";
const MAX_RULES=64, MAX_EDITOR=8192;
const DISCORD_SHORT=/^:[A-Za-z0-9_-]{2,48}:$/;
// TikTok native non-Unicode emoji use square-bracket names such as [smile].
// A user may also configure :smile: and it will match the same TikTok token.
const TIKTOK_SHORT=/^\[[A-Za-z][A-Za-z0-9_-]{1,47}\]$/;
const TIKTOK_TOKEN=/^\[([A-Za-z][A-Za-z0-9_-]{1,47})\]/;
const DISCORD_FULL=/^<a?:[A-Za-z0-9_]{2,32}:[0-9]{5,22}>$/;
const DISCORD_TOKEN=/^<a?:([A-Za-z0-9_]{2,32}):[0-9]{5,22}>/;
const EMOJI=/[\p{Extended_Pictographic}\p{Regional_Indicator}\u20E3]/u;
// Named emotes can arrive as plain labels (e.g. GGWP), not only Unicode
// or :shortcodes:. Require an uppercase character to avoid arbitrary
// lowercase prose being treated as an emote key.
const NAMED_EMOTE=/^(?=.{2,48}$)(?=.*[A-Z])[A-Za-z][A-Za-z0-9_-]*$/;
const WORD_EDGE=/[\p{L}\p{N}_:@#-]/u;
const VARIATION_SELECTORS=/[\uFE0E\uFE0F]/gu;
const SKIN_TONES=/[\u{1F3FB}-\u{1F3FF}]/gu;
function normalizeGlyph(glyph,tones=false){
  const plain=glyph.replace(VARIATION_SELECTORS,"");
  return tones?plain.replace(SKIN_TONES,""):plain;
}
function hasTokenBoundaries(text,start,length){
  const before=start>0?String.fromCodePoint(text.codePointAt(start-(
    start>=2&&/[\uDC00-\uDFFF]/.test(text[start-1])?2:1))):"";
  const after=start+length<text.length
    ?String.fromCodePoint(text.codePointAt(start+length)):"";
  return !WORD_EDGE.test(before)&&!WORD_EDGE.test(after);
}
function validKey(key){
  return typeof key==="string" && key.length>0 &&
    [...key].length<=48 && !/[\u0000-\u001f\u007f\s]/u.test(key) &&
    (DISCORD_SHORT.test(key)||DISCORD_FULL.test(key)||TIKTOK_SHORT.test(key)
      ||NAMED_EMOTE.test(key)||EMOJI.test(key));
}
function validate(dictionary){
  if(!dictionary || typeof dictionary!=="object"||Array.isArray(dictionary))
    throw Error("พจนานุกรมอีโมจิไม่ถูกต้อง");
  const entries=Object.entries(dictionary);
  if(entries.length>MAX_RULES)throw Error("กำหนดคำอ่านอีโมจิได้สูงสุด 64 รายการต่อโหมด");
  const result={};
  for(const [key,value] of entries){
    if(!validKey(key))throw Error("รายการไม่ใช่อีโมจิหรือชื่ออีโมจิ: "+key.slice(0,40));
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
    if(split<1)throw Error("แต่ละบรรทัดต้องเป็น อีโมจิหรือชื่ออีโมจิ = คำอ่าน");
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
  // Exact Unicode emoji mappings take precedence. Otherwise, standard
  // platform differences (emoji/text variation selectors and skin tones)
  // resolve to the base glyph without overwriting an explicit variant.
  const normalized=new Map(),base=new Map();
  for(const [key,value] of entries){
    if(!EMOJI.test(key))continue;
    const canonical=normalizeGlyph(key);
    if(!normalized.has(canonical))normalized.set(canonical,value);
    const neutral=normalizeGlyph(key,true);
    // Only a genuinely neutral configured emoji is a generic fallback.
    // A pink/medium-tone mapped hand must not take over other skin tones.
    if(neutral===canonical&&!base.has(neutral))base.set(neutral,value);
  }
  // A grapheme includes modifiers, flags, ZWJ family sequences and VS16.
  // Never replace just the first code point of an unmapped complex emoji.
  // Intl.Segmenter works in supported modern browsers and Node; without it
  // the original exact-key behavior is retained.
  const graphemes=new Map();
  if(typeof Intl!=="undefined"&&typeof Intl.Segmenter==="function"){
    for(const chunk of new Intl.Segmenter("und",{granularity:"grapheme"}).segment(text))
      if(EMOJI.test(chunk.segment))graphemes.set(chunk.index,chunk.segment);
  }
  let result="",i=0;
  while(i<text.length){
    let matched=null;
    // Treat Discord custom emoji markup as an atomic token. Never replace
    // an inner bare name/Unicode fragment if no full emoji key exists.
    const discord=DISCORD_TOKEN.exec(text.slice(i));
    if(discord){
      const exact=dictionary[discord[0]];
      const byName=dictionary[":"+discord[1]+":"];
      if(exact!==undefined || byName!==undefined)
        matched={length:discord[0].length,
                 value:exact!==undefined?exact:byName};
      else{
        result+=discord[0];
        i+=discord[0].length;
        continue;
      }
    }
    // For a TikTok [shortcode], prefer a specifically configured [name]
    // over the alternative :name: spelling. Never interpret bare words in
    // prose as an emote or alter a bracket token when no rule is configured.
    const tiktok=TIKTOK_TOKEN.exec(text.slice(i));
    if(!matched&&tiktok){
      const exact=dictionary[tiktok[0]];
      const colon=dictionary[":"+tiktok[1]+":"];
      if(exact!==undefined||colon!==undefined)
        matched={length:tiktok[0].length,value:exact!==undefined?exact:colon};
      else{
        result+=tiktok[0];
        i+=tiktok[0].length;
        continue;
      }
    }
    const grapheme=graphemes.get(i);
    if(!matched){
      for(const [key,value] of entries){
        if(!text.startsWith(key,i))continue;
        if(NAMED_EMOTE.test(key)&&!hasTokenBoundaries(text,i,key.length))
          continue;
        // An emoji key must not stop in the middle of a grapheme cluster:
        // e.g. plain 👍 cannot eat only the first code point of 👍🏽.
        if(grapheme&&EMOJI.test(key)&&key.length<grapheme.length)
          continue;
        matched={length:key.length,value};break;
      }
    }
    if(!matched&&grapheme){
      const canonical=normalizeGlyph(grapheme);
      const value=normalized.get(canonical)??base.get(normalizeGlyph(grapheme,true));
      if(value!==undefined)matched={length:grapheme.length,value};
    }
    if(matched){
      result+=" "+matched.value+" ";
      i+=matched.length;
    }else if(grapheme){
      result+=grapheme;i+=grapheme.length;
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
