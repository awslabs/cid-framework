#!/bin/bash

RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m' # No Color

folder=$(git rev-parse --show-toplevel)/Data_Collection/Optimization/Code
success_count=0
failure_count=0

for file in "$folder"/*.yaml; do
    echo "Linting $file"
    fail=0

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
