#!/bin/bash
# ============================================================
#  Master Deploy Script
#  Cloud Hosting & Networking Project — AWS
#  Deploys the full stack via CloudFormation
# ============================================================

set -euo pipefail

# ─── Configuration ────────────────────────────────────────────────────────
PROJECT_NAME="${PROJECT_NAME:-cloud-hosting-project}"
ENVIRONMENT="${ENVIRONMENT:-production}"
AWS_REGION="${AWS_REGION:-us-east-1}"
STACK_NAME="${PROJECT_NAME}-stack"
KEY_PAIR_NAME="${KEY_PAIR_NAME:-}"
SSH_CIDR="${SSH_CIDR:-0.0.0.0/0}"
INSTANCE_TYPE="${INSTANCE_TYPE:-t3.micro}"
S3_DEPLOY_BUCKET="${S3_DEPLOY_BUCKET:-}"

log()   { echo -e "\033[0;32m[$(date '+%H:%M:%S')] ✅  $*\033[0m"; }
warn()  { echo -e "\033[0;33m[$(date '+%H:%M:%S')] ⚠️  $*\033[0m"; }
error() { echo -e "\033[0;31m[$(date '+%H:%M:%S')] ❌  $*\033[0m"; exit 1; }

# ─── Preflight Checks ─────────────────────────────────────────────────────
log "Running preflight checks..."
command -v aws   >/dev/null 2>&1 || error "AWS CLI not found. Install from https://aws.amazon.com/cli/"
command -v python3 >/dev/null 2>&1 || error "Python 3 not found."
aws sts get-caller-identity --region "$AWS_REGION" >/dev/null 2>&1 || error "AWS credentials not configured."

[ -z "$KEY_PAIR_NAME" ] && error "KEY_PAIR_NAME is required. Set via: export KEY_PAIR_NAME=your-key"
[ -z "$S3_DEPLOY_BUCKET" ] && error "S3_DEPLOY_BUCKET is required. Set via: export S3_DEPLOY_BUCKET=your-bucket"

# ─── Upload Templates to S3 ───────────────────────────────────────────────
log "Uploading CloudFormation templates to S3..."
TEMPLATES_PREFIX="cloudformation/${PROJECT_NAME}"

for template in cloudformation/*.yaml; do
  aws s3 cp "$template" "s3://${S3_DEPLOY_BUCKET}/${TEMPLATES_PREFIX}/$(basename $template)" \
    --region "$AWS_REGION"
  log "Uploaded: $template"
done

TEMPLATE_URL="https://s3.amazonaws.com/${S3_DEPLOY_BUCKET}/${TEMPLATES_PREFIX}/main-stack.yaml"

# ─── Deploy or Update Stack ───────────────────────────────────────────────
STACK_EXISTS=$(aws cloudformation describe-stacks \
  --stack-name "$STACK_NAME" \
  --region "$AWS_REGION" \
  --query "Stacks[0].StackStatus" \
  --output text 2>/dev/null || echo "DOES_NOT_EXIST")

PARAMS=(
  "ParameterKey=ProjectName,ParameterValue=${PROJECT_NAME}"
  "ParameterKey=Environment,ParameterValue=${ENVIRONMENT}"
  "ParameterKey=EC2InstanceType,ParameterValue=${INSTANCE_TYPE}"
  "ParameterKey=KeyPairName,ParameterValue=${KEY_PAIR_NAME}"
  "ParameterKey=SSHAllowedCIDR,ParameterValue=${SSH_CIDR}"
)

if [ "$STACK_EXISTS" == "DOES_NOT_EXIST" ]; then
  log "Creating new CloudFormation stack: $STACK_NAME"
  aws cloudformation create-stack \
    --stack-name "$STACK_NAME" \
    --template-url "$TEMPLATE_URL" \
    --parameters "${PARAMS[@]}" \
    --capabilities CAPABILITY_NAMED_IAM \
    --region "$AWS_REGION" \
    --tags \
      "Key=Project,Value=${PROJECT_NAME}" \
      "Key=Environment,Value=${ENVIRONMENT}"
  ACTION="create"
else
  log "Updating existing stack: $STACK_NAME (current status: $STACK_EXISTS)"
  aws cloudformation update-stack \
    --stack-name "$STACK_NAME" \
    --template-url "$TEMPLATE_URL" \
    --parameters "${PARAMS[@]}" \
    --capabilities CAPABILITY_NAMED_IAM \
    --region "$AWS_REGION" || {
      warn "No changes detected in stack."
      exit 0
    }
  ACTION="update"
fi

# ─── Wait for Completion ──────────────────────────────────────────────────
log "Waiting for stack ${ACTION} to complete..."
aws cloudformation wait "stack-${ACTION}-complete" \
  --stack-name "$STACK_NAME" \
  --region "$AWS_REGION"

# ─── Show Outputs ─────────────────────────────────────────────────────────
log "Stack deployed successfully! Outputs:"
aws cloudformation describe-stacks \
  --stack-name "$STACK_NAME" \
  --region "$AWS_REGION" \
  --query "Stacks[0].Outputs[].[OutputKey,OutputValue]" \
  --output table

log "Deployment complete. 🎉"
