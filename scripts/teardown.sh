#!/bin/bash
# ============================================================
#  Teardown Script — Remove all AWS resources
#  Cloud Hosting & Networking Project
#  WARNING: This is DESTRUCTIVE and irreversible!
# ============================================================

set -euo pipefail

PROJECT_NAME="${PROJECT_NAME:-cloud-hosting-project}"
AWS_REGION="${AWS_REGION:-us-east-1}"
STACK_NAME="${PROJECT_NAME}-stack"

log()   { echo -e "\033[0;32m[$(date '+%H:%M:%S')] $*\033[0m"; }
warn()  { echo -e "\033[0;33m[$(date '+%H:%M:%S')] ⚠️  $*\033[0m"; }
error() { echo -e "\033[0;31m[$(date '+%H:%M:%S')] ❌  $*\033[0m"; exit 1; }

echo ""
echo "  ⚠️  WARNING: This will DELETE all resources for project: ${PROJECT_NAME}"
echo "  Region: ${AWS_REGION}"
echo "  Stack:  ${STACK_NAME}"
echo ""
read -rp "  Type 'DELETE' to confirm: " CONFIRM
[ "$CONFIRM" != "DELETE" ] && error "Aborted."

# ─── Empty S3 Buckets ─────────────────────────────────────────────────────
log "Emptying S3 buckets for project ${PROJECT_NAME}..."
for bucket in $(aws s3api list-buckets \
    --query "Buckets[?starts_with(Name, '${PROJECT_NAME}')].Name" \
    --output text); do
  warn "Emptying s3://${bucket}..."
  aws s3 rm "s3://${bucket}" --recursive --region "$AWS_REGION" || true
  # Remove versioned objects
  aws s3api list-object-versions \
    --bucket "$bucket" \
    --query '{Objects: Versions[].{Key:Key,VersionId:VersionId}}' \
    --output json 2>/dev/null | \
    aws s3api delete-objects --bucket "$bucket" --delete file:///dev/stdin 2>/dev/null || true
  log "Emptied: $bucket"
done

# ─── Delete CloudFormation Stack ──────────────────────────────────────────
log "Deleting CloudFormation stack: ${STACK_NAME}..."
aws cloudformation delete-stack \
  --stack-name "$STACK_NAME" \
  --region "$AWS_REGION"

log "Waiting for stack deletion..."
aws cloudformation wait stack-delete-complete \
  --stack-name "$STACK_NAME" \
  --region "$AWS_REGION"

log "Stack ${STACK_NAME} deleted successfully."
log "Teardown complete."
