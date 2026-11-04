import json, subprocess, sys, tempfile, unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from adapters.identity import identify,serial_from_text,_from_system_cnf
from planner import plan

class IdentityTests(unittest.TestCase):
    def setUp(self):self.t=tempfile.TemporaryDirectory();self.base=Path(self.t.name)
    def tearDown(self):self.t.cleanup()
    def test_md_title(self):
        b=bytearray(0x200);b[0x100:0x104]=b'SEGA';b[0x150:0x150+5]=b'SONIC'
        f=self.base/'sonic.md';f.write_bytes(b);result=identify(f)
        self.assertEqual(result['identity']['display_name'],'SONIC')
        self.assertEqual(result['identity']['name_source'],'rom_header')
    def test_psx_not_false_serial(self):
        f=self.base/'boot.psx';f.write_bytes(b'PS-X EXE'+bytes(0x800-8))
        result=identify(f)['identity'];self.assertIsNone(result['game_id']);self.assertIsNone(result['display_name'])
    def test_psx_project_path_hint(self):
        f=self.base/'ps1-ridge-racer-68468e09be'/'sources'/'boot.psx';f.parent.mkdir(parents=True)
        f.write_bytes(b'PS-X EXE'+bytes(0x800-8))
        d=identify(f)['identity'];self.assertEqual(d['display_name'],'Ridge Racer');self.assertEqual(d['confidence'],'hint_only')
    def test_serial_normalization(self):
        self.assertEqual(serial_from_text('cdrom:\\SLUS_005.94;1'),'SLUS-00594')
        self.assertEqual(_from_system_cnf('BOOT2 = cdrom0:\\SCPS_110.04;1','ps2').game_id,'SCPS-11004')
    def test_stfs_title_id(self):
        b=bytearray(0x800);b[0:4]=b'LIVE';b[0x360:0x364]=bytes.fromhex('4541080f')
        name='Example Game'.encode('utf-16-be');b[0x411:0x411+len(name)]=name
        f=self.base/'game.stfs';f.write_bytes(b)
        d=identify(f)['identity'];self.assertEqual(d['game_id'],'4541080F');self.assertEqual(d['display_name'],'Example Game')
    def test_xex_execution_id(self):
        b=bytearray(0x200);b[0:4]=b'XEX2';b[0x14:0x18]=(1).to_bytes(4,'big')
        b[0x18:0x1c]=(0x40006).to_bytes(4,'big');b[0x1c:0x20]=(0x60).to_bytes(4,'big');b[0x6c:0x70]=bytes.fromhex('1234abcd')
        f=self.base/'default.xex';f.write_bytes(b)
        d=identify(f)['identity'];self.assertEqual(d['game_id'],'1234ABCD');self.assertIsNone(d['display_name'])
    def test_basic_iso9660_system_cnf(self):
        sectors=[bytearray(2048) for _ in range(24)];pvd=sectors[16];pvd[:7]=b'\x01CD001\x01'
        def rec(extent,length,name,flag=0):
            n=name.encode('ascii');size=33+len(n)+(len(n)%2==0)
            b=bytearray(size);b[0]=size;b[2:6]=extent.to_bytes(4,'little');b[10:14]=length.to_bytes(4,'little');b[25]=flag;b[32]=len(n);b[33:33+len(n)]=n;return b
        root=rec(20,2048,'\x00',2);pvd[156:156+len(root)]=root
        r=rec(21,40,'SYSTEM.CNF;1');sectors[20][:len(r)]=r
        content=b'BOOT = cdrom:\\SLUS_005.94;1\r\n'
        sectors[21][:len(content)]=content
        f=self.base/'disc.iso';f.write_bytes(b''.join(sectors))
        d=identify(f)['identity'];self.assertEqual(d['system'],'ps1');self.assertEqual(d['game_id'],'SLUS-00594')
    def test_no_false_title_for_unknown(self):
        f=self.base/'unrelated.bin';f.write_bytes(b'not a disc or supported ROM header')
        d=identify(f)['identity'];self.assertIsNone(d['display_name'])
    def test_readiness_on_original_fixture_db(self):
        p=Path('/mnt/data/targetnames-build/catalogue.sqlite')
        if not p.exists():self.skipTest('not mounted fixture')
        r=plan(str(p));self.assertEqual(r['totals']['targets'],2)
        self.assertTrue(all(f['readiness'].startswith('NEEDS_') for t in r['targets'] for f in t['functions']))
    def test_cli_adapters(self):
        p=subprocess.run([sys.executable,str(ROOT/'recomp_bridge.py'),'adapters'],capture_output=True,text=True)
        self.assertEqual(p.returncode,0);self.assertIn('Xbox 360',p.stdout);self.assertIn('PlayStation 2',p.stdout)
    def test_title_db_exact_and_ambiguity(self):
        f=self.base/'SYSTEM.CNF';f.write_text('BOOT = cdrom:\\SLUS_005.94;1')
        csv_file=self.base/'titles.csv';csv_file.write_text('system,id,title\nps1,SLUS-00594,Example Title\n')
        p=subprocess.run([sys.executable,str(ROOT/'recomp_bridge.py'),'identify','--input',str(f),'--title-db',str(csv_file)],capture_output=True,text=True)
        self.assertEqual(p.returncode,0,p.stderr);r=json.loads(p.stdout);self.assertEqual(r['identity']['display_name'],'Example Title')

if __name__=='__main__':unittest.main()


class MoreIdentityTests(unittest.TestCase):
    def setUp(self):self.t=tempfile.TemporaryDirectory();self.base=Path(self.t.name)
    def tearDown(self):self.t.cleanup()

    def test_psx_serial_from_original_executable_filename(self):
        f=self.base/'SLUS_005.94';f.write_bytes(b'PS-X EXE'+bytes(0x800-8))
        d=identify(f)['identity'];self.assertEqual(d['game_id'],'SLUS-00594')

    def test_ps1_raw_2352_mode2_iso_system_cnf(self):
        # Minimal 24-sector CD-XA Mode2/Form1 stream: user data at offset 24.
        sectors=[bytearray(2352) for _ in range(24)]
        pvd=bytearray(2048);pvd[:7]=b'\x01CD001\x01'
        def record(extent,length,name,flag=0):
            n=name.encode('ascii');size=33+len(n)+(len(n)%2==0)
            b=bytearray(size);b[0]=size;b[2:6]=extent.to_bytes(4,'little')
            b[10:14]=length.to_bytes(4,'little');b[25]=flag;b[32]=len(n);b[33:33+len(n)]=n
            return b
        pvd[156:156+34]=record(20,2048,'\x00',2)
        sectors[16][24:24+2048]=pvd
        directory=bytearray(2048);r=record(21,40,'SYSTEM.CNF;1');directory[:len(r)]=r
        sectors[20][24:24+2048]=directory
        t=b'BOOT = cdrom:\\SLUS_005.94;1\r\n';sectors[21][24:24+len(t)]=t
        f=self.base/'ps1.bin';f.write_bytes(b''.join(sectors))
        self.assertEqual(identify(f)['identity']['game_id'],'SLUS-00594')

class NameSyncTests(unittest.TestCase):
    def setUp(self):
        self.t=tempfile.TemporaryDirectory();self.base=Path(self.t.name)
    def tearDown(self):self.t.cleanup()
    def test_project_hinted_title_upgrades_boot(self):
        import sqlite3,hashlib
        from name_sync import scan_names
        f=self.base/'ps1-ridge-racer-68468e09be'/'sources'/'boot.psx';f.parent.mkdir(parents=True)
        f.write_bytes(b'PS-X EXE'+bytes(0x800-8));sha=hashlib.sha256(f.read_bytes()).hexdigest()
        db=self.base/'catalogue.sqlite';con=sqlite3.connect(db)
        con.executescript('''CREATE TABLE targets (target_id TEXT PRIMARY KEY,source_sha256 TEXT NOT NULL);
            CREATE TABLE target_names (target_id TEXT PRIMARY KEY,display_name TEXT NOT NULL,
            name_source TEXT NOT NULL CHECK(name_source IN ('owner_alias','megadrive_header','local_filename','evidence_folder')), evidence_sha256 TEXT NOT NULL);''')
        con.execute('INSERT INTO targets VALUES (?,?)',('psx-target',sha))
        con.execute('INSERT INTO target_names VALUES (?,?,?,?)',('psx-target','boot','local_filename',sha));con.commit();con.close()
        preview=scan_names(db,self.base)
        self.assertEqual(preview['status'],'preview');self.assertTrue(preview['sha_matched_names'][0]['eligible'])
        con=sqlite3.connect(db);self.assertEqual(con.execute('SELECT display_name FROM target_names').fetchone()[0],'boot');con.close()
        applied=scan_names(db,self.base,apply=True)
        self.assertEqual(applied['status'],'applied');self.assertTrue(Path(applied['backup']).is_file())
        con=sqlite3.connect(db);self.assertEqual(con.execute('SELECT display_name FROM target_names').fetchone()[0],'Ridge Racer');con.close()
    def test_owner_alias_not_overwritten(self):
        import sqlite3,hashlib
        from name_sync import scan_names
        f=self.base/'ps1-ridge-racer-68468e09be'/'sources'/'boot.psx';f.parent.mkdir(parents=True)
        f.write_bytes(b'PS-X EXE'+bytes(0x800-8));sha=hashlib.sha256(f.read_bytes()).hexdigest()
        db=self.base/'catalogue.sqlite';con=sqlite3.connect(db)
        con.executescript('''CREATE TABLE targets (target_id TEXT PRIMARY KEY,source_sha256 TEXT NOT NULL);
            CREATE TABLE target_names (target_id TEXT PRIMARY KEY,display_name TEXT NOT NULL,
            name_source TEXT NOT NULL,evidence_sha256 TEXT NOT NULL);''')
        con.execute('INSERT INTO targets VALUES (?,?)',('psx-target',sha))
        con.execute('INSERT INTO target_names VALUES (?,?,?,?)',('psx-target','Owner title','owner_alias',sha));con.commit();con.close()
        res=scan_names(db,self.base,apply=True)
        self.assertFalse(res['sha_matched_names'][0]['eligible'])
        con=sqlite3.connect(db);self.assertEqual(con.execute('SELECT display_name FROM target_names').fetchone()[0],'Owner title');con.close()
