# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](http://keepachangelog.com/en/1.0.0/)
and this project adheres to [Semantic Versioning](http://semver.org/spec/v2.0.0.html).


## [Unreleased]

### Added

- Added `-w/--workers` option for `--benchmark`: passes `--processes N` to locust, spawning N worker processes so a single-process CPU ceiling doesn't cap throughput

### Changed

- Rebalanced the locust workload: collection ids, item ids, and bboxes are cached per user in `on_start` instead of re-fetched every task; `get_item` picks a random item from a random collection (was 11 hot fixture ids in one collection); search fan-out is capped at 3 item fetches — get-item was ~88% of all requests
- Raised pgstac `DB_MAX_CONN_SIZE` from 1 to 10 (`DB_MIN_CONN_SIZE` 2) so its connection pool is comparable to the other backends' default client pools

### Fixed


## [v0.3.1]

### Added

- Added README section documenting an example stac-fastapi-os vs stac-os-rs benchmark: methodology, environment, results table, and summary

### Fixed

- Added missing `"type": "Collection"` to the sample collection fixture; required by STAC 1.0.0 and enforced by stac-fastapi v8 backends, so ingest was failing


## [v0.3.0]

### Added

- Added mongodb docker files for local testing [#6](https://github.com/Healy-Hyperspatial/stac-api-load-testing/pull/6)
- Added `stac-os-rs` backend (`ghcr.io/jonhealy1/stac-os-rs:0.2.0` on `:8087` with a dedicated OpenSearch 3.8.0 datastore)
- Added `--benchmark` mode: headless locust concurrency sweep with a comparison table and optional CSV output (`--users`, `--spawn-rate`, `--run-time`, `-o/--output`; comma-separated `--api-address` compares multiple backends)

### Changed

- Updated stac-fastapi backends: pgstac 7.2.0 (pgstac v0.10.0 image, new `PG*` env vars), mongo 3.2.0 (mongo 7.0 image)
- Elasticsearch/OpenSearch apps now use the published sfeos images (`ghcr.io/stac-utils/stac-fastapi-es:v8.1.1`, `stac-fastapi-os:v8.1.1`, multi-arch) with `BACKEND=` env var and ES 9.3.2 / OpenSearch 3.5.0 datastores
- Migrated packaging from `setup.py` to `pyproject.toml`; now requires Python >= 3.11
- Replaced deprecated `pkg_resources` with `importlib.resources`
- Updated dependencies: locust >= 2.32, bzt >= 1.17.0; added missing `requests` and `pyyaml` requirements
- Updated pre-commit hooks (isort 9.0.2, black 26.10.1, flake8 7.4.0, mypy 2.4.0, pydocstyle 6.3.0)
- CI now tests Python 3.11-3.13

### Fixed

- Fixed missing `__init__.py` in the `stac_api_load_testing` package
- Fixed typo in Taurus template `default-address`
- `data_loader` subpackage and setup data are now included in built distributions
- Backend apps now wait for their datastore before starting (docker compose)
- Datastores given equal ~2GB memory budgets for fair backend comparison (ES/OS `-Xms2g -Xmx2g` + memlock, pgstac `shared_buffers=2GB`, mongo `wiredTigerCacheSizeGB 2`)



## [v0.2.0]

### Added

- Taurus config options in cli. [#5](https://github.com/Healy-Hyperspatial/stac-api-load-testing/pull/5)

### Changed

### Fixed


## [v0.1.1]

### Added

- Added opensearch docker files for local testing [#3](https://github.com/Healy-Hyperspatial/stac-api-load-testing/pull/3)

### Changed

### Fixed

- Fixed sample data location in package files [#4](https://github.com/Healy-Hyperspatial/stac-api-load-testing/pull/4)


## [v0.1.0]

### Added

- First release


[Unreleased]: <https://github.com/Healy-Hyperspatial/stac-api-load-testing/compare/v0.3.1...main>
[v0.3.1]: <https://github.com/Healy-Hyperspatial/stac-api-load-testing/compare/v0.3.0...v0.3.1>
[v0.3.0]: <https://github.com/Healy-Hyperspatial/stac-api-load-testing/compare/v0.2.0...v0.3.0>
[v0.2.0]: <https://github.com/Healy-Hyperspatial/stac-api-load-testing/compare/v0.1.1...v0.2.0>
[v0.1.1]: <https://github.com/Healy-Hyperspatial/stac-api-load-testing/compare/v0.1.0...v0.1.1>
[v0.1.0]: <https://github.com/Healy-Hyperspatial/stac-api-load-testing/tree/v0.1.0>