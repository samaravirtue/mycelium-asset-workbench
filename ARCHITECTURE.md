# Design decisions

## Boundary
Only explicit local files are copied. Source paths are not persisted automatically; callers supply a provenance description. SQLite holds classifications and append-only application audit events. Objects are named by SHA256, not arbitrary user paths. Display names do not become paths. Search uses in-memory casefold matching after parameter-free read; writes use SQL placeholders.

## Deduplication vs identity
Two domain associations may share bytes without becoming the same conceptual asset. Hash-named objects are deduplicated, IDs remain independent. IDs cannot be overwritten; corrections use new version IDs and `superseded` on old ones. This avoids silently replacing source material.

## Failure handling
Files are streamed, copied to a temporary file, re-hashed, then renamed into storage. Database transactions cover metadata and audit events. A crash between object rename and DB insert can leave an orphan object; no source deletion occurs. Existing corrupted objects stop intake. Export rechecks hashes. JSON export uses same-directory atomic replace. This is a single-user prototype; filesystem race resistance and simultaneous writers are not production-hardened. Do not expose the workspace to untrusted writers.

## Evidence
Status is a claim, not proof. A tested label requires a recorded description/reference and matching stored bytes. It cannot verify another engine's rendering, collision, scale or licensing. Gate checks and engine adapters are future work. Superseded assets remain visible in full catalog/export but never in the tested-only export.

## Compatibility
Schema version 1 manifests reference `objects/<hash>` relative to the catalog root; original filename is metadata. Exports are indices, not automatic object bundles or engine imports. Preserve the catalog `objects` directory beside manifests when transferring privately. Keep SQLite backups only while the app is closed.
