'use strict';
const $=x=>document.getElementById(x),esc=x=>String(x??'—').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
let token='',active=false,timer=null,supportedNativeSystems=new Set();
async function api(name,options){const r=await fetch('/api/'+name,{cache:'no-store',...options});const d=await r.json();if(!r.ok||!d.ok)throw Error(d.error||'Workbench request failed');return d.data;}
async function refreshEvidence(){
 try{const [prepared,evidence]=await Promise.all([api('native-preparation'),api('native-pilots')]);
 const chosen=$('pilot-source').value;
 const sources=prepared.targets.filter(x=>supportedNativeSystems.has(x.system)&&x.target_id);
 $('pilot-source').innerHTML='<option value="">Select a game with native execution support…</option>'+sources.map(x=>`<option value="${esc(x.source_id)}">${esc(x.display_name||x.path)} (${esc(x.candidate_count)} candidates)</option>`).join('');
 if(sources.some(x=>x.source_id===chosen))$('pilot-source').value=chosen;
 else if(sources.length===1)$('pilot-source').value=sources[0].source_id;
 $('pilot-count').textContent=evidence.jobs.length+' attempts';
 $('pilot-results').innerHTML=evidence.jobs.length?'<table><thead><tr><th>Game</th><th>Status</th><th>Translated instructions</th><th>Native steps</th><th>Stopping condition</th></tr></thead><tbody>'+evidence.jobs.map(x=>`<tr><td>${esc(x.display_name)}</td><td><span class="pill warn">${esc(x.status)}</span></td><td>${Number(x.translated_instructions).toLocaleString()}</td><td>${Number(x.native_steps).toLocaleString()}</td><td class="table-long">${esc(x.blocker)}</td></tr>`).join('')+'</tbody></table>':'<div class="empty">No native execution attempts recorded yet.</div>';
 }catch(e){$('pilot-message').textContent=e.message;}
}
async function poll(){
 try{const j=await api('native-pilot-job');active=j.state==='RUNNING'||j.state==='STOP_REQUESTED';
 $('pilot-log').textContent=j.log||j.message||'No worker output yet';
 const attempts=j.attempts||[];
 $('pilot-timeline').innerHTML=attempts.length?'<table><thead><tr><th>Try</th><th>Native steps</th><th>Logical PC</th><th>ROM offset</th><th>Result</th><th>Recovery</th></tr></thead><tbody>'+attempts.map(a=>`<tr><td>${Number(a.attempt)+1}</td><td>${Number(a.native_steps).toLocaleString()}</td><td>0x${Number(a.pc).toString(16).toUpperCase()}</td><td>0x${Number(a.physical_offset||0).toString(16).toUpperCase()}</td><td>${esc(a.status)}</td><td>${esc(a.recovery_blocker||a.recovery||'—')+(a.recovery_diagnostic?'<div class=\"muted\">Byte classification: '+esc(a.recovery_diagnostic.classification||'unknown')+'; exact Ghidra: '+esc(a.recovery_diagnostic.ghidra_exact_status||'not run')+'</div>':'')}</td></tr>`).join('')+'</tbody></table>':'<div class="empty">Recovery attempts will appear when the job finishes.</div>';
 const tr=j.trace||{};
 const graph=j.dependency_graph||{};const parity=j.reference_check||{};const divergence=j.divergence_diagnosis||{};
 $('pilot-verification').textContent='Source-attested dependency graph: '+Number(graph.authenticated_instructions||0).toLocaleString()+' instructions, '+Number(graph.unresolved_edges||0).toLocaleString()+' unresolved edges. Independent reference: '+esc(parity.status||j.reference_parity||'NOT_TESTED')+(divergence.classification?'; divergence focus: '+esc(divergence.classification):'')+'. Full ordered event stream: '+(tr.event_stream_complete?'HASH-VERIFIED AT CAPTURE':'unavailable/incomplete')+'; chunks '+Number(tr.event_stream_chunks||0)+'.';
 const hs=Array.isArray(tr.hotspots)?tr.hotspots:[];
 const checkpoints=Array.isArray(tr.checkpoints)?tr.checkpoints:[];
 const summary=hs.length?`<p><strong>Top executed ROM offsets:</strong> ${hs.slice(0,5).map(h=>`0x${Number(h.physical_offset).toString(16).toUpperCase()} (${Number(h.count).toLocaleString()} hits)`).join(' · ')}</p>`:'';
 const visual=tr.native_steps!==undefined?`<p><strong>Hardware:</strong> VDP control ${Number(tr.vdp_control_writes||0).toLocaleString()}, VDP data ${Number(tr.vdp_data_writes||0).toLocaleString()}, PSG ${Number(tr.psg_writes||0).toLocaleString()} · First VDP event at step ${Number(tr.first_vdp_port_step||0)||'not reached'} · First PSG event at step ${Number(tr.first_psg_step||0)||'not reached'}</p>`:'';
 const watched=Array.isArray(tr.watched_memory)?tr.watched_memory:[];
 const watchText=watched.length?'<p><strong>Configured RAM watches:</strong> '+watched.map(w=>'0x'+Number(w.address).toString(16).toUpperCase()+': '+Number(w.reads)+' reads, '+Number(w.writes)+' writes ('+Number(w.nonzero_writes)+' nonzero); last writer PC 0x'+Number(w.last_writer_pc).toString(16).toUpperCase()).join(' · ')+'</p>':'';
 const frame=tr.native_steps!==undefined?`<p><strong>Approximate frame clock:</strong> ${Number(tr.frames||0)} frame ticks, ${Number(tr.vblank_events||0)} VBlank events, ${Number(tr.maskable_interrupts||0)} delivered interrupts, ${Number(tr.halt_wait_ticks||0)} HALT idle ticks.</p><p><strong>Graphics state:</strong> ${Number(tr.vram_nonzero_bytes||0)} nonzero VRAM bytes, ${Number(tr.cram_nonzero_bytes||0)} CRAM bytes, VDP registers: ${esc(JSON.stringify(tr.vdp_registers||[]))}. Not reference verified.</p>`:'';
 const divergenceText=divergence.suggested_investigation?'<p><strong>First divergence:</strong> '+esc(divergence.classification||'investigate')+' at event '+(Number((divergence.first_event_divergence||{}).event_index)||0).toLocaleString()+'. '+esc(divergence.suggested_investigation)+'</p>':'';
 const budgets=Array.isArray(j.budget_history)?j.budget_history:[];const budgetText=budgets.length?'<p><strong>Bounded adaptive replays:</strong> '+budgets.map(b=>Number(b.step_budget).toLocaleString()+' steps ('+esc(b.status)+', '+(b.observable_state_change?'observed state change':'no observed progress')+')').join(' → ')+'</p>':'';
 const cp=checkpoints.length?'<table><thead><tr><th>Step</th><th>PC</th><th>AF</th><th>BC</th><th>DE</th><th>HL</th><th>SP</th></tr></thead><tbody>'+checkpoints.map(c=>`<tr><td>${Number(c.step).toLocaleString()}</td><td>0x${Number(c.pc).toString(16).toUpperCase()}</td><td>0x${Number(c.af).toString(16).toUpperCase()}</td><td>0x${Number(c.bc).toString(16).toUpperCase()}</td><td>0x${Number(c.de).toString(16).toUpperCase()}</td><td>0x${Number(c.hl).toString(16).toUpperCase()}</td><td>0x${Number(c.sp).toString(16).toUpperCase()}</td></tr>`).join('')+'</tbody></table>':'';
 $('pilot-diagnostics').innerHTML=visual||summary||cp||divergenceText?`<div>${divergenceText}${budgetText}${frame}${watchText}${visual}${summary}${cp}</div>`:'<div class="empty">Diagnostics appear after the compiled run.</div>';
 $('pilot-message').textContent=`Job: ${j.state}${j.returncode===undefined||j.returncode===null?'':' (exit '+j.returncode+')'}. ${j.report_written?'Report saved locally.':''}`;
 if(j.report_written&&j.id){$('pilot-preview').src='/api/native-pilot-preview/'+encodeURIComponent(j.id);$('pilot-preview-section').hidden=false;$('pilot-preview').onerror=()=>{$('pilot-preview-section').hidden=true;};}
 $('pilot-run').disabled=active;$('pilot-cancel').disabled=!active;
 if(!active)await refreshEvidence();
 }catch(e){$('pilot-message').textContent=e.message;}
 if(active){clearTimeout(timer);timer=setTimeout(poll,1200);}
}
async function post(name,payload){return api(name,{method:'POST',headers:{'Content-Type':'application/json','X-RecompDev-Token':token,'Origin':location.origin},body:JSON.stringify(payload)});}
$('pilot-run').addEventListener('click',async()=>{
 const source_id=$('pilot-source').value;if(!source_id){$('pilot-message').textContent='Select a prepared game first.';return;}
 try{const input=$('pilot-watches').value.trim();const addresses=input?input.split(',').map(x=>{const trimmed=x.trim();if(!/^(0x[0-9a-f]+|[0-9]+)$/i.test(trimmed))throw Error('Invalid RAM watch address '+trimmed);return Number(trimmed);}):[];
 if(addresses.length>8||addresses.some(x=>!Number.isInteger(x)||x<0xc000||x>0xffff))throw Error('Select up to eight RAM addresses, 0xC000–0xFFFF');
 $('pilot-message').textContent='Starting bounded native translation…';await post('native-pilot-run',{source_id,max_steps:Number($('pilot-budget').value),max_recoveries:Number($('pilot-recoveries').value),batch_prefetch:Number($('pilot-batch').value),adaptive_execution:$('pilot-adaptive').checked,reference_file:$('pilot-reference').value.trim(),watch_addresses:addresses});poll();}
 catch(e){$('pilot-message').textContent=e.message;}
});
$('pilot-cancel').addEventListener('click',async()=>{try{await post('native-pilot-cancel',{});poll();}catch(e){$('pilot-message').textContent=e.message;}});
$('pilot-refresh').addEventListener('click',async()=>{await refreshEvidence();await poll();});
(async()=>{try{const caps=await api('native-capabilities');supportedNativeSystems=new Set(caps.systems.filter(c=>c.native_execution).map(c=>c.system));$('adapter-capabilities').innerHTML='<table><thead><tr><th>System</th><th>CPU</th><th>Native x86-64</th><th>Current blockers</th></tr></thead><tbody>'+caps.systems.map(c=>'<tr><td>'+esc(c.system)+'</td><td>'+esc(c.cpu)+'</td><td>'+esc(c.native_execution?'Experimental C++':'Not integrated')+'</td><td>'+esc(c.blockers.join(', '))+'</td></tr>').join('')+'</tbody></table>';const control=await api('native-pilot-control');token=control.token;await refreshEvidence();poll();}catch(e){$('pilot-message').textContent=e.message;}})();
