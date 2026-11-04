import importlib.util,json,sqlite3,sys,tempfile
from contextlib import closing
from pathlib import Path
root=Path(sys.argv[1]);reports=Path(sys.argv[2]);spec=importlib.util.spec_from_file_location('sidecar',root/'tools/import_discovery.py')
mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
with tempfile.TemporaryDirectory() as temp:
 out=Path(temp)/'new-sidecar.sqlite'
 result=mod.convert(reports/'main.events.jsonl',out)
 assert result['events']==13 and result['candidate_start_bytes']==11 and result['review_tasks']==7,result
 # sqlite3.Connection.__exit__ commits/rolls back but DOES NOT close.
 # Windows keeps the file locked until close(), so use closing explicitly.
 with closing(sqlite3.connect(out)) as db:
  assert db.execute('select count(*) from discovery_sources').fetchone()[0]==1
  assert db.execute('select count(*) from discovery_regions').fetchone()[0]==11
  assert db.execute('select count(*) from discovery_tasks').fetchone()[0]==7
 try:mod.convert(reports/'main.events.jsonl',out)
 except ValueError as e:assert 'already exists' in str(e)
 else:raise AssertionError('Attempted overwrite of existing sidecar was allowed')
 # Prove there are no leaked SQLite handles before TemporaryDirectory cleanup.
 # This is especially important on Windows, where unlinking an open DB fails.
 out.unlink()
print('ISOLATED_DISCOVERY_STORE_COMPATIBILITY_PASS')
