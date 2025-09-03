#!/usr/bin/env bash
set -Eeuo pipefail

# ---------------------------------------------------------
# 统一在项目根目录执行（本脚本在 scripts/deploy/ 下）
# ---------------------------------------------------------
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")"/../.. && pwd)"
cd "$ROOT"

# ---------------------------------------------------------
# venv 配置
# ---------------------------------------------------------
VENV_DIR="${VENV_DIR:-$ROOT/venv}"
PY="$VENV_DIR/bin/python3"

# 如果 venv 不存在，就创建一个
if [ ! -x "$PY" ]; then
  echo "[deploy] creating venv at: $VENV_DIR"
  command -v python3 >/dev/null || { echo "❌ python3 未安装"; exit 1; }
  python3 -m venv "$VENV_DIR"
  "$PY" -m ensurepip --upgrade || true
  "$PY" -m pip install --upgrade pip setuptools wheel
fi

# 打印当前解释器路径
echo "[deploy] python: $("$PY" -c 'import sys; print(sys.executable)')"

# ---------------------------------------------------------
# 安装依赖
# ---------------------------------------------------------
if [ -f requirements.txt ]; then
  echo "[deploy] installing deps from requirements.txt"
  "$PY" -m pip install -r requirements.txt
else
  echo "[deploy] no requirements.txt found, skip deps"
fi

# ---------------------------------------------------------
# 加载环境变量（可选）
# ---------------------------------------------------------
if [ -f .env ]; then
  set -a
  . ./.env
  set +a
  echo "[deploy] .env loaded"
fi

# ---------------------------------------------------------
# 启动服务（请按实际入口改 main.py / app.py）
# ---------------------------------------------------------
echo "[deploy] starting service..."
exec "$PY" main.py
