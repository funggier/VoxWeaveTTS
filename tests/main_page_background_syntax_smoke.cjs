// Compile every inline JS block in the real HTML; no browser needed.
const assert=require("node:assert/strict");
const fs=require("node:fs");
const vm=require("node:vm");
const html=fs.readFileSync("web/index.html","utf8");
const scripts=[...html.matchAll(/<script\b([^>]*)>([\s\S]*?)<\/script>/gi)];
let inline=0;
for(const [,attrs,source] of scripts){
  if(/\bsrc\s*=/.test(attrs))continue;
  if(!source.trim())continue;
  new vm.Script(source,{filename:"web/index.html [inline script "+(++inline)+"]"});
}
assert.ok(inline>=1);
assert.match(html,/\/v1\/jobs\/".*"\?wait=1"/);
assert.doesNotMatch(html,/jobPollTimer\s*=\s*setInterval/);
console.log("PASS: "+inline+" real HTML inline script(s) compile; reader, studio and queue use server-side job wait");
