#!/bin/bash
# Runs automatically the FIRST time the postgres container starts
# (only when the data volume is still empty).
# It creates 3 databases, each with its own user:
#   1) Airflow metadata   2) Celery results   3) ELT data (YouTube)
# All values come from the .env file (passed in by docker-compose env_file).

set -e   # stop on the first error
set -u   # stop if a variable is missing

create_user_and_database() {
  local database=$1
  local username=$2
  local password=$3

  echo "Creating user '$username' and database '$database'"

  psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "postgres" <<EOSQL
CREATE USER $username WITH PASSWORD '$password';
CREATE DATABASE $database OWNER $username;
GRANT ALL PRIVILEGES ON DATABASE $database TO $username;
EOSQL
}

create_user_and_database "$METADATA_DATABASE_NAME" "$METADATA_DATABASE_USERNAME" "$METADATA_DATABASE_PASSWORD"
create_user_and_database "$CELERY_BACKEND_NAME" "$CELERY_BACKEND_USERNAME" "$CELERY_BACKEND_PASSWORD"
create_user_and_database "$ELT_DATABASE_NAME" "$ELT_DATABASE_USERNAME" "$ELT_DATABASE_PASSWORD"

echo "All databases created successfully"