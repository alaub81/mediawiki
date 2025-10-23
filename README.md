# MediaWiki Docker Stack (with Elasticsearch + CirrusSearch)

A reproducible MediaWiki stack powered by Docker. It includes a custom MediaWiki image, MariaDB, Memcached with a web UI, **Elasticsearch + CirrusSearch** for full‑text search, scheduled sitemap generation, rottenlinks updates and CirrusSearch indexing, short URLs, and an Apache reverse proxy for the MemcachePHP UI.

**What you get**

> - Opinionated MediaWiki image (`mediawiki-custom`) with sensible defaults
> - Short URLs (`/wiki/...`)
> - Elasticsearch + CirrusSearch for search and RelatedArticles
> - Automatic sitemap generation (cron via supercronic)
> - Automatic rottenlinks generation (cron via supercronic)
> - Memcached + MemcachePHP admin UI (proxied at `/memcacheui/`)
> - Clear environment-driven configuration and volume persistence
> - Cookie Banner with CookieConsent Extension
> - and these included MediaWiki Extensions:
    - Lockdown
    - Description2
    - RelatedArticles
    - MobileFrontend
    - CirrusSearch & Elastica
    - HitCounters & TopTenPages
    - RottenLinks
    - WikiCategoryTagCloud
    - CookieConsent
    - DynamicPageList

---

## 1) Project overview

This repo builds a **custom MediaWiki** image and composes a full stack:

- **MediaWiki** (based on official MediaWiki Image) with configurable extensions/skins
- **MariaDB** for the wiki database
- **Memcached** plus a **MemcachePHP** admin UI (reverse-proxied via Apache)
- **Elasticsearch** + **CirrusSearch/Elastica** for search and suggestions
- **Supercronic** to run scheduled jobs (e.g., sitemap generation, optional link checks)

Target use-cases: local development and small/medium server deployments.

---

## 2) Stack & services

- **MediaWiki**: custom image `mediawiki-custom` (Apache + PHP 8.x), short URLs, scripts in `resources/mediawiki`
- **MariaDB**: official image (11.x), persistent volume for data
- **Memcached**: caching backend used by MediaWiki
- **MemcachePHP**: tiny admin UI, reverse-proxied by Apache under `/memcacheui/`
- **Elasticsearch (single node)**: for CirrusSearch integration
- **Networks**: `app-nw` (front), `backend-nw` (internal)

**Port defaults:**

> - Wiki: `http://localhost:${MW_HTTP_PORT:-8080}`
> - MemcachePHP direct: `${MEMCACHEPHP_HTTP_PORT:-8097}` (also proxied as `/memcacheui/` on the wiki host)

---

## 3) Quick start

**Prerequisites:**
Docker + Docker Compose

**1) Prepare environment**
Create a local `.env` (or reuse your existing, or have a look at .env.example) with at least:

```env
MW_HTTP_PORT=8080
MARIADB_ROOT_PASSWORD=R00tPassword
TZ=Europe/Berlin

# (optional) MemcachePHP UI
MEMCACHEPHP_ADMIN_USER=admin
MEMCACHEPHP_ADMIN_PASS=supersecret
MEMCACHEPHP_HTTP_PORT=8097

# (recommended) Server URL for installer / sitemap
MW_SERVER_URL=http://localhost:8080
```

**2) Start the stack**
use this command:

```bash
# if you like to build yourself
docker compose -f docker-compose.dev.yml --env-file .env up -d --build
# if you like to use prebuilt images
docker compose -f docker-compose.yml --env-file .env up -d --build
```

**3) First-run install**
The entrypoint runs `resources/mediawiki/mw-default-setup.sh`
which:

- creates/extends `LocalSettings.php` at `${MW_CONFIG_FILE}`
- enables short URLs (`/wiki/$1` and action paths)
- applies PHP/upload size limits
- wires Memcached, VisualEditor-friendly rewrites
- configures basic CirrusSearch settings to talk to Elasticsearch
- (if configured) sets up sitemap generation & Apache redirect for `/sitemap.xml`

when:

- you are mounting a conf folder for LocalSettings.php `- ./data/mediawiki/conf/mw_local_settings:/var/www/html/conf/:rw`
- you are including the `.env.mwsetup` in your `docker-compose.yml`

  ```yml
  ...
      env_file:
        - .env.mwsetup
  ...
      volumes:
        - ./data/mediawiki/conf/mw_local_settings:/var/www/html/conf/:rw
  ```

> You can later mount a host-side `LocalSettings.php` (see **Volumes & persistence**).

---

## 4) Configuration (environment variables)

The stack is **environment-first**. Most knobs are set via `environment:` in Compose, optionally complemented by an `env_file:`.

### MediaWiki core

- `MW_CONFIG_FILE` — path of the wiki config file inside the container (default `/var/www/html/LocalSettings.php`)
- `MW_LANG` — default language (e.g., `de`)
- `MW_SERVER_URL` — canonical base URL used by maintenance scripts and sitemap
- `MW_DEFAULT_SKIN` — default skin code (e.g., `vector-2022`, `minerva`)

### Extensions & skins

- **Build-time fetch lists** (git-cloned during image build):
  - `MW_INSTALL_EXTENSIONS` — space-separated extension names or Git URLs
  - `MW_INSTALL_SKINS` — space-separated skin names or Git URLs
- **Runtime activation** (appended to `LocalSettings.php` on container start):
  - `MW_ACTIVE_EXTENSIONS` — space-separated canonical extension names
  - `MW_ACTIVE_SKINS` — space-separated skin codes (e.g., `vector-2022 deskmessmirrored`)

> The image contains helper logic to clone by branch with fallback or to pin to a specific commit (see `Dockerfile-mediawiki`).

### Elasticsearch

- `ES_JAVA_OPTS` — e.g., `-Xms512m -Xmx512m` (or `-Xms1g -Xmx1g`)
- `discovery.type=single-node` — set in Compose by default
- Ensure the container RAM matches your heap (heap ≈ 50% of container memory).

### Sitemaps

- `MW_SITEMAP_GENERATION` — `true|false`
- `MW_SITEMAP_CRON` — default `"20 */12 * * *"`
- `MW_SITEMAP_SERVER` — e.g., `https://www.example.com`
- `MW_SITEMAP_URLPATH` — e.g., `sitemap/` (creates files under `/var/www/html/sitemap/…`)
- `MW_SITEMAP_SKIP_REDIRECTS` — `true|false`
- `MW_SITEMAP_RUN_ON_START` — `true|false`
- `MW_SITEMAP_IDENTIFIER` — identifier inserted into file names, e.g., `wiki`

### MemcachePHP

- `MEMCACHEPHP_SERVERS` — e.g., `memcached:11211`
- `MEMCACHEPHP_ADMIN_USER`, `MEMCACHEPHP_ADMIN_PASS`, `MEMCACHEPHP_HTTP_PORT`

### Database

- `MARIADB_ROOT_PASSWORD` — root password for MariaDB
- Wiki database/user/pass are applied by the installer (`mw-default-setup.sh`) via flags.

### Timezone

- `TZ` — e.g., `UTC` or `Europe/Berlin`

> **Precedence:** values in the Compose `environment:` section override `env_file` entries of the same name. Consider using Compose `secrets:` for sensitive values like DB root password.

---

## 5) Volumes & persistence

- `data_mw_db:/var/lib/mysql` — MariaDB data (persistent)
- `data_mw_images:/var/www/html/images` — MediaWiki uploads (persistent)

**LocalSettings.php**

- Default path in container: `/var/www/html/LocalSettings.php`
- You can mount your host file to this path or to `/var/www/html/conf/…` (then set `MW_CONFIG_FILE` accordingly).

**Sitemaps**

- Default files are emitted under `/var/www/html/` or inside `/var/www/html/<MW_SITEMAP_URLPATH>/` if you set `MW_SITEMAP_URLPATH` (e.g., `/var/www/html/sitemap/sitemap-index-<id>.xml`).

---

## 6) Short URLs & Apache

- Rewrites map `/wiki/<Title>` to the MediaWiki front controller, and actions like `/wiki/edit/<Title>` are supported.
- VisualEditor friendly: consider `AllowEncodedSlashes NoDecode` in your Apache conf for REST-style endpoints.
- MemcachePHP UI is reverse-proxied by Apache to the `memcachephp` container under convenient paths:
  - `/memcacheui/` (canonical)
  - plus optional helpers like `/memcache` or `/mcui` → redirect to `/memcacheui/`
  - Proper `X-Forwarded-*` headers and `ProxyPassReverseCookiePath` are configured in the provided conf.

---

## 7) Extensions & skins

- **Fetching at build time:** The Dockerfile supports cloning Wikimedia-hosted extensions/skins by branch (with a fallback), or by **pinned commit**.
- **Activation at runtime:** The entrypoint reads `MW_ACTIVE_EXTENSIONS` and `MW_ACTIVE_SKINS` and appends `wfLoadExtension()` / skin settings to `LocalSettings.php` if not present.
- Typical set included/tested in this stack:
  - Extensions: CookieConsent, MobileFrontend, CirrusSearch, Elastica, RelatedArticles, Lockdown, Description2, WikiCategoryTagCloud, RottenLinks (optional), etc.
  - Skins: Vector 2022, Minerva, Timeless, MonoBook, DeskMessMirrored, …

> Some extensions (e.g., **CirrusSearch/Elastica**) require `composer install` inside the MediaWiki directory to provide `vendor/autoload.php`. The image takes care of running Composer where necessary.

---

## 8) Search with Elasticsearch + CirrusSearch

- **Elasticsearch** runs as a **single node**, configured for MediaWiki.
- The entrypoint/script applies the CirrusSearch settings to `LocalSettings.php` and points MediaWiki to the ES host (`elasticsearch`).
- **Initial index:** use the helper script to bootstrap and build indices:

  ```bash
  docker compose exec -T mediawiki sh -lc '/usr/local/bin/generate-elasticindex.sh'
  ```

  This runs through `UpdateSearchIndexConfig`, `ForceSearchIndex`, and optionally `UpdateSuggesterIndex` once the metastore exists.
- **Memory sizing:** start with `ES_JAVA_OPTS=-Xms512m -Xmx512m`; raise to `1g` if you see sustained heap pressure. Heap ~50% of container RAM.
- **Verification:**
  - MediaWiki API search using Cirrus backend (after index): queries should return results; RelatedArticles can use Cirrus as backend.
  - Elasticsearch health: `GET /_cluster/health` should be `yellow` or `green` in single-node mode.

---

## 9) Sitemaps & scheduled jobs

- Script: `/usr/local/bin/generate-sitemap.sh`
  - Adds flags **only** when corresponding env vars are set (e.g., `--server`, `--urlpath`, `--skip-redirects`).
  - Runs as `www-data` and ensures the output directory exists/has proper ownership.
- Apache 301 for `/sitemap.xml`:
  - If `MW_SITEMAP_URLPATH` is set (e.g., `sitemap/`), redirect to `/<urlpath>/**sitemap-index-<id>.xml**`
  - If not set, redirect to `/sitemap-index-<id>.xml` in the docroot.
- Scheduling via **supercronic**:
  - `MW_SITEMAP_GENERATION=true`
  - `MW_SITEMAP_CRON="20 */12 * * *"` (example)
  - Similar pattern can be used for optional link-check jobs (RottenLinks), guarded by a file existence check.

---

## 10) Release & tagging

- Suggested policy (example): git tag `v1.43.1` → container images tagged as:
  - `1.43.1`
  - `1.43`
  - `latest`

---

## 11) Security & updates

- **Dependabot**: keep Docker base images and GitHub Actions up to date.
- **Watchtower labels** (optional): permit automatic updates for selected services.
- **Extensions**: prefer pinned commits for stability; otherwise, branch fallback logic fetches latest for the chosen branch.
- **Secrets**: consider Docker `secrets:` for DB root password and admin creds.

---

## 12) Troubleshooting

- **VisualEditor & short URLs**: ensure Apache allows encoded slashes: `AllowEncodedSlashes NoDecode` in your site conf.
- **Sitemap redirect is 301 but file 404**: confirm the sitemap script created `sitemap-index-<id>.xml` at the expected path (`/var/www/html` or `/var/www/html/<urlpath>`), and ownership is `www-data`.
- **CirrusSearch** says `Elastica\Client not found`: run Composer so `vendor/autoload.php` exists for Elastica; ensure both CirrusSearch and Elastica ran `composer install`.
- **Elasticsearch heap pressure**: check `/_cat/nodes?h=heap.percent,heap.current,heap.max` and logs for `CircuitBreakingException`; increase `ES_JAVA_OPTS` if needed.
- **LocalSettings mount blocks installer**: if you mount an existing `LocalSettings.php` in Compose, the automated installer is skipped; adjust `docker-compose.*.yml` for CI vs. dev.
- **env_file vs environment precedence**: values in `environment:` override `env_file` for the same key.

---

## 13) Directory layout

```txt
.
├─ Dockerfile-mediawiki
├─ Dockerfile-memcachephp
├─ docker-compose.dev.yml              # main compose for dev/prod
├─ docker-compose.ci.yml               # (optional) CI-oriented overrides
├─ resources/
│  └─ mediawiki/
│     ├─ mw-default-setup.sh          # creates/amends LocalSettings, short URLs, Cirrus, etc.
│     ├─ generate-sitemap.sh          # sitemap generator (runs as www-data)
│     └─ generate-elasticindex.sh     # Cirrus/Elasticsearch bootstrap + index
├─ conf/
│  ├─ mediawiki-rewrites.conf         # short URLs, VE-friendly settings
│  └─ memcachephp-proxy.conf          # reverse proxy for /memcacheui/
└─ data/
   └─ mediawiki/
      └─ conf/                        # mounted configs (LocalSettings.php, robots.txt, .htaccess, …)
```

---

## 14) Credits

This project builds on:

- **MediaWiki** (Wikimedia Foundation & contributors)
- **Elasticsearch**, **CirrusSearch**, **Elastica**
- **MariaDB**, **Memcached**, **MemcachePHP**
- **supercronic**
