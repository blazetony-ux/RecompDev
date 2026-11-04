'use strict';
const $=id=>document.getElementById(id);
const esc=v=>String(v??'—').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&quot;',"'":'&#39;'}[c]));
const number=v=>Number(v||0).toLocaleString('en-GB');
let names={},state={overview:null,query:'',target:'',seq:0};
async function api(route,query={}){const u=new URL('/api/'+route,location.href);for(const [k,v] of Object.entries(query))if(v)u.searchParams.set(k,v);const r=await fetch(u);const d=await r.json();if(!d.ok)throw Error(d.error||'Unable to read native evidence');return d.data}
function title(id){return names[id]?.display_name||names[id]?.target_id||id}
function rowTable(host,columns,rows){if(!rows.length){$(host).innerHTML='<div class="empty">No matching evidence recorded. This does not establish that the binary has no functions.</div>';return}
 $(host).innerHTML='<table><thead><tr>'+columns.map(c=>`<th>${esc(c[0])}</th>`).join('')+'</tr></thead><tbody>'+rows.map(r=>'<tr>'+columns.map(c=>`<td>${c[1](r)}</td>`).join('')+'</tr>').join('')+'</tbody></table>'}
const tag=(v,good)=>`<span class="pill ${good?'good':'warn'}">${esc(v||'Not recorded')}</span>`;
async function reload(){const seq=++state.seq;for(const id of ['native-results','batch-results','prepared-results','prepared-functions','progress-results'])$(id).innerHTML='<div class="empty">Loading…</div>';
 try{const o=await api('overview');if(seq!==state.seq)return;state.overview=o;names=Object.fromEntries(o.targets.map(t=>[t.target_id,t]));
 $('native-target').innerHTML='<option value="">All targets</option>'+o.targets.map(t=>`<option value="${esc(t.target_id)}">${esc(title(t.target_id))}</option>`).join('');$('native-target').value=state.target;
 const params={target:state.target,q:state.query,limit:2000};const [r,b,n,p]=await Promise.all([api('functions-v031',params),api('conversion',params),api('native-preparation'),api('native-progress')]);if(seq!==state.seq)return;
 const progress=(p.games||[]).filter(x=>(!state.target||x.target_id===state.target)&&(!state.query||String(x.display_name||'').toLowerCase().includes(state.query.toLowerCase())||String(x.native_status).toLowerCase().includes(state.query.toLowerCase())));
 $('progress-count').textContent=number(progress.filter(x=>x.native_status!=='NOT_RUN').length)+' run / '+number(progress.length)+' games';
 rowTable('progress-results',[['Game',x=>esc(x.display_name)],['System',x=>esc(x.system)],['Translated records',x=>x.native_status==='NOT_RUN'?'—':number(x.translated_instructions)],['Native steps (latest)',x=>x.native_status==='NOT_RUN'?'—':number(x.native_steps)],['Result',x=>tag(x.native_status,false)],['Parity',x=>esc(x.reference_parity)],['Blocker',x=>esc(x.blocker)]],progress);
 $('prepared-count').textContent=number(n.targets.length)+' prepared';
 rowTable('prepared-results', [['Game',x=>esc(x.display_name||x.path)],['System',x=>esc(x.system)],['CPU',x=>esc(x.cpu)],['Status',x=>tag(x.status,x.status==='CANDIDATES_RECOVERED_TRANSLATOR_NEEDED')],['Ghidra candidates',x=>number(x.candidate_count)],['Remaining work',x=>`<div class="table-long">${esc(x.blocker)}</div>`]],n.targets);
 const candidateIds=new Set(state.target?[state.target]:n.targets.map(x=>x.target_id));
 const prepc=n.candidates.filter(x=>candidateIds.has(x.target_id)&&(!state.query||x.name.toLowerCase().includes(state.query.toLowerCase())||x.entry_hex.toLowerCase().includes(state.query.toLowerCase())));
 $('prepared-functions-count').textContent=number(prepc.length)+' candidates';
 rowTable('prepared-functions',[['Target',x=>esc(x.target_id)],['Address',x=>`<span class="mono">${esc(x.entry_hex)}</span>`],['Name',x=>esc(x.name)],['Instructions',x=>number(x.instruction_count)],['Boundary',x=>esc(x.boundary_state)]],prepc.slice(0,400));
 $('native-count').textContent=number(r.jobs.length)+' attempts';
 rowTable('native-results', [['Game',x=>esc(title(x.target_id))],['Entry',x=>`<span class="mono">${esc(x.entry_hex)}</span>`],['Body',x=>tag(x.boundary_status,false)],['Corroboration',x=>esc(x.reconcile_status)],['C++ result',x=>tag(x.compile_status,String(x.compile_status||'').startsWith('COMPILED_'))],['Verification',x=>esc(x.verification_status)],['Blocker',x=>`<div class="table-long">${esc(x.blocker||'—')}</div>`]],r.jobs);
 $('batch-count').textContent=number(b.jobs.length)+' jobs';
 rowTable('batch-results',[['Game',x=>esc(title(x.target_id))],['Entry',x=>`<span class="mono">${esc(x.entry_hex)}</span>`],['Instructions',x=>number(x.instruction_count)],['Boundary',x=>esc(x.boundary_state)],['Stage',x=>tag(x.stage,x.stage==='COMPILED')],['Blocker',x=>`<div class="table-long">${esc(x.blocker||'—')}</div>`]],b.jobs);
 }catch(e){if(seq===state.seq){$('native-results').innerHTML=`<div class="empty">${esc(e.message)}</div>`;$('batch-results').innerHTML='';$('prepared-results').innerHTML=esc(e.message);$('prepared-functions').innerHTML='';$('progress-results').innerHTML='';}}
}
$('native-target').addEventListener('change',e=>{state.target=e.target.value;reload()});
let delay;$('native-search').addEventListener('input',e=>{state.query=e.target.value.trim();clearTimeout(delay);delay=setTimeout(reload,220)});
$('native-refresh').addEventListener('click',reload);reload();
