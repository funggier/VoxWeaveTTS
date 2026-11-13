"use strict";
const assert=require("node:assert/strict");
const emoji=require("../web/emoji_pronunciation.js");
const dict=emoji.parseEditor(
  "😂 = หัวเราะ\n❤️ = หัวใจ\n👍 = เยี่ยม\n👍🏽 = เยี่ยมมาก\n"+
  "🇹🇭 = ประเทศไทย\n👨‍👩‍👧‍👦 = ครอบครัว\n"+
  ":party_parrot: = นกเต้น\n:face-blue-smiling: = หน้ายิ้มสีฟ้า\n<:exact:123456789012345678> = ตรงตัว\n"
);
assert.equal(dict["😂"],"หัวเราะ");
assert.equal(emoji.replace("สวัสดี 😂❤️",dict),"สวัสดี หัวเราะ หัวใจ");
assert.equal(emoji.replace("👍🏽 และ 👍",dict),"เยี่ยมมาก และ เยี่ยม");
assert.equal(emoji.replace("🇹🇭 👨‍👩‍👧‍👦",dict),"ประเทศไทย ครอบครัว");
assert.equal(emoji.replace(" <:party_parrot:123456789012345678> ",dict),"นกเต้น");
assert.equal(emoji.replace(" <a:party_parrot:123456789012345678> ",dict),"นกเต้น");
assert.equal(emoji.replace("<:exact:123456789012345678>",dict),"ตรงตัว");
assert.equal(emoji.replace(":face-blue-smiling:",dict),"หน้ายิ้มสีฟ้า");
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
assert.equal(emoji.parseEditor("").constructor,Object,
  "blank mapping editor is valid");
console.log("PASS: Unicode/ZWJ/flags/skin-tone and Discord emoji dictionary, safe one-pass replacement");
