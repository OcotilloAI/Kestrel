#!/bin/bash
set -e

# Configuration
OLLAMA_HOST_URL="${OLLAMA_HOST:-http://ollama:11434}"
MODEL_NAME="${GOOSE_MODEL:-qwen3-coder:30b-a3b-q4_K_M}"
export GOOSE_PROVIDER="${GOOSE_PROVIDER:-ollama}"
export GOOSE_MODEL="${MODEL_NAME}"
export GOOSE_MODE="${GOOSE_MODE:-auto}"

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
    # Trigger pull with correct quoting
    curl -v -d "{\"name\": \"$MODEL_NAME\"}" "$OLLAMA_HOST_URL/api/pull"
    
    echo "Model pull initiated. Waiting for completion..."
    
    # Loop checking 'api/tags' until it appears
    until curl -s "$OLLAMA_HOST_URL/api/tags" | grep -q "$MODEL_NAME"; do
        echo "Still pulling $MODEL_NAME..."
        sleep 10
    done
    echo "Model $MODEL_NAME pulled successfully."
fi

# Configure Goose
mkdir -p $HOME/.config/goose
CONFIG_FILE="$HOME/.config/goose/config.yaml"

if [ ! -f "$CONFIG_FILE" ]; then
    echo "Generating Goose config..."
    cat <<EOF > "$CONFIG_FILE"
GOOSE_PROVIDER: ollama
GOOSE_MODEL: $MODEL_NAME
GOOSE_MODE: auto
extensions:
  developer:
    enabled: true
    name: developer
    type: builtin
  extensionmanager:
    enabled: true
    name: extensionmanager
    type: builtin
EOF
fi

if [ "${GOOSE_TRANSPORT}" = "goosed" ]; then
    export GOOSE_HOST="${GOOSE_HOST:-0.0.0.0}"
    export GOOSE_PORT="${GOOSE_PORT:-3001}"
    export GOOSE_SERVER__SECRET_KEY="${GOOSE_SERVER__SECRET_KEY:-${GOOSE_SERVER_SECRET:-kestrel}}"
    echo "Starting Goose server on ${GOOSE_HOST}:${GOOSE_PORT}..."
    /usr/local/bin/goosed agent &
    echo "Waiting for Goose server..."
    for i in {1..30}; do
        if curl -s -H "X-Secret-Key: ${GOOSE_SERVER__SECRET_KEY}" "http://127.0.0.1:${GOOSE_PORT}/sessions" > /dev/null; then
            echo "Goose server is ready."
            break
        fi
        sleep 1
    done
fi

echo "Starting Kestrel Server..."
# Add src to PYTHONPATH so 'from goose_wrapper import ...' works
export PYTHONPATH=$PYTHONPATH:/app/src
exec uvicorn src.server:app --host 0.0.0.0 --port 8000
