#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT_DIR"

PYTHON_BIN=${PYTHON:-python3}

if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  echo "[!] python3 未找到，请先安装 Python 3.9+" >&2
  exit 1
fi

if [ ! -d .venv ]; then
  "$PYTHON_BIN" -m venv .venv
  echo "[*] 已创建虚拟环境 .venv"
fi

# shellcheck source=/dev/null
source .venv/bin/activate

python -m pip install --upgrade pip
python -m pip install -r requirements.txt

if [ ! -f .env ]; then
  cp -n .env.example .env
  echo "[*] 已生成 .env，请填写 TELEGRAM_TOKEN/TELEGRAM_CHAT_ID 等参数后重新运行"
  exit 0
fi

exec python main.py
