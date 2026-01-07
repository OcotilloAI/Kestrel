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

# 3. Check LLM Backend
if [ -z "$LLM_BASE_URL" ]; then
    echo ""
    echo "Note: LLM_BASE_URL not set. You'll need to configure your LLM backend."
    echo "For local ollama:  export LLM_BASE_URL=http://localhost:11434/v1"
    echo "For OpenAI:        export LLM_BASE_URL=https://api.openai.com/v1"
fi

echo ""
echo "Setup complete. Run ./start.sh to begin."
