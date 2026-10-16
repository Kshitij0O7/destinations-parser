"""Travel video URL -> structured place records, stored in R2."""

import sys

from save import save
from transcript import transcribe
from translate import extract_places


def process(url, city=None):
    """Fetch `url`'s transcript, extract its places, and store them in R2.

    The city is taken from the extraction unless `city` overrides it. Returns
    the R2 object key, or None if any step fails.
    """
    text = transcribe(url)
    if not text:
        return None

    result = extract_places(text)
    if not result:
        return None

    city = city or result.get("city")
    if not city:
        print(f"no city identified for {url}; pass one as an argument")
        return None

    return save(result["places"], city)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("usage: main.py <video_url> [city]")
        raise SystemExit(1)

    key = process(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)
    if key:
        print(f"saved to R2: {key}")
