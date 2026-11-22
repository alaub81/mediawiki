# Shared Compose base and local builds

Normal operation and local development share `compose.yml`. It contains service
configuration, published project images, dependencies, healthchecks, profiles,
networks and named volumes. `compose.config.yml` adds the existing private
`data/mediawiki/conf/LocalSettings.php` as a read-only mount. `compose.dev.yml`
adds only local build definitions and the original local image names.

## Select files in .env

Keep one active `COMPOSE_FILE` assignment in your private `.env`:

```dotenv
# Published images with an existing wiki configuration.
COMPOSE_FILE=compose.yml:compose.config.yml
# Alternative for local builds; replace the active assignment above.
# COMPOSE_FILE=compose.yml:compose.config.yml:compose.dev.yml
```

These examples use the Linux/macOS `:` separator. Windows uses `;` by default,
or you can explicitly configure `COMPOSE_PATH_SEPARATOR`.
Run commands from the repository root with the same environment selection:

```bash
docker compose config --quiet
docker compose up -d
docker compose ps
docker compose logs --tail 100 mediawiki
```

For local development, select the dev overlay and run
`docker compose up -d --build`. To return to published images, remove the dev
overlay from the selection and recreate the services. Do not change the project
name, database credentials or named volumes when changing build mode.
`COMPOSE_PROJECT_NAME`/`-p` identify the Compose project; `PROJECT_NAME` is also
used for this repository's network-interface names and is not a substitute.

The public environment template selects published images by default. Updating
an existing `.env` requires only adding or reviewing `COMPOSE_FILE`; never replace
private credentials with the template. A wiki must already have valid settings
and an initialized database for normal operation. Local building does not invoke
the fresh installer.

## Explicit files, local overrides and secrets

Explicit `-f` options replace `COMPOSE_FILE`. The equivalent local-build command is:

```bash
docker compose --env-file .env -f compose.yml -f compose.config.yml -f compose.dev.yml up -d --build
```

Keep the root base first: relative build and mount paths resolve from it. The
dev overlay no longer runs as a standalone stack. Container runtime settings
remain in the base, so changes apply consistently to published-image and local
build modes.

When using `COMPOSE_FILE`, Compose does not automatically append a pre-existing
`compose.override.yml`. Preserve such a file and explicitly append it last if it
contains personal mounts, settings or services. For example, after reviewing it:

```dotenv
COMPOSE_FILE=compose.yml:compose.config.yml:compose.dev.yml:compose.override.yml
```

An optional personal `compose.local.yml` can be selected the same way; it is
ignored by Git. Only name files that actually exist. This step adds no Autoheal
service or automatic restart behavior. Existing configuration overrides remain
under the operator's control.

The sanitized `.env.secrets` template selects
`compose.yml:compose.config.yml:compose.secrets.yml`. For local builds, use
`compose.yml:compose.config.yml:compose.dev.yml:compose.secrets.yml`.
Supply the required private secret files and permissions as described in the
[README](../README.md#use-password-files-with-docker-compose). Do not restore
password environment variables through a personal override loaded afterwards.

## Setup and CI stay explicit

`compose.setup.yml` is still the unchanged standalone setup stack. Do not append
it to the new base/dev combination. Continue selecting it explicitly with
`docker compose --env-file .env -f compose.setup.yml ...`. Its installer,
configuration-path and writable-mount migration is a separate step. The existing
[published-image first-install procedure](installation.md#new-wiki-with-published-images)
also continues to select its setup files explicitly, omitting the normal read-only
config overlay until the generated settings have been copied to the host.

CI and release keep selecting the production base and their isolated test
override explicitly. They do not load the private `.env`, the normal settings
mount or local deployment overlays. Existing application healthchecks, optional
profiles, security tests and Trivy gates remain in force.

## Archived originals and verification

The [snapshot](../archive/2026-11-19-compose-base-dev/README.md) contains the public
Compose files and environment templates from before the migration, plus the old
README as `README.md.txt`. Private local settings were separately backed up into
its Git-ignored `private/` directory with restrictive permissions. `SHA256SUMS`
verifies the public copies. Renovate excludes `archive/**`; these historical
Compose files are not active dependency inputs.

Offline Compose tests validate all four optional-profile combinations, runtime
parity, environment-based mode selection, project/volume identity, local overlay
precedence, secrets and explicit setup/CI selection. Run the
[pre-commit checks](development.md#before-every-commit), then the full E2E suite
for changes to the shared runtime.

Docker documents [file selection](https://docs.docker.com/compose/how-tos/environment-variables/envvars/#compose_file)
and [merge order and relative paths](https://docs.docker.com/compose/how-tos/multiple-compose-files/merge/).
