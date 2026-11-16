# Mycelium Asset Workbench

## What and why
A working local-first Python/SQLite organizer for layered creative assets. It is a shared foundation for OS and game workflows, not an OS or playable game. Domains contain underground, terrain, water, flora, structures and sky layers. Stable asset IDs connect references to proposed modules without treating pictures as production meshes.

The problem: images, plans and exported assets become hard to find and their completion status gets blurred. This prototype copies explicitly selected files, records provenance and hashes, retains originals, and exposes searchable reports and integrity-checked manifests.

## Run from a fresh checkout
These commands use the default `main` branch. Requires Python 3.10+ only. No dependencies, account, API key, paid services or network needed after download.
```sh
git clone https://github.com/samaravirtue/mycelium-asset-workbench.git
cd mycelium-asset-workbench
python -m unittest discover -s . -v
python demo.py
python workbench.py --workspace layered_demo/catalog search winter
python workbench.py --workspace layered_demo/catalog verify
```
On Windows use `py -3` in place of `python`. Open `layered_demo/layers.html` for the layer overview and `layered_demo/gallery.html` for the searchable report. These are read-only reports: regenerate after CLI catalog changes. GitHub displays HTML source; download the repo and open the generated files locally.

## Backup/restore milestone and review history
Backup/restore was reviewed on `draft-backup-restore-review` at commit `493b40ed6705fe5c53b0601e6cc994c810f025ec`, against the then-current main `3b2dc6a`, on 16 November 2026. To inspect the review branch separately from your current main checkout:

```sh
git switch draft-backup-restore-review
python -m unittest discover -v
python verify_milestone_roundtrip.py
```
On Windows use `py -3` in place of `python`. The roundtrip script uses fictional data only: it backs up a synthetic asset, verifies the archive, restores a new workspace, checks unchanged original bytes, and refuses a non-empty destination. See [BACKUP_REVIEW_20261116.md](BACKUP_REVIEW_20261116.md) on this review branch. These commands follow the branch tip; the dated test evidence below applies to the specified commit.

Stop all other workspace writers before backup. SQLite online backup provides a consistent database snapshot, not a multi-file transactional snapshot of the object tree. Archive hashes check integrity, not authenticity or ownership. Restore supports Windows and Linux; restore into a separate new or empty destination, never over a live workspace. Schema migration is not implemented.

## Useful synthetic sample
The demo creates 24 original procedural SVG diagrams, four illustrative domains and six layers each. This is not a four-domain limit or a copy of private story canon. Search `winter`, `water` or `underground`; follow stable IDs in `scene_plan.json` to proposed underground passages, surface accesses and shore boundaries. Plans record revision, vertical bands and required engineering checks. Manifest records source, SHA256 and workflow state. Zero samples claim engine readiness. No creature assets or proprietary artwork included.

## How it works
`workbench.py` provides SQLite metadata and audit records; copied content-addressed storage deduplicates identical bytes while preserving catalog associations. Intake rejects duplicate IDs, unsupported statuses and symlinks. Corrupt/missing objects block exports. HTML metadata is escaped. JSON manifests are intended for future adapters.

```sh
python workbench.py ingest example.png --id example-v1 --name "Example reference" --domain example --layer terrain --source "owner-approved source" --tags terrain,reference --status reference
python workbench.py search terrain
python workbench.py report gallery.html
```
Default intake uses a separate local workspace. It never automatically scans or uploads your computer. Use only material you choose to catalog.

Statuses `reference`, `proposal`, `artifact` and `tested` describe workflow. `tested` requires a declared test reference tied to the stored hash; the tool does NOT independently run that test. It is not equivalent to engine-tested, licensed or production-ready. The demo uses references and proposals only.

## Evidence and limits
Evidence is revision-specific. The baseline main at `3b2dc6a` contains 45 core and manifest-import tests. The backup review candidate at `493b40e` adds 15 independent backup/restore tests, for 60 total. A fresh Windows Python 3.14.9 run on 16 November 2026 passed 59 with one existing symlink-permission skip; the separate synthetic roundtrip exercise also passed. Muse independently reported 60 passed on Linux Python 3.12.3 on 16 November 2026. That Linux result is reviewer-reported, distinct from the Windows run verified on the laptop. See [BACKUP_REVIEW_20261116.md](BACKUP_REVIEW_20261116.md) for the published candidate review; older checked-in logs describe earlier revisions, not this 60-test run.

All tests use synthetic data, not the real collection. Passing regression tests is not production certification. No Blender/Godot adapter, 3D collision validation, 3D generation, write-capable GUI, schema migration engine or production deployment is implemented.

## Authorship and development
Samara supplied the product direction and organization requirements. Puck, OpenAI assistant, wrote this implementation, tests and synthetic fixtures. It is not evidence of unaided coding or professional engineering experience. Owner review and understanding are required before portfolio submission.

This is a new public repository. Its commits document genuine publication stages, not a fabricated long-term development record. Future history should reflect actual work and tests. No application has been submitted. Licensed under MIT; see LICENSE.

## Next real milestones
1. Validated manifest import with conflict preview ? merged into main as PR #1 (`3b2dc6a`).
2. Editable local UI and accessible thumbnails ? future.
3. Backup/restore ? implemented and reviewed as the candidate described above. Schema migration and its tests ? future.
4. A Godot adapter tested using synthetic geometry, separately from this planning schema ? future.

## Cross-project index
`layered_demo/project_index.json` links fictional OS, game and world projects through stable asset IDs and explicit proposed relationships. It includes status, revision and provenance; it is not an exhaustive real-work inventory. Private integration is separate.

## Start learning the current tool
See WALKTHROUGH.md for a small guided exercise. Manifest import is merged into main as PR #1. For backup/restore commands and revision-specific evidence, see the milestone section above. This repository is an organizer prototype, not an application submission or a claim of engineering experience.
