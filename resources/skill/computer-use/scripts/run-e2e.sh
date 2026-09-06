#!/bin/sh
# cu 自测入口（三套，全部自驱动）：
#   1) tests/test_coords.py   坐标/键码单测，无权限要求，任何 python+pyobjc 可跑
#   2) scripts/e2e_ax.py      AX 闭环 e2e，仅需「辅助功能」权限（不需要录屏）
#   3) scripts/e2e_test.py    视觉闭环 e2e，需要录屏+辅助功能 → 从已授权的宿主跑：
#                             open -a Terminal scripts/run-e2e.sh
# 结果分别写入 /tmp/cu-e2e-result.json 与 /tmp/cu-ax-e2e-result.json。
DIR="$(cd "$(dirname "$0")" && pwd)"
PY="$DIR/../.venv/bin/python"

echo "== test_coords =="; "$PY" "$DIR/../tests/test_coords.py" || exit 1
echo "== e2e_ax ==";     "$PY" "$DIR/e2e_ax.py"       || exit 1
echo "== e2e visual =="; "$PY" "$DIR/e2e_test.py"
