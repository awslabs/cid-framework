#!/bin/bash
folder=$(pwd)
code_path=$(git rev-parse --show-toplevel)/Data_Collection/Optimization/Code

RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m' # No Color

echo "linting CFN templates"
for template in $code_path/*.yaml; do
  rel_path=$template
  echo "Linting"
  echo "$(cfn_nag_scan --input-path $rel_path -f && echo -e "cfn_nag_scan ${GREEN}OK${NC}" || echo -e "cfn_nag_scan ${RED}KO${NC}" )"  | awk '{ print "\t" $0 }'
  echo "$(cfn-lint  -- $rel_path                 && echo -e "cfn-lint     ${GREEN}OK${NC}" || echo -e "cfn-lint     ${RED}KO${NC}" )"  | awk '{ print "\t" $0 }'
done

cd $pwd


