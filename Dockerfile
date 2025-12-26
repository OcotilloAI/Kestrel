FROM python:3.11-slim

# Set unbuffered output for python
ENV PYTHONUNBUFFERED=1

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    tar \
    bzip2 \
    libxcb1 \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements and install python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the local goose directory to access the install script
# We assume the context is the root of the project
COPY goose/download_cli.sh /tmp/install_goose.sh

# Install Goose
# We set GOOSE_BIN_DIR to /usr/local/bin so it's in the PATH
ENV GOOSE_BIN_DIR=/usr/local/bin
ENV CONFIGURE=false
RUN chmod +x /tmp/install_goose.sh && /tmp/install_goose.sh

# Copy application code
COPY src/ src/
COPY static/ static/
COPY scripts/ scripts/

# Create a non-root user (optional, but good practice, though Goose might need write access to some dirs)
# For simplicity in this demo, running as root.

# Expose port
EXPOSE 8000

# Set environment variables for Goose
ENV ANTHROPIC_API_KEY=""
ENV OPENAI_API_KEY=""

# Entrypoint script to handle setup
COPY scripts/container_entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

ENTRYPOINT ["/app/entrypoint.sh"]
