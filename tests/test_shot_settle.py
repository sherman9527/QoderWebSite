# -*- coding: utf-8 -*-
"""`shot.mjs` 量的"破图"必须只包含真破的图，而且没加载完时不能装作量到了结论。

为什么单独立一个文件：09-24 视觉基线自己红了两次、两次数字不一样（`brokenImgs 0→4`、
`0→6`），查下去发现量的那份快照 12 张图全在磁盘上。原因是 `brokenImgs` 把
「还没加载完」和「加载失败」算成了同一个东西，而等加载的那一句写成
`waitForFunction(...).catch(() => {})` —— 超时被咽掉，于是页面没稳定也照样出数。
一道会随机器快慢变的闸门，等于没有闸门：它既会误伤，也会在最该响的时候沉默。

memo 里已经记过这条轴的另一端（LV 篇：`brokenImgs:0` 与肉眼看到的白卡同时为真）。
同一个根：在任意时刻采样 `complete`。
"""
import io
import json
import os
import subprocess

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _page(tmp_path, imgs):
    d = tmp_path / "site"
    (d / "images").mkdir(parents=True)
    from PIL import Image
    Image.new("RGB", (600, 400), (200, 120, 60)).save(
        str(d / "images" / "ok.png"), "PNG")
    page = d / "page.html"
    io.open(str(page), "w", encoding="utf-8").write(
        u'<!doctype html><meta charset="utf-8"><body>' + imgs +
        u'<div style="height:4000px"></div></body>')
    return page


def _run(page, tmp_path):
    out = tmp_path / "geo.json"
    r = subprocess.run(
        ["node", os.path.join("scripts", "shot.mjs"), str(page),
         "--widths", "1440", "--out", str(tmp_path / "shots"),
         "--json-out", str(out)],
        cwd=ROOT, capture_output=True, timeout=300)
    body = r.stdout.decode("utf-8", "ignore")
    rec = {}
    for line in body.splitlines():
        line = line.strip()
        if line.startswith("{"):
            rec = json.loads(line)
            break
    return r, rec


def test_a_file_that_is_actually_missing_is_still_reported(tmp_path):
    """拆"还没加载完"不能顺手把真破图也拆没了——那才是这道闸门存在的理由。"""
    page = _page(tmp_path, u'<img src="images/nope.png" loading="lazy">')
    r, rec = _run(page, tmp_path)
    assert rec.get("brokenImgs") == 1, u"引用断了却没报：%s" % (rec,)


def test_an_image_that_has_not_loaded_yet_is_not_called_broken(tmp_path):
    """`display:none` 的懒加载图永远不会开始加载，`complete` 恒为 false。
    这是最稳定的"没加载完"夹具——旧代码把它算成破图（实测 bad=3）。"""
    page = _page(tmp_path, u'<img src="images/ok.png" loading="lazy">'
                            + u'<img src="images/ok.png" loading="lazy" style="display:none">' * 3)
    r, rec = _run(page, tmp_path)
    assert rec.get("brokenImgs") == 0, \
        u"图在磁盘上、引用也对，只是没被加载，不该算破图：%s" % (rec,)
    assert rec.get("pendingImgs") == 3, u"没加载完要单独报数，不能不提：%s" % (rec,)


def test_the_measurement_refuses_to_silently_settle_for_an_unsettled_page(tmp_path):
    """没稳定就要出声。旧写法 `.catch(() => {})` 把超时咽了，
    于是"页面还没稳定"与"页面没问题"打出同一份 JSON，看数的人分不出来。"""
    page = _page(tmp_path, u'<img src="images/ok.png" loading="lazy" style="display:none">')
    r, rec = _run(page, tmp_path)
    assert r.returncode != 0, u"永远加载不完的页面却正常退出：%s" % (rec,)
    err = r.stderr.decode("utf-8", "ignore")
    assert u"没加载完" in err or "pending" in err.lower(), \
        u"退出码非 0 还不够，要说出为什么：%s" % (err[-300:],)
