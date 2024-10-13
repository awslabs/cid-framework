#!/bin/bash
# shellcheck disable=SC2086
# This script builds a zip to be uploaded

code_path=$(git rev-parse --show-toplevel)/rls/deploy

rm $code_path/create_rls.zip
zip -j $code_path/create_rls.zip $code_path/create_rls.py
echo 'Done build'
