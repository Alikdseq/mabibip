#!/usr/bin/env bash
set -euo pipefail

# Restore helper (quarterly test): download -> age decrypt -> psql
#
# Env:
#   DATABASE_URL=postgres://...
#   AGE_IDENTITY_FILE=/path/to/key.txt
#   S3_BUCKET=...
#   S3_KEY=promaster/backups/promaster-....sql.age
#   S3_ENDPOINT_URL=... (optional)

enc="/tmp/restore.sql.age"
sql="/tmp/restore.sql"

echo "Downloading s3://${S3_BUCKET}/${S3_KEY}"
if [[ -n "${S3_ENDPOINT_URL:-}" ]]; then
  aws --endpoint-url "${S3_ENDPOINT_URL}" s3 cp "s3://${S3_BUCKET}/${S3_KEY}" "${enc}"
else
  aws s3 cp "s3://${S3_BUCKET}/${S3_KEY}" "${enc}"
fi

echo "Decrypting..."
age -d -i "${AGE_IDENTITY_FILE}" -o "${sql}" "${enc}"
rm -f "${enc}"

echo "Restoring..."
psql "${DATABASE_URL}" -v ON_ERROR_STOP=1 < "${sql}"
rm -f "${sql}"
echo "OK"

