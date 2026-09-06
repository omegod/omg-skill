#!/usr/bin/env python3
"""Self-driving end-to-end test for cu.py — closed vision loop, no human input.

Flow: screenshot → open TextEdit (verify frontmost + real doc window, not the
iCloud browser) → click via window bounds → type → OCR-verify → OCR-guided
drag select → cmd+c → clipboard-verify → multi-line scroll → select-all copy
→ cleanup.

Run with a python that has pyobjc AND a host app holding Screen Recording +
Accessibility permissions (e.g. granted Terminal):
    .venv/bin/python scripts/e2e_test.py
"""
import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))

CU = os.path.join(HERE, "cu.py")
LOG = []
FAILED = []
ORIGINAL_CLIP = ""
TE_OWNER_HINTS = ("textedit", "文本编辑")
BROWSER_TITLE_HINTS = ("文本编辑", "textedit", "icloud")


def cu(*args, timeout=30):
    r = subprocess.run([sys.executable, CU, *args], capture_output=True, text=True,
                       timeout=timeout)
    try:
        return json.loads(r.stdout)
    except json.JSONDecodeError:
        return {"ok": False, "error": f"bad output: {r.stdout!r} {r.stderr!r}"}


def step(name, ok, detail=""):
    LOG.append({"step": name, "ok": bool(ok), "detail": str(detail)[:300]})
    print(f"[{'PASS' if ok else 'FAIL'}] {name} {str(detail)[:200]}", flush=True)
    if not ok:
        FAILED.append(name)
    return ok


def is_textedit_owner(w):
    owner = (w.get("owner") or "")
    return any(h in owner.lower() or h in owner for h in TE_OWNER_HINTS)


def is_doc_window(w):
    """A real TextEdit document window, NOT the iCloud document-browser panel
    (whose title is the app name / contains iCloud)."""
    if not is_textedit_owner(w) or w["w"] < 300 or w["h"] < 200:
        return False
    title = (w.get("title") or "").lower()
    return not any(h in title for h in BROWSER_TITLE_HINTS)


def frontmost_is_textedit():
    f = cu("frontmost")
    if not f.get("ok"):
        return False
    name = f.get("name") or ""
    return any(h in name.lower() or h in name for h in TE_OWNER_HINTS)


def find_doc_window():
    wins = cu("windows").get("windows", [])
    return next((w for w in wins if is_doc_window(w)), None), wins


def focus_textedit():
    """Re-activate TextEdit and raise the doc window by clicking its title bar
    (the user may have stolen focus mid-test). Re-find the window afterwards.
    Returns the fresh window dict or None."""
    for _ in range(3):
        te, _wins = find_doc_window()
        if te is None:
            return None
        cu("click", str(te["x"] + te["w"] // 2), str(te["y"] + 12), "--mode", "pts")
        time.sleep(0.3)
        te2, _wins = find_doc_window()
        if te2 and frontmost_is_textedit():
            return te2
    return None


def ensure_textedit_doc(attempts=5):
    """Activate TextEdit and cmd+n until a real document window appears.
    Returns the window dict or None."""
    te = None
    for _ in range(attempts):
        if not frontmost_is_textedit():
            cu("open", "TextEdit", "--settle", "1500")
            if not frontmost_is_textedit():
                continue
        cu("key", "cmd+n")
        time.sleep(0.8)
        te, wins = find_doc_window()
        if te:
            return te
    return None


def ocr_text():
    # ALWAYS take a fresh screenshot — ocr without --path reads the last
    # screenshot's meta, which may be stale after focus changes.
    shot = cu("screenshot", "--out", "/tmp/cu-e2e-ocr.png")
    if not shot.get("ok"):
        return False, ""
    r = cu("ocr", "--path", "/tmp/cu-e2e-ocr.png", "--lang", "zh-Hans,en-US")
    if not r.get("ok"):
        return False, ""
    return True, " ".join(line["text"] for line in r["lines"])


def find_line(ocr_json, needle):
    for line in ocr_json.get("lines", []):
        if needle.lower() in line["text"].lower():
            return line
    return None


def main():
    global ORIGINAL_CLIP
    # 0. permissions
    d = cu("doctor")
    if not d.get("ok"):
        LOG.append({"step": "doctor", "ok": False, "detail": d.get("notes")})
        finish(reason="permissions missing")
        return 1
    step("doctor", True, d["checks"])

    # 1. displays
    dd = cu("displays")
    step("displays", dd.get("ok") and len(dd.get("displays", [])) >= 1, dd.get("displays"))

    # 2. screenshot + meta sanity
    shot1 = cu("screenshot", "--out", "/tmp/cu-e2e-1.png")
    meta_ok = (shot1.get("ok") and shot1["pixel_w"] > 0
               and abs(shot1["pixel_w"] / shot1["point_w"] - shot1["scale"]) < 0.02)
    step("screenshot-meta", meta_ok, {k: shot1.get(k) for k in
                                      ("pixel_w", "pixel_h", "point_w", "point_h", "scale")})

    # 3. clipboard roundtrip (and keep original for restore)
    ORIGINAL_CLIP = cu("clipboard", "get").get("text", "")
    step("clipboard-set", cu("clipboard", "set", "CU_E2E_MARKER").get("ok"))
    step("clipboard-get", cu("clipboard", "get").get("text") == "CU_E2E_MARKER")

    # 4. fresh TextEdit with a real document window
    subprocess.run(["killall", "TextEdit"], capture_output=True)
    time.sleep(0.5)
    step("open-textedit", cu("open", "TextEdit", "--settle", "2500").get("ok"))
    te = ensure_textedit_doc()
    if not step("textedit-doc-window", te is not None, te):
        finish()
        return 1

    # 4b. cu 2.0: screenshot --window — meta origin must equal the window bounds
    sw = cu("screenshot", "--window", str(te["window_id"]), "--out", "/tmp/cu-e2e-win.png")
    okw = (sw.get("ok") and abs(sw["origin_x"] - te["x"]) <= 1
           and abs(sw["origin_y"] - te["y"]) <= 1 and sw.get("pixel_w", 0) > 0)
    step("screenshot-window", okw,
         {k: sw.get(k) for k in ("origin_x", "origin_y", "point_w", "point_h",
                                 "scale", "window_id")})

    # 5. click into the text area (screen points from window bounds)
    cx, cy = te["x"] + te["w"] // 2, te["y"] + min(int(te["h"] * 0.4), 350)
    step("click-textarea", cu("click", str(cx), str(cy), "--mode", "pts").get("ok"), (cx, cy))
    pos = cu("position")
    near = abs(pos["x"] - cx) < 5 and abs(pos["y"] - cy) < 5
    step("position-verify", near, pos)
    step("textedit-frontmost", frontmost_is_textedit(), cu("frontmost"))

    # 6. type → OCR verify (retry once via clipboard paste if OCR misses)
    step("type-text", cu("type", "computer use E2E 测试 12345").get("ok"))
    time.sleep(0.4)
    cu("screenshot", "--out", "/tmp/cu-e2e-2.png")
    ok2, txt2 = ocr_text()
    if not ("computer use e2e" in txt2.lower() and "12345" in txt2.lower()):
        te = focus_textedit()
        if te:
            cx, cy = te["x"] + te["w"] // 2, te["y"] + min(int(te["h"] * 0.4), 350)
            cu("click", str(cx), str(cy), "--mode", "pts")
            cu("key", "cmd+a")
            cu("key", "delete")
            cu("clipboard", "set", "computer use E2E 测试 12345")
            cu("key", "cmd+v")
            time.sleep(0.4)
            ok2, txt2 = ocr_text()
    step("ocr-verify-typed", ok2 and "computer use e2e" in txt2.lower() and "12345" in txt2,
         txt2[:120])

    # 7. OCR-guided drag select → copy → clipboard verify (strict: must contain
    # the typed words, otherwise the marker would false-pass)
    ocr2 = cu("ocr", "--lang", "zh-Hans,en-US")
    line = find_line(ocr2, "e2e")
    if step("ocr-line-found", line is not None, ocr2.get("lines")):
        lyc = line["y"] + line["h"] // 2
        cu("drag", str(line["x"] - 4), str(lyc),
           str(line["x"] + line["w"] + 30), str(lyc), "--duration", "500")
        cu("key", "cmd+c")
        time.sleep(0.3)
        clip = cu("clipboard", "get").get("text", "")
        step("drag-select-copy",
             clip != "CU_E2E_MARKER" and "e2e" in clip.lower(), clip[:80])
    else:
        step("drag-select-copy", False, "line not found")

    # 8. multi-line typing + scroll (sign of --down verified here)
    te = focus_textedit()
    if not step("refocus-2", te is not None, te):
        finish()
        return 1
    cx, cy = te["x"] + te["w"] // 2, te["y"] + min(int(te["h"] * 0.4), 350)
    cu("click", str(cx), str(cy), "--mode", "pts")
    cu("key", "cmd+a")
    cu("key", "delete")
    lines = "\n".join(f"LINE-{i:02d} padding" for i in range(1, 41))
    step("type-40-lines", cu("type", lines).get("ok"))
    time.sleep(0.5)
    # After typing, TextEdit's view sits at the bottom (cursor visible), so
    # verify BOTH scroll directions: up → LINE-01 appears, down → it hides
    # again and LINE-40 is back.
    cu("scroll", str(cx), str(cy), "--mode", "pts", "--up", "40")
    time.sleep(0.5)
    okA, txtA = ocr_text()
    cu("scroll", str(cx), str(cy), "--mode", "pts", "--down", "60")
    time.sleep(0.5)
    okB, txtB = ocr_text()
    step("scroll-up", okA and ("LINE-01" in txtA or "LINE-02" in txtA),
         {"up_top_visible": "LINE-01" in txtA or "LINE-02" in txtA})
    # down: bottom (LINE-40) reached AND the view differs from the top state —
    # exact wheel-notch-to-line ratio is not 1:1, so don't require LINE-01 to
    # be fully off-screen.
    step("scroll-down", okB and ("LINE-40" in txtB)
         and (("LINE-01" not in txtB) or (txtB != txtA)),
         {"down_L40_visible": "LINE-40" in txtB, "view_changed": txtB != txtA})

    # 9. select-all copy of the whole document
    te = focus_textedit()
    cx, cy = (te["x"] + te["w"] // 2, te["y"] + min(int(te["h"] * 0.4), 350)) if te else (cx, cy)
    cu("click", str(cx), str(cy), "--mode", "pts")
    cu("key", "cmd+a")
    cu("key", "cmd+c")
    time.sleep(0.3)
    whole = cu("clipboard", "get").get("text", "")
    step("cmd-a-copy", "LINE-01" in whole and "LINE-40" in whole, whole[:80])

    finish()
    return 0 if not FAILED else 1


def finish(reason=None):
    subprocess.run(["killall", "TextEdit"], capture_output=True)
    cu("clipboard", "set", ORIGINAL_CLIP)
    status = "ABORT" if reason else ("PASS" if not FAILED else "FAIL")
    result = {"e2e": status, "reason": reason,
              "passed": len(LOG) - len(FAILED), "total": len(LOG), "failed": FAILED}
    print(json.dumps(result, ensure_ascii=False))
    with open("/tmp/cu-e2e-result.json", "w") as f:
        json.dump({"result": result, "log": LOG}, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    sys.exit(main())
