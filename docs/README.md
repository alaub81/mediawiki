# Documentation

The [root README](../README.md) remains the main guide. Its existing setup,
compatibility, local build, maintenance and troubleshooting instructions are
retained during the staged Repository Standard v1 migration.

- [Repository structure and Compose filename migration](repository-structure.md)
- [Shared Compose base, .env mode selection and local-build migration](compose-modes.md)
- [Local development, pinned tools and test commands](development.md)
- [Checks before every commit and additional tests by change type](development.md#before-every-commit)
- [CI architectures, test isolation and Trivy policy](ci.md)
- [Release gates, image reuse, version aliases and release notes](releases.md)
- [Dependency update ownership, schedules and compatibility](dependencies.md)
- [Installation, private settings and first-start persistence](installation.md)
- [Operations, backups and restore verification](operations.md)
- [Read-only extension usage audit](extension-audit.md)
- [Standard v1 implementation and remaining work](standard-v1.md)
- [Requirements](../README.md#requirements)
- [Quick start and password files](../README.md#quick-start)
- [Local image builds](../README.md#build-and-run-locally)
- [OpenSearch configuration](../README.md#opensearch-configuration)
- [CirrusSearch indexing](../README.md#building-the-cirrussearch-index)
- [Scheduled jobs](../README.md#scheduled-jobs)
- [ClamAV](../README.md#clamav)
- [Memcached and MemcachePHP](../README.md#memcached-and-memcachephp)
- [Production upgrade](../README.md#production-upgrade-from-145x-to-146)
- [Troubleshooting](../README.md#troubleshooting)
- [Security policy](../SECURITY.md)

The [NGINX host configuration example](examples/nginx_mw_proxy_vhost_example.conf)
is an optional reference, not part of either image. It assumes additional host
services and include files; review its domains, ports, TLS and cache settings
before adapting it to your deployment.
