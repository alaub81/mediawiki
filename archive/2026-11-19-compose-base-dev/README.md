# Compose snapshot before the shared-base/dev migration

Created on 2026-11-19 before changing the active Compose files and environment
templates. `SOURCE_COMMIT` records the source revision and `SHA256SUMS` verifies
these byte-for-byte copies of the original public root files.

These are historical references, not active deployment files. Their relative
paths originally referred to the repository root. Do not run these copies as a
standalone deployment from this archive directory. Review and copy back the
required files into the root when deliberately restoring the previous layout.

Existing private environment files and local Compose files were backed up under
`private/`, with restrictive permissions. That directory is ignored by Git and
must never be committed or included in public artifacts. Do not overwrite live
credentials or production data while restoring a public template.

The setup variant is retained as an unchanged standalone file in the active
root. Its migration is a separate step. See the current
[Compose documentation](../../docs/repository-structure.md).
