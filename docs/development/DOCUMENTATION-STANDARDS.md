# Documentation quality standard

**Status:** Current. Last reviewed: 2026-11-04.

## Organisation and ownership

`README.md` explains the project; `CHANGELOG.md` records workspace snapshots; `docs/README.md` is the navigation index. `docs/architecture/` records contracts/decisions, `docs/components/` records versioned plugin details, `docs/recompilation/` documents real processing, `docs/platforms/` documents machine support, `docs/research/` preserves evidence-backed findings, `docs/project/` records status/next work, `docs/development/` describes reproducible commands, and `docs/history/` preserves superseded instructions without claiming they are current.

## Required substance

Current docs must answer: *what does it do, where is the implementation, how is it validated, what remains unproven, and what follows?* Use clear titles, project-relative references and commands checked against the current CLI. Record exact source paths, component versions, evidence status and relevant dates. Do not manufacture references or claim emulator/hardware parity from synthetic fixtures.

## Automatically checked

`python -m workspace.docs_governance check` requires the active index, source contract, current handover, workspace changelog, release note, one current status/changelog for every registered component, and valid local Markdown links in current documents. It rejects incomplete version changelogs and missing release files. The historical folder is retained verbatim; old links within historical documents are not considered authoritative.

## Updated component changelog entry

Append a section matching `## [0.1.1] - YYYY-MM-DD` with a concrete reason for the change, the test name(s) performed, compatibility consequences and any known limitations. Only the changed component gets a new version. Keep the original baseline entry for provenance. Do not increment versions just to revise documentation.

## Conversation handovers

`docs/project/HANDOVER.md` must state the current real architecture, latest validated observations, file locations, exact outstanding blocker and next acceptance test. A new developer should be able to resume without requiring the previous chat transcript. The document must be updated when an accepted engineering release changes those facts.
