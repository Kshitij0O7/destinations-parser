"""Turn a travel transcript into structured place records with a local LLM."""

import json

import ollama

MODEL = "qwen3.5:4b"

# Passed to Ollama as `format`, which constrains decoding to this shape. The
# model cannot emit malformed JSON or invent fields.
SCHEMA = {
    "type": "object",
    "properties": {
        "city": {"type": "string"},
        "places": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "fact": {"type": "string"},
                    "advice": {"type": "string"},
                },
                "required": ["name", "fact", "advice"],
            },
        },
    },
    "required": ["city", "places"],
}

PROMPT = """Extract the places mentioned in this travel transcript.

First, identify the city or region the video is about and put it in `city`.

Then list the places in `places`. For each one:
- name: the place, named as the speaker names it
- fact: a fact the transcript states about the place, such as its history or a
  local legend
- advice: advice the transcript gives about visiting, such as going early or
  avoiding crowds

Rules:
- Do not list the city or region itself as a place. Only list places within or
  near it.
- Use only what the transcript actually says.
- If the transcript gives no fact for a place, set fact to "".
- If the transcript gives no advice for a place, set advice to "".
- Never fill a field from your own knowledge of the place. An empty string is
  the correct answer when the transcript is silent.

Transcript:
{text}"""


def extract_places(text, model=MODEL):
    """Extract the subject city and its places from `text`.

    Returns {"city": str, "places": [{name, fact, advice}, ...]}, or None on
    failure.
    """
    try:
        response = ollama.chat(
            model=model,
            messages=[{"role": "user", "content": PROMPT.format(text=text)}],
            format=SCHEMA,
            # This is a reading task, not a reasoning one -- a thinking trace
            # would be discarded output we wait on.
            think=False,
            # Ollama defaults num_ctx to 4096 and truncates silently past it.
            # 8192 covers a long transcript plus the generated JSON.
            options={"num_ctx": 8192, "temperature": 0},
        )
        return json.loads(response["message"]["content"])

    except Exception as e:
        print(f"extract failed: {e}")
        return None


if __name__ == "__main__":
    import sys

    text = open(sys.argv[1]).read() if len(sys.argv) > 1 else sys.stdin.read()
    result = extract_places(text)
    if result:
        print(json.dumps(result, indent=2, ensure_ascii=False))
