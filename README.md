# travel-transcript

Turns travel videos into structured place data. Give it a YouTube URL and it
returns the places the creator actually talks about, with the facts and advice
they gave about each one:

```json
{
  "city": "Kyoto",
  "updated_at": "2026-10-16",
  "places": [
    {
      "name": "Arashiyama bamboo grove",
      "fact": "The most popular bamboo forest, accessible by direct train from Kyoto station to Saga-Arashiyama.",
      "advice": "Arrive early to beat dense crowds that gather by mid-morning."
    },
    {
      "name": "Yasaka Pagoda",
      "fact": "",
      "advice": ""
    }
  ]
}
```

Travel YouTube holds recommendations that aren't well indexed anywhere else —
the stall with no sign, the viewpoint five minutes past where everyone stops.
This extracts that into something queryable.

## Pipeline

```
YouTube URL
   -> transcript.py   fetch the transcript        (Supadata API)
   -> translate.py    extract places as JSON      (local LLM via Ollama)
   -> save.py         merge into city record      (Cloudflare R2)
```

`main.py` chains the three for one video. `batch.py` walks a seed list of
cities and is the entry point for the scheduled job.

## Setup

Requires [uv](https://docs.astral.sh/uv/) and [Ollama](https://ollama.com).

```bash
uv sync
ollama pull qwen3.5:4b
cp .env.example .env   # then fill in your keys
```

## Usage

One video, printed as JSON:

```bash
uv run main.py "https://www.youtube.com/watch?v=aSksCBrDKO8"
```

The city is inferred from the transcript; pass one to override it:

```bash
uv run main.py "https://www.youtube.com/watch?v=..." "Kyoto"
```

Each stage runs standalone, which makes the pipeline easy to debug:

```bash
uv run transcript.py "<url>" > kyoto.txt   # transcript only
uv run translate.py kyoto.txt              # extraction only
```

Batch over `cities.json`, skipping cities already in R2:

```bash
uv run batch.py              # pre-warm new cities
uv run batch.py --refresh    # reprocess stored cities too
```

## Deployment

The container runs Ollama and the batch as a single short-lived job: the
entrypoint starts `ollama serve`, runs `batch.py`, and exits. Nothing persists
between runs, so a weekly schedule costs only the hours it actually runs.

```bash
docker build --platform linux/amd64 -t travel-places .
docker run --rm --env-file .env travel-places
```

`--platform linux/amd64` matters — an image built natively on Apple Silicon
won't start on an amd64 host.

Then schedule it. On a VM:

```bash
0 3 * * 0  docker run --rm --env-file /opt/travel/.env travel-places
```

The model is baked into the image at build time, so the cold start reads it
from local disk rather than downloading 3.6GB on every run.

## Design notes

**Transcripts come from an API, not `yt-dlp` + Whisper.** The first version
downloaded audio and transcribed locally with `mlx-whisper`. It worked well on
a laptop and is a liability in production: YouTube blocks datacenter IPs, and
`yt-dlp` breaks whenever YouTube ships a change. Accuracy also went the
opposite way from what was expected — creator-uploaded captions beat local ASR
on exactly the proper nouns that matter. Whisper produced `Kiyomistera` and
`Fushiminari`; the captions had `Kiyomizu-dera` and `Fushimi Inari`.

**Extraction runs on a local model.** The task is mechanical reading, not
reasoning, so a 4B model is enough. Running it locally means re-running the
whole corpus after a prompt change costs nothing, which matters when the
prompt is where all the quality lives.

**The output schema is enforced, not requested.** Ollama's `format` parameter
constrains decoding to a JSON schema, so malformed output is impossible rather
than merely unlikely. Asking a small model politely for JSON fails a few
percent of the time; this doesn't.

**Empty fields are a feature.** The prompt forbids filling `fact` or `advice`
from the model's own knowledge — if the transcript is silent, the field stays
empty. Famous places are heavily represented in pretraining data, so a model
asked for "a fact about Kiyomizu-dera" will happily supply one the creator
never said. Empty means "not mentioned", which keeps the data trustworthy.

**Thinking is disabled.** `qwen3.5:4b` is a reasoning model, and its thinking
trace was most of the wall-clock time for output that gets discarded.

**Writes merge instead of overwriting.** Several videos cover one city, so
`save()` reads the existing record and merges on place name. A later video can
fill a `fact` an earlier one left empty, so coverage improves as videos are
added. Re-running a video is a no-op.

## Known limitations

- **Deduplication is exact-match on name.** `Kiyomizu-dera` and
  `Kiyomizu Dera` from two creators become two entries. Fuzzy or
  embedding-based matching is the fix.
- **Source errors pass straight through.** If a creator's captions say
  `Great Eastern Temple` instead of Tōdai-ji, that's what gets stored.
  Grounding against a places API would resolve these.
- **Recall decays over long transcripts.** Places mentioned in the final
  minutes are sometimes missed. Chunking the transcript into overlapping
  windows would address it.
- **No provenance.** Once merged, nothing records which video contributed
  which fact.
