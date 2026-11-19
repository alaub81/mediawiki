# Installation and configuration

Run commands from the repository root. The [README](../README.md#quick-start)
explains the public environment template, independent passwords, profiles and
compatibility requirements. Preserve existing credentials, volumes and project
names during updates; the fresh installer below is only for an empty wiki.

## New wiki with published images

Start from the README clone and `.env` preparation. Set the public URL and strong,
separate `MARIADB_ROOT_PASSWORD`, `MARIADB_PASSWORD` and `MEMCACHEPHP_ADMIN_PASS`.
For a minimal first installation use `COMPOSE_PROFILES=` and
`CLAMAV_ENABLED=false`, `MW_WANDA_ENABLED=false`, `MW_AUTO_UPDATE=false`.
Optional services can be enabled after the core stack works.

Prepare an ignored copy of the setup-only settings. Generate a fourth independent
password and enter its output as `MW_ADMIN_PASS` in `.env.setup`; also review
`MW_LANG`, `MW_ADMIN_USER` and the optional extension list:

```bash
cp .env.mwsetup .env.setup
chmod 600 .env.setup
# Generate the initial wiki administrator password for MW_ADMIN_PASS.
openssl rand -hex 32
```

Do not put a real administrator password into the tracked `.env.mwsetup` template.
The install overlay uses the standard in-container configuration path. It is
local and ignored, and leaves the generated file in the disposable writable
container until it is copied out:

```bash
cat > compose.install.override.yml <<'YAML'
services:
  mediawiki:
    env_file:
      - .env.setup
    environment:
      MW_CONFIG_FILE: /var/www/html/LocalSettings.php
      MW_AUTO_UPDATE: "false"
YAML

docker compose --env-file .env -f compose.yml -f compose.install.override.yml pull
docker compose --env-file .env -f compose.yml -f compose.install.override.yml up -d
```

Run the installer explicitly; the entrypoint does not run it automatically.
The configured MariaDB application user must already exist, as created by the
MariaDB service from `.env` on first database initialization:

```bash
docker compose --env-file .env -f compose.yml -f compose.install.override.yml \
  exec -T -u www-data mediawiki bash -lc '/usr/local/bin/mw-default-setup.sh'
```

**Known published-image issue with ClamAV disabled:** the installer can finish
creating the database and settings, then exit with `Invalid configuration for
parameter Antivirus` (the message may be localized). It writes a boolean where
MediaWiki 1.46 requires a string or `null`. Only for that exact failure, correct
the generated settings and finish the update before continuing:

```bash
docker compose --env-file .env -f compose.yml -f compose.install.override.yml \
  exec -T -u www-data mediawiki sed -i \
  's/^[[:space:]]*\$wgAntivirus = false;$/\$wgAntivirus = null;/' /var/www/html/LocalSettings.php
docker compose --env-file .env -f compose.yml -f compose.install.override.yml \
  exec -T -u www-data mediawiki php maintenance/run.php update --quick
```

Do not bypass configuration validation or ignore other installer failures. This
is a workaround for the published image; the runtime fix remains in the backlog.

Only copy into a new file. An existing live configuration must not be overwritten:

```bash
test ! -e data/mediawiki/conf/LocalSettings.php
mkdir -p data/mediawiki/conf
(umask 077; docker compose --env-file .env -f compose.yml -f compose.install.override.yml \
  exec -T mediawiki cat /var/www/html/LocalSettings.php > data/mediawiki/conf/LocalSettings.php)
test -s data/mediawiki/conf/LocalSettings.php
```

Give the container's PHP user access to this one file, without changing ownership
of the tracked configuration directory or making secrets readable to everyone:

```bash
docker compose --env-file .env -f compose.yml -f compose.install.override.yml \
  run --rm --no-deps --user root --entrypoint sh \
  -v ./data/mediawiki/conf/LocalSettings.php:/setup-config mediawiki \
  -c 'chown www-data:www-data /setup-config && chmod 640 /setup-config'
```

On Linux the resulting host file belongs to the image's `www-data` identity.
Use suitable administrative permissions for host-side editing and backups.
Docker Desktop may represent ownership differently; the container must be able
to read the file. The parent directory and other tracked examples remain unchanged.

Switch to the normal read-only mount and recreate MediaWiki. The normal stack no
longer receives `.env.setup`:

```bash
cat > compose.override.yml <<'YAML'
services:
  mediawiki:
    volumes:
      - ./data/mediawiki/conf/LocalSettings.php:/var/www/html/LocalSettings.php:ro
YAML

docker compose --env-file .env -f compose.yml -f compose.override.yml up -d --wait
docker compose --env-file .env ps
curl -fsS 'http://localhost:8080/api.php?action=query&meta=siteinfo&format=json'
```

Use the configured host/port in the API check if they differ from the example.
Expect healthy services and a JSON response containing `query`. Verify that the
home page loads. Keep the database and upload volumes and the generated file when
recreating containers. Do not run `down -v` on a real wiki.

Default Compose discovery loads `compose.override.yml` with `compose.yml`.
Explicit `-f` commands must include the override. The local files `.env.setup`,
`compose.install.override.yml` and `compose.override.yml` are Git-ignored.
After installation, store or remove the setup-only password file securely; it is
not required for normal startup. Review the [security notes](../README.md#security-notes).

## Local setup variant

The existing `compose.setup.yml` variant builds locally and mounts
`data/mediawiki/conf/mw_local_settings` at `/var/www/html/conf`. It uses the
tracked `.env.mwsetup` as its original template. For real credentials, copy that
file to an ignored `.env.setup` and use a local override changing the service's
`env_file` to `.env.setup`. Select the setup variant consistently for its startup,
exec, logs and stop commands. This historical variant is retained, not silently
rewritten by the documentation migration.

Its custom configuration path, schema-update and scheduled-maintenance behavior
need the end-to-end follow-up recorded in the [backlog](../notices_and_todos.md).
The standard-path published-image procedure above avoids relying on that custom
path. After generating a valid host settings file, the standalone `compose.dev.yml`
local-build path in the README mounts it read-only.

## Preconfigured example and browser installer alternatives

Both older installation alternatives remain available:

- **Preconfigured file:** copy `data/mediawiki/conf/LocalSettings.php.example`,
  replace its passwords/keys and review all enabled extensions. Mount it at the
  standard path. For an empty database, run the command printed by the entrypoint:
  `php maintenance/run.php installPreConfigured --conf /var/www/html/LocalSettings.php`
  inside the MediaWiki container. Do not point a new schema installation at an
  existing populated wiki database.
- **Browser setup:** initially start without an existing `LocalSettings.php`
  mount, visit the configured public URL and complete the setup wizard using the
  exact database settings from `.env`. Save its generated file to the host, then
  switch to the read-only mount. Retain the extensions/search/security settings
  required by this stack; the bare browser wizard does not configure them all.

Most `.env.mwsetup` values are direct values; review the administrator password.
`MW_DB_NAME`, `MW_DB_USER` and `MW_DB_PASS` can use the `MARIADB_*` values supplied
by Compose. Values in the service's `environment` take precedence over `env_file`,
including `MW_SITENAME`. The development variant originally reads `MW_DB_PASS`
through its env file. Preserve custom configuration choices when migrating.

## Configuration keys

The public example contains deliberately unusable placeholders for `$wgSecretKey`
and `$wgUpgradeKey`. If using that file, replace them with two independent values:

```bash
# Unique per-wiki secret key: 32 random bytes, encoded as 64 hex characters.
openssl rand -hex 32
# A separate upgrade key, used as the web-updater password.
openssl rand -hex 16
```

The normal MediaWiki installer generates keys itself. Keep existing private keys
for routine updates. If the old public example values were deployed, rotate them
as a separate security action and review sessions/integrations; do not assume
changing the example file changes an installed wiki. See MediaWiki's official
[secret-key](https://www.mediawiki.org/wiki/Manual:$wgSecretKey) and
[upgrade-key](https://www.mediawiki.org/wiki/Manual:$wgUpgradeKey) documentation.
