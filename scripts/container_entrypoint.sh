#!/bin/bash
set -e

# Configuration
MODEL_NAME="${LLM_MODEL:-qwen3-coder:30b-a3b-q4_K_M}"
export LLM_PROVIDER="${LLM_PROVIDER:-ollama}"
export LLM_MODEL="${MODEL_NAME}"

if [ "$LLM_PROVIDER" = "ollama" ]; then
    OLLAMA_HOST_URL="${OLLAMA_HOST:-http://ollama:11434}"
    echo "Waiting for Ollama at $OLLAMA_HOST_URL..."

    # Wait for Ollama to be ready
    until curl -s "$OLLAMA_HOST_URL/api/tags" > /dev/null; do
        echo "Ollama not ready, retrying in 2s..."
        sleep 2
    done

    echo "Ollama is ready!"

    # Check if model exists, if not pull it
    if curl -s "$OLLAMA_HOST_URL/api/tags" | grep -q "$MODEL_NAME"; then
        echo "Model $MODEL_NAME already exists."
    else
        echo "Pulling model $MODEL_NAME (this may take a while)..."
        curl -v -d "{\"name\": \"$MODEL_NAME\"}" "$OLLAMA_HOST_URL/api/pull"

        echo "Model pull initiated. Waiting for completion..."

        until curl -s "$OLLAMA_HOST_URL/api/tags" | grep -q "$MODEL_NAME"; do
            echo "Still pulling $MODEL_NAME..."
            sleep 10
        done
        echo "Model $MODEL_NAME pulled successfully."
    fi
fi

echo "Starting Kestrel Server..."
# Add src to PYTHONPATH
export PYTHONPATH=$PYTHONPATH:/app/src
exec uvicorn src.server:app --host 0.0.0.0 --port 8000
