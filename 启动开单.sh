#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
if [[ -x .venv/bin/python ]]; then
  PY=".venv/bin/python"
else
  echo "还没有开单环境。在仓库根目录执行一次："
  echo "  python3 -m venv .venv"
  echo "  .venv/bin/python -m pip install -e '.[dev]'"
  exit 1
fi
exec "$PY" -u scripts/start_clerk.py "$@"
