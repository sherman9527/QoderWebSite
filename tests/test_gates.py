# -*- coding: utf-8 -*-
"""逐条闸门的正反例（tasks 7.2–7.6）。

只测"合法输入不报错"等于没测——每条都必须有一个破坏性反例，
否则闸门可能在永远返回空列表的情况下"通过"。
"""
import copy
import io
import json
import os
import re
import shutil

import pytest

import validate as V
from conftest import make_passing_data, make_passing_html, write_image

ALL_GATES = V.DOMAIN_GATES


def run(gate, ctx):
    return gate.check(ctx) or []


def by_id(gid):
    for g in ALL_GATES:
        if g.id == gid:
            return g
    raise KeyError(gid)


# ------------------------------------------------------------------ 元测试

def test_every_gate_has_id_and_spec():
    for g in ALL_GATES:
        assert g.id.startswith("G-"), g
        assert g.spec_ref and os.path.isfile(os.path.join(
            V.ROOT, "openspec", "changes", "build-knowledge-html-generator", g.spec_ref)), g.id


def test_gate_ids_are_explicit_and_stable():
    """编号显式绑定，不按位置生成：加一条闸门不得让既有闸门改号。"""
    assert [g.id for g in ALL_GATES] == [
        "G-01", "G-02", "G-03", "G-04", "G-05", "G-06", "G-07", "G-08", "G-09", "G-10", "G-13"]
    glob = [g.id for g in V.GATES if g.scope == "global"]
    assert glob == ["G-12", "G-14"], "全站级闸门应单独标注，不参与逐领域校验"


# ------------------------------------------------------------------ 全绿基线

@pytest.mark.parametrize("gate", ALL_GATES, ids=lambda g: g.id)
def test_valid_input_passes_all_gates(gate, passing_ctx, monkeypatch):
    # 让"当前模板指纹"等于夹具里写的那份，否则 G-08 会去跑 node
    monkeypatch.setattr(V, "current_fingerprint", lambda: json.loads(
        V.re.search(r"<!--template-fingerprint:(.*?)-->", passing_ctx.html, V.re.S).group(1)))
    findings = run(gate, passing_ctx)
    fails = [f for f in findings if f.level == "fail"]
    assert not fails, "%s 误报：%s" % (gate.id, [str(f) for f in fails])


# ------------------------------------------------------------------ 反例

def test_G01_rejects_wrong_filename(passing_ctx, tmp_path):
    bad = tmp_path / "output" / passing_ctx.topic / "随手起的名字.html"
    bad.parent.mkdir(parents=True, exist_ok=True)
    bad.write_text(passing_ctx.html, encoding="utf-8")
    ctx = copy.copy(passing_ctx)
    ctx.page_path = str(bad)
    assert run(by_id("G-01"), ctx), "文件名不合规却没报错"


def test_G01_rejects_a_dated_page_name(passing_ctx):
    """W-145：日期名从此不合法——一篇只有一页，名字是 `<领域>.html`。

    不是审美问题：日期名会让每篇的深层链接每天变一次，`web_list.md` 里记的 URL
    跟着失效——即使内容一字未改。稳定名让"要不要重发"由内容指纹决定，不由日历决定。
    接受那一侧由 `test_valid_input_passes_all_gates[G-01]` 守（夹具已经是稳定名）。
    """
    dated = os.path.join(passing_ctx.out_dir, "%s_2026-09-19.html" % passing_ctx.topic)
    shutil.copyfile(passing_ctx.page_path, dated)
    ctx = copy.copy(passing_ctx)
    ctx.page_path = dated
    try:
        findings = run(by_id("G-01"), ctx)
    finally:
        os.remove(dated)
    assert any(u"文件名" in str(f) for f in findings), \
        "带日期的文件名又被放行了：%s" % [str(f) for f in findings]


def test_G01_rejects_a_second_page_in_the_same_topic_dir(passing_ctx):
    """日期页不许重新堆积——**用闸门挡，不靠约定**。

    这条是 W-145 的护栏：同目录再出现第二个 `.html` 就当场判死。否则"只保留最新版"
    会在下一次手工复制时悄悄破掉，而破掉之后的样子和正常状态一模一样。
    """
    twin = os.path.join(passing_ctx.out_dir, "旧版.html")
    io.open(twin, "w", encoding="utf-8").write("<html></html>")
    try:
        assert run(by_id("G-01"), passing_ctx), \
            "同目录多了一页，G-01 却没说话——那日期页会重新堆回来"
    finally:
        os.remove(twin)


def test_a_topic_is_found_by_its_stable_page_name(tmp_path):
    """`build_ctx` 靠文件名找页面，换成稳定名之后它必须还认得。

    这条单独存在是因为改名不是"去掉后缀"这么轻：**发现逻辑与命名规则是两处代码**，
    只改 G-01 会让闸门去判一个 `build_ctx` 根本找不到的页面。
    """
    topic = "测试领域"
    d = tmp_path / "output" / topic
    d.mkdir(parents=True)
    (d / (topic + ".html")).write_text("<html></html>", encoding="utf-8")
    (d / "data.json").write_text("{}", encoding="utf-8")
    ctx, pre = V.build_ctx(topic, str(tmp_path / "output"))
    assert ctx is not None, "稳定文件名没被认出来：%s" % [str(f) for f in pre]


def test_G01_judges_a_pending_candidate_by_its_resolved_name(passing_ctx):
    """换名协议判的是 `<领域>.html.pending`——G-01 要比的是"它发布出去叫什么"。

    这条是被集成套件逼出来的：我第一版让 G-01 直接看临时文件的 basename，
    于是每一次正常发布都被判死，而它抱怨的那个名字恰恰是协议要求的样子。
    闸门不能要求被检对象先变成它自己还没变成的东西。
    """
    pending = os.path.join(passing_ctx.out_dir, "%s.html.pending" % passing_ctx.topic)
    shutil.copyfile(passing_ctx.page_path, pending)
    ctx = copy.copy(passing_ctx)
    ctx.page_path = pending
    try:
        findings = [str(f) for f in run(by_id("G-01"), ctx)]
    finally:
        os.remove(pending)
    assert not any(u"文件名" in f for f in findings), \
        u"候选页被自己的临时名判死了：%s" % findings


def test_G14_fails_when_the_ledger_disagrees_with_the_products(monkeypatch, tmp_path):
    """G-14 判"账实相符"：`web_list.md` 是派生物，与各篇 `data.json.site` 不一致就是 fail。

    为什么值得开一条闸门：一份东西活在几处迟早会不一致，这条项目已经付过两次学费
    （示意图的三处、封面声明）。派生物一旦允许手改，它就会在某个时刻说出
    一个并不存在的事实，而没人会去怀疑一张清单。
    """
    import publish as PUB
    out = tmp_path / "output"
    (out / u"咖啡").mkdir(parents=True)
    (out / u"咖啡" / "images").mkdir()
    (out / u"咖啡" / "咖啡.html").write_text(
        u'<html><body><img src="images/01_a.jpg" alt="x"/></body></html>',
        encoding="utf-8")
    (out / u"咖啡" / "images" / "01_a.jpg").write_bytes(b"\xff\xd8\xff\xe0" + b"0" * 500)
    (out / u"咖啡" / "data.json").write_text(json.dumps({
        "topic": u"咖啡", "category": u"饮食", "tags": [], "generated_date": "2026-09-25",
        "theme": {"token": "coffee-roast"}, "sections": [], "sources": [],
        "site": {"url": u"https://coffee-abc.qoder.website/", "slug": "coffee",
                 "content_sha": "deadbeefdeadbeef", "published_date": "2026-09-25",
                 "access": u"public"},
    }, ensure_ascii=False), encoding="utf-8")
    (tmp_path / "web_list.md").write_text(u"# 手写的假清单\n", encoding="utf-8")
    monkeypatch.setattr(V, "ROOT", str(tmp_path))
    monkeypatch.setattr(V, "OUTPUT", str(out))
    findings = V.g14_ledger(None)
    assert findings, "账本与产物不一致，G-14 却没说话"


def test_G14_is_silent_when_nothing_has_been_published(monkeypatch, tmp_path):
    """一篇都没发布时不该报——"还没有账本"和"账本错了"是两件事。

    这条防的是：新克隆的仓库、或者第一次发布之前，全站被一条与内容无关的
    闸门判死，那只会让人去关掉闸门。
    """
    out = tmp_path / "output"
    out.mkdir()
    monkeypatch.setattr(V, "ROOT", str(tmp_path))
    monkeypatch.setattr(V, "OUTPUT", str(out))
    assert not V.g14_ledger(None)


def test_G02_rejects_missing_section(passing_ctx):
    data = copy.deepcopy(passing_ctx.data)
    dropped = data["sections"].pop()
    ctx = copy.copy(passing_ctx)
    ctx.data = data
    f = run(by_id("G-02"), ctx)
    assert any(dropped["id"] in str(x) for x in f), "缺章节却没报错"


def test_G02_rejects_empty_section(passing_ctx):
    data = copy.deepcopy(passing_ctx.data)
    data["sections"][2]["blocks"] = [{"type": "note", "tone": "tip", "text": "太短"}]
    ctx = copy.copy(passing_ctx)
    ctx.data = data
    assert run(by_id("G-02"), ctx)


def test_G02_flags_undeclared_section(passing_ctx):
    data = copy.deepcopy(passing_ctx.data)
    extra = copy.deepcopy(data["sections"][0])
    extra["id"] = "sec-extra"
    data["sections"].append(extra)
    ctx = copy.copy(passing_ctx)
    ctx.data = data
    ctx._outline = type("o", (), {
        "words_range": passing_ctx._outline.words_range,
        "sections": passing_ctx._outline.sections,
    })()
    assert any("sec-extra" in str(x) for x in run(by_id("G-02"), ctx))


def test_G03_rejects_missing_image_file(passing_ctx):
    os.remove(os.path.join(passing_ctx.out_dir, "images", "03_test.jpg"))
    f = run(by_id("G-03"), passing_ctx)
    assert any("不存在" in str(x) for x in f), "图片文件被删却没报错"


def test_G03_rejects_too_few_images(passing_ctx):
    data = copy.deepcopy(passing_ctx.data)
    for s in data["sections"][3:]:
        s["images"] = []
    ctx = copy.copy(passing_ctx)
    ctx.data = data
    ctx.html = make_passing_html(data)
    assert run(by_id("G-03"), ctx)


def test_G03_rejects_remote_image_and_empty_alt(passing_ctx):
    html = passing_ctx.html.replace('src="images/01_test.jpg"',
                                    'src="https://cdn.example.com/x.jpg"')
    html = html.replace('alt="第 2 章测试配图"', 'alt=""')
    ctx = copy.copy(passing_ctx)
    ctx.html = html
    msgs = [str(x) for x in run(by_id("G-03"), ctx)]
    assert any("远程" in m for m in msgs), msgs
    assert any("alt" in m for m in msgs), msgs


def test_G03_flags_orphan_image(passing_ctx):
    open(os.path.join(passing_ctx.out_dir, "images", "99_orphan.jpg"), "wb").write(b"x")
    assert any("孤儿" in str(x) for x in run(by_id("G-03"), passing_ctx))


def test_G03_orphan_check_only_looks_at_image_files(passing_ctx):
    """W-105 把召回统计 `search-stats.json` 落在 images/ 里，G-03 当场把大模型篇判死：
    `孤儿图片：产物未引用`。它不是图片。孤儿判据按图片扩展名筛，
    顺带取代原来那句"只放过 manifest"的特例——那是同一个漏洞的上一种写法。
    真孤儿（没人引用的 .jpg）照样要报。"""
    d = passing_ctx.out_dir
    io.open(os.path.join(d, "images", "search-stats.json"), "w", encoding="utf-8").write("{}")
    open(os.path.join(d, "images", "97_junk.jpg"), "wb").write(b"x")
    msgs = [str(x) for x in run(by_id("G-03"), passing_ctx)]
    assert not any("search-stats" in m for m in msgs),         u"非图片文件被判成孤儿图片：%s" % [m for m in msgs if u"孤儿" in m][:2]
    assert any("97_junk" in m for m in msgs), u"真孤儿却漏了"


def test_G03_does_not_call_another_pages_image_an_orphan(passing_ctx):
    """孤儿判据必须是"这个领域磁盘上没有任何一页用它"，不是"当前这一页没用它"。
    差别的代价实测过：重做配图之后、索引换到新页面之前，入口页指着的是上一版，
    上一版引用的正是这批"当前页没引用"的文件。判成孤儿，流水线就只能赶在发布之前
    删掉它们（G-03 不过就 return），被索引那一页当场断图——09-21 百达翡丽 18 个破链。
    """
    d = passing_ctx.out_dir
    io.open(os.path.join(d, u"咖啡_2026-09-18.html"), "w", encoding="utf-8").write(
        '<html><img src="images/99_yesterday.jpg" alt="上一版在用的图"></html>')
    open(os.path.join(d, "images", "99_yesterday.jpg"), "wb").write(b"x")
    open(os.path.join(d, "images", "98_junk.jpg"), "wb").write(b"x")
    msgs = [str(x) for x in run(by_id("G-03"), passing_ctx)]
    assert not any("99_yesterday" in m for m in msgs), \
        u"上一版页面还在用的图被判成孤儿：%s" % [m for m in msgs if "孤儿" in m][:3]
    assert any("98_junk" in m for m in msgs), u"谁都没用的真孤儿却漏了：%s" % msgs[:3]


def test_G04_rejects_external_resources(passing_ctx):
    for inj, label in [
        ('<script src="https://cdn.example.com/a.js"></script>', "script"),
        ('<link rel="stylesheet" href="https://fonts.example.com/f.css">', "link"),
        ("<style>@import url('https://x.example.com/y.css');</style>", "import"),
        ('<img src="https://host/x.jpg" alt="x">', "远程图片"),
    ]:
        ctx = copy.copy(passing_ctx)
        ctx.html = passing_ctx.html + inj
        assert run(by_id("G-04"), ctx), "未拦下外链：" + label


def test_G05_rejects_short_and_long_text(passing_ctx):
    data = copy.deepcopy(passing_ctx.data)
    for s in data["sections"]:
        for b in s["blocks"]:
            if b["type"] == "prose":
                b["text"] = "短"
    ctx = copy.copy(passing_ctx)
    ctx.data = data
    assert any("低于" in str(x) for x in run(by_id("G-05"), ctx))

    data2 = copy.deepcopy(passing_ctx.data)
    for s in data2["sections"]:
        for b in s["blocks"]:
            if b["type"] == "prose":
                b["text"] = b["text"] * 40
    ctx2 = copy.copy(passing_ctx)
    ctx2.data = data2
    assert any("超过" in str(x) for x in run(by_id("G-05"), ctx2))


def test_G05_follows_the_outline_not_a_hardcoded_band(passing_ctx):
    """篇幅区间必须来自大纲。写死在代码里，改大纲就会静默失效。"""
    ctx = copy.copy(passing_ctx)
    loose = type("o", (), {
        "words_range": (10, 999999), "sections": passing_ctx._outline.sections})()
    assert not run(by_id("G-05"), _with(ctx, outline=loose)), "放宽区间后仍报错，说明闸门没读大纲"
    tight = type("o", (), {
        "words_range": (9000, 12000), "sections": passing_ctx._outline.sections})()
    assert run(by_id("G-05"), _with(ctx, outline=tight)), "收紧区间后没报错，说明闸门没读大纲"


def _with(ctx, **over):
    c = copy.copy(ctx)
    for k, v in over.items():
        setattr(c, "_" + k if hasattr(c, "_" + k) else k, v)
    return c


def test_G06_rejects_unsourced_number(passing_ctx):
    data = copy.deepcopy(passing_ctx.data)
    data["sections"][0]["blocks"][1]["rows"][0].pop("source_ids")
    ctx = copy.copy(passing_ctx)
    ctx.data = data
    assert any("无来源" in str(x) for x in run(by_id("G-06"), ctx))


def test_G06_rejects_price_table_without_as_of(passing_ctx):
    data = copy.deepcopy(passing_ctx.data)
    data["sections"][1]["blocks"][1]["as_of"] = "2026"
    ctx = copy.copy(passing_ctx)
    ctx.data = data
    assert any("as_of" in str(x) for x in run(by_id("G-06"), ctx))


def test_G06_rejects_blacklisted_source_domain(passing_ctx):
    data = copy.deepcopy(passing_ctx.data)
    data["sources"][0]["url"] = "https://baijiahao.baidu.com/x?id=1"
    ctx = copy.copy(passing_ctx)
    ctx.data = data
    assert any("黑名单" in str(x) for x in run(by_id("G-06"), ctx))


def test_G06_rejects_dangling_source_reference(passing_ctx):
    data = copy.deepcopy(passing_ctx.data)
    data["sections"][0]["blocks"][2]["facts"][0]["source_ids"] = ["S999"]
    ctx = copy.copy(passing_ctx)
    ctx.data = data
    assert any("S999" in str(x) for x in run(by_id("G-06"), ctx))


def test_G07_rejects_placeholders(passing_ctx):
    data = copy.deepcopy(passing_ctx.data)
    data["sections"][0]["blocks"][0]["text"] += "\nTODO 这段还没写完"
    ctx = copy.copy(passing_ctx)
    ctx.data = data
    assert any("占位" in str(x) for x in run(by_id("G-07"), ctx))


def test_G08_rejects_missing_and_stale_fingerprint(passing_ctx):
    ctx = copy.copy(passing_ctx)
    ctx.html = V.re.sub(r"<!--template-fingerprint:.*?-->", "", passing_ctx.html, flags=V.re.S)
    assert run(by_id("G-08"), ctx), "手工编辑过的产物（无指纹）应被拦下"

    stale = make_passing_html(passing_ctx.data, fingerprint=json.dumps(
        {"blocks": ["prose"], "rev": "ke-template-0"}))
    ctx2 = copy.copy(passing_ctx)
    ctx2.html = stale
    ctx2.data = passing_ctx.data
    assert run(by_id("G-08"), ctx2), "旧模板产物应被识别为需要重渲染"


def test_G09_is_empty_when_no_active_red_lines(monkeypatch):
    monkeypatch.setattr(V, "active_red_lines", lambda: [])
    # 无生效红线时 G-09 不应产生任何 fail，但也不该报错
    assert run(by_id("G-09"), _stub_ctx()) == []


def test_G09_honours_added_red_line(monkeypatch, passing_ctx):
    monkeypatch.setattr(V, "active_red_lines",
                        lambda: [("R-01", u"产物禁止任何外部网络资源")])
    ctx = copy.copy(passing_ctx)
    ctx.html = passing_ctx.html + '<link rel="stylesheet" href="https://x.example.com/a.css">'
    assert any("R-01" in str(x) for x in run(by_id("G-09"), ctx))


def test_G10_rejects_schema_violation(passing_ctx):
    data = copy.deepcopy(passing_ctx.data)
    data["sections"][0]["blocks"][0]["type"] = "hover_table"
    ctx = copy.copy(passing_ctx)
    ctx.data = data
    assert run(by_id("G-10"), ctx), "非法区块类型没被 schema 拦下"


def test_G10_rejects_bad_image_path_pattern(passing_ctx):
    data = copy.deepcopy(passing_ctx.data)
    data["sections"][0]["images"][0]["file"] = "img/nope.jpeg"
    ctx = copy.copy(passing_ctx)
    ctx.data = data
    assert run(by_id("G-10"), ctx)


def _stub_ctx():
    bar = json.load(open(os.path.join(V.CONFIG, "quality_bar.json"), encoding="utf-8"))
    return V.Ctx("stub", "/tmp", "/tmp/stub_2026-09-19.html", "<html></html>",
                 {"sections": [], "sources": []}, bar, outline=object())


def test_theme_distance_flags_twin_palettes(monkeypatch, tmp_path):
    """两页配色雷同必须报错——10 页趋同是 AI 生成页最明显的破绽。"""
    (tmp_path / "A").mkdir()
    (tmp_path / "B").mkdir()
    monkeypatch.setattr(V, "OUTPUT", str(tmp_path))
    monkeypatch.setattr(V, "palette_of",
                        lambda t: ["#FFFFFF", "#111111", "#222222"])
    bar = json.load(open(os.path.join(V.CONFIG, "quality_bar.json"), encoding="utf-8"))
    f = V._cross_domain_theme(bar)
    assert f and "雷同" in str(f[0])


# --- G-11 的量法：身份色，不是"三块颜色一起平均" ------------------------------------
# 09-21 实测：`validate.py --all` 报 42/55 对雷同。原因不是 11 套主题真的趋同，
# 而是判据把**底色**也平均进了距离——而底色本来就该是可读的纸白/深色，
# 两片米白之间 ΔE 只有 1.7，于是"咖啡底 + 完全不同的品牌色"也被拖到线下。
# 一个 90% 时间都在狼来了的闸门等于没有闸门（而且它把 52 条真 G-03 fail 埋了）。

def test_G11_ignores_a_shared_background_when_identity_colors_differ(monkeypatch, tmp_path):
    """同一底色 + 不同身份色不该判成雷同。
    夹具就是 09-21 实测到的假阳性那一堆：劳力士（深绿 + 银）vs 浪琴（石板蓝 + 银），
    底色 ΔE 1.7、主色 ΔE 46，只有银色强调色相近——旧量法把三块一起平均，
    判它们"雷同"（实测 19.3 < 60）。"""
    (tmp_path / "A").mkdir()
    (tmp_path / "B").mkdir()
    monkeypatch.setattr(V, "OUTPUT", str(tmp_path))
    pals = {"A": ["#F5F7F6", "#0F6B3D", "#A9B0B6"],
            "B": ["#F4F5F7", "#4A5A6A", "#8B97A3"]}
    monkeypatch.setattr(V, "palette_of", lambda t: pals[t])
    bar = json.load(open(os.path.join(V.CONFIG, "quality_bar.json"), encoding="utf-8"))
    assert not V._cross_domain_theme(bar), "同一底色 + 不同身份色被误判成雷同"


def test_G11_flags_twins_even_if_the_background_differs(monkeypatch, tmp_path):
    """反过来：换一张底色不能蒙混过关——身份色两个都近，就是同一张皮。"""
    (tmp_path / "A").mkdir()
    (tmp_path / "B").mkdir()
    monkeypatch.setattr(V, "OUTPUT", str(tmp_path))
    pals = {"A": ["#FFFFFF", "#33261A", "#C08A4E"],
            "B": ["#121212", "#3A2C20", "#C79155"]}
    monkeypatch.setattr(V, "palette_of", lambda t: pals[t])
    bar = json.load(open(os.path.join(V.CONFIG, "quality_bar.json"), encoding="utf-8"))
    f = V._cross_domain_theme(bar)
    assert f and "雷同" in str(f[0]), "身份色几乎一样、只换了底色，没判成雷同"


def test_the_real_theme_set_is_not_a_wall_of_twins(monkeypatch, tmp_path):
    """闸门必须对着真色板成立。阈值 60 从来没人量过：真 11 套主题按它就全灭，
    于是"配色不得雷同"变成一句永远在响、也永远没人看的警报。
    这条测试钉住的是"裁判说的是人话"，顺带让新领域的色板在 commit 时就被查一次雷同
    ——查的是全部大纲领域，不是只查已经生成过的那几个。"""
    import glob
    topics = sorted(os.path.basename(p)[:-5] for p in
                    glob.glob(os.path.join(V.CONFIG, "topics", "*.json")))
    assert topics, "没找到任何领域大纲，这条测试就是空转"
    for t in topics:
        assert V.palette_of(t), "领域 %s 取不到色板（token 没进 index.ts？）" % t
        (tmp_path / t).mkdir()
    monkeypatch.setattr(V, "OUTPUT", str(tmp_path))
    bar = json.load(open(os.path.join(V.CONFIG, "quality_bar.json"), encoding="utf-8"))
    findings = V._cross_domain_theme(bar)
    assert not findings, "真主题过不了 G-11：%s" % [str(f) for f in findings][:4]


def test_G13_is_a_real_browser_gate_not_a_stub(passing_ctx):
    """G-13 必须真的会红。一个永远返回空的闸门比没有闸门更糟——它会让人以为查过了。"""
    g = by_id("G-13")
    import subprocess, json, os
    if not os.path.isfile(os.path.join(V.ROOT, "scripts", "measure-layout.mjs")):
        pytest.skip("measure-layout.mjs 不存在")
    # 好产物：应当无 fail（浏览器不可用时会给出 fail，那也是诚实的结果）
    good = [f for f in (g.check(passing_ctx) or []) if f.level == "fail"]
    assert not good or "浏览器不可用" in str(good[0]), [str(f) for f in good][:3]


def test_G13_detects_a_deliberately_broken_page(tmp_path, quality_bar):
    """把已知缺陷注回产物，G-13 必须抓到——否则这条闸门等于没写。"""
    real = os.path.join(V.ROOT, "demo_site", "output", u"咖啡")
    page = os.path.join(real, u"咖啡_2026-09-19.html")
    if not os.path.isfile(page):
        pytest.skip("没有 demo 产物可用于注错")
    src = io.open(page, encoding="utf-8").read()
    bad = src.replace('</div><div class="cover-body">', '<div class="cover-body">')
    bad = bad.replace('</div></header>', '</div></div></header>')
    # 标题被塞进 cover-media 之后还得让它真的裁得到：无封面时那层是 height:auto，
    # 且 .cover-noimg .cover-media 的特异性更高，注错必须一起压住。
    inj = ".cover-media,.cover-noimg .cover-media{height:140px;min-height:0}"
    bad = bad.replace("</style>", inj + "</style>", 1)
    assert bad != src, "注错锚点失效，需同步更新本测试"
    assert bad.index(inj) > bad.index("--measure"), \
        "注错样式必须排在页面样式之后，否则被覆盖"
    d = tmp_path / u"咖啡"; (d / "images").mkdir(parents=True)
    p = d / (u"咖啡_2026-09-19.html"); p.write_text(bad, encoding="utf-8")
    ctx = V.Ctx(u"咖啡", str(d), str(p), bad, {"sections": [], "sources": []}, quality_bar)
    fails = [f for f in (by_id("G-13").check(ctx) or []) if f.level == "fail"]
    assert any("h1" in str(f) or "浏览器不可用" in str(f) for f in fails),         "标题被 overflow:hidden 裁掉，G-13 却没报错"


@pytest.mark.parametrize("css,gate", [
    ("p,li{max-width:none}", "prose-measure"),
    (".figs .ratio{width:1150px;aspect-ratio:1/1}", "fig-wall"),
    (".figs .ratio{width:1150px;aspect-ratio:1/1}", "img-upscale"),
])
def test_G13_detects_wide_screen_defects(tmp_path, quality_bar, css, gate):
    """2026-09-19 开发者反馈"内容不自适应"暴露的三类缺陷：正文拉满整屏、
    一张图吃掉一屏、小图被放大成糊图。注回去，闸门必须各抓各的。"""
    real = os.path.join(V.ROOT, "demo_site", "output", u"咖啡")
    page = os.path.join(real, u"咖啡_2026-09-19.html")
    if not os.path.isfile(page):
        pytest.skip("没有 demo 产物可用于注错")
    src = io.open(page, encoding="utf-8").read()
    bad = src.replace("</style>", "%s</style>" % css, 1)
    assert bad != src, "注错锚点失效，需同步更新本测试"
    assert bad.index(css) > bad.index("--measure"), "注错样式排在页面样式之前会被覆盖"
    d = tmp_path / u"咖啡"; (d / "images").mkdir(parents=True)
    for f in os.listdir(os.path.join(real, "images")):
        shutil.copyfile(os.path.join(real, "images", f), os.path.join(str(d), "images", f))
    p = d / (u"咖啡_2026-09-19.html"); p.write_text(bad, encoding="utf-8")
    ctx = V.Ctx(u"咖啡", str(d), str(p), bad, {"sections": [], "sources": []}, quality_bar)
    fails = [f for f in (by_id("G-13").check(ctx) or []) if f.level == "fail"]
    assert any(gate in str(f) for f in fails), "%s 注错后 G-13 没抓到（实际：%s）" % (
        gate, [str(f).split(u"：", 1)[-1][:70] for f in fails][:8])


def test_cjk_count_only_counts_hanzi():
    assert V.cjk_count(u"咖啡 100 元 abc") == 3  # 咖啡 + 元
    assert V.cjk_count("ABC 123 -!") == 0
    assert V.cjk_count(u"咖啡") == 2


def test_G06_requires_every_bar_in_a_chart_to_be_sourced(passing_ctx):
    """红线 R-02 的检测器是 G-06/G-07，所以评分图必须走同一条路：
    闸门按区块类型分派，新加的 bar_chart 若忘了挂进去，图里的数字就成了
    "全页唯一不需要来源的地方"。schema 那道是第一层，这层是第二层。"""
    data = copy.deepcopy(passing_ctx.data)
    data["sections"][0]["blocks"].append({
        "type": "bar_chart", "heading": u"公开评测得分", "unit": u"分", "max": 100,
        "bars": [
            {"label": "A", "value": 88.8, "source_ids": ["S1"]},
            {"label": "B", "value": 77.7},          # ← 没来源
        ],
    })
    ctx = copy.copy(passing_ctx)
    ctx.data = data
    fails = run(by_id("G-06"), ctx)
    assert any("柱" in str(f) or "77.7" in str(f) for f in fails), \
        "有一根柱子没挂来源，G-06 却没报错：%s" % [str(f) for f in fails][:4]


def test_the_chart_block_is_measured_for_right_edge():
    """新增的可见区块必须进 G-13 的右边界比对组，不然它就是下一个"右差 356.8px"。
    W-81 的教训：那组选择器当时只量 `.body > *`，而区块都包在 `.blk` 里，
    参差发生在下一层，闸门量不到。
    （这条只钉住 chart 一个类名——它是手写的清单，加新区块的人要记得同时加这里。）"""
    src = io.open(os.path.join(V.ROOT, "scripts", "measure-layout.mjs"), encoding="utf-8").read()
    m = re.search(r'"\.body > \*",\s*(.*?)\]\]', src, re.S)
    assert m, "找不到 G-13 的右边界比对组，选择器写法变了要同步改这条测试"
    group = m.group(1)
    assert ".chart" in group, "`.chart` 不在比对组里：%s" % group.replace("\n", " ")[:120]


def test_G03_flags_the_same_image_used_by_multiple_sections(quality_bar, tmp_path):
    """开发者问"正文图片完全一样是 bug 吗"。真实管线按字节哈希去重，
    但产物里真出现"每章同一张图"时必须被闸门抓住，而不是靠人肉看。"""
    data = make_passing_data()
    shared = data["sections"][0]["images"][0]["file"]
    for s in data["sections"][1:]:
        s["images"] = [dict(data["sections"][0]["images"][0])]
    for s in data["sections"]:
        for im in s["images"]:
            (tmp_path / im["file"].replace("/", os.sep)).parent.mkdir(parents=True, exist_ok=True)
            write_image(os.path.join(str(tmp_path), im["file"].replace("/", os.sep)))
    html = make_passing_html(data)
    ctx = V.Ctx(u"重复", str(tmp_path), "x.html", html, data, quality_bar)
    fails = [f for f in (by_id("G-03").check(ctx) or []) if f.level == "fail"]
    assert any("重复" in str(f) for f in fails), \
        "每章同一张图却没报错：%s" % [str(f)[:70] for f in fails]


def test_G13_detects_low_contrast(tmp_path, quality_bar):
    """对比度检查自己也要被注错证明有效（红线 R-09）：
    深色主题下 kicker/编号糊成一片是本项目真出过的事故。"""
    real = os.path.join(V.ROOT, "demo_site", "output", u"咖啡")
    page = os.path.join(real, u"咖啡_2026-09-19.html")
    if not os.path.isfile(page):
        pytest.skip("没有 demo 产物可用于注错")
    src = io.open(page, encoding="utf-8").read()
    inj = ".cover-kicker{color:#B9B9B9 !important}"
    bad = src.replace("</style>", inj + "</style>", 1)
    assert bad != src and bad.index(inj) > bad.index("--measure")
    d = tmp_path / u"咖啡"; (d / "images").mkdir(parents=True)
    for f in os.listdir(os.path.join(real, "images")):
        shutil.copyfile(os.path.join(real, "images", f), os.path.join(str(d), "images", f))
    p = d / (u"咖啡_2026-09-19.html"); p.write_text(bad, encoding="utf-8")
    ctx = V.Ctx(u"咖啡", str(d), str(p), bad, {"sections": [], "sources": []}, quality_bar)
    fails = [f for f in (by_id("G-13").check(ctx) or []) if f.level == "fail"]
    assert any("contrast" in str(f) for f in fails), \
        "灰字压白底没被抓到：%s" % [str(f).split(u"：", 1)[-1][:60] for f in fails][:5]


def _pad_to(ctx, target):
    """把正文汉字数调到 target 附近：先清空 prose，再按缺口填汉字。"""
    data = copy.deepcopy(ctx.data)
    for s in data["sections"]:
        for b in s["blocks"]:
            if b["type"] == "prose":
                b["text"] = "。"
    c = V.cjk_count(V.data_text(data))
    prose = next(b for s in data["sections"] for b in s["blocks"] if b["type"] == "prose")
    prose["text"] = "咖" * max(10, target - c)
    out = copy.copy(ctx)
    out.data = data
    return out


def test_G05_warns_when_slightly_over_the_soft_ceiling(passing_ctx):
    """开发者 2026-09-19：「稍微写超 没关系，主要看 文章质量」。
    所以软上限之上只降级为 warn——既不因为超一点字数废掉好文章，
    也不把"约 10 分钟读完"这个承诺悄悄删掉（warn 仍然会在报告里挂着）。"""
    soft = passing_ctx.bar["words"]["max_chars"]
    hard = passing_ctx.bar["words"]["hard_max_chars"]
    assert hard > soft, "硬上限必须高于软上限，否则这个分级没生效"
    ctx = _pad_to(passing_ctx, int((soft + hard) / 2.0))
    got = run(by_id("G-05"), ctx)
    assert not [f for f in got if f.level == "fail"], \
        u"超软上限未过冲硬上限却被判死：%s" % [str(f) for f in got]
    assert [f for f in got if f.level == "warn"], "超软上限却一声不吭，篇幅承诺就没人守了"


def test_G05_still_fails_when_grossly_over(passing_ctx):
    hard = passing_ctx.bar["words"]["hard_max_chars"]
    ctx = _pad_to(passing_ctx, hard + 1500)
    got = run(by_id("G-05"), ctx)
    assert [f for f in got if f.level == "fail"], \
        u"超硬上限 %d 还不判死，10 分钟就彻底没人管了" % hard


# ---------------------------------------------------------------- W-155
# 正文里手写的 [Sxx] 与块级 source_ids 是两套东西：前者直接印在页面上，
# 读者会以为那句话有出处。09-26 全站量到 99 处，全部悬空，5 个已上线页面带着它们。
def test_G06_rejects_a_dangling_inline_marker(passing_ctx):
    data = copy.deepcopy(passing_ctx.data)
    data["sections"][0]["blocks"][0]["text"] += u"（读数见 [S9]）"
    ctx = copy.copy(passing_ctx)
    ctx.data = data
    hits = [str(x) for x in run(by_id("G-06"), ctx)]
    assert any("S9" in h and "内嵌" in h for h in hits), \
        u"正文里指向不存在来源的 [S9] 没被判：\n%s" % "\n".join(hits)


def test_G06_accepts_an_inline_marker_that_resolves(passing_ctx):
    """夹具的 sources 里有 S1。能解析的内嵌标号不是错——
    把它一起判死，等于逼人删掉真引用。"""
    data = copy.deepcopy(passing_ctx.data)
    data["sections"][0]["blocks"][0]["text"] += u"（读数见 [S1]）"
    ctx = copy.copy(passing_ctx)
    ctx.data = data
    hits = [str(x) for x in run(by_id("G-06"), ctx)]
    assert not any("内嵌" in h for h in hits), u"能解析的标号被误判：%s" % hits


def test_G06_ignores_brackets_that_are_not_source_ids(passing_ctx):
    """`[2024]`、`[注3]`、`[S]` 都不是来源标号。判据必须只认 `S` + 数字，
    否则这条闸门会变成全站噪声源（本项目已经有一条 90% 时间在响的闸门了）。"""
    data = copy.deepcopy(passing_ctx.data)
    data["sections"][0]["blocks"][0]["text"] += u" [2024] [注3] [S] [SS1] [1S]"
    ctx = copy.copy(passing_ctx)
    ctx.data = data
    hits = [str(x) for x in run(by_id("G-06"), ctx)]
    assert not any("内嵌" in h for h in hits), u"非来源形状的方括号被误判：%s" % hits


def test_G06_checks_inline_markers_in_non_prose_blocks_too(passing_ctx):
    """timeline / price_table / card_grid 里的文字同样会印到页面上。
    只扫 prose 等于留了个后门。夹具里有 timeline 与 price_table，各测一处。"""
    data = copy.deepcopy(passing_ctx.data)
    tl = next(b for s in data["sections"] for b in s["blocks"] if b.get("type") == "timeline")
    tl["items"][0]["text"] += u"（口径见 [S77]）"
    pt = next(b for s in data["sections"] for b in s["blocks"] if b.get("type") == "price_table")
    pt["rows"][0]["cells"][-1] += u" [S78]"
    ctx = copy.copy(passing_ctx)
    ctx.data = data
    hits = [str(x) for x in run(by_id("G-06"), ctx)]
    for sid in (u"S77", u"S78"):
        assert any(sid in h and "内嵌" in h for h in hits), \
            u"%s 在非 prose 块里没被判：\n%s" % (sid, "\n".join(hits))


def test_G06_says_out_loud_when_prose_carries_unsourced_numbers(passing_ctx):
    """G-06 里那条 `elif t == "prose" and has_num and not b.get("source_ids")`
    的函数体曾经是 `pass`——它检测到了正确的东西，然后什么都不做。
    09-26 量到全站 635 个 prose 块里有 195 个带数字且无块级来源，全被这个 pass 咽掉。
    现在报一条 warn（每页一条带计数，不是每块一条：195 行的日志一周就会被人跳过）。"""
    data = copy.deepcopy(passing_ctx.data)
    n = 0
    for s in data["sections"]:
        for b in s["blocks"]:
            if b.get("type") == "prose":
                b.pop("source_ids", None)
                b["text"] = u"实测重量 40 克，视场角 30 度。"
                n += 1
    ctx = copy.copy(passing_ctx)
    ctx.data = data
    hits = [x for x in run(by_id("G-06"), ctx)]
    assert hits, u"带数字又没来源的 prose 块仍然完全静默"
    assert all(getattr(x, "level", "fail") == "warn" for x in hits), \
        u"这是存量欠账不是新坏掉的东西，判 fail 会把 22 篇全部踢出索引"
    assert any(str(n) in str(x) for x in hits), u"要报数，不然没人知道规模：%s" % [str(x) for x in hits]
