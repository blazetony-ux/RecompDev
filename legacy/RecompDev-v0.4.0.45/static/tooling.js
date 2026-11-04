'use strict';
const el=id=>document.getElementById(id);
const make=(tag,text)=>{const e=document.createElement(tag);e.textContent=String(text??'—');return e;};
function grid(id,headers,rows){const target=el(id);target.replaceChildren();const table=document.createElement('table');
 const thead=document.createElement('thead'),tr=document.createElement('tr');for(const h of headers)tr.append(make('th',h));thead.append(tr);table.append(thead);
 const tbody=document.createElement('tbody');for(const fields of rows){const row=document.createElement('tr');for(const v of fields)row.append(make('td',v));tbody.append(row);}table.append(tbody);target.append(table);
 if(!rows.length)target.append(make('p','No recorded jobs yet'));}
async function load(){try{const result=await fetch('/api/tooling-status',{cache:'no-store'});if(!result.ok)throw Error('Tooling API '+result.status);
 const data=(await result.json()).data;el('mission').textContent=data.mission;
 grid('tool-engines',['Engine','Integration','Role','Architectures'],Object.entries(data.capabilities.tools).map(([name,v])=>[name,v.integration,v.role,v.architectures.join(', ')||'—']));
 grid('tool-gates',['Gate','Current status'],Object.entries(data.release_validation));
 grid('tool-jobs',['Job','ISA','State','Engines','Parity'],data.recent_jobs.map(j=>[j.job,j.isa,j.status,j.engines.join(', '),j.native_parity]));
 grid('campaign-jobs',['Campaign','Attempt','ISA','State','Native qualified'],(data.recent_campaigns||[]).map(j=>[j.job,j.attempt,j.isa,j.status,'NO']));
 }catch(e){for(const id of ['tool-engines','tool-gates','tool-jobs','campaign-jobs'])el(id).textContent='Could not load tool status: '+e.message;}}
el('tool-refresh').addEventListener('click',load);load();

async function loadUnified(){try{const r=await fetch('/api/unified-evidence',{cache:'no-store'});if(!r.ok)throw Error('Evidence API '+r.status);
 const d=(await r.json()).data;const rows=[];for(const t of d.targets){if(t.pilots.length){for(const p of t.pilots){rows.push([t.display_name,t.system,p.install,p.native_status,p.translated_instructions,p.native_steps,p.event_integrity,p.reference_parity]);}}
 for(const c of t.integrated_campaigns||[]){rows.push([t.display_name,t.system,'integrated native campaign',c.status,'—',c.host?.native_steps??'—',c.event_integrity,'NOT_ESTABLISHED']);}
 else rows.push([t.display_name,t.system,'—',t.catalogue_native_status,0,0,'NOT_CAPTURED','NOT_TESTED']);}
 grid('unified-evidence',['Target','System','Install','Native status','Translated','Executed','Event integrity','Reference'],rows);
 }catch(e){el('unified-evidence').textContent='Could not load source-linked evidence: '+e.message;}}
el('unified-refresh').addEventListener('click',loadUnified);loadUnified();
