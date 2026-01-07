#!/usr/bin/env bash
set -euo pipefail

if ! command -v docker >/dev/null 2>&1; then
  echo "docker is required to run the builder container." >&2
  exit 1
fi

if ! command -v docker compose >/dev/null 2>&1; then
  echo "docker compose is required to run the builder container." >&2
  exit 1
fi

if [ "$#" -lt 1 ]; then
  echo "Usage: scripts/run_in_builder.sh <command>" >&2
  exit 1
fi

docker compose up -d builder >/dev/null
docker compose exec builder bash -lc "$*"
