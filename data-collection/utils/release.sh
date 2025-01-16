#!/bin/bash
# shellcheck disable=SC2016,SC2086,SC2162
# This script can be used for release

export AWS_REGION=us-east-1
export STACK_SET_NAME=LayerBuckets
export CENTRAL_BUCKET=aws-managed-cost-intelligence-dashboards

code_path=$(git rev-parse --show-toplevel)/data-collection/deploy

echo "sync to central bucket"
aws s3 sync $code_path/       s3://$CENTRAL_BUCKET/cfn/data-collection/

echo "sync to regional bucket with version prefix"
version=$(cat data-collection/utils/version.json | tr -d '"{} ' | awk -F: '{print $2}')
aws s3 sync $code_path/       s3://$CENTRAL_BUCKET/cfn/data-collection/$version/

aws cloudformation list-stack-instances \
  --stack-set-name $STACK_SET_NAME \
  --query 'Summaries[].[StackId,Region]' \
  --output text |
  while read stack_id region; do
    echo "sync to $region"
    bucket=$(aws cloudformation list-stack-resources --stack-name $stack_id \
      --query 'StackResourceSummaries[?LogicalResourceId == `LayerBucket`].PhysicalResourceId' \
      --region $region --output text)

    aws s3 sync $code_path/       s3://$bucket/cfn/data-collection/ --delete
  done

echo 'Done'