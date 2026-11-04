"""Local Workbench: read-only evidence plus bounded owner-approved discovery jobs."""
import json
import secrets
import sqlite3
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs,urlsplit
from graph_store import connect
from discovery.workbench_jobs import DiscoveryController

ROOT=Path(__file__).resolve().parent


def _installation_roots():
    import re
    # Discover only sibling, numbered RecompDev installations. No unrelated paths.
    items=[p for p in ROOT.parent.iterdir() if p.is_dir() and not p.is_symlink()
           and re.fullmatch(r'RecompDev-v0\.4\.0\.[0-9]+',p.name)]
    items.sort(key=lambda x:int(x.name.rsplit('.',1)[-1]),reverse=True)
    return items[:32]



def hx(value):
    return f'0x{value:08X}' if value is not None else None


def rows(con,query,params=()):
    return [dict(r) for r in con.execute(query,params).fetchall()]

LATEST=''' r.rowid IN (SELECT MAX(r2.rowid) FROM graph_runs r2 GROUP BY r2.target_id) '''


def _table_available(con,name):
    return bool(con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",(name,)).fetchone())


def _pilot_report_summary(report_path,expected_sha):
    """Read *only* a bounded generated report in a sibling RecompDev install.

    Old working catalogues retain absolute report paths. Never use such a path
    as unrestricted file access or reveal the source ROM's contents.
    """
    import re
    try:
        file=Path(report_path).resolve(strict=True)
        install=next((part for part in file.parents if part.parent==ROOT.parent),None)
        if (not install or not re.fullmatch(r'RecompDev-v0\.4\.0\.\d+',install.name)
            or not install.is_dir() or file.name!='pilot-report.json'
            or len(file.relative_to(install).parts)!=5
            or file.relative_to(install).parts[0]!='evidence'
            or not re.fullmatch(r'native-pilot-v\d+',file.relative_to(install).parts[1])
            or file.relative_to(install).parts[2]!='jobs'
            or not re.fullmatch(r'[0-9a-f]{16}',file.relative_to(install).parts[3])
            or file.stat().st_size>3_000_000):
            return {}
        doc=json.loads(file.read_text(encoding='utf-8'))
        if doc.get('source_id')!=expected_sha:return {}
        trace=doc.get('trace') or {}
        generation=doc.get('generation') or {}
        return {'recovery_count':sum(x.get('recovery') in ('BANK_SOURCE_VERIFIED','SOURCE_VERIFIED','FIXED_SOURCE_VERIFIED') or
             str(x.get('recovery','')).endswith('_VERIFIED') for x in doc.get('recovery_attempts',[])),
            'attempt_count':len(doc.get('recovery_attempts',[])),
            'source_bytes_covered':generation.get('source_bytes_covered'),
            'reference_parity':doc.get('reference_parity','NOT_TESTED'),
            'frames_simulated':trace.get('frames'),
            'interrupts_delivered':trace.get('maskable_interrupts'),
            'dependency_unresolved':(doc.get('dependency_graph') or {}).get('unresolved_edges'),
            'hardware_events':trace.get('events_total'), 'hardware_events_truncated':bool(trace.get('events_truncated') and not trace.get('event_stream_complete')),
            'hardware_events_preview_truncated':trace.get('events_truncated'), 'hardware_events_stream_complete_at_capture':trace.get('event_stream_complete'),
            'report_available':True}
    except (OSError,ValueError,TypeError,KeyError,json.JSONDecodeError):
        return {}


def _native_progress(con):
    """Unify native preparation and execution by immutable source identity.

    This is an evidence summary, NOT a count of verified native functions or
    whole-ROM conversion progress. Older/partial databases are supported.
    """
    if not _table_available(con,'discovery_sources'):return []
    sources=rows(con,'SELECT source_id,display_name,path,system,bytes FROM discovery_sources ORDER BY display_name,source_id')
    prepared={}
    if _table_available(con,'native_preparations_v0403'):
        prepared={r['source_id']:r for r in rows(con,'SELECT source_id,target_id,cpu,status,candidate_count FROM native_preparations_v0403')}
    pilots={}
    if _table_available(con,'native_pilots_v0404'):
        pilots={r['source_id']:r for r in rows(con,'SELECT source_id,target_id,status,translated_instructions,native_steps,blocker,report_path,updated_utc FROM native_pilots_v0404')}
    overlays={}
    if _table_available(con,'native_bank_evidence_v0405'):
        overlays=dict(con.execute('SELECT source_id,COUNT(*) FROM native_bank_evidence_v0405 GROUP BY source_id').fetchall())
    nodes={};frontier={}
    if _table_available(con,'native_code_nodes_v0410'):
        nodes=dict(con.execute('SELECT source_id,COUNT(*) FROM native_code_nodes_v0410 GROUP BY source_id').fetchall())
    if _table_available(con,'native_code_edges_v0410'):
        frontier=dict(con.execute("SELECT source_id,COUNT(*) FROM native_code_edges_v0410 WHERE state='UNRESOLVED' GROUP BY source_id").fetchall())
    result=[]
    for src in sources:
        sid=src['source_id'];prep=prepared.get(sid,{});run=pilots.get(sid,{})
        item={'source_id':sid,'target_id':prep.get('target_id') or run.get('target_id'),
              'display_name':src['display_name'] or Path(src['path']).name,
              'system':src['system'],'rom_bytes':src['bytes'],
              'preparation_status':prep.get('status','NOT_PREPARED'),
              'candidate_count':prep.get('candidate_count',0),
              'native_status':run.get('status','NOT_RUN'),
              'translated_instructions':run.get('translated_instructions',0),
              'native_steps':run.get('native_steps',0),
              'blocker':run.get('blocker',''),
              'bank_evidence_entries':overlays.get(sid,0),
              'dependency_nodes':nodes.get(sid,0),
              'dependency_frontier':frontier.get(sid,0),
              'reference_parity':'NOT_TESTED'}
        if run.get('report_path'):
            item.update(_pilot_report_summary(run['report_path'],sid))
        result.append(item)
    return result



def _native_history_sources(con):
    """Reconcile native evidence with SHA-256 identities from BOTH catalogue domains.

    `discovery_sources.source_id` is not always a full SHA-256 in imported
    catalogues. `targets.source_sha256` is the authoritative static-graph
    identity. Never guess a source hash from a target name, prefix, or path.
    """
    from platform424.evidence import SHA
    candidates={}
    diagnostics=[]
    for item in _native_progress(con):
        sid=item.get('source_id')
        if not isinstance(sid,str) or not SHA.fullmatch(sid):
            diagnostics.append({'source_id':str(sid)[:80],
                'reason':'DISCOVERY_SOURCE_ID_NOT_FULL_SHA256'})
            continue
        candidates[sid]=item
    if _table_available(con,'targets'):
        has_labels=_table_available(con,'target_names')
        label='n.display_name' if has_labels else 'NULL'
        join=' LEFT JOIN target_names n ON n.target_id=t.target_id' if has_labels else ''
        graph_rows=rows(con,f"""SELECT t.target_id,t.source_sha256,t.system_tag,
            {label} AS display_name FROM targets t{join}
            ORDER BY t.target_id""")
        for graph in graph_rows:
            sha=graph['source_sha256']
            if not isinstance(sha,str) or not SHA.fullmatch(sha):
                diagnostics.append({'source_id':str(graph['target_id'])[:80],
                    'reason':'GRAPH_TARGET_MISSING_FULL_SHA256'})
                continue
            if sha not in candidates:
                candidates[sha]={'source_id':sha,'target_id':graph['target_id'],
                    'display_name':graph['display_name'] or graph['target_id'],
                    'system':graph['system_tag'],'preparation_status':'NOT_PREPARED',
                    'native_status':'NOT_RUN'}
            else:
                item=candidates[sha]
                if not item.get('target_id'):item['target_id']=graph['target_id']
                if graph['display_name'] and (not item.get('display_name') or
                        item['display_name']==item.get('source_id')):
                    item['display_name']=graph['display_name']
    return sorted(candidates.values(),key=lambda x:(str(x['display_name']).lower(),x['source_id'])),diagnostics[:50]


def _read_history_for_sources(sources,installs,max_jobs=3,check_events=True):
    """Reject one bad record without aborting evidence for unrelated games."""
    from platform424.evidence import history
    found=[];issues=[]
    for item in sources[:80]:
        try:
            evidence=history(item['source_id'],installs,max_jobs=max_jobs,check_events=check_events)
        except (ValueError,OSError,TypeError,KeyError,sqlite3.Error) as exc:
            issues.append({'source_id':item['source_id'],'reason':type(exc).__name__+': '+str(exc)[:140]})
            continue
        found.append((item,evidence))
    return found,issues


def data(con,resource,qs):
    target=qs.get('target',[''])[0]; run=qs.get('run',[''])[0]
    search=qs.get('q',[''])[0].strip().lower()[:120]
    limit=min(max(int(qs.get('limit',['1000'])[0]),1),2000)
    if resource=='discovery':
        # Discovery evidence is read-only through GET; the separate controlled POST API starts jobs.
        if not con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='discovery_sources'").fetchone():
            return {'schema':'recomp-autonomous-discovery-v0.4.0',
                    'sources':[], 'assets':[], 'tasks':[], 'task_status_counts':{},'disc_files':0,
                    'disclaimer':'Run Run-v040-Discover.ps1 to populate autonomous discovery evidence.'}
        from discovery.store import summary
        result=summary(con,limit=500)
        if search:
            result['assets']=[x for x in result['assets'] if search in x['format'].lower() or search in x['kind'].lower() or search in x['source_id']]
            result['tasks']=[x for x in result['tasks'] if search in x['kind'].lower() or search in x['reason'].lower() or search in x['status'].lower()]
        return result
    if resource=='native-progress':
        return {'games':_native_progress(con),'note':'Structural ROM coverage, translated instructions, executed steps and reference parity are different measurements. No counts here establish verified native functions.'}
    if resource=='native-pilots':
        if not con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='native_pilots_v0404'").fetchone():return {'jobs':[]}
        return {'jobs':rows(con,'''SELECT p.*,s.display_name,s.path FROM native_pilots_v0404 p
             JOIN discovery_sources s ON s.source_id=p.source_id ORDER BY updated_utc DESC''')}
    if resource=='native-preparation':
        if not con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='native_preparations_v0403'").fetchone():
            return {'targets':[],'candidates':[],'note':'No games prepared yet. Use Autonomous Discovery to prepare an imported source.'}
        prepared=rows(con,'''SELECT p.*,s.display_name,s.path FROM native_preparations_v0403 p
                             JOIN discovery_sources s ON s.source_id=p.source_id
                             ORDER BY p.updated_utc DESC''')
        candidates=rows(con,'''SELECT f.* FROM native_function_candidates_v0403 f
                               ORDER BY f.target_id,f.entry LIMIT 1500''')
        for f in candidates:f['entry_hex']=hx(f['entry'])
        return {'targets':prepared,'candidates':candidates,
                'note':'Ghidra candidates are uncorroborated; use Native Execution for bounded static C++ pilot attempts.'}
    if resource=='functions-v031':
        exists=con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='conversion_v031'").fetchone()
        if not exists:return {'jobs':[],'totals':{},'note':'Run recover-cpp with a Ghidra body export to populate verified source-byte / compiler evidence.'}
        where=' WHERE target_id=?' if target else ''
        params=(target,) if target else ()
        jobs=rows(con,'SELECT target_id,entry,source_sha256,compile_status,verification_status,boundary_status,reconcile_status,blocker,relative_manifest FROM conversion_v031'+where+' ORDER BY attempted_utc DESC, target_id, entry LIMIT ?',(*params,limit))
        for j in jobs:j['entry_hex']=hx(j['entry'])
        if search:jobs=[j for j in jobs if search in j['target_id'].lower() or search in j['entry_hex'].lower() or search in j['blocker'].lower() or search in j['compile_status'].lower()]
        totals=rows(con,'SELECT compile_status,COUNT(*) count FROM conversion_v031'+where+' GROUP BY compile_status',params)
        return {'jobs':jobs,'totals':{r['compile_status']:r['count'] for r in totals},
                'note':'Ghidra function claims and compiler smoke are NOT original CPU execution parity.'}
    if resource=='conversion':
        exists=con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='batch_campaigns'").fetchone()
        if not exists:return {'campaign':None,'targets':[],'jobs':[],'totals':{},'note':'No batch campaign yet. Run recomp.py batch-cpp to assess the catalogue.'}
        campaign=con.execute('SELECT * FROM batch_campaigns ORDER BY rowid DESC LIMIT 1').fetchone()
        if campaign is None:return {'campaign':None,'targets':[],'jobs':[],'totals':{},'note':'No batch campaign yet.'}
        bt=rows(con,'SELECT * FROM batch_targets WHERE campaign_id=? ORDER BY display_name',(campaign['campaign_id'],))
        extra=' AND target_id=?' if target else ''
        params=(campaign['campaign_id'],target) if target else (campaign['campaign_id'],)
        jobs=rows(con,'SELECT target_id,entry,run_id,instruction_count,boundary_state,stage,blocker FROM batch_jobs WHERE campaign_id=?'+extra+' ORDER BY target_id,entry LIMIT ?',(*params,limit))
        for j in jobs:j['entry_hex']=hx(j['entry'])
        if search:
            jobs=[j for j in jobs if search in j['stage'].lower() or search in j['target_id'].lower() or search in j['entry_hex'].lower() or search in j['blocker'].lower()]
        counts=rows(con,'SELECT stage,COUNT(*) count FROM batch_jobs WHERE campaign_id=? GROUP BY stage ORDER BY count DESC',(campaign['campaign_id'],))
        return {'campaign':dict(campaign),'targets':bt,'jobs':jobs,'totals':{x['stage']:x['count'] for x in counts},
                'note':'Compiled native units, where shown, are bounded experiments, not verified whole-function conversion.'}
    if resource=='overview':
        # Read-only compatibility with older catalogues that have not yet been migrated.
        has_names=bool(con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='target_names'").fetchone())
        label_expr='n.display_name AS display_name,n.name_source AS name_source,' if has_names else 'NULL AS display_name,NULL AS name_source,'
        join_expr=' LEFT JOIN target_names n ON n.target_id=t.target_id' if has_names else ''
        targets=rows(con,f'''SELECT t.target_id,t.isa,t.system_tag,substr(t.source_sha256,1,12) AS sha12,
        {label_expr}
        (SELECT COUNT(*) FROM observations o WHERE o.target_id=t.target_id) AS instruction_count,
        (SELECT COUNT(*) FROM graph_runs r WHERE r.target_id=t.target_id) AS analysis_runs,
        (SELECT COUNT(DISTINCT f.entry) FROM graph_functions f JOIN graph_runs r ON f.run_id=r.run_id WHERE r.target_id=t.target_id) AS functions,
        (SELECT COUNT(*) FROM (SELECT DISTINCT e.source,e.dest,e.kind FROM graph_transfers e JOIN graph_runs r ON e.run_id=r.run_id WHERE r.target_id=t.target_id AND e.kind IN ('direct_call','indirect_call'))) AS calls,
        (SELECT COUNT(*) FROM (SELECT DISTINCT b.address,b.reason FROM graph_barriers b JOIN graph_runs r ON b.run_id=r.run_id WHERE r.target_id=t.target_id)) AS barriers,
        (SELECT COUNT(*) FROM (SELECT DISTINCT e.source,e.kind FROM graph_transfers e JOIN graph_runs r ON e.run_id=r.run_id WHERE r.target_id=t.target_id AND e.kind IN ('indirect_jump','indirect_call'))) AS indirects
        FROM targets t{join_expr} ORDER BY COALESCE(display_name,t.target_id),t.target_id''')
        # Native campaigns and static graphs are distinct evidence domains.
        # Read authenticated source-keyed history without silently rewriting graph counts.
        native_history=[]
        sources,identity_issues=_native_history_sources(con)
        records,read_issues=_read_history_for_sources(sources,_installation_roots(),max_jobs=3,check_events=False)
        for item,h in records:
            if h['integrated_campaigns'] or h['pilots']:
                native_history.append({'source_id':item['source_id'],
                  'display_name':item['display_name'],'system':item['system'],
                  'integrated_campaigns':h['integrated_campaigns'],
                  'pilots':h['pilots'],'rejected_evidence':h['rejected_evidence']})
        return dict(targets=targets,runs=targets,native_history=native_history,
           native_history_issues=(identity_issues+read_issues)[:50],
           totals=dict(targets=len(targets),instructions=sum(r['instruction_count'] for r in targets),
                       function_candidates=sum(r['functions'] for r in targets),calls=sum(r['calls'] for r in targets),
                       barriers=sum(r['barriers'] for r in targets),indirects=sum(r['indirects'] for r in targets)),
           caveat='Distinct known call sites across analyzers; function entries are not independently verified.')
    where=['1=1'];args=[]
    if target:where.append('r.target_id=?');args.append(target)
    if run:where.append('r.run_id=?');args.append(run)
    # Multiple independent analysis runs remain visible; do not silently hide previous evidence.
    where=' AND '.join(where)
    if resource=='functions':
        term=''
        if search:
            try:
                n=int(search,0)
                term=' AND f.entry=?';args.append(n)
            except ValueError:
                term=' AND (lower(f.origin) LIKE ? OR lower(r.target_id) LIKE ?)';args.extend(['%'+search+'%']*2)
        result=rows(con,f'''SELECT f.run_id,r.target_id,r.analyzer,f.entry,(SELECT l.name FROM graph_function_labels l WHERE l.run_id=f.run_id AND l.entry=f.entry) AS label,f.origin,f.confidence,f.instruction_count,f.boundary_state,
            (SELECT COUNT(*) FROM graph_transfers c WHERE c.run_id=f.run_id AND c.caller_entry=f.entry AND c.kind IN ('direct_call','indirect_call')) AS outgoing,
            (SELECT COUNT(*) FROM graph_transfers c WHERE c.run_id=f.run_id AND c.dest=f.entry AND c.kind='direct_call') AS incoming
            FROM graph_functions f JOIN graph_runs r ON r.run_id=f.run_id WHERE {where}{term} ORDER BY r.target_id,f.entry LIMIT ?''',(*args,limit))
        for x in result:x['entry_hex']=hx(x['entry'])
        return result
    if resource in ('calls','transfers'):
        kinds="('direct_call','indirect_call')" if resource=='calls' else "('direct_jump','indirect_jump','taken','fallthrough','return_site','delay_slot','direct_call','indirect_call')"
        if search:
            try:
                n=int(search,0)
                where+=' AND (e.source=? OR e.dest=?)';args.extend([n,n])
            except ValueError:
                where+=' AND (lower(e.kind) LIKE ? OR lower(r.target_id) LIKE ?)';args.extend(['%'+search+'%']*2)
        result=rows(con,f'''SELECT r.target_id,r.analyzer,e.run_id,e.source,e.dest,e.kind,e.evidence,e.inside_region,e.caller_entry,e.ownership
            FROM graph_transfers e JOIN graph_runs r ON r.run_id=e.run_id
            WHERE {where} AND e.kind IN {kinds} ORDER BY r.target_id,e.source,e.kind LIMIT ?''',(*args,limit))
        for x in result:
            x['source_hex']=hx(x['source']);x['dest_hex']=hx(x['dest']);x['caller_hex']=hx(x['caller_entry'])
        return result
    if resource=='barriers':
        if search:
            where+=' AND (lower(b.reason) LIKE ? OR lower(r.target_id) LIKE ?)';args.extend(['%'+search+'%']*2)
        result=rows(con,f'''SELECT r.target_id,r.analyzer,b.run_id,b.address,b.reason FROM graph_barriers b
            JOIN graph_runs r ON r.run_id=b.run_id WHERE {where} ORDER BY r.target_id,b.address LIMIT ?''',(*args,limit))
        for x in result:x['address_hex']=hx(x['address'])
        return result
    if resource=='forms':
        params=[];filter_clause=''
        if target:filter_clause=' WHERE (EXISTS (SELECT 1 FROM observations o WHERE o.form_key=allforms.form_key AND o.target_id=?) OR EXISTS (SELECT 1 FROM candidate_forms c WHERE c.form_key=allforms.form_key AND c.target_id=?))';params.extend([target,target])
        if search:
            filter_clause+=(' AND ' if filter_clause else ' WHERE ')+'lower(allforms.form_key) LIKE ?';params.append('%'+search+'%')
        return rows(con,f'''SELECT allforms.form_key,
            (SELECT COUNT(*) FROM observations o WHERE o.form_key=allforms.form_key {"AND o.target_id=?" if target else ""}) AS observed,
            (SELECT COUNT(DISTINCT o.target_id) FROM observations o WHERE o.form_key=allforms.form_key {"AND o.target_id=?" if target else ""}) AS targets,
            (SELECT COALESCE(SUM(c.candidate_count),0) FROM candidate_forms c WHERE c.form_key=allforms.form_key {"AND c.target_id=?" if target else ""}) AS speculative,
            (SELECT GROUP_CONCAT(cap.backend||':'||cap.stage) FROM capabilities cap WHERE cap.form_key=allforms.form_key) AS stages
            FROM (SELECT form_key FROM observations UNION SELECT form_key FROM candidate_forms) allforms
            {filter_clause} ORDER BY observed DESC,speculative DESC,allforms.form_key LIMIT ?''',(*([target]*3 if target else []),*params,limit))
    if resource=='runs':
        return rows(con,'SELECT * FROM graph_runs ORDER BY rowid DESC LIMIT ?', (limit,))
    if resource=='detail':
        fn=qs.get('entry',[''])[0];rid=qs.get('run',[''])[0]
        if not rid or not fn:raise ValueError('run and entry required')
        entry=int(fn,0)
        candidates=rows(con,'''SELECT f.*,(SELECT l.name FROM graph_function_labels l WHERE l.run_id=f.run_id AND l.entry=f.entry) AS label,r.target_id FROM graph_functions f JOIN graph_runs r ON r.run_id=f.run_id WHERE f.run_id=? AND f.entry=?''',(rid,entry))
        if not candidates:raise ValueError('no such candidate')
        calls=rows(con,'''SELECT source,dest,kind,ownership FROM graph_transfers WHERE run_id=? AND caller_entry=? AND kind IN ('direct_call','indirect_call') ORDER BY source LIMIT 100''',(rid,entry))
        callers=rows(con,'''SELECT source,caller_entry,kind FROM graph_transfers WHERE run_id=? AND dest=? AND kind='direct_call' ORDER BY source LIMIT 100''',(rid,entry))
        for x in calls:x['source_hex']=hx(x['source']);x['dest_hex']=hx(x['dest'])
        for x in callers:x['source_hex']=hx(x['source']);x['caller_hex']=hx(x['caller_entry'])
        return {'candidate':candidates[0],'outgoing':calls,'incoming':callers}
    raise ValueError('unknown API resource')


def serve(db,host='127.0.0.1',port=8777,rom_roots=None,native_prepare_analysis=True):
    db=Path(db).resolve()
    if not db.is_file():raise FileNotFoundError(f'Catalogue not found: {db}')
    if host!='127.0.0.1':raise ValueError('Workbench actions are restricted to 127.0.0.1')
    controller=DiscoveryController(ROOT,db,rom_roots or [],native_prepare_analysis=native_prepare_analysis)
    class Handler(BaseHTTPRequestHandler):
        def _host_ok(self):
            if self.headers.get('Host')!=f'127.0.0.1:{port}':
                self.send_error(403,'Invalid local host');return False
            return True
        def _safe_write(self,body):
            try:self.wfile.write(body)
            except (BrokenPipeError, ConnectionAbortedError, ConnectionResetError):
                # Client closed/refreshed the browser; worker is independent.
                pass
        def _json(self,status,obj):
            body=json.dumps(obj).encode('utf-8')
            self.send_response(status);self.send_header('Content-Type','application/json; charset=utf-8')
            self.send_header('Content-Length',str(len(body)))
            self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff')
            self.end_headers();self._safe_write(body)
        def do_GET(self):
            if not self._host_ok():return
            url=urlsplit(self.path);path=url.path
            if path=='/' or path=='/index.html':
                body=(ROOT/'static/index.html').read_bytes();ctype='text/html; charset=utf-8'
            elif path in ('/native','/native/','/native.html'):
                body=(ROOT/'static/native.html').read_bytes();ctype='text/html; charset=utf-8'
            elif path in ('/execution','/execution/','/execution.html'):
                body=(ROOT/'static/execution.html').read_bytes();ctype='text/html; charset=utf-8'
            elif path in ('/tooling','/tooling/','/tooling.html'):
                body=(ROOT/'static/tooling.html').read_bytes();ctype='text/html; charset=utf-8'
            elif path in ('/discovery','/discovery/','/discovery.html'):
                body=(ROOT/'static/discovery.html').read_bytes();ctype='text/html; charset=utf-8'
            elif path=='/static/app.js':
                body=(ROOT/'static/app.js').read_bytes();ctype='text/javascript; charset=utf-8'
            elif path=='/static/tooling.js':
                body=(ROOT/'static/tooling.js').read_bytes();ctype='text/javascript; charset=utf-8'
            elif path=='/static/execution.js':
                body=(ROOT/'static/execution.js').read_bytes();ctype='text/javascript; charset=utf-8'
            elif path=='/static/native.js':
                body=(ROOT/'static/native.js').read_bytes();ctype='text/javascript; charset=utf-8'
            elif path=='/static/discovery.js':
                body=(ROOT/'static/discovery.js').read_bytes();ctype='text/javascript; charset=utf-8'
            elif path=='/static/style.css':
                body=(ROOT/'static/style.css').read_bytes();ctype='text/css; charset=utf-8'
            elif path=='/api/discovery-control':
                body=json.dumps({'ok':True,'data':{'token':controller.token,'roots':[str(p) for p in controller.roots],
                    'job':controller.status()}}).encode();ctype='application/json; charset=utf-8'
            elif path=='/api/discovery-library':
                try:
                    result=controller.browse(parse_qs(url.query).get('folder',[''])[0])
                except (ValueError,OSError) as exc:
                    self._json(400,{'ok':False,'error':str(exc)});return
                body=json.dumps({'ok':True,'data':result}).encode();ctype='application/json; charset=utf-8'
            elif path=='/api/tooling-status':
                from tooling.orchestrator import capabilities
                base=(controller.evidence_root/'evidence'/'tooling-v0424'/'jobs').resolve()
                recent=[]
                if base.is_dir():
                    for folder in sorted((x for x in base.iterdir() if x.is_dir() and not x.is_symlink()),
                                         key=lambda x:x.stat().st_mtime,reverse=True)[:12]:
                        file=folder/'analysis-job.json'
                        if file.is_file() and not file.is_symlink() and file.stat().st_size<=32768:
                            try:
                                item=json.loads(file.read_text(encoding='utf-8'))
                                if item.get('schema')=='recomp-multitool-job-v1':
                                    recent.append({'job':folder.name[:80],'isa':item.get('isa'),
                                        'status':item.get('status'),'engines':list(item.get('engines',{})),
                                        'native_parity':item.get('native_parity','NOT_TESTED')})
                            except (ValueError,OSError):pass
                campaigns=[]
                campaign_root=(controller.evidence_root/'evidence'/'campaign-v0424'/'jobs').resolve()
                if campaign_root.is_dir() and not campaign_root.is_symlink():
                    for job in sorted((x for x in campaign_root.iterdir() if x.is_dir() and not x.is_symlink()),
                                      key=lambda x:x.stat().st_mtime,reverse=True)[:12]:
                        attempts=sorted((x for x in job.iterdir() if x.is_dir() and x.name.startswith('attempt-')
                                         and not x.is_symlink()),reverse=True)
                        for attempt in attempts[:1]:
                            file=attempt/'attempt-manifest.json'
                            if file.is_file() and not file.is_symlink() and file.stat().st_size<=100000:
                                try:
                                    item=json.loads(file.read_text(encoding='utf-8'))
                                    if item.get('schema')=='recomp-durable-campaign-v0422':
                                        campaigns.append({'job':job.name[:80],'attempt':attempt.name,
                                            'isa':item.get('inputs',{}).get('isa','UNKNOWN'),
                                            'status':item.get('status','UNKNOWN'),
                                            'native_qualified':False,'gameplay':'NOT_ESTABLISHED'})
                                except (ValueError,OSError,TypeError):pass
                charter=json.loads((ROOT/'PLATFORM_CHARTER.json').read_text(encoding='utf-8'))
                body=json.dumps({'ok':True,'data':{'capabilities':capabilities(),
                    'recent_jobs':recent,'recent_campaigns':campaigns,'mission':charter['mission'],
                    'milestones':charter['acceptance_milestones'],
                    'release_validation':json.loads((ROOT/'BUILD_VALIDATION_v0435.json').read_text(encoding='utf-8'))['milestones']}}).encode()
                ctype='application/json; charset=utf-8'
            elif path=='/api/unified-evidence':
                from platform424.evidence import history
                con=connect(db,readonly=True)
                try: sources,identity_issues=_native_history_sources(con)
                finally:con.close()
                records,read_issues=_read_history_for_sources(sources,_installation_roots(),max_jobs=3)
                summaries=[]
                for item,evidence in records:
                    summaries.append({'source_id':item['source_id'],'display_name':item['display_name'],
                        'system':item['system'],'prepared':item['preparation_status'],
                        'catalogue_native_status':item['native_status'],
                        'pilots':evidence['pilots'],'integrated_campaigns':evidence['integrated_campaigns'],
                        'rejected_evidence':evidence['rejected_evidence'],
                        'gameplay':'NOT_ESTABLISHED','native_qualified':False})
                body=json.dumps({'ok':True,'data':{'schema':'recomp-unified-evidence-v0431',
                      'release':'0.4.0.45','targets':summaries,
                      'identity_issues':(identity_issues+read_issues)[:50],
                      'note':'Read-only SHA-256 target history. Invalid legacy identifiers cannot abort the request; no emulator parity is inferred.'}}).encode()
                ctype='application/json; charset=utf-8'
            elif path=='/api/native-capabilities':
                from nativecore.registry import all_capabilities
                body=json.dumps({'ok':True,'data':all_capabilities()}).encode();ctype='application/json; charset=utf-8'
            elif path=='/api/native-pilot-control':
                body=json.dumps({'ok':True,'data':{'token':controller.token,'job':controller.pilot_status()}}).encode();ctype='application/json; charset=utf-8'
            elif path=='/api/native-pilot-job':
                body=json.dumps({'ok':True,'data':controller.pilot_status()}).encode();ctype='application/json; charset=utf-8'
            elif path=='/api/native-prepare-job':
                body=json.dumps({'ok':True,'data':controller.native_status()}).encode();ctype='application/json; charset=utf-8'
            elif path=='/api/discovery-job':
                body=json.dumps({'ok':True,'data':controller.status()}).encode();ctype='application/json; charset=utf-8'
            elif path.startswith('/api/native-pilot-preview/'):
                import re
                job_id=path.rsplit('/',1)[-1]
                if not re.fullmatch(r'[0-9a-f]{16}',job_id):self.send_error(404);return
                picture=(controller.evidence_root/'evidence'/'native-pilot-v0424'/'jobs'/job_id/'diagnostic-background.png').resolve()
                root=(controller.evidence_root/'evidence'/'native-pilot-v0424'/'jobs').resolve()
                if not picture.is_file() or root not in picture.parents or picture.stat().st_size>2*1024*1024:
                    self.send_error(404);return
                body=picture.read_bytes()
                if not body.startswith(b'\x89PNG\r\n\x1a\n'):self.send_error(404);return
                ctype='image/png'
            elif path.startswith('/api/discovery-preview/'):
                # ONLY generated PNG previews under this installation's evidence directory.
                import re
                aid=path.rsplit('/',1)[-1]
                if not re.fullmatch(r'[0-9a-f]{32}',aid):self.send_error(404);return
                con=connect(db,readonly=True)
                try:
                    if not con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='discovery_assets'").fetchone():
                        self.send_error(404);return
                    record=con.execute('SELECT preview_path FROM discovery_assets WHERE asset_id=?',(aid,)).fetchone()
                finally:con.close()
                if not record or not record['preview_path']:self.send_error(404);return
                image_path=Path(record['preview_path']).resolve()
                # A v0.4.0.1 catalogue can be an independent SQLite snapshot of
                # v0.4.0. Retain its existing *generated previews* without moving
                # original ROM bytes or rewriting the previous installation.
                # Only PNGs inside these two fixed evidence roots are allowed.
                approved_roots=((ROOT/'evidence').resolve(),
                                (ROOT.parent/'RecompDev-v0.4.0'/'evidence').resolve(),
                                (ROOT.parent/'RecompDev-v0.4.0.1'/'evidence').resolve(),
                                (ROOT.parent/'RecompDev-v0.4.0.2'/'evidence').resolve())
                allowed=any(root in image_path.parents for root in approved_roots)
                if not allowed or image_path.suffix.lower()!='.png' or not image_path.is_file() or image_path.stat().st_size>8*1024*1024:
                    self.send_error(404);return
                body=image_path.read_bytes()
                if not body.startswith(b'\x89PNG\r\n\x1a\n'):self.send_error(404);return
                ctype='image/png'
            elif path.startswith('/api/'):
                try:
                    con=connect(db,readonly=True)
                    try:result=data(con,path[5:],parse_qs(url.query))
                    finally:con.close()
                    body=json.dumps({'ok':True,'data':result}).encode();ctype='application/json; charset=utf-8'
                except (ValueError,sqlite3.Error) as exc:
                    self.send_response(400);self.send_header('Content-Type','application/json');self.end_headers()
                    self._safe_write(json.dumps({'ok':False,'error':str(exc)}).encode());return
            else:
                self.send_error(404);return
            self.send_response(200);self.send_header('Content-Type',ctype)
            self.send_header('Content-Length',str(len(body)))
            self.send_header('Cache-Control','no-store')
            self.send_header('X-Content-Type-Options','nosniff')
            self.send_header('Content-Security-Policy',"default-src 'self'; connect-src 'self'; script-src 'self'; style-src 'self'; img-src 'self'; object-src 'none'; base-uri 'none'")
            self.end_headers();self._safe_write(body)
        def do_POST(self):
            if not self._host_ok():return
            path=urlsplit(self.path).path
            if path not in ('/api/discovery-run','/api/discovery-cancel','/api/native-prepare-run','/api/native-prepare-cancel','/api/native-pilot-run','/api/native-pilot-cancel'):
                self.send_error(405,'Only discovery actions are supported');return
            if (self.headers.get('Origin')!=f'http://127.0.0.1:{port}' or
                not secrets.compare_digest(self.headers.get('X-RecompDev-Token',''),controller.token) or
                self.headers.get('Content-Type','').split(';')[0].strip().lower()!='application/json'):
                self._json(403,{'ok':False,'error':'Local origin / action token required'});return
            try:
                length=int(self.headers.get('Content-Length','0'))
                if not 2<=length<=8192:raise ValueError('Invalid request length')
                request=json.loads(self.rfile.read(length))
                if path=='/api/discovery-run':result=controller.launch(request)
                elif path=='/api/discovery-cancel':result=controller.cancel()
                elif path=='/api/native-prepare-run':result=controller.prepare_native(request)
                elif path=='/api/native-pilot-run':result=controller.launch_pilot(request)
                elif path=='/api/native-pilot-cancel':result=controller.cancel_pilot()
                else:result=controller.cancel_native()
                self._json(202,{'ok':True,'data':result})
            except (ValueError,TypeError,json.JSONDecodeError) as exc:
                self._json(400,{'ok':False,'error':str(exc)})
            except RuntimeError as exc:
                self._json(409,{'ok':False,'error':str(exc)})
            except OSError as exc:
                self._json(500,{'ok':False,'error':type(exc).__name__+': '+str(exc)[:240]})
        def log_message(self,format,*args):pass
    server=ThreadingHTTPServer((host,port),Handler)
    print(f'WORKBENCH=http://{host}:{port}/\nCATALOGUE={db}\nMODE=DISCOVERY_CONTROLLED_LOCAL\nROM_ROOTS={len(controller.roots)}\nCTRL+C to stop',flush=True)
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:controller.shutdown();server.server_close()
