// Dependency-free regression smoke for browser Rules/Pronunciations controls.
// Run from repository root: node tests/json_settings_ui_smoke.cjs
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');

async function main(){
  const html=fs.readFileSync('web/index.html','utf8');
  const start=html.indexOf('const jsonLabels =');
  const endMarker='el("pronAdd").addEventListener("click", () => addConfigValue("pron", "pronMatch", "pronSpoken"));';
  const end=html.indexOf(endMarker,start)+endMarker.length;
  assert.ok(start>0 && end>start);
  const nodes=new Map();
  function el(id){
    if(!nodes.has(id))nodes.set(id,{
      value:'', disabled:true, files:[], textContent:'', listeners:{},
      classList:{toggle(){}},focus(){},
      addEventListener(type,fn){this.listeners[type]=fn;},
      click(){return this.listeners.click?.();},
    });
    return nodes.get(id);
  }
  el('rule').value='[{"match":"first","spoken":"A"}]';
  el('pron').value='{"เดิม":"เดิม"}';
  const server={
    rules:[{match:"ฮ่า",spoken:"ฮ่า ฮ่า"}],
    pronunciations:{"อมตะ":"อะ มะ ตะ"},
    revisions:{rules:"a".repeat(64),pronunciations:"b".repeat(64)},
    saved:{rules:true,pronunciations:true},
  };
  const posts=[];
  const downloads=[];
  let conflict=false;
  async function fetch(url,options){
    if(url==='/v1/settings/text' && (!options || options.method!=='POST')){
      return {ok:true,async json(){return JSON.parse(JSON.stringify(server));}};
    }
    if(url==='/v1/settings/text' && options?.method==='POST'){
      const submitted=JSON.parse(options.body);posts.push(submitted);
      if(conflict){
        return {ok:false,status:409,async json(){return {error:"settings conflict"};}};
      }
      server[submitted.section]=submitted.value;
      server.revisions[submitted.section]="c".repeat(64);
      return {ok:true,status:200,async json(){
        return {section:submitted.section,revision:"c".repeat(64),
                value:submitted.value,saved:true};
      }};
    }
    throw Error("unexpected URL: "+url);
  }
  const sandbox={
    el,fetch,TextDecoder,Blob,JSON,URL:{
      createObjectURL:()=> 'blob:test',revokeObjectURL:()=>{}
    },
    setTimeout:(fn)=>fn(),
    window:{confirm:()=>true},
    document:{body:{appendChild(){}},createElement:()=>({
      download:'',href:'',click(){downloads.push(this.download);},remove(){}
    })},
  };
  vm.createContext(sandbox);
  vm.runInContext(html.slice(start,end),sandbox);
  await new Promise(resolve=>setImmediate(resolve));
  assert.equal(JSON.parse(el('rule').value)[0].match,'ฮ่า','saved rules should load on start');
  assert.equal(JSON.parse(el('pron').value).อมตะ,'อะ มะ ตะ');
  assert.equal(el('ruleSave').disabled,false);
  el('pronMatch').value='“ฮ่า\\ฮ่า” 🧑🏽‍💻';
  el('pronSpoken').value='เสียง "พิเศษ" \nดัง';
  el('pronAdd').click();
  assert.equal(JSON.parse(el('pron').value)['“ฮ่า\\ฮ่า” 🧑🏽‍💻'],'เสียง "พิเศษ" \nดัง');
  await el('pronSave').click();
  assert.equal(posts.length,1);
  assert.equal(posts[0].section,'pronunciations');
  assert.equal(posts[0].expected_revision,'b'.repeat(64));
  assert.equal(server.pronunciations['“ฮ่า\\ฮ่า” 🧑🏽‍💻'],'เสียง "พิเศษ" \nดัง');
  // A stale tab must not erase an in-progress edit on HTTP 409.
  el('ruleMatch').value='new';el('ruleSpoken').value='voice';
  el('ruleAdd').click();
  const dirty=el('rule').value;
  conflict=true;
  await el('ruleSave').click();
  assert.equal(el('rule').value,dirty);
  assert.match(el('ruleJsonStatus').textContent,/แท็บอื่น/);
  conflict=false;
  // Re-import a file, but do not upload it to the persistent server.
  const oldPosts=posts.length;
  el('ruleImportFile').files=[{
    size:36,async arrayBuffer(){return Buffer.from('[{"match":"🎵","spoken":"ดนตรี"}]','utf8');}
  }];
  await el('ruleImportFile').listeners.change();
  assert.equal(JSON.parse(el('rule').value)[0].match,'🎵');
  assert.equal(posts.length,oldPosts);
  el('ruleFormat').click();
  el('ruleDownload').click();
  assert.deepEqual(downloads,['rules.json']);
  el('rule').value='{bad JSON}';
  el('ruleCheck').click();
  assert.equal(el('rule').value,'{bad JSON}','invalid editor text must be preserved');
  // Reload saved config must restore server state on demand.
  el('ruleReload').click();
  await new Promise(resolve=>setImmediate(resolve));
  assert.equal(JSON.parse(el('rule').value)[0].match,'ฮ่า');
  console.log('PASS: startup loading, Unicode quick entry, atomic save, stale-tab conflict, file import/download, reload, invalid-JSON preservation');
}
main().catch(error=>{console.error(error);process.exitCode=1;});