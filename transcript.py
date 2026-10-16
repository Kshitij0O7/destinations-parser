"""Fetch a video's transcript as plain text via the Supadata API."""

import os
import time

from dotenv import load_dotenv
from supadata import Supadata

load_dotenv()


def transcribe(url, lang="en", timeout=300):
    """Fetch the transcript for `url`. Returns plain text, or None on failure.

    Needs SUPADATA_API_KEY in the environment.
    """
    try:
        client = Supadata(api_key=os.environ["SUPADATA_API_KEY"])
        result = client.transcript(url=url, lang=lang, text=True, mode="auto")

        # Short videos return the text directly; longer ones hand back a job id.
        if hasattr(result, "content"):
            return result.content

        deadline = time.time() + timeout
        while time.time() < deadline:
            job = client.transcript.get_job_status(result.job_id)
            if job.status == "completed":
                return job.result.content
            if job.status == "failed":
                print(f"transcript job failed for {url}: {job.error}")
                return None
            time.sleep(2)

        print(f"transcript timed out after {timeout}s for {url}")
        return None

    except Exception as e:
        print(f"transcribe failed for {url}: {e}")
        return None


if __name__ == "__main__":
    import sys

    text = transcribe(sys.argv[1])
    if text:
        print(text)
