# DRAFT: manifest import for joint review

Not merged into main. This is a review draft, not a completed milestone. Only fictional test fixtures are used.

## Reproduce
```
python -m unittest test_import -v
```
Ten importer tests cover preview/no copied objects, copy/audit, duplicate-ID rejection, batch rejection, path traversal, corrupt objects, tested-status downgrade, schema rejection, same ID with different bytes and missing source objects.

## Requested conflict cases
- Same ID with different bytes: both preview and apply refuse with `Conflicting asset ID: sample-v1`. The existing destination hash and object stay unchanged.
- Missing object: both refuse with `Unsafe/missing source object`. Destination remains empty.

## Honest gaps for review
The current preview fails at the first conflict; it does NOT yet produce a complete per-asset conflict list or a same-ID/same-bytes vs different-bytes comparison. It offers no skip/rename/overwrite resolution. Preview creates an empty destination SQLite workspace, although it adds no rows or copied objects. Database changes are transactional, but an I/O failure can leave unreferenced copied objects. Concurrent filesystem changes/writers are not fully hardened. Exception handling and malformed-manifest coverage need further review. Imported tested claims are downgraded to unverified; source test evidence is not imported as independently verified evidence.

Discuss these behaviors before calling the milestone done. Do not use on valuable/private source material yet. Main remains the existing organizer. No application is submitted, and AI authorship remains as disclosed in README.
