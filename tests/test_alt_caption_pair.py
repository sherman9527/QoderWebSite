# -*- coding: utf-8 -*-
"""G-03 的 alt 判据改成「alt 与可见图注二者皆空才 fail」（W-188 ②）。

为什么改：`<figcaption>` 渲染的是 `img.caption || img.alt`（`TopicPage.tsx:397`），
而采集期这两行都取自同一个 `title`（`generate.py:811-812`），于是全站 465 张图里
406 张把同一串来源站 SEO 文案写了两遍——屏读会把 figcaption 与 alt 各念一遍，
读者听到的是「【百达翡丽手表价格及图片】PATEK PHILIPPE…官网型号查询|腕表之家触屏版」×2。
把 alt 置空之后，图注仍是那句话，但只念一遍；`alt=""` 也正是「装饰性图片」的正确写法。

代价：alt 空了，可见图注就成了唯一的文本承载。所以判据必须跟着改——
**空 alt 不再是缺陷，"空 alt 又没有可见图注"才是**。封面单独算：
封面框里没有可见图注，alt 是它唯一的可读文本，所以声明了封面就必须带 alt。
"""
import io
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))
import validate as V  # noqa: E402


def _ctx(tmp_path, images, cover=None, alt_attrs=True):
    out_dir = tmp_path / "output" / "T"
    (out_dir / "images").mkdir(parents=True)
    for im in images:
        (out_dir / "images" / im["file"].split("/")[-1]).write_bytes(b"\xff\xd8\xff" + b"0" * 4000)
    if cover:
        (out_dir / "images" / cover["file"].split("/")[-1]).write_bytes(b"\xff\xd8\xff" + b"0" * 4000)

    body = []
    for im in images:
        tag = u'<img src="%s"' % im["file"]
        if alt_attrs:
            tag += u' alt="%s"' % (im.get("alt") or u"")
        body.append(tag + u">")
        if (im.get("caption") or u"").strip():
            body.append(u"<figcaption>%s</figcaption>" % im["caption"])
    page = out_dir / "T.html"
    html = (u"<html><body><h1>第一章</h1>"
            u"<p>劳力士年产百万只，正文里有数字与百分号，本条判的不关它们事。</p>"
            + u"".join(body) + u"</body></html>")
    page.write_text(html, encoding="utf-8")

    data = {
        "topic": u"T",
        "sources": [],
        "sections": [{u"id": u"s1", u"title": u"第一章",
                      u"images": [{u"file": im["file"], u"alt": im.get("alt") or u"",
                                   u"caption": im.get("caption") or u"",
                                   u"kind": im.get("kind")}
                                  if im.get("kind") else
                                  {u"file": im["file"], u"alt": im.get("alt") or u"",
                                   u"caption": im.get("caption") or u""}
                                  for im in images],
                      u"blocks": []}],
    }
    if cover:
        data["cover"] = {u"file": cover["file"], u"alt": cover.get("alt") or u"",
                         u"source_page": u"https://official.example.com/x/"}
    json.dump(data, io.open(str(out_dir / "data.json"), "w", encoding="utf-8"))
    bar = json.load(io.open(os.path.join(V.ROOT, "config", "quality_bar.json"), encoding="utf-8"))
    return V.Ctx(u"T", str(out_dir), str(page), html, data, bar)


def _msgs(ctx):
    return u" ".join(f.message for f in V.g03_images(ctx))


def test_an_empty_alt_is_fine_when_the_reader_can_see_a_caption(tmp_path):
    """新行为：图注可见 ⇒ alt 允许为空，不再报。"""
    ctx = _ctx(tmp_path, [{u"file": u"images/a.jpg", u"alt": u"",
                           u"caption": u"日内瓦博物馆里的古董钟表"}])
    m = _msgs(ctx)
    assert u"alt" not in m, u"有可见图注的空 alt 仍被判死：%s" % m


def test_an_image_with_neither_alt_nor_caption_still_fails(tmp_path):
    ctx = _ctx(tmp_path, [{u"file": u"images/a.jpg", u"alt": u"", u"caption": u""}])
    m = _msgs(ctx)
    assert u"alt" in m, u"既没 alt 又没图注却被放过：%s" % m


def test_a_missing_alt_attribute_is_still_caught(tmp_path):
    """置空 alt ≠ 删掉属性。属性缺失会让 img 与 alt 数量对不上，这条不许松。"""
    ctx = _ctx(tmp_path, [{u"file": u"images/a.jpg", u"alt": u"",
                           u"caption": u"日内瓦博物馆里的古董钟表"}], alt_attrs=False)
    m = _msgs(ctx)
    assert u"alt" in m, u"img 上没有 alt 属性却没被发现：%s" % m


def test_a_declared_cover_must_carry_alt_because_it_has_no_caption(tmp_path):
    ctx = _ctx(tmp_path, [{u"file": u"images/a.jpg", u"alt": u"",
                           u"caption": u"日内瓦博物馆里的古董钟表"}],
                cover={u"file": u"images/cover.jpg", u"alt": u""})
    m = _msgs(ctx)
    assert u"封面" in m, u"封面 alt 为空被放过，屏读到了这一格只剩静音：%s" % m


def test_the_projection_keeps_an_explicit_empty_alt():
    """`image_ref` 原来把空串一律丢掉，于是 `alt=""` 到 data.json 里变成"没有 alt 这个键"，
    而 schema 的 required 里有 alt —— 三步改动差这一处就是 21 条集成测试红。
    空 alt 是**写上去的值**（装饰性图片），不是"没填"，投影必须留着它。"""
    import generate as G
    ref = G.image_ref({u"file": u"images/a.jpg", u"alt": u"", u"caption": u"古董钟表",
                       u"source_page": u"https://x.example.com/a", u"title": u"SEO 标题"})
    assert ref.get(u"alt") == u"", u"空 alt 被投影丢掉了：%s" % sorted(ref)
    assert u"title" not in ref and u"source_image" not in ref, u"投影漏了白名单外的键"
    # 但别的空串照旧要丢：`source_page: ""` 会撞 schema 的 ^https?://
    assert G.image_ref({u"file": u"images/a.jpg", u"alt": u"x", u"source_page": u""}) == \
        {u"file": u"images/a.jpg", u"alt": u"x"}, u"空 source_page 被留进了投影"
