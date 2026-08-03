#!/usr/bin/env bash

# Load environment variables from .env (if present)
if [ -f "../.env" ]; then
  export $(grep -v '^#' ../.env | xargs)
fi

# Ensure DATABASE_URL is set
if [ -z "$DATABASE_URL" ]; then
  echo "Error: DATABASE_URL is not set. Please configure it in .env"
  exit 1
fi

# Directory containing migration SQL files
MIGRATIONS_DIR="../supabase/migrations"

# Apply each migration in order
for file in $(ls $MIGRATIONS_DIR/*.sql | sort); do
  echo "Applying migration $file..."
  psql "$DATABASE_URL" -f "$file"
  if [ $? -ne 0 ]; then
    echo "Migration $file failed. Stopping."
    exit 1
  fi
done

echo "All migrations applied successfully."
