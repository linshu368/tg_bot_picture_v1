# 安装 commit-msg hook
#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(git rev-parse --show-toplevel)"
HOOK_DIR="$ROOT_DIR/.git/hooks"

mkdir -p "$HOOK_DIR"

# commit-msg hook
cat > "$HOOK_DIR/commit-msg" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

COMMIT_MSG_FILE="$1"
REPO_ROOT="$(git rev-parse --show-toplevel)"
bash "$REPO_ROOT/scripts/commit/commit_msg.sh" "$COMMIT_MSG_FILE"
EOF

chmod +x "$HOOK_DIR/commit-msg"
echo "✅ commit-msg hook 已安装"

