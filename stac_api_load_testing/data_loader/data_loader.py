"""data loader."""

import json
from importlib import resources

import click
import requests


def load_data(filename):
    """Load json data."""
    try:
        file_path = resources.files(__package__).joinpath(f"setup_data/{filename}")
        with file_path.open("r") as file:
            return json.load(file)
    except FileNotFoundError:
        click.secho(f"File {filename} not found in package resources.", fg="red")
        return None


def load_collection(collection_id: str, stac_api_base_url: str):
    """Load stac collection into the database."""
    collection = load_data("collection.json")
    if collection:
        collection["id"] = collection_id
        try:
            resp = requests.post(f"{stac_api_base_url}/collections", json=collection)
            if resp.status_code in [200, 201]:  # Added 201 for created status code
                click.secho(f"Added collection: {collection['id']}", fg="green")
            elif resp.status_code == 409:
                click.secho(
                    f"Collection: {collection['id']} already exists", fg="yellow"
                )
            else:
                click.secho(f"Error {resp.status_code}: {resp.text}", fg="red")
        except requests.ConnectionError:
            click.secho("Failed to connect to API.", fg="red")


def load_items(stac_api_base_url: str):
    """Load stac items into the database."""
    feature_collection = load_data("sentinel-s2-l2a-cogs_0_100.json")
    if feature_collection:
        collection = "test-collection"
        load_collection(collection_id=collection, stac_api_base_url=stac_api_base_url)

        for feature in feature_collection["features"]:
            try:
                feature["collection"] = collection
                resp = requests.post(
                    f"{stac_api_base_url}/collections/{collection}/items", json=feature
                )
                if resp.status_code in [200, 201]:  # Added 201 for created status code
                    click.secho(f"Added item: {feature['id']}", fg="green")
                elif resp.status_code == 409:
                    click.secho(f"Item: {feature['id']} already exists", fg="yellow")
                else:
                    click.secho(f"Error {resp.status_code}: {resp.text}", fg="red")
            except requests.ConnectionError:
                click.secho("Failed to connect to API.", fg="red")
