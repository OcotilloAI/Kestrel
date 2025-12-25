#!/bin/bash
# Setup Kestrel

echo "Setting up Kestrel..."

# 1. Install System Deps (User might need to do this manually if no sudo)
# sudo apt-get install -y python3-venv libportaudio2

# 2. Setup Python Venv
if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv .venv
fi

source .venv/bin/activate

echo "Installing Python dependencies..."
pip install -r requirements.txt

# 3. Check for Goose Binary
if [ ! -f "goose-bin" ]; then
    echo "Goose binary not found. Please ensure 'goose-bin' is present in the root."
    echo "You might need to build it using: docker build -t goose-cli goose/ && docker create --name temp goose-cli && docker cp temp:/usr/local/bin/goose ./goose-bin && docker rm temp"
fi

echo "Setup complete. Run ./start.sh to begin."
