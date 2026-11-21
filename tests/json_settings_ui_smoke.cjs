// Dependency-free regression smoke for browser Rules/Pronunciations controls.
// Run from repository root: node tests/json_settings_ui_smoke.cjs
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const quickRule=require('../web/rule_quick_add.js');

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
      children:[],classList:{toggle(){}},focus(){},
      appendChild(child){this.children.push(child);return child;},
      addEventListener(type,fn){this.listeners[type]=fn;},
      click(){return this.listeners.click?.();},
    });
    return nodes.get(id);
  }
  el('ruleMatchMode').value='literal';
  el('ruleMode').value='replace';
  el('ruleSilenceMs').value='400';
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
    window:{confirm:()=>true,VoxRuleQuickAdd:quickRule},
    document:{body:{appendChild(){}},createElement:tag=>({
      tagName:tag.toUpperCase(),value:'',checked:false,children:[],
      download:'',href:'',textContent:'',listeners:{},
      appendChild(child){this.children.push(child);return child;},
      addEventListener(name,fn){this.listeners[name]=fn;},
      click(){if(tag==='a')downloads.push(this.download);},
      remove(){}
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
  el('rule').value='[]';
  el('ruleMatchMode').value='phrase_run';
  el('ruleMatchMode').listeners.change();
  assert.equal(el('ruleRepeatGroup').hidden,false);
  assert.equal(el('ruleMatch').maxLength,100);
  el('ruleMatch').value='หน้าหัวเราะ';
  el('ruleRepeatMin').value='3';
  el('ruleSpoken').value='';
  el('ruleMatch').listeners.input();
  assert.equal(JSON.parse(el('ruleQuickPreview').textContent).match_mode,'phrase_run');
  el('ruleAdd').click();
  assert.equal(JSON.parse(el('rule').value).length,1);
  assert.equal(JSON.parse(el('rule').value)[0].min_repeats,3);
  assert.equal('spoken' in JSON.parse(el('rule').value)[0],false,
    'blank spoken collapses repeated phrase to a single copy on backend');
  el('ruleMatchMode').value='repeat_run';
  el('ruleMatchMode').listeners.change();
  assert.equal(el('ruleRepeatGroup').hidden,false);
  assert.equal(el('ruleMatch').maxLength,16);
  el('ruleMatch').value='w';
  for(const [count,spoken] of [[3,'ฮ่าฮ่าฮ่า'],[5,'ขำมากมากฮ่าฮ่า'],[7,'ขำไม่หยุดฮ่าฮ่าฮ่า']]){
    el('ruleRepeatMin').value=String(count);
    el('ruleSpoken').value=spoken;
    el('ruleAdd').click();
    const added=JSON.parse(el('rule').value).at(-1);
    assert.equal(added.match_mode,'repeat_run');
    assert.equal(added.min_repeats,count);
    assert.equal(added.spoken,spoken);
  }
  assert.equal(JSON.parse(el('rule').value).length,4);
  el('ruleRepeatMin').value='1';
  el('ruleRepeatMin').listeners.input();
  assert.match(el('ruleQuickPreview').textContent,/2–1000/);
  el('ruleAdd').click();
  assert.equal(JSON.parse(el('rule').value).length,4,
    'bad minimum must not damage existing unsaved rules');
  el('ruleMatchMode').value='literal';
  el('ruleMatchMode').listeners.change();
  assert.equal(el('ruleRepeatGroup').hidden,true);
  console.log('PASS: JSON editor, Unicode, phrase collapse and 3/5/7 repeated character rule builder');
}
main().catch(error=>{console.error(error);process.exitCode=1;});