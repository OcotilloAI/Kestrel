# Stage 1: Build Frontend
FROM node:20-slim AS frontend-builder
WORKDIR /app/ui/web
COPY ui/web/package*.json ./
RUN npm install
COPY ui/web/ ./
RUN npm run build

# Stage 2: Final Image
FROM python:3.11-slim

# Set unbuffered output for python
ENV PYTHONUNBUFFERED=1

# Install system dependencies (including Node.js for Goose extensions)
RUN apt-get update && apt-get install -y \
    curl \
    tar \
    bzip2 \
    libxcb1 \
    git \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements and install python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Goose
COPY goose/download_cli.sh /tmp/install_goose.sh
ENV GOOSE_BIN_DIR=/usr/local/bin
ENV CONFIGURE=false
RUN chmod +x /tmp/install_goose.sh && /tmp/install_goose.sh

# Copy built frontend from Stage 1
COPY --from=frontend-builder /app/ui/web/dist /app/ui/web/dist

# Copy application code
COPY src/ src/
COPY scripts/ scripts/
COPY static/ static/

# Expose port
EXPOSE 8000

# Entrypoint script
COPY scripts/container_entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

ENTRYPOINT ["/app/entrypoint.sh"]
