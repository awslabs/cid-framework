#!/bin/bash
# This script runs cfn-lint cfn_nag_scan and checkov for all templates in folder

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
NC='\033[0m' # No Color

folder=$(git rev-parse --show-toplevel)/data-collection/deploy
success_count=0
failure_count=0

# CKV_AWS_18 - Ensure AWS access logging is enabled on S3 buckets
# CKV_AWS_117 - Ensure AWS Lambda function is configured inside a VPC
# CKV_AWS_116 - Ensure the S3 bucket has logging enabled:
# CKV_AWS_173 - Check encryption settings for Lambda environmental variable
# CKV_AWS_195 - Ensure Glue component has a security configuration associated
# CKV_SECRET_6 - Base64 High Entropy String
checkov_skip=CKV_AWS_18,CKV_AWS_117,CKV_AWS_116,CKV_AWS_173,CKV_AWS_195,CKV_SECRET_6

export exclude_files=("module-inventory.yaml" "module-pricing.yaml") # For::Each breaks lint :'(

yaml_files=$(find "$folder" -type f -name "*.yaml" -exec ls -1t "{}" +;) # ordered by date

for file in $yaml_files; do
    echo "Linting $(basename $file)"
    fail=0

    # checkov
    output=$(eval checkov  --skip-download --skip-check $checkov_skip --quiet -f "$file")
    if [ $? -ne 0 ]; then
        echo "$output" | awk '{ print "\t" $0 }'
        echo -e "checkov      ${RED}KO${NC}"  | awk '{ print "\t" $0 }'
        fail=1
    else
        echo -e "checkov      ${GREEN}OK${NC}"  | awk '{ print "\t" $0 }'
    fi

    if [ "$(basename $file)" == "${exclude_files[0]}" ] || [ "$(basename $file)" == "${exclude_files[1]}" ]; then
        echo -e "cfn-lint     ${YELLOW}SKIP${NC} For::Each breaks lint"  | awk '{ print "\t" $0 }'
        echo -e "cfn_nag_scan ${YELLOW}SKIP${NC} For::Each breaks lint"  | awk '{ print "\t" $0 }'
        continue
    fi

    # cfn-lint
    output=$(eval cfn-lint -- "$file")
    if [ $? -ne 0 ]; then
        echo "$output" | awk '{ print "\t" $0 }'
        echo -e "cfn-lint     ${RED}KO${NC}"  | awk '{ print "\t" $0 }'
        fail=1
    else
        echo -e "cfn-lint     ${GREEN}OK${NC}"  | awk '{ print "\t" $0 }'
    fi

    # cfn_nag_scan
    output=$(eval cfn_nag_scan --input-path "$file")
    if [ $? -ne 0 ]; then
        echo "$output" | awk '{ print "\t" $0 }'
        echo -e "cfn_nag_scan ${RED}KO${NC}"  | awk '{ print "\t" $0 }'
        fail=1
    else
        echo -e "cfn_nag_scan ${GREEN}OK${NC}"  | awk '{ print "\t" $0 }'
    fi

    if [ $fail -ne 0 ]; then
        ((failure_count++))
    else
        ((success_count++))
    fi
done

echo "Successful lints: $success_count"
echo "Failed lints:     $failure_count"
if [ $failure_count -ne 0 ]; then
    exit 1
else
    exit 0
fi
