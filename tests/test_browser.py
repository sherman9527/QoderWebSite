# -*- coding: utf-8 -*-
""""用默认浏览器打开"这件事的可执行约束（W-59，开发者 2026-09-19 提出）。

分两条路，别混：
  * 给人看的 → 走系统文件关联（os.startfile），默认浏览器换了命令不用改；
  * 量几何的（G-13 / shot）→ 必须指定内核，而且要挑开发者实际用的那颗。
"""
import io
import json
import os
import subprocess
import sys

import pytest

import open as OPEN  # scripts/open.py

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BROWSER_MJS = os.path.join(ROOT, "scripts", "browser.mjs")


def test_open_uses_the_os_association_not_a_hardcoded_exe(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(os, "startfile", lambda p: calls.append(p), raising=False)
    page = tmp_path / "x.html"
    page.write_text("<html></html>", encoding="utf-8")
    OPEN.open_in_default_browser(str(page))
    assert calls == [str(page)], "没走系统默认处理器：%s" % calls
    src = io.open(os.path.join(ROOT, "scripts", "open.py"), encoding="utf-8").read()
    assert ".exe" not in src, "写死了浏览器可执行文件，用户改默认浏览器后这条命令就骗人了"


def test_open_rejects_missing_file(tmp_path):
    with pytest.raises(SystemExit):
        OPEN.open_in_default_browser(str(tmp_path / "nope.html"))


def test_geometry_gate_engine_matches_the_users_default_browser():
    """G-13 量的必须是开发者看的那颗内核。这台机器装了 Edge → 应该选 msedge。"""
    edge = any(os.path.exists(p) for p in [
        r"C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe",
        r"C:/Program Files/Microsoft/Edge/Application/msedge.exe",
    ])
    code = ("import(%r).then(m => console.log(m.resolveChannel()))"
            % ("file:///" + BROWSER_MJS.replace("\\", "/")))
    out = subprocess.run([os.environ.get("NODE", "node"), "-e", code],
                         capture_output=True, text=True, cwd=ROOT, timeout=60)
    got = out.stdout.strip()
    assert got, out.stderr[:200]
    if edge:
        assert got == "msedge", "装了 Edge 却不用它量几何：%s" % got
