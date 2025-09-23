#!/bin/bash
set -e

REMOTE="$1"
URL="$2"
REPO_ROOT="$(git rev-parse --show-toplevel)"

while read local_ref local_sha remote_ref remote_sha
do
    if [ "$remote_sha" = "0000000000000000000000000000000000000000" ]; then
        RANGE="$local_sha"
    else
        RANGE="$remote_sha..$local_sha"
    fi

    COMMITS=$(git log $RANGE --pretty=format:"%H")

    "$REPO_ROOT/venv/bin/python" scripts/push/gen_pushlog.py \
        --remote "$REMOTE" \
        --branch "$(git rev-parse --abbrev-ref HEAD)" \
        --commits "$COMMITS"
done