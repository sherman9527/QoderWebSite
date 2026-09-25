# -*- coding: utf-8 -*-
"""W-37：模板改动的视觉基线比对。

为什么不是像素 diff：字体渲染、抗锯齿、截图时刻都会让像素图天天变，
diff 出来的噪音没人看。这里比的是**实测几何**（版心宽、封面尺寸、首图尺寸、
横向溢出），它恰好是"样式改坏了"的信号，而且稳定可解释。

重跑基线（量的是**真产物的冻结快照**，不是桩件正文，也不是 output/ 里的活文件）：
    node scripts/render.mjs --data tests/golden/coffee/data.json --out .probe/base.html
    node scripts/shot.mjs .probe/base.html --widths 375,1440,3762 --json-out tests/golden/layout-coffee.json

为什么不直接钉 output/咖啡/…：那是批量生成会就地重写的目录。钉上去以后，
跑一次 --redo-images 或任何重生成都会让这道闸门因为"内容变了"而红，
而它要防的是"模板改坏了"。两者混在一起，红的时候就没人信它了。
"""
import copy
import io
import json
import os
import shutil
import subprocess

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GOLDEN = os.path.join(ROOT, "tests", "golden", "layout-coffee.json")
DATA = os.path.join(ROOT, "tests", "golden", "coffee", "data.json")
WIDTHS = ["375", "1440", "3762"]
TOL_PX = 3          # 绝对像素容差：亚像素取整不该让 CI 红
TOL_HEIGHT = 0.03   # 整页高度随文本浮动，只防"突然长高/塌掉"


def _current(tmp_path):
    assert os.path.isfile(DATA), u"基线量的是冻结快照：%s 不在，比对就没内容可量" % DATA
    page = tmp_path / "base.html"
    # 配图也要带上：不然 brokenImgs 量的全是"临时目录里没图"，跟模板无关
    shutil.copytree(os.path.join(os.path.dirname(DATA), "images"),
                    str(tmp_path / "images"))
    r = subprocess.run(["node", os.path.join("scripts", "render.mjs"),
                        "--data", DATA, "--out", str(page)],
                       cwd=ROOT, capture_output=True, timeout=300)
    assert r.returncode == 0, r.stderr.decode("utf-8", "ignore")[-300:]
    out = tmp_path / "geo.json"
    r = subprocess.run(["node", os.path.join("scripts", "shot.mjs"), str(page),
                        "--widths", ",".join(WIDTHS), "--out", str(tmp_path / "shots"),
                        "--json-out", str(out)],
                       cwd=ROOT, capture_output=True, timeout=300)
    assert r.returncode == 0, r.stderr.decode("utf-8", "ignore")[-300:]
    return {int(x["width"]): x for x in json.load(io.open(str(out), encoding="utf-8"))}


def _diff(base, now):
    bad = []
    for width, want in base.items():
        got = now.get(width) or now.get(str(width))
        if got is None:
            bad.append(u"缺视口 %s" % width)
            continue
        for key in ("docScrollW", "totalImgs", "brokenImgs"):
            if want.get(key) != got.get(key):
                bad.append(u"@%s %s %s→%s" % (width, key, want.get(key), got.get(key)))
        for key in ("cover", "wrap", "h1", "firstFig"):
            a, b = want.get(key) or {}, got.get(key) or {}
            for prop in ("x", "w"):
                if prop in a and abs(a[prop] - b.get(prop, -9e9)) > TOL_PX:
                    bad.append(u"@%s %s.%s %s→%s" % (width, key, prop, a[prop], b.get(prop)))
            if "h" in a and a["h"] and abs(a["h"] - b.get("h", 0)) > max(TOL_PX, a["h"] * TOL_HEIGHT):
                bad.append(u"@%s %s.h %s→%s" % (width, key, a["h"], b.get("h")))
    return bad


@pytest.mark.skipif(not os.path.isfile(GOLDEN), reason="还没有几何基线，先按模块文档重跑")
def test_layout_matches_the_recorded_baseline(tmp_path):
    base = {int(x["width"]): x for x in json.load(io.open(GOLDEN, encoding="utf-8"))}
    bad = _diff(base, _current(tmp_path))
    assert not bad, u"模板几何相对基线变了：\n  " + u"\n  ".join(bad[:12])


def test_baseline_diff_actually_detects_a_shift(tmp_path, monkeypatch):
    """基线比对自己也要能被证伪——否则"没红"只是因为它什么都看不见。"""
    base = {375: {"width": 375, "docScrollW": 375, "totalImgs": 7, "brokenImgs": 5,
                  "cover": {"x": 15, "w": 345, "h": 258},
                  "wrap": {"x": 15, "w": 345, "h": 5301},
                  "h1": {"x": 15, "w": 345, "h": 64},
                  "firstFig": {"x": 15, "w": 345, "h": 215}}}
    shifted = copy.deepcopy(base)
    shifted[375]["wrap"]["w"] = 999
    assert _diff(base, shifted), "版心从 345 变成 999 都没发现，基线等于没写"
    assert _diff(base, base) == []
