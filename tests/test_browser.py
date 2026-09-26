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


def test_measure_layout_refuses_to_report_when_images_never_loaded(tmp_path):
    """`waitForFunction(...).catch(() => {})` 把超时咽掉了，于是"图还没加载完"
    不是失败而是**静默跳过**——`if (!im.complete || !im.naturalWidth) continue`
    会让所有量几何的检查跳过没加载的图。漏检比误伤更阴：它永远绿。
    （同一个根因在 `shot.mjs` 上已经造成过两次跑出 4 与 6 两个数字。）"""
    page = tmp_path / "broken.html"
    page.write_text(
        u'<html><body><img src="does-not-exist.png" width="10" height="10"/></body></html>',
        encoding="utf-8")
    # 一个真会 404 的图：complete 会是 true 而 naturalWidth 是 0，
    # 这正是"没加载成却被当成加载完"的形状。
    # 注意 `--file`：直接把路径当位置参数传，脚本会打印用法并 rc=2，
    # 于是这条测试会**因为用错 CLI 而假绿**（第一版就是这样，0.36 秒就"过"了）。
    r = subprocess.run(["node", os.path.join(ROOT, "scripts", "measure-layout.mjs"),
                        "--file", str(page)],
                       capture_output=True, timeout=300)
    # 不用 `text=True`：Windows 上它按 GBK 解码，中文输出会整段变空
    # （这条测试第一版就是因此拿到空 blob）。仓库里量几何的测试统一
    # 拿 bytes 再 `decode("utf-8", "ignore")`，照抄那个形状。
    blob = (r.stdout or b"").decode("utf-8", "ignore") + (r.stderr or b"").decode("utf-8", "ignore")
    # rc==2 是用法错（把路径当位置参数传就会这样），那会让这条测试假绿——
    # 第一版就是这么"过"的，0.36 秒。所以先确认它真的跑了检查。
    assert r.returncode != 2, u"CLI 用错了，脚本根本没跑：\n%s" % blob[-400:]
    assert r.returncode == 1, u"图没加载成却仍然 rc=0（漏检）：\n%s" % blob[-400:]
    assert u"images-not-loaded" in blob, \
        u"失败了，但没说是因为图没加载：\n%s" % blob[-400:]
