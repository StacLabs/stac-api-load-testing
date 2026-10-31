"""stac-api-load-testing cli tool."""

import os
import re
import subprocess
from importlib import resources

import click
import yaml

from .data_loader import data_loader


def _package_resource(*parts: str) -> str:
    """Return the filesystem path to a resource bundled in this package."""
    return str(resources.files("stac_api_load_testing").joinpath(*parts))


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
    help="Specify the STAC API URL to test against.",
)
@click.version_option(version="0.3.0")
def main(
    ingest: bool,
    locust: bool,
    taurus: bool,
    api_address: str,
    concurrency: int,
    ramp_up: str,
    iterations: int,
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
        api_address (str): The base URL of the STAC API to be tested.
    """
    os.environ["LOCUST_HOST"] = api_address

    if ingest:
        # Load data into the STAC API
        data_loader.load_items(stac_api_base_url=api_address)
    elif locust:
        # Execute Locust load tests
        locust_file_path = _package_resource("config_files", "locustfile.py")
        subprocess.run(
            ["locust", "--locustfile", locust_file_path, "--host", api_address],
            check=True,
        )
    elif taurus:
        # Generate and run a custom Taurus configuration for performance testing
        config_file_path = generate_taurus_config(
            api_address, concurrency, ramp_up, iterations
        )
        if config_file_path:
            try:
                subprocess.run(["bzt", config_file_path], check=True)
            finally:
                if os.path.exists(config_file_path):
                    os.remove(config_file_path)  # Cleanup after running


if __name__ == "__main__":
    main()
