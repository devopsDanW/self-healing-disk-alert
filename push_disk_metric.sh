#!/usr/bin/env bash
set -euo pipefail

NAMESPACE="KangaNews/Disk"
METRIC_NAME="UsedPercent"

CHECK_PATH="${CHECK_PATH:-/}"
REGION="${AWS_REGION:-ap-southeast-2}"

# IMDSv2, put request token, get instanceId with token, IMDSv1 SSRF
if [[ -z "${INSTANCE_ID:-}" ]]; then
    TOKEN=$(curl -sX PUT "http://169.254.169.254/latest/api/token" -H "X-aws-ec2-metadata-token-ttl-seconds: 21600")
    INSTANCE_ID=$(curl -s -H "X-aws-ec2-metadata-token: $TOKEN" "http://169.254.169.254/latest/meta-data/instance-id")
fi

USED_PERCENT=$(df --output=pcent "$CHECK_PATH" 2>/dev/null | tail -n1 | tr -dc '0-9') || true

if [[ -z "${USED_PERCENT}" ]]; then
    echo "ERROR: could not read disk used for path $CHECK_PATH" >&2
    exit 1
fi

aws cloudwatch put-metric-data \
    --region "$REGION" \
    --namespace "$NAMESPACE" \
    --metric-name "$METRIC_NAME" \
    --value "$USED_PERCENT" \
    --unit Percent \
    --dimensions "InstanceId=$INSTANCE_ID,Path=$CHECK_PATH"

echo "sent UsedPercent=$USED_PERCENT instance=$INSTANCE_ID path=$CHECK_PATH"