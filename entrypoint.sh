#!/bin/sh
# Ollama's lifetime is the job's lifetime: start it, run the batch, exit.
set -e

ollama serve &

echo "waiting for ollama..."
timeout 60 sh -c 'until ollama list >/dev/null 2>&1; do sleep 1; done'

echo "running pipeline..."
# The venv's interpreter directly -- `uv run` would re-check the environment
# and can rebuild it, which is pure latency inside an already-built image.
# Args are passed through: <video_url> [city]
exec /app/.venv/bin/python main.py "$@"
