#!/bin/bash

# Enforce environment variables inside the script since cron runs in a stripped environment
export PGPASSWORD="routor_password"

BACKUP_DIR="/backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/backup_$TIMESTAMP.sql.gz"

echo "=== DATABASE BACKUP INITIALIZED ==="

# Execute pg_dumpall via network host and compress on the fly using gzip
pg_dumpall -h routor_db -U routor_user | gzip > "$BACKUP_FILE"

echo "=== BACKUP COMPLETED SUCCESSFULLY: $BACKUP_FILE ==="

# Data retention policy: Remove backups older than 7 days to prevent disk space exhaustion
find "$BACKUP_DIR" -type f -mtime +7 -name "*.sql.gz" -delete