# Manifest import draft, review round 2

Status: draft branch only, not merged or production-ready.

## Changes for review
- Preview lists each asset with `add`, `skip-identical`, `conflict`, or `invalid`, plus reasons, counts, and `can_apply`.
- Same existing ID and verified bytes skips without modifying metadata, status, events, or objects.
- Same ID and different bytes conflicts. Duplicate IDs within one input manifest are conflicts (even when identical), avoiding ambiguous metadata selection.
- Invalid source entries do not hide later entries. Invalid top-level schema or unreadable destination remains a whole-request failure.
- CLI preview passes the workspace path, never initializes Catalog, and creates no destination directory or database. Existing databases are opened read-only/immutable; SQLite sidecars cause refusal rather than recovery/sidecar writes.
- Apply recomputes validation. Any conflict/invalid blocks the whole batch. Tested source claims are downgraded on added assets, not on skipped local assets.

## Try it
```sh
python -m unittest discover -v
python demo.py
python manifest_import.py layered_demo/manifest.json --objects-root layered_demo/catalog --workspace disposable_import
# Verify disposable_import still does not exist. Then explicitly apply:
python manifest_import.py layered_demo/manifest.json --objects-root layered_demo/catalog --workspace disposable_import --apply
python manifest_import.py layered_demo/manifest.json --objects-root layered_demo/catalog --workspace disposable_import
```
The final preview should say 24 skip-identical and zero add/conflict/invalid.

## Verified in this round
44 tests pass on Linux. Tests cover all four verdicts in one batch, both duplicate rows marked, absent-workspace CLI preview, byte/mtime preservation of existing destination during preview and identical apply, missing sources, same-ID/different-bytes conflict, no partial apply on invalid batch, and retained local tested metadata. These tests use synthetic files only.

## Still limited
- No rename/overwrite/resolution choices, GUI, or engine adapter.
- Identical means same ID and object bytes, not metadata equality; local metadata wins explicitly.
- Preview intentionally refuses SQLite sidecars; do not use against a concurrently edited workspace. No full adversarial multi-process/filesystem-race guarantee.
- Database writes roll back, but disk failure after copying can leave unreferenced object files or an initialized empty destination. Filesystem and SQLite are not one atomic transaction. Originals remain untouched.
- Existing legacy callers that construct Catalog themselves already create their workspace; use a path for side-effect-free preview.


## Windows follow-up correction
An actual laptop run with Python 3.14.9 exposed 13 cleanup errors: the SQLite connection context manager did not close preview connections. The snapshot now uses contextlib.closing. Added a regression asserting closure on successful reads and query exceptions.
Windows after correction: 45 tests run, 44 passed, one symlink-privilege skip, no errors (5.082s). See WINDOWS_FIXED_TEST_RUN.txt. This is an actual Windows laptop result, not hosted CI. The preceding 44-test Linux result applies to the previous revision; this correction still needs fresh Linux confirmation. No merge.
