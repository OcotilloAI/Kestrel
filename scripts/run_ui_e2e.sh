#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BASE_URL="${BASE_URL:-${1:-http://localhost:8000}}"
export BASE_URL

echo "Installing UI dependencies..."
npm --prefix "$ROOT_DIR/ui/web" install

echo "Ensuring Playwright browsers are installed..."
npm --prefix "$ROOT_DIR/ui/web" run test:e2e:install

echo "Running UI Playwright tests against ${BASE_URL}..."
npm --prefix "$ROOT_DIR/ui/web" run test:e2e
