#!/bin/bash
set -e

LATEST_BACKUP=$(ls -t /tmp/backups/*.sql.gz 2>/dev/null | head -n 1 || true)

if [ -n "$LATEST_BACKUP" ]; then
    echo "========================================================"
    echo "Backup found: $LATEST_BACKUP"
    echo "Loading data from backup to database $POSTGRES_DB..."
    echo "========================================================"
    gunzip -c "$LATEST_BACKUP" | psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"
else
    echo "========================================================"
    echo "No backups were found in /tmp/backups."
    echo "Initializing with default schema /tmp/schema.sql..."
    echo "========================================================"
    if [ -f /tmp/schema.sql ]; then
        psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -f /tmp/schema.sql
    else
        echo "ERROR: No file /tmp/schema.sql found!"
    fi
fi