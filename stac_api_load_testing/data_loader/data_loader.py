"""data loader."""

import copy
import json
import random
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


def _shift_coords(coords, dx, dy):
    """Recursively translate a nested GeoJSON coordinate structure."""
    if isinstance(coords[0], (int, float)):
        return [coords[0] + dx, coords[1] + dy] + list(coords[2:])
    return [_shift_coords(c, dx, dy) for c in coords]


def _shift_bbox(bbox, dx, dy):
    """Translate a STAC bbox (4 or 6 elements)."""
    dims = len(bbox) // 2
    lo = [bbox[0] + dx, bbox[1] + dy] + list(bbox[2:dims])
    hi = [bbox[dims] + dx, bbox[dims + 1] + dy] + list(bbox[dims + 2 :])
    return lo + hi


def synthesize_item(feature, suffix, collection):
    """Derive a unique item from a base feature with shifted geometry.

    The offset is bounded by the feature's own extent so the translated
    geometry stays within valid lon/lat - the ring is moved whole rather
    than wrapped per-vertex, which would break polygons.
    """
    item = copy.deepcopy(feature)
    item["id"] = f"{feature['id']}-{suffix}"
    item["collection"] = collection
    bbox = item.get("bbox")
    if bbox:
        dims = len(bbox) // 2
        dx = random.uniform(-180 - bbox[0], 180 - bbox[dims])
        dy = random.uniform(-90 - bbox[1], 90 - bbox[dims + 1])
        item["bbox"] = _shift_bbox(bbox, dx, dy)
    else:
        dx = dy = 0.0
    if item.get("geometry"):
        item["geometry"]["coordinates"] = _shift_coords(
            item["geometry"]["coordinates"], dx, dy
        )
    return item


def load_items(
    stac_api_base_url: str,
    num_collections: int = 1,
    items_per_collection: int = 100,
):
    """Load stac items into the database."""
    feature_collection = load_data("sentinel-s2-l2a-cogs_0_100.json")
    if feature_collection:
        features = feature_collection["features"]
        for c in range(num_collections):
            collection = "test-collection" if c == 0 else f"test-collection-{c + 1}"
            load_collection(
                collection_id=collection, stac_api_base_url=stac_api_base_url
            )

            for i in range(items_per_collection):
                base = features[i % len(features)]
                if i < len(features):
                    feature = copy.deepcopy(base)
                    feature["collection"] = collection
                else:
                    feature = synthesize_item(base, i, collection)
                try:
                    resp = requests.post(
                        f"{stac_api_base_url}/collections/{collection}/items",
                        json=feature,
                    )
                    if resp.status_code in [200, 201]:
                        click.secho(f"Added item: {feature['id']}", fg="green")
                    elif resp.status_code == 409:
                        click.secho(
                            f"Item: {feature['id']} already exists", fg="yellow"
                        )
                    else:
                        click.secho(f"Error {resp.status_code}: {resp.text}", fg="red")
                except requests.ConnectionError:
                    click.secho("Failed to connect to API.", fg="red")
