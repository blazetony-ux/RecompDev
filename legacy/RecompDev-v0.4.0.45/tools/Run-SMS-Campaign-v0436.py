#!/usr/bin/env python3
"""Owner-local seven-game RecompDev v0.4.0.36 correctness and recovery campaign.

No ROMs or generated machine code are included in the evidence ZIP. This is an
operator test harness, not a RecompDev release or a reference-parity test.
"""
import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
# Resolve release modules even when launched from C:\Users\... via an absolute script path.
import re
import subprocess
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import uuid
import zipfile

GAMES = (
    ("shinobi", "Shinobi (USA, Europe, Brazil) (En) (Rev 1).sms"),
    ("bank-panic", "Bank Panic (Europe).sms"),
    ("alex-kidd", "Alex Kidd in Miracle World (USA) (Rev-A).sms"),
    ("fantasy-zone", "Fantasy Zone (USA) (Rev-A).sms"),
    ("r-type", "R-Type (USA).sms"),
    ("sonic-sms", "Sonic the Hedgehog (USA).sms"),
    ("wonder-boy", "Wonder Boy (USA) (Rev-A).sms"),
)


def sha256(path):
    d = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            d.update(block)
    return d.hexdigest()


def read_json(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, UnicodeError):
        return None


def run_stage(name, cmd, log, cwd, timeout):
    print("  " + name + " ...", flush=True)
    start = dt.datetime.now(dt.timezone.utc)
    status = "OK"
    exit_code = None
    try:
        with log.open("w", encoding="utf-8", errors="replace") as f:
            p = subprocess.run(cmd, cwd=str(cwd), stdout=f, stderr=subprocess.STDOUT,
                               stdin=subprocess.DEVNULL, timeout=timeout, check=False)
            exit_code = p.returncode
            if exit_code:
                status = "EXIT_" + str(exit_code)
    except subprocess.TimeoutExpired:
        status = "TIMEOUT"
    except (OSError, ValueError) as e:
        status = "LAUNCH_ERROR"
        with log.open("a", encoding="utf-8") as f:
            f.write("\nLAUNCH_ERROR: " + repr(e) + "\n")
    elapsed = round((dt.datetime.now(dt.timezone.utc) - start).total_seconds(), 1)
    print("    " + name + ": " + status + " (" + str(elapsed) + "s)", flush=True)
    return {"status": status, "exit_code": exit_code, "seconds": elapsed, "log": log.name}


def evidence_zip(folder, destination):
    # Only small, explicit diagnostic artifacts. Exclude ROMs, Ghidra exports,
    # C++ source and native executables from the owner evidence archive.
    allowed = {
        "campaign-summary.json", "cross-game-triage.json", "discovery-report.json", "preparation-report.json",
        "continuous-recovery-report.json", "continuous-session.json",
        "discovery.log", "preparation.log", "recovery.log",
        "native-run-stdout.log", "native-run-stderr.log", "compiler-last.log",
    }
    with zipfile.ZipFile(destination, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for p in sorted(folder.rglob("*")):
            if p.is_file() and p.name in allowed and p.stat().st_size <= 4 * 1024 * 1024:
                z.write(p, p.relative_to(folder))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", type=Path, default=Path(r"C:\Projects\RecompDev-v0.4.0.36"))
    ap.add_argument("--rom-dir", type=Path, default=Path(r"C:\Roms\MASTERSYSTEM"))
    ap.add_argument("--frames", type=int, default=120)
    ap.add_argument("--steps", type=int, default=2_000_000)
    ap.add_argument("--max-recoveries", type=int, default=6)
    ap.add_argument("--compile-timeout", type=int, default=600)
    ap.add_argument("--no-capture", action="store_true", help="Keep lightweight null A/V evidence (no frame hashes)")
    args = ap.parse_args()
    root, rom_dir = args.root.resolve(), args.rom_dir.resolve()
    db = root / "catalogue.v0436-working.sqlite"
    prep_tool = root / "nativeprep" / "engine.py"
    recovery_tool = root / "tools" / "Run-Continuous-Recovery-v0436.py"
    if not root.is_dir() or not db.is_file() or not prep_tool.is_file() or not recovery_tool.is_file():
        print("ERROR: RecompDev v0.4.0.36 installation or working catalogue missing:", root, file=sys.stderr)
        print("Expected working catalogue:", db, file=sys.stderr)
        return 2
    if not 1 <= args.frames <= 36000 or not 1 <= args.steps <= 20_000_000 or not 0 <= args.max_recoveries <= 10 or not 30 <= args.compile_timeout <= 1800:
        ap.error("Invalid execution budgets")

    run_id = dt.datetime.now().strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:6]
    out = root / "evidence" / ("sms-seven-v0436-" + run_id)
    out.mkdir(parents=True, exist_ok=False)
    summary = {
        "schema": "recompdev-sms-seven-owner-campaign-v1",
        "release": "0.4.0.36", "created_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "rom_directory": str(rom_dir), "catalogue": str(db),
        "frames_requested": args.frames, "steps_requested": args.steps,
        "max_recoveries": args.max_recoveries, "compile_timeout": args.compile_timeout,
        "hardware_capture": not args.no_capture,
        "reference_parity": "NOT_TESTED", "gameplay": "NOT_ESTABLISHED",
        "games": [],
    }
    print("RecompDev v0.4.0.36 - seven-game authentic ROM campaign")
    print("Reports:", out)

    try:
        for index, (slug, name) in enumerate(GAMES, 1):
            print("\n[{}/7] {}".format(index, name), flush=True)
            dest = out / slug
            dest.mkdir()
            rom = rom_dir / name
            record = {"game": name, "slug": slug, "status": "NOT_STARTED"}
            summary["games"].append(record)
            if slug == 'shinobi' and not rom.is_file():
                matches = sorted(rom_dir.glob('Shinobi*.sms'))
                if len(matches) == 1:
                    rom = matches[0]
                    record['game'] = rom.name
                elif len(matches)>1:
                    record.update(status='AMBIGUOUS_SHINOBI_SOURCE',error='Multiple local Shinobi ROMs; do not guess identity')
                    print('  AMBIGUOUS_SHINOBI_SOURCE:',len(matches),flush=True)
                    continue
            if not rom.is_file():
                record.update(status="ROM_NOT_FOUND", error=str(rom))
                print("  ROM_NOT_FOUND:", rom, flush=True)
                continue
            try:
                digest = sha256(rom)
                record["sha256"] = digest
                record["bytes"] = rom.stat().st_size
            except OSError as e:
                record.update(status="ROM_READ_ERROR", error=str(e))
                continue

            discovery = dest / "discovery"
            discovery.mkdir()
            record["discovery"] = run_stage(
                "Discovery", [sys.executable, "-m", "discovery.engine", "--db", str(db),
                              "--source", str(rom), "--output", str(discovery)],
                dest / "discovery.log", root, 300)
            if record["discovery"]["status"] != "OK":
                record["status"] = "DISCOVERY_FAILED"
                continue

            preparation = dest / "preparation"
            preparation.mkdir()
            record["preparation"] = run_stage(
                "Ghidra native preparation",
                [sys.executable, "-m", "nativeprep.engine", "--db", str(db),
                 "--source-id", digest, "--output", str(preparation),
                 "--allowed-root", str(rom_dir)],
                dest / "preparation.log", root, 480)
            prep_report = read_json(preparation / "preparation-report.json")
            if prep_report:
                record["preparation_status"] = prep_report.get("status")
                record["candidate_count"] = prep_report.get("candidates")
                record["preparation_blocker"] = prep_report.get("blocker")
            export = prep_report.get("ghidra_export") if prep_report else None
            if record["preparation"]["status"] != "OK" or not export or not Path(export).is_file():
                record["status"] = "PREPARATION_BLOCKED"
                print("  No usable source-attested Ghidra export; continue to next game.", flush=True)
                continue

            recovery = dest / "recovery"
            # No recovery directory creation here: coordinator requires new/empty output.
            record["recovery"] = run_stage(
                "Compiled recovery and replay",
                [sys.executable, str(recovery_tool), "--rom", str(rom),
                 "--db", str(db), "--output-dir", str(recovery),
                 "--frames", str(args.frames), "--steps", str(args.steps),
                 "--max-recoveries", str(args.max_recoveries),
                 "--compile-timeout", str(args.compile_timeout)] +
                ([] if args.no_capture else ["--capture-hardware"]),
                dest / "recovery.log", root, max(1800,(args.max_recoveries+1)*(args.compile_timeout+150)))
            report = read_json(recovery / "continuous-recovery-report.json")
            if report:
                record.update(
                    status=report.get("status", "REPORT_WITHOUT_STATUS"),
                    blocker=report.get("blocker", ""),
                    attempts=report.get("attempt_count"),
                    recovered_instruction_addresses=report.get("recovered_entries"),
                    maximum_frames_observed=report.get("maximum_frames_observed"),
                    maximum_steps_observed=report.get("maximum_steps_observed"),
                    attempt_statuses=[x.get("status") for x in report.get("attempts", [])],
                    attempt_pcs=[x.get("pc") for x in report.get("attempts", [])],
                )
            else:
                record["status"] = "RECOVERY_NO_REPORT_" + record["recovery"]["status"]
            print("  RESULT: {} | frames={} | recovered={} | blocker={}".format(
                record["status"], record.get("maximum_frames_observed", "?"),
                record.get("recovered_instruction_addresses", "?"),
                record.get("blocker", "")[:120]), flush=True)
    except KeyboardInterrupt:
        summary["interrupted"] = True
        print("\nCampaign interrupted; packaging completed reports.", flush=True)
    finally:
        (out / "campaign-summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
        try:
            from nativecore.session_triage_v0436 import analyze_campaign
            triage = analyze_campaign(summary,out)
            (out/'cross-game-triage.json').write_text(json.dumps(triage,indent=2)+'\n',encoding='utf-8')
            print('CROSS_GAME_TRIAGE='+str(out/'cross-game-triage.json'))
        except (ValueError,OSError,TypeError,KeyError) as error:
            print('CROSS_GAME_TRIAGE_BLOCKED='+str(error),file=sys.stderr)
        archive = out.with_suffix(".zip")
        evidence_zip(out, archive)
        print("\nEVIDENCE_ZIP=" + str(archive), flush=True)
        print("RESULT SUMMARY:")
        for g in summary["games"]:
            print("  {}: {} (frames={}, recovered={})".format(
                g["game"], g["status"], g.get("maximum_frames_observed", "?"),
                g.get("recovered_instruction_addresses", "?")))
        print("No original ROM, generated machine code, native binaries, or raw A/V captures included in the ZIP.", flush=True)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
