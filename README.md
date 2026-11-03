# stac-api-load-testing
Taurus and Locust load testing tools for stac-api backends.

![Alt text](readme_files/taurus-pgstac.png?raw=true "stac-fastapi-pgstac")

Requires Python >= 3.11.

## Run stac-fastapi backends locally (elasticsearch|opensearch|pgstac|mongo|stac-os-rs)
```$ docker compose up elasticsearch```   
```$ docker compose up app-elasticsearch```

Backend ports: pgstac `:8083`, elasticsearch `:8084`, opensearch `:8085`, mongo `:8086`, stac-os-rs `:8087`

| backend | app image | database image |
| --- | --- | --- |
| pgstac | stac-fastapi.pgstac 7.2.0 (built locally) | ghcr.io/stac-utils/pgstac:v0.10.0 |
| elasticsearch | ghcr.io/stac-utils/stac-fastapi-es:v8.1.1 | elasticsearch 9.3.2 |
| opensearch | ghcr.io/stac-utils/stac-fastapi-os:v8.1.1 | opensearch 3.8.0 |
| mongo | stac-fastapi.mongo 3.2.0 (built locally) | mongo 7.0 |
| stac-os-rs | ghcr.io/jonhealy1/stac-os-rs:0.2.0 | opensearch 3.8.0 |

All datastores are given a ~2GB memory budget for comparable benchmarks: ES/OpenSearch heaps `-Xms2g -Xmx2g` with `bootstrap.memory_lock`, pgstac `shared_buffers=2GB`, mongo `--wiredTigerCacheSizeGB 2`. Ingest the same data into each backend before comparing (`stac-api-load-testing --ingest --api-address <url>`).

## Install locally for development
```$ pip install -e .```  
    
## Install from PyPI   
```$ pip install stac-api-load-testing```  

```
Usage: stac-api-load-testing [OPTIONS]

  Entry point for the stac-api-load-testing CLI tool.

  This tool facilitates data ingestion, Locust load testing, and Taurus
  performance testing against a specified STAC API endpoint.

  Args:     
  ingest (bool): If True, ingest sample data into the specified STAC API.     
  locust (bool): If True, execute Locust load tests against the
  specified STAC API.     
  taurus (bool): If True, perform Taurus performance
  testing with custom settings against the specified STAC API.     
  concurrency (int): Specifies the number of concurrent users for Taurus testing. Default is 10.      
  ramp_up (str): Specifies the ramp-up period for Taurus testing, in Taurus notation (e.g., '1m' for 1 minute). Default is '1m'.  
  iterations (int): Specifies the number of iterations each virtual user will
  execute in Taurus testing. Default is 100.     
  api_address (str): The base URL of the STAC API to be tested.

Options:
  -i, --ingest               Ingest sample data into the STAC API.
  --collections INTEGER      Number of collections to create for --ingest.
  --items-per-collection INTEGER
                             Items per collection for --ingest; beyond the
                             100 bundled items, duplicates are synthesized
                             with new ids and shifted geometry.
  -l, --locust               Run Locust load tests against the STAC API.
  -t, --taurus               Run the Taurus wrapper for performance testing
                             against the STAC API.
  -c, --concurrency INTEGER  Number of concurrent users for Taurus option.
  -r, --ramp-up TEXT         Ramp-up time for Taurus option.
  -n, --iterations INTEGER   Number of iterations for Taurus option.
  -a, --api-address TEXT     Specify the STAC API URL to test against.
                             Accepts a comma-separated list for --benchmark.
  -b, --benchmark            Run a headless locust benchmark sweep against the
                             STAC API.
  -u, --users TEXT           Comma-separated concurrency levels for
                             --benchmark.
  --spawn-rate INTEGER       Users spawned per second for --benchmark.
  --run-time TEXT            Duration of each --benchmark run, in locust
                             notation (e.g. '30s', '1m').
  -w, --workers INTEGER      Locust worker processes for --benchmark; >1
                             distributes load across cores on this machine.
  -o, --output PATH          Write aggregated --benchmark results to a CSV
                             file.
  --version                  Show the version and exit.
  --help                     Show this message and exit.
```

## Ingest test data - http://localhost:8084 is just an example url
```$ stac-api-load-testing --ingest --api-address http://localhost:8084```

Larger synthetic datasets: `--collections` creates `test-collection`, `test-collection-2`, ..., and `--items-per-collection` controls items per collection. Above the 100 bundled items, duplicates are derived from the sample features with new ids and randomly relocated geometry:

```$ stac-api-load-testing --ingest --api-address http://localhost:8084 --collections 2 --items-per-collection 500```

## Run Locust Load Testing Ouside of Taurus Wrapper
```$ stac-api-load-testing --locust --api-address http://localhost:8084```  
- go to ```http://localhost:8089``` and start with desired settings
- or run headless: ```$ locust --locustfile stac_api_load_testing/config_files/locustfile.py --host http://localhost:8084 --headless -u 10 -r 1 -t 1m```

## Inside of Taurus Wrapper
```$ stac-api-load-testing --taurus --api-address http://localhost:8084```

## Benchmark / compare backends
Runs headless locust sweeps at each concurrency level and prints a comparison
table. Ingest into each backend first, then run them one at a time:

```$ stac-api-load-testing --benchmark --api-address http://localhost:8085 --users 10,50,100 --run-time 1m```

Compare multiple backends in one command (comma-separated addresses):

```$ stac-api-load-testing --benchmark --api-address http://localhost:8085,http://localhost:8087 --users 10,50,100 --run-time 1m -o results.csv```

## Example benchmark: pgstac vs opensearch vs stac-os-rs

Methodology used for the comparison below:

1. Start all three backends, each with its own datastore on a ~2GB memory budget (OpenSearch 3.8.0 `-Xms2g -Xmx2g`, pgstac `shared_buffers=2GB`):

   ```$ docker compose up -d opensearch opensearch-rs app-opensearch app-stac-os-rs pgstac app-pgstac```

2. Ingest the same dataset into each backend — 1 collection (`test-collection`) with 100 Sentinel-2 L2A items:

   ```$ stac-api-load-testing --ingest --api-address http://localhost:8083```   
   ```$ stac-api-load-testing --ingest --api-address http://localhost:8085```   
   ```$ stac-api-load-testing --ingest --api-address http://localhost:8087```

3. Run the benchmark sweep against all three in one command (10/50/100 users, spawn rate 10 users/s, 1 minute per run, 8 locust worker processes):

   ```$ stac-api-load-testing --benchmark --api-address http://localhost:8083,http://localhost:8085,http://localhost:8087 --users 10,50,100 --run-time 1m -w 8 -o results.csv```

Environment: AMD Ryzen 7 8845HS (16 threads), 28GB RAM, Docker 29.8.0, locust 2.47.0 (`-w 8`), stac-fastapi.pgstac 7.2.0, stac-fastapi-os v8.1.1, stac-os-rs 0.2.0. The locustfile drives a read/search workload — landing page, collections, collection items, single items, and GET/POST `/search` with bbox, intersects, and sortby queries; write tasks are disabled.

### Results

| api | users | requests | failures | median (ms) | p95 (ms) | p99 (ms) | req/s |
| --- | --- | --- | --- | --- | --- | --- | --- |
| stac-fastapi-pgstac (:8083) | 10 | 23,844 | 0 | 14 | 120 | 150 | 397 |
| stac-fastapi-pgstac (:8083) | 50 | 30,273 | 0 | 20 | 360 | 1,900 | 504 |
| stac-fastapi-pgstac (:8083) | 100 | 30,094 | 0 | 37 | 570 | 3,400 | 501 |
| stac-fastapi-os (:8085) | 10 | 71,109 | 0 | 6 | 18 | 25 | 1,184 |
| stac-fastapi-os (:8085) | 50 | 88,225 | 0 | 29 | 62 | 98 | 1,469 |
| stac-fastapi-os (:8085) | 100 | 85,916 | 0 | 60 | 120 | 160 | 1,429 |
| stac-os-rs (:8087) | 10 | 153,131 | 0 | 3 | 6 | 31 | 2,551 |
| stac-os-rs (:8087) | 50 | 196,175 | 0 | 11 | 36 | 70 | 3,267 |
| stac-os-rs (:8087) | 100 | 203,499 | 0 | 22 | 62 | 100 | 3,387 |

### Summary

stac-os-rs sustained ~2.3x the throughput of stac-fastapi-os and ~6.7x stac-fastapi-pgstac, peaking at ~3,400 req/s with zero failures across all nine runs. Running enough locust workers matters: in single-process runs the same setup measured only ~1,300 req/s for stac-os-rs and ~860 req/s for stac-fastapi-os because the load generator itself was CPU-bound — with `-w 8` no CPU warnings appeared and reported numbers reflect the backends. stac-fastapi-pgstac is genuinely backend-limited (~500 req/s regardless of generator capacity) and shows severe tail latency at 100 users (p99 3.4s), while the OpenSearch-backed APIs stay under ~160ms p99. These numbers reflect a small (100-item) dataset on a single machine and should be treated as a relative comparison, not absolute capacity.

## Debugging Locust tasks using a single simulated user
```$ python stac_api_load_testing/config_files/locustfile.py```
