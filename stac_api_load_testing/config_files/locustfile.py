"""stac-api-load-testing locustfile.py config."""

import json
import os
import random
from importlib import resources

from locust import HttpUser, run_single_user, tag, task

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

    def on_start(self):
        """Initialize resources before any task is executed."""
        pass

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
        items_body = items_response.json()
        item_ids = [feature["id"] for feature in items_body["features"]]

        # Request between 1 and min(10, result count) Items, serially
        for item_id in item_ids:
            self.client.get(
                f"/collections/{collection_id}/items/{item_id}", name="get-item"
            )

    def get_collection_bbox(self, collection_id):
        """
        Retrieve the bounding box (bbox) of a specified collection.

        Args:
            collection_id (str): The ID of the collection to fetch the bbox for.

        Returns:
            list: A list representing the bbox of the collection.
        """
        collection_response = self.client.get(
            f"/collections/{collection_id}", name="get-collection"
        )
        return collection_response.json()["extent"]["spatial"]["bbox"][0]

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

        Selects an item ID at random from a predefined list and requests it.
        """
        random_number = random.randint(1, 11)
        item = self.load_file("sentinel-s2-l2a-cogs_0_100.json")
        random_id = item["features"][random_number]["id"]
        self.client.get(
            f"/collections/test-collection/items/{random_id}", name="get-item"
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
            json={"bbox": [16.171875, -79.095963, 179.992188, 19.824820]},
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
        collection_ids = self.get_collection_ids()
        collection_id = random.choice(collection_ids)

        # Randomize GET / POST
        get_post = random.choice(["GET", "POST"])
        if get_post == "GET":
            items_response = self.client.get(
                f"/search?collections={collection_id}", name="get-search-collection"
            )
        elif get_post == "POST":
            items_response = self.client.post(
                "/search",
                json={"collections": [collection_id]},
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
        collection_ids = self.get_collection_ids()
        collection_id = random.choice(collection_ids)
        bbox = self.get_collection_bbox(collection_id)

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
        collection_ids = self.get_collection_ids()
        collection_id = random.choice(collection_ids)
        bbox = self.get_collection_bbox(collection_id)

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
                + f"&sortby={','.join(sortby)}",
                name="get-multisearch-bbox",
            )
        elif get_post == "POST":
            items_response = self.client.post(
                "/search",
                json={
                    "collections": [collection_id],
                    "bbox": search_bbox,
                    "sortby": sortby,
                },
                name="post-multisearch-bbox",
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


# Run tests in debugger if launched directly,
# e.g. "python3 debugging.py", not "locust -f debugging.py"
if __name__ == "__main__":
    run_single_user(WebsiteTestUser)
