#!/bin/bash
# Start Kestrel

# Ensure we are in the project root
cd "$(dirname "$0")"

# Activate virtual environment
if [ -d ".venv" ]; then
    source .venv/bin/activate
else
    echo "Virtual environment not found. Please run ./setup.sh first."
    exit 1
fi

# Check LLM configuration
if [ -z "$LLM_BASE_URL" ]; then
    echo "Warning: LLM_BASE_URL not set. Using default (http://localhost:11434/v1)"
    export LLM_BASE_URL="http://localhost:11434/v1"
fi

if [ -z "$LLM_MODEL" ]; then
    echo "Warning: LLM_MODEL not set. Using default (qwen2.5-coder:7b)"
    export LLM_MODEL="qwen2.5-coder:7b"
fi

# Check if Frontend is built
if [ ! -d "ui/web/dist" ]; then
    echo "Frontend build not found. Building..."
    (cd ui/web && npm install && npm run build)
fi

# Run the web server
echo "Starting Kestrel Web Server..."
echo "LLM: $LLM_MODEL @ $LLM_BASE_URL"
uvicorn src.server:app --host 0.0.0.0 --port 8000 --reload
