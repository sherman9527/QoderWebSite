# -*- coding: utf-8 -*-
"""索引主页与 tags 归档（specs/golden-template + tasks W-29..W-32）。"""
import io
import json
import os
import re
import shutil

import pytest

import build_index as BI
import validate as V
from conftest import make_passing_data, write_image


def _make_site(tmp_path, monkeypatch, gate=None):
    """造两个已生成完毕的领域，产物结构照真实 output/ 摆。"""
    out = tmp_path / "output"
    for topic, cat, token in [(u"甲领域", u"腕表", "coffee-roast"),
                              (u"乙领域", u"汽车", "bentley-racing")]:
        data = make_passing_data(topic=topic)
        data["category"] = cat
        data["tags"] = [topic, cat, u"测试"]
        data["theme"] = {"token": token}
        d = out / topic
        (d / "images").mkdir(parents=True)
        for s in data["sections"]:
            for im in s["images"]:
                im.setdefault("width", 1600)
                im.setdefault("height", 900)
                write_image(d / im["file"])     # 解得开的图，见 conftest.write_image
        (d / "data.json").write_text(
            json.dumps(data, ensure_ascii=False), encoding="utf-8")
        (d / ("%s.html" % topic)).write_text(
            "<html><body>ok</body></html>", encoding="utf-8")
    monkeypatch.setattr(BI, "OUTPUT", str(out))
    monkeypatch.setattr(V, "OUTPUT", str(out))
    if gate is not None:
        monkeypatch.setattr(BI, "_publishable", gate)
    return out


@pytest.fixture
def site(tmp_path, monkeypatch):
    """本夹具测的是"索引怎么归档"，所以把闸门 stub 成永远放行——
    夹具里的 HTML 是假的（`<html><body>ok</body></html>`），真闸门会把它判死。
    闸门与索引的接线由 `site_gated` 那两条单独钉，两边都不放过。"""
    return _make_site(tmp_path, monkeypatch, gate=lambda topic, root: [])


@pytest.fixture
def site_gated(tmp_path, monkeypatch):
    """同样的产物，但**不** stub 闸门：用来测「索引收录前先问闸门」这件事本身。"""
    return _make_site(tmp_path, monkeypatch, gate=None)


def test_the_index_asks_the_validator_before_listing_a_domain(tmp_path, monkeypatch):
    """W-80 的正解：一个领域能不能上入口页，判据必须只有 validate 一处。
    这条钉的是**接线**——索引确实去调了 run()，并且排掉了要开浏览器的 G-13。"""
    called = {}

    def fake_run(gate_filter=None, domains=None, skip=(), output_dir=None):
        called["args"] = (domains, tuple(skip), output_dir)
        # where 必须落在**这个领域**的产物上，否则它就不该算到该领域头上
        # （见 test_a_site_level_finding_does_not_get_blamed_on_every_domain）。
        return ([V.Finding(V.g03_images, "output/某领域/某领域_2026-09-22.html#ch",
                           u"该章节无配图")], 1, domains)

    monkeypatch.setattr(V, "run", fake_run)
    fails = BI._publishable(u"某领域", str(tmp_path))
    assert fails, "闸门报了 fail，_publishable 却说可以上架"
    assert called["args"][0] == [u"某领域"], "没有只查这一个领域"
    assert "G-13" in called["args"][1], "索引重建里等真浏览器，每个领域白等一遍"


def test_a_domain_that_fails_the_gates_is_left_off_the_index(tmp_path, monkeypatch):
    """09-22 实测：积家 4 章没图、G-03 判死，索引照列它——因为索引只在
    "某领域自己 verify 通过"时重建，而门槛后来收紧了。
    这里用真闸门（不 stub _publishable）跑一个"全页没有来源"的领域，它必须被跳过。"""
    out = tmp_path / "output"
    d = out / u"空壳领域"
    (d / "images").mkdir(parents=True)
    data = make_passing_data(topic=u"空壳领域")
    data["sources"] = []                      # G-06：全页没有登记任何来源
    for s in data["sections"]:
        s["images"] = []
        for b in s["blocks"]:
            b.pop("source_ids", None)
    (d / "data.json").write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    (d / (u"空壳领域_2026-09-19.html")).write_text(
        "<html><body>ok</body></html>", encoding="utf-8")
    monkeypatch.setattr(BI, "OUTPUT", str(out))
    monkeypatch.setattr(V, "OUTPUT", str(out))
    assert BI.collect("2026-09-19") == [], "闸门判死的领域仍然被索引收录"


def test_a_site_level_finding_does_not_get_blamed_on_every_domain(site_gated, monkeypatch):
    """`_publishable` 只按 level=="fail" 过滤、不看 `where` 的话，
    一条**全站级**的 fail（G-09 报的是 rule.md，不属于任何领域）会被算到
    每个被询问的领域头上 → 索引空 → `build()` 当成"还没有产物"返回 None →
    generate.py 打「✓ 完成（索引未更新）」并以 0 退出。
    整站入口消失而每次运行都报告成功。09-22 code review 找出来的。"""
    def fake_run(gate_filter=None, domains=None, skip=(), output_dir=None):
        return ([V.Finding(V.g09_red_lines, "rule.md",
                           u"红线 R-99 指向不存在的闸门 G-14")], 1, domains)
    monkeypatch.setattr(V, "run", fake_run)
    assert BI._publishable(u"甲领域", str(site_gated)) == [], \
        u"rule.md 上的全站问题被算成了「甲领域不合格」"


def test_build_refuses_to_silently_empty_the_index(site_gated, monkeypatch):
    """有产物、但闸门把它们全挡了——这不是"还没有产物"，必须响。"""
    monkeypatch.setattr(BI, "_publishable", lambda topic, root: [u"[G-03/fail] 该章节无配图"])
    assert list((site_gated / u"甲领域").glob("*.html")), u"夹具本身要有产物，这条测试才成立"
    with pytest.raises(RuntimeError) as e:
        BI.build("2026-09-19", str(site_gated))
    assert u"索引" in str(e.value) or u"闸门" in str(e.value)


def _publish_two(site, urls):
    """给夹具里两篇都补上"已发布"记录。URL 只活在 tmp 里，绝不写回真实产物。"""
    for topic, url in urls.items():
        dp = os.path.join(str(site / topic), "data.json")
        data = json.loads(io.open(dp, encoding="utf-8").read())
        data["site"] = {"url": url, "slug": topic.lower(),
                        "content_sha": "x" * 16, "published_date": "2026-09-24",
                        "access": "public"}
        io.open(dp, "w", encoding="utf-8").write(json.dumps(data, ensure_ascii=False))


def test_a_hosted_index_links_to_the_published_sites(site):
    """线上版主页：卡片链各篇的站点 URL，封面内联成 base64。

    为什么封面要内联——主页站自己是一个站，如果卡片图去引各篇文章站的图片 URL，
    任何一篇没发上去或挂了，主页就出现碎图；而主页站本该是自包含的那一个。
    """
    _publish_two(site, {u"甲领域": u"https://jia-abc.qoder.website/",
                        u"乙领域": u"https://yi-abc.qoder.website/"})
    html = io.open(BI.build("2026-09-25", str(site), variant="hosted"),
                   encoding="utf-8").read()
    assert 'href="https://jia-abc.qoder.website/"' in html
    assert "data:image/" in html, "线上版封面没有内联，会依赖别的站"
    assert 'href="甲领域/' not in html, "线上版还在链相对路径，那是本地版"


def test_a_hosted_index_refuses_a_card_without_a_url(site):
    """有一篇没发布，线上版必须**报错**而不是悄悄退回相对路径。

    退回的结果是一个看起来正常、点进去两篇行为不一致的主页：
    一篇跳公网、一篇跳本地文件——在公网托管的站上后者必然 404。
    """
    _publish_two(site, {u"甲领域": u"https://jia-abc.qoder.website/"})
    with pytest.raises(BI.NotPublished):
        BI.build("2026-09-25", str(site), variant="hosted")


def test_the_hosted_index_still_carries_no_runtime_js(site):
    _publish_two(site, {u"甲领域": u"https://jia-abc.qoder.website/",
                        u"乙领域": u"https://yi-abc.qoder.website/"})
    html = io.open(BI.build("2026-09-25", str(site), variant="hosted"),
                   encoding="utf-8").read()
    assert "<script" not in html.lower()
    assert 'name="sort"' in html, "线上版丢了排序控件"


def test_the_local_index_keeps_relative_links_even_after_everything_is_published(site):
    """本地版不许因为"有了 URL"就跟着改链公网。

    开发者的规则是成对的：主页用本地地址时，里面文章也必须是本地地址。
    两个变体各说一件事，混在一起就变成"本地打开的页面点不开"。
    """
    _publish_two(site, {u"甲领域": u"https://jia-abc.qoder.website/",
                        u"乙领域": u"https://yi-abc.qoder.website/"})
    html = io.open(BI.build("2026-09-25", str(site)), encoding="utf-8").read()
    assert "qoder.website" not in html, "本地版被发布记录带跑，去链公网了"
    assert 'href="甲领域/甲领域.html"' in html


def test_collect_reads_categories_and_tags(site):
    entries = BI.collect("2026-09-19")
    assert len(entries) == 2
    by = {e["topic"]: e for e in entries}
    assert by[u"甲领域"]["category"] == u"腕表"
    assert by[u"甲领域"]["tags"][:2] == [u"甲领域", u"腕表"]
    assert by[u"甲领域"]["sections"] >= 5
    assert by[u"甲领域"]["minutes"] >= 1
    assert by[u"甲领域"]["href"].endswith(".html")
    # 封面路径相对 output/ 而非领域目录，否则索引页会 404
    assert by[u"甲领域"]["cover"]["file"] == u"甲领域/images/01_test.jpg"


def test_the_auto_cover_never_picks_a_self_drawn_illustration():
    """索引卡片上没有「示意图 · 非实拍」这行字，拿示意图当门面等于让读者
    以为那是真实照片——比配错图更糟，因为它连"图源"都给不出来。
    人可以显式声明封面（那是要负责的决定），自动规则不行。"""
    photo = {"file": "images/01_实物.jpg", "alt": u"实物", "caption": u"实物",
             "source_page": "https://x/1", "width": 1200, "height": 800}
    drawn = {"file": "images/02_剖面.png", "alt": u"示意图", "caption": u"画的",
             "kind": "illustration", "based_on": ["a#b"], "width": 4000, "height": 2600}
    data = {"sections": [{"id": "s1", "images": [photo, drawn]}]}
    got = BI.cover_of(data)
    assert got["file"] == "images/01_实物.jpg", \
        u"自动封面挑中了示意图（它更宽），索引卡片会把它当成实拍：%s" % (got,)
    declared = dict(data, cover=drawn)
    assert BI.cover_of(declared)["file"] == "images/02_剖面.png", \
        u"人显式声明的封面被自动规则否了"


def test_cover_prefers_the_widest_image_and_has_no_size_floor(site):
    """门槛式筛选会把整面照片墙退成渐变（2026-09-19 开发者反馈"封面没显示出来"）。
    正确做法：永远给一张封面，防放大交给模板的 --cover-w 封顶。"""
    for e in BI.collect("2026-09-19"):
        d = os.path.join(str(site), e["topic"], "data.json")
        data = json.loads(io.open(d, encoding="utf-8").read())
        widths = []
        for i, s in enumerate(data["sections"]):
            for im in s.get("images") or []:
                im["width"] = 700 + i
                widths.append(im["width"])
        picked = BI.cover_of(data)
        assert picked is not None, u"%s：小图被门槛筛掉了" % e["topic"]
        assert (picked.get("width") or 0) == max(widths), "没选最宽的那张"


def test_minutes_use_the_same_ruler_as_G05(site):
    """索引显示的分钟数必须和篇幅闸门同一口径，否则两处数字会互相打脸。"""
    e = BI.collect("2026-09-19")[0]
    data = json.loads(io.open(os.path.join(str(site), e["topic"], "data.json"),
                              encoding="utf-8").read())
    bar = V._bar()
    per_min = bar["reading"]["assumed_chinese_chars_per_minute"]
    imgs = sum(len(s.get("images") or []) for s in data["sections"])
    assert e["minutes"] == max(1, int(round(BI.cjk(data) / float(per_min) + imgs * 0.15)))


def test_build_emits_category_feed_with_tags(site):
    path = BI.build("2026-09-19")
    assert path and os.path.isfile(path)
    html = io.open(path, encoding="utf-8").read()
    # 单一连续 feed：类别锚点挂在每类第一张卡片上，不再是 per-category 网格
    assert 'id="cat-腕表"' in html and 'id="cat-汽车"' in html
    assert html.count('<div class="feed">') == 1, "又切回多个 feed 网格了"
    assert html.count('<a class="card"') == 2
    assert "#甲领域" in html and "#腕表" in html, "tag 没渲染出来"
    assert "分钟" in html and "章" in html


def test_a_card_knows_the_day_it_was_created_not_the_day_it_was_rerendered(site):
    """W-128 那条性质不变，W-145 换了它的载体。

    原来"第一次上架是哪天"读的是**最早那篇日期页**的文件名——那要求旧日期页一直留着。
    一篇只留一页之后没有"最早那篇"可读，所以创建时间必须落在 `data.json.created_date`：
    写一次、`--offline` 重渲染永不改写。`generated_date` 不能顶替，它每次都变。
    """
    dp = os.path.join(str(site / u"甲领域"), "data.json")
    data = json.loads(io.open(dp, encoding="utf-8").read())
    data["created_date"] = "2026-09-12"
    data["generated_date"] = "2026-09-24"
    io.open(dp, "w", encoding="utf-8").write(json.dumps(data, ensure_ascii=False))

    entries = {e["topic"]: e for e in BI.collect()}
    assert entries[u"甲领域"]["created"] == "2026-09-12", \
        u"创建时间被重渲染日期污染：%s" % (entries[u"甲领域"],)
    assert entries[u"甲领域"]["href"].endswith(u"甲领域.html"), \
        u"卡片链接该指那一页稳定的文件：%s" % entries[u"甲领域"]["href"]


def test_a_page_without_a_created_date_falls_back_and_says_so(site, capsys):
    """缺 `created_date` 的旧产物不能静默排到最后——那看起来像"它最新"。

    退到 `generated_date` 是没办法的办法，所以必须**喊一声**：
    谁看见顺序不对，得能从 stderr 知道是这个字段没回填。
    """
    dp = os.path.join(str(site / u"甲领域"), "data.json")
    data = json.loads(io.open(dp, encoding="utf-8").read())
    data.pop("created_date", None)
    data["generated_date"] = "2026-09-19"
    io.open(dp, "w", encoding="utf-8").write(json.dumps(data, ensure_ascii=False))

    entries = {e["topic"]: e for e in BI.collect()}
    assert entries[u"甲领域"]["created"] == "2026-09-19"
    err = capsys.readouterr().err
    assert u"created_date" in err, \
        u"退到 generated_date 却没留下任何话，下次没人知道顺序为什么可疑"


def test_the_index_sorts_by_creation_date_both_ways_without_runtime_js(site):
    """升序/降序用 CSS `order` + `:has()` 做，不引 JS——
    `test_index_is_self_contained` 钉着"索引页不该带运行时 JS"，
    为一个排序按钮破掉它不值，而且浏览器不支持 `:has()` 时
    无条件那条 `.card{order:var(--desc)}` 照样给出"最新在前"，只是切换失效。"""
    html = io.open(BI.build("2026-09-19"), encoding="utf-8").read()
    assert 'name="sort"' in html, "没有排序控件"
    assert html.count('type="radio"') == 2, "升序/降序两个选项才叫排序"
    asc = [int(x) for x in re.findall(r"--asc:(\d+)", html)]
    desc = [int(x) for x in re.findall(r"--desc:(\d+)", html)]
    assert asc and asc == sorted(asc), "DOM 顺序没按创建时间升序排，--asc 就是假的"
    assert len(asc) == len(desc) == 2
    assert [a + d for a, d in zip(asc, desc)] == [len(asc) - 1] * len(asc), \
        u"两个方向不是互为倒序：%s / %s" % (asc, desc)
    assert "body:has(#sort-old:checked)" in html, \
        u"升序那条规则没接上，切换按钮是死的（挂在 .feed 上不算——radio 不是它的后代）"
    assert "<script" not in html.lower()


def test_a_card_shows_its_creation_date(site):
    """排序键必须看得见，否则读者只会觉得卡片顺序莫名其妙。"""
    html = io.open(BI.build("2026-09-19"), encoding="utf-8").read()
    assert html.count('class="cdate"') == 2, "卡片上没有创建日期"
    assert "09-19" in html


def test_index_is_self_contained(site):
    path = BI.build("2026-09-19")
    html = io.open(path, encoding="utf-8").read()
    assert not re.search(r'<(script|link)\b[^>]*(?:src|href)=["\']https?://', html, re.I)
    assert "<script" not in html.lower(), "索引页不该带运行时 JS"
    assert html.count("<style>") == 1


def test_a_card_without_a_cover_is_typographic_not_an_empty_frame(site):
    """无封面的卡片以前只有一块品牌色渐变（`CoverArt` 是个 `aria-hidden` 的纯渐变），
    读者看到的就是"图裂了"——开发者 09-20 在主页上就是这么报的
    （LV 正在重做、data.json 处于"引用已清空"的中途态，索引恰好在那时被重建）。
    没有图也必须是一张**排版封面**，不是一个坏掉的图框。"""
    dp = os.path.join(str(site), u"甲领域", "data.json")
    data = json.loads(io.open(dp, encoding="utf-8").read())
    for s in data["sections"]:
        s["images"] = []
    io.open(dp, "w", encoding="utf-8").write(json.dumps(data, ensure_ascii=False))

    html = io.open(BI.build("2026-09-19"), encoding="utf-8").read()
    card = html[html.index('href="甲领域/'):]
    head = card[:card.index('class="bd"')]
    assert 'class="ph-word"' in head, u"无封面卡片没有排版层，看着像图裂：%s" % head[:220]
    assert u"甲领域" in head[head.index('class="ph-word"'):][:80], "排版封面没带上领域名"
    assert "<img" not in head, "没有封面却还留着 img 标签"


def test_G12_passes_on_a_good_index(site):
    BI.build("2026-09-19")
    assert [str(f) for f in V.g12_index(None) if f.level == "fail"] == []


def test_G12_flags_dead_card_link(site):
    BI.build("2026-09-19")
    shutil.rmtree(os.path.join(str(site), u"甲领域"))
    fails = [f for f in V.g12_index(None) if f.level == "fail"]
    assert any("不存在" in str(f) for f in fails), "卡片链接失效却没报错"


def test_G12_flags_missing_index(site):
    os.remove(os.path.join(str(site), "index.html")) if os.path.isfile(
        os.path.join(str(site), "index.html")) else None
    fails = [f for f in V.g12_index(None) if f.level == "fail"]
    assert any("缺少索引主页" in str(f) for f in fails)


def test_G12_flags_uncategorised_topic(site):
    """没配 category 的专题会掉进"未归类"，索引上看得出来，就该报错。"""
    dp = os.path.join(str(site), u"甲领域", "data.json")
    data = json.load(io.open(dp, encoding="utf-8"))
    data["category"] = ""
    io.open(dp, "w", encoding="utf-8").write(json.dumps(data, ensure_ascii=False))
    BI.build("2026-09-19")
    fails = [f for f in V.g12_index(None) if f.level == "fail"]
    assert any("未归类" in str(f) for f in fails)


def test_outline_schema_requires_category_and_tags():
    """category/tags 是索引归类与归档检索的依据，缺了就不该通过大纲校验。"""
    schema = json.load(io.open(os.path.join(BI.ROOT, "config", "topic_outline.schema.json"),
                               encoding="utf-8"))
    assert "category" in schema["required"] and "tags" in schema["required"]
    data_schema = json.load(io.open(
        os.path.join(BI.ROOT, "config", "topic_data.schema.json"), encoding="utf-8"))
    assert "category" in data_schema["required"]


def test_every_seed_outline_declares_category_and_tags():
    import outline as O
    cats = {}
    for t in O.available_topics(root=BI.ROOT):
        raw = json.load(io.open(os.path.join(BI.ROOT, "config", "topics", t + ".json"),
                                encoding="utf-8"))
        assert raw.get("category"), "%s 缺 category" % t
        assert len(raw.get("tags") or []) >= 3, "%s tags 太少，归档检索没抓手" % t
        cats.setdefault(raw["category"], []).append(t)
    assert len(cats) >= 3, "类别太少，索引的归类导航没有意义"


def test_all_mode_runs_geometry_gate_on_the_index(site):
    """W-11b：`--all` 扫了索引的 G-12，却从没扫过索引的几何——
    索引页是全站入口，它跑版没人知道。"""
    BI.build("2026-09-19")
    idx = os.path.join(str(site), "index.html")
    good = [f for f in V.run(gate_filter="G-13")[0] if "index.html" in str(f)]
    assert good == [], u"干净索引不该有几何问题：%s" % [str(f) for f in good]
    html = io.open(idx, encoding="utf-8").read()
    io.open(idx, "w", encoding="utf-8").write(
        html.replace("</style>", ".feed{width:4000px}</style>", 1))
    findings = [f for f in V.run(gate_filter="G-13")[0] if "index.html" in str(f)]
    assert findings, "索引页跑版了，--all 却没抓到"
