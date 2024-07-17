#!/bin/bash
export account_id=$(aws sts get-caller-identity --query "Account" --output text )
export bucket=cid-$account_id-test
./data-collection/utils/upload.sh  "$bucket"
python3 ./data-collection/test/test_from_scratch.py "$@"