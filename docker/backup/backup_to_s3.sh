#!/usr/bin/env bash
set -euo pipefail

# F10.1.5: pg_dump -> age -> S3
#
# Requires on host/container:
# - pg_dump
# - age (https://age-encryption.org/)
# - aws cli (or s3-compatible endpoint)
#
# Env:
#   DATABASE_URL=postgres://user:pass@host:5432/dbname
#   AGE_RECIPIENT=age1...
#   S3_BUCKET=my-bucket
#   S3_PREFIX=promaster/backups
#   AWS_REGION=...
#   AWS_ACCESS_KEY_ID=...
#   AWS_SECRET_ACCESS_KEY=...
#   S3_ENDPOINT_URL=... (optional for S3-compatible)

ts="$(date -u +%Y%m%dT%H%M%SZ)"
tmp="/tmp/promaster-${ts}.sql"
enc="/tmp/promaster-${ts}.sql.age"

echo "Dumping DB..."
pg_dump "${DATABASE_URL}" --format=plain --no-owner --no-privileges > "${tmp}"

echo "Encrypting..."
age -r "${AGE_RECIPIENT}" -o "${enc}" "${tmp}"
rm -f "${tmp}"

key="${S3_PREFIX:-promaster/backups}/promaster-${ts}.sql.age"
echo "Uploading to s3://${S3_BUCKET}/${key}"

if [[ -n "${S3_ENDPOINT_URL:-}" ]]; then
  aws --endpoint-url "${S3_ENDPOINT_URL}" s3 cp "${enc}" "s3://${S3_BUCKET}/${key}"
else
  aws s3 cp "${enc}" "s3://${S3_BUCKET}/${key}"
fi

rm -f "${enc}"
echo "OK"

