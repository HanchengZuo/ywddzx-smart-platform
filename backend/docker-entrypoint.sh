#!/bin/sh
set -e

: "${DB_HOST:=db}"
: "${DB_PORT:=5432}"
: "${DB_USER:=postgres}"
: "${DB_NAME:=ywddzx}"

echo "Waiting for PostgreSQL at ${DB_HOST}:${DB_PORT}/${DB_NAME} ..."
until PGPASSWORD="${DB_PASSWORD:-postgres}" pg_isready -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" >/dev/null 2>&1; do
  sleep 1
done

echo "PostgreSQL is ready. Applying database migrations ..."
flask --app app db upgrade

echo "Starting Flask application with gunicorn ..."
exec gunicorn \
  -w "${GUNICORN_WORKERS:-4}" \
  -b 0.0.0.0:5000 \
  --error-logfile - \
  --timeout "${GUNICORN_TIMEOUT:-120}" \
  app:app
