# Operations and recovery

## Updates

Preserve the Compose project name, database/upload volumes, credentials and
private `LocalSettings.php` when changing images. Back up first, read the release
notes and the README's [production migration notes](../README.md#production-upgrade-from-145x-to-146),
then test the same upgrade against a separate restored instance. Review extension
and search-backend compatibility before changing the MediaWiki release line.
An image rollback alone does not undo database schema changes.

Automatic schema updates are disabled in the public templates. Perform planned
schema migrations explicitly, with the correct mounted configuration and user,
after reviewing the relevant release's instructions. Do not run the fresh-wiki
installer against a populated database.

## Backups

A recoverable backup needs all of the following from the same maintenance window:

- A consistent MariaDB dump of the wiki database, including required database
  objects. Use a supported MariaDB backup/dump tool and the configured credentials;
  protect the dump as sensitive data.
- Uploaded files from the MediaWiki images volume.
- The private `LocalSettings.php`, environment/secret files and local Compose
  overrides, stored securely outside Git. Record the project name and image tags
  or digests so recovery uses the intended versions.
- Any additional operator-managed data and the configuration needed to rebuild
  search indexes. Search indexes alone are not a substitute for the wiki database.

Coordinate writes or use an appropriate maintenance window for a consistent
database/upload snapshot. Copying live MariaDB volume files is not a validated
logical backup. Do not include private backups in issues or CI artifacts.

## Restore verification

Restore into a separate Compose project with separate ports and volumes first.
Restore the database and matching uploads, provide the private configuration with
container-readable permissions, and use the recorded compatible image versions.
Verify a page, login, an uploaded file, a database-backed API request and search.
Rebuild CirrusSearch indexes when required using the README's
[indexing procedure](../README.md#building-the-cirrussearch-index).

Only switch production after the restored instance has been checked. Keep the
previous backup and a documented way back. Never use `docker compose down -v` on
a live wiki as an update or recovery step. This repository's isolated E2E tests
do not prove that an operator's production backup is restorable.

For normal checks and diagnostics, use the README's
[scheduled jobs](../README.md#scheduled-jobs),
[persistent volumes](../README.md#persistent-volumes) and
[troubleshooting](../README.md#troubleshooting) sections.
