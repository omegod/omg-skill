#!/usr/bin/env python3
"""cu — macOS computer-use executor for vision-only agents.

Screenshot via `screencapture`, mouse/keyboard via pyobjc Quartz CGEvents,
accessibility (AX) tree reads and semantic actions via pyobjc ApplicationServices.
All commands print a single JSON object on stdout: {"ok": true, ...} or
{"ok": false, "error": "..."}.

Coordinate contract:
  * `screenshot` writes a sidecar meta file recording pixel size, point size,
    scale and display origin of the captured image (region/window crops save
    their own adjusted origin, so clicks on a cropped image resolve correctly).
  * click/move/drag/scroll default to IMAGE PIXEL coordinates of the last
    screenshot and convert to screen points automatically.
    `--pts` accepts raw screen points, `--norm` accepts 0..1000 normalized.
  * `ax tree`/`ax find` output `pos`/`size` in screen points directly —
    consume them with `click --mode pts`.

Freshness contract (ax):
  * `ax tree`/`ax find` write a handle snapshot (path → role+title).
  * Action commands (`ax press/set/action/select/focus/attr`) re-resolve the
    path live and verify it against the snapshot; any mismatch fails closed
    with {"code": "stale"} — re-dump the tree and pick a fresh handle.
"""

import argparse
import ctypes
import json
import os
import re
import struct
import subprocess
import sys
import time

import Quartz
import objc
import ApplicationServices as AS
from AppKit import NSWorkspace
from CoreFoundation import CFEqual, CFRange

META_DIR = os.path.expanduser("~/.cache/omg-computer-use")
META_PATH = os.path.join(META_DIR, "last-screenshot.json")

MOVE_DELAY = 0.08
DOWN_UP_DELAY = 0.02
KEY_DELAY = 0.02
TYPE_DELAY = 0.006

# Virtual key codes (macOS standard)
KEY_CODES = {
    "return": 36, "enter": 36, "tab": 48, "space": 49,
    "delete": 51, "backspace": 51, "forwarddelete": 117, "del": 117,
    "escape": 53, "esc": 53,
    "up": 126, "down": 125, "left": 123, "right": 124,
    "home": 115, "end": 119, "pageup": 116, "pagedown": 121,
    "capslock": 57, "fn": 63,
    "f1": 122, "f2": 120, "f3": 99, "f4": 118, "f5": 96, "f6": 97,
    "f7": 98, "f8": 100, "f9": 101, "f10": 109, "f11": 103, "f12": 111,
    "f13": 105, "f14": 107, "f15": 113,
    "volumeup": 72, "volumedown": 73, "mute": 74,
    # letters/digits: real keycodes so shortcuts like cmd+c carry the right key
    **{
    "a": 0, "s": 1, "d": 2, "f": 3, "h": 4, "g": 5, "z": 6, "x": 7, "c": 8,
    "v": 9, "b": 11, "q": 12, "w": 13, "e": 14, "r": 15, "y": 16, "t": 17,
    "u": 32, "i": 34, "o": 31, "p": 35, "l": 37, "j": 38, "k": 40, "n": 45,
    "m": 46,
    "1": 18, "2": 19, "3": 20, "4": 21, "5": 23, "6": 22, "7": 26, "8": 28,
    "9": 25, "0": 29,
    },
}

MODIFIERS = {
    "cmd": Quartz.kCGEventFlagMaskCommand, "command": Quartz.kCGEventFlagMaskCommand,
    "shift": Quartz.kCGEventFlagMaskShift,
    "ctrl": Quartz.kCGEventFlagMaskControl, "control": Quartz.kCGEventFlagMaskControl,
    "alt": Quartz.kCGEventFlagMaskAlternate, "opt": Quartz.kCGEventFlagMaskAlternate,
    "option": Quartz.kCGEventFlagMaskAlternate,
    # pyobjc lacks a named constant for the fn flag; CGEventTypes.h: 1 << 23
    "fn": getattr(Quartz, "kCGEventFlagMaskSecondaryFn", 1 << 23),
}

BUTTONS = {
    "left": (Quartz.kCGEventLeftMouseDown, Quartz.kCGEventLeftMouseUp,
             Quartz.kCGEventLeftMouseDragged, Quartz.kCGMouseButtonLeft),
    "right": (Quartz.kCGEventRightMouseDown, Quartz.kCGEventRightMouseUp,
              Quartz.kCGEventRightMouseDragged, Quartz.kCGMouseButtonRight),
    "middle": (Quartz.kCGEventOtherMouseDown, Quartz.kCGEventOtherMouseUp,
               Quartz.kCGEventOtherMouseDragged, Quartz.kCGMouseButtonCenter),
}


def out(payload):
    print(json.dumps(payload, ensure_ascii=False))
    sys.exit(0 if payload.get("ok") else 1)


def fail(error, **extra):
    out(dict(ok=False, error=error, **extra))


# ---------------------------------------------------------------- meta / coords

def save_meta(meta):
    os.makedirs(META_DIR, exist_ok=True)
    tmp = META_PATH + ".tmp"
    with open(tmp, "w") as f:
        json.dump(meta, f)
    os.replace(tmp, META_PATH)


def load_meta(required=True):
    try:
        with open(META_PATH) as f:
            return json.load(f)
    except FileNotFoundError:
        if required:
            fail("no screenshot taken yet: run `cu screenshot` first so image "
                 "coordinates can be resolved", hint="cu screenshot")
        return None


def resolve_xy(x, y, mode, meta):
    """Return global screen points for (x, y) given in `mode` coordinates."""
    if mode == "pts":
        return float(x), float(y)
    if meta is None:
        fail("no screenshot meta available; run `cu screenshot` first")
    ox, oy = meta["origin_x"], meta["origin_y"]
    if mode == "norm":
        return (ox + float(x) / 1000.0 * meta["point_w"],
                oy + float(y) / 1000.0 * meta["point_h"])
    if mode == "image":
        return (ox + float(x) / meta["scale"],
                oy + float(y) / meta["scale"])
    fail(f"unknown coordinate mode: {mode}")


def resolve_rect(x, y, w, h, mode, meta):
    rx, ry = resolve_xy(x, y, mode, meta)
    if mode == "norm":
        rw, rh = float(w) / 1000.0 * meta["point_w"], float(h) / 1000.0 * meta["point_h"]
    else:
        s = 1.0 if mode == "pts" else meta["scale"]
        rw, rh = float(w) / s, float(h) / s
    return rx, ry, rw, rh


# ---------------------------------------------------------------- displays

def list_displays():
    err, ids, count = Quartz.CGGetActiveDisplayList(16, None, None)
    if err != 0:
        fail(f"CGGetActiveDisplayList error {err}")
    displays = []
    for i, did in enumerate(ids[:count]):
        b = Quartz.CGDisplayBounds(did)
        displays.append({
            "index": i + 1,              # 1-based index for `screencapture -D`
            "display_id": int(did),
            "main": did == Quartz.CGMainDisplayID(),
            "x": int(b.origin.x), "y": int(b.origin.y),
            "point_w": int(b.size.width), "point_h": int(b.size.height),
        })
    return displays


def find_display(index=None):
    displays = list_displays()
    if index is None:
        main = [d for d in displays if d["main"]]
        return (main or displays)[0]
    for d in displays:
        if d["index"] == index:
            return d
    fail(f"display {index} not found; available: {displays}")


# ---------------------------------------------------------------- screenshot

def png_size(path):
    with open(path, "rb") as f:
        head = f.read(24)
    if head[:8] != b"\x89PNG\r\n\x1a\n":
        fail("screenshot output is not a PNG")
    w, h = struct.unpack(">II", head[16:24])
    return w, h


def _window_rect(window_id):
    """window_id → (rect pts, display, window info)；不在屏则 fail-closed。"""
    opts = Quartz.kCGWindowListOptionOnScreenOnly | Quartz.kCGWindowListExcludeDesktopElements
    for w in Quartz.CGWindowListCopyWindowInfo(opts, Quartz.kCGNullWindowID) or []:
        if w.get("kCGWindowNumber") == window_id:
            b = w.get("kCGWindowBounds", {})
            rect = (float(b.get("X", 0)), float(b.get("Y", 0)),
                    float(b.get("Width", 0)), float(b.get("Height", 0)))
            cx, cy = rect[0] + rect[2] / 2, rect[1] + rect[3] / 2
            disp = next((d for d in list_displays()
                         if d["x"] <= cx < d["x"] + d["point_w"]
                         and d["y"] <= cy < d["y"] + d["point_h"]), None)
            return rect, disp or find_display(None), w
    fail(f"window {window_id} not on screen; run `cu windows` for window ids")


def cmd_screenshot(args):
    if args.window is not None:
        rect, disp, winfo = _window_rect(args.window)
        region = True
    elif args.region_px:
        x, y, w, h = args.region_px
        # prev 可能缺键（从未截过图）——补默认值再走 resolve_rect，直传会 KeyError
        prev = load_meta(required=False) or {}
        rect = resolve_rect(x, y, w, h, "pts" if args.pts else "image",
                            {"origin_x": prev.get("origin_x", 0),
                             "origin_y": prev.get("origin_y", 0),
                             "scale": prev.get("scale") or 2.0})
        disp = find_display(args.display)
        region = True
    else:
        disp = find_display(args.display)
        rect = (float(disp["x"]), float(disp["y"]),
                float(disp["point_w"]), float(disp["point_h"]))
        region = False
    out_path = args.out or os.path.join(META_DIR, "screen.png")
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    if args.window is not None:
        # -l<id> 截窗口本体（-o 去阴影 → 图像边界=窗口 bounds）；后台/被遮挡窗口也可截
        cmd = ["screencapture", "-x", "-o", f"-l{args.window}", out_path]
        if args.cursor:
            cmd.append("-C")
    else:
        cmd = ["screencapture", "-x", "-D", str(disp["index"]), out_path]
        if args.cursor:
            cmd.insert(2, "-C")
        if region:
            cmd += ["-R", f"{rect[0]:.2f},{rect[1]:.2f},{rect[2]:.2f},{rect[3]:.2f}"]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
    if r.returncode != 0:
        fail(f"screencapture failed: {r.stderr.strip()}", code=r.returncode)
    if not os.path.exists(out_path) or os.path.getsize(out_path) == 0:
        fail("screencapture produced no output")
    pw, ph = png_size(out_path)
    meta = {
        "path": os.path.abspath(out_path),
        "display_id": disp["display_id"], "display_index": disp["index"],
        # origin/point_w/point_h 描述"这张截图覆盖的屏幕区域"——局部截图也
        # 保存自己的原点，图内像素坐标可直接喂给 click/move/drag/scroll
        "origin_x": rect[0], "origin_y": rect[1],
        "point_w": rect[2], "point_h": rect[3],
        "pixel_w": pw, "pixel_h": ph,
        "scale": round(pw / rect[2], 4) if rect[2] else None,
        "region": region,
        "captured_at": time.time(),
    }
    if args.window is not None:
        meta["window_id"] = args.window
        meta["owner"] = winfo.get("kCGWindowOwnerName")
        meta["title"] = winfo.get("kCGWindowName")
    save_meta(meta)
    out(dict(ok=True, **meta))


# ---------------------------------------------------------------- mouse

# --app 后台派发：非 None 时键盘事件直投该进程队列（CGEventPostToPid，公开 API）。
# 实测：QQ音乐 后台空格切换播放态成功；调研：macOS 无全局键盘过滤器，键盘直投
# 基本可行。鼠标不走此通道（部分自绘 app/Chromium 会忽略合成鼠标事件）。
_DISPATCH_PID = None


def post(event):
    if _DISPATCH_PID is not None:
        Quartz.CGEventPostToPid(_DISPATCH_PID, event)
    else:
        Quartz.CGEventPost(Quartz.kCGHIDEventTap, event)


def move_to(x, y, button="left"):
    down, up, dragged, btn = BUTTONS[button]
    kind = Quartz.kCGEventMouseMoved
    if button != "left":
        kind = {Quartz.kCGMouseButtonRight: Quartz.kCGEventRightMouseMoved,
                Quartz.kCGMouseButtonCenter: Quartz.kCGEventOtherMouseMoved}[btn]
    ev = Quartz.CGEventCreateMouseEvent(None, kind, (x, y), btn)
    post(ev)
    time.sleep(MOVE_DELAY)


def cmd_move(args):
    meta = load_meta() if args.mode != "pts" else None
    x, y = resolve_xy(args.x, args.y, args.mode, meta)
    move_to(x, y)
    out(dict(ok=True, x=x, y=y, mode=args.mode))


def cmd_click(args):
    if args.down and args.up:
        fail("--down 与 --up 互斥")
    meta = load_meta() if args.mode != "pts" else None
    x, y = resolve_xy(args.x, args.y, args.mode, meta)
    down_t, up_t, _, btn = BUTTONS[args.button]
    if args.down:  # 按下不释放（后续 --up 或 move 组合手势）
        move_to(x, y, args.button)
        ev = Quartz.CGEventCreateMouseEvent(None, down_t, (x, y), btn)
        Quartz.CGEventSetIntegerValueField(ev, Quartz.kCGMouseEventClickState, 1)
        post(ev)
        time.sleep(DOWN_UP_DELAY)
        out(dict(ok=True, x=x, y=y, button=args.button, phase="down", mode=args.mode))
    if args.up:  # 只释放：释放点=给定坐标，不在释放前移动指针
        ev = Quartz.CGEventCreateMouseEvent(None, up_t, (x, y), btn)
        Quartz.CGEventSetIntegerValueField(ev, Quartz.kCGMouseEventClickState, 1)
        post(ev)
        time.sleep(DOWN_UP_DELAY)
        out(dict(ok=True, x=x, y=y, button=args.button, phase="up", mode=args.mode))
        return
    move_to(x, y, args.button)
    for i in range(1, args.count + 1):
        for t in (down_t, up_t):
            ev = Quartz.CGEventCreateMouseEvent(None, t, (x, y), btn)
            Quartz.CGEventSetIntegerValueField(ev, Quartz.kCGMouseEventClickState, i)
            post(ev)
            time.sleep(DOWN_UP_DELAY)
        if i < args.count:
            time.sleep(0.06)
    out(dict(ok=True, x=x, y=y, button=args.button, count=args.count, mode=args.mode))


def cmd_drag(args):
    meta = load_meta() if args.mode != "pts" else None
    x1, y1 = resolve_xy(args.x1, args.y1, args.mode, meta)
    x2, y2 = resolve_xy(args.x2, args.y2, args.mode, meta)
    down_t, up_t, dragged_t, btn = BUTTONS[args.button]
    move_to(x1, y1, args.button)
    ev = Quartz.CGEventCreateMouseEvent(None, down_t, (x1, y1), btn)
    Quartz.CGEventSetIntegerValueField(ev, Quartz.kCGMouseEventClickState, 1)
    post(ev)
    time.sleep(0.05)
    steps = max(8, int(args.duration / 20))
    for i in range(1, steps + 1):
        t = i / steps
        ix, iy = x1 + (x2 - x1) * t, y1 + (y2 - y1) * t
        ev = Quartz.CGEventCreateMouseEvent(None, dragged_t, (ix, iy), btn)
        Quartz.CGEventSetIntegerValueField(ev, Quartz.kCGMouseEventClickState, 1)
        post(ev)
        time.sleep(args.duration / 1000.0 / steps)
    ev = Quartz.CGEventCreateMouseEvent(None, up_t, (x2, y2), btn)
    Quartz.CGEventSetIntegerValueField(ev, Quartz.kCGMouseEventClickState, 1)
    post(ev)
    time.sleep(DOWN_UP_DELAY)
    out(dict(ok=True, from_=[x1, y1], to=[x2, y2], duration_ms=args.duration, mode=args.mode))


def cmd_scroll(args):
    meta = load_meta() if (args.x is not None and args.mode != "pts") else None
    x, y = resolve_xy(args.x, args.y, args.mode, meta) if args.x is not None else None
    if x is not None:
        move_to(x, y)
    lines_v = -args.down + args.up          # positive wheel1 = scroll up
    lines_h = args.right - args.left        # sign verified live; see references
    try:
        ev = Quartz.CGEventCreateScrollWheelEvent(
            None, Quartz.kCGScrollEventUnitLine, 2, lines_v, lines_h)
    except TypeError:
        ev = Quartz.CGEventCreateScrollWheelEvent(
            None, Quartz.kCGScrollEventUnitLine, 1, lines_v)
    post(ev)
    time.sleep(0.05)
    out(dict(ok=True, at=[x, y] if x is not None else "cursor",
             down=args.down, up=args.up, left=args.left, right=args.right))


def cmd_position(args):
    loc = Quartz.CGEventGetLocation(Quartz.CGEventCreate(None))
    out(dict(ok=True, x=int(loc.x), y=int(loc.y)))


# ---------------------------------------------------------------- keyboard

def type_char(ch):
    if ch == "\n":
        key_code(KEY_CODES["return"], [])
        return
    if ch == "\t":
        key_code(KEY_CODES["tab"], [])
        return
    down = Quartz.CGEventCreateKeyboardEvent(None, 0, True)
    Quartz.CGEventKeyboardSetUnicodeString(down, len(ch), ch)
    up = Quartz.CGEventCreateKeyboardEvent(None, 0, False)
    Quartz.CGEventKeyboardSetUnicodeString(up, len(ch), ch)
    post(down)
    time.sleep(TYPE_DELAY)
    post(up)
    time.sleep(TYPE_DELAY)


def key_code(code, mods):
    flags = 0
    for m in mods:
        flags |= MODIFIERS[m]
    down = Quartz.CGEventCreateKeyboardEvent(None, code, True)
    up = Quartz.CGEventCreateKeyboardEvent(None, code, False)
    for ev in (down, up):
        Quartz.CGEventSetFlags(ev, flags)
    post(down)
    time.sleep(KEY_DELAY)
    post(up)
    time.sleep(KEY_DELAY)


def key_hold(code, mods, ms):
    """按住：down → sleep → up（holdkey / key --hold 共用）。"""
    flags = 0
    for m in mods:
        flags |= MODIFIERS[m]
    down = Quartz.CGEventCreateKeyboardEvent(None, code, True)
    up = Quartz.CGEventCreateKeyboardEvent(None, code, False)
    for ev in (down, up):
        Quartz.CGEventSetFlags(ev, flags)
    post(down)
    time.sleep(max(ms, 20) / 1000.0)
    post(up)
    time.sleep(KEY_DELAY)


def unicode_key_hold(text, mods, ms):
    flags = 0
    for m in mods:
        flags |= MODIFIERS[m]
    down = Quartz.CGEventCreateKeyboardEvent(None, 0, True)
    Quartz.CGEventKeyboardSetUnicodeString(down, len(text), text)
    Quartz.CGEventSetFlags(down, flags)
    up = Quartz.CGEventCreateKeyboardEvent(None, 0, False)
    Quartz.CGEventKeyboardSetUnicodeString(up, len(text), text)
    Quartz.CGEventSetFlags(up, flags)
    post(down)
    time.sleep(max(ms, 20) / 1000.0)
    post(up)
    time.sleep(KEY_DELAY)


def _parse_combo(combo):
    parts = [p.strip().lower() for p in combo.split("+") if p.strip()]
    return parts[:-1], parts[-1]


def _press_combo(combo, hold_ms=None):
    mods, name = _parse_combo(combo)
    if name in KEY_CODES:
        if hold_ms:
            key_hold(KEY_CODES[name], mods, hold_ms)
        else:
            key_code(KEY_CODES[name], mods)
    else:  # punctuation or other char: unicode event with modifier flags
        if hold_ms:
            unicode_key_hold(name, mods, hold_ms)
            return
        flags = 0
        for m in mods:
            flags |= MODIFIERS[m]
        down = Quartz.CGEventCreateKeyboardEvent(None, 0, True)
        Quartz.CGEventKeyboardSetUnicodeString(down, len(name), name)
        Quartz.CGEventSetFlags(down, flags)
        up = Quartz.CGEventCreateKeyboardEvent(None, 0, False)
        Quartz.CGEventKeyboardSetUnicodeString(up, len(name), name)
        Quartz.CGEventSetFlags(up, flags)
        post(down)
        time.sleep(KEY_DELAY)
        post(up)
        time.sleep(KEY_DELAY)


def cmd_key(args):
    global _DISPATCH_PID
    app_info = None
    if args.app:
        # 后台直投：先解析目标 app（fail-closed），键盘事件不经 HID 全局流
        app = resolve_app(args.app)
        app_info = _app_info(app)
        _DISPATCH_PID = app_info["pid"]
    for _ in range(args.repeat):
        for combo in args.keys:
            _press_combo(combo, args.hold)
    out(dict(ok=True, keys=args.keys, repeat=args.repeat,
             hold_ms=args.hold, channel="pid" if args.app else "foreground",
             app=app_info))


def cmd_type(args):
    global _DISPATCH_PID
    app_info = None
    if args.app:
        app = resolve_app(args.app)
        app_info = _app_info(app)
        _DISPATCH_PID = app_info["pid"]
    if args.paste:
        if args.repeat > 1:
            fail("--paste 与 --repeat > 1 不兼容")
        old = subprocess.run(["pbpaste"], capture_output=True, timeout=5).stdout
        subprocess.run(["pbcopy"], input=args.text.encode(), timeout=5)
        key_code(KEY_CODES["v"], ["cmd"])
        time.sleep(0.5)  # 等目标应用读完剪贴板再恢复
        subprocess.run(["pbcopy"], input=old, timeout=5)
        if args.press_enter:
            key_code(KEY_CODES["return"], [])
        out(dict(ok=True, pasted_len=len(args.text), mode="paste",
                 press_enter=args.press_enter, clipboard_restored=True,
                 channel="pid" if args.app else "foreground", app=app_info,
                 note="粘贴后已恢复原剪贴板文本（图片等非文本剪贴板无法恢复）"))
        return
    for _ in range(args.repeat):
        for ch in args.text:
            type_char(ch)
        if args.press_enter:
            key_code(KEY_CODES["return"], [])
    out(dict(ok=True, typed_len=len(args.text) * args.repeat,
             press_enter=args.press_enter,
             channel="pid" if args.app else "foreground", app=app_info))


def cmd_holdkey(args):
    name = args.key.strip().lower()
    if len(name) != 1 or name not in KEY_CODES:
        fail(f"holdkey 只支持单个可映射按键（字母/数字/功能键），得到 {args.key!r}")
    key_hold(KEY_CODES[name], [], args.duration)
    out(dict(ok=True, key=name, held_ms=args.duration))


# ---------------------------------------------------------------- environment

def _ax_probe_status():
    """辅助功能权限分项：denied（未授权）/ stale（已授权但宿主未重启）/ ok。"""
    if not AS.AXIsProcessTrusted():
        return "denied"
    # trusted 但宿主未重启时 AX 读会持续失败：用最可能可读的应用实测一次
    candidates = []
    fm = NSWorkspace.sharedWorkspace().frontmostApplication()
    if fm is not None and fm.activationPolicy() == 0:
        candidates.append(fm)
    for a in running_apps():
        if (a.bundleIdentifier() or "").startswith("com.apple.finder"):
            candidates.append(a)
            break
    for a in candidates:
        err, _ = ax_read(app_element(a.processIdentifier()), "AXRole")
        if err == 0:
            return "ok"
    return "stale"


def cmd_doctor(args):
    ax_status = _ax_probe_status()
    try:
        sr = Quartz.CGPreflightScreenCaptureAccess()
    except AttributeError:
        sr = None
    res = {
        "accessibility": ax_status == "ok",
        "screen_recording": sr is True,
        "status": {"accessibility": ax_status,
                   "screen-recording": "ok" if sr else "denied"},
    }
    try:
        app = NSWorkspace.sharedWorkspace().frontmostApplication()
        res["frontmost_app"] = app.localizedName()
    except Exception:
        res["frontmost_app"] = None
    res["displays"] = list_displays()
    res["python"] = sys.executable
    res["meta_path"] = META_PATH
    ok = res["accessibility"] and res["screen_recording"]
    notes = []
    if ax_status == "denied":
        notes.append("Accessibility permission missing: System Settings > "
                     "Privacy & Security > Accessibility: enable it for the "
                     "host app and restart it. Without it, clicks/keys are "
                     "silently dropped and AX reads fail.")
    elif ax_status == "stale":
        notes.append("Accessibility is granted but the AX probe failed: fully "
                     "restart the host app (terminal/editor) to pick it up. "
                     "AX reads/actions will fail until then.")
    if sr is None:
        notes.append("Screen Recording status unknown (macOS < 10.15).")
    elif sr is not True:
        notes.append("Screen Recording permission missing: System Settings > "
                     "Privacy & Security > Screen Recording: enable it for the "
                     "host app (terminal/editor) and fully restart it. Without "
                     "it, screencapture silently returns wallpaper-only images.")
    out(dict(ok=ok, checks=res, notes=notes))


def cmd_displays(args):
    out(dict(ok=True, displays=list_displays()))


def cmd_frontmost(args):
    app = NSWorkspace.sharedWorkspace().frontmostApplication()
    if app is None:
        fail("no frontmost application")
    out(dict(ok=True, name=app.localizedName(),
             bundle_id=app.bundleIdentifier(), pid=app.processIdentifier()))


def cmd_windows(args):
    opts = Quartz.kCGWindowListOptionOnScreenOnly | Quartz.kCGWindowListExcludeDesktopElements
    wins = Quartz.CGWindowListCopyWindowInfo(opts, Quartz.kCGNullWindowID) or []
    result = []
    for w in wins:
        if w.get("kCGWindowLayer", 99) != 0:
            continue
        if args.pid is not None and w.get("kCGWindowOwnerPID") != args.pid:
            continue
        b = w.get("kCGWindowBounds", {})
        result.append({
            "window_id": w.get("kCGWindowNumber"),
            "pid": w.get("kCGWindowOwnerPID"),
            "owner": w.get("kCGWindowOwnerName"),
            "title": w.get("kCGWindowName"),
            "layer": w.get("kCGWindowLayer", 0),
            "x": int(b.get("X", 0)), "y": int(b.get("Y", 0)),
            "w": int(b.get("Width", 0)), "h": int(b.get("Height", 0)),
        })
    out(dict(ok=True, windows=result))


def cmd_open(args):
    if args.bundle_id:
        target, cmd, via = args.bundle_id, ["open", "-b", args.bundle_id], "bundle-id"
    elif args.url:
        target, cmd, via = args.url, ["open", args.url], "url"
    elif args.app:
        target, cmd, via = args.app, ["open", "-a", args.app], "name"
    else:
        fail("open 需要 app 名、--bundle-id 或 --url 之一")
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        fail(f"open failed: {r.stderr.strip()}")
    time.sleep(args.settle / 1000.0)
    app = NSWorkspace.sharedWorkspace().frontmostApplication()
    out(dict(ok=True, opened=target, via=via,
             frontmost=app.localizedName() if app else None))


def cmd_wait(args):
    time.sleep(args.ms / 1000.0)
    out(dict(ok=True, waited_ms=args.ms))


def cmd_clipboard(args):
    if args.action == "get":
        text = subprocess.run(["pbpaste"], capture_output=True, timeout=5).stdout
        out(dict(ok=True, text=text.decode("utf-8", "replace")))
    else:
        r = subprocess.run(["pbcopy"], input=args.text.encode(), timeout=5)
        out(dict(ok=True, set=True, r=r.returncode))


# ---------------------------------------------------------------- OCR (Vision)

def cmd_ocr(args):
    import Vision
    from Vision import VNImageRequestHandler, VNRecognizeTextRequest
    from Foundation import NSURL
    path = args.path or (load_meta() or {}).get("path")
    if not path or not os.path.exists(path):
        fail(f"image not found: {path}")
    handler = VNImageRequestHandler.alloc().initWithURL_options_(
        NSURL.fileURLWithPath_(path), None)
    req = VNRecognizeTextRequest.alloc().init()
    req.setRecognitionLevel_(getattr(Vision, "VNRequestTextRecognitionLevelAccurate", "accurate"))
    req.setRecognitionLanguages_(args.lang.split(","))
    req.setUsesLanguageCorrection_(True)
    ok, err = handler.performRequests_error_([req], None)
    if not ok:
        fail(f"Vision OCR failed: {err}")
    pw, ph = png_size(path)
    results = []
    for obs in req.results() or []:
        cand = obs.topCandidates_(1)
        if not cand:
            continue
        c = cand[0]
        text = c.string
        conf = c.confidence
        if callable(text):
            text = text()
        if callable(conf):
            conf = conf()
        bb = obs.boundingBox()  # normalized, origin bottom-left
        results.append({
            "text": text,
            "confidence": round(float(conf), 3),
            "x": int(bb.origin.x * pw),
            "y": int((1 - bb.origin.y - bb.size.height) * ph),
            "w": int(bb.size.width * pw),
            "h": int(bb.size.height * ph),
        })
    results.sort(key=lambda r: (r["y"], r["x"]))
    out(dict(ok=True, image=path, pixel_w=pw, pixel_h=ph, lines=results))


# ---------------------------------------------------------------- accessibility (AX)
#
# 语义通道：AXUIElement 读树 + 语义动作，后台安全（不动真实鼠标、不抢焦点）。
# 元素用路径句柄引用：w0.1.3 = 窗口 0 下的子节点下标链；m0.* = 菜单栏。
# 新鲜度契约：tree/find 把 (path → role+title) 存进快照，动作命令重新解析路径并
# 校验签名，不一致 fail-closed 返回 code:"stale"。

AX_META_PATH = os.path.join(META_DIR, "last-ax-snapshot.json")

AX_HINTS = {
    "stale": "UI 可能已变化，重新 ax tree",
    "no-action": "该元素不支持此动作；用 ax attr 查看它声明的动作",
    "not-found": "路径无法解析，重新 ax tree",
    "permission": "辅助功能权限缺失或宿主未重启，运行 cu doctor",
    "unsupported": "目标应用未暴露 AX（或元素不支持该操作）",
}

# AXError → 错误码（未列出的归入 unsupported）
_AX_ERR_CODE = {
    -25202: "stale",      # kAXErrorInvalidUIElement
    -25204: "stale",      # kAXErrorCannotComplete
    -25206: "no-action",  # kAXErrorActionUnsupported
    -25201: "not-found",  # kAXErrorIllegalArgument
    -25205: "not-found",  # kAXErrorAttributeUnsupported
    -25212: "not-found",  # kAXErrorNoValue
}

# pyobjc 没包 AXValueGetValue，用 ctypes 直调（AXValueRef 指针经 objc.pyobjc_id 取）
_AX_LIB = ctypes.CDLL("/System/Library/Frameworks/ApplicationServices.framework/"
                      "ApplicationServices")
_AX_LIB.AXValueGetValue.restype = ctypes.c_bool
_AX_LIB.AXValueGetValue.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p]


def ax_fail(code, detail=None, **extra):
    payload = dict(ok=False, code=code, hint=AX_HINTS.get(code, ""))
    if detail:
        payload["error"] = detail
    payload.update(extra)
    out(payload)


def _ax_err_out(err, path, **extra):
    ax_fail(_AX_ERR_CODE.get(err, "unsupported"), detail=f"AXError {err}",
            path=path, **extra)


def _ax_value_n(v, vtype, n=2):
    buf = (ctypes.c_double * n)()
    if _AX_LIB.AXValueGetValue(ctypes.c_void_p(objc.pyobjc_id(v)), vtype, buf):
        return [round(buf[i]) for i in range(n)]
    return None


def ax_point(v):
    return _ax_value_n(v, 1)


def ax_size(v):
    return _ax_value_n(v, 2)


def ax_read(el, attr):
    """读属性 → (err, value)；失败时 value 为 None。"""
    try:
        err, val = AS.AXUIElementCopyAttributeValue(el, attr, None)
        return err, val
    except Exception:
        return -1, None


def ax_get(el, attr):
    return ax_read(el, attr)[1]


def ax_actions(el):
    """元素声明的动作列表（必须用函数 API；属性读法在很多元素上返回 -25205）。"""
    try:
        err, acts = AS.AXUIElementCopyActionNames(el, None)
    except Exception:
        return None
    return [str(a) for a in (acts or [])] if err == 0 else None


def _plain(v, limit=200):
    """AX 值 → JSON 可序列化的朴素值。"""
    if v is None:
        return None
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return v
    if isinstance(v, str):
        return v[:limit]
    if isinstance(v, (list, tuple)):
        return [_plain(x, limit) for x in v]
    try:
        t = AS.AXValueGetType(v)
        if t == 1:
            return ax_point(v)
        if t == 2:
            return ax_size(v)
        if t == 4:  # CFRange
            buf = (ctypes.c_long * 2)()
            if _AX_LIB.AXValueGetValue(ctypes.c_void_p(objc.pyobjc_id(v)), 4, buf):
                return [int(buf[0]), int(buf[1])]
    except Exception:
        pass
    role = ax_get(v, "AXRole")
    if role:  # 子元素引用 → 摘要
        t = ax_get(v, "AXTitle")
        return f"<{role} {t or ''}>".strip()
    return str(v)[:limit]


# ------------------------------------------------- app 解析与 AX 树遍历

def running_apps():
    return [a for a in NSWorkspace.sharedWorkspace().runningApplications()
            if a.activationPolicy() == 0 and a.processIdentifier() > 0]


def resolve_app(spec):
    """pid | bundle-id | 应用名 → NSRunningApplication；唯一才通过（fail-closed）。"""
    apps = running_apps()
    if str(spec).lstrip("-").isdigit():
        pid = int(spec)
        for a in apps:
            if a.processIdentifier() == pid:
                return a
        ax_fail("not-found", detail=f"没有 pid 为 {pid} 的 GUI 应用",
                hint="cu apps 查看运行中的应用")
    low = str(spec).lower()
    if "." in spec:
        hits = [a for a in apps if (a.bundleIdentifier() or "").lower() == low]
        if hits:
            return hits[0]
    def _app_names(a):
        vals = {a.localizedName() or ""}
        try:
            bp = a.bundleURL().lastPathComponent() or ""
            if bp.endswith(".app"):
                bp = bp[:-4]
            vals.add(bp)
        except Exception:
            pass
        try:
            vals.add(a.executableName() or "")
        except AttributeError:
            pass
        return {v.lower() for v in vals if v}

    by_name = [(a, n) for a in apps for n in _app_names(a)]
    for match in (lambda n: n == low, lambda n: n.startswith(low), lambda n: low in n):
        hits = [a for a, n in by_name if match(n)]
        if len(hits) == 1:
            return hits[0]
        if len(hits) > 1:
            ax_fail("not-found", detail="应用名匹配到多个："
                    + ", ".join(f"{a.localizedName()}({a.processIdentifier()})"
                                for a in hits[:6]),
                    hint="用 pid 或 bundle id 精确指定")
    ax_fail("not-found", detail=f"没有运行中的应用匹配 {spec}",
            hint="cu apps 查看运行中的应用")


def app_element(pid):
    return AS.AXUIElementCreateApplication(pid)


def app_windows(el, boost=True):
    err, wins = ax_read(el, "AXWindows")
    if (err != 0 or not wins) and boost:
        # Chromium/Electron 默认不生成 AX 树，公开 setter 打开后再试（ZCode 同款手法）
        try:
            AS.AXUIElementSetAttributeValue(el, "AXManualAccessibility", True)
        except Exception:
            pass
        time.sleep(0.5)
        err, wins = ax_read(el, "AXWindows")
    return list(wins) if err == 0 and wins else []


def _norm_role(x):
    x = (x or "").lower().strip()
    return x[2:] if x.startswith("ax") else x


def walk_tree(app_el, max_depth=10, max_nodes=300, role_spec=None, want_all=False):
    """DFS 读 AX 树（窗口 + 菜单栏）。返回 nodes/sig/focus_path/truncated。"""
    wins = app_windows(app_el)
    roots = [(f"w{i}", w) for i, w in enumerate(wins)]
    err, menubar = ax_read(app_el, "AXMenuBar")
    if err == 0 and menubar:
        roots.append(("m0", menubar))
    err, focus_el = ax_read(app_el, "AXFocusedUIElement")
    focus_el = focus_el if err == 0 else None

    role_filter = None
    if role_spec:
        role_filter = {_norm_role(w) for w in role_spec.split(",") if w.strip()}

    nodes, sig = [], {}
    st = {"out": 0, "visited": 0, "truncated": False, "focus_path": None}
    cap_nodes = 10 ** 9 if want_all else max_nodes
    cap_visited = 10 ** 9 if want_all else max(1500, max_nodes * 6)

    def visit(path, el, depth):
        if st["out"] >= cap_nodes or st["visited"] >= cap_visited:
            st["truncated"] = True
            return
        st["visited"] += 1
        role = ax_get(el, "AXRole")
        if role is None:
            return
        if focus_el is not None and CFEqual(focus_el, el):
            st["focus_path"] = path
        title = ax_get(el, "AXTitle")
        value = ax_get(el, "AXValue")
        desc = ax_get(el, "AXDescription")   # 自绘 app（如 QQ音乐）把可读标签放在这里
        help_ = ax_get(el, "AXHelp")
        # 快照记录所有可读节点（与 --role 输出过滤解耦），
        # 保证未出现在过滤输出里的路径不会因快照缺签而失效
        sig[path] = [role, title if isinstance(title, str) else None]
        if role_filter is None or _norm_role(role) in role_filter:
            node = {"p": path, "role": role}
            if isinstance(title, str) and title:
                node["title"] = title[:80]
            if isinstance(desc, str) and desc and desc != title:
                node["desc"] = desc[:80]
            if isinstance(help_, str) and help_:
                node["help"] = help_[:60]
            if value is not None:
                p = _plain(value, 120)
                if p is not None and p != "" and p != []:
                    node["value"] = p
            pos = ax_get(el, "AXPosition")
            if pos is not None:
                node["pos"] = ax_point(pos)
            size = ax_get(el, "AXSize")
            if size is not None:
                node["size"] = ax_size(size)
            acts = ax_actions(el)
            if acts:
                node["acts"] = acts[:4]
            err_s, sett = AS.AXUIElementIsAttributeSettable(el, "AXValue", None)
            if err_s == 0 and sett:
                node["editable"] = True
            nodes.append(node)
            st["out"] += 1
        if depth < max_depth:
            kids = ax_get(el, "AXChildren")
            for j, k in enumerate(kids or []):
                visit(f"{path}.{j}", k, depth + 1)
                if st["out"] >= cap_nodes or st["visited"] >= cap_visited:
                    st["truncated"] = True
                    break

    for path, root in roots:
        visit(path, root, 0)
    return {"nodes": nodes, "sig": sig, "focus_path": st["focus_path"],
            "truncated": st["truncated"]}


def _webarea_skeleton(res):
    """WebArea 存在但其下记录到的子节点 < 5 → 空壳（Chromium 惰性建树）。"""
    roles = {p: v[0] for p, v in (res.get("sig") or {}).items()}
    for p, r in roles.items():
        if r == "AXWebArea" and sum(1 for q in roles if q.startswith(p + ".")) < 5:
            return True
    return False


def _walk_with_web_retry(app_el, depth, max_nodes, role_spec, want_all):
    """walk + WebArea 空壳重试：页面刚加载时 WebArea 先出现、内容后填充，
    重试至多 2 次（每次等 1.5s），避免 agent 拿到空树就误判「页面无内容」。"""
    res = walk_tree(app_el, depth, max_nodes, role_spec, want_all)
    retried = 0
    while retried < 2 and _webarea_skeleton(res):
        time.sleep(1.5)
        retried += 1
        res = walk_tree(app_el, depth, max_nodes, role_spec, want_all)
    return res, retried


def save_ax_snapshot(app_info, sig, handles=None):
    os.makedirs(META_DIR, exist_ok=True)
    tmp = AX_META_PATH + ".tmp"
    with open(tmp, "w") as f:
        json.dump({"app": app_info, "sig": sig, "handles": handles or {},
                   "ts": time.time()}, f, ensure_ascii=False)
    os.replace(tmp, AX_META_PATH)


def load_ax_snapshot():
    try:
        with open(AX_META_PATH) as f:
            return json.load(f)
    except FileNotFoundError:
        return None


def _app_info(a):
    return {"pid": a.processIdentifier(), "name": a.localizedName(),
            "bundle_id": a.bundleIdentifier()}


# ------------------------------------------------- ax state（原生式优先级检索）
#
# get_app_state 式：BFS + 交互角色优先 + 时间预算。每节点只读便宜属性
# （role/title/desc/value/children），命中元素按交互优先级排序输出编号句柄 [i]，
# 后续 ax press/set/attr/focus/action/select 可直接用数字引用（快照存 index→path
# 映射）。解决大页面（B 站级 DOM，1000+ 节点）上 find 全树遍历"够不到/超时"。

_STATE_INTERACTIVE = {"button", "link", "radiobutton", "checkbox", "menuitem",
                      "menubaritem", "popupbutton"}
_STATE_ENTRY = {"textfield", "textarea", "searchfield", "combobox", "slider",
                "incrementor"}


def _state_class(nrole, has_text):
    """输出优先级：0 可按压交互 > 1 文本输入 > 2 纯文本叶子 > 3 带文本次要
    > 4 空容器（不输出，但子树照常遍历）。"""
    if nrole in _STATE_INTERACTIVE:
        return 0
    if nrole in _STATE_ENTRY:
        return 1
    if nrole in ("statictext", "heading"):
        return 2
    return 3 if has_text else 4


def walk_state(app_el, timeout_s=10.0, top_n=200, text=None, role_spec=None):
    t_deadline = (time.monotonic() + timeout_s) if timeout_s and timeout_s > 0 else None
    wins = app_windows(app_el)
    err_m, menubar = ax_read(app_el, "AXMenuBar")
    err_f, focus_el = ax_read(app_el, "AXFocusedUIElement")
    focus_el = focus_el if err_f == 0 else None

    win_meta = []
    for i, w in enumerate(wins):
        t = ax_get(w, "AXTitle")
        pos, size = ax_get(w, "AXPosition"), ax_get(w, "AXSize")
        win_meta.append({"p": f"w{i}", "title": t if isinstance(t, str) else None,
                         "pos": ax_point(pos) if pos is not None else None,
                         "size": ax_size(size) if size is not None else None})

    role_filter = None
    if role_spec:
        role_filter = {_norm_role(w) for w in role_spec.split(",") if w.strip()}
    t_text = (text or "").lower()

    sig, cand = {}, []
    st = {"walked": 0, "budget_hit": False, "focus_path": None}
    queue = [(f"w{i}", w) for i, w in enumerate(wins)]
    if err_m == 0 and menubar:
        queue.append(("m0", menubar))
    qi = 0
    while qi < len(queue):
        if t_deadline is not None and qi % 8 == 0 and time.monotonic() > t_deadline:
            st["budget_hit"] = True
            break
        if st["walked"] >= 50000:   # 无预算模式下的兜底上限
            st["budget_hit"] = True
            break
        path, el = queue[qi]
        qi += 1
        st["walked"] += 1
        role = ax_get(el, "AXRole")
        if role is None:
            continue
        nrole = _norm_role(role)
        title = ax_get(el, "AXTitle")
        sig[path] = [role, title if isinstance(title, str) else None]
        if focus_el is not None and CFEqual(focus_el, el):
            st["focus_path"] = path
        desc = ax_get(el, "AXDescription")
        value = ax_get(el, "AXValue")
        kids = ax_get(el, "AXChildren")
        if kids:
            for j, k in enumerate(kids):
                queue.append((f"{path}.{j}", k))
        node = {"p": path, "role": role}
        name = title if isinstance(title, str) and title else \
            (desc if isinstance(desc, str) and desc else None)
        if name:
            node["name"] = name[:80]
        if isinstance(desc, str) and desc and desc != name:
            node["desc"] = desc[:80]
        if value is not None:
            pv = _plain(value, 120)
            if pv is not None and pv != "" and pv != []:
                node["value"] = pv
        cls = 0
        if role_filter is not None:
            if nrole not in role_filter:
                continue
        else:
            cls = _state_class(nrole, bool(name or node.get("value")))
            if cls >= 4:
                continue
            if cls <= 1:  # 交互/输入元素：隐藏实例（0×0，网页常驻同名副本）不占编号
                szv = ax_get(el, "AXSize")
                if szv is not None:
                    s = ax_size(szv)
                    if s == [0, 0]:
                        continue
                    node["size"] = s
        if t_text:
            hay = " ".join(filter(None, (node.get("name"), node.get("desc"),
                                         str(node.get("value") or "")))).lower()
            if t_text not in hay:
                continue
        cand.append((el, node, cls))

    # 稳定排序：同优先级保持 BFS 文档序；焦点元素置顶
    cand.sort(key=lambda x: (0 if x[1]["p"] == st["focus_path"] else x[2]))
    chosen = cand[:top_n] if top_n and top_n > 0 else cand

    elements, handles = [], {}
    for i, (el, node, _cls) in enumerate(chosen):
        node["i"] = i
        hmeta = {"p": node["p"]}
        handles[str(i)] = hmeta
        flags = ["focused"] if node["p"] == st["focus_path"] else []
        # 修饰读（actions/settable/enabled/pos/size）只对入选元素做，且受预算约束；
        # pos/size 同时进编号句柄元数据，供动作解析时复核元素是否被换掉
        if t_deadline is None or time.monotonic() <= t_deadline:
            acts = ax_actions(el) or []
            if "AXPress" in acts or _norm_role(node["role"]) in _STATE_INTERACTIVE:
                flags.append("pressable")
            if "AXShowMenu" in acts:
                flags.append("has_menu")
            err_s, sett = AS.AXUIElementIsAttributeSettable(el, "AXValue", None)
            if err_s == 0 and sett:
                flags.append("editable")
            err_e, ena = ax_read(el, "AXEnabled")
            if err_e == 0 and ena is False:
                flags.append("disabled")
            pos = ax_get(el, "AXPosition")
            if pos is not None:
                pv = ax_point(pos)
                node["pos"] = pv
                hmeta["pos"] = pv
            if "size" not in node:
                size = ax_get(el, "AXSize")
                if size is not None:
                    node["size"] = ax_size(size)
            if "size" in node:
                hmeta["size"] = node["size"]
        if flags:
            node["flags"] = flags
        elements.append(node)
    return {"elements": elements, "sig": sig, "handles": handles,
            "windows": win_meta, "focus_path": st["focus_path"],
            "walked": st["walked"], "budget_hit": st["budget_hit"],
            "candidates": len(cand)}


def cmd_ax_state(args):
    app = resolve_app(args.app)
    info = _app_info(app)
    res = walk_state(app_element(app.processIdentifier()),
                     args.timeout, args.top, args.text, args.role)
    save_ax_snapshot(info, res["sig"], res["handles"])
    payload = dict(ok=True, app=info, windows=res["windows"],
                   elements=res["elements"], count=len(res["elements"]),
                   walked=res["walked"], budget_hit=res["budget_hit"],
                   focus=res["focus_path"])
    if res["budget_hit"]:
        payload["note"] = ("时间预算内未走完整棵树（budget_hit=true）：交互元素优先"
                           "返回，深层节点可能遗漏；需要更全时 --timeout 调大重跑")
    elif not res["elements"]:
        payload["note"] = "没有可输出的元素（无窗口或全是空容器）；ax tree 看原始树"
    out(payload)


def resolve_path(path):
    """路径句柄（w0.1.3 / m0.2.0 / ax state 编号）→ (element, app_info, role, verified)。
    fail-closed：not-found / stale。"""
    snap = load_ax_snapshot()
    if not snap:
        ax_fail("not-found", detail="还没有 ax 快照：先对目标应用执行 cu ax tree",
                hint="cu ax tree <app>")
    app_info = snap.get("app") or {}
    pid = app_info.get("pid")
    app = next((a for a in running_apps() if a.processIdentifier() == pid), None)
    if app is None:
        ax_fail("not-found", detail=f"快照中的应用已退出（pid {pid}）",
                hint="cu ax tree <app> 重新 dump")
    path = str(path)
    hmeta = None
    if path.isdigit():  # ax state 编号句柄 → 结构路径（附 pos/size 复核元数据）
        h = (snap.get("handles") or {}).get(path)
        if not h:
            ax_fail("not-found", path=path,
                    detail=f"编号 {path} 不在最近一次快照的编号表里",
                    hint="编号绑定最近一次 ax state 输出；重新 cu ax state 获取")
        if isinstance(h, dict):
            path, hmeta = h.get("p") or "", h
        else:
            path = h
    parts = path.split(".")
    if not re.fullmatch(r"[wm]\d+", parts[0].lower()) or \
            not all(s.isdigit() for s in parts[1:]):
        ax_fail("not-found", detail=f"路径格式不合法：{path}（应为 w0.1.3 或 m0.2.0）")
    el = app_element(pid)
    head = parts[0].lower()
    if head[0] == "w":
        wins = app_windows(el)
        idx = int(head[1:])
        if idx >= len(wins):
            ax_fail("stale", path=path,
                    detail=f"窗口 w{idx} 不存在（现有 {len(wins)} 个窗口）")
        cur = wins[idx]
    else:
        err, mb = ax_read(el, "AXMenuBar")
        if err != 0 or not mb:
            ax_fail("stale", path=path, detail="菜单栏不可读")
        if int(head[1:]) > 0:
            ax_fail("not-found", detail=f"菜单栏只有 m0：{path}")
        cur = mb
    for seg in parts[1:]:
        kids = ax_get(cur, "AXChildren")
        i = int(seg)
        if not kids or i >= len(kids):
            ax_fail("stale", path=path, detail=f"路径 {path} 在当前 UI 中已不存在")
        cur = kids[i]
    # 新鲜度契约：与快照记录的 role+title 比对
    role = ax_get(cur, "AXRole")
    title = ax_get(cur, "AXTitle")
    sig = (snap.get("sig") or {}).get(path)
    if sig is None:
        ax_fail("not-found", path=path,
                detail=f"路径 {path} 不在最近一次 ax tree 输出里",
                hint="重新 cu ax tree 并使用新输出的路径")
    cur_title = title if isinstance(title, str) else None
    if role != sig[0] or cur_title != sig[1]:
        ax_fail("stale", path=path,
                detail=f"元素已变化：快照 {sig[0]}/{sig[1]!r} ≠ 当前 {role}/{cur_title!r}")
    if hmeta and hmeta.get("pos") and hmeta.get("size"):
        # 动态网页 DOM 会重排：路径可能漂到另一个同名节点。pos/size 复核把
        # "静默按错元素"转成显式 stale（±2pt 容差吸收取整抖动）。
        lpos, lsize = ax_get(cur, "AXPosition"), ax_get(cur, "AXSize")
        lp = ax_point(lpos) if lpos is not None else None
        ls = ax_size(lsize) if lsize is not None else None
        if lp is None or ls is None or \
                any(abs(a - b) > 2 for a, b in zip(lp, hmeta["pos"])) or \
                any(abs(a - b) > 2 for a, b in zip(ls, hmeta["size"])):
            ax_fail("stale", path=path,
                    detail=f"编号指向的元素已移动/隐藏：快照 pos{hmeta['pos']} "
                           f"size{hmeta['size']} ≠ 当前 pos{lp} size{ls}",
                    hint="动态网页 DOM 会重排：重新 cu ax state 获取新编号")
    return cur, app_info, role, True


# ------------------------------------------------- ax 命令

def cmd_ax_tree(args):
    app = resolve_app(args.app)
    info = _app_info(app)
    res, retried = _walk_with_web_retry(app_element(app.processIdentifier()),
                                        args.depth, args.max, args.role, args.all)
    save_ax_snapshot(info, res["sig"])
    payload = dict(ok=True, app=info, nodes=res["nodes"], focus=res["focus_path"],
                   truncated=res["truncated"])
    if retried:
        payload["retried"] = retried
    if not res["nodes"]:
        payload["note"] = "该应用未暴露可读的 AX 树（无窗口或元素不可读）"
    out(payload)


def cmd_ax_find(args):
    if not (args.text or args.title or args.role):
        fail("ax find 需要 --text / --title / --role 至少一个")
    app = resolve_app(args.app)
    info = _app_info(app)
    res, retried = _walk_with_web_retry(app_element(app.processIdentifier()),
                                        args.depth, args.max, args.role, False)
    t = (args.text or "").lower()
    ti = (args.title or "").lower()
    matches = []
    for n in res["nodes"]:
        # --text/--title 同时匹配 title/desc/help：自绘 app 的标签在 description 里
        hay = " ".join(filter(None, (n.get("title"), n.get("desc"),
                                     n.get("help")))).lower()
        if t and not (t in hay or t in str(n.get("value") or "").lower()):
            continue
        if ti and ti not in hay:
            continue
        matches.append(n)
    save_ax_snapshot(info, res["sig"])
    if args.first:
        matches = matches[:1]
    payload = dict(ok=True, app=info, count=len(matches), matches=matches,
                   focus=res["focus_path"], truncated=res["truncated"])
    if retried:
        payload["retried"] = retried
    out(payload)


def cmd_ax_press(args):
    el, app, role, _ = resolve_path(args.path)
    acts = ax_actions(el)
    if acts is None:
        acts = []
    if acts and "AXPress" not in acts:
        # 落空引导：元素有几何信息时给出坐标/键盘替代路径（自绘 app 常吞合成鼠标）
        extra = {"hint": "改用 ax action 指定元素声明的动作，或用键盘输入"}
        pos = ax_get(el, "AXPosition")
        if pos is not None:
            extra["pos"] = ax_point(pos)
            extra["hint"] = ("该元素不声明 AXPress：可 click --mode pts 点其 pos（自绘 app "
                             "可能忽略合成鼠标事件，此时改用键盘 key/type --app）")
        ax_fail("no-action", path=args.path,
                detail=f"{role} 声明的动作：{acts}", **extra)
    err = AS.AXUIElementPerformAction(el, "AXPress")
    if err != 0:
        extra = {"hint": ("AXPress 失败：自绘 app 可能忽略合成事件——改用键盘 key/type"
                          " --app，或 click --mode pts 点元素 pos")}
        pos = ax_get(el, "AXPosition")
        if pos is not None:
            extra["pos"] = ax_point(pos)
        _ax_err_out(err, args.path, **extra)
    out(dict(ok=True, acted="AXPress", path=args.path, role=role, app=app))


def cmd_ax_action(args):
    el, app, role, _ = resolve_path(args.path)
    acts = ax_actions(el) or []
    if args.name not in acts:
        ax_fail("no-action", path=args.path,
                detail=f"{role} 声明的动作：{acts or '（无）'}")
    err = AS.AXUIElementPerformAction(el, args.name)
    if err != 0:
        _ax_err_out(err, args.path)
    out(dict(ok=True, acted=args.name, path=args.path, role=role, app=app))


def cmd_ax_set(args):
    el, app, role, _ = resolve_path(args.path)
    err_s, sett = AS.AXUIElementIsAttributeSettable(el, "AXValue", None)
    if err_s != 0:
        _ax_err_out(err_s, args.path)
    if not sett:
        ax_fail("unsupported", path=args.path,
                detail=f"{role} 的 AXValue 不可直接写",
                hint="改用 ax focus + type --paste，或对按钮类元素 ax press")
    err = AS.AXUIElementSetAttributeValue(el, "AXValue", args.value)
    if err != 0:
        try:
            num = int(args.value)
        except ValueError:
            try:
                num = float(args.value)
            except ValueError:
                num = None
        if num is None or AS.AXUIElementSetAttributeValue(el, "AXValue", num) != 0:
            _ax_err_out(err, args.path)
    out(dict(ok=True, set="AXValue", path=args.path, value=args.value,
             role=role, app=app))


def cmd_ax_attr(args):
    el, app, role, _ = resolve_path(args.path)
    if args.name:
        err, val = ax_read(el, args.name)
        if err != 0:
            _ax_err_out(err, args.path, attribute=args.name)
        out(dict(ok=True, path=args.path, role=role, name=args.name,
                 value=_plain(val, 100000), app=app))
        return
    err, names = AS.AXUIElementCopyAttributeNames(el, None)
    if err != 0:
        _ax_err_out(err, args.path)
    attrs = {}
    for n in list(names or [])[:30]:
        err, val = ax_read(el, n)
        if err == 0:
            p = _plain(val)
            if p is not None and p != "" and p != []:
                attrs[n] = p
    out(dict(ok=True, path=args.path, role=role, attrs=attrs, app=app))


def cmd_ax_select(args):
    el, app, role, _ = resolve_path(args.path)
    start, length = args.range
    v = AS.AXValueCreate(4, CFRange(int(start), int(length)))
    err = AS.AXUIElementSetAttributeValue(el, "AXSelectedTextRange", v)
    if err != 0:
        _ax_err_out(err, args.path)
    out(dict(ok=True, selected=[start, length], path=args.path, role=role, app=app))


def cmd_ax_focus(args):
    el, app, role, _ = resolve_path(args.path)
    err = AS.AXUIElementSetAttributeValue(el, "AXFocused", True)
    if err != 0:
        _ax_err_out(err, args.path)
    payload = dict(ok=True, focused=args.path, role=role, app=app,
                   app_active=bool(app.get("pid") and _is_app_active(app["pid"])))
    if not payload["app_active"]:
        payload["note"] = "应用未激活：type/key 类输入动作前先 cu open 激活"
    out(payload)


def _is_app_active(pid):
    for a in running_apps():
        if a.processIdentifier() == pid:
            return a.isActive()
    return False


def cmd_apps(args):
    apps = [{"pid": a.processIdentifier(), "name": a.localizedName(),
             "bundle_id": a.bundleIdentifier(), "frontmost": bool(a.isActive()),
             "hidden": bool(a.isHidden())} for a in running_apps()]
    apps.sort(key=lambda x: (not x["frontmost"], (x["name"] or "").lower()))
    out(dict(ok=True, count=len(apps), apps=apps))


# ---------------------------------------------------------------- CLI

def main():
    p = argparse.ArgumentParser(prog="cu", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("doctor", help="check accessibility / screen recording permissions")
    sub.add_parser("displays", help="list displays with bounds")

    sp = sub.add_parser("screenshot", help="capture a display (writes coord meta)")
    sp.add_argument("--display", type=int, default=None, help="display index (1-based)")
    sp.add_argument("--out", default=None, help="output png path")
    sp.add_argument("--cursor", action="store_true", help="include mouse cursor")
    sp.add_argument("--window", type=int, default=None,
                    help="capture a specific window by id (from `cu windows`)")
    sp.add_argument("--region-px", nargs=4, type=int, metavar=("X", "Y", "W", "H"),
                    help="crop region in last-screenshot pixels (or points with --pts)")
    sp.add_argument("--pts", action="store_true",
                    help="treat --region-px values as screen points instead of image pixels")

    sp = sub.add_parser("click")
    sp.add_argument("x", type=int); sp.add_argument("y", type=int)
    sp.add_argument("--mode", choices=("image", "pts", "norm"), default="image")
    sp.add_argument("--button", choices=("left", "right", "middle"), default="left")
    sp.add_argument("--count", type=int, default=1, help="1 single, 2 double, 3 triple")
    sp.add_argument("--down", action="store_true",
                    help="press and hold (release later with --up)")
    sp.add_argument("--up", action="store_true", help="release a held press")

    sp = sub.add_parser("move")
    sp.add_argument("x", type=int); sp.add_argument("y", type=int)
    sp.add_argument("--mode", choices=("image", "pts", "norm"), default="image")

    sp = sub.add_parser("drag")
    sp.add_argument("x1", type=int); sp.add_argument("y1", type=int)
    sp.add_argument("x2", type=int); sp.add_argument("y2", type=int)
    sp.add_argument("--mode", choices=("image", "pts", "norm"), default="image")
    sp.add_argument("--duration", type=int, default=400, help="ms")
    sp.add_argument("--button", choices=("left", "right", "middle"), default="left")

    sp = sub.add_parser("scroll")
    sp.add_argument("x", type=int, nargs="?", default=None)
    sp.add_argument("y", type=int, nargs="?", default=None)
    sp.add_argument("--mode", choices=("image", "pts", "norm"), default="image")
    sp.add_argument("--down", type=int, default=0); sp.add_argument("--up", type=int, default=0)
    sp.add_argument("--left", type=int, default=0); sp.add_argument("--right", type=int, default=0)

    sub.add_parser("position", help="current cursor position (screen points)")

    sp = sub.add_parser("key", help='press combo, e.g. `key cmd+c` `key cmd+shift+t`')
    sp.add_argument("keys", nargs="+", help="e.g. return esc cmd+c")
    sp.add_argument("--repeat", type=int, default=1)
    sp.add_argument("--hold", type=int, default=None,
                    help="ms to hold each combo down (down → sleep → up)")
    sp.add_argument("--app", default=None,
                    help="pid | bundle-id | app name: 后台直投键盘到该进程"
                         "（不抢焦点；输出 channel=pid）")

    sp = sub.add_parser("type", help="type unicode text (supports 中文)")
    sp.add_argument("text")
    sp.add_argument("--repeat", type=int, default=1)
    sp.add_argument("--press-enter", action="store_true")
    sp.add_argument("--paste", action="store_true",
                    help="clipboard relay: write clipboard + cmd+v (long text "
                         "preferred); original text clipboard is restored after")
    sp.add_argument("--app", default=None,
                    help="pid | bundle-id | app name: 后台直投键盘到该进程"
                         "（不抢焦点；输出 channel=pid）")

    sp = sub.add_parser("holdkey", help="hold a single key, e.g. `holdkey w --duration 2000`")
    sp.add_argument("key", help="single key name (letter/digit/f-key)")
    sp.add_argument("--duration", type=int, default=1000, help="ms to hold")

    sp = sub.add_parser("open", help="launch/activate app (by name, --bundle-id or --url)")
    sp.add_argument("app", nargs="?", default=None)
    sp.add_argument("--bundle-id", default=None, help="e.g. com.apple.TextEdit")
    sp.add_argument("--url", default=None, help="open a URL with the default handler")
    sp.add_argument("--settle", type=int, default=1200, help="ms to wait for launch")

    sp = sub.add_parser("clipboard")
    sp.add_argument("action", choices=("get", "set"))
    sp.add_argument("text", nargs="?", default=None)

    sp = sub.add_parser("ocr", help="Vision OCR of a screenshot (default: last one)")
    sp.add_argument("--path", default=None)
    sp.add_argument("--lang", default="en-US,zh-Hans")

    sp = sub.add_parser("windows", help="list on-screen windows (bounds in points)")
    sp.add_argument("--pid", type=int, default=None, help="only windows of this pid")

    sub.add_parser("apps", help="running GUI apps (pid/bundle id/name/frontmost)")
    sub.add_parser("frontmost", help="name/bundle id/pid of the frontmost application")

    axp = sub.add_parser("ax", help="accessibility tree: semantic observe & act "
                                    "(background-safe, no mouse/focus steal)")
    axsub = axp.add_subparsers(dest="ax_cmd", required=True)

    sp = axsub.add_parser("tree", help="dump AX tree (writes handle snapshot)")
    sp.add_argument("app", help="pid | bundle-id | app name")
    sp.add_argument("--depth", type=int, default=10)
    sp.add_argument("--max", type=int, default=300, help="node budget")
    sp.add_argument("--role", default=None, help="comma-separated roles, e.g. button,textfield")
    sp.add_argument("--all", action="store_true", help="no budget (slow)")

    sp = axsub.add_parser("find", help="search nodes by --text / --title / --role")
    sp.add_argument("app")
    sp.add_argument("--text", default=None, help="substring of title or value")
    sp.add_argument("--title", default=None, help="substring of title")
    sp.add_argument("--role", default=None)
    sp.add_argument("--first", action="store_true", help="only the first match")
    sp.add_argument("--depth", type=int, default=10)
    sp.add_argument("--max", type=int, default=600)

    sp = axsub.add_parser("state", help="priority-ranked element list with numbered "
                                        "handles (time-budgeted, large-page friendly)")
    sp.add_argument("app")
    sp.add_argument("--text", default=None, help="substring of name/desc/value")
    sp.add_argument("--role", default=None, help="comma-separated roles")
    sp.add_argument("--top", type=int, default=200, help="max elements returned")
    sp.add_argument("--timeout", type=float, default=10.0,
                    help="walk budget in seconds (0 = unlimited)")

    sp = axsub.add_parser("press", help="AXPress (background-safe click)")
    sp.add_argument("path", help="handle from ax tree/find/state, e.g. w0.1.3 or 42")
    sp = axsub.add_parser("focus", help="set keyboard focus on the element")
    sp.add_argument("path")
    sp = axsub.add_parser("attr", help="read element attributes")
    sp.add_argument("path")
    sp.add_argument("--name", default=None, help="single attribute (default: list all)")

    sp = axsub.add_parser("set", help="write AXValue (semantic set_value)")
    sp.add_argument("path")
    sp.add_argument("--value", required=True)

    sp = axsub.add_parser("action", help="perform a named AX action, e.g. AXOpen")
    sp.add_argument("path")
    sp.add_argument("--name", required=True, help="one of the element's acts")

    sp = axsub.add_parser("select", help="set selected text range")
    sp.add_argument("path")
    sp.add_argument("--range", nargs=2, type=int, metavar=("START", "LEN"), required=True)

    sp = sub.add_parser("wait")
    sp.add_argument("ms", type=int)

    args = p.parse_args()
    if args.cmd == "ax":
        fn = globals().get(f"cmd_ax_{args.ax_cmd}")
    else:
        fn = globals().get(f"cmd_{args.cmd}")
    if fn is None:
        fail(f"unknown command {args.cmd}")
    try:
        fn(args)
    except SystemExit:
        raise
    except Exception as e:
        fail(f"{type(e).__name__}: {e}")


if __name__ == "__main__":
    main()
