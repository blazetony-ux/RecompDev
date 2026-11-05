#!/usr/bin/env python3
"""RecompDev Workbench: a standalone read-only, loopback-only SQLite browser.

No ROM loading, compilers, dependencies, write endpoints or arbitrary SQL API.
Source is separate from the catalogue and all Workbench logs are external.
"""
from __future__ import annotations
import argparse
from contextlib import closing
import html
import json
import os
import secrets
import sqlite3
import sys
import time
import urllib.parse
import webbrowser
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

SOURCE=Path(__file__).resolve().parents[1]
VERSION='0.1.0'
MAX_LIMIT=100
DEFAULT_LIMIT=25
QUERY_LIMIT_SECONDS=3.0

CSS="""*{box-sizing:border-box}body{margin:0;background:#101620;color:#e6edf5;font-family:system-ui,-apple-system,'Segoe UI',sans-serif;font-size:14px}a{color:#77b8f0;text-decoration:none}a:hover{text-decoration:underline}.shell{display:grid;grid-template-columns:245px 1fr;min-height:100vh}.side{background:#151f2b;border-right:1px solid #2a3544;padding:25px 18px}.brand{font-size:22px;font-weight:800;color:#eaf5ff;letter-spacing:-.4px}.brand small{display:block;font-size:11px;font-weight:500;letter-spacing:1px;color:#89a0b8;margin-top:5px;text-transform:uppercase}.nav{margin-top:35px}.nav a{display:block;padding:10px 12px;border-radius:9px;margin:5px 0;color:#b9cadb}.nav a:hover{background:#223248}.bottom{font-size:12px;color:#90a8bb;line-height:1.8;margin-top:55px}.content{padding:32px 38px;min-width:0;max-width:1700px}h1{font-size:30px;letter-spacing:-.7px;margin:4px 0 8px}h2{font-size:20px;margin:26px 0 14px}.muted{color:#98adc4}.pill{display:inline-block;border:1px solid #36516b;padding:5px 10px;border-radius:99px;font-size:12px;color:#bcd7ef;background:#1b2a39}.facts{display:flex;gap:14px;flex-wrap:wrap;margin:25px 0}.fact{background:#1b2734;border:1px solid #304052;padding:17px 20px;border-radius:14px;min-width:170px}.fact strong{display:block;font-size:22px;margin-top:7px}.panel{background:#182330;border:1px solid #304052;border-radius:14px;overflow:hidden;margin:22px 0}.panel h2{margin:0;padding:20px 22px;border-bottom:1px solid #304052}.scroll{overflow-x:auto}table{border-collapse:collapse;width:100%;min-width:620px}th{text-align:left;background:#202e3e;color:#b5c8da;font-weight:600}th,td{padding:11px 14px;border-bottom:1px solid #2b3c4e;vertical-align:top;max-width:340px;overflow-wrap:anywhere}tr:last-child td{border-bottom:0}tr:hover td{background:#202c3b}.mono{font-family:ui-monospace,SFMono-Regular,Consolas,monospace;font-size:12px}.tiny{font-size:11px;color:#849db5}.empty{padding:24px}.toolbar{display:flex;gap:12px;flex-wrap:wrap;align-items:end;padding:18px 20px;border-bottom:1px solid #304052}label{display:flex;flex-direction:column;gap:5px;color:#a7c0d7;font-size:12px}input,select{background:#0f1925;border:1px solid #39516a;padding:9px 11px;color:#eaf4ff;border-radius:8px;max-width:280px}.btn{background:#2f75ab;padding:10px 14px;color:white;border:0;border-radius:8px;cursor:pointer}.pager{display:flex;gap:18px;align-items:center;padding:17px 20px}.warning{border-left:3px solid #e5a64a;background:#252b30;padding:14px 18px;border-radius:6px;margin-top:17px}@media(max-width:850px){.shell{grid-template-columns:1fr}.side{padding:14px}.nav{margin-top:10px}.nav a{display:inline-block}.bottom{display:none}.content{padding:20px}}"""

def esc(x): return html.escape(str(x),quote=True)

def qi(name):return '"'+str(name).replace('"','""')+'"'

def read_only_db(db):
    db=Path(db).resolve(strict=True)
    if not db.is_file():raise ValueError('A SQLite catalogue file is required')
    con=sqlite3.connect(db.as_uri()+'?mode=ro',uri=True,timeout=1.0)
    con.row_factory=sqlite3.Row
    con.execute('PRAGMA query_only=ON')
    started=time.monotonic()
    con.set_progress_handler(lambda: 1 if time.monotonic()-started>QUERY_LIMIT_SECONDS else 0, 10000)
    return con

def tables(con):
    return [str(row[0]) for row in con.execute("SELECT name FROM sqlite_master WHERE type IN ('table','view') AND name NOT LIKE 'sqlite_%' ORDER BY name")]

def columns(con,table):
    if table not in tables(con):raise LookupError('Unknown table')
    return [dict(row) for row in con.execute('PRAGMA table_info('+qi(table)+')')]

def values_for_json(value):
    if isinstance(value,bytes):return {'type':'blob','bytes':len(value)}
    if value is None or isinstance(value,(int,float)):return value
    return str(value)[:2048]

def query_table(con,table,offset=0,limit=DEFAULT_LIMIT,column=None,contains=None):
    fields=columns(con,table)
    if not isinstance(offset,int) or not 0<=offset<=1_000_000 or not isinstance(limit,int) or not 1<=limit<=MAX_LIMIT:
        raise ValueError('Out-of-range pagination')
    names=[col['name'] for col in fields]
    if contains is not None:
        if column not in names or not isinstance(contains,str) or len(contains)>128:
            raise ValueError('Invalid search column or filter')
        clause=f' WHERE CAST({qi(column)} AS TEXT) LIKE ? ESCAPE \'\\\''
        # A literal LIKE substring (not a SQL wildcard expression).
        pattern='%'+contains.replace('\\','\\\\').replace('%','\\%').replace('_','\\_')+'%'
        params=[pattern]
    else:
        clause='';params=[]
    q=f'SELECT * FROM {qi(table)}'+clause+' LIMIT ? OFFSET ?'
    rows=[{name:values_for_json(row[name]) for name in names} for row in con.execute(q,[*params,limit+1,offset])]
    has_next=len(rows)>limit
    return {'table':table,'columns':fields,'rows':rows[:limit],'offset':offset,'limit':limit,
            'has_next':has_next,'filter_column':column,'filter_contains':contains}

def layout(title,body,token, db):
    root='/?token='+urllib.parse.quote(token)
    return '<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>'+esc(title)+' · RecompDev Workbench</title><style>'+CSS+'</style></head><body><div class="shell"><aside class="side"><div class="brand">RecompDev <small>Workbench / SQLite</small></div><div class="nav"><a href="'+root+'">Catalogue overview</a></div><div class="bottom"><span class="pill">READ ONLY</span><p>Local browser service · v'+VERSION+'</p><p>No SQL execution or database writes.</p></div></aside><main class="content">'+body+'<p class="tiny">Catalogue: '+esc(db)+'<br>Loopback only · database never copied or modified by this service</p></main></div></body></html>'

def url_for_table(table,token,**kwargs):
    path='/table/'+urllib.parse.quote(table,safe='')
    return path+'?'+urllib.parse.urlencode({'token':token,**{k:v for k,v in kwargs.items() if v is not None}})

class WorkbenchServer(ThreadingHTTPServer):
    daemon_threads=True
    allow_reuse_address=True
    def __init__(self,address,database,token,log_path=None):
        if address[0] != '127.0.0.1':raise ValueError('Workbench is restricted to loopback')
        self.database=Path(database).resolve(strict=True)
        self.token=token
        self.log_path=Path(log_path) if log_path else None
        super().__init__(address,WorkbenchHandler)

class WorkbenchHandler(BaseHTTPRequestHandler):
    server_version='RecompDevWorkbench/0.1.0'
    def log_message(self,fmt,*args):
        msg=(datetime.now(timezone.utc).isoformat()+' '+self.address_string()+' '+(fmt%args).split('?token=')[0]+'\n')
        if self.server.log_path:
            self.server.log_path.parent.mkdir(parents=True,exist_ok=True)
            with self.server.log_path.open('a',encoding='utf8') as f:f.write(msg)
    def _send(self,status,body,kind='text/html; charset=utf-8'):
        encoded=body.encode('utf-8') if isinstance(body,str) else body
        self.send_response(status)
        for k,v in {'Content-Type':kind,'Content-Length':str(len(encoded)),
                    'Cache-Control':'no-store','X-Content-Type-Options':'nosniff',
                    'Referrer-Policy':'no-referrer',
                    'Content-Security-Policy':"default-src 'none'; style-src 'unsafe-inline'; form-action 'self'; base-uri 'none'; frame-ancestors 'none'"}.items():self.send_header(k,v)
        self.end_headers();self.wfile.write(encoded)
    def do_POST(self):self._send(405,'Method not allowed','text/plain')
    def do_PUT(self):self._send(405,'Method not allowed','text/plain')
    def do_DELETE(self):self._send(405,'Method not allowed','text/plain')
    def do_GET(self):
        parsed=urllib.parse.urlsplit(self.path)
        qs=urllib.parse.parse_qs(parsed.query,keep_blank_values=True)
        if qs.get('token',[''])[0]!=self.server.token:
            self._send(403,'Workbench access token required','text/plain');return
        path=urllib.parse.unquote(parsed.path)
        try:
            with closing(read_only_db(self.server.database)) as con:
                if path=='/':
                    listed=tables(con)
                    rows=''.join('<tr><td><a href="'+esc(url_for_table(t,self.server.token))+'">'+esc(t)+'</a></td><td class="mono">'+esc(len(columns(con,t)))+'</td><td>Browse →</td></tr>' for t in listed)
                    body='<span class="pill">READ-ONLY DATABASE</span><h1>Catalogue overview</h1><p class="muted">Explore discovered sources, recovery jobs, assets and analysis records. Select any table to browse the entries.</p><div class="facts"><div class="fact"><span class="muted">Tables / views</span><strong>'+str(len(listed))+'</strong></div><div class="fact"><span class="muted">Database size</span><strong>'+str(round(self.server.database.stat().st_size/1024/1024,2))+' MB</strong></div><div class="fact"><span class="muted">Mode</span><strong>Read only</strong></div></div><div class="panel"><h2>Database tables</h2><div class="scroll"><table><thead><tr><th>Table</th><th>Columns</th><th>Action</th></tr></thead><tbody>'+rows+'</tbody></table></div></div>'
                    self._send(200,layout('Catalogue',body,self.server.token,self.server.database));return
                if path.startswith('/table/'):
                    name=path[len('/table/'):]
                    offset=int(qs.get('offset',['0'])[0]);limit=int(qs.get('limit',[str(DEFAULT_LIMIT)])[0])
                    column=qs.get('column',[None])[0];contains=qs.get('contains',[None])[0]
                    if contains=='':contains=None
                    info=query_table(con,name,offset,limit,column,contains)
                    headers=''.join('<th>'+esc(c['name'])+'<div class="tiny">'+esc(c['type'])+'</div></th>' for c in info['columns'])
                    trs=''
                    for row in info['rows']:
                        trs+='<tr>'+''.join('<td class="mono">'+(('<em class="tiny">NULL</em>') if row[c['name']] is None else esc('BLOB ('+str(row[c['name']]['bytes'])+' bytes)' if isinstance(row[c['name']],dict) else row[c['name']]))+'</td>' for c in info['columns'])+'</tr>'
                    filters='<option value="">Choose column</option>'+''.join('<option value="'+esc(c['name'])+'"'+(' selected' if c['name']==column else '')+'>'+esc(c['name'])+'</option>' for c in info['columns'])
                    toolbar='<form method="get" class="toolbar"><input type="hidden" name="token" value="'+esc(self.server.token)+'"><label>Filter column<select name="column">'+filters+'</select></label><label>Contains<input name="contains" maxlength="128" value="'+esc(contains or '')+'" placeholder="Text to find"></label><label>Page size<select name="limit">'+''.join(f'<option value="{n}"'+(' selected' if limit==n else '')+f'>{n}</option>' for n in (10,25,50,100))+'</select></label><button class="btn">Search</button></form>'
                    paging='<div class="pager">Showing rows '+str(offset+1 if info['rows'] else 0)+'–'+str(offset+len(info['rows']))
                    kwargs={'limit':limit,'column':column,'contains':contains}
                    if offset>0:paging+=' · <a href="'+esc(url_for_table(name,self.server.token,offset=max(0,offset-limit),**kwargs))+'">← Previous</a>'
                    if info['has_next']:paging+=' · <a href="'+esc(url_for_table(name,self.server.token,offset=offset+limit,**kwargs))+'">Next →</a>'
                    paging+='</div>'
                    body='<a href="/?token='+esc(urllib.parse.quote(self.server.token))+'">← Catalogue overview</a><h1>'+esc(name)+'</h1><p class="muted">'+str(len(info['columns']))+' columns · read-only row preview · '+str(limit)+' rows per page</p><div class="panel">'+toolbar+'<div class="scroll"><table><thead><tr>'+headers+'</tr></thead><tbody>'+trs+'</tbody></table></div>'+paging+'</div>'
                    self._send(200,layout(name,body,self.server.token,self.server.database));return
                if path=='/api/tables':
                    obj={'schema':'recompdev-workbench-v1','read_only':True,'tables':tables(con)}
                    self._send(200,json.dumps(obj), 'application/json; charset=utf-8');return
                if path.startswith('/api/table/'):
                    name=path[len('/api/table/'):]
                    info=query_table(con,name,int(qs.get('offset',['0'])[0]),int(qs.get('limit',[str(DEFAULT_LIMIT)])[0]),qs.get('column',[None])[0],qs.get('contains',[None])[0])
                    self._send(200,json.dumps(info,ensure_ascii=False),'application/json; charset=utf-8');return
                self._send(404,'No such Workbench page','text/plain')
        except (LookupError,ValueError) as exc:self._send(400,'Invalid catalogue request: '+str(exc),'text/plain')
        except sqlite3.Error as exc:self._send(503,'SQLite read failed: '+type(exc).__name__,'text/plain')

def parse_args(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--db',type=Path,default=SOURCE.parent/'RecompDev-Data/catalogue.sqlite')
    p.add_argument('--port',type=int,default=8765)
    p.add_argument('--open-browser',action='store_true')
    from workspace.manager import manifest
    p.add_argument('--log-dir',type=Path,default=SOURCE.parent/'RecompDev-Evidence'/manifest(SOURCE)['workspace_release']/'workbench')
    return p.parse_args(argv)

def main(argv=None):
    args=parse_args(argv)
    if not 0<=args.port<=65535:raise ValueError('Invalid port')
    token=secrets.token_urlsafe(22)
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    log=args.log_dir/f'workbench-{stamp}-{os.getpid()}.log'
    with WorkbenchServer(('127.0.0.1',args.port),args.db,token,log) as server:
        url=f'http://127.0.0.1:{server.server_port}/?token='+urllib.parse.quote(token)
        print('RECOMPDEV_WORKBENCH_URL='+url,flush=True)
        print('RECOMPDEV_WORKBENCH_DATABASE='+str(server.database),flush=True)
        print('Read-only Workbench. Press Ctrl+C to stop.',flush=True)
        if args.open_browser:webbrowser.open(url)
        try:server.serve_forever(poll_interval=.25)
        except KeyboardInterrupt:pass
    return 0

if __name__=='__main__':raise SystemExit(main())
