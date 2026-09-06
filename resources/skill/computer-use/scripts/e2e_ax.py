#!/usr/bin/env python3
"""AX closed-loop e2e for cu.py 2.x — semantic path only, no screen recording.

Covers SPEC 2.0 §5 tests 1/2/3/5 plus ax select / key --hold / click --down/--up,
and cu 2.1 background channel (--app pid dispatch + AXDescription):
  launch TextEdit in background → ax find textarea → ax set → ax attr readback →
  mixed path (ax coords → click --mode pts with --down/--up split) → ax focus →
  menu 保存_AXPress (file content verified on disk) → 打印 dialog: AXSheet appears,
  AX-cancel dismisses it (Escape equivalent, no keystrokes into user apps) →
  关闭 (NSDocument autosave-closes silently) → stale handle fails closed →
  --paste 511 汉字逐字比对 → ax select → background typing (`type/key --app`,
  Finder 抢前台) → ax state（编号句柄 set/attr 回读 + --text 过滤 + 越界 fail-closed）
  → Chrome 大页面 state（skip-if-absent：预算内完成/交互优先/菜单 0×0 过滤）
  → QQ音乐 desc-tree + background space toggle (skip-if-absent) →
  screenshot --region-px argparse 回归 → cleanup.

实测约束（已同步 SKILL.md）：
  * 菜单项 AXPress 仅对激活态应用生效（后台回执 ok 但不执行）→ 菜单阶段先 open -a。
  * TextEdit 关闭修改过的文档 = 自动保存静默关闭，无 sheet（NSDocument 模型）。
  * key/type --app 走 CGEventPostToPid（公开 API），后台空格切换 QQ音乐 播放态已实测。
Runs under any host with Accessibility granted (Screen Recording NOT needed).
    .venv/bin/python scripts/e2e_ax.py
"""
import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
CU = os.path.join(HERE, "cu.py")
DOC = "/tmp/cu-ax-e2e.txt"
PASTE_DOC = "/tmp/cu-ax-e2e-paste.txt"
RESULT = "/tmp/cu-ax-e2e-result.json"
LOG, FAILED = [], []
PASTE_TEXT = ("计算机使用测试" * 20) + "，追加中文长文本" + ("甲乙丙丁戊己庚辛壬癸" * 36) + "END"
ORIGINAL_CLIP = ""
TE_NAMES = ("TextEdit", "文本编辑")


def cu(*args, timeout=60):
    r = subprocess.run([sys.executable, CU, *args], capture_output=True,
                       text=True, timeout=timeout)
    try:
        payload = json.loads(r.stdout)
    except json.JSONDecodeError:
        payload = {"ok": False, "error": f"bad output: {r.stdout!r} {r.stderr!r}"}
    return payload, r.returncode


def step(name, ok, detail=""):
    LOG.append({"step": name, "ok": bool(ok), "detail": str(detail)[:300]})
    print(f"[{'PASS' if ok else 'FAIL'}] {name} {str(detail)[:200]}", flush=True)
    if not ok:
        FAILED.append(name)
    return ok


def textedit_pid():
    for a in cu("apps")[0].get("apps", []):
        bid = (a.get("bundle_id") or "").lower()
        if "textedit" in bid or (a.get("name") or "") in TE_NAMES:
            return a["pid"]
    return None


def doc_windows(pid):
    if pid is None:
        return []
    return cu("windows", "--pid", str(pid))[0].get("windows", [])


def frontmost_is_textedit():
    f = cu("frontmost")[0]
    return f.get("ok") and (f.get("name") in TE_NAMES or
                            (f.get("bundle_id") or "").lower() == "com.apple.textedit")


def find_menu_item(app, contains, prefixes):
    """返回 (命中节点或 None, 候选标题列表)。"""
    r = cu("ax", "find", app, "--text", contains, "--role", "menuitem")
    cands = r[0].get("matches", [])
    titles = [c.get("title") for c in cands]
    for c in cands:  # exact title first
        if (c.get("title") or "") in prefixes:
            return c, titles
    for c in cands:  # then prefix match (打印… / 保存… 等)
        t = c.get("title") or ""
        if any(t.startswith(px) for px in prefixes):
            return c, titles
    return None, titles


def clear_windows(pid):
    """关掉 TextEdit 全部窗口。

    两个实测坑：
    * 未命名文档关闭会弹「你要保留此新文稿吗？」panel（删除/取消/保存），不会
      静默自动保存——按「删除」丢弃草稿（e2e 产生的垃圾草稿，语义正确）。
    * panel 挂着时 文件>关闭 是 disabled（AXEnabled=False, 0x0），菜单 press
      回执 ok 但 no-op——所以每轮先看 panel 再看菜单。
    """
    for i in range(14):
        if not doc_windows(pid):
            return True
        tr = cu("ax", "tree", str(pid), "--max", "300")[0]
        nodes = tr.get("nodes", [])
        delbtn = next((n for n in nodes if n.get("role") == "AXButton" and
                       (n.get("title") or "") == "删除"), None)
        if delbtn is not None:
            cu("ax", "press", delbtn["p"])       # 丢弃未命名草稿
        elif i % 2 == 0 and frontmost_is_textedit():
            cu("key", "esc")                     # 打开面板/工作表类 key window
        else:
            close, _ = find_menu_item(str(pid), "关闭", ("关闭",))
            if close:
                cu("ax", "press", close["p"])
        time.sleep(0.6)
    return not doc_windows(pid)


def main():
    global ORIGINAL_CLIP
    # 0. permissions: accessibility required, screen recording not needed here
    d, _ = cu("doctor")
    ax_status = (d.get("checks") or {}).get("status", {}).get("accessibility")
    if not step("doctor-accessibility", ax_status == "ok", d.get("checks", {}).get("status")):
        finish(reason="accessibility not granted for this host")
        return 1
    ORIGINAL_CLIP = cu("clipboard", "get")[0].get("text", "")

    # 1. bare background launch → clear stray windows → exactly one doc window
    subprocess.run(["killall", "TextEdit"], capture_output=True)
    time.sleep(0.5)
    # 清掉窗口恢复缓存：NSDocument 恢复态会让冷启动弹出一堆历史窗口，干扰定位。
    # TextEdit 是沙盒应用，恢复态在容器内
    for state_dir in (
        os.path.expanduser("~/Library/Saved Application State/"
                           "com.apple.TextEdit.savedState"),
        os.path.expanduser("~/Library/Containers/com.apple.TextEdit/Data/"
                           "Library/Saved Application State/"
                           "com.apple.TextEdit.savedState"),
    ):
        subprocess.run(["rm", "-rf", state_dir], capture_output=True)
    subprocess.run(["open", "-g", "-a", "TextEdit"], capture_output=True)
    pid = None
    for _ in range(10):
        pid = textedit_pid()
        if pid:
            break
        time.sleep(0.6)
    if not step("launch-background", pid is not None, f"pid={pid}"):
        finish()
        return 1
    subprocess.run(["open", "-a", "TextEdit"], capture_output=True)
    time.sleep(0.8)
    step("windows-cleared", clear_windows(pid), doc_windows(pid))
    with open(DOC, "w") as f:
        f.write("AXE2E-ORIGINAL\n")
    subprocess.run(["open", "-g", "-a", "TextEdit", DOC], capture_output=True)
    te = None
    for _ in range(10):
        wins = doc_windows(pid)
        if wins:
            te = wins[0]
            break
        time.sleep(0.5)
    if not step("single-doc-window", te is not None and len(doc_windows(pid)) == 1,
                [(w["window_id"], w["title"]) for w in doc_windows(pid)]):
        finish()
        return 1

    # 2. ax find the textarea (background read, frontmost untouched so far)
    fr, _ = cu("ax", "find", str(pid), "--role", "textarea", "--first")
    ta = (fr.get("matches") or [None])[0]
    if not step("ax-find-textarea", ta is not None and ta.get("p") and
                "AXE2E-ORIGINAL" in str(ta.get("value") or ""), ta):
        finish()
        return 1
    P = ta["p"]

    # 3. ax set → ax attr readback (SPEC §5 test 1, value half)
    VAL = "AXE2E 写值 ✅ 123"
    step("ax-set", cu("ax", "set", P, "--value", VAL)[0].get("ok"))
    ar, _ = cu("ax", "attr", P, "--name", "AXValue")
    step("ax-attr-readback", ar.get("ok") and ar.get("value") == VAL,
         {"got": ar.get("value"), "want": VAL})

    # 4. mixed path: ax coords → click --mode pts via --down/--up (SPEC §5 test 2)
    cx = int(ta["pos"][0] + ta["size"][0] / 2)
    cy = int(ta["pos"][1] + ta["size"][1] / 2)
    step("click-down", cu("click", str(cx), str(cy), "--mode", "pts", "--down")[0].get("ok"))
    step("click-up", cu("click", str(cx), str(cy), "--mode", "pts", "--up")[0].get("ok"))
    pos = cu("position")[0]
    step("cursor-at-target", abs(pos["x"] - cx) <= 2 and abs(pos["y"] - cy) <= 2, pos)
    foc = cu("ax", "attr", P, "--name", "AXFocused")[0]
    step("focused-flip", foc.get("ok") and foc.get("value") is True, foc)

    # 5. menu 保存_AXPress（菜单需激活态）→ 文件落盘验证
    subprocess.run(["open", "-a", "TextEdit"], capture_output=True)
    time.sleep(0.8)
    save, save_titles = find_menu_item(str(pid), "存", ("保存", "存储", "储存"))
    if step("find-menu-save", save is not None, save_titles):
        step("ax-press-menu-save", cu("ax", "press", save["p"])[0].get("ok"), save["p"])
        time.sleep(1.0)
        try:
            saved = open(DOC).read()
        except OSError:
            saved = ""
        step("file-saved-via-ax", VAL in saved, saved[:80])
    else:
        step("ax-press-menu-save", False, "menu item not found")
        step("file-saved-via-ax", False, "skipped")

    # 6. dialog: 打印面板 = 真实 AXSheet → AX 取消（Escape 等价，不动键盘）
    pr, pr_titles = find_menu_item(str(pid), "打印", ("打印",))
    if step("find-menu-print", pr is not None, pr_titles):
        step("ax-press-menu-print", cu("ax", "press", pr["p"])[0].get("ok"))
        time.sleep(1.2)
        tr = cu("ax", "tree", str(pid), "--max", "400")[0]
        sheets = [n["p"] for n in tr.get("nodes", []) if n.get("role") == "AXSheet"]
        step("print-dialog-appears", bool(sheets), sheets)
        cancel = next((n for n in tr.get("nodes", [])
                       if n.get("role") == "AXButton" and
                       (n.get("title") or "") in ("取消", "Cancel")), None)
        if step("dialog-cancel-found", cancel is not None,
                [(n.get("p"), n.get("title")) for n in tr.get("nodes", [])
                 if n.get("role") == "AXButton"][:8]):
            step("ax-press-dialog-cancel", cu("ax", "press", cancel["p"])[0].get("ok"),
                 cancel["p"])
            time.sleep(0.8)
            tr2 = cu("ax", "tree", str(pid), "--max", "400")[0]
            step("print-dialog-dismissed",
                 not [n for n in tr2.get("nodes", []) if n.get("role") == "AXSheet"],
                 "sheet gone")
        else:
            step("ax-press-dialog-cancel", False, "skipped")
            step("print-dialog-dismissed", False, "skipped")
    else:
        for n in ("ax-press-menu-print", "print-dialog-appears",
                  "dialog-cancel-found", "ax-press-dialog-cancel",
                  "print-dialog-dismissed"):
            step(n, False, "skipped")

    # 7. stale: 关闭唯一文档窗口（NSDocument 自动保存静默关闭）→ 旧句柄 fail-closed
    close, close_titles = find_menu_item(str(pid), "关闭", ("关闭",))
    if step("find-menu-close", close is not None, close_titles):
        step("ax-press-menu-close", cu("ax", "press", close["p"])[0].get("ok"))
        time.sleep(1.2)
        step("window-closed", not doc_windows(pid), doc_windows(pid))
    else:
        step("ax-press-menu-close", False, "skipped")
        step("window-closed", False, "skipped")
    stale, rc = cu("ax", "press", P)
    step("stale-fails-closed",
         rc == 1 and stale.get("ok") is False and stale.get("code") == "stale",
         {"rc": rc, "payload": stale})
    try:
        saved = open(DOC).read()
        step("autosave-on-close", VAL in saved, saved[:60])
    except OSError:
        step("autosave-on-close", False, "file gone")

    # 8. --paste 511 汉字逐字比对 (SPEC §5 test 5) — 前台 cmd+v
    with open(PASTE_DOC, "w") as f:
        f.write("")
    subprocess.run(["open", "-a", "TextEdit", PASTE_DOC], capture_output=True)
    time.sleep(1.2)
    step("paste-doc-open", len(doc_windows(pid)) == 1, doc_windows(pid))
    fr2, _ = cu("ax", "find", str(pid), "--role", "textarea", "--first")
    ta2 = (fr2.get("matches") or [None])[0]
    if step("ax-find-textarea-2", ta2 is not None, ta2 and ta2.get("p")):
        P2 = ta2["p"]
        step("ax-focus", cu("ax", "focus", P2)[0].get("ok"))
        time.sleep(0.3)
        pt, _ = cu("type", PASTE_TEXT, "--paste")
        step("type-paste", pt.get("ok") and pt.get("pasted_len") == len(PASTE_TEXT),
             {k: pt.get(k) for k in ("ok", "pasted_len", "clipboard_restored")})
        time.sleep(0.4)
        ar2, _ = cu("ax", "attr", P2, "--name", "AXValue")
        step("paste-verified", ar2.get("value") == PASTE_TEXT,
             f"len got={len(str(ar2.get('value') or ''))} want={len(PASTE_TEXT)}")
        sel, _ = cu("ax", "select", P2, "--range", "0", "4")
        sattr, _ = cu("ax", "attr", P2, "--name", "AXSelectedTextRange")
        step("ax-select", sel.get("ok") and sattr.get("value") == [0, 4],
             {"set": sel.get("ok"), "read": sattr.get("value")})
        clip_after = cu("clipboard", "get")[0].get("text", "")
        step("clipboard-restored", clip_after == ORIGINAL_CLIP,
             f"len={len(clip_after)} vs original={len(ORIGINAL_CLIP)}")
    else:
        for n in ("ax-focus", "type-paste", "paste-verified", "ax-select",
                  "clipboard-restored"):
            step(n, False, "skipped")

    # 9. key --hold code path (harmless modifier-only hold)
    hk, _ = cu("key", "cmd", "--hold", "120")
    step("key-hold", hk.get("ok") and hk.get("hold_ms") == 120, hk)

    # 10. background typing channel (cu 2.1 --app): Finder 抢前台，TextEdit 保持后台
    subprocess.run(["open", "-a", "Finder"], capture_output=True)
    time.sleep(0.8)
    te_active = frontmost_is_textedit()
    step("bg-frontend-check", not te_active, {"frontmost": cu("frontmost")[0].get("name")})
    fr3, _ = cu("ax", "find", str(pid), "--role", "textarea", "--first")
    ta3 = (fr3.get("matches") or [None])[0]
    if step("ax-find-textarea-3", ta3 is not None, ta3 and ta3.get("p")):
        P3 = ta3["p"]
        step("ax-focus-bg", cu("ax", "focus", P3)[0].get("ok"))
        cu("ax", "set", P3, "--value", "")
        time.sleep(0.3)
        BG_TEXT = "BG后台键入"
        tt, _ = cu("type", BG_TEXT, "--app", str(pid))
        step("type-app-bg", tt.get("ok") and tt.get("channel") == "pid", tt)
        time.sleep(0.4)
        ar3, _ = cu("ax", "attr", P3, "--name", "AXValue")
        step("type-app-bg-verified", ar3.get("value") == BG_TEXT,
             {"got": ar3.get("value"), "want": BG_TEXT})
        ka, _ = cu("key", "--app", str(pid), "left")
        step("key-app-bg", ka.get("ok") and ka.get("channel") == "pid", ka)
        time.sleep(0.4)
        # left = keyDown 路径（后台有效，光标 6→5）。两条实测边界：
        # cmd+a 这类**菜单快捷键**后台不触发（key equivalent 由菜单系统派发，需激活态）；
        # home 在 TextEdit 里不移动插入点（滚动语义），不能当验证 oracle
        sattr3, _ = cu("ax", "attr", P3, "--name", "AXSelectedTextRange")
        step("key-app-bg-verified",
             sattr3.get("value") == [5, 0], sattr3.get("value"))
    else:
        for n in ("ax-focus-bg", "type-app-bg", "type-app-bg-verified",
                  "key-app-bg", "key-app-bg-verified"):
            step(n, False, "skipped")

    # 11. ax state（编号句柄）：TextEdit 小页面——set/attr 走编号、--text 过滤、越界 fail-closed
    stt, _ = cu("ax", "state", str(pid))
    els = stt.get("elements", [])
    step("state-ok", stt.get("ok") is True and bool(els) and
         all(isinstance(e.get("i"), int) and e.get("p") for e in els),
         {"count": stt.get("count"), "walked": stt.get("walked"),
          "budget_hit": stt.get("budget_hit")})
    st_ta = next((e for e in els if e.get("role") in ("AXTextArea", "AXTextField")
                  and "editable" in (e.get("flags") or [])), None)
    if step("state-textarea-editable-handle", st_ta is not None, st_ta):
        VAL4 = "STATE句柄写值"
        step("state-idx-set",
             cu("ax", "set", str(st_ta["i"]), "--value", VAL4)[0].get("ok"))
        rb, _ = cu("ax", "attr", str(st_ta["i"]), "--name", "AXValue")
        step("state-idx-attr-readback", rb.get("ok") and rb.get("value") == VAL4,
             {"got": rb.get("value")})
    else:
        step("state-idx-set", False, "skipped")
        step("state-idx-attr-readback", False, "skipped")
    stf, _ = cu("ax", "state", str(pid), "--text", "STATE句柄")
    step("state-text-filter",
         stf.get("ok") and any("STATE句柄" in str(e.get("value") or "")
                               for e in stf.get("elements", [])),
         {"hits": stf.get("count")})
    oob, rc = cu("ax", "press", "99999")
    step("state-idx-oob-fails-closed",
         rc == 1 and oob.get("ok") is False and oob.get("code") == "not-found",
         {"rc": rc, "code": oob.get("code")})

    # 12. ax state 大页面（Chrome，skip-if-absent）：预算内完成、交互优先、菜单 0×0 过滤
    chr_app = next((a for a in cu("apps")[0].get("apps", [])
                    if (a.get("bundle_id") or "") == "com.google.Chrome"), None)
    if chr_app is None:
        step("chrome-state-segment", True, "skipped: Chrome not running")
    else:
        cpid = str(chr_app["pid"])
        t0 = time.time()
        stc, _ = cu("ax", "state", cpid, "--timeout", "12", timeout=30)
        dt = round(time.time() - t0, 1)
        els_c = stc.get("elements", [])
        step("chrome-state-large-page",
             stc.get("ok") is True and bool(els_c) and dt < 30,
             {"count": stc.get("count"), "walked": stc.get("walked"),
              "budget_hit": stc.get("budget_hit"), "sec": dt})
        mis = [e for e in els_c if e.get("role") == "AXMenuItem"]
        step("chrome-state-menuitem-filter",
             all(e.get("size") not in (None, [0, 0]) for e in mis),
             {"menuitem_in_output": len(mis)})
        pr = [e for e in els_c if "pressable" in (e.get("flags") or [])]
        step("chrome-state-pressable-ranked-first",
             len(pr) > 10 and pr and pr[0]["i"] < 20,
             {"pressable": len(pr), "first_i": pr[0]["i"] if pr else None})
        ub = next((e for e in els_c if e.get("role") == "AXTextField" and
                   (e.get("name") or "") in ("地址和搜索栏",
                                             "Address and search bar")), None)
        if ub is None:
            # 富 web AX 页面会把 entry 类元素挤出默认 top N——用 --text 过滤重查
            for q in ("地址和搜索栏", "Address and search"):
                ub_st, _ = cu("ax", "state", cpid, "--text", q,
                              "--timeout", "12", timeout=30)
                ub = next((e for e in ub_st.get("elements", [])
                           if (e.get("name") or "") in ("地址和搜索栏",
                                                        "Address and search bar")), None)
                if ub is not None:
                    break
        if step("chrome-state-urlbar-found", ub is not None,
                [(e.get("i"), e.get("name")) for e in els_c
                 if e.get("role") == "AXTextField"][:4]):
            ur, _ = cu("ax", "attr", str(ub["i"]), "--name", "AXValue", timeout=30)
            step("chrome-state-urlbar-attr-via-idx",
                 ur.get("ok") and isinstance(ur.get("value"), str),
                 {"got": str(ur.get("value"))[:60]})
        else:
            step("chrome-state-urlbar-attr-via-idx", False, "skipped")

    # 13. QQ音乐（cu 2.1 AXDescription + 后台键盘，skip-if-absent）
    qm = next((a for a in cu("apps")[0].get("apps", [])
               if (a.get("bundle_id") or "") == "com.tencent.QQMusicMac"), None)
    if qm is None:
        step("qqmusic-segment", True, "skipped: QQ音乐 not running")
    else:
        qpid = str(qm["pid"])
        trq, _ = cu("ax", "tree", qpid, "--depth", "20", "--max", "1500")
        nodes = trq.get("nodes", [])
        descs = [n for n in nodes if n.get("desc")]
        step("qqm-desc-tree", any(n.get("desc") == "播放控制栏" for n in nodes) and
             any((n.get("desc") or "").startswith("歌曲名：") for n in nodes),
             {"nodes": len(nodes), "with_desc": len(descs)})
        btn = next((n for n in nodes if n.get("desc") in ("播放", "暂停播放")
                    and n.get("p", "").startswith("w")), None)
        menu_item = next((n for n in nodes if n.get("role") == "AXMenuItem" and
                          (n.get("title") or "") in ("播放", "暂停")
                          and n.get("p", "").startswith("m")), None)
        if step("qqm-state-node-found", btn is not None and menu_item is not None,
                {"btn": btn and btn.get("desc"), "menu": menu_item and
                 menu_item.get("title")}):
            before_b, before_m = btn.get("desc"), menu_item.get("title")
            k1, _ = cu("key", "--app", qpid, "space")
            time.sleep(1.5)
            trq1, _ = cu("ax", "tree", qpid, "--depth", "20", "--max", "1500")
            btn1 = next((n for n in trq1.get("nodes", []) if n.get("p") == btn["p"]),
                        None)
            flipped1 = (btn1 or {}).get("desc") not in (None, before_b)
            step("qqm-key-app-toggle-1",
                 k1.get("ok") and k1.get("channel") == "pid" and flipped1,
                 {"before": before_b, "after": (btn1 or {}).get("desc")})
            k2, _ = cu("key", "--app", qpid, "space")
            time.sleep(1.5)
            trq2, _ = cu("ax", "tree", qpid, "--depth", "20", "--max", "1500")
            btn2 = next((n for n in trq2.get("nodes", []) if n.get("p") == btn["p"]),
                        None)
            step("qqm-key-app-toggle-2-restores",
                 (btn2 or {}).get("desc") == before_b,
                 {"orig": before_b, "now": (btn2 or {}).get("desc")})
        else:
            for n in ("qqm-key-app-toggle-1", "qqm-key-app-toggle-2-restores"):
                step(n, False, "skipped")

    # 14. screenshot --region-px argparse 回归：曾因未定义 --pts 而 AttributeError（cu 2.2）
    # 无录屏权限的宿主上走到 screencapture 失败也是 PASS——崩溃点在更早的 rect 计算
    sr, _ = cu("screenshot", "--region-px", "10", "10", "200", "150")
    step("screenshot-region-px-no-crash",
         "ok" in sr and "AttributeError" not in str(sr.get("error", "")),
         {"ok": sr.get("ok"), "error": str(sr.get("error", ""))[:120]})

    finish()
    return 0 if not FAILED else 1


def finish(reason=None):
    subprocess.run(["killall", "TextEdit"], capture_output=True)
    for p in (DOC, PASTE_DOC):
        try:
            os.unlink(p)
        except OSError:
            pass
    if ORIGINAL_CLIP:
        cu("clipboard", "set", ORIGINAL_CLIP)
    status = "ABORT" if reason else ("PASS" if not FAILED else "FAIL")
    result = {"e2e_ax": status, "reason": reason,
              "passed": len(LOG) - len(FAILED), "total": len(LOG), "failed": FAILED}
    print(json.dumps(result, ensure_ascii=False))
    with open(RESULT, "w") as f:
        json.dump({"result": result, "log": LOG}, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    sys.exit(main())
