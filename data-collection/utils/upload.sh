#!/bin/bash
# shellcheck disable=SC2086
# This script uploads CloudFormation files to S3 bucket. Can be used with any testing bucket or prod.
# see also README.md

if [ -n "$1" ]; then
  bucket=$1
else
  echo "ERROR: First parameter not supplied. Provide a bucket name. aws-well-architected-labs for prod aws-wa-labs-staging for stage "
  echo " prod  aws-well-architected-labs "
  exit 1
fi
code_path=$(git rev-parse --show-toplevel)/data-collection/deploy

# Create zip file for each lambda function
lambda_path="$code_path"/source/lambda
for file in "$lambda_path"/*.py; do
  filename=$(basename "$file")
  zipfilename="${filename%.*}.zip"
  zip -qu "$lambda_path/$directory/$zipfilename" "$file"
done

echo "Sync to $bucket"
aws s3 sync $code_path/       s3://$bucket/cfn/data-collection/
echo 'Done'
