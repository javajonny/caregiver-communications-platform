#!/bin/bash
# =============================================
# BACKUP RESTORATION SCRIPT
# =============================================
# Usage: ./scripts/restore_backup.sh <backup_file>
# Example: ./scripts/restore_backup.sh ./backups/backup_20260118_020000.sql.gz.enc
#
# This script decrypts and restores a database backup.
# WARNING: This will OVERWRITE the current database!

set -e

if [ -z "$1" ]; then
    echo "Usage: $0 <backup_file>"
    echo "Example: $0 ./backups/backup_20260118_020000.sql.gz.enc"
    exit 1
fi

BACKUP_FILE="$1"

if [ ! -f "$BACKUP_FILE" ]; then
    echo "ERROR: Backup file not found: $BACKUP_FILE"
    exit 1
fi

# Load environment variables
if [ -f .env ]; then
    export $(grep -v '^#' .env | xargs)
fi

ENCRYPTION_KEY="${BACKUP_ENCRYPTION_KEY:-changeme}"
CONTAINER_NAME="${POSTGRES_CONTAINER:-caregiver_db}"
DB_USER="${POSTGRES_USER:-postgres}"
DB_NAME="${POSTGRES_DB:-caregiver_db}"

echo "========================================"
echo "  DATABASE RESTORE"
echo "========================================"
echo "Backup file: $BACKUP_FILE"
echo "Target database: $DB_NAME"
echo ""
read -p "This will OVERWRITE the current database. Continue? (yes/no): " CONFIRM

if [ "$CONFIRM" != "yes" ]; then
    echo "Restore cancelled."
    exit 0
fi

echo ""
echo "Decrypting and restoring..."

# Decrypt, decompress, and restore
openssl enc -aes-256-cbc -d -pbkdf2 -pass pass:"$ENCRYPTION_KEY" -in "$BACKUP_FILE" | \
    gunzip | \
    docker exec -i "$CONTAINER_NAME" psql -U "$DB_USER" -d "$DB_NAME"

if [ $? -eq 0 ]; then
    echo ""
    echo "✅ Restore completed successfully!"
else
    echo ""
    echo "❌ ERROR: Restore failed!"
    exit 1
fi
