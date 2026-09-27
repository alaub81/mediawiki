# Security Policy

This repository contains the Docker setup from **LHlab wiki**, including the custom MediaWiki and MemcachePHP images. Please report security issues in this setup privately so they can be investigated before public disclosure.

## Supported versions

Security fixes are developed against the current `main` branch and, when appropriate, published in a new versioned image release. The currently documented MediaWiki release line is `1.46.x`. Older tags remain available, but fixes are not guaranteed to be backported to them. Please include the exact Git commit, release tag, or image tag in your report, regardless of the version affected.

## Report a vulnerability

If the repository offers **Report a vulnerability**, use the private report form under [Security → Advisories](https://github.com/alaub81/mediawiki/security/advisories/new). If that option is unavailable, [open an issue requesting a private security contact](https://github.com/alaub81/mediawiki/issues/new) **without posting exploit details, credentials, or other sensitive information**. Do not submit a vulnerability description in a public issue.

Please include, where possible:

- The affected component, file, and commit or image tag.
- The impact and steps to reproduce the issue in a test environment.
- Relevant configuration, logs, or screenshots with secrets and personal data removed.
- Any known mitigation.

We will review reports and coordinate a fix and disclosure with the reporter. No fixed acknowledgement or remediation deadline is promised.

## Scope

Issues in this repository are in scope, including:

- Dockerfiles, Compose files, GitHub Actions workflows, and release configuration.
- Entrypoint and maintenance scripts, Apache proxy and rewrite configuration, and the bundled MemcachePHP application.
- Example MediaWiki configuration and this stack's handling of credentials, Docker secrets, uploads, and internal services.
- Integration problems involving MediaWiki, MariaDB, OpenSearch, Elasticsearch, Memcached, or ClamAV when caused by this repository's configuration or code.

Vulnerabilities that exist solely in an upstream project should be reported to that project's maintainers. If this stack's configuration makes an upstream issue exploitable or prevents a fix from being applied, please report that here as well.

## Responsible testing

Test only systems you own or are authorized to assess. Avoid accessing other users' data or disrupting a production wiki. Give maintainers an opportunity to investigate and coordinate disclosure before publishing details.
