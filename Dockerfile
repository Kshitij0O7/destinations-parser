# Cloudflare Containers run linux/amd64 -- build with --platform linux/amd64
# on an Apple Silicon machine or the image will not start.
FROM python:3.12-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

RUN curl -fsSL https://ollama.com/install.sh | sh

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Dependencies first so a code change doesn't re-resolve them.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project

# Bake the model into the image. Pulling it here means the weekly cold start
# reads 3.6GB from local disk instead of downloading it.
RUN (ollama serve &) \
    && timeout 300 sh -c 'until ollama list >/dev/null 2>&1; do sleep 1; done' \
    && ollama pull qwen3.5:4b

COPY . .

ENTRYPOINT ["/app/entrypoint.sh"]
