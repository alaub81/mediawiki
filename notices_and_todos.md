# Backlog and review notes

Documentation and source comments are maintained in English. The review below is
historical; its original completion markers are retained. The migration status
section distinguishes later work from findings that still need investigation.

## Ideas and operational notes

- [?] Investigate setting `MARIADB_VARS` and creating the wiki database automatically.
- [!] Do not apply the proposed `MW_SITEMAP_IDENTIFIER=wiki` / `$wgArticlePath = "/wiki/$1";` redirect and short-URL experiment without a separate review.
- [?] Consider [ExternalContent](https://www.mediawiki.org/wiki/Extension:External_Content) when available for the relevant MediaWiki version (original note: 1.44).
- [!] Do not remove the database port from the `mw-default-setup.sh` installer.
- [!] Copying SyntaxHighlight configuration is not suitable as a default.
- [?] Consider lowercase article titles. These settings change canonical titles; test on staging first:

  ```php
  // Make first character of page titles case-sensitive globally
  $wgCapitalLinks = false; // Changes canonical titles. Test on staging first!
  // Override just the main namespace to allow lowercase first letters
  $wgCapitalLinkOverrides[NS_MAIN] = false; // Only main namespace is affected
  ```

- [x] Support optional secret files; `LocalSettings.php` must support both methods.
- [x] Test all three installation alternatives (historical result, not proof of every current variant).
- [x] Review whether the database variables are needed or should become defaults.
- [ ] Clean up categories/subcategories; add logos and text to main categories.
- [ ] Apply PageSpeed findings.
- [ ] Once Google AdSense works, enable CSP and review security headers and PageSpeed:
  <https://securityheaders.com/?q=https%3A%2F%2Flhlab.wiki&followRedirects=on>
  <https://pagespeed.web.dev/analysis/https-lhlab-wiki-wiki-Dimplex_Wärmepumpe_Smart-Grid_mit_Shelly_Relais/57ygqq2725?form_factor=mobile>
- [ ] Update the wiki article.
- [ ] Evaluate using the example Compose file as a base and all other variants as overlays. This is a proposal, not the current standalone-variant contract.
- [ ] Consider `BIND_ADDRESS=127.0.0.1`.

Maintenance command reference (run against the correct configuration and service):

```bash
php maintenance/run.php /var/www/html/extensions/Wanda/maintenance/ReindexAllPages.php

# Search-index jobs
php maintenance/run.php ./extensions/CirrusSearch/maintenance/CirrusNeedsToBeBuilt.php
php maintenance/run.php ./extensions/CirrusSearch/maintenance/ForceSearchIndex.php --skipLinks --indexOnSkip
php maintenance/run.php ./extensions/CirrusSearch/maintenance/ForceSearchIndex.php --skipParse
php maintenance/run.php ./extensions/CirrusSearch/maintenance/UpdateSuggesterIndex.php
php maintenance/run.php showJobs
php maintenance/run.php showJobs --group
php maintenance/run.php runJobs
```

## MW setup script reference


```txt
Script runner options:
    --conf <CONF>: Location of LocalSettings.php, if not default
    --globals: Output globals at the end of processing for debugging
    --help (-h): Display this help message
    --memory-limit <MEMORY-LIMIT>: Set a specific memory limit for the
        script, "max" for no limit or "default" to avoid changing it
    --profiler <PROFILER>: Profiler output format (usually "text")
    --quiet (-q): Whether to suppress non-error output
    --server <SERVER>: The protocol and server name to use in URLs, e.g.
        https://en.wikipedia.org. This is sometimes necessary because server
        name detection may fail in command line scripts.
    --wiki <WIKI>: For specifying the wiki ID

Common options:
    --dbgroupdefault <DBGROUPDEFAULT>: The default DB group to use.
    --dbpass <DBPASS>: The password for the DB user for normal
        operations
    --dbuser <DBUSER>: The user to use for normal operations (wikiuser)

Script specific options:
    --confpath <CONFPATH>: Path to write LocalSettings.php to
        (/var/www/html)
    --dbname <DBNAME>: The database name (my_wiki)
    --dbpassfile <DBPASSFILE>: An alternative way to provide dbpass
        option, as the contents of this file
    --dbpath <DBPATH>: The path for the SQLite DB ($IP/data)
    --dbport <DBPORT>: The database port; only for PostgreSQL (5432)
    --dbprefix <DBPREFIX>: Optional database table name prefix
    --dbschema <DBSCHEMA>: The schema for the MediaWiki DB in PostgreSQL
        (mediawiki)
    --dbserver <DBSERVER>: The database host (localhost)
    --dbssl: Connect to the database over SSL
    --dbtype <DBTYPE>: The type of database (mysql)
    --env-checks: Run environment checks only, don't change anything
    --extensions <EXTENSIONS>: Comma-separated list of extensions to
        install
    --installdbpass <INSTALLDBPASS>: The password for the DB user to
        install as.
    --installdbuser <INSTALLDBUSER>: The user to use for installing
        (root)
    --lang <LANG>: The language to use (en)
    --pass <PASS>: The password for the wiki administrator.
    --passfile <PASSFILE>: An alternative way to provide pass option, as
        the contents of this file
    --scriptpath <SCRIPTPATH>: The relative path of the wiki in the web
        server (/html)
    --skins <SKINS>: Comma-separated list of skins to install (default:
        all)
    --with-developmentsettings: Load DevelopmentSettings.php in
        LocalSettings.php
    --with-extensions: Detect and include extensions

Arguments:
    [name]: The name of the wiki
    [admin]: The username of the wiki administrator.

```

## Installation alternatives

1. **Setup script:** enable the setup environment file (the template is `.env.mwsetup`), select the setup configuration mount, start Compose, then explicitly run `mw-default-setup.sh`.
2. **Preconfigured settings:** without the setup environment file, copy and customize `LocalSettings.php.example`, mount it, start Compose, then run `php maintenance/run.php installPreConfigured --conf /var/www/html/LocalSettings.php` inside the container for an empty database.
3. **Browser configuration generator:** start without a `LocalSettings.php` mount, visit the configured public URL (original example: `http://localhost:8080`), complete the wizard using the database settings from `.env`, and persist the generated file.

Use the current [installation guide](docs/installation.md) for credentials, exact
commands, configuration persistence, permissions and known variant limitations.

## Historical code and README review: 2026-09-27

This was a static review of the working tree at that time. `./tests/linter-check.sh`,
`bash -n`, JSON validation of `renovate.json`, and `docker compose config --quiet`
for example, development and secrets configurations passed. Real container/E2E
checks were unavailable because access to the Docker daemon was denied. Existing
changes, including uncommitted changes, were preserved. File line references below
have been replaced with paths because the staged migration moved the code.

### P0: Installation, operations and security

- [ ] **Unify configuration paths.** `.env.mwsetup` and the old CI installed into `/var/www/html/conf/LocalSettings.php`, but `--confpath` does not create the standard `/var/www/html/LocalSettings.php` entry point. The entrypoint, setup update call, CirrusSearch and RottenLinks maintenance commands did not consistently pass `--conf`; only the sitemap helper used `MW_CONFIG_FILE`. Either provide the standard file or prove that web and every maintenance command use the same custom path. Test installation, restart, schema update and cron jobs. Sources: `.env.mwsetup`, `resources/mediawiki/mw-default-setup.sh`, `resources/mediawiki/mediawiki-entrypoint.sh`, [Install.php](https://www.mediawiki.org/wiki/Manual:Install.php), [Run.php](https://www.mediawiki.org/wiki/Manual:Run.php).
- [x] **Document Elastica/CirrusSearch load order.** Load order is not significant. The README states this and uses the same order as the example settings; runtime configuration was unchanged.
- [ ] **Make the fresh-wiki quickstart executable and complete.** The old README mentioned an env file and writable configuration directory, but `compose.yml` enabled neither setup env loading nor a configuration mount, and the entrypoint did not invoke the installer. Document the setup invocation, permissions, persistent host file and read-only final mount, then test a fresh Compose project. Sources: `README.md`, `compose.yml`, `resources/mediawiki/mediawiki-entrypoint.sh`.
- [ ] **Align CI installation with the configuration lifecycle.** Old CI used the custom config path and setup as `www-data` while only uploads were mounted. Verify writable setup storage, persistent config, empty-volume installation and container recreation. Sources: `.github/workflows/ci.yml`, `tests/compose.test.yml`, `compose.yml`.
- [ ] **Make examples safe and usable.** The old template enabled Wanda with a placeholder API key, enabled continuous schema updates and contained known example passwords. Choose safe defaults, require real credentials at setup, and align debugging examples. Sources: `.env.example`, `.env.mwsetup`, `README.md`.
- [ ] **Remove static wiki keys from the public example.** Replace concrete `$wgSecretKey` and `$wgUpgradeKey` values with placeholders or documented generation. Investigate whether the old public values were used in a live wiki and rotate them if so. Source: `data/mediawiki/conf/LocalSettings.php.example`.

### P1: Behavior and test reliability

- [x] **Harden MemcachePHP despite existing Basic Auth.** Escape HTML keys, values and server names; validate decoded keys/server indexes. Delete and flush use POST and session CSRF tokens. `tests/memcachephp_security_test.py` checks unauthenticated 401, rejected GET/invalid POST actions, valid delete/flush, text-only output and rejected CR/LF keys.
- [ ] **Separate CirrusSearch bootstrap from the periodic job.** `update-cirrussearch-index.sh` treats every failed alias request as a missing index and invokes `UpdateSearchIndexConfig --startOver` plus full indexing. Distinguish reachability/configuration failures from missing aliases, avoid automatic destructive rebuilds, and read custom index base names from wiki settings.
- [x] **Fix the CI MemcachePHP UI check.** The authenticated proxy request uses `/memcacheui/`, GET, retries, status 200 and a content assertion. Remove the ineffective check against unpublished port 8097 and its variable; the MemcachePHP port remains internal.
- [x] **Eliminate misleading CI success.** Skin checks run in the current shell; missing skins fail. Siteinfo uses `jq` and rejects a wrong sitename. ClamAV checks verify both configuration and container values with a mandatory timeout. DB waiting uses a POSIX-compatible counter bounded at 120 seconds instead of `SECONDS` under `sh`. Negative tests for missing skins, wrong sitename and an expired counter returned status 1.
- [x] **Test real search, Compose profiles and workflow syntax.** Create a unique search term and require it through the MediaWiki search API after bootstrap. Validate base, ClamAV, Elasticsearch/Wanda and full profiles and expected services. Run actionlint for workflow syntax/expressions/job dependencies. Keep the mandatory EICAR test.
- [ ] **Resolve ineffective extension/skin build arguments.** `compose.dev.yml` and `tests/compose.test.yml` pass `MW_INSTALL_EXTENSIONS` and `MW_INSTALL_SKINS`, but the Dockerfile declares fixed ENV lists without corresponding ARG declarations. Wire them correctly or remove ineffective options; reconcile `MW_EXTRA_EXTENSIONS` with actual clones. Sources: `resources/mediawiki/Dockerfile`, Compose variants and CI.
- [ ] **Define extension version strategy.** `clone_with_fallback` silently falls back from missing `REL1_46` to `main` or default HEAD. This weakens the release-branch compatibility claim and makes builds time-dependent. Fail for incompatible required branches or pin tested commits. Sources: `resources/mediawiki/Dockerfile`, README update instructions.
- [ ] **Unify maintenance users and configuration.** Supercronic and some PHP/index jobs run as root while sitemap/RottenLinks use `www-data`. Test read-only settings and upload access and use `www-data` consistently where possible. Sources: entrypoint, index and sitemap scripts.
- [ ] **Complete fresh-clone secrets instructions.** At review time the overlay/templates were untracked and `.env.secrets` was ignored. Track sanitized examples and overlay, document copying/permissions and test startup without pre-existing secrets. Never commit real secrets. Sources: `compose.secrets.yml`, `.env.secrets`, `secrets_example/`, `.gitignore`, README.
- [ ] **Optimize resource usage.** Prioritize measured consumers (historical snapshot: OpenSearch 1.44 GiB, Elasticsearch 1.26 GiB, ClamAV 0.99 GiB). Check optional-service needs, heap, caches and worker sizing. Measure each change under comparable load and monitor latency, indexing, antivirus and OOM/swap. Record before/after values and chosen defaults. Sources: `.env.example`, `compose.yml`, README.

### P2: Documentation and maintenance

- [ ] **Correct missing favicon references.** Example settings and the setup script reference `favicon-16x16.png` and `favicon-32x32.png`, absent from `resources/mediawiki/favicon/`. Supply files or remove references, then check HTTP responses.
- [x] **Write a repository-specific security policy.** `SECURITY.md` identifies the project, supported release line, private GitHub reporting/fallback, scope and realistic response expectations; unrelated component references were removed.
- [x] **Review old release/dependency automation.** Remove the unrelated `LOGANALYZER_VERSION` regex and use valid Renovate update types. Disable implicit metadata-action `latest`; only the highest stable release should receive `1.46`, `1` and `latest`, with old releases receiving immutable full tags only. Historical dry runs used `v1.46.5` and `v1.46.4`. The newer release implementation is documented in `docs/releases.md`.
- [x] **Measure resource requirements and profiles.** Base profile measured for two minutes peaked at 1.57 GiB; full profile with ClamAV and Elasticsearch over four minutes reached 3.61 GiB (earlier full snapshot: 4.07 GiB). Each profile served 120 successful read API calls. Indexing covered one page and schema update found no pending changes. No OOM, restart or cgroup swap at measurement end. README preserves these provisional observations and 3/6 GiB planning values; representative larger datasets still need measurement.

### Additional CI proposals from the historical review

- [ ] Run the isolated MemcachePHP security regression in CI to catch escaping, CSRF, GET mutation, key-validation and Basic Auth regressions.
- [ ] Test installer/update idempotence: repeat the setup/update path, check errors and duplicate config lines. Config persistence and container recreation remain separate P0 concerns.
- [ ] Add generated temporary secrets and secrets-overlay Compose validation to the profile matrix, then a runtime startup test. First ensure sanitized templates/overlay are tracked.
- [ ] Test Wanda/Elasticsearch beyond service startup: connection and configuration at minimum. An external AI API test requires an explicitly dedicated secret and separate optional job.
- [ ] Make database authentication mandatory; missing clients or invalid credentials must fail rather than merely proving a TCP port is open.
- [ ] Define Trivy blocking severities explicitly and upload SARIF independently of gate success.
- [ ] Always capture bounded Compose status/log diagnostics on E2E failure and upload artifacts, including failures outside API waiting.

## Status after migration steps 1–5

The items above retain their historical markers. Later implementation changes:

- CI now uses isolated projects with the standard configuration path, tests native
  amd64/arm64 images, authenticated DB access, MemcachePHP security, real search
  and ClamAV, and captures failure diagnostics. See [CI](docs/ci.md).
- Secrets overlays and sanitized templates are tracked and checked by offline
  Compose tests. A production-style secrets startup/restore exercise is not
  implied by configuration validation.
- Fixable CRITICAL gates and independently uploaded full SARIF are implemented in CI
  and release. HIGH findings are advisory.
- Public templates disable continuous updates, Wanda and optional service profiles
  by default. README requires independent passwords and preserves all advanced
  feature guides; the public example now uses explicit wiki-key placeholders.
  Whether old keys were used live is unverified; rotate them if applicable.
- The new first-start guide explicitly installs and persists standard-path
  settings. The current published installer writes `$wgAntivirus = false` when
  ClamAV is disabled, which MediaWiki 1.46 rejects; the guide records a targeted
  `null` workaround. Fix the runtime generator separately and retain the regression.
- Custom-path setup, full installer/schema-update idempotence, maintenance users,
  unsafe index bootstrap, extension fallback/build arguments, missing favicon
  files, external Wanda functionality and resource tuning remain follow-ups.
- Account-side Dependabot activation and Mend mode need verification; branch
  protection remains deferred. See [dependency policy](docs/dependencies.md) and
  [Standard v1 status](docs/standard-v1.md).
