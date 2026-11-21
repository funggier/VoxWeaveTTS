"use strict";
const assert=require("node:assert/strict");
const emoji=require("../web/emoji_pronunciation.js");
const dict=emoji.parseEditor(
  "😂 = หัวเราะ\n❤️ = หัวใจ\n👍 = เยี่ยม\n👍🏽 = เยี่ยมมาก\n"+
  "🇹🇭 = ประเทศไทย\n👨‍👩‍👧‍👦 = ครอบครัว\n"+
  "GGWP = เก่งมาก\n:party_parrot: = นกเต้น\n:face-blue-smiling: = หน้ายิ้มสีฟ้า\n<:exact:123456789012345678> = ตรงตัว\n"
);
assert.equal(dict["😂"],"หัวเราะ");
assert.equal(emoji.replace("สวัสดี 😂❤️",dict),"สวัสดี หัวเราะ หัวใจ");
assert.equal(emoji.replace("👍🏽 และ 👍",dict),"เยี่ยมมาก และ เยี่ยม");
assert.equal(emoji.replace("🇹🇭 👨‍👩‍👧‍👦",dict),"ประเทศไทย ครอบครัว");
assert.equal(emoji.replace(" <:party_parrot:123456789012345678> ",dict),"นกเต้น");
assert.equal(emoji.replace(" <a:party_parrot:123456789012345678> ",dict),"นกเต้น");
assert.equal(emoji.replace("<:exact:123456789012345678>",dict),"ตรงตัว");
assert.equal(emoji.replace(":face-blue-smiling:",dict),"หน้ายิ้มสีฟ้า");
assert.equal(emoji.replace("GGWP!",dict),"เก่งมาก !");
assert.equal(emoji.replace("ขอบคุณ GGWP มาก ๆ",dict),"ขอบคุณ เก่งมาก มาก ๆ");
assert.equal(emoji.replace("GGWPXYZ and xGGWP @GGWP #GGWP",dict),
  "GGWPXYZ and xGGWP @GGWP #GGWP",
  "named emotes must match standalone tokens, not parts of words or mentions");
assert.equal(emoji.replace("<:GGWP:123456789012345678>",dict),
  "<:GGWP:123456789012345678>",
  "plain-name mapping must not rewrite part of custom emoji markup");
assert.equal(emoji.replace("<:GGWP:123456789012345678>",
  {...dict,":GGWP:":"จีจี"}),"จีจี",
  "an explicit shortcode mapping can match custom emoji markup");
assert.equal(emoji.replace("ไม่มีชื่อ 😶‍🌫️ :unknown:",dict),"ไม่มีชื่อ 😶‍🌫️ :unknown:");
assert.equal(emoji.replace("@เพื่อน 😂 ไป @ทุกคน",dict),"@เพื่อน หัวเราะ ไป @ทุกคน");
assert.equal(emoji.replace("😂",{"😂":"❤️","❤️":"หัวใจ"}),"❤️",
  "one-pass mapping must never cascade into another replacement");
assert.deepEqual(Object.entries(emoji.parseEditor(emoji.formatEditor(dict))),Object.entries(dict));
for(const invalid of ["@", "hello", "123", " "])
  assert.equal(emoji.validKey(invalid),false);
for(const invalid of ["😂 = \n","😂 หัวเราะ\n","😂 = ชอบ\n😂 = รัก",
   "hello = บางคำ","@ = คุณ","😂 = "+("น".repeat(61))])
  assert.throws(()=>emoji.parseEditor(invalid));
assert.throws(()=>emoji.parseEditor(
  Array.from({length:65},(_,i)=>"😂"+i+" = คำ").join("\n")),/64/);
assert.equal(emoji.validKey("GGWP"),true);
// YouTube-wide emotes are available to all viewers, unlike channel-only
// emoji; API and browser both expose their canonical :name: shortcodes.
const youtube=emoji.parseEditor(
  ":face-blue-smiling: = หน้ายิ้มสีฟ้า\n:yt: = ยูทูบ");
assert.equal(emoji.replace(":face-blue-smiling: :yt:",youtube),
  "หน้ายิ้มสีฟ้า ยูทูบ");
assert.equal(emoji.replace(":yt::yt::yt:",youtube),
  "ยูทูบ ยูทูบ ยูทูบ");

// Standard Unicode emoji from YouTube and Discord can differ by presentation
// VS16 and by modifiers. Exact variants always win; the generic mapping
// works for unlisted tones without leaking leftover variation selectors.
const shared=emoji.parseEditor(
  "❤ = หัวใจ\n👍 = เยี่ยม\n👍🏽 = เยี่ยมมาก\n👩‍💻 = โปรแกรมเมอร์");
assert.equal(emoji.replace("❤️ ❤ 👍 👍🏽 👍🏻 👩🏽‍💻",shared),
  "หัวใจ หัวใจ เยี่ยม เยี่ยมมาก เยี่ยม โปรแกรมเมอร์");
assert.equal(emoji.replace("👍🏼",{ "👍🏽":"ผิวเข้ม" }),"👍🏼",
  "specific tinted emoji must not become fallback for another tone");
assert.equal(emoji.replace("👍🏽",{ "👍":"ดี", "👍🏽":"ดีมาก" }),"ดีมาก");
assert.equal(emoji.replace("👍🏽",{ "👍":"ดี" }),"ดี");
assert.equal(emoji.replace("🥹🤣🇹🇭",{ "😂":"ขำ" }),"🥹🤣🇹🇭",
  "unconfigured Unicode graphemes are unchanged");
assert.equal(emoji.replace("😂 😂 😂",{ "😂":"หน้าหัวเราะ" }),
  "หน้าหัวเราะ หน้าหัวเราะ หน้าหัวเราะ",
  "user can apply phrase_run to post-emoji text");
assert.equal(emoji.replace("<:smile:123456789012345678>",{
  ":smile:":"ยิ้ม"}),"ยิ้ม");
assert.equal(emoji.replace("<a:smile:123456789012345678>",{
  ":smile:":"ยิ้ม"}),"ยิ้ม");
assert.equal(emoji.replace(":smile:",{":smile:":"ยิ้ม"}),"ยิ้ม");
// TikTok's platform-owned emoji names use brackets rather than colons.
// Allow both spellings as opt-in dictionary keys, preferring exact brackets.
assert.equal(emoji.validKey("[smile]"),true);
assert.equal(emoji.validKey("[laughwithtears]"),true);
const tikTok=emoji.parseEditor(
  "[smile] = ยิ้ม\n:cry: = ร้องไห้\n[laughwithtears] = หัวเราะ");
assert.equal(emoji.replace("[smile] [smile] [laughwithtears] [cry]",tikTok),
  "ยิ้ม ยิ้ม หัวเราะ ร้องไห้");
assert.equal(emoji.replace("[smile]",{"[smile]":"ยิ้มจริง",":smile:":"ยิ้มสำรอง"}),
  "ยิ้มจริง");
assert.equal(emoji.replace("[smile]",{":smile:":"ยิ้มสำรอง"}),"ยิ้มสำรอง");
assert.equal(emoji.replace("ข้อความ [unmapped] [🙂]",tikTok),"ข้อความ [unmapped] [🙂]");
assert.equal(emoji.replace("plain smile and smiling",tikTok),"plain smile and smiling",
  "never interpret a bare lowercase word as a TikTok emoji");
for(const invalid of ["[]","[a]","[smile here]","[123]","[test]extra"])
  assert.equal(emoji.validKey(invalid),false);
assert.equal(emoji.validKey("catJAM"),true);
assert.equal(emoji.parseEditor("").constructor,Object,
  "blank mapping editor is valid");
console.log("PASS: Unicode/ZWJ/flags/skin-tone and Discord emoji dictionary, safe one-pass replacement");
