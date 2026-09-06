#!/bin/bash
# cu — macOS computer-use executor 入口。
# 优先用技能自带 .venv；缺失时尝试系统 python3；都没有 pyobjc 则自动创建 venv 并安装。
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_PY="$DIR/../.venv/bin/python"

if [ -x "$VENV_PY" ]; then
    exec "$VENV_PY" "$DIR/cu.py" "$@"
fi

if command -v python3 >/dev/null 2>&1 && python3 -c "import Quartz" >/dev/null 2>&1; then
    exec python3 "$DIR/cu.py" "$@"
fi

echo '{"ok": false, "error": "pyobjc not available; bootstrapping venv (requires network). Rerun this command after setup finishes."}' >&2
if command -v python3 >/dev/null 2>&1; then
    python3 -m venv "$DIR/../.venv"
    "$DIR/../.venv/bin/pip" install -q pyobjc-framework-Quartz pyobjc-framework-Cocoa \
        pyobjc-framework-ApplicationServices pyobjc-framework-Vision
    echo '{"ok": true, "note": "venv bootstrapped, rerun command"}' >&2
fi
exit 1
