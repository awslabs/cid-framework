#!/bin/bash
# This script builds the Lambda Layer that contains Pydantic & Llama_index

git_root=$(git rev-parse --show-toplevel)
# shellcheck disable=SC2155 disable=SC2002
export version=$(cat "${git_root}/case-summarization/utils/version.json" | jq .version --raw-output)
export prefix='llm'
cd "$(dirname "$0")" || exit

function build_layer {
    echo 'Building a layer'
    rm -rf ./python
    mkdir -p ./python
    python3 -m pip install   --only-binary=:all: --platform=manylinux2014_x86_64 --target=./python --requirement=./requirements.txt
    du -sh ./python # must be less then 256M
    rm -rf "$prefix-$version.zip"
    zip -qr "$prefix-$version.zip" ./python
    ls -h -l "$prefix-$version.zip"
    rm -rf ./python
}

build_layer 1>&2

ls "$prefix-$version.zip"