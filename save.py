"""Store extracted place records in Cloudflare R2, one object per city."""

import json
import os
import re
from datetime import date

import boto3
from botocore.exceptions import ClientError
from dotenv import load_dotenv

load_dotenv()

BUCKET = "travel-places"


def _client():
    """An S3 client pointed at the R2 bucket."""
    return boto3.client(
        "s3",
        endpoint_url=f"https://{os.environ['ACCOUNT_ID']}.r2.cloudflarestorage.com",
        aws_access_key_id=os.environ["ACCESS_KEY_ID"],
        aws_secret_access_key=os.environ["SECRET_ACCESS_KEY"],
        # R2 has no regions, but boto3 insists on one.
        region_name="auto",
    )


def _key(city):
    """"Kyoto, Japan" -> "kyoto-japan.json"."""
    return re.sub(r"[^a-z0-9]+", "-", city.lower()).strip("-") + ".json"


def _merge(existing, new):
    """Combine two place lists, keyed on name.

    A place seen in a later video can fill a fact or advice the earlier one
    left empty, so coverage improves as more videos are processed.
    """
    by_name = {p["name"].strip().lower(): dict(p) for p in existing}
    for place in new:
        name = place["name"].strip().lower()
        if name in by_name:
            for field in ("fact", "advice"):
                if not by_name[name].get(field) and place.get(field):
                    by_name[name][field] = place[field]
        else:
            by_name[name] = dict(place)
    return list(by_name.values())


def _read(city):
    """Read a city's stored record, or None if it isn't stored yet.

    save() uses this to merge into an existing object. Anything other than a
    missing key -- bad credentials, a network failure, a missing bucket --
    raises, because a broken R2 connection must not look like an empty bucket.
    """
    try:
        obj = _client().get_object(Bucket=BUCKET, Key=_key(city))
        return json.loads(obj["Body"].read())
    except ClientError as e:
        # A missing key means no data yet; a missing bucket is a real problem.
        if e.response["Error"]["Code"] in ("NoSuchKey", "404"):
            return None
        raise


# The public R2 lookup. Not used by this pipeline -- Travel Buddy's `get_places`
# tool does the lookup and triggers this job on a miss -- but kept here because
# that tool needs exactly this call.
#
# def load(city):
#     """Return a city's stored places, or None if we have no data for it."""
#     return _read(city)


def save(places, city):
    """Merge `places` into the city's object in R2.

    Returns the object key on success, or None on failure.
    """
    try:
        existing = _read(city)
        merged = _merge(existing["places"] if existing else [], places)

        body = {
            "city": city,
            "updated_at": date.today().isoformat(),
            "places": merged,
        }
        _client().put_object(
            Bucket=BUCKET,
            Key=_key(city),
            Body=json.dumps(body, ensure_ascii=False, indent=2).encode("utf-8"),
            ContentType="application/json",
        )
        return _key(city)

    except Exception as e:
        print(f"save failed for {city}: {e}")
        return None
