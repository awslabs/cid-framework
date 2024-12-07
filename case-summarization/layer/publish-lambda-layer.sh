#!/bin/bash
# This script can be used for release or testing of lambda layers upload.

# First build layer
git_root=$(git rev-parse --show-toplevel)
cd "${git_root}/case-summarization/layer/" || exit
layer=$(./build-layer.sh)

# Then publish on s3
export AWS_REGION=us-east-1
export STACK_SET_NAME=LayerBuckets
aws cloudformation list-stack-instances \
  --stack-set-name $STACK_SET_NAME \
  --query 'Summaries[].[StackId,Region]' \
  --output text |
  while read -r stack_id region; do
    echo "uploading $layer to $region"
    # shellcheck disable=SC2016
    bucket=$(aws cloudformation list-stack-resources --stack-name "$stack_id" \
      --query 'StackResourceSummaries[?LogicalResourceId == `LayerBucket`].PhysicalResourceId' \
      --region "$region" --output text)
    # shellcheck disable=SC2181
    output=$(aws s3api put-object \
      --bucket "$bucket" \
      --key "cid-llm-lambda-layer/$layer" \
      --body "./$layer")
    # shellcheck disable=SC2181 disable=SC2002
    if [ $? -ne 0 ]; then
      echo "Error: $output"
    else
      echo "Uploaded successfuly"
    fi
  done

echo 'Cleanup'
rm -vf "./$layer"

echo 'Done'