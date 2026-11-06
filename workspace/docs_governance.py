#!/usr/bin/env python3
"""Documentation, component changelog and workspace release validation.

Source-only tooling; no generated files, game ROMs, runtime binary or database
are written by this module. Documentation scope is separate from the compiled
controller and from the immutable historical source baselines.
"""
from __future__ import annotations
import argparse
import json
import re
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[1]
LINK_RE = re.compile(r'(?<!!)\[[^\]\n]+\]\(([^)]+)\)')
VERSION_HEADING = re.compile(r'^## \[([^\]]+)\] - (\d{4}-\d{2}-\d{2})\s*$', re.M)


def check_markdown_links(source: Path, paths: list[Path]) -> None:
    """Check local links in authoritative documents, excluding old frozen notes."""
    errors = []
    for file in paths:
        raw = file.read_text(encoding='utf8')
        # Code fences may contain illustrative links and are not documentation links.
        raw = re.sub(r'^```.*?^```\s*$', '', raw, flags=re.M | re.S)
        for match in LINK_RE.finditer(raw):
            dest = match.group(1).split('#', 1)[0].strip()
            if not dest or dest.startswith(('https:', 'http:', 'mailto:')):
                continue
            if dest.startswith(('/', '\\')) or re.match(r'^[a-zA-Z]:', dest):
                errors.append(f'{file.relative_to(source)}: absolute Markdown link {dest}')
                continue
            target = (file.parent / dest).resolve()
            if not target.is_relative_to(source.resolve()) or not target.exists():
                errors.append(f'{file.relative_to(source)}: broken link {dest}')
    if errors:
        raise ValueError('Broken documentation references:\n' + '\n'.join(errors[:30]))


def _component_changelog(source: Path, name: str) -> Path:
    return source / 'docs' / 'components' / name / 'CHANGELOG.md'


def read_change_entry(text: str, version: str) -> str:
    headings = list(VERSION_HEADING.finditer(text))
    for index, match in enumerate(headings):
        if match.group(1) == version:
            stop = headings[index + 1].start() if index + 1 < len(headings) else len(text)
            return text[match.end():stop].strip()
    raise ValueError('Missing dated changelog entry for version ' + version)


def check_entry(entry: str, name: str) -> None:
    for field in ('Changed:', 'Validation:', 'Compatibility:'):
        if field not in entry:
            raise ValueError(f'{name}: changelog entry must contain {field}')
    # Require actual prose rather than an empty or placeholder section.
    content = re.sub(r'\*\*', '', entry)
    if len(content) < 135 or any(x in content.lower() for x in ('todo:', 'tbd:', 'lorem ipsum')):
        raise ValueError(f'{name}: changelog explanation is incomplete or a placeholder')


def validate_component_update(source: Path, name: str, version: str,
                              changed: set[str]) -> None:
    """An accepted component version requires a new, meaningful changelog."""
    rel = f'docs/components/{name}/CHANGELOG.md'
    if rel not in changed:
        raise ValueError(f'{name}: required component changelog was not updated: {rel}')
    file = source / rel
    if not file.is_file():
        raise ValueError(f'{name}: changelog file not found: {rel}')
    entry = read_change_entry(file.read_text(encoding='utf8'), version)
    check_entry(entry, name)


WORKSPACE_HEADER_RE = re.compile(r'^## \[workspace/(v\d+\.\d+\.\d+(?:\.\d+)?)\][^\n]*$',re.M)


def check_workspace_changelog(log: str, current_release: str) -> None:
    if not log.startswith('# RecompDev workspace changelog\n'):
        raise ValueError('Main changelog must begin with its document title')
    if log.count('# RecompDev workspace changelog') != 1:
        raise ValueError('Duplicate workspace changelog title')
    hits = WORKSPACE_HEADER_RE.findall(log)
    if not hits or 'workspace/' + hits[0] != current_release:
        raise ValueError('Workspace changelog current release must be the first entry')
    if len(hits) != len(set(hits)):
        raise ValueError('Duplicate workspace release headings')
    versions = [tuple(int(piece) for piece in v[1:].split('.')) for v in hits]
    if versions != sorted(versions,reverse=True):
        raise ValueError('Workspace changelog release entries must be newest-first')


def check(source: Path = SOURCE, *, release: str | None = None) -> dict:
    """Check authoritatively maintained docs without modifying any files."""
    source = Path(source).resolve()
    import json
    manifest = json.loads((source / 'workspace/components.json').read_text(encoding='utf8'))
    if manifest.get('schema') != 'recompdev-components-v1':
        raise ValueError('Unexpected component registry schema')
    components = manifest['components']
    required = [
        'README.md', 'CHANGELOG.md', 'docs/README.md',
        'docs/architecture/ARCHITECTURE-CONTRACT.md',
        'docs/architecture/DATA-FLOW.md',
        'docs/architecture/decisions/README.md',
        'docs/project/PROJECT-VISION.md', 'docs/project/HANDOVER.md',
        'docs/project/DEVELOPMENT-CONTRACT.md', 'docs/project/PREBUILD-v0.4.9.7.md',
        'docs/project/ROADMAP.md', 'docs/development/WORKSPACE.md',
        'docs/development/RELEASE-PROCESS.md',
        'docs/development/DOCUMENTATION-STANDARDS.md',
        'docs/recompilation/PRODUCTION-PIPELINE.md',
        'docs/components/README.md', 'docs/platforms/README.md',
        'docs/research/SHINOBI-RECOVERY.md',
        'docs/research/HARDWARE-VALIDATION-GAPS.md',
        'docs/releases/README.md', 'docs/history/README.md',
    ]
    for name in components:
        required.extend((f'docs/components/{name}/README.md',
                         f'docs/components/{name}/CHANGELOG.md'))
    current_release = release or 'workspace/' + manifest['workspace_release']
    if release is not None and release != 'workspace/' + manifest['workspace_release']:
        raise ValueError('Release tag disagrees with workspace_release in components.json')
    version = current_release.removeprefix('workspace/')
    if not re.fullmatch(r'v\d+\.\d+\.\d+(?:\.\d+)?', version):
        raise ValueError('Workspace release version must be vN.N.N or a four-part patch release')
    required.append(f'docs/releases/{version}.md')
    missing = [p for p in required if not (source / p).is_file()]
    if missing:
        raise ValueError('Missing authoritative documents: ' + ', '.join(missing))
    if version >= 'v0.4.9.8':
        installer=source/'Install-RecompDev-Release.ps1'
        if not installer.is_file() or installer.stat().st_size < 2000:
            raise ValueError('Permanent root release installer missing or incomplete')
        process=(source/'docs/development/RELEASE-PROCESS.md').read_text(encoding='utf8')
        if not all(x in process for x in ('-ExpectedSha256', '-Mode Validate', '-Mode Install', 'Git-managed')):
            raise ValueError('Permanent installer release process is not fully documented')
    for p in required:
        if (source / p).stat().st_size < 110:
            raise ValueError('Document too short to be useful: ' + p)
    # A release cannot silently lose the owner's native-first/approval contract.
    contract=(source/'docs/project/DEVELOPMENT-CONTRACT.md').read_text(encoding='utf8')
    if not all(x.lower() in contract.lower() for x in ('mandatory approval', 'RecompDev.exe', 'Shinobi', 'DLL')):
        raise ValueError('Binding development contract is incomplete')
    handover=(source/'docs/project/HANDOVER.md').read_text(encoding='utf8')
    if 'DEVELOPMENT-CONTRACT.md' not in handover or 'PREBUILD-v0.4.9.7.md' not in handover:
        raise ValueError('Handover must reference owner-approved development contract and report')
    prebuild=(source/'docs/project/PREBUILD-v0.4.9.7.md').read_text(encoding='utf8')
    if 'approval' not in prebuild.lower() or 'SHINOBI' not in prebuild.upper():
        raise ValueError('Pre-build report missing approval rules or Shinobi continuity')
    release_doc=(source/f'docs/releases/{version}.md').read_text(encoding='utf8')
    if version >= 'v0.4.9.7' and not all(x in release_doc for x in ('DEVELOPMENT-CONTRACT.md', 'PREBUILD-v0.4.9.7.md', 'BLOCKED')):
        raise ValueError('Release compliance must acknowledge approved scope and remaining acceptance blockers')
    log = (source / 'CHANGELOG.md').read_text(encoding='utf8')
    check_workspace_changelog(log, current_release)
    for name, spec in components.items():
        readme = (source / f'docs/components/{name}/README.md').read_text(encoding='utf8')
        if spec['scope'] not in readme or 'workspace/components.json' not in readme:
            raise ValueError(f'{name}: component README lacks scope or registry reference')
        changelog = _component_changelog(source, name).read_text(encoding='utf8')
        entry = read_change_entry(changelog, spec['version'])
        check_entry(entry, name)
    active = [source / p for p in required]
    active += [p for p in (source / 'docs').rglob('*.md')
               if 'history' not in p.relative_to(source / 'docs').parts
               and p not in active]
    check_markdown_links(source, active)
    return {'status': 'PASS', 'workspace_release': current_release,
            'component_changelogs': len(components),
            'authoritative_docs_checked': len(active), 'local_links': 'VERIFIED',
            'untouched_frozen_histories': ['legacy/', 'baselines/']}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('check',))
    parser.add_argument('--source', type=Path, default=SOURCE)
    parser.add_argument('--release', default=None)
    args = parser.parse_args(argv)
    try:
        result = check(args.source, release=args.release)
    except (OSError, ValueError, TypeError, KeyError) as exc:
        print(json.dumps({'status': 'ERROR', 'reason': str(exc)}, indent=2))
        return 2
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
