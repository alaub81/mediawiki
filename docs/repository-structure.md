# Repository structure

This is step 1 of the staged Repository Standard v1 migration. It organizes
files and repository templates. CI/release behavior, dependency-update policy,
application behavior and the wider documentation review are separate steps.
Branch protection remains deferred. No other repository is changed.

## File responsibilities

| Location | Responsibility |
| --- | --- |
| `resources/mediawiki/` | MediaWiki image inputs, scripts, Apache configuration, favicons and extension patches |
| `resources/memcachephp/` | MemcachePHP image inputs and PHP application |
| `compose.yml` | Published-image production template |
| `compose.dev.yml` | Standalone local-build stack |
| `compose.setup.yml` | Existing development/setup variant with `.env.mwsetup` and writable configuration mount |
| `compose.secrets.yml` | Password-file overlay; combine with a root-level base Compose file |
| `tests/compose.test.yml` | CI build override; combine with the root-level production file |
| `tests/` | Existing application tests and integration-test configuration |
| `tools/` | Host-side development utilities |
| `docs/examples/` | Optional host configuration examples |
| `data/` | Existing runtime configuration templates and supplied assets |
| `.github/` | Workflows, issue/PR templates, dependency configuration and `FUNDING.yml` |

The image contexts remain self-contained. The host-only commit lookup utility
and NGINX example have moved out of `resources/`. They are not image inputs.
Local checks now use `tests/linter-check.sh`, `tests/test-check.sh` and
`tests/integration-check.sh`. See the [development guide](development.md) for
the step 2 tooling.

## Compose filename migration

| Previous path | Current path |
| --- | --- |
| `docker-compose.example.yml` | `compose.yml` |
| `docker-compose.dev.yml` | `compose.dev.yml` |
| `docker-compose.dev.mwsetup.yml` | `compose.setup.yml` |
| `docker-compose.secrets.yml` | `compose.secrets.yml` |
| `docker-compose.ci.yml` | `tests/compose.test.yml` |
| `resources/helper/get-last-git-commit.sh` | `tools/get-last-git-commit.sh` |
| `resources/helper/nginx/nginx_mw_proxy_vhost_example.conf` | `docs/examples/nginx_mw_proxy_vhost_example.conf` |

Docker Compose prefers `compose.yml` over `docker-compose.yml`. Existing
installations with a customized, Git-ignored `docker-compose.yml` must therefore
select that file explicitly, including in timers, scripts and service units:

```bash
docker compose --env-file .env -f docker-compose.yml config --quiet
docker compose --env-file .env -f docker-compose.yml ps
docker compose --env-file .env -f docker-compose.yml up -d
```

Keep the original checkout directory and project name. Preserve any existing
`-p`/`COMPOSE_PROJECT_NAME` setting, `.env`, secrets, configuration mounts and
volumes. Do not substitute `PROJECT_NAME` for Compose's actual project name:
this repository also uses that variable for network-interface names.
Do not copy the new template over your live file or run `down -v` to migrate.
Merge desired template changes into the existing file after reviewing them.

If your ignored `docker-compose.yml` is a symlink to the old
`docker-compose.example.yml`, update that link to `compose.yml` after verifying
its current target with `readlink docker-compose.yml`. This only changes the
link target; it must not replace a regular customized production file.

New deployments use `compose.yml` explicitly; local builds use `compose.dev.yml`.
Run commands from the repository root. The setup variant retains its existing
setup requirements; renaming it does not fix or change installation behavior.
All overlay paths are resolved relative to the first Compose file, so keep the
root-level base file first:

```bash
# Production configuration with password files.
docker compose --env-file .env.secrets -f compose.yml -f compose.secrets.yml config --quiet

# Existing CI configuration with disposable example credentials.
docker compose --env-file .env.ci-test -f compose.yml -f tests/compose.test.yml config --quiet
```

Step 1 changed only filenames. The subsequent CI migration now uses a disposable
stack resolved from the production base, the test override and `tests/e2e.env`;
it no longer copies a root `docker-compose.yml`. See the [CI guide](ci.md).
Release workflow logic is unchanged. Historical tags retain their own layouts.

## GitHub templates and funding

Issue templates refer to MediaWiki and request versions, platforms, profiles and
sanitized diagnostics. The PR template asks for validation, documentation and
deployment consequences. Regular/security dependency ownership is reviewed in
the later dependency step; the current Dependabot and Renovate policies remain.

The canonical funding file is `.github/FUNDING.yml`, with
`buy_me_a_coffee: alaub81`. Its case is normalized and the README links to the
same recipient. The visible GitHub Sponsor entry depends on repository settings;
this file change does not modify those settings.

Docker documents [Compose file selection](https://docs.docker.com/compose/intro/compose-application-model/#the-compose-file)
and [path resolution when merging files](https://docs.docker.com/compose/how-tos/multiple-compose-files/merge/).
