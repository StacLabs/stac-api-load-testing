# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](http://keepachangelog.com/en/1.0.0/)
and this project adheres to [Semantic Versioning](http://semver.org/spec/v2.0.0.html).


## [Unreleased]

### Added

### Changed

### Fixed


## [v0.3.0]

### Added

- Added mongodb docker files for local testing [#6](https://github.com/Healy-Hyperspatial/stac-api-load-testing/pull/6)

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


[Unreleased]: <https://github.com/Healy-Hyperspatial/stac-api-load-testing/compare/v0.3.0...main>
[v0.3.0]: <https://github.com/Healy-Hyperspatial/stac-api-load-testing/compare/v0.2.0...v0.3.0>
[v0.2.0]: <https://github.com/Healy-Hyperspatial/stac-api-load-testing/compare/v0.1.1...v0.2.0>
[v0.1.1]: <https://github.com/Healy-Hyperspatial/stac-api-load-testing/compare/v0.1.0...v0.1.1>
[v0.1.0]: <https://github.com/Healy-Hyperspatial/stac-api-load-testing/tree/v0.1.0>