
#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(git rev-parse --show-toplevel)"
HOOK_DIR="$ROOT_DIR/.git/hooks"

mkdir -p "$HOOK_DIR"

#############################################
# commit-msg hook
#############################################
cat > "$HOOK_DIR/commit-msg" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

COMMIT_MSG_FILE="$1"
REPO_ROOT="$(git rev-parse --show-toplevel)"
bash "$REPO_ROOT/ops/git/commit/commit_msg.sh" "$COMMIT_MSG_FILE"
EOF

chmod +x "$HOOK_DIR/commit-msg"
echo "✅ commit-msg hook 已安装"


#############################################
# pre-push hook
#############################################
cat > "$HOOK_DIR/pre-push" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

REMOTE="$1"
URL="$2"

REPO_ROOT="$(git rev-parse --show-toplevel)"
bash "$REPO_ROOT/ops/git/push/pre-push-hook.sh" "$@"
EOF

chmod +x "$HOOK_DIR/pre-push"
echo "✅ pre-push hook 已安装"


#############################################
# post-commit hook
#############################################
cat > "$HOOK_DIR/post-commit" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel)"
bash "$REPO_ROOT/ops/git/commit/post-commit.sh"
EOF

chmod +x "$HOOK_DIR/post-commit"
echo "✅ post-commit hook 已安装"