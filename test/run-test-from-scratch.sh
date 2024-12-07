#!/bin/bash
# see ../CONTRIBUTION.md

# vars
account_id=$(aws sts get-caller-identity --query "Account" --output text )
bucket=cid-$account_id-test
export bucket

# upload files
./data-collection/utils/upload.sh  "$bucket"

# run test
python3 ./test/test_from_scratch.py "$@"