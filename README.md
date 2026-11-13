# Mycelium Asset Workbench

## What and why
A working local-first Python/SQLite organizer for layered creative assets. It is a shared foundation for OS and game workflows, not an OS or playable game. Domains contain underground, terrain, water, flora, structures and sky layers. Stable asset IDs connect references to proposed modules without treating pictures as production meshes.

The problem: images, plans and exported assets become hard to find and their completion status gets blurred. This prototype copies explicitly selected files, records provenance and hashes, retains originals, and exposes searchable reports and integrity-checked manifests.

## Run from a fresh checkout
Requires Python 3.10+ only. No dependencies, account, API key, paid services or network needed after download.
```sh
git clone https://github.com/samaravirtue/mycelium-asset-workbench.git
cd mycelium-asset-workbench
python -m unittest discover -s . -v
python demo.py
python workbench.py --workspace layered_demo/catalog search winter
python workbench.py --workspace layered_demo/catalog verify
```
On Windows use `py -3` in place of `python`. Open `layered_demo/layers.html` for the layer overview and `layered_demo/gallery.html` for the searchable report. These are read-only reports: regenerate after CLI catalog changes. GitHub displays HTML source; download the repo and open the generated files locally.

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
27 Windows automated tests: 26 passed, one symlink-privilege test skipped. The original 26-test core also passed on Linux before this expanded fixture. New expanded fixture has not been run on Linux. See WINDOWS_TEST_RUN.txt. No Blender/Godot adapter, collision validation, 3D generation, write-capable GUI or production deployment is implemented.

## Authorship and development
Samara supplied the product direction and organization requirements. Puck, OpenAI assistant, wrote this implementation, tests and synthetic fixtures. It is not evidence of unaided coding or professional engineering experience. Owner review and understanding are required before portfolio submission.

This is a new public repository. Its commits document genuine publication stages, not a fabricated long-term development record. Future history should reflect actual work and tests. No application has been submitted. Licensed under MIT; see LICENSE.

## Next real milestones
1. Validated manifest import with conflict preview.
2. Editable local UI and accessible thumbnails.
3. Backup/restore and schema migration tests.
4. A Godot adapter tested using synthetic geometry, separately from this planning schema.

## Cross-project index
`layered_demo/project_index.json` links fictional OS, game and world projects through stable asset IDs and explicit proposed relationships. It includes status, revision and provenance; it is not an exhaustive real-work inventory. Private integration is separate.

## Start learning the current tool
See WALKTHROUGH.md for a small guided exercise. Manifest import remains a future milestone, not part of this published version. This repository is an organizer prototype, not an application submission or a claim of engineering experience.
