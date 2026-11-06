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

2. Ingest the same dataset into each backend — 4 collections with 500 Sentinel-2 L2A items each (2,000 items total):

   ```$ stac-api-load-testing --ingest --api-address http://localhost:8083 --collections 4 --items-per-collection 500```   
   ```$ stac-api-load-testing --ingest --api-address http://localhost:8085 --collections 4 --items-per-collection 500```   
   ```$ stac-api-load-testing --ingest --api-address http://localhost:8087 --collections 4 --items-per-collection 500```

3. Run the benchmark sweep against all three in one command (10/50/100/150 users, spawn rate 10 users/s, 1 minute per run, 8 locust worker processes):

   ```$ stac-api-load-testing --benchmark --api-address stac-fastapi-pgstac=http://localhost:8083,stac-fastapi-os=http://localhost:8085,stac-os-rs=http://localhost:8087 --users 10,50,100,150 --run-time 1m -w 8 -o results.csv```

Environment: AMD Ryzen 7 8845HS (16 threads), 28GB RAM, Docker 29.8.0, locust 2.47.0 (`-w 8`), stac-fastapi.pgstac 7.2.0, stac-fastapi-os v8.1.1, stac-os-rs 0.5.0. The locustfile drives a read/search workload — landing page, collections, collection items, single items across all collections, GET/POST `/search` with bbox, intersects, sortby, datetime, CQL2, and ids queries, one level of `next`-link pagination, and filtered item lists; every search uses `limit=10`; write tasks are disabled.

Note on parity: stac-fastapi-os and stac-os-rs compute `numberMatched` (total-hit counting) on every search, while this stac-fastapi-pgstac version ships no context extension and skips count work entirely — so pgstac's reported numbers do not include a cost the OpenSearch-backed APIs pay per query.

### Results

| api | collections | items | users | requests | failures | median (ms) | p95 (ms) | p99 (ms) | req/s |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| stac-fastapi-pgstac (:8083) | 4 | 2,000 | 10 | 11,252 | 0 | 27 | 140 | 170 | 187 |
| stac-fastapi-pgstac (:8083) | 4 | 2,000 | 50 | 13,817 | 0 | 54 | 780 | 2,500 | 230 |
| stac-fastapi-pgstac (:8083) | 4 | 2,000 | 100 | 13,629 | 0 | 120 | 1,300 | 5,900 | 227 |
| stac-fastapi-pgstac (:8083) | 4 | 2,000 | 150 | 13,619 | 0 | 250 | 1,600 | 7,300 | 227 |
| stac-fastapi-os (:8085) | 4 | 2,000 | 10 | 49,492 | 0 | 9 | 25 | 32 | 824 |
| stac-fastapi-os (:8085) | 4 | 2,000 | 50 | 59,998 | 0 | 43 | 98 | 140 | 999 |
| stac-fastapi-os (:8085) | 4 | 2,000 | 100 | 58,755 | 0 | 90 | 170 | 220 | 978 |
| stac-fastapi-os (:8085) | 4 | 2,000 | 150 | 51,455 | 0 | 150 | 270 | 330 | 857 |
| stac-os-rs (:8087) | 4 | 2,000 | 10 | 100,517 | 0 | 5 | 10 | 12 | 1,674 |
| stac-os-rs (:8087) | 4 | 2,000 | 50 | 131,865 | 0 | 20 | 38 | 47 | 2,196 |
| stac-os-rs (:8087) | 4 | 2,000 | 100 | 130,389 | 0 | 40 | 68 | 82 | 2,170 |
| stac-os-rs (:8087) | 4 | 2,000 | 150 | 105,080 | 0 | 72 | 120 | 150 | 1,748 |

### Summary

stac-os-rs sustained ~2.2x the throughput of stac-fastapi-os and ~8.8x stac-fastapi-pgstac, peaking at ~2,200 req/s with zero failures across all twelve runs. All three backends saturate by ~100 users on this box — throughput knees at ~250 (pgstac), ~1,000 (fastapi-os), and ~2,200 (stac-os-rs) req/s; at 150 users each shows the classic overload curve with declining throughput and rising latency. The OpenSearch-backed APIs degrade without errors, as does pgstac — its earlier failures (CQL2 500s, dropped connections) traced to Docker's 64MB `/dev/shm` default starving Postgres parallel-query workers, fixed by `shm_size: 1gb` on the pgstac container; with that resolved its ~230 req/s ceiling is clean but its p99 still reaches 7.3s at 150 users. Running enough locust workers matters: in single-process runs the same setup measured only ~1,000 req/s because the load generator itself was CPU-bound — with `-w 8` no CPU warnings appeared and reported numbers reflect the backends. These numbers reflect a 2,000-item dataset on a single machine and should be treated as a relative comparison, not absolute capacity.

## Debugging Locust tasks using a single simulated user
```$ python stac_api_load_testing/config_files/locustfile.py```
