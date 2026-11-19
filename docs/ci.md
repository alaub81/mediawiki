# CI and Trivy policy

This describes step 3 of Repository Standard v1. The subsequent release migration
is documented in the [release guide](releases.md). Branch protection remains deferred; `CI required`
is a workflow result, not an assertion that GitHub enforces branch rules.

## Plan and execute only applicable checks

`tools/change_plan.py` reads the complete diff. Unknown/unavailable bases, shared
runtime inputs, workflows and test-runner changes require the full stack.
Documentation-only changes run static checks without application builds.
Known lint/bot/tool-manifest changes run offline checks without application builds.
Image-context inputs always count as image changes, including files ending in
`.md` inside a build context.

Directly affected image contexts are recorded separately. Full E2E tests require
the dependency closure of both current-source images: MediaWiki proxies the
MemcachePHP UI, so neither is replaced by a possibly stale published image.

Linters and offline/Compose regressions run once through the same local commands.
Independent architecture jobs use `fail-fast: false`:

| Own image | Platforms | Native CI runners |
| --- | --- | --- |
| `mediawiki-custom` | `linux/amd64`, `linux/arm64` | `ubuntu-24.04`, `ubuntu-24.04-arm` |
| `memcachephp` | `linux/amd64`, `linux/arm64` | `ubuntu-24.04`, `ubuntu-24.04-arm` |

CI and release control jobs also use `ubuntu-24.04`. The pinned Actionlint
1.7.12 does not recognize Ubuntu 26.04 runner labels, so Renovate's
`github-runners` rule restricts the `ubuntu` package to `24.04` for now.
Review that range when a released Actionlint version supports the newer labels,
then update the tool manifest and runner policy together. Runner-label checking
remains enabled; no custom-label override is added.

The third-party Wikimedia OpenSearch image remains amd64, as in the production
template. The arm64 runner enables amd64 emulation for that dependency only; the
two own application images build and run natively. This is not a claim that the
complete stack is entirely native arm64. GitHub lists the available
[native runner labels](https://docs.github.com/en/actions/reference/runners/github-hosted-runners).

Each application image is built once per architecture with an architecture/image
specific cache. A receipt records its immutable local ID and architecture before
E2E. The same tags are used without `--build` for the full stack and reused for
the MemcachePHP security test. The scanner verifies the receipt again and scans
the recorded IDs. Missing images, wrong platforms or changed tags fail.

There is no CI push to GHCR and no registry login. PR jobs do not need production
secrets. `CI required` always evaluates lint and architecture-job results; a
skipped stack is accepted only when the successful planner explicitly selected it.
New pushes can cancel stale CI runs on the same PR/branch.

## Full-stack E2E and isolation

The existing checks are extracted into `tests/e2e/` and invoked by the shared
`tests/e2e-check.sh`. They still cover database readiness, installation, API,
sitemaps, short URLs, upload response headers, loaded extensions/skins, page
creation, Memcached, site information, CirrusSearch indexing/search, rendered
pages, RottenLinks, antivirus rejection and the MemcachePHP proxy. Database
authentication is now a mandatory SQL query rather than an optional TCP ping.
The existing upstream-patch warning remains visible.

The generated stack uses `tests/e2e.env`, disposable credentials, loopback ports,
a random project name and project-owned volumes/networks. Fixed bridge names
from the production template are removed in the test override. A writable
test-only configuration volume is owned by `www-data` before installation.
The runner never mounts or writes a production `LocalSettings.php`.

The test override is for use with the root-level base file, not standalone.
Production/development/setup Compose files retain their application behavior.
Diagnostics are collected and the temporary stack is removed even after a test
failure. Abrupt VM termination still relies on the ephemeral runner's lifecycle.
Elasticsearch is started with the existing full profile; no real external AI API
is called. These tests do not replace a production-data upgrade rehearsal.

## Vulnerability evidence and gate

Trivy 0.70.0 is pinned, including download checksums, in `lint-tools.json`.
`tests/scan-images.sh` performs one vulnerability scan per own image to JSON:

- JSON and derived SARIF retain UNKNOWN, LOW, MEDIUM, HIGH and CRITICAL findings,
  including vulnerabilities without a fix.
- A separate gate input retains fixable findings. Conversion blocks HIGH and
  CRITICAL with exit code 1. Full reports are never filtered by the gate.
- There are no blanket suppressions, `continue-on-error` gates or CVE exceptions.
  Scanner/database/conversion errors fail the job.
- Image/architecture-specific filenames and SARIF categories keep results distinct.
- Scan attempts continue for the second image after an image scan or gate failure.
  Scans also run after E2E failure if the build succeeded.

This follows Trivy's [JSON conversion interface](https://trivy.dev/docs/latest/references/configuration/cli/trivy_convert/).
Real pinned Trivy conversion is exercised offline with synthetic vulnerabilities
to verify fixable HIGH/CRITICAL failures and preservation of full JSON/SARIF.
Only the image-reading step is simulated in those tests, so no database or
registry is needed for policy regressions.

Complete reports, tested-image receipts and bounded E2E diagnostics are uploaded
with `always()` and retained for seven days. Public main pushes additionally
upload SARIF to Code Scanning after checking file existence. Fork/Dependabot PRs
keep full artifact reports without requesting Code Scanning upload. Published
release images are not changed by this CI migration.

CI detects the reports in `RUNNER_TEMP` with an `always()` Bash step and passes
its result to the upload condition. Both detection and upload therefore run
independently of the vulnerability gate's exit status. Do not use `hashFiles()`
for these temporary paths: GitHub restricts that function to files inside
`GITHUB_WORKSPACE` ([expression documentation](https://docs.github.com/en/actions/reference/workflows-and-actions/expressions#hashfiles)).
Release reports already reside under the workspace's `reports/trivy` directory,
where its existing `hashFiles()` existence check remains valid.

## Local verification on 2026-11-18

Both own images built for amd64 and arm64. The full E2E suite and MemcachePHP
security checks passed for each architecture. Local arm64 execution was native;
local amd64 execution used Docker Desktop emulation. The configured native GitHub
runner matrix still needs confirmation after this change is pushed.

Linters and all 24 offline regressions passed. The actual image scans returned
gate failure for both architectures, with complete JSON and SARIF preserved:

| Image | Fixable HIGH | Fixable CRITICAL | Architecture results |
| --- | --- | --- | --- |
| MediaWiki | 12 | 4 | Same counts for amd64 and arm64 |
| MemcachePHP | 7 | 4 | Same counts for amd64 and arm64 |

These counts are package findings, not unique CVEs. They include Apache packages
(`CVE-2026-119618`), `linux-libc-dev` and `zlib1g`; MediaWiki also contains Go
standard-library findings in Supercronic. Image security updates require a
separate follow-up before CI can become green. The CI migration does not waive
those findings, change the application Dockerfiles or add exceptions.

Local evidence is under ignored `.test-reports/step3/<arch>/`, including E2E logs,
exit codes, recorded image IDs and full `trivy/*.json`/`trivy/*.sarif` reports.
This snapshot describes the local build inputs and database at that time; future
base-image, package, Supercronic or database updates must be scanned again.
