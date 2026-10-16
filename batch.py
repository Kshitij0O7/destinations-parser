"""Walk a seed list of cities through the pipeline. Entry point for the cron job."""

import json
import sys

from main import process
from save import load

SEEDS = "cities.json"


def run(seeds_path=SEEDS, refresh=False):
    """Process every seeded city that has no data in R2 yet.

    `refresh` reprocesses cities that are already stored; results merge into
    the existing object rather than replacing it.
    """
    with open(seeds_path) as f:
        seeds = json.load(f)

    for city, urls in seeds.items():
        if not urls:
            print(f"{city}: no seed URLs, skipping")
            continue
        if not refresh and load(city):
            print(f"{city}: already stored, skipping")
            continue

        for url in urls:
            key = process(url, city)
            print(f"{city}: {'saved ' + key if key else 'FAILED'}  <- {url}")


if __name__ == "__main__":
    run(
        sys.argv[1] if len(sys.argv) > 1 else SEEDS,
        refresh="--refresh" in sys.argv,
    )
