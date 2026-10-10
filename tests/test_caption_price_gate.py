# -*- coding: utf-8 -*-
"""G-03 新增一条：图注里的价格必须有引用位（W-188）。

为什么判图注：图注是**直接印在页面上的一句断言**，但它没有 `source_ids` 可挂——
区块有、行有、正文有，图片记录只有 `source_page`（一个 URL，不带标签）。
于是"3999 元""584.10 万元"这种数可以越过 R-02 出现在页面上而全站 0 fail。

判据（10-04 量过才敢定）：图注里有价格 ⇒ 这张图的 `source_page` 必须是本篇
`sources[].url` 之一。真库上 13 张带价格的图注，**命中 0 条已引来源**，
所以这条今天不误伤任何正当公价（浪琴那种"官方公价￥18200"走的是表格行，有芯片）。
"""
import io
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))
import validate as V  # noqa: E402

CTX = V.Ctx if hasattr(V, "Ctx") else None


def _ctx(tmp_path, bar, caption, source_page, cited_urls):
    out_dir = tmp_path / "output" / "T"
    (out_dir / "images").mkdir(parents=True)
    img = out_dir / "images" / "a.jpg"
    img.write_bytes(b"\xff\xd8\xff" + b"0" * 4000)
    data = {
        "topic": u"T",
        "sources": [{u"id": u"S001", u"url": u, u"label": u"来源"} for u in cited_urls],
        "sections": [{u"id": u"s1", u"title": u"第一章",
                      u"images": [{u"file": u"images/a.jpg", u"alt": caption,
                                   u"caption": caption, u"source_page": source_page}],
                      u"blocks": []}],
    }
    page = out_dir / "T.html"
    page.write_text(u"<html><body><h1>第一章</h1>"
                    u"<p>劳力士年产百万只，正文里有数字与百分号，本条判的不关它们事。</p>"
                    u"<img src=\"images/a.jpg\" alt=\"" + caption + u"\"></body></html>",
                    encoding="utf-8")
    json.dump(data, io.open(str(out_dir / "data.json"), "w", encoding="utf-8"))
    return V.Ctx(u"T", str(out_dir), str(page), u"", data, bar)


def test_a_caption_price_without_a_cited_source_is_caught(tmp_path):
    bar = json.load(io.open(os.path.join(V.ROOT, "config", "quality_bar.json"), encoding="utf-8"))
    c = _ctx(tmp_path, bar, u"3999元！某款眼镜发布：250 小时待机_什么值得买",
             u"https://post.example.com/p/1/", [])
    msgs = u" ".join(f.message for f in V.g03_images(c))
    assert u"图注" in msgs and u"价格" in msgs, u"图注里的价格没被抓到：%s" % msgs


def test_a_caption_price_backed_by_a_cited_source_passes(tmp_path):
    bar = json.load(io.open(os.path.join(V.ROOT, "config", "quality_bar.json"), encoding="utf-8"))
    url = u"https://official.example.com/price/"
    c = _ctx(tmp_path, bar, u"官方公价 18,200 元", url, [url])
    msgs = u" ".join(f.message for f in V.g03_images(c))
    assert not (u"图注" in msgs and u"价格" in msgs), u"正当公价被误伤：%s" % msgs
