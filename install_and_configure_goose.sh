#!/bin/bash
set -e

# Configuration
GOOSE_PROVIDER="ollama"
GOOSE_MODEL="qwen3-coder:30b-a3b-q4_K_M"
OLLAMA_HOST="http://localhost:11434"

echo "Installing Goose..."
# Use the included download script
if [ -f "goose/download_cli.sh" ]; then
    bash goose/download_cli.sh
else
    echo "Error: goose/download_cli.sh not found."
    exit 1
fi

echo "Configuring Goose..."
CONFIG_DIR="$HOME/.config/goose"
CONFIG_FILE="$CONFIG_DIR/config.yaml"

mkdir -p "$CONFIG_DIR"

if [ -f "$CONFIG_FILE" ]; then
    echo "Warning: $CONFIG_FILE already exists. Backing up to config.yaml.bak"
    cp "$CONFIG_FILE" "$CONFIG_FILE.bak"
fi

cat <<EOF > "$CONFIG_FILE"
GOOSE_PROVIDER: $GOOSE_PROVIDER
GOOSE_MODEL: $GOOSE_MODEL
extensions: {}
EOF

echo "Goose configured to use $GOOSE_PROVIDER with model $GOOSE_MODEL."
echo "Make sure Ollama is running at $OLLAMA_HOST and the model is pulled."
echo "You can pull the model with: ollama pull $GOOSE_MODEL"
