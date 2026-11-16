# Backup/restore review candidate

Separate review branch, not main. Implementation based on c097242; adds 15 independent synthetic tests and a reproducible end-to-end exercise. AI-assisted implementation and testing are explicitly acknowledged. No real collection or manuscript is used.

Run `python -m unittest discover -v` then `python verify_milestone_roundtrip.py` (Windows: `py -3`). Latest Linux run: 60 passed. Actual Windows Python 3.14.9 run: 60 run, 59 passed, 1 pre-existing symlink-permission skip. The first Windows run exposed two unclosed connections in the added tests; fixed with explicit contextlib.closing and rerun successfully.

The exercise creates a fictional asset, backs up its workspace, verifies the archive, restores a new workspace, checks original bytes unchanged and refuses nonempty destination overwrite. Temporary example data is disposed after the run.

The original published backup draft omitted its earlier reported backup suite. These 15 tests are new independent coverage, not a reconstruction of the missing 79-pass result. Historical README and DRAFT_REVIEW claims predate this review.

Stop other workspace writers before backup. SQLite online backup is consistent for the database, not a multi-file transactional filesystem snapshot. Hashes check integrity, not authenticity. Restore supports Windows/Linux; there is no migration engine, editable GUI, cloud backup, encryption, or production certification. Existing protected originals remain untouched. Review before any merge.
