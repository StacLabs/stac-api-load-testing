"""stac-api-load-testing locustfile.py config."""

import json
import os
import random
import time
from datetime import datetime, timedelta
from importlib import resources
from urllib.parse import urlparse

import requests
from gevent.lock import Semaphore
from locust import HttpUser, events, run_single_user, tag, task
from locust.runners import MasterRunner

SEARCH_LIMIT = 10

test_item = {
    "stac_version": "1.0.0",
    "stac_extensions": [],
    "type": "Feature",
    "id": "20201211_223832_CS2",
    "bbox": [
        172.91173669923782,
        1.3438851951615003,
        172.95469614953714,
        1.3690476620161975,
    ],
    "geometry": {
        "type": "Polygon",
        "coordinates": [
            [
                [172.91173669923782, 1.3438851951615003],
                [172.95469614953714, 1.3438851951615003],
                [172.95469614953714, 1.3690476620161975],
                [172.91173669923782, 1.3690476620161975],
                [172.91173669923782, 1.3438851951615003],
            ]
        ],
    },
    "properties": {"datetime": "2020-12-11T22:38:32.125000Z"},
    "collection": "simple-collection",
    "links": [
        {
            "rel": "collection",
            "href": "./collection.json",
            "type": "application/json",
            "title": "Simple Example Collection",
        },
        {
            "rel": "root",
            "href": "./collection.json",
            "type": "application/json",
            "title": "Simple Example Collection",
        },
        {
            "rel": "parent",
            "href": "./collection.json",
            "type": "application/json",
            "title": "Simple Example Collection",
        },
    ],
    "assets": {
        "visual": {
            "href": "https://storage.googleapis.com/open-cogs/stac-examples/20201211_223832_CS2.tif",
            "type": "image/tiff; application=geotiff; profile=cloud-optimized",
            "title": "3-Band Visual",
            "roles": ["visual"],
        },
        "thumbnail": {
            "href": "https://storage.googleapis.com/open-cogs/stac-examples/20201211_223832_CS2.jpg",
            "title": "Thumbnail",
            "type": "image/jpeg",
            "roles": ["thumbnail"],
        },
    },
}


def _fixture_item_ids() -> list:
    """Return the ids of the bundled sample items."""
    fixture_path = resources.files("stac_api_load_testing.data_loader").joinpath(
        "setup_data/sentinel-s2-l2a-cogs_0_100.json"
    )
    with fixture_path.open() as file:
        return [feature["id"] for feature in json.load(file)["features"]]


def _synthesize_item_ids(count: int) -> list:
    """Reproduce the ingest id scheme: bundled ids, then <base_id>-<index>."""
    base_ids = _fixture_item_ids()
    return [
        base_ids[i] if i < len(base_ids) else f"{base_ids[i % len(base_ids)]}-{i}"
        for i in range(count)
    ]


def _discover_catalog(host):
    """
    Fetch collection metadata once per worker and derive item ids locally.

    Item ids follow the ingest scheme (bundled ids, then <base_id>-<index>)
    so no items pages are fetched at all — discovery costs one /collections
    request. Item counts come from the STAC_COLLECTION_COUNTS env var the
    benchmark CLI sets from its metadata query; without it only the 100
    bundled ids are used. Retries briefly on failure and degrades to an
    empty catalog so a struggling backend does not respawn-loop users.
    """
    counts = json.loads(os.environ.get("STAC_COLLECTION_COUNTS") or "{}")
    for attempt in range(3):
        try:
            collections = requests.get(f"{host}/collections", timeout=30).json()[
                "collections"
            ]
            item_ids, bboxes, temporal = {}, {}, {}
            for collection in collections:
                collection_id = collection["id"]
                item_ids[collection_id] = _synthesize_item_ids(
                    counts.get(collection_id, 100)
                )
                bboxes[collection_id] = collection["extent"]["spatial"]["bbox"][0]
                temporal[collection_id] = collection["extent"]["temporal"]["interval"][
                    0
                ]
            return {
                "ids": [c["id"] for c in collections],
                "item_ids": item_ids,
                "bboxes": bboxes,
                "temporal": temporal,
            }
        except Exception:
            if attempt < 2:
                time.sleep(1)
    return {"ids": [], "item_ids": {}, "bboxes": {}, "temporal": {}}


class WebsiteTestUser(HttpUser):
    """
    Simulates a user performing various API requests to test a web application's performance and behavior.

    This user model includes tasks that cover fetching collections, retrieving specific items within those collections,
    and conducting spatial searches among other API interactions to simulate real user behavior.

    Attributes:
        host (str): The base URL for the API, defaulted to 'http://localhost:8083' but can be overridden.
        default_load_multiplier (int): A default multiplier to adjust the load each task generates.
    """

    host = os.getenv("LOCUST_HOST", "http://localhost:8083")
    default_load_multiplier = 1
    _catalog_cache = None
    _catalog_lock = Semaphore()

    def on_start(self):
        """Attach the worker's cached catalog, discovering it lazily if needed."""
        with WebsiteTestUser._catalog_lock:
            if WebsiteTestUser._catalog_cache is None:
                WebsiteTestUser._catalog_cache = _discover_catalog(self.host)
        cache = WebsiteTestUser._catalog_cache
        self.collection_ids = cache["ids"]
        self.item_ids = cache["item_ids"]
        self.bboxes = cache["bboxes"]
        self.temporal_intervals = cache["temporal"]

    def _random_collection_id(self):
        """Pick a random cached collection id, or None if discovery failed."""
        return random.choice(self.collection_ids) if self.collection_ids else None

    def on_stop(self):
        """Clean up resources after tasks are completed."""
        pass

    def load_file(self, file) -> dict:
        """
        Load JSON data from a specified file.

        Args:
            file (str): The path to the file to be loaded.

        Returns:
            dict: A dictionary containing the loaded JSON data.
        """
        try:
            file_path = resources.files("stac_api_load_testing.data_loader").joinpath(
                f"setup_data/{file}"
            )
            with file_path.open("r") as file:
                return json.load(file)
        except FileNotFoundError as e:
            print(f"File not found: {e}")
            return {}

    def get_collection_ids(self):
        """
        Fetch and return all available collection IDs from the API.

        Returns:
            list: A list of collection IDs.
        """
        collections_response = self.client.get("/collections", name="get-collections")
        collections_body = collections_response.json()
        collection_ids = [
            collection["id"] for collection in collections_body["collections"]
        ]
        return collection_ids

    def parse_request_items(self, collection_id, items_response):
        """
        Parse items from a response and makes requests for each item.

        Args:
            collection_id (str): The ID of the collection the items belong to.
            items_response: The response object containing the items data.
        """
        try:
            items_body = items_response.json()
        except ValueError:
            # Empty/invalid body under load — skip fan-out rather than crash
            return
        item_ids = [feature["id"] for feature in items_body["features"]]

        # Request up to 2 items from the search result, serially
        for item_id in item_ids[:2]:
            self.client.get(
                f"/collections/{collection_id}/items/{item_id}", name="get-item"
            )

    def random_datetime_interval(self, collection_id):
        """
        Generate a random datetime interval inside a collection's temporal extent.

        Args:
            collection_id (str): The ID of the collection whose extent bounds the range.

        Returns:
            str: A STAC datetime interval in 'start/end' RFC3339 format. Open-ended
            intervals ('../end', 'start/..') are returned if the extent is open.
        """
        start, end = self.temporal_intervals[collection_id]
        if start is None or end is None:
            return f"{start or '..'}/{end or '..'}"
        t0 = datetime.fromisoformat(start.replace("Z", "+00:00"))
        t1 = datetime.fromisoformat(end.replace("Z", "+00:00"))
        span = (t1 - t0).total_seconds()
        a, b = sorted(random.uniform(0, span) for _ in range(2))
        d0 = t0 + timedelta(seconds=a)
        d1 = t0 + timedelta(seconds=b)
        return (
            f"{d0.isoformat().replace('+00:00', 'Z')}"
            f"/{d1.isoformat().replace('+00:00', 'Z')}"
        )

    def get_sortby(self, get_post):
        """
        Randomizes the sort order among available fields for item sorting.

        Args:
            get_post (str): Indicates the method of the request ('GET' or 'POST').

        Returns:
            list: A list of strings or dictionaries representing the sort order for items.
        """
        # TODO retrieve all sortable fields common to items in collection
        fields = ["id", "properties.datetime", "properties.eo:cloud_cover"]
        directions = [random.choice(["+", "-"]) for _ in fields]
        sym2text = {"+": "asc", "-": "desc"}

        if get_post == "GET":
            return [
                f"{direction}{field}" for direction, field in zip(directions, fields)
            ]
        elif get_post == "POST":
            return [
                {"field": field, "direction": sym2text[direction]}
                for field, direction in zip(fields, directions)
            ]

    @tag("root_catalog")
    @task(default_load_multiplier)
    def get_root_catalog(self):
        """Fetch the landing page/root catalog of the API."""
        self.client.get("/", name="get-landing")

    @tag("all_collections")
    @task(default_load_multiplier)
    def get_all_collections(self):
        """Fetch all collections available in the API."""
        self.client.get("/collections", name="get-collections")

    @tag("get_collection")
    @task(default_load_multiplier)
    def get_collection(self):
        """Fetch a specific collection by ID."""
        self.client.get("/collections/test-collection", name="get-collection")

    @tag("item_collection")
    @task(default_load_multiplier)
    def get_item_collection(self):
        """Fetch items within a specific collection."""
        self.client.get("/collections/test-collection/items", name="get-items")

    @tag("get_item")
    @task(default_load_multiplier)
    def get_item(self):
        """
        Fetch a specific item by ID within a collection.

        Selects a random item from a random collection, using the ids
        cached in on_start.
        """
        collection_id = self._random_collection_id()
        if collection_id is None:
            return
        ids = self.item_ids.get(collection_id)
        if not ids:
            return
        random_id = random.choice(ids)
        self.client.get(
            f"/collections/{collection_id}/items/{random_id}", name="get-item"
        )

    @tag("get_bbox")
    @task(0)
    def get_bbox_search(self):
        """
        Perform a GET request to search items within a specified bounding box.

        This method simulates a search query using a predefined bounding box to fetch items
        that fall within the specified geographical area.
        """
        self.client.get(
            "/search?bbox=-16.171875,-79.095963,179.992188,19.824820",
            name="get-search-bbox",
        )

    @tag("post_bbox")
    @task(default_load_multiplier)
    def post_bbox_search(self):
        """
        Perform a POST request to search items within a specified bounding box.

        This method sends a JSON payload with a bounding box to search for items within
        that geographical area using a POST request.
        """
        self.client.post(
            "/search",
            json={
                "bbox": [16.171875, -79.095963, 179.992188, 19.824820],
                "limit": SEARCH_LIMIT,
            },
            name="post-search-bbox",
        )

    @tag("point_intersects")
    @task(default_load_multiplier)
    def post_intersects_search(self):
        """
        Search for items that intersect with a specified point.

        Args:
            None

        This method simulates a user performing a spatial search to find items that intersect
        with a specific point, using a POST request with a JSON payload describing the point.
        """
        self.client.post(
            "/search",
            json={
                "collections": ["test-collection"],
                "intersects": {"type": "Point", "coordinates": [150.04, -33.14]},
                "limit": SEARCH_LIMIT,
            },
            name="post-search-intersects",
        )

    @tag("basic_nonspatial")
    @task(default_load_multiplier)
    def basic_nonspatial_search(self):
        """
        Perform a basic non-spatial search for a collection by ID.

        This method randomly chooses between a GET or POST request to search for items
        within a specific collection identified by its ID. The choice between GET or POST
        and the handling of the response showcases flexibility in API interaction.
        """
        collection_id = self._random_collection_id()
        if collection_id is None:
            return

        # Randomize GET / POST
        get_post = random.choice(["GET", "POST"])
        if get_post == "GET":
            items_response = self.client.get(
                f"/search?collections={collection_id}&limit={SEARCH_LIMIT}",
                name="get-search-collection",
            )
        elif get_post == "POST":
            items_response = self.client.post(
                "/search",
                json={"collections": [collection_id], "limit": SEARCH_LIMIT},
                name="post-search-collection",
            )

        self.parse_request_items(collection_id, items_response)

    @tag("intersects_sortby")
    @task(default_load_multiplier)
    def paged_poi_search(self):
        """
        Perform a paged point-of-interest search within a collection's bounding box.

        This method simulates a more complex user interaction by selecting a random point
        within the bounding box of a randomly chosen collection. It then performs a search
        to find items that intersect with this point, also applying a randomized sort order.
        """
        # Get the bbox of a random collection
        collection_id = self._random_collection_id()
        if collection_id is None:
            return
        bbox = self.bboxes[collection_id]

        # Create random point inside bbox for /search intersects
        x = random.random() * (bbox[2] - bbox[0]) + bbox[0]
        y = random.random() * (bbox[3] - bbox[1]) + bbox[1]

        # Search (only POST possible for "intersects")
        sortby = self.get_sortby("POST")
        items_response = self.client.post(
            "/search",
            json={
                "collections": [collection_id],
                "intersects": {"type": "Point", "coordinates": [x, y]},
                "sortby": sortby,
                "limit": SEARCH_LIMIT,
            },
            name="post-multisearch-intersects",
        )

        self.parse_request_items(collection_id, items_response)

    @tag("user_bbox")
    @task(default_load_multiplier)
    def paged_bbox_search(self):
        """
        Conduct a paged search within a user-defined bounding box.

        This method demonstrates a scenario where a user specifies an Area of Interest (AOI)
        as a bounding box within the bounding box of a randomly selected collection. It then
        performs a search (either GET or POST) to find items within this user-defined AOI,
        applying a randomized sort order.
        """
        # Get the bbox of a random collection
        collection_id = self._random_collection_id()
        if collection_id is None:
            return
        bbox = self.bboxes[collection_id]

        # Create a random search bbox inside collection bbox
        x = [random.random() * (bbox[2] - bbox[0]) + bbox[0] for _ in range(2)]
        y = [random.random() * (bbox[3] - bbox[1]) + bbox[1] for _ in range(2)]
        search_bbox = [min(x), min(y), max(x), max(y)]

        # Search, randomly using GET or POST
        get_post = random.choice(["GET", "POST"])
        sortby = self.get_sortby(get_post)
        if get_post == "GET":
            search_bbox_str = ",".join([str(x) for x in search_bbox])
            items_response = self.client.get(
                f"/search?collections={collection_id}&bbox={search_bbox_str}"
                + f"&sortby={','.join(sortby)}&limit={SEARCH_LIMIT}",
                name="get-multisearch-bbox",
            )
        elif get_post == "POST":
            items_response = self.client.post(
                "/search",
                json={
                    "collections": [collection_id],
                    "bbox": search_bbox,
                    "sortby": sortby,
                    "limit": SEARCH_LIMIT,
                },
                name="post-multisearch-bbox",
            )

        self.parse_request_items(collection_id, items_response)

    @tag("datetime_search")
    @task(default_load_multiplier)
    def datetime_search(self):
        """
        Search for items within a random datetime range of a random collection.

        Picks a random sub-interval inside the collection's cached temporal extent
        and issues a GET or POST /search with the datetime parameter.
        """
        collection_id = self._random_collection_id()
        if collection_id is None:
            return
        datetime_interval = self.random_datetime_interval(collection_id)

        get_post = random.choice(["GET", "POST"])
        if get_post == "GET":
            items_response = self.client.get(
                f"/search?collections={collection_id}&datetime={datetime_interval}"
                + f"&limit={SEARCH_LIMIT}",
                name="get-search-datetime",
            )
        elif get_post == "POST":
            items_response = self.client.post(
                "/search",
                json={
                    "collections": [collection_id],
                    "datetime": datetime_interval,
                    "limit": SEARCH_LIMIT,
                },
                name="post-search-datetime",
            )

        self.parse_request_items(collection_id, items_response)

    @tag("filtered_items")
    @task(default_load_multiplier)
    def filtered_items(self):
        """
        Fetch an item collection filtered by a random datetime interval.

        Exercises the /collections/{id}/items endpoint with real query
        parameters rather than an unfiltered page.
        """
        collection_id = self._random_collection_id()
        if collection_id is None:
            return
        datetime_interval = self.random_datetime_interval(collection_id)
        self.client.get(
            f"/collections/{collection_id}/items"
            + f"?datetime={datetime_interval}&limit={SEARCH_LIMIT}",
            name="get-items-datetime",
        )

    @tag("paged_search")
    @task(default_load_multiplier)
    def paged_search(self):
        """
        Fetch a search page then follow its `next` link once.

        Covers actual pagination behavior; the next link's origin is
        rewritten to this user's host because some implementations emit
        their configured root URL instead of the request host.
        """
        collection_id = self._random_collection_id()
        if collection_id is None:
            return
        response = self.client.get(
            f"/search?collections={collection_id}&limit={SEARCH_LIMIT}",
            name="get-search-paged",
        )
        try:
            links = response.json().get("links", [])
        except ValueError:
            return
        next_href = next(
            (
                link["href"]
                for link in links
                if link.get("rel") == "next" and link.get("href")
            ),
            None,
        )
        if next_href is None:
            return
        parsed = urlparse(next_href)
        path = parsed.path + (f"?{parsed.query}" if parsed.query else "")
        self.client.get(path, name="get-search-next")

    @tag("ids_search")
    @task(default_load_multiplier)
    def ids_search(self):
        """
        Search for up to 3 cached item ids within a random collection.

        Exercises the ids parameter of POST /search using real ids
        discovered at test start.
        """
        collection_id = self._random_collection_id()
        if collection_id is None:
            return
        ids = self.item_ids.get(collection_id)
        if not ids:
            return
        picked = random.sample(ids, min(3, len(ids)))
        self.client.post(
            "/search",
            json={
                "collections": [collection_id],
                "ids": picked,
                "limit": SEARCH_LIMIT,
            },
            name="post-search-ids",
        )

    @tag("cql2_filter")
    @task(default_load_multiplier)
    def cql2_filter(self):
        """
        Search with a simple CQL2-JSON property filter.

        Picks a random comparison on a well-known item property; all
        tested backends implement the filter extension, so this is real
        filter work rather than an ignored parameter.
        """
        collection_id = self._random_collection_id()
        if collection_id is None:
            return
        prop, value = random.choice(
            [
                ("properties.platform", "sentinel-2b"),
                ("properties.constellation", "sentinel-2"),
                ("properties.sentinel:grid_square", "CV"),
            ]
        )
        items_response = self.client.post(
            "/search",
            json={
                "collections": [collection_id],
                "filter-lang": "cql2-json",
                "filter": {"op": "=", "args": [{"property": prop}, value]},
                "limit": SEARCH_LIMIT,
            },
            name="post-search-cql2",
        )

        self.parse_request_items(collection_id, items_response)

    @tag("create_item")
    @task(0)
    def create_item(self):
        """
        Create a new item in a specified collection.

        This method simulates the creation of a new item in a test collection by posting
        a JSON payload representing the item. The item ID is generated randomly to ensure
        uniqueness.
        """
        random_number = random.randint(1, 100000)
        item = test_item
        item["id"] = f"test-item-{random_number}"
        item["collection"] = "test-collection"
        self.client.post(
            "/collections/test-collection/items", json=item, name="post-create-item"
        )


@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    """Populate the per-process catalog cache before users spawn.

    Runs on each worker process (skipped on the master, which hosts no
    users), so discovery completes before measured traffic begins.
    """
    if isinstance(environment.runner, MasterRunner):
        return
    if environment.host and WebsiteTestUser._catalog_cache is None:
        WebsiteTestUser._catalog_cache = _discover_catalog(environment.host)


# Run tests in debugger if launched directly,
# e.g. "python3 debugging.py", not "locust -f debugging.py"
if __name__ == "__main__":
    run_single_user(WebsiteTestUser)
