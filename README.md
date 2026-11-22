# LHlab wiki — MediaWiki Docker Stack

A customizable Docker Compose stack from **LHlab wiki**, based on MediaWiki 1.46 with MariaDB, OpenSearch, CirrusSearch, Elastica, Memcached, ClamAV, scheduled maintenance jobs, and a custom MediaWiki image.

## Included services

- **MediaWiki 1.46** with Apache and PHP
- **MariaDB 12.3 LTS** as the database
- **OpenSearch 1.3.20** as the CirrusSearch backend
- **CirrusSearch** and **Elastica** from the MediaWiki `REL1_46` branches
- **Memcached** and the MemcachePHP administration UI
- **ClamAV** for upload scanning (optional `clamav` profile)
- **Elasticsearch 8.19** for Wanda (optional `elasticsearch` profile; separate from CirrusSearch's OpenSearch backend)
- **Supercronic** for MediaWiki jobs, sitemap generation, RottenLinks, and search-index maintenance

OpenSearch runs only on the internal Docker network and is not exposed publicly.
ClamAV and Wanda are disabled in the public environment templates. Enable their
Compose profiles and matching application flags together; see [ClamAV](#clamav)
and [Wanda and Elasticsearch](#wanda-and-elasticsearch).

## Important compatibility information

MediaWiki 1.46 and its matching CirrusSearch branch expect OpenSearch 1.3. Do not replace the configured image with an arbitrary OpenSearch 2.x or 3.x image.

This stack uses the Wikimedia OpenSearch image containing the search plugins expected by CirrusSearch:

```text
docker-registry.wikimedia.org/repos/search-platform/cirrussearch-opensearch-image:v1.3.20-12
```

The image is primarily intended for `linux/amd64`. On Apple Silicon, Docker may require amd64 emulation or a locally built Wikimedia OpenSearch image.

## Included MediaWiki extensions

The custom Dockerfile adds the following 16 extensions to the MediaWiki base
image. The list was checked against `resources/mediawiki/Dockerfile` and the
extensions present in the custom image:

- Lockdown
- Description2
- RelatedArticles
- MobileFrontend
- Elastica
- CirrusSearch
- ExternalData
- HitCounters
- TopTenPages
- RottenLinks
- intersection (DynamicPageList)
- WikiCategoryTagCloud
- CookieConsent
- WikiSEO
- Wanda
- WandaScore

`intersection` is the extension directory and load identifier; its displayed
extension name is **DynamicPageList**. It is one extension, not two.

The build downloads these extensions from the public Wikimedia GitHub mirrors
(`wikimedia/mediawiki-extensions-<name>`), except RottenLinks, which uses its
Miraheze GitHub repository. Wanda and RottenLinks use explicit commit pins.
These clones do not require Gerrit access.
Other clones prefer the matching `REL1_46` branch but currently fall back to
`main` or the default HEAD if it is absent. Check build logs and compatibility;
the fallback does not guarantee a matching release branch. See the
[extension-version backlog](notices_and_todos.md).

### Extension activation and skins

Files present in the image are not automatically active in every wiki. The
example `LocalSettings.php` loads the additional extensions listed above other than
Wanda/WandaScore; those two are conditional on `MW_WANDA_ENABLED=true`.
For fresh installation, an empty `MW_ACTIVE_EXTENSIONS` in the setup settings
selects all installed extensions except Wanda/WandaScore. A nonempty value
selects a space-separated list for the installer. Existing wikis retain the
extensions enabled in their own settings.

The custom Dockerfile currently installs no additional skins (`MW_INSTALL_SKINS`
is empty).

To see the extensions actually loaded by a running wiki, visit `Special:Version`
or query its API (authentication may be required for a private wiki):

```text
/api.php?action=query&meta=siteinfo&siprop=extensions&format=json
```

## Requirements

- Docker Engine
- Docker Compose 2.24.4 or newer
- Plan for about 3 GiB of memory available to Docker for the core services, or about 6 GiB when explicitly enabling the optional `clamav,elasticsearch` profiles. These are provisional capacity guidelines, not measured peak requirements.
- An amd64 host or amd64 container emulation for the Wikimedia OpenSearch image

RAM measurements on a Docker Desktop VM with 7.75 GiB allocated (27 September 2026, `docker stats`, roughly four seconds between samples):

| Profile | Containers | Highest sampled total | Observation |
| --- | ---: | ---: | --- |
| Core services, optional profiles disabled | 5 | 1.57 GiB | Two minutes, including startup from a stopped stack |
| Full optional profiles (`clamav,elasticsearch`) | 7 | 3.61 GiB | Four minutes, adding the optional services to the running core stack |

An earlier full-stack snapshot showed 4.07 GiB (ClamAV 0.99 GiB, Elasticsearch 1.26 GiB, OpenSearch 1.44 GiB, other services 0.39 GiB). Each measured profile answered 120 read-only API requests (site information, search, recent changes) successfully. A bounded search-index update processed only one page, and the MediaWiki database updater found no pending schema changes. At the end of the full-profile run, cgroup swap usage was zero and no container had been OOM-killed or restarted. These short runs on a nearly empty wiki do not establish minimum RAM or worst-case peaks. Leave room for larger indexes and maintenance jobs and, on Docker Desktop, allocate the memory to the Docker VM.

## Quick start

The current Compose files have these roles:

| File | Purpose |
| --- | --- |
| `compose.yml` | Shared runtime base using published project images |
| `compose.config.yml` | Normal-operation overlay mounting the existing settings file read-only |
| `compose.dev.yml` | Local-build overlay for both project images; load after the base and config overlay |
| `compose.setup.yml` | Local-build setup variant with a writable configuration directory |
| `compose.secrets.yml` | Password-file overlay, combined with a base file and the configuration mount |
| `tests/compose.test.yml` | CI/E2E overlay, combined with the production base |

The commands below use these current filenames. When migrating an existing
customized deployment, first follow the
[Compose filename migration guide](docs/repository-structure.md#compose-filename-migration).
It retains the previous filenames and explicit-file commands for older setups.
Keep the same project name, configuration mounts and volumes; do not switch files
implicitly or replace live settings with a template. `PROJECT_NAME` controls the
bridge-interface names here; preserve any separate `-p`/`COMPOSE_PROJECT_NAME`
setting that identifies your existing Compose project.

Select normal operation in `.env` with
`COMPOSE_FILE=compose.yml:compose.config.yml`. For local builds, use
`COMPOSE_FILE=compose.yml:compose.config.yml:compose.dev.yml` instead. Compose
loads the files in that order for ordinary `docker compose` commands. Explicit
`-f` arguments replace this selection. See the
[selection and migration guide](docs/compose-modes.md), including existing local
overrides, secrets, archived originals and the unchanged standalone setup variant.

### 1. Create the environment file

Clone the repository and copy the public configuration template:

```bash
git clone https://github.com/alaub81/mediawiki.git
cd mediawiki
cp .env.example .env
chmod 600 .env
```

Generate independent credentials for the database administrator, database
application user and MemcachePHP administration UI. Run each command separately
and put its output into the named variable in `.env`:

```bash
# MARIADB_ROOT_PASSWORD: database administration, not the application login.
openssl rand -hex 32
# MARIADB_PASSWORD: shared application database login used by the wiki.
openssl rand -hex 32
# MEMCACHEPHP_ADMIN_PASS: Basic Auth for the administration UI.
openssl rand -hex 32
```

Each call generates 32 random bytes encoded as 64 hexadecimal characters. Keep
these values different. For a new wiki, generate a fourth value later for
`MW_ADMIN_PASS` in the ignored `.env.setup`. Keep existing credentials and volumes
when upgrading; changing an environment file does not change stored DB accounts.
The public templates keep optional ClamAV/Wanda services and automatic schema
updates disabled until you intentionally enable them. Review the public wiki URL.

Example:

```dotenv
PROJECT_NAME=lhwiki
MW_VERSION=1.46
MW_HTTP_PORT=8080
MW_SERVER_URL=http://localhost:8080
MW_AUTO_UPDATE=false

MARIADB_VERSION=12.3
MARIADB_ROOT_PASSWORD=change-this-root-password
MARIADB_DATABASE=wikidb
MARIADB_USER=wikiuser
MARIADB_PASSWORD=change-this-database-password

OPENSEARCH_VERSION=v1.3.20-12
MW_OPENSEARCH_URL=http://opensearch:9200
OPENSEARCH_HEAP_MIN=512m
OPENSEARCH_HEAP_MAX=512m

MEMCACHED_VERSION=alpine
MEMCACHED_CACHE_MB=32

TZ=Europe/Berlin
```

### 2. Prepare `LocalSettings.php`

For an existing wiki, preserve its current `LocalSettings.php` at:

```text
data/mediawiki/conf/LocalSettings.php
```

Its CirrusSearch configuration must contain:

```php
wfLoadExtension( 'CirrusSearch' );
wfLoadExtension( 'Elastica' );

$wgCirrusSearchServers = [ 'opensearch' ];
$wgSearchType = 'CirrusSearch';
```

For an existing installation, retain its mounts and keys; do not run the fresh
installer over its database. For a **new** wiki using published images, follow
[the first-install procedure](docs/installation.md#new-wiki-with-published-images).
It prepares ignored `.env.setup` and `compose.install.override.yml` files, runs
`mw-default-setup.sh` explicitly, copies the resulting configuration to the host,
and switches to the read-only `compose.config.yml` mount. The entrypoint does not
run this installer automatically. The guide also preserves the local setup,
preconfigured-template and browser installer alternatives.

When copying `data/mediawiki/conf/LocalSettings.php.example` instead of using the
installer, replace both `$wgSecretKey` and `$wgUpgradeKey` placeholders with
separate random values before starting. Generate the secret key with
`openssl rand -hex 32` and the upgrade key with a separate `openssl rand -hex 16`.
The installer generates its own keys. Preserve live keys during ordinary updates;
if the old public example keys were ever deployed, rotate them deliberately.
See the [configuration-key guidance](docs/installation.md#configuration-keys).
If `LocalSettings.php` is already present but its MediaWiki database has not been installed, `MW_AUTO_UPDATE=true` skips the updater and prints the `installPreConfigured` command with the configured file path. Run that installation command before relying on scheduled maintenance jobs.

When `MW_WANDA_ENABLED=true`, provide the OpenAI API key as `MW_WANDA_OPENAI_API_key` in `.env` or mount a Docker secret named `mw_wanda_openai_api_key` into the MediaWiki container at `/run/secrets/mw_wanda_openai_api_key`. The secret takes precedence. The Compose examples pass the `.env` value into the container as `MW_WANDA_OPENAI_API_KEY`, matching the uppercase lookup in `dockerSecret()`. A Docker secret must also be granted to the `mediawiki` service in your Compose configuration.

For a new checkout using an existing settings file, select the tracked normal
configuration overlay in `.env`:

```dotenv
COMPOSE_FILE=compose.yml:compose.config.yml
```

The selected config overlay mounts the settings file read-only. When selecting
files with `-f`, include it explicitly. An existing `compose.override.yml` is not
automatically appended to `COMPOSE_FILE`: retain it as the last entry if it holds
personal settings. Keep custom project names and volume mounts when reusing an
existing deployment. No existing local override needs to be overwritten.

### Use password files with Docker Compose

`compose.secrets.yml` mounts the five files from `./secrets/` and removes the password environment variables inherited from `compose.yml`. It also changes the MariaDB health check to read the root password file. Use `.env.secrets` for the remaining, non-secret settings:

For a new deployment, copy the public placeholders to an ignored directory:

```bash
mkdir -p secrets
chmod 700 secrets
cp -n secrets_example/* secrets/
chmod 600 secrets/*
```

These permissions protect the host copies. On Linux, also arrange ownership or
ACLs so each mounted secret is readable by its consuming service user (including
MediaWiki's `www-data`), without making it world-readable. Compose file-backed
secrets inherit host-file permissions; `chmod 600` alone does not guarantee access
from a different container UID. Validate this before switching an existing wiki.

Replace `mariadb_root_password`, `mw_db_pass`, `mw_admin_pass` and
`memcachephp_admin_pass` with four independent password values. Provide a real
`mw_wanda_openai_api_key` only when enabling Wanda; the template is not a usable
API key. Keep `.env.secrets` non-secret. Include your configuration override:

```bash
docker compose --env-file .env.secrets config --quiet
docker compose --env-file .env.secrets up -d
```

The overlay requires Docker Compose 2.24.4 or newer for `!override`. Include the appropriate `LocalSettings.php` mount through your deployment override or existing customized base file. Replace the example passwords and the placeholder OpenAI key in `./secrets/` before deployment. If the MariaDB data volume already exists, its stored passwords must match the secret files; changing the files does not change database accounts. The `.env.secrets` file has no password assignments. With this overlay, inherited password environment variables are removed even if they are present in an env file, but keeping them there is unnecessary and makes an accidental start without the overlay use those values.

### 3. Start the production stack

After an existing settings file is mounted or the fresh-install procedure has
completed, start with the published MediaWiki and MemcachePHP images:

```bash
docker compose --env-file .env up -d --wait
```

### 4. Inspect service health

```bash
docker compose ps
docker compose logs --tail 100 mediawiki
docker compose logs --tail 100 opensearch
```

The wiki is available by default at:

```text
http://localhost:8080
```

### Debugging

Set `MW_DEBUG=true` in `.env` to enable `$wgShowExceptionDetails`, `$wgShowDebug`, and `$wgDevelopmentWarnings` together. The default is `false`. These settings can expose internal details in page output, so turn them off again after debugging. `MW_DEPRECATION_RELEASE_LIMIT=1.43` optionally limits MediaWiki deprecation warnings to features deprecated through release 1.43; leave it empty to see all deprecations. This value is a release number, not a boolean. The Compose configuration passes both variables to the MediaWiki container. Recreate the container after changing `.env`, for example with `docker compose --env-file .env up -d --force-recreate mediawiki`.

## Build and run locally

To build from the checkout, prepare the same `.env` and settings file as above.
Set this selection in `.env`; keep its other settings and credentials:

```dotenv
COMPOSE_FILE=compose.yml:compose.config.yml:compose.dev.yml
```

The dev overlay only changes build settings and the two project image names.
The shared config overlay mounts `data/mediawiki/conf/LocalSettings.php` read-only.
Start the selected stack with:

```bash
docker compose --env-file .env up -d --build
```

Check the locally built stack with `docker compose ps` and
`docker compose logs --tail 100 mediawiki`. Keep the same `.env` selection for
later build/log/stop commands and preserve any existing `-p`/`COMPOSE_PROJECT_NAME`
setting. Alternatively, specify all three files explicitly with `-f`.
The dev file is now an overlay, not a standalone stack. A local build does not
initialize an empty database automatically. Switch back to published images by
removing `:compose.dev.yml` from `COMPOSE_FILE` and recreate the services.
For a fresh local installation, see [local setup](docs/installation.md#local-setup-variant).
Build arguments for extension/skin lists are not wired into the current Dockerfile;
see the [open backlog](notices_and_todos.md) before relying on custom build arguments.

## Repository layout

```text
.
├── compose.yml
├── compose.config.yml
├── compose.dev.yml
├── compose.setup.yml
├── compose.secrets.yml
├── .env.example
├── archive/
├── .github/
│   ├── FUNDING.yml
│   ├── ISSUE_TEMPLATE/
│   ├── PULL_REQUEST_TEMPLATE.md
│   ├── dependabot.yml
│   └── workflows/
├── docs/
│   ├── README.md
│   ├── repository-structure.md
│   └── examples/
├── tests/
│   ├── compose.test.yml
│   └── memcachephp_security_test.py
├── tools/
│   └── get-last-git-commit.sh
├── resources/
│   ├── memcachephp/
│   │   ├── .dockerignore
│   │   ├── Dockerfile
│   │   └── memcache.php
│   └── mediawiki/
│       ├── .dockerignore
│       ├── Dockerfile
│       ├── favicon/
│       ├── patches/
│       ├── mediawiki-entrypoint.sh
│       ├── mw-default-setup.sh
│       ├── generate-opensearch-index.sh
│       ├── update-cirrussearch-index.sh
│       ├── generate-sitemap.sh
│       └── generate-rottenlinks.sh
└── data/
    ├── clamav/
    └── mediawiki/
        ├── conf/
        └── logo/
```

Each image has a self-contained build context under `resources/<image>/`.
The MediaWiki directory includes its scripts, Apache configuration, favicons and
extension patches; MemcachePHP includes its PHP application. Compose files,
runtime configuration under `data/`, tests and repository tooling remain outside
the image contexts. Host-side utilities live under `tools/`; the NGINX example
lives under `docs/examples/`. See the [documentation index](docs/README.md) and
[Compose filename migration](docs/repository-structure.md#compose-filename-migration)
before updating an existing installation.

To build either image directly from the repository root:

```bash
docker build -t mediawiki-custom resources/mediawiki
docker build -t memcachephp resources/memcachephp
```

CI, release builds, Renovate and Dependabot use the same image directories.
Scheduled rebuilds of historical tags also support the previous root-level
Dockerfiles and repository-wide build context.

## OpenSearch configuration

The Compose configuration should use the following service definition:

```yaml
services:
  opensearch:
    platform: ${OPENSEARCH_PLATFORM:-linux/amd64}
    image: docker-registry.wikimedia.org/repos/search-platform/cirrussearch-opensearch-image:${OPENSEARCH_VERSION:-v1.3.20-12}
    restart: unless-stopped
    environment:
      - TZ=${TZ:-UTC}
      - discovery.type=single-node
      - bootstrap.memory_lock=true
      - OPENSEARCH_JAVA_OPTS=-Xms${OPENSEARCH_HEAP_MIN:-512m} -Xmx${OPENSEARCH_HEAP_MAX:-512m}
    volumes:
      - data_osdata:/usr/share/opensearch/data
    ulimits:
      memlock:
        soft: -1
        hard: -1
      nofile:
        soft: 65536
        hard: 65536
    healthcheck:
      test:
        - CMD-SHELL
        - curl -fsS 'http://localhost:9200/_cluster/health?wait_for_status=yellow'
      interval: 15s
      timeout: 10s
      retries: 20
      start_period: 60s
    networks:
      backend-nw:

volumes:
  data_osdata:
```

The correct heap variable is `OPENSEARCH_JAVA_OPTS`. `OS_JAVA_OPTS` is not used by OpenSearch.

The MediaWiki service must wait for OpenSearch and receive the internal URL:

```yaml
services:
  mediawiki:
    depends_on:
      opensearch:
        condition: service_healthy
    environment:
      MW_OPENSEARCH_URL: "${MW_OPENSEARCH_URL:-http://opensearch:9200}"
```

## Building the CirrusSearch index

On a fresh installation, `mw-default-setup.sh` builds the initial CirrusSearch index after the database update. The commands below rebuild an index manually, for example after a migration.

OpenSearch data cannot be reused directly from an Elasticsearch data volume. After migrating, create a fresh OpenSearch volume and rebuild the search index from MediaWiki.

### Verify OpenSearch

```bash
docker compose exec -T opensearch \
  curl -fsS http://localhost:9200/
```

With the default `v1.3.20-12` image tag, the response should report OpenSearch
1.3.20. If you deliberately selected another compatible tag, check that version.

List the installed plugins:

```bash
docker compose exec -T opensearch \
  sh -lc 'bin/opensearch-plugin list'
```

### Rebuild the complete index

```bash
docker compose exec -T mediawiki \
  php maintenance/run.php update --quick

docker compose exec -T mediawiki \
  php maintenance/run.php CirrusSearch:UpdateSearchIndexConfig --startOver

docker compose exec -T mediawiki \
  php maintenance/run.php CirrusSearch:ForceSearchIndex

docker compose exec -T mediawiki \
  php maintenance/run.php CirrusSearch:UpdateSuggesterIndex
```

Alternatively, use the bundled helper:

```bash
docker compose exec -T mediawiki \
  /usr/local/bin/generate-opensearch-index.sh
```

The `--startOver` command deletes and recreates only the CirrusSearch indexes. It does not delete MediaWiki database content or uploaded files.

### Verify the index

```bash
docker compose exec -T opensearch \
  curl -fsS 'http://localhost:9200/_cat/indices?v'
```

For the default database name, indexes or aliases beginning with the following value should appear:

```text
wikidb_content
```

Verify the configured MediaWiki search backend:

```bash
docker compose exec -T mediawiki sh -lc \
  'printf "%s\n" "echo \$wgSearchType, PHP_EOL;" | php maintenance/run.php eval'
```

The expected output is:

```text
CirrusSearch
```

## Migrating from Elasticsearch

1. Stop the current stack.
2. Replace the Elasticsearch service with the OpenSearch service.
3. Rename `MW_ES_URL` to `MW_OPENSEARCH_URL` and `ES_VERSION` to `OPENSEARCH_VERSION`.
4. Rename `ES_HEAP_MIN` and `ES_HEAP_MAX` to `OPENSEARCH_HEAP_MIN` and `OPENSEARCH_HEAP_MAX`.
5. Change `$wgCirrusSearchServers` from `elasticsearch` to `opensearch`.
6. Use a new `data_osdata` volume; do not mount the old Elasticsearch data volume into OpenSearch.
7. Start OpenSearch and wait until its health status is yellow or green.
8. Rebuild the CirrusSearch indexes with `--startOver`.
9. Run the application and E2E tests.

The old Elasticsearch volume can remain untouched until the migration has been verified. Remove it only when it is no longer needed.

## Scheduled jobs

### MediaWiki job queue

Enable periodic MediaWiki jobs with:

```dotenv
MW_JOBS_CRON=true
```

### CirrusSearch index maintenance

```dotenv
MW_CS_INDEX_UPDATE=true
MW_CS_INDEX_CRON=15 * * * *
MW_CS_INDEX_RUN_ON_START=true
MW_OPENSEARCH_URL=http://opensearch:9200
```

The index-maintenance script first checks whether the expected content and general aliases exist. Missing indexes are rebuilt before the suggester index is updated.

### Sitemap generation

```dotenv
MW_SITEMAP_GENERATION=true
MW_SITEMAP_CRON=20 */12 * * *
MW_SITEMAP_RUN_ON_START=true
MW_SITEMAP_IDENTIFIER=wiki
MW_SITEMAP_URLPATH=sitemap
MW_SITEMAP_SKIP_REDIRECTS=true
```

The generated sitemap index is available through `/sitemap.xml`.

### RottenLinks

```dotenv
MW_ROTTENLINKS_GENERATION=true
MW_ROTTENLINKS_CRON=30 */12 * * *
MW_ROTTENLINKS_RUN_ON_START=false
```

## ClamAV

Enable the Compose profile and MediaWiki integration:

```dotenv
COMPOSE_PROFILES=clamav
CLAMAV_ENABLED=true
CLAMAV_HOST=clamav
CLAMAV_PORT=3310
```

Disable both the profile and `CLAMAV_ENABLED` if ClamAV is not required.

## Wanda and Elasticsearch

Wanda and WandaScore are installed in the image but loaded conditionally by the
example and setup-generated settings. To enable them, configure a real API key
and start their dedicated Elasticsearch service:

```dotenv
COMPOSE_PROFILES=elasticsearch
MW_WANDA_ENABLED=true
MW_WANDA_OPENAI_API_key=replace-with-your-own-api-key
MW_ELASTICSEARCH_URL=http://elasticsearch:9200
ELASTICSEARCH_VERSION=8.19.21
ELASTICSEARCH_HEAP_MIN=512m
ELASTICSEARCH_HEAP_MAX=512m
```

Use `COMPOSE_PROFILES=clamav,elasticsearch` when enabling both optional services.
The `.env` key's spelling above matches the public template; Compose passes it
into the container as `MW_WANDA_OPENAI_API_KEY`. The password-file alternative
is described under [Use password files with Docker Compose](#use-password-files-with-docker-compose).
Elasticsearch serves Wanda; CirrusSearch continues using OpenSearch. Keep both
search services internal. The example settings disable Wanda's automatic full
reindex; perform the initial reindex deliberately after configuration:

```bash
docker compose exec -T -u www-data mediawiki \
  php maintenance/run.php extensions/Wanda/maintenance/ReindexAllPages.php
```

## Memcached and MemcachePHP

Example configuration:

```dotenv
MEMCACHED_VERSION=alpine
MEMCACHED_CACHE_MB=32
MW_MEMCACHED_SERVERS=memcached:11211
MEMCACHEPHP_SERVERS=${MW_MEMCACHED_SERVERS}
MEMCACHEPHP_ADMIN_USER=admin
MEMCACHEPHP_ADMIN_PASS=change-this-password
MEMCACHEPHP_DATE_FORMAT=Y-m-d H:i:s
MEMCACHEPHP_GRAPH_SIZE=220
MEMCACHEPHP_MAX_ITEM_DUMP=100
```

The MemcachePHP UI is reverse-proxied through MediaWiki at:

```text
/memcacheui/
```

The UI requires Basic Auth. Deleting an item or flushing a server uses a POST form with a session CSRF token; old `op=5` and `op=6` GET links no longer perform these actions.

## Persistent volumes

- `data_db` stores the MariaDB database.
- `data_mw_images` stores uploaded MediaWiki files.
- `data_osdata` stores OpenSearch indexes.
- `data_esdata` stores the optional Wanda Elasticsearch data.
- `clamav_db` stores ClamAV signatures.

The OpenSearch index is derived data and can be rebuilt from the MediaWiki database. Database and uploaded-file backups remain essential.
The live `LocalSettings.php` is a separate host-mounted file, not part of those
named volumes. Preserve it together with private environment/secret files and
deployment overrides; see [operations and recovery](docs/operations.md).

## Development and checks

Run the shared local checks from the repository root:

```bash
./tests/linter-check.sh
./tests/test-check.sh
./tests/integration-check.sh
./tests/e2e-check.sh
```

The linter prepares pinned tools in ignored, isolated directories. The test
command runs offline regressions and resolves the Compose examples without
starting containers. The integration command runs the existing MemcachePHP
security test with disposable containers and requires a running Docker daemon.
The E2E command builds both current-source images once and runs the full isolated
MediaWiki suite. CI reuses its already built images with `--skip-build`.
See [local development and checks](docs/development.md) for requirements,
tool versions, test coverage and the staged CI migration.
The [pre-commit checklist](docs/development.md#before-every-commit) distinguishes
the checks required for every commit from additional tests by change type.

## CI and E2E tests

CI runs the shared linters and offline checks once, then tests current-source
MediaWiki and MemcachePHP images on native amd64 and arm64 runners. Each image is
built once per architecture and reused for E2E, security tests and Trivy. Only
the third-party amd64 OpenSearch image uses emulation on arm64. Documentation-only
changes skip application builds; unknown/shared inputs run the complete stack.
The final `CI required` status rejects failed, cancelled or unexpectedly skipped checks.

Trivy scans each own image once to full JSON and derives full SARIF plus a
fixable HIGH/CRITICAL gate. Complete reports and E2E diagnostics are retained for
seven days even after a gate failure; SARIF is also uploaded to Code Scanning on
public main pushes. PRs retain the full reports as artifacts without requiring
Code Scanning write access. See the [CI and scan policy](docs/ci.md).

The CI workflow and local dev overlay inherit OpenSearch from `compose.yml`.
Keep settings consistent with the still-standalone setup variant:

- `compose.yml`
- `compose.setup.yml`

CI adds `tests/compose.test.yml` to the production base for isolated builds.
The E2E checks address the service as `opensearch`; for a normally started stack,
the equivalent diagnostic is:

```bash
docker compose exec -T opensearch sh -lc \
  "curl -fsS --max-time 4 'http://localhost:9200/_cat/health?h=status' \
  | grep -Eq 'yellow|green'"
```

Plugin diagnostics use:

```bash
docker compose exec -T opensearch \
  sh -lc 'bin/opensearch-plugin list || true'
```

If overriding search settings in CI, use the current variable names:

```dotenv
MW_OPENSEARCH_URL=http://opensearch:9200
OPENSEARCH_VERSION=v1.3.20-12
OPENSEARCH_HEAP_MIN=512m
OPENSEARCH_HEAP_MAX=512m
```

## Dependency updates

For dependency PR timing, Supercronic automerge, compatibility limits and the
division between Renovate and Dependabot, see the [dependency policy](docs/dependencies.md).

## Releases

Push the source commit and wait for successful default-branch CI before pushing
a stable `vMAJOR.MINOR.PATCH` tag. The release workflow checks that exact commit,
builds changed images or reuses previous immutable digests, and runs full E2E and
Trivy checks on native amd64 and arm64 runners. Only complete successful results
can update public image aliases and create English release notes.

Tuesday refreshes and manual runs with `rebuild_tags=true` rebuild the selected
recent tags without replacing existing release notes. Existing HIGH/CRITICAL
findings remain blocking. See [release operation and recovery](docs/releases.md).

## Production upgrade from 1.45.x to 1.46

This checklist covers the changes since `v1.45.5`. Keep the existing production Compose project, database volume, uploaded files, and `LocalSettings.php`; do not replace the live settings file with the example or run `docker compose down -v`.

| Area | Change to review |
| --- | --- |
| Images | MediaWiki `1.45` → `1.46`; MariaDB `11.8` → `12.3` LTS; Supercronic `0.2.45` → `0.2.51` in the current Dockerfile. Pin the production image tags you intend to run. |
| Search | CirrusSearch now uses the Wikimedia OpenSearch image `v1.3.20-12` and a new `data_osdata` volume. Rename `ES_VERSION` → `OPENSEARCH_VERSION`, `MW_ES_URL` → `MW_OPENSEARCH_URL`, and `ES_HEAP_MIN`/`ES_HEAP_MAX` → `OPENSEARCH_HEAP_MIN`/`OPENSEARCH_HEAP_MAX`. `OPENSEARCH_PLATFORM` defaults to `linux/amd64`. The old Elasticsearch volume is not an OpenSearch data volume. |
| Optional services | Elasticsearch `8.19.21` is now separate and used by Wanda 3. Set `MW_WANDA_ENABLED` together with the `elasticsearch` Compose profile and review `MW_ELASTICSEARCH_URL`, `ELASTICSEARCH_VERSION`, `ELASTICSEARCH_HEAP_MIN`, and `ELASTICSEARCH_HEAP_MAX`. `CLAMAV_VERSION` is new; keep `CLAMAV_ENABLED` and the `clamav` profile in sync. |
| Wiki configuration | `MW_SITENAME` and `MW_METANAMESPACE` can now supply site names. The example `LocalSettings.php` changed its database name from `wiki` to `wikidb`: retain the **actual production database name and credentials**. Review the new file-extension allowlist, searchable namespaces, and conditional Wanda configuration before merging settings. |
| Extensions | The image pins Wanda 3 and an updated RottenLinks commit, adds ExternalData, and no longer pins CookieConsent to its old commit. The example settings now load ExternalData and CheckUser. The image also applies a private-wiki RelatedArticles patch. Review the production extension list. |
| Maintenance and UI | `MW_CS_INDEX_CRON=15 * * * *` now runs at minute 15 each hour. MemcachePHP can read `MEMCACHEPHP_ADMIN_PASS_FILE` when a password file is mounted; its health check supports this too. |

Before upgrading, make verified backups of the MariaDB database, `data_mw_images`, and the live `LocalSettings.php`. The commands below assume the current Compose filenames and default deployment override. For a customized or older deployment, select the same files and project consistently as described in the [migration guide](docs/repository-structure.md#compose-filename-migration). Perform the following steps during a maintenance window:

1. Stop MediaWiki while the old database is still running: `docker compose --env-file .env stop mediawiki`. Run `git pull` to get the new stack files.
2. Update the **existing** production `.env`, Compose configuration (`compose.yml` and your deployment overrides in the current layout), and mounted `LocalSettings.php` using their example files as references. Do not replace the live files wholesale: retain the actual database name, credentials, uploaded-file mounts, and other production settings. Set `MARIADB_VERSION=12.3` and the new OpenSearch variables, and point `$wgCirrusSearchServers` at `opensearch`. Changing MariaDB password variables does not change credentials in an existing database volume. Keep `MW_WANDA_ENABLED=false` until its API key and separate Elasticsearch service are ready. If you use a nonstandard `MW_CONFIG_FILE`, pass it **into the container** and point it at the mounted file; merely placing it in `.env` is not enough with the example Compose file.
3. Pull the new images: `docker compose --env-file .env pull`.
4. If the old Elasticsearch search volume is no longer needed, stop and remove the container using it, identify the **exact** old project volume with `docker volume ls`, and remove only that volume with `docker volume rm <old-project>_data_esdata`. Never remove `data_db` or `data_mw_images`. The new Compose file also uses `data_esdata` for Wanda's optional Elasticsearch service, so check whether that service uses the volume before deleting it. The old search volume can be retained until the migration has been verified.
5. Start only the new MariaDB image: `docker compose --env-file .env up -d database`. Once it is healthy, run `docker compose --env-file .env exec --user root database mariadb-upgrade --user=root --password` and enter the **existing** database root password at the prompt. Run `docker compose --env-file .env restart database` and verify its health with `docker compose --env-file .env ps`. The Compose file does not set `MARIADB_AUTO_UPGRADE`, so the system-table upgrade does not run automatically. See the [MariaDB upgrade guide](https://mariadb.com/docs/server/clients-and-utilities/deployment-tools/mariadb-upgrade).
6. Set `MW_AUTO_UPDATE=true` in `.env`, then start MediaWiki with `docker compose --env-file .env up -d mediawiki`. The entrypoint runs MediaWiki's `maintenance/run.php update` before Apache when it finds `LocalSettings.php`. Check `docker compose --env-file .env logs mediawiki` for a successful update. This MediaWiki schema update is separate from `mariadb-upgrade`; see the [MediaWiki updater documentation](https://www.mediawiki.org/wiki/Manual:Update.php).
7. Rebuild the CirrusSearch index once with `docker compose --env-file .env exec -T mediawiki /usr/local/bin/generate-opensearch-index.sh`. This recreates search indexes, not wiki pages. If enabling Wanda, configure a real API key and run its initial full reindex separately.
8. After the schema update and index rebuild succeed, set `MW_AUTO_UPDATE=false` in `.env` and apply it with `docker compose --env-file .env up -d --force-recreate mediawiki`. Check `Special:Version`, page reads and edits, uploads, search, scheduled jobs, and the health of MariaDB and OpenSearch before ending the maintenance window.

The [MediaWiki 1.46 upgrade notes](https://www.mediawiki.org/wiki/Release_notes/1.46) and [upgrade manual](https://www.mediawiki.org/wiki/Manual:Upgrading) cover core changes beyond this Docker stack.

## Updating MediaWiki

When upgrading to another MediaWiki branch:

1. Update the MediaWiki base-image version.
2. Review the matching `RELx_xx` branch or tested commit for each extension. Check build logs for branch fallbacks; the current fallback to `main`/default HEAD is not a compatibility guarantee.
3. Check the CirrusSearch compatibility requirements before changing the OpenSearch version.
4. Enable `MW_AUTO_UPDATE=true` for the first controlled startup.
5. After the MediaWiki schema update succeeds, set `MW_AUTO_UPDATE=false` again.
6. Rebuild the CirrusSearch index when required by the CirrusSearch upgrade notes.

Do not combine MediaWiki 1.46 with CirrusSearch or Elastica from `master`.

## Troubleshooting

### `Unknown filter type [truncate_norm]`

This usually indicates that CirrusSearch is connected to Elasticsearch or to a plain OpenSearch image without the expected Wikimedia search plugins.

Confirm that the configured image is:

```text
docker-registry.wikimedia.org/repos/search-platform/cirrussearch-opensearch-image:v1.3.20-12
```

Then recreate the OpenSearch container and rebuild the index.

### MediaWiki cannot resolve `opensearch`

Ensure both services use the same Docker network and that `LocalSettings.php` contains:

```php
$wgCirrusSearchServers = [ 'opensearch' ];
```

### OpenSearch ignores the configured heap size

The environment variable must be named `OPENSEARCH_JAVA_OPTS`:

```yaml
- OPENSEARCH_JAVA_OPTS=-Xms512m -Xmx512m
```

### CirrusSearch reports `Elastica\Client` as missing

Ensure that Elastica and CirrusSearch were installed from the MediaWiki 1.46 release branches and that their Composer dependencies were installed during the image build.

### Search results are empty after migration

Rebuild the index:

```bash
docker compose exec -T mediawiki \
  php maintenance/run.php CirrusSearch:UpdateSearchIndexConfig --startOver

docker compose exec -T mediawiki \
  php maintenance/run.php CirrusSearch:ForceSearchIndex
```

## Help and security

The [documentation index](docs/README.md) also links installation, backup/restore
guidance and the [Standard v1 status](docs/standard-v1.md), including open work.

For failures, start with the [troubleshooting examples](#troubleshooting) and
collect the image tag/commit, host architecture, Docker/Compose versions, enabled
profiles, service health and relevant sanitized logs. Open a
[bug report](https://github.com/alaub81/mediawiki/issues/new/choose) with those
facts. Do not attach `.env`, cookies, API keys, secret files or private wiki content.
Report suspected vulnerabilities privately according to [SECURITY.md](SECURITY.md).

## Security notes

- Never expose OpenSearch port 9200 directly to the internet.
- Keep the OpenSearch service on the internal backend network.
- Replace all example passwords before deployment.
- Prefer Docker secrets or another secret-management mechanism for production credentials.
- Back up the MariaDB database and MediaWiki uploads regularly.
- Pin production image versions instead of using floating `latest` tags.

## Support this project

If this project is useful to you, you can optionally
[support its maintenance on Buy Me a Coffee](https://www.buymeacoffee.com/alaub81).

## License

See [LICENSE](LICENSE) for repository licensing information. The included applications and extensions retain their respective licenses.
