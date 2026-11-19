# Dependency updates

## Ownership and timing

Renovate owns regular version updates. Its repository configuration permits new
PRs on Mondays from 00:00 to 05:59, Europe/Berlin, with a minimum release age of
three days and at most three concurrent PRs. This is an allowed window, not a
guaranteed execution time. The installed application must actually run during
that window. Review the [Dependency Dashboard](https://github.com/alaub81/mediawiki/issues/15)
for pending updates and run details in the Mend application.

Dependabot owns alert-driven security updates. `open-pull-requests-limit: 0`
disables its regular version PRs, not its security PRs. Those security PRs do not
inherit Renovate's Monday window or three-day delay. Renovate vulnerability PRs
are disabled to avoid two bots owning the same alert. Repository settings must
enable Dependabot alerts and security updates for this division to work.

See the official [Dependabot security PR documentation](https://docs.github.com/en/code-security/how-tos/secure-your-supply-chain/manage-your-dependency-security/customizing-dependabot-security-prs)
and [Renovate scheduling documentation](https://docs.renovatebot.com/key-concepts/scheduling/).

## Coverage and compatibility

| Dependency | Source and update policy |
| --- | --- |
| GitHub Actions | Workflow references; related non-major updates grouped together. |
| Python lint tools | `tests/requirements-lint.txt`; minor/patch updates grouped. |
| Native check tools | `lint-tools.json`; each release asset's version and SHA-256 updated together through `github-release-attachments`. |
| Supercronic | Download URL in `resources/mediawiki/Dockerfile`; covers both target architectures. |
| Base and service images | Dockerfiles and Compose files, plus annotated versions in `.env.example` and `.env.secrets`. |
| MediaWiki | Remains on the tested `1.46` line; moving to another line requires a compatibility review and a configuration change. |
| CirrusSearch OpenSearch | Remains on Wikimedia's `v1.3.x-build` images; other major lines are deliberately outside the allowed range. |
| Wanda Elasticsearch | Remains on `8.19.x`; review Wanda compatibility before changing that range. |
| Published project images | This repository's own image references are excluded from Renovate to avoid release/update loops. Update their release line deliberately. |

Docker packages are otherwise separate, so unrelated services do not share one
large update PR. Major updates require manual review; majors outside the explicit
compatibility ranges are not proposed until the range is changed deliberately.
Do not interpret a quiet dashboard as proof that every upstream major is allowed.

Floating tags such as `alpine` or `stable` do not themselves pin image contents.
Image refreshes and [Trivy gates](ci.md#vulnerability-evidence-and-gate) remain necessary. Dependabot
also cannot repair every package vulnerability inside a container image; its
security coverage depends on supported ecosystems and available dependency alerts.
Extension branches and commits cloned by the Dockerfile still need a separate
compatibility review; they are not covered by the new regex managers.

## Automerge

Only Supercronic minor and patch updates are allowlisted. They use their own PR,
wait for successful tests (`ignoreTests: false`), and rebase when behind the base
branch. Renovate performs the merge itself (`platformAutomerge: false`); GitHub's
native auto-merge switch is not required. All other updates remain manual.
The [CI change planner](ci.md) must continue classifying Dockerfile changes as
image changes so a documentation-only check cannot approve a Supercronic update.
Current image vulnerabilities can therefore also prevent these PRs from merging.
Branch protection remains deferred; no GitHub enforcement settings are changed.

## Validation and application settings

Run `./tests/linter-check.sh` and `./tests/test-check.sh` after changing the config.
The offline dependency tests check regex coverage against actual files, every
native asset's version/digest pair, and the compatibility boundaries.
Validate the schema with the official validator as well. For example, from the
repository root, this mounts only the public configuration file:

```bash
docker run --rm -v "$PWD/renovate.json:/work/renovate.json:ro" -w /work \
  --entrypoint renovate-config-validator ghcr.io/renovatebot/renovate:44.252.8 \
  --strict renovate.json
```

Actual extraction was also checked with that Renovate version in a temporary
Git snapshot containing only public tracked files. Do not give a local extraction
test access to private `.env`, credentials, live configuration or backup files.
Extraction without a GitHub token does not verify release lookups or actual PR
creation. Consult [Renovate's local platform documentation](https://docs.renovatebot.com/modules/platform/local/).

The GitHub dependency dashboard confirms that Renovate has processed this repo.
Application access and its current mode must still be checked in Mend: select
the repository, confirm Renovate is enabled and that the mode permits PRs, then
inspect the latest job log. The GitHub API inspection for this migration did not
expose whether Dependabot alerts/security updates are enabled. Check those two
switches in repository Settings → Security → Code security (the exact navigation
can vary). A committed `dependabot.yml` does not activate missing account settings.
Do not enable branch protection as part of this check.
