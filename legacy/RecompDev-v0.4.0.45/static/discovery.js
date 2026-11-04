'use strict';
const $=id=>document.getElementById(id);
const esc=v=>String(v??'—').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const number=v=>Number(v||0).toLocaleString('en-GB');
const nameOf=s=>String(s?.path||'').split(/[\\/]/).pop()||'Unnamed source';
const tidy=v=>String(v||'').replace(/\s+/g,' ').trim();
const sourceName=s=>{const label=tidy(s.display_name);return (!label||label.length<3||['XBOX360','BLUS30917'].includes(label))?nameOf(s):label;};
const pct=(a,b)=>b?Math.min(100,Math.max(0,100*Number(a||0)/b)):0;
const state={data:null,progress:null,source:'',query:'',status:'',taskQuery:'',confidence:'',seq:0};
async function api(){const r=await fetch('/api/discovery');const body=await r.json();if(!r.ok||!body.ok)throw Error(body.error||'Failed to read discovery evidence');return body.data}
function box(numberText,label,detail=''){return `<div class="metric"><div class="number">${esc(numberText)}</div><div class="label">${esc(label)}</div>${detail?`<div class="subnote">${esc(detail)}</div>`:''}</div>`;}
function populate(){const d=state.data,sources=d.sources||[],tasks=d.tasks||[],assets=d.assets||[];
 $('discovery-metrics').innerHTML=box(number(sources.length),'Source files inventoried')+box(number(assets.filter(x=>x.confidence==='STRUCTURALLY_VALIDATED').length),'Structurally validated assets')+box(number(assets.filter(x=>x.confidence!=='STRUCTURALLY_VALIDATED').length),'Unverified asset candidates')+box(number(tasks.filter(t=>t.status==='DONE').length)+' / '+number(tasks.length),'Discovery tasks completed');
 const srcs=sources.slice().sort((a,b)=>sourceName(a).localeCompare(sourceName(b)));
 $('source-filter').innerHTML='<option value="">All sources</option>'+srcs.map(s=>`<option value="${esc(s.source_id)}">${esc(sourceName(s))} · ${esc(s.system)}</option>`).join('');
 $('source-filter').value=state.source;
 $('prepare-source').innerHTML='<option value="">Choose an imported game</option>'+srcs.map(s=>`<option value="${esc(s.source_id)}">${esc(sourceName(s))} · ${esc(s.system)}</option>`).join('');
 if(prep.selected && srcs.some(s=>s.source_id===prep.selected))$('prepare-source').value=prep.selected;
 else if(state.source && srcs.some(s=>s.source_id===state.source))$('prepare-source').value=state.source;
 else if(!prep.selected && srcs.length===1)$('prepare-source').value=srcs[0].source_id;
 prep.selected=$('prepare-source').value;prepButtons();
 const statuses=[...new Set(tasks.map(t=>t.status))].sort();
 $('task-status').innerHTML='<option value="">All statuses</option>'+statuses.map(v=>`<option value="${esc(v)}">${esc(v.replace(/_/g,' '))}</option>`).join('');
 $('task-status').value=state.status;
 render();
}
function matchesSource(s){const q=state.query.toLowerCase();return (!state.source||s.source_id===state.source)&&(!q||[sourceName(s),nameOf(s),s.system,s.path,s.display_name].some(v=>String(v||'').toLowerCase().includes(q)))}
function render(){if(!state.data)return;
 const d=state.data,sources=d.sources||[],allAssets=d.assets||[],allTasks=d.tasks||[];
 const visible=sources.filter(matchesSource),idset=new Set(visible.map(s=>s.source_id));const sourceById=new Map(sources.map(s=>[s.source_id,s]));
 $('source-count').textContent=number(visible.length)+' of '+number(sources.length);
 if(!visible.length){$('source-results').innerHTML='<div class="empty">No sources match those filters.</div>'}
 else{$('source-results').innerHTML='<table><thead><tr><th>Source</th><th>System</th><th>Size</th><th>Structure</th><th>Validated</th><th>Candidate</th><th>Unknown</th><th>Coverage by bytes</th></tr></thead><tbody>'+visible.map(s=>{
   const c=s.coverage_bytes||{},n=s.bytes||0,validated=c.ASSET||0,structure=c.STRUCTURE||0,candidates=(c.ASSET_CANDIDATE||0)+(c.CODE_CANDIDATE||0),unknown=c.UNKNOWN||0;
   const knownPct=pct(validated+structure,n),candidatePct=pct(candidates,n),unknownPct=pct(unknown,n);
   return `<tr><td><span class="source-meta"><strong>${esc(sourceName(s))}</strong><small>${esc(nameOf(s))} · ${esc(s.source_hash_kind)}</small></span></td><td>${esc(s.system)}</td><td>${number(n)}</td><td>${pct(structure,n).toFixed(2)}%</td><td>${pct(validated,n).toFixed(2)}%</td><td>${candidatePct.toFixed(2)}%</td><td>${unknownPct.toFixed(2)}%</td><td><div class="coverage-meter" role="img" aria-label="${knownPct.toFixed(2)}% structural and validated, ${candidatePct.toFixed(2)}% candidate, ${unknownPct.toFixed(2)}% unknown"><span class="mapped" style="width:${knownPct}%"></span><span class="candidate" style="width:${candidatePct}%"></span><span class="unknown" style="width:${unknownPct}%"></span></div><div class="coverage-labels">${number(s.region_claims||0)} range claims</div></td></tr>`
 }).join('')+'</tbody></table>'}
 renderNativeProgress(visible);
 const assets=allAssets.filter(a=>idset.has(a.source_id)&&(!state.confidence||a.confidence===state.confidence));
 $('asset-count').textContent=number(assets.length)+' of '+number(allAssets.length);
 $('asset-results').innerHTML=assets.length?assets.map(a=>{
   const s=sourceById.get(a.source_id),type=a.confidence==='STRUCTURALLY_VALIDATED'?'Validated structure':'Unverified candidate';
   return `<article class="asset-preview"><img src="/api/discovery-preview/${encodeURIComponent(a.asset_id)}" alt="Generated preview of ${esc(a.format)}; ${esc(type)}" loading="lazy"><strong>${esc(a.format.replace(/_/g,' '))}</strong><div>${type==='Validated structure'?'<span class="pill good">Structurally validated</span>':'<span class="pill warn">Unverified interpretation</span>'}</div><span class="asset-source">${esc(s?sourceName(s):a.source_id)}</span><small>Offset 0x${Number(a.offset).toString(16).toUpperCase()} · ${number(a.length)} bytes</small></article>`;
 }).join(''):'<div class="empty">No assets match these filters. Mega Drive tile interpretations are not confirmed game artwork.</div>';
 const tq=state.taskQuery.toLowerCase();const tasks=allTasks.filter(t=>idset.has(t.source_id)&&(!state.status||t.status===state.status)&&(!tq||[t.kind,t.reason,t.status,t.subject].some(v=>String(v||'').toLowerCase().includes(tq))));
 $('task-count').textContent=number(tasks.length)+' of '+number(allTasks.length);
 $('task-results').innerHTML=tasks.length?'<table><thead><tr><th>Investigation</th><th>Source</th><th>Status</th><th>Priority</th><th>Attempts</th><th>Next action / evidence</th></tr></thead><tbody>'+tasks.map(t=>{
  const s=sourceById.get(t.source_id),status=t.status==='DONE'?'good':'warn';
  return `<tr><td><strong>${esc(t.kind.replace(/_/g,' '))}</strong>${t.subject?`<div class="subnote">${esc(t.subject)}</div>`:''}</td><td class="table-long">${esc(s?sourceName(s):t.source_id)}</td><td><span class="pill ${status}">${esc(t.status)}</span></td><td>${number(t.priority)}</td><td>${number(t.attempts)}</td><td class="table-long">${esc(t.reason||'Completed; no outstanding requirement recorded.')}</td></tr>`;
 }).join('')+'</tbody></table>':'<div class="empty">No tasks match these filters.</div>';
}
function renderNativeProgress(visible){
 const records=new Map((state.progress?.games||[]).map(x=>[x.source_id,x]));
 const rows=visible.map(s=>records.get(s.source_id)||{source_id:s.source_id,display_name:sourceName(s),preparation_status:'NOT_PREPARED',native_status:'NOT_RUN'});
 $('native-progress-count').textContent=number(rows.filter(x=>x.native_status!=='NOT_RUN').length)+' executed / '+number(rows.length)+' shown';
 $('native-progress-results').innerHTML=rows.length?'<table><thead><tr><th>Game</th><th>Prepared candidates</th><th>Translated records</th><th>Native steps (latest run)</th><th>Latest native status</th><th>Reference parity</th></tr></thead><tbody>'+rows.map(x=>{
 const active=x.native_status!=='NOT_RUN';return `<tr><td><strong>${esc(x.display_name)}</strong><div class="subnote">${esc(x.system||'')} · <a href="/execution">Native Execution</a> · <a href="/native">Native Recompilation</a></div></td><td>${number(x.candidate_count||0)}</td><td>${active?number(x.translated_instructions):'—'}</td><td>${active?number(x.native_steps):'—'}</td><td><span class="pill ${active?'warn':''}">${esc(x.native_status)}</span>${x.blocker?`<div class="subnote">${esc(x.blocker)}</div>`:''}</td><td>${esc(x.reference_parity||'NOT_TESTED')}</td></tr>`;
 }).join('')+'</tbody></table>':'<div class="empty">No imported games match the source selection.</div>';
}
async function reload(){const seq=++state.seq;$('source-results').innerHTML='<div class="empty">Loading discovery evidence…</div>';try{const [d,progress]=await Promise.all([api(),localGet('/api/native-progress')]);if(seq!==state.seq)return;state.data=d;state.progress=progress;populate()}catch(e){if(seq===state.seq){$('source-results').innerHTML=`<div class="empty">${esc(e.message)}</div>`;$('asset-results').innerHTML='';$('task-results').innerHTML='';}}}
$('source-filter').addEventListener('change',e=>{state.source=e.target.value;render()});
$('source-search').addEventListener('input',e=>{state.query=e.target.value.trim();render()});
$('asset-confidence').addEventListener('change',e=>{state.confidence=e.target.value;render()});
$('task-status').addEventListener('change',e=>{state.status=e.target.value;render()});
$('task-search').addEventListener('input',e=>{state.taskQuery=e.target.value.trim();render()});
$('discovery-refresh').addEventListener('click',reload);
reload();


// Local control panel. Browser sees directory NAMES only; the Python server owns paths.
const control={token:null,roots:[],folder:'',file:'',busy:false,lastJob:'',timer:null};
async function localGet(url){const response=await fetch(url,{cache:'no-store'}),data=await response.json();if(!data.ok)throw Error(data.error||'Request failed');return data.data;}
async function localPost(url,data){const response=await fetch(url,{method:'POST',headers:{'Content-Type':'application/json','X-RecompDev-Token':control.token},body:JSON.stringify(data)});const answer=await response.json();if(!answer.ok)throw Error(answer.error||'Discovery command failed');return answer.data;}
function controlMessage(txt,isError=false){$('job-state').textContent=txt;$('job-state').classList.toggle('control-error',isError)}
function updateButtons(){const active=control.busy;$('scan-selected').disabled=active||!control.file;$('scan-folder').disabled=active||!control.folder;$('scan-cancel').disabled=!active;$('rom-parent').disabled=active;}
async function browse(folder){const result=await localGet('/api/discovery-library?folder='+encodeURIComponent(folder));control.folder=result.folder;control.file='';
 $('rom-current').textContent=result.folder||'Select a ROM library';$('rom-parent').disabled=!result.parent;
 const dirs=(result.directories||[]).map(d=>`<button type="button" class="rom-entry dir" data-directory="${esc(d.path)}"><span class="rom-symbol">▸</span><span>${esc(d.name)}</span></button>`).join('');
 const files=(result.files||[]).map(f=>`<label class="rom-entry file"><input type="radio" name="rom-selected" value="${esc(f.path)}"><span>${esc(f.name)}</span><small>${number(f.bytes)} B</small></label>`).join('');
 $('rom-browser').innerHTML=dirs+files||'<div class="empty">No supported ROM files or subfolders here.</div>';
 if(result.truncated){$('rom-browser').insertAdjacentHTML('beforeend','<p class="muted">Only the first 1,000 entries are shown. Select a narrower folder.</p>')}
 $('rom-browser').querySelectorAll('[data-directory]').forEach(b=>b.addEventListener('click',()=>browse(b.dataset.directory).catch(e=>controlMessage(e.message,true))));
 $('rom-browser').querySelectorAll('input[type=radio]').forEach(r=>r.addEventListener('change',()=>{control.file=r.value;updateButtons()}));
 $('rom-parent').onclick=()=>browse(result.parent).catch(e=>controlMessage(e.message,true));updateButtons();}
function displayJob(job){
 control.busy=job.state==='RUNNING'||job.state==='STOP_REQUESTED';updateButtons();
 const labels={IDLE:'Discovery engine ready',RUNNING:'Discovery in progress',COMPLETE:'Discovery finished',FAILED:'Discovery failed',CANCELLED:'Discovery stopped',STOP_REQUESTED:'Stopping discovery…'};
 controlMessage(labels[job.state]||job.state,job.state==='FAILED');
 $('job-description').textContent=job.selection?`${job.selection} · budget ${job.budget} · ${job.state}`:(job.message||'');
 $('job-log').hidden=!job.log;$('job-log').textContent=job.log||'';
 if(job.id&&job.id!==control.lastJob){control.lastJob=job.id;}
 if(control.busy&&!control.timer)control.timer=setInterval(pollJob,1400);
 if(!control.busy&&control.timer){clearInterval(control.timer);control.timer=null;reload();}
}
async function pollJob(){try{const j=await localGet('/api/discovery-job');displayJob(j)}catch(e){controlMessage(e.message,true)}}
async function startDiscovery(mode){
 try{
 const path=mode==='file'?control.file:control.folder;if(!path)return;
 const budget=Number($('scan-budget').value),max_files=Number($('scan-max-files').value);
 if(!Number.isInteger(budget)||budget<1||budget>500||!Number.isInteger(max_files)||max_files<1||max_files>300){throw Error('Enter a budget of 1–500 and a file limit of 1–300.')}
 const result=await localPost('/api/discovery-run',{mode,path,budget,max_files,retry_failed:$('retry-failed').checked});displayJob(result);
 }catch(e){controlMessage(e.message,true)}
}
$('scan-selected').addEventListener('click',()=>startDiscovery('file'));
$('scan-folder').addEventListener('click',()=>startDiscovery('folder'));
$('scan-cancel').addEventListener('click',async()=>{try{displayJob(await localPost('/api/discovery-cancel',{}))}catch(e){controlMessage(e.message,true)}});
$('rom-root').addEventListener('change',e=>browse(e.target.value).catch(error=>controlMessage(error.message,true)));
(async()=>{try{
 const info=await localGet('/api/discovery-control');control.token=info.token;control.roots=info.roots;
 $('rom-root').innerHTML=control.roots.map(r=>`<option value="${esc(r)}">${esc(r)}</option>`).join('');
 if(!control.roots.length){$('rom-root').innerHTML='<option value="">No configured folders</option>';
  $('rom-browser').innerHTML='<div class="empty">No ROM folder is configured. Add a -RomRoot path to Run-Workbench.ps1 and restart.</div>'}
 else await browse(control.roots[0]);
 displayJob(info.job);
 }catch(e){controlMessage('Local discovery controls unavailable: '+e.message,true);$('rom-browser').innerHTML='<div class="empty">Discovery controls unavailable; the evidence viewer remains usable.</div>'}
})();

// Native-preparation controls are separate from the discovery job, but the server
// serialises DB-changing jobs. Source IDs, not arbitrary filesystem paths, are posted.
const prep={selected:'',busy:false,timer:null};
function prepButtons(){
 $('prepare-run').disabled=prep.busy||!prep.selected||control.busy;
 $('prepare-cancel').disabled=!prep.busy;
}
$('prepare-source').addEventListener('change',e=>{prep.selected=e.target.value;prepButtons()});
function showPrep(job){
 prep.busy=job.state==='RUNNING'||job.state==='STOP_REQUESTED';prepButtons();
 $('prepare-state').textContent={'IDLE':'Ready to prepare',RUNNING:'Preparing native target…',COMPLETE:'Preparation finished',FAILED:'Preparation failed',CANCELLED:'Preparation stopped',STOP_REQUESTED:'Stopping preparation…'}[job.state]||job.state;
 $('prepare-status').textContent=job.report_written?'Report saved to local evidence directory':(job.source_id||'');
 $('prepare-log').hidden=!job.log;$('prepare-log').textContent=job.log||'';
 if(prep.busy&&!prep.timer)prep.timer=setInterval(pollPrep,1400);
 if(!prep.busy&&prep.timer){clearInterval(prep.timer);prep.timer=null;reload();}
}
async function pollPrep(){try{showPrep(await localGet('/api/native-prepare-job'))}catch(e){$('prepare-state').textContent=e.message}}
$('prepare-run').addEventListener('click',async()=>{
 if(!prep.selected)return;
 try{showPrep(await localPost('/api/native-prepare-run',{source_id:prep.selected}))}
 catch(e){$('prepare-state').textContent=e.message}
});
$('prepare-cancel').addEventListener('click',async()=>{
 try{showPrep(await localPost('/api/native-prepare-cancel',{}))}
 catch(e){$('prepare-state').textContent=e.message}
});
pollPrep();
