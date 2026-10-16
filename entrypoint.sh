#!/bin/sh
# Ollama's lifetime is the job's lifetime: start it, run the batch, exit.
set -e

ollama serve &

echo "waiting for ollama..."
timeout 60 sh -c 'until ollama list >/dev/null 2>&1; do sleep 1; done'

echo "running batch..."
exec uv run --frozen batch.py "$@"
