# Build for the host arch when testing locally; add --platform linux/amd64 when
# deploying to Cloudflare Containers.
#
# 3.11 matches the interpreter uv.lock was resolved against, so uv reuses this
# one instead of downloading its own at runtime.
FROM python:3.11-slim

# Never fetch a Python at runtime, and keep the venv at a fixed path so the
# build layer below is the one that actually gets used.
ENV UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/app/.venv

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl ca-certificates zstd \
    && rm -rf /var/lib/apt/lists/*

RUN curl -fsSL https://ollama.com/install.sh | sh

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Dependencies first so a code change doesn't re-resolve them.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project

# Bake the model in. The job is triggered on a cache miss while a user waits,
# so a ~3.5 minute download at startup would sit inside their wait. Placed
# before the code copy so a code change doesn't re-pull it.
# stdout is dropped because the progress bar emits megabytes of carriage
# returns; errors still surface on stderr and the && chain still catches them.
RUN (ollama serve &) \
    && timeout 300 sh -c 'until ollama list >/dev/null 2>&1; do sleep 1; done' \
    && ollama pull qwen3.5:4b >/dev/null

COPY . .

# Install the project itself, so nothing is left for the entrypoint to resolve.
RUN uv sync --frozen

# The model is pulled at startup, not baked in: it keeps the image near 1.4GB
# instead of 5GB, which builds and pushes far faster. The one-off 3.6GB
# download is noise against a multi-hour weekly batch.

ENTRYPOINT ["/app/entrypoint.sh"]
