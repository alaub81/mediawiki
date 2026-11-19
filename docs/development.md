# Local development and checks

Local entry points and pinned tools are shared with CI. CI now runs both supported
architectures; the release workflow is still awaiting its separate migration.
Branch protection remains deferred. See the [CI and scan policy](ci.md).

## Requirements and tool installation

Use Bash, Git and Python 3.10 or newer. Linters support Linux and macOS on amd64
and arm64. Python is the host runtime; the lint package and native tool versions
are fixed below. No system Python packages or globally installed tools are changed.

Run `./tests/linter-check.sh` to create `.lint-venv/`, install the exact packages
from `tests/requirements-lint.txt` and prepare native tools in `.lint-tools/bin/`.
Initial setup requires network access to PyPI and GitHub release assets. Later
runs reuse matching installed versions. All generated tools/caches are ignored.

| Tool | Pinned version | Declaration |
| --- | --- | --- |
| ShellCheck | 0.11.0 | `lint-tools.json` |
| Hadolint | 2.15.1 | `lint-tools.json` |
| Actionlint | 1.7.12 | `lint-tools.json` |
| Trivy | 0.70.0 | `lint-tools.json` |
| Ruff | 0.17.5 | `tests/requirements-lint.txt` |
| yamllint | 1.38.0 | `tests/requirements-lint.txt` |
| PyYAML | 6.0.3 | `tests/requirements-lint.txt` |
| pathspec | 1.1.1 | `tests/requirements-lint.txt` |

Native release downloads must match their platform-specific SHA-256 checksums.
An existing executable with the required version can instead be copied from
the host PATH into the isolated tool directory. Hadolint has no macOS binary in
this manifest, so macOS users must provide Hadolint 2.15.1 on PATH first. Missing
assets, wrong versions and checksum failures stop the check; they are not skipped.
Keep all platform versions/checksums together when updating the manifest.

## Entry points

These commands locate the checkout independently of the caller's directory:

```bash
./tests/linter-check.sh
./tests/test-check.sh
./tests/integration-check.sh
./tests/e2e-check.sh
```

The scripts reject unsupported arguments and return
a nonzero status when a prerequisite or check fails.

### Linters

`tests/linter-check.sh` checks tracked and new non-ignored files while excluding
deleted paths, private runtime files and tool caches. It checks text hygiene,
local Markdown links/anchors, JSON syntax and duplicate keys, YAML syntax and
duplicate keys, ShellCheck, Hadolint, Actionlint and Python lint/format with Ruff.
Formatting is checked without rewriting files.

ShellCheck covers standalone shell scripts, including the extracted E2E checks.
Actionlint checks the CI workflow and its embedded shell commands. The unchanged
legacy release workflow retains syntax/expression checking without embedded shell
checking until its separate migration.

For intentional Python formatting changes after reviewing the diff:

```bash
.lint-venv/bin/ruff format tests
```

### Offline behavior and Compose tests

`tests/test-check.sh` runs `unittest` discovery for `tests/test_*.py`. It requires
the Docker CLI with the Compose plugin and `jq`, but no running Docker daemon,
accounts or application secrets. It prepares pinned Trivy on first use, requiring
network access for that tool download. The tests themselves need no network or
vulnerability database. The secrets overlay requires Compose 2.24.4+.

The tests exercise:

- Native installer failures, checksums, archive extraction and platform selection
  with mocked downloads; no downloaded executable is run by these unit tests.
- Core, ClamAV, Elasticsearch and full profiles for production, development and
  setup Compose variants, including internal-only OpenSearch access.
- Resolved production/development runtime parity, excluding build/image choices
  and the intentional read-only development `LocalSettings.php` mount.
- The setup variant's writable configuration mount and persistent uploads.
- CI override build contexts relative to the root base file.
- Secrets overlay removal of password values and the intended service grants.
- Change planning, tested-image identity checks and full-report/gate boundaries.

Compose resolution uses only the versioned public environment examples and a
controlled environment. It does not load the private `.env`, create secret files,
start services or touch existing volumes. These configuration checks do not prove
that an uninitialized wiki can install or that an upgrade succeeds.

### MemcachePHP integration test

`tests/integration-check.sh` runs the existing security behavior test. It builds
only MemcachePHP, uses a Memcached container, binds random ports on loopback and
checks Basic Auth, HTML escaping, POST-only mutation, CSRF/session isolation,
key validation, deletion/flushing and the forwarded proxy prefix.

The test creates uniquely named containers, an isolated network and a temporary
image, and removes its own resources in a `finally` block. It does not start the
MediaWiki stack or use production volumes. Initial image pulls/builds can require
network access. Missing Docker access fails with a clear error.

The Python test also remains directly runnable. It now has a `main` guard so
importing it never starts containers, and it rejects optimized Python execution
because its security assertions must remain active.

Use `./tests/integration-check.sh --image EXISTING_IMAGE` to test an already built
MemcachePHP image without rebuilding or deleting that image.

### Full MediaWiki E2E suite

`./tests/e2e-check.sh` builds both images once and runs the complete suite extracted
from the former CI workflow under `tests/e2e/`. `--skip-build` requires the prepared
images instead. Set `TEST_ARCH=amd64` or `TEST_ARCH=arm64` for architecture-specific
tags, or omit it to use host-native `mediawiki-ci:local` and `memcachephp-ci:local`.
The tests require Docker, Compose 2.24.4+, curl, jq and sufficient Docker memory for
the complete ClamAV/Elasticsearch/OpenSearch stack. Initial pulls/builds require
network access; full E2E testing is intentionally separate from offline checks.

The runner creates a random Compose project, loopback port and temporary fixture
directory. A test-only volume holds writable `LocalSettings.php`; no production
configuration directory is mounted. All project containers/networks/volumes are
removed on normal exit or a handled failure. Diagnostics are saved under ignored
`.test-reports/e2e/` or the chosen `--reports` directory. The full suite also runs
MemcachePHP security checks against its existing image without rebuilding.
