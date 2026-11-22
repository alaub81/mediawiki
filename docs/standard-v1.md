# Repository Standard v1: MediaWiki profile

This repository builds the MediaWiki and MemcachePHP images for `linux/amd64`
and `linux/arm64`. The migration is staged; this document does not certify that
every target-standard requirement or production scenario is already satisfied.
The shared target document is maintained outside this repository under
`/GIT/REPOSITORY-STANDARD-v1.md` (the local checkout directory may differ).

| Area | Repository implementation |
| --- | --- |
| Structure | Image-specific files under `resources/mediawiki` and `resources/memcachephp`; [layout and Compose migration](repository-structure.md). |
| Compose modes | Shared runtime base, read-only config overlay and local-build overlay selected through `.env`; [mode selection](compose-modes.md). The existing setup stack remains standalone pending its separate migration. |
| Local verification | Shared lint/test entry points and pinned tool releases with checksums; [development](development.md). |
| CI and security | Change planning, native tests for both architectures, shared image artifacts, HIGH/CRITICAL gates and independently uploaded full SARIF; [CI](ci.md). |
| Releases | Successful source CI required before publication, compatible image reuse, explicit alias promotion and automatic release notes; [releases](releases.md). |
| Dependencies | Renovate regular updates, Dependabot security ownership, compatibility ranges and Supercronic allowlist; [dependency policy](dependencies.md). |
| Documentation | Root README keeps local builds, setup, profiles, maintenance and advanced features; detailed [installation](installation.md) and [operations](operations.md) guides supplement it. |
| GitHub metadata | Issue/PR templates, security policy, release-note configuration and `.github/FUNDING.yml`. |

Documentation and source comments are written in English. Localized product text
and user-selected wiki languages may remain localized. README revisions must
preserve existing functionality, commands and operational caveats; if a detailed
procedure moves to another document, keep a descriptive link in the README.
Do not replace advanced features with a shortened generic quickstart.

## Outstanding work and verification limits

- Existing fixable HIGH/CRITICAL image findings remain release blockers. Updating
  Renovate policy does not fix them, and no exceptions or relaxed gates are added.
- Dependabot alerts/security-update activation and current Mend application mode
  need account-side verification; see the dependency policy.
- The published installer currently writes an invalid boolean antivirus value
  with ClamAV disabled. The installation guide records a targeted workaround.
  A runtime fix and a full custom-path/setup-variant regression remain follow-ups.
- Extension branch fallback, ineffective extension/skin build arguments, scheduled
  job permissions, CirrusSearch bootstrap behavior and other historical review
  items remain visible in the [backlog](../notices_and_todos.md).
- A production backup/restore exercise remains an operator responsibility.

The repository maintainer owns these follow-ups; review open blockers before the
next release. Branch protection is deferred by explicit decision. Kiwione is
outside this migration and remains unchanged.

On 2026-11-19, the published-image installation procedure, including the stated
antivirus workaround, was tested in a disposable core-stack project. All services
became healthy, siteinfo returned successfully, and the same wiki remained
accessible after recreating MediaWiki with the protected read-only settings mount.
The test project's containers, networks and volumes were removed afterwards.
This verifies that procedure, not every historical setup or secrets variant.
