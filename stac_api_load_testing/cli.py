"""stac-api-load-testing cli tool."""

import csv
import os
import re
import shutil
import subprocess
import sys
import tempfile
from importlib import resources
from pathlib import Path

import click
import requests
import yaml

from .data_loader import data_loader


def _package_resource(*parts: str) -> str:
    """Return the filesystem path to a resource bundled in this package."""
    return str(resources.files("stac_api_load_testing").joinpath(*parts))


def _tool_path(name: str) -> str:
    """Resolve a console script on PATH, falling back to this env's bin dir."""
    return shutil.which(name) or str(Path(sys.executable).parent / name)


def generate_taurus_config(api_url: str, concurrency: int, ramp_up, iterations) -> str:
    """
    Generate a custom Taurus configuration file based on the specified settings.

    Args:
        api_url (str): The base URL for the STAC API to be tested.
        concurrency (int): The number of concurrent users to simulate.
        ramp_up (str): The duration over which to ramp up the load test.
        iterations (int): The total number of iterations to perform.

    Returns:
        str: The path to the generated Taurus configuration file.
    """
    template_path = _package_resource("config_files", "taurus_locust.yml")
    locustfile_path = _package_resource("config_files", "locustfile.py")

    safe_api_url = re.sub(r"[^a-zA-Z0-9]+", "_", api_url)
    output_path = f"taurus_config_{safe_api_url}.yml"

    try:
        with open(template_path, "r") as file:
            config = yaml.safe_load(file)

        # Setting the script path directly to where `locustfile.py` is expected to be within the package
        config["execution"][0]["concurrency"] = concurrency
        config["execution"][0]["ramp-up"] = ramp_up
        config["execution"][0]["iterations"] = iterations
        config["scenarios"]["default"]["script"] = locustfile_path
        config["scenarios"]["default"]["default-address"] = api_url

        with open(output_path, "w") as file:
            yaml.safe_dump(config, file)

        return output_path
    except Exception as e:
        print(f"Error creating Taurus configuration file: {e}")
        return None


def _read_aggregated_stats(csv_path: str) -> dict:
    """Return the 'Aggregated' row from a locust *_stats.csv file."""
    with open(csv_path, newline="") as file:
        for row in csv.DictReader(file):
            if row.get("Name") == "Aggregated":
                return row
    return {}


def _collection_ids(base_url: str) -> list:
    """Return all collection ids served by a STAC API."""
    response = requests.get(f"{base_url}/collections", timeout=30)
    response.raise_for_status()
    return [c["id"] for c in response.json().get("collections", [])]


def _collection_item_count(base_url: str, collection_id: str) -> int:
    """Count items in one collection, preferring the cheap numberMatched field."""
    response = requests.post(
        f"{base_url}/search",
        json={"collections": [collection_id], "limit": 1},
        timeout=30,
    )
    response.raise_for_status()
    matched = response.json().get("numberMatched")
    if matched is not None:
        return matched

    # APIs without the context extension: count by paging the items endpoint.
    count = 0
    url = f"{base_url}/collections/{collection_id}/items?limit=500"
    for _ in range(100):
        response = requests.get(url, timeout=60)
        response.raise_for_status()
        page = response.json()
        count += len(page.get("features", []))
        url = next(
            (
                link["href"]
                for link in page.get("links", [])
                if link.get("rel") == "next" and link.get("href")
            ),
            None,
        )
        if url is None:
            return count
    return count


def _api_metadata(base_url: str) -> dict:
    """Fetch the catalog title and dataset size from a STAC API.

    Returns a dict with 'name', 'collections' and 'items' keys; fields are
    empty when the API is unreachable or doesn't report them.
    """
    meta: dict[str, object] = {"name": "", "collections": "", "items": ""}
    try:
        response = requests.get(base_url, timeout=30)
        response.raise_for_status()
        meta["name"] = response.json().get("title", "")
    except requests.RequestException as exc:
        click.secho(f"could not fetch catalog info from {base_url}: {exc}", fg="yellow")

    try:
        collection_ids = _collection_ids(base_url)
        meta["collections"] = len(collection_ids)
        meta["items"] = sum(
            _collection_item_count(base_url, collection_id)
            for collection_id in collection_ids
        )
    except requests.RequestException as exc:
        click.secho(f"could not count items in {base_url}: {exc}", fg="yellow")
    return meta


def run_benchmark(
    api_addresses: list,
    concurrency_levels: list,
    spawn_rate: int,
    run_time: str,
    output: str,
    workers: int,
):
    """
    Run headless Locust benchmark sweeps against one or more STAC APIs.

    For each API address, a headless locust run is executed at every
    concurrency level. Aggregated statistics are collected from locust's
    CSV output and printed as a comparison table.

    Args:
        api_addresses (list): STAC API base URLs to benchmark, in order.
        concurrency_levels (list): Concurrent user counts to sweep.
        spawn_rate (int): Users spawned per second in each run.
        run_time (str): Duration of each run, in locust notation (e.g. '30s').
        output (str): Optional path to write aggregated results as CSV.
        workers (int): Locust worker processes (--processes); >1 runs
            distributed on this machine to avoid a single-process CPU ceiling.
    """
    locustfile_path = _package_resource("config_files", "locustfile.py")
    results = []

    for target in api_addresses:
        # Targets can be labelled: "name=http://..." overrides the catalog title.
        name, _, address = target.partition("=")
        if not address:
            name, address = "", target

        meta = _api_metadata(address)
        api_name = name or meta["name"] or address
        click.secho(
            f"\n=== {api_name} ({address}) — "
            f"{meta['collections']} collections, {meta['items']} items ===",
            fg="cyan",
        )
        for users in concurrency_levels:
            click.secho(f"\n>>> {address} @ {users} users for {run_time}", fg="cyan")
            with tempfile.TemporaryDirectory() as tmpdir:
                csv_prefix = os.path.join(tmpdir, "locust")
                stats_csv = f"{csv_prefix}_stats.csv"
                cmd = [
                    _tool_path("locust"),
                    "--locustfile",
                    locustfile_path,
                    "--host",
                    address,
                    "--headless",
                    "-u",
                    str(users),
                    "-r",
                    str(spawn_rate),
                    "-t",
                    run_time,
                    "--csv",
                    csv_prefix,
                    "--only-summary",
                ]
                if workers > 1:
                    cmd += ["--processes", str(workers)]
                # locust exits non-zero when requests fail; under load that is
                # data (backend errors), not a benchmark tool error.
                subprocess.run(cmd)

                if not os.path.exists(stats_csv):
                    click.secho(
                        f"no stats produced for {address} @ {users} users",
                        fg="red",
                    )
                    continue

                stats = _read_aggregated_stats(stats_csv)
                if stats:
                    results.append(
                        {
                            "api": api_name,
                            "url": address,
                            "collections": meta["collections"],
                            "items": meta["items"],
                            "users": users,
                            "requests": stats.get("Request Count"),
                            "failures": stats.get("Failure Count"),
                            "median_ms": stats.get("Median Response Time"),
                            "p95_ms": stats.get("95%"),
                            "p99_ms": stats.get("99%"),
                            "rps": round(float(stats.get("Requests/s") or 0), 1),
                        }
                    )

    if not results:
        click.secho("No benchmark results collected.", fg="red")
        return

    header = (
        f"{'api':<36}{'colls':>6}{'items':>7}{'users':>7}{'reqs':>9}"
        f"{'fails':>7}{'med':>8}{'p95':>8}{'p99':>8}{'rps':>9}"
    )
    click.echo("\n" + header)
    click.echo("-" * len(header))
    for row in results:
        click.echo(
            f"{row['api']:<36}{row['collections']:>6}{row['items']:>7}"
            f"{row['users']:>7}{row['requests']:>9}"
            f"{row['failures']:>7}{row['median_ms']:>8}{row['p95_ms']:>8}"
            f"{row['p99_ms']:>8}{row['rps']:>9}"
        )

    if output:
        with open(output, "w", newline="") as file:
            writer = csv.DictWriter(file, fieldnames=list(results[0].keys()))
            writer.writeheader()
            writer.writerows(results)
        click.secho(f"\nResults written to {output}", fg="green")


@click.command()
@click.option(
    "-i", "--ingest", is_flag=True, help="Ingest sample data into the STAC API."
)
@click.option(
    "-l", "--locust", is_flag=True, help="Run Locust load tests against the STAC API."
)
@click.option(
    "-t",
    "--taurus",
    is_flag=True,
    help="Run the Taurus wrapper for performance testing against the STAC API.",
)
@click.option(
    "-c",
    "--concurrency",
    default=10,
    help="Number of concurrent users for Taurus option.",
    type=int,
)
@click.option("-r", "--ramp-up", default="1m", help="Ramp-up time for Taurus option.")
@click.option(
    "-n",
    "--iterations",
    default=100,
    help="Number of iterations for Taurus option.",
    type=int,
)  # Changed the flag to -n to avoid conflict
@click.option(
    "-a",
    "--api-address",
    default="http://localhost:8080",
    help="Specify the STAC API URL to test against. Accepts a comma-separated list for --benchmark; prefix with 'name=' to label a target in results.",
)
@click.option(
    "--collections",
    default=1,
    help="Number of collections to create for --ingest (test-collection, test-collection-2, ...).",
    type=int,
)
@click.option(
    "--items-per-collection",
    default=100,
    help="Items to load per collection for --ingest; beyond the 100 bundled items, duplicates are synthesized with new ids and shifted geometry.",
    type=int,
)
@click.option(
    "-b",
    "--benchmark",
    is_flag=True,
    help="Run a headless locust benchmark sweep against the STAC API.",
)
@click.option(
    "-u",
    "--users",
    default="10,50,100",
    help="Comma-separated concurrency levels for --benchmark.",
)
@click.option(
    "--spawn-rate",
    default=10,
    help="Users spawned per second for --benchmark.",
    type=int,
)
@click.option(
    "--run-time",
    default="30s",
    help="Duration of each --benchmark run, in locust notation (e.g. '30s', '1m').",
)
@click.option(
    "-w",
    "--workers",
    default=1,
    help="Locust worker processes for --benchmark (--processes); >1 distributes load across cores on this machine.",
    type=int,
)
@click.option(
    "-o",
    "--output",
    default=None,
    help="Write aggregated --benchmark results to a CSV file.",
    type=click.Path(),
)
@click.version_option(version="0.3.1")
def main(
    ingest: bool,
    locust: bool,
    taurus: bool,
    api_address: str,
    concurrency: int,
    ramp_up: str,
    iterations: int,
    collections: int,
    items_per_collection: int,
    benchmark: bool,
    users: str,
    spawn_rate: int,
    run_time: str,
    workers: int,
    output: str,
):
    """
    Entry point for the stac-api-load-testing CLI tool.

    This tool facilitates data ingestion, Locust load testing, and Taurus performance testing
    against a specified STAC API endpoint.

    Args:
        ingest (bool): If True, ingest sample data into the specified STAC API.
        locust (bool): If True, execute Locust load tests against the specified STAC API.
        taurus (bool): If True, perform Taurus performance testing with custom settings against the specified STAC API.
        concurrency (int): Specifies the number of concurrent users for Taurus testing. Default is 10.
        ramp_up (str): Specifies the ramp-up period for Taurus testing, in Taurus notation (e.g., '1m' for 1 minute). Default is '1m'.
        iterations (int): Specifies the number of iterations each virtual user will execute in Taurus testing. Default is 100.
        collections (int): Number of collections to create for ingest. Default 1.
        items_per_collection (int): Items per collection for ingest. Default 100;
            above 100, duplicates are synthesized with new ids and shifted geometry.
        api_address (str): The base URL of the STAC API to be tested. Comma-separated list allowed for benchmark.
        benchmark (bool): If True, run headless locust runs sweeping --users levels and print a comparison table.
        users (str): Comma-separated concurrency levels for benchmark. Default '10,50,100'.
        spawn_rate (int): Users spawned per second in each benchmark run. Default 10.
        run_time (str): Duration of each benchmark run in locust notation. Default '30s'.
        workers (int): Locust worker processes per benchmark run. Default 1.
        output (str): Optional CSV file path for aggregated benchmark results.
    """
    os.environ["LOCUST_HOST"] = api_address

    if ingest:
        # Load data into the STAC API
        data_loader.load_items(
            stac_api_base_url=api_address,
            num_collections=collections,
            items_per_collection=items_per_collection,
        )
    elif locust:
        # Execute Locust load tests
        locust_file_path = _package_resource("config_files", "locustfile.py")
        subprocess.run(
            [
                _tool_path("locust"),
                "--locustfile",
                locust_file_path,
                "--host",
                api_address,
            ],
            check=True,
        )
    elif taurus:
        # Generate and run a custom Taurus configuration for performance testing
        config_file_path = generate_taurus_config(
            api_address, concurrency, ramp_up, iterations
        )
        if config_file_path:
            try:
                subprocess.run([_tool_path("bzt"), config_file_path], check=True)
            finally:
                if os.path.exists(config_file_path):
                    os.remove(config_file_path)  # Cleanup after running
    elif benchmark:
        concurrency_levels = [int(x) for x in users.split(",")]
        api_addresses = [a.strip() for a in api_address.split(",")]
        run_benchmark(
            api_addresses, concurrency_levels, spawn_rate, run_time, output, workers
        )


if __name__ == "__main__":
    main()
