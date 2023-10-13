#!/bin/bash
# This script can be used for release

export AWS_REGION=us-east-1
export STACK_SET_NAME=LayerBuckets

code_path=$(git rev-parse --show-toplevel)/data-collection/deploy

aws cloudformation list-stack-instances \
  --stack-set-name $STACK_SET_NAME \
  --query 'Summaries[].[StackId,Region]' \
  --output text |
  while read stack_id region; do
    echo "uploading cid-$CID_VERSION.zip to $region"
    bucket=$(aws cloudformation list-stack-resources --stack-name $stack_id \
      --query 'StackResourceSummaries[?LogicalResourceId == `LayerBucket`].PhysicalResourceId' \
      --region $region --output text)

    aws s3 sync $code_path/       s3://$bucket/cfn/data-collection/
  done

echo 'Done'