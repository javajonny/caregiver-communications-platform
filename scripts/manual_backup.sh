#!/bin/bash
# =============================================
# MANUAL BACKUP SCRIPT
# =============================================
# Usage: ./scripts/manual_backup.sh
#
# Creates an immediate encrypted backup without waiting for the scheduled time.
# Useful for creating backups before major changes.

set -e

# Load environment variables
if [ -f .env ]; then
    export $(grep -v '^#' .env | xargs)
fi

ENCRYPTION_KEY="${BACKUP_ENCRYPTION_KEY:-changeme}"
CONTAINER_NAME="${POSTGRES_CONTAINER:-caregiver_db}"
DB_USER="${POSTGRES_USER:-postgres}"
DB_NAME="${POSTGRES_DB:-caregiver_db}"
BACKUP_DIR="./backups"

# Create backup directory if it doesn't exist
mkdir -p "$BACKUP_DIR"

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="${BACKUP_DIR}/manual_backup_${TIMESTAMP}.sql.gz.enc"

echo "========================================"
echo "  MANUAL DATABASE BACKUP"
echo "========================================"
echo "Database: $DB_NAME"
echo "Output: $BACKUP_FILE"
echo ""

echo "Creating backup..."

docker exec "$CONTAINER_NAME" pg_dump -U "$DB_USER" --clean --if-exists "$DB_NAME" | \
    gzip | \
    openssl enc -aes-256-cbc -salt -pbkdf2 -pass pass:"$ENCRYPTION_KEY" \
    > "$BACKUP_FILE"

if [ $? -eq 0 ]; then
    SIZE=$(ls -lh "$BACKUP_FILE" | awk '{print $5}')
    echo ""
    echo "✅ Backup completed!"
    echo "   File: $BACKUP_FILE"
    echo "   Size: $SIZE"
else
    echo ""
    echo "❌ ERROR: Backup failed!"
    exit 1
fi
