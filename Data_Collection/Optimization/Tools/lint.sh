#!/bin/bash
# This script runs cfn-lint and cfn_nag_scan for all templates in folder
# run with 'all' parameter to show also checkov results (optionals)

RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m' # No Color

folder=$(git rev-parse --show-toplevel)/Data_Collection/Optimization/Code
success_count=0
failure_count=0
checkov_skip=CKV_AWS_18,CKV_AWS_117,CKV_AWS_116,CKV_AWS_173,CKV_AWS_115,CKV_AWS_195,CKV_SECRET_6

export exclude_files=("module-inventory.yaml" "module-pricing.yaml") # For::Each breaks lint :'(

yaml_files=$(find "$folder" -type f -name "*.yaml"
  -exec stat -c "%Y %n" {} \; | sort -n | awk '{print $2}')

for file in $yaml_files; do
    echo "Linting $(basename $file)"
    fail=0

    # Check if the current file is one of the two specified files
    if [ "$(basename $file)" == "${exclude_files[0]}" ] || [ "$(basename $file)" == "${exclude_files[1]}" ]; then
        echo -e "cfn-lint     ${RED}SKIP${NC} Fn:Each breaks lint"  | awk '{ print "\t" $0 }'
        echo -e "cfn_nag_scan ${RED}SKIP${NC} Fn:Each breaks lint"  | awk '{ print "\t" $0 }'
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

    if [[ "$1" == "all" ]]; then
        # checkov (optional)
        output=$(eval checkov  --skip-download --skip-check $checkov_skip --quiet -f "$file")
        if [ $? -ne 0 ]; then
            echo "$output" | awk '{ print "\t" $0 }'
            echo -e "checkov      ${RED}KO${NC}"  | awk '{ print "\t" $0 }'
            fail=1
        else
            echo -e "checkov      ${GREEN}OK${NC}"  | awk '{ print "\t" $0 }'
        fi
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
