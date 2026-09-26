# LHlab wiki — MediaWiki Docker Stack

A reproducible Docker stack for **LHlab wiki**, based on MediaWiki 1.46 with MariaDB, OpenSearch, CirrusSearch, Elastica, Memcached, ClamAV, scheduled maintenance jobs, and a custom MediaWiki image.

## Included services

- **MediaWiki 1.46** with Apache and PHP
- **MariaDB 12.3** as the database
- **OpenSearch 1.3.20** as the CirrusSearch backend
- **CirrusSearch** and **Elastica** from the MediaWiki `REL1_46` branches
- **Memcached** and the MemcachePHP administration UI
- **ClamAV** for upload scanning
- **Supercronic** for MediaWiki jobs, sitemap generation, RottenLinks, and search-index maintenance

OpenSearch runs only on the internal Docker network and is not exposed publicly.

## Important compatibility information

MediaWiki 1.46 and its matching CirrusSearch branch expect OpenSearch 1.3. Do not replace the configured image with an arbitrary OpenSearch 2.x or 3.x image.

This stack uses the Wikimedia OpenSearch image containing the search plugins expected by CirrusSearch:

```text
docker-registry.wikimedia.org/repos/search-platform/cirrussearch-opensearch-image:v1.3.20-12
```

The image is primarily intended for `linux/amd64`. On Apple Silicon, Docker may require amd64 emulation or a locally built Wikimedia OpenSearch image.

## Included MediaWiki extensions

The custom MediaWiki image installs these extensions:

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

## Repository layout

```text
.
├── Dockerfile-mediawiki
├── Dockerfile-memcachephp
├── docker-compose.dev.yml
├── docker-compose.example.yml
├── docker-compose.ci.yml
├── .env.example
├── resources/
│   ├── favicon/
│   ├── helper/
│   ├── memcachephp/
│   └── mediawiki/
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

## Requirements

- Docker Engine
- Docker Compose v2
- At least 2 GB of available memory for the complete stack
- An amd64 host or amd64 container emulation for the Wikimedia OpenSearch image

## Quick start

### 1. Create the environment file

Copy the example configuration:

```bash
cp .env.example .env
```

At minimum, review the database passwords and public MediaWiki URL.

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

For an existing wiki, copy the current `LocalSettings.php` to:

```text
data/mediawiki/conf/LocalSettings.php
```

Its CirrusSearch configuration must contain:

```php
wfLoadExtension( 'Elastica' );
wfLoadExtension( 'CirrusSearch' );

$wgCirrusSearchServers = [ 'opensearch' ];
$wgSearchType = 'CirrusSearch';
```

Elastica must be loaded before CirrusSearch. The hostname `opensearch` is the Docker Compose service name.

For a new installation, enable the setup configuration described in `.env.mwsetup` and make the configuration directory writable during initial setup. After setup, the generated `LocalSettings.php` can be mounted read-only.

### 3. Start the development stack

```bash
docker compose \
  -f docker-compose.dev.yml \
  --env-file .env \
  up -d --build
```

To use the prebuilt MediaWiki and MemcachePHP images, first copy the example Compose file:

```bash
cp docker-compose.example.yml docker-compose.yml
docker compose --env-file .env up -d
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

OpenSearch data cannot be reused directly from an Elasticsearch data volume. After migrating, create a fresh OpenSearch volume and rebuild the search index from MediaWiki.

### Verify OpenSearch

```bash
docker compose exec -T opensearch \
  curl -fsS http://localhost:9200/
```

The response should report OpenSearch 1.3.20.

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

## Memcached and MemcachePHP

Example configuration:

```dotenv
MEMCACHED_VERSION=alpine
MEMCACHED_CACHE_MB=32
MEMCACHEPHP_SERVERS=memcached:11211
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

## Persistent volumes

- `data_db` stores the MariaDB database.
- `data_mw_images` stores uploaded MediaWiki files.
- `data_osdata` stores OpenSearch indexes.
- `clamav_db` stores ClamAV signatures.

The OpenSearch index is derived data and can be rebuilt from the MediaWiki database. Database and uploaded-file backups remain essential.

## CI and E2E tests

The CI workflow uses `docker-compose.example.yml` as its base configuration. Therefore, OpenSearch must be configured consistently in both:

- `docker-compose.dev.yml`
- `docker-compose.example.yml`

The E2E workflow should address the service as `opensearch`:

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

## Production upgrade from 1.45.x to 1.46

This checklist covers the changes since `v1.45.5`. Keep the existing production Compose project, database volume, uploaded files, and `LocalSettings.php`; do not replace the live settings file with the example or run `docker compose down -v`.

| Area | Change to review |
| --- | --- |
| Images | MediaWiki `1.45` → `1.46`; MariaDB `11.8` → `12.3`; Supercronic `0.2.45` → `0.2.49`. Pin the production image tags you intend to run. |
| Search | CirrusSearch now uses the Wikimedia OpenSearch image `v1.3.20-12` and a new `data_osdata` volume. Rename `ES_VERSION` → `OPENSEARCH_VERSION`, `MW_ES_URL` → `MW_OPENSEARCH_URL`, and `ES_HEAP_MIN`/`ES_HEAP_MAX` → `OPENSEARCH_HEAP_MIN`/`OPENSEARCH_HEAP_MAX`. `OPENSEARCH_PLATFORM` defaults to `linux/amd64`. The old Elasticsearch volume is not an OpenSearch data volume. |
| Optional services | Elasticsearch `8.19.21` is now separate and used by Wanda 3. Set `MW_WANDA_ENABLED` together with the `elasticsearch` Compose profile and review `MW_ELASTICSEARCH_URL`, `ELASTICSEARCH_VERSION`, `ELASTICSEARCH_HEAP_MIN`, and `ELASTICSEARCH_HEAP_MAX`. `CLAMAV_VERSION` is new; keep `CLAMAV_ENABLED` and the `clamav` profile in sync. |
| Wiki configuration | `MW_SITENAME` and `MW_METANAMESPACE` can now supply site names. The example `LocalSettings.php` changed its database name from `wiki` to `wikidb`: retain the **actual production database name and credentials**. Review the new file-extension allowlist, searchable namespaces, and conditional Wanda configuration before merging settings. |
| Extensions | The image pins Wanda 3 and an updated RottenLinks commit, adds ExternalData, and no longer pins CookieConsent to its old commit. The example settings now load ExternalData and CheckUser. The image also applies MediaHandler and private-wiki RelatedArticles patches. Review the production extension list. |
| Maintenance and UI | `MW_CS_INDEX_CRON=15 * * * *` now runs at minute 15 each hour. MemcachePHP can read `MEMCACHEPHP_ADMIN_PASS_FILE` when a password file is mounted; its health check supports this too. |

Before upgrading, make verified backups of the MariaDB database, `data_mw_images`, and the live `LocalSettings.php`. Edit the existing production `.env` rather than replacing it with `.env.example`; the MariaDB image does not reset passwords or create new database users in an existing data volume. Then perform the upgrade during a maintenance window:

1. Stop the MediaWiki service while the old database is still running: `docker compose --env-file .env stop mediawiki`. Update the production `.env` and Compose configuration with the variables above. Point the existing `LocalSettings.php` at `opensearch` for CirrusSearch while retaining the production database settings. Keep `MW_WANDA_ENABLED=false` until its API key and Elasticsearch service are ready. If you use a nonstandard `MW_CONFIG_FILE`, ensure it is passed **into the container** and points to the mounted file; merely placing it in `.env` is not enough with the example Compose file.
2. Start only the new MariaDB image: `docker compose --env-file .env up -d database`. Once it is healthy, run `docker compose --env-file .env exec --user root database mariadb-upgrade --user=root --password` and enter the **existing** database root password at the prompt. Run `docker compose --env-file .env restart database` and verify its health. The Compose file does not set `MARIADB_AUTO_UPGRADE`, so do not assume the MariaDB system-table upgrade runs automatically. See the [MariaDB upgrade guide](https://mariadb.com/docs/server/clients-and-utilities/deployment-tools/mariadb-upgrade).
3. Set `MW_AUTO_UPDATE=true` for the first MediaWiki 1.46 startup, then start MediaWiki with `docker compose --env-file .env up -d mediawiki`. The entrypoint runs MediaWiki's `maintenance/run.php update` before Apache when it finds `LocalSettings.php`. Check `docker compose logs mediawiki` for a successful update. This is a **separate** database-schema step from `mariadb-upgrade`; see the [MediaWiki updater documentation](https://www.mediawiki.org/wiki/Manual:Update.php). Set `MW_AUTO_UPDATE=false` afterward and run `docker compose --env-file .env up -d --force-recreate mediawiki` to apply that value.
4. Rebuild the CirrusSearch index once with `docker compose --env-file .env exec -T mediawiki /usr/local/bin/generate-opensearch-index.sh`. This recreates search indexes, not wiki pages. Keep the old Elasticsearch volume until search and page content have been verified. If enabling Wanda, configure a real API key and run its initial full reindex separately.
5. Check `Special:Version`, page reads and edits, uploads, search, scheduled jobs, and the health of MariaDB and OpenSearch before ending the maintenance window.

The [MediaWiki 1.46 upgrade notes](https://www.mediawiki.org/wiki/Release_notes/1.46) and [upgrade manual](https://www.mediawiki.org/wiki/Manual:Upgrading) cover core changes beyond this Docker stack.

## Updating MediaWiki

When upgrading to another MediaWiki branch:

1. Update the MediaWiki base-image version.
2. Ensure all Wikimedia extensions use the matching `RELx_xx` branch.
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

## Security notes

- Never expose OpenSearch port 9200 directly to the internet.
- Keep the OpenSearch service on the internal backend network.
- Replace all example passwords before deployment.
- Prefer Docker secrets or another secret-management mechanism for production credentials.
- Back up the MariaDB database and MediaWiki uploads regularly.
- Pin production image versions instead of using floating `latest` tags.

## License

See [LICENSE](LICENSE) for repository licensing information. The included applications and extensions retain their respective licenses.
