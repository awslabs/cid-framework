#!/bin/bash
# shellcheck disable=SC2016,SC2086,SC2162
# This script can be used for release

export CENTRAL_BUCKET=aws-managed-cost-intelligence-dashboards

code_path=$(git rev-parse --show-toplevel)/case-summarization/deploy

echo "sync to central bucket"
aws s3 sync $code_path/       s3://$CENTRAL_BUCKET/cfn/case-summarization/