#!/bin/sh
# Start Ollama, then serve the pipeline over HTTP for the Worker to call.
# With no arguments this runs the server; with arguments it runs a one-off job
# instead, which is how `docker run ... "<url>"` still works locally.
set -e

ollama serve &

echo "waiting for ollama..."
timeout 60 sh -c 'until ollama list >/dev/null 2>&1; do sleep 1; done'

# Not baked into the image -- a 5GB image is too large for Cloudflare's build
# environment to unpack. ~58s on their network. stdout is dropped because the
# progress bar emits megabytes of carriage returns; errors still reach stderr.
echo "pulling model..."
ollama pull "${OLLAMA_MODEL:-qwen3.5:4b}" >/dev/null

if [ "$#" -eq 0 ]; then
    echo "starting server..."
    exec /app/.venv/bin/python server.py
fi

echo "running one-off job..."
exec /app/.venv/bin/python main.py "$@"
