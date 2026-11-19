# Documentation

The [root README](../README.md) remains the main guide. Its existing setup,
compatibility, local build, maintenance and troubleshooting instructions are
retained during the staged Repository Standard v1 migration.

- [Repository structure and Compose filename migration](repository-structure.md)
- [Local development, pinned tools and test commands](development.md)
- [CI architectures, test isolation and Trivy policy](ci.md)
- [Requirements](../README.md#requirements)
- [Quick start and password files](../README.md#quick-start)
- [Local image builds](../README.md#repository-layout)
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
