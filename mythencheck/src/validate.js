const fs=require('fs'); const vm=require('vm');
const ctx={}; vm.createContext(ctx);
for (const f of ['data1.js','data2.js','data3.js']) vm.runInContext(fs.readFileSync(f,'utf8'),ctx,{filename:f});
const T=[...ctx.TOPICS_1,...ctx.TOPICS_2,...ctx.TOPICS_3];
const cats=new Set(['natur','gesundheit','geschichte','staat','maechte']);
const reserved=/^(settings|sidebar|customize|upgrade|downloads|comment-.*)$/;
let err=0; const ids=new Set(); let nq=0, ns=0, nf=0;
const bad=(m)=>{err++; console.log('ERR',m)};
for (const t of T){
  if(ids.has(t.id)) bad('dup id '+t.id); ids.add(t.id);
  if(!/^[a-z0-9-]+$/.test(t.id)||reserved.test(t.id)) bad('id '+t.id);
  if(!cats.has(t.cat)) bad('cat '+t.id);
  for (const k of ['title','short','claim']) if(typeof t[k]!=='string'||t[k].length<10) bad(k+' '+t.id);
  if(!Array.isArray(t.origin)||!t.origin.length) bad('origin '+t.id);
  if(!Array.isArray(t.facts)||t.facts.length<3) bad('facts '+t.id);
  t.facts.forEach(f=>{ if(f.length!==2||!f[0]||!f[1]) bad('fact shape '+t.id)}); nf+=t.facts.length;
  if(!Array.isArray(t.sources)||t.sources.length<3) bad('sources '+t.id);
  t.sources.forEach(s=>{ ns++; if(s.length!==3) bad('src shape '+t.id); if(s[2] && !/^https:\/\/[^\s"]+$/.test(s[2])) bad('url '+t.id+' '+s[2]); });
  if(!Array.isArray(t.quiz)||t.quiz.length!==3) bad('quiz count '+t.id);
  t.quiz.forEach(q=>{ nq++; if(q.length!==3||q[1].length!==4) bad('quiz shape '+t.id+' '+q[0]); if(new Set(q[1]).size!==4) bad('dup option '+t.id); if(!q[2]) bad('no expl '+t.id); });
  const all=JSON.stringify(t);
  if(/[–—]/.test(all)) bad('dash in '+t.id+': '+all.match(/.{30}[–—].{30}/)?.[0]);
  if(/\\"/.test(all)) bad('ascii quote in '+t.id);
}
console.log({topics:T.length, questions:nq, sources:ns, facts:nf, errors:err});
const per={}; T.forEach(t=>per[t.cat]=(per[t.cat]||0)+1); console.log(per);
// duplicate URLs across topics (just info)
