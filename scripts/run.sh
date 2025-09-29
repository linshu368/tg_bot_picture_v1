# ---------------------------------------------------------
# 检查是否有 pm2 正在运行本项目
# ---------------------------------------------------------
if command -v pm2 >/dev/null 2>&1; then
  if pm2 list | grep -q "tg-bot-picture"; then
    echo "❌ 检测到 pm2 中已运行 tg-bot-picture，请先停止 pm2 再运行 run.sh"
    echo "👉 运行: pm2 stop tg-bot-picture"
    exit 1
  fi
fi


#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")"/../.. && pwd)"
cd "$ROOT"

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
# 加载环境变量
# ---------------------------------------------------------
if [ -f .env ]; then
  set -a
  . ./.env
  set +a
  echo "[deploy] .env loaded"
fi

# ---------------------------------------------------------
# 检查 PM2 冲突
# ---------------------------------------------------------
if command -v pm2 >/dev/null 2>&1; then
  if pm2 list | grep -q "tg-bot-picture"; then
    echo "❌ 检测到 pm2 中已运行 tg-bot-picture，请先停止 pm2 再运行 run.sh"
    echo "👉 运行: pm2 stop tg-bot-picture"
    exit 1
  fi
fi

# ---------------------------------------------------------
# 启动服务
# ---------------------------------------------------------
echo "[deploy] starting service..."
exec "$PY" main.py