#!/bin/sh
set -e

echo "Waiting for the database and running migrations..."
until alembic upgrade head; do
  echo "  ...migrations not ready yet, retrying in 2s"
  sleep 2
done
echo "Migrations applied."

exec "$@"
