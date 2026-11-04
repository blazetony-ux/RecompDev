"""Loopback-only Workbench controller for bounded owner-local discovery jobs.

Never uploads/serves source ROM bytes. Only preconfigured roots may be browsed.
Launches an argv-only child (no shell), with per-job reports/logs and one active job.
"""
import os
import secrets
import subprocess
import sys
import threading
import uuid
from pathlib import Path
from discovery.engine import INPUT_SUFFIXES,EXCLUDE

class DiscoveryController:
    def __init__(self, root, db, allowed_roots, native_prepare_analysis=True):
        self.root=Path(root).resolve()
        self.native_prepare_analysis=bool(native_prepare_analysis)
        self.db=Path(db).resolve()
        self.roots=[]
        for raw in allowed_roots:
            base=Path(raw).resolve()
            if base.is_dir() and base not in self.roots:self.roots.append(base)
        # Database outside the installation (e.g. synthetic regression) owns
        # its own isolated evidence root; temporary fixtures never pollute
        # authentic owner-local production jobs.
        self.evidence_root = self.root if self.db.is_relative_to(self.root) else self.db.parent
        self.token=secrets.token_urlsafe(40)
        self.lock=threading.RLock()
        self.job=None
        self.native_job=None
        self.pilot_job=None
        self.output_root=self.evidence_root/'evidence'/'discovery-v0402'/'jobs'

    def _within(self,path):
        p=Path(path).resolve()
        if not any(p==r or r in p.parents for r in self.roots):
            raise ValueError('Only configured ROM folders can be selected')
        return p

    def browse(self,raw=''):
        if not raw:
            return {'roots':[str(r) for r in self.roots],'folder':'', 'parent':'', 'directories':[], 'files':[],
                    'hint':'Select a configured ROM folder to browse its contents.'}
        path=self._within(raw)
        if not path.is_dir():raise ValueError('Selected path is not a directory')
        directories=[];files=[]
        for item in sorted(path.iterdir(),key=lambda p:(not p.is_dir(),p.name.casefold())):
            if item.is_symlink() or item.name.startswith('.') or item.name in EXCLUDE:continue
            if item.is_dir():directories.append({'name':item.name,'path':str(item)})
            elif item.is_file() and (item.suffix.lower() in INPUT_SUFFIXES or not item.suffix):
                files.append({'name':item.name,'path':str(item),'bytes':item.stat().st_size})
            if len(directories)+len(files)>=1000:break
        parent=path.parent
        return {'roots':[str(r) for r in self.roots], 'folder':str(path),
                'parent':str(parent) if any(parent==r or r in parent.parents for r in self.roots) else '',
                'directories':directories,'files':files,
                'truncated':len(directories)+len(files)>=1000}

    def _job_data(self):
        job=self.job
        if job is None:return {'state':'IDLE','message':'No discovery job has been started from this Workbench.'}
        process=job['process']
        rc=process.poll()
        if rc is not None and job['state'] in ('RUNNING','STOP_REQUESTED'):
            job['state']=('CANCELLED' if job['state']=='STOP_REQUESTED' else ('COMPLETE' if rc==0 else 'FAILED'))
            job['returncode']=rc
        logfile=job['log']
        tail=''
        if logfile.is_file():
            with open(logfile,'rb') as f:
                f.seek(max(0,logfile.stat().st_size-12000));tail=f.read(12000).decode('utf-8','replace')
        return {'id':job['id'],'state':job['state'],'returncode':job.get('returncode'),
                'selection':job['selection'],'budget':job['budget'],'log':tail[-9500:],
                'report_written':job['report'].is_file(),
                'message':('Running analysis; the catalogue will refresh when this job finishes.' if job['state']=='RUNNING'
                           else 'Review the result below and refresh discovery evidence.')}

    def status(self):
        with self.lock:return self._job_data()

    def launch(self, request):
        if not isinstance(request,dict):raise ValueError('Expected JSON object')
        mode=request.get('mode');selection=request.get('path')
        if mode not in ('file','folder') or not isinstance(selection,str) or not selection:
            raise ValueError('Choose one file or folder from the ROM browser')
        path=self._within(selection)
        if mode=='file':
            if not path.is_file() or (path.suffix.lower() not in INPUT_SUFFIXES and path.suffix):
                raise ValueError('Selected file is not a supported ROM/container candidate')
        elif not path.is_dir():raise ValueError('Selected folder does not exist')
        # Reject booleans; bool is an int subclass.
        budget=request.get('budget',150);max_files=request.get('max_files',100)
        if type(budget) is not int or not 1<=budget<=500:
            raise ValueError('Budget must be an integer from 1 to 500')
        if type(max_files) is not int or not 1<=max_files<=300:
            raise ValueError('File limit must be an integer from 1 to 300')
        retry=request.get('retry_failed',False)
        if type(retry) is not bool:raise ValueError('Invalid retry option')
        with self.lock:
            if self.job and self._job_data()['state'] in ('RUNNING','STOP_REQUESTED'):
                raise RuntimeError('A discovery job is already running; let it complete or stop it first')
            if self.native_job and self._native_status()['state'] in ('RUNNING','STOP_REQUESTED'):
                raise RuntimeError('A native preparation job is still running')
            if self.pilot_job and self._pilot_status()['state'] in ('RUNNING','STOP_REQUESTED'):
                raise RuntimeError('A native execution job is still running')
            jid=uuid.uuid4().hex[:16]
            output=self.output_root/jid
            output.mkdir(parents=True,exist_ok=False)
            logfile=output/'worker.log'
            argv=[sys.executable,'-u','-X','faulthandler','-m','discovery.engine',
                  '--db',str(self.db),'--output',str(output),'--budget',str(budget),
                  '--max-files',str(max_files),'--source' if mode=='file' else '--source-root',str(path)]
            if retry:argv.append('--retry-failed')
            # Open the bounded log in the server. Never use shell=True; paths are argv values.
            with open(logfile,'wb') as log:
                proc=subprocess.Popen(argv,cwd=str(self.root),stdin=subprocess.DEVNULL,
                                      stdout=log,stderr=subprocess.STDOUT,close_fds=True)
            self.job={'id':jid,'state':'RUNNING','process':proc,'log':logfile,
                      'report':output/'discovery-report.json','selection':str(path),'budget':budget}
            return self._job_data()

    def cancel(self):
        with self.lock:
            if not self.job or self._job_data()['state']!='RUNNING':
                raise ValueError('There is no running discovery job')
            self.job['process'].terminate()
            self.job['state']='STOP_REQUESTED'
            return self._job_data()

    def _native_status(self):
        job=self.native_job
        if job is None:return {'state':'IDLE','message':'Select an imported source to prepare.'}
        rc=job['process'].poll()
        if rc is not None and job['state'] in ('RUNNING','STOP_REQUESTED'):
            job['state']='CANCELLED' if job['state']=='STOP_REQUESTED' else ('COMPLETE' if rc==0 else 'FAILED')
            job['returncode']=rc
        tail=''
        if job['log'].is_file():
            with open(job['log'],'rb') as f:
                f.seek(max(0,job['log'].stat().st_size-9000))
                tail=f.read(9000).decode('utf-8','replace')
        return {'id':job['id'],'state':job['state'],'returncode':job.get('returncode'),
                'source_id':job['source_id'],'log':tail[-8000:],
                'report_written':job['report'].is_file()}

    def native_status(self):
        with self.lock:return self._native_status()

    def prepare_native(self,request):
        if not isinstance(request,dict) or not isinstance(request.get('source_id'),str):
            raise ValueError('Choose an imported source')
        sid=request['source_id']
        if len(sid)>128 or not sid:raise ValueError('Invalid source ID')
        import sqlite3
        con=sqlite3.connect(str(self.db))
        try:row=con.execute('SELECT path FROM discovery_sources WHERE source_id=?',(sid,)).fetchone()
        except sqlite3.OperationalError:row=None
        finally:con.close()
        if not row:raise ValueError('Source not found. Add the ROM using Autonomous Discovery first')
        source=self._within(row[0])
        if not source.is_file():raise ValueError('Selected source file is missing')
        with self.lock:
            if self.job and self._job_data()['state'] in ('RUNNING','STOP_REQUESTED'):
                raise RuntimeError('Wait for the current discovery job to finish')
            if self.native_job and self._native_status()['state'] in ('RUNNING','STOP_REQUESTED'):
                raise RuntimeError('A native preparation is already running')
            if self.pilot_job and self._pilot_status()['state'] in ('RUNNING','STOP_REQUESTED'):
                raise RuntimeError('A native execution job is still running')
            jid=uuid.uuid4().hex[:16]
            output=self.evidence_root/'evidence'/'native-prepare-v0403'/'jobs'/jid
            output.mkdir(parents=True,exist_ok=False)
            logfile=output/'worker.log'
            argv=[sys.executable,'-u','-X','faulthandler','-m','nativeprep.engine',
                  '--db',str(self.db),'--source-id',sid,'--output',str(output)]
            for r in self.roots:argv.extend(['--allowed-root',str(r)])
            if not self.native_prepare_analysis:argv.append('--no-analysis')
            with open(logfile,'wb') as log:
                proc=subprocess.Popen(argv,cwd=str(self.root),stdin=subprocess.DEVNULL,
                                      stdout=log,stderr=subprocess.STDOUT,close_fds=True)
            self.native_job={'id':jid,'process':proc,'state':'RUNNING','source_id':sid,
                             'log':logfile,'report':output/'preparation-report.json'}
            return self._native_status()

    def cancel_native(self):
        with self.lock:
            if not self.native_job or self._native_status()['state']!='RUNNING':
                raise ValueError('No native preparation currently running')
            self.native_job['process'].terminate()
            self.native_job['state']='STOP_REQUESTED'
            return self._native_status()

    def _pilot_status(self):
        job=self.pilot_job
        if job is None:return {'state':'IDLE','message':'Select a prepared source; native execution requires an integrated CPU and system adapter.'}
        rc=job['process'].poll()
        if rc is not None and job['state'] in ('RUNNING','STOP_REQUESTED'):
            job['state']='CANCELLED' if job['state']=='STOP_REQUESTED' else ('COMPLETE' if rc==0 else 'FAILED')
            job['returncode']=rc
        tail=''
        if job['log'].is_file():
            with open(job['log'],'rb') as f:
                f.seek(max(0,job['log'].stat().st_size-11000))
                tail=f.read(11000).decode('utf-8','replace')
        summary=[];trace={};graph={};parity={};diagnosis={};parity_status='NOT_TESTED';budget_history=[]
        if job['report'].is_file() and job['report'].stat().st_size<2*1024*1024:
            try:
                import json
                doc=json.loads(job['report'].read_text(encoding='utf-8'))
                diagnosis=doc.get('divergence_diagnosis') or {}
                summary=[{k:v for k,v in a.items() if k in ('attempt','status','native_steps','pc','physical_offset','mapper','translated_instructions','recovery','recovery_blocker','first_vdp_port_step','recovery_target')} for a in doc.get('recovery_attempts',[])[:6]]
                graph=doc.get('dependency_graph') or {};parity=doc.get('reference_check') or {};parity_status=doc.get('reference_parity','NOT_TESTED')
                budget_history=(doc.get('budget_history') or [])[:24]
                raw=doc.get('trace') or {}
                trace={k:v for k,v in raw.items() if k in ('native_steps','checkpoints','hotspots','vdp_control_writes','vdp_data_writes','psg_writes','events_total','events_truncated','event_stream_complete','event_stream_chunks','watched_memory','maskable_interrupts','vblank_events','frames','first_vdp_port_step','first_vdp_data_step','first_psg_step','elapsed_ms')} if isinstance(raw,dict) else {}
            except (OSError,ValueError,TypeError):pass
        return {'id':job['id'],'state':job['state'],'returncode':job.get('returncode'),
                'source_id':job['source_id'],'log':tail[-9500:],
                'attempts':summary,'trace':trace,'budget_history':budget_history,'dependency_graph':graph,'reference_check':parity,'divergence_diagnosis':diagnosis,'reference_parity':parity_status,'report_written':job['report'].is_file()}

    def pilot_status(self):
        with self.lock:return self._pilot_status()

    def launch_pilot(self,request):
        if not isinstance(request,dict) or not isinstance(request.get('source_id'),str):
            raise ValueError('Choose a prepared game')
        sid=request['source_id']
        if len(sid)>128 or not sid:raise ValueError('Invalid source identity')
        watch=request.get('watch_addresses',[])
        if not isinstance(watch,list) or len(watch)>8 or any(type(a)!=int or not 0xc000<=a<=0xffff for a in watch):
            raise ValueError('Watchpoints must be a list of at most eight RAM addresses (0xC000..0xFFFF)')
        batch=request.get('batch_prefetch',0)
        if type(batch)!=int or not 0<=batch<=2:raise ValueError('Branch prefetch must be 0, 1 or 2')
        reference=request.get('reference_file','')
        if type(reference)!=str or len(reference)>100 or (reference and (not reference.endswith('.json') or '\\' in reference or '..' in reference or len(Path(reference).parts)>2)):
            raise ValueError('Independent reference must be a simple .json filename')
        steps=request.get('max_steps',50000)
        adaptive=request.get('adaptive_execution',False)
        if type(adaptive)!=bool:raise ValueError('Adaptive execution must be true or false')
        recoveries=request.get('max_recoveries',2)
        if type(recoveries)!=int or not 0<=recoveries<=5:
            raise ValueError('Recovery budget must be an integer from 0 to 5')
        if type(steps) is not int or not 1<=steps<=2000000:
            raise ValueError('Step budget must be an integer from 1 to 2000000')
        import sqlite3
        con=sqlite3.connect(str(self.db))
        try:row=con.execute('''SELECT s.path,s.system FROM discovery_sources s JOIN native_preparations_v0403 p
            ON p.source_id=s.source_id WHERE s.source_id=? ''',(sid,)).fetchone()
        except sqlite3.OperationalError:row=None
        finally:con.close()
        if not row:raise ValueError('Prepare the ROM in Autonomous Discovery first')
        from nativecore.registry import capabilities
        cap=capabilities(row[1])
        if not cap['native_execution']:raise ValueError('Native execution not integrated for '+row[1]+': '+', '.join(cap['blockers']))
        if not self._within(row[0]).is_file():raise ValueError('Original ROM missing')
        with self.lock:
            if self.job and self._job_data()['state'] in ('RUNNING','STOP_REQUESTED'):
                raise RuntimeError('Discovery currently running')
            if self.native_job and self._native_status()['state'] in ('RUNNING','STOP_REQUESTED'):
                raise RuntimeError('Native preparation currently running')
            if self.pilot_job and self._pilot_status()['state'] in ('RUNNING','STOP_REQUESTED'):
                raise RuntimeError('Native pilot currently running')
            jid=uuid.uuid4().hex[:16]
            output=self.evidence_root/'evidence'/'native-pilot-v0424'/'jobs'/jid
            output.mkdir(parents=True,exist_ok=False)
            logfile=output/'worker.log'
            argv=[sys.executable,'-u','-X','faulthandler','-m','nativepilot.engine',
                '--db',str(self.db),'--source-id',sid,'--output',str(output),'--max-steps',str(steps),'--max-recoveries',str(recoveries)]
            argv.extend(['--batch-prefetch',str(batch)])
            if adaptive:argv.append('--adaptive')
            if reference:
                folder=(self.root/'evidence'/'independent-reference').resolve()
                selected=(folder/reference).resolve()
                if not selected.is_relative_to(folder) or not selected.is_file() or selected.stat().st_size>1024*1024:
                    raise ValueError('Reference JSON must exist under this installation evidence/independent-reference (max 1 MB)')
                argv.extend(['--reference',str(selected)])
            for address in watch:argv.extend(['--watch',hex(address)])
            for r in self.roots:argv.extend(['--allowed-root',str(r)])
            with open(logfile,'wb') as log:
                proc=subprocess.Popen(argv,cwd=str(self.root),stdin=subprocess.DEVNULL,
                                      stdout=log,stderr=subprocess.STDOUT,close_fds=True)
            self.pilot_job={'id':jid,'process':proc,'state':'RUNNING','source_id':sid,
                            'log':logfile,'report':output/'pilot-report.json'}
            return self._pilot_status()

    def cancel_pilot(self):
        with self.lock:
            if not self.pilot_job or self._pilot_status()['state']!='RUNNING':
                raise ValueError('No native pilot job currently running')
            self.pilot_job['process'].terminate()
            self.pilot_job['state']='STOP_REQUESTED'
            return self._pilot_status()

    def shutdown(self):
        # Reap child processes: Windows locks worker.log while a worker holds it.
        with self.lock:
            for job in (self.job,self.native_job,self.pilot_job):
                if not job:continue
                proc=job['process']
                if proc.poll() is not None:continue
                try:
                    proc.terminate()
                    try:proc.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        proc.kill();proc.wait(timeout=5)
                except (OSError,subprocess.TimeoutExpired):pass
