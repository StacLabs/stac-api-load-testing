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
  -o, --output PATH          Write aggregated --benchmark results to a CSV
                             file.
  --version                  Show the version and exit.
  --help                     Show this message and exit.
```

## Ingest test data - http://localhost:8084 is just an example url
```$ stac-api-load-testing --ingest --api-address http://localhost:8084```

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

## Debugging Locust tasks using a single simulated user
```$ python stac_api_load_testing/config_files/locustfile.py```
