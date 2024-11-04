#!/bin/bash
# This script can be used for release or testing of lambda layers upload.

# First build layer
git_root=$(git rev-parse --show-toplevel)
cd ${git_root}/case-summarization/layer/
layer=$(./build-layer.sh)

# Then publish on s3
export AWS_REGION=us-east-1
export STACK_SET_NAME=LayerBuckets
aws cloudformation list-stack-instances \
  --stack-set-name $STACK_SET_NAME \
  --query 'Summaries[].[StackId,Region]' \
  --output text |
  while read stack_id region; do
    echo "uploading $layer to $region"
    bucket=$(aws cloudformation list-stack-resources --stack-name $stack_id \
      --query 'StackResourceSummaries[?LogicalResourceId == `LayerBucket`].PhysicalResourceId' \
      --region $region --output text)
    output=$(aws s3api put-object \
      --bucket "$bucket" \
      --key cid-llm-lambda-layer/$layer \
      --body ./$layer)
    if [ $? -ne 0 ]; then
      echo "Error: $output"
    else
      echo "Uploaded successfuly"
    fi
  done

echo 'Cleanup'
rm -vf ./$layer

echo 'Done'