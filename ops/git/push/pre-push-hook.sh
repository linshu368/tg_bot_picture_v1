#!/bin/bash
set -e

# 加载配置
SCRIPT_DIR="$(dirname "$(realpath "$0")")"
source "$SCRIPT_DIR/../config.sh"

REMOTE="$1"
URL="$2"

# 设置Python环境
[ -x "$PYTHON_BIN" ] || PYTHON_BIN="$PYTHON_FALLBACK"

while read local_ref local_sha remote_ref remote_sha
do
    if [ "$remote_sha" = "0000000000000000000000000000000000000000" ]; then
        RANGE="$local_sha"
    else
        RANGE="$remote_sha..$local_sha"
    fi

    COMMITS=$(git log $RANGE --pretty=format:"%H")

    "$PYTHON_BIN" "$PROJECT_ROOT/ops/git/push/gen_pushlog.py" \
        --remote "$REMOTE" \
        --branch "$(git rev-parse --abbrev-ref HEAD)" \
        --commits "$COMMITS"
done