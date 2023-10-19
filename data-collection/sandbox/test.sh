#!/bin/bash
cd /home/erichre/code/cid-framework
export account_id=$(aws sts get-caller-identity --query "Account" --output text )
export bucket=cid-$account_id-test
#sh ./data-collection/utils/lint.sh
#python3 ./data-collection/utils/pylint.py
sh ./data-collection/utils/upload.sh  "cid-317256447485-test"
pytest ./data-collection/test/test_from_scratch.py --mode $1 | tee ./data-collection/sandbox/testout.txt


