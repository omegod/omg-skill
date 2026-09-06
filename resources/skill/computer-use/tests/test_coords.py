#!/usr/bin/env python3
"""Self-contained tests for cu.py coordinate resolution + key mapping.

Run with a python that has pyobjc (e.g. the skill venv):
  .venv/bin/python tests/test_coords.py
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

META = {
    "path": "/tmp/screen.png",
    "display_id": 1, "display_index": 1,
    "origin_x": 0, "origin_y": 0,
    "point_w": 1280, "point_h": 832,
    "pixel_w": 2560, "pixel_h": 1664,
    "scale": 2.0,
    "captured_at": 0,
}

failures = []


def check(name, got, want):
    if got != want:
        failures.append(f"{name}: got {got!r}, want {want!r}")
    else:
        print(f"  ok  {name}")


# --- coordinate resolution -------------------------------------------------
import cu  # noqa: E402

x, y = cu.resolve_xy(2560, 1664, "image", META)
check("image px top-left -> points", (round(x), round(y)), (1280, 832))

x, y = cu.resolve_xy(100, 200, "image", META)
check("image px quarter -> points", (round(x), round(y)), (50, 100))

META2 = dict(META, origin_x=-1440, origin_y=0, scale=2.0)  # left-extended display
x, y = cu.resolve_xy(500, 800, "image", META2)
check("secondary display origin", (round(x), round(y)), (-1440 + 250, 400))

x, y = cu.resolve_xy(500, 500, "norm", META)
check("norm 0-1000 -> points", (round(x, 1), round(y, 1)), (640.0, 416.0))

x, y = cu.resolve_xy(-30, 40, "pts", META)
check("pts passthrough", (x, y), (-30.0, 40.0))

rx, ry, rw, rh = cu.resolve_rect(200, 100, 400, 200, "image", META)
check("rect in image px", (round(rx), round(ry), round(rw), round(rh)), (100, 50, 200, 100))

rx, ry, rw, rh = cu.resolve_rect(200, 100, 400, 200, "pts", META)
check("rect pts passthrough", (rx, ry, rw, rh), (200.0, 100.0, 400.0, 200.0))

# region 期望像素 = resolve_rect 的逆运算：image 模式期望 == 输入像素；pts 模式乘换算时
# 的同一个 scale。捕获后用它校验"PNG 实际尺寸"（裁剪未生效 fail-closed）。勿用
# CGDisplayPixelsWide 量显示 scale——macOS 26 返回点数，会把正确的裁剪误报为失败。
check("region expected px image==input", cu.region_expected_px(800, 600, "image", 2.0), (800, 600))
check("region expected px pts 2x", cu.region_expected_px(400, 300, "pts", 2.0), (800, 600))
check("region expected px pts 1x", cu.region_expected_px(400, 300, "pts", 1.0), (400, 300))

# --- key mapping ------------------------------------------------------------
check("keycode cmd+c base key", cu.KEY_CODES["c"], 8)
check("keycode return", cu.KEY_CODES["return"], 36)
check("keycode f5", cu.KEY_CODES["f5"], 96)
check("modifier flag cmd", cu.MODIFIERS["cmd"], cu.Quartz.kCGEventFlagMaskCommand)
check("modifier flag shift", cu.MODIFIERS["shift"], cu.Quartz.kCGEventFlagMaskShift)

# no duplicate keycode collisions among letters/digits
letters = "abcdefghijklmnopqrstuvwxyz0123456789"
codes = [cu.KEY_CODES[c] for c in letters]
check("no letter/digit keycode collisions", len(codes), len(set(codes)))

print()
if failures:
    print(json.dumps({"ok": False, "failures": failures}, indent=2))
    sys.exit(1)
print(json.dumps({"ok": True, "tests_passed": True}))
