#!/usr/bin/env bash
set -euo pipefail

if ! command -v docker >/dev/null 2>&1; then
  echo "docker is required to run this test." >&2
  exit 1
fi

if ! command -v docker compose >/dev/null 2>&1; then
  echo "docker compose is required to run this test." >&2
  exit 1
fi

docker compose up -d builder >/dev/null

builder_id="$(docker compose ps -q builder)"
if [ -z "${builder_id}" ]; then
  echo "builder container is not running." >&2
  exit 1
fi

network_name="$(docker inspect -f '{{range $k,$v := .NetworkSettings.Networks}}{{println $k}}{{end}}' "${builder_id}" | head -n 1)"
if [ -z "${network_name}" ]; then
  echo "failed to resolve builder network." >&2
  exit 1
fi

cleanup() {
  if docker ps -a --format '{{.Names}}' | grep -q '^kestrel-pg$'; then
    docker rm -f kestrel-pg >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT

if ! docker ps --format '{{.Names}}' | grep -q '^kestrel-pg$'; then
  docker run --name kestrel-pg \
    --network "${network_name}" \
    -e POSTGRES_PASSWORD=postgres \
    -d ankane/pgvector >/dev/null
fi

for _ in $(seq 1 30); do
  if docker exec kestrel-pg pg_isready -U postgres >/dev/null 2>&1; then
    break
  fi
  sleep 1
done

docker compose exec builder bash -lc "if [ ! -d /tmp/builder-venv ]; then python3 -m venv /tmp/builder-venv; fi"
docker compose exec builder bash -lc "source /tmp/builder-venv/bin/activate && pip -q install 'psycopg[binary]'"
docker compose exec builder bash -lc "source /tmp/builder-venv/bin/activate && python - <<'PY'
import psycopg

conn = psycopg.connect('dbname=postgres user=postgres password=postgres host=kestrel-pg')
conn.execute('CREATE EXTENSION IF NOT EXISTS vector;')
conn.execute('DROP TABLE IF EXISTS items;')
conn.execute('CREATE TABLE items (id serial primary key, embedding vector(3));')
conn.execute('INSERT INTO items (embedding) VALUES (%s), (%s);', ('[1,2,3]', '[1,1,1]'))
row = conn.execute('SELECT id FROM items ORDER BY embedding <-> %s LIMIT 1;', ('[1,2,2]',)).fetchone()
conn.commit()
conn.close()
if not row:
    raise SystemExit('vector query returned no rows')
print('pgvector OK, closest id:', row[0])
PY"

echo "pgvector scenario test succeeded."
