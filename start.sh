#!/bin/bash
# Start Kestrel

# Ensure we are in the project root
cd "$(dirname "$0")"

# Activate virtual environment
if [ -d ".venv" ]; then
    source .venv/bin/activate
else
    echo "Virtual environment not found. Please run setup first."
    exit 1
fi

# Check if Goose is configured
if [ ! -f "$HOME/.config/goose/config.yaml" ]; then
    echo "Goose is not configured. Starting configuration..."
    ./goose-bin configure
fi

# Check if Frontend is built
if [ ! -d "ui/web/dist" ]; then
    echo "Frontend build not found. Building..."
    (cd ui/web && npm install && npm run build)
fi

# Run the web server
echo "Starting Kestrel Web Server..."
uvicorn src.server:app --host 0.0.0.0 --port 8000 --reload
