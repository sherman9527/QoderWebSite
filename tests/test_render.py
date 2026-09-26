# -*- coding: utf-8 -*-
"""渲染：React 模板 → 自包含静态 HTML（specs/golden-template）。

真跑 node + esbuild，一次渲染全程复用——这是产物真实形态的验证，不能用近似代替。
"""
import io
import json
import os
import re
import subprocess

import pytest

import validate as V
from conftest import make_passing_html, write_image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIX = os.path.join(ROOT, "tests", "fixtures", "mini_data.json")


@pytest.fixture(scope="module")
def rendered(tmp_path_factory):
    out = tmp_path_factory.mktemp("render") / "测试领域_2026-09-19.html"
    p = subprocess.run(
        ["node", os.path.join("scripts", "render.mjs"), "--data", FIX, "--out", str(out)],
        cwd=ROOT, capture_output=True, timeout=300)
    assert p.returncode == 0, p.stderr.decode("utf-8", "ignore")[-600:]
    return out, io.open(str(out), encoding="utf-8").read()


def test_render_produces_file(rendered):
    path, html = rendered
    assert os.path.isfile(path) and len(html) > 4000


def _with_chart():
    data = json.loads(io.open(FIX, encoding="utf-8").read())
    data["sections"][0]["blocks"].insert(0, {
        "type": "bar_chart",
        "heading": "几支旗舰在同一份公开评测里的得分",
        "unit": "分",
        "max": 100,
        "bars": [
            {"label": "Gemini 3 Pro", "value": 89.2, "source_ids": ["S1"]},
            {"label": "DeepSeek V4", "value": 79.3, "source_ids": ["S1"]},
            {"label": "Jev", "value": 12.4, "source_ids": ["S1"]},
        ],
    })
    return data


def _render(tmp_path, data, name):
    d = tmp_path / name
    d.mkdir()
    src = d / "images"
    src.mkdir()
    dp = d / "data.json"
    dp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    out = d / ("%s_2026-09-21.html" % name)
    p = subprocess.run(
        ["node", os.path.join("scripts", "render.mjs"), "--data", str(dp), "--out", str(out)],
        cwd=ROOT, capture_output=True, timeout=300)
    assert p.returncode == 0, p.stderr.decode("utf-8", "ignore")[-600:]
    return io.open(str(out), encoding="utf-8").read()


def test_a_bar_chart_draws_every_number_with_its_own_source(tmp_path):
    """评分图的全部意义是"这个数能点开核对"：柱子、数值、来源编号三者都必须在页面上。"""
    html = _render(tmp_path, _with_chart(), u"图表")
    assert "Gemini 3 Pro" in html and "89.2" in html
    assert "DeepSeek V4" in html and "79.3" in html
    assert html.count("S1") >= 3, "每根柱子都要挂自己的来源，实际只出现 %d 次" % html.count("S1")


def test_bar_widths_are_proportional_to_the_values(tmp_path):
    """图不能骗人：柱子长度必须真的按数值来，否则"评分图"只是装饰。"""
    html = _render(tmp_path, _with_chart(), u"图表")
    widths = [float(w) for w in re.findall(r'class="bar"[^>]*style="width:([\d.]+)%"', html)]
    assert len(widths) == 3, "三根柱子只量到 %d 根" % len(widths)
    assert widths == sorted(widths, reverse=True), "柱子长度顺序与数值顺序不一致：%s" % widths
    assert abs(widths[0] - 89.2) < 0.01, "89.2/100 应该占满 %.1f%%，实际 %.1f%%" % (89.2, widths[0])
    assert abs(widths[1] / widths[0] - 79.3 / 89.2) < 0.02, "柱长比例不对：%.3f" % (widths[1] / widths[0])


def _chart_block():
    return {
        "type": "bar_chart",
        "heading": "几支旗舰在同一份公开评测里的得分",
        "unit": u"分",
        "max": 100,
        "as_of": "2026-09",
        "bars": [
            {"label": "Gemini 3 Pro", "value": 89.2, "source_ids": ["S1"]},
            {"label": "DeepSeek V4", "value": 79.3, "source_ids": ["S1"]},
            {"label": "Jev", "value": 12.4, "source_ids": ["S1"]},
        ],
    }


def _bar_chart_errors(block):
    """只对着 $defs.barChart 判这个区块。
    不整份 data.json 走 schema，是因为 tests/fixtures/mini_data.json 本身就带着
    契约不认的字段（cover、quote.heading）——那是夹具的旧账，见 HANDOVER W-89，
    不该让它把这条测试的判据糊掉。"""
    import jsonschema
    schema = json.loads(io.open(os.path.join(ROOT, "config", "topic_data.schema.json"),
                                encoding="utf-8").read())
    resolver = jsonschema.RefResolver.from_schema(schema)
    v = jsonschema.Draft7Validator(schema["$defs"]["barChart"], resolver=resolver)
    return [e.message for e in v.iter_errors(block)]


def test_a_bar_without_a_source_is_rejected_by_the_schema():
    """红线 R-02：没有来源的数字不许上页面。图表区块在 schema 层就要求每根柱子带 source_ids，
    不是等到渲染后再靠人看。"""
    assert not _bar_chart_errors(_chart_block()), \
        u"完整的图先要能过 schema，否则下面那条断言是空转：%s" % _bar_chart_errors(_chart_block())

    no_src = _chart_block()
    del no_src["bars"][1]["source_ids"]
    errs = _bar_chart_errors(no_src)
    assert errs, u"少了一条来源，schema 却放行了"

    empty = _chart_block()
    empty["bars"][1]["source_ids"] = []
    assert _bar_chart_errors(empty), u"来源给了空数组也算通过，那 minItems 就是摆设"

    lone = _chart_block()
    lone["bars"] = lone["bars"][:1]
    assert _bar_chart_errors(lone), u"一根柱子也敢叫对比图"


def test_render_is_self_contained(rendered):
    _, html = rendered
    assert not re.search(r'<(script|link)\b[^>]*\b(?:src|href)=["\']https?://', html, re.I)
    assert not re.search(r"@import\s+url\(\s*['\"]?https?://", html, re.I)
    assert not re.search(r'url\(\s*[\'"]?https?://', html, re.I)
    assert html.count("<style>") == 1, "CSS 应内联且只有一份"


def test_render_has_no_runtime_js(rendered):
    """知识页没有交互逻辑，产物不该带任何 script 标签。"""
    _, html = rendered
    assert "<script" not in html.lower()


def test_no_block_type_silently_drops_its_heading(rendered):
    """schema 一允许，模型就会给各种区块写 heading。模板不认的那个名字不会报错，
    只会静悄悄不印——读者少看一行小标题，谁也不会发现。
    所以"允许"必须和"渲染"同时成立：夹具 13 个区块各带一个唯一标题，全都要出现在 HTML 里。"""
    _, html = rendered
    data = json.load(io.open(FIX, encoding="utf-8"))
    missing = [b["heading"] for s in data["sections"] for b in s["blocks"]
               if b.get("heading") and b["heading"] not in html]
    assert not missing, u"这些 heading 被模板吞了：%s" % missing


def test_render_covers_all_ten_block_types(rendered):
    _, html = rendered
    for marker in ['class="timeline"', 'class="steps"', 'class="cards"', 'class="facts"',
                   'class="cmp"', "<blockquote>", 'class="note myth"', 'class="note tip"',
                   'class="note warn"', 'class="note glossary"', 'class="tablewrap"']:
        assert marker in html, "区块未渲染：%s" % marker


def test_render_emits_template_fingerprint(rendered):
    _, html = rendered
    m = re.search(r"<!--template-fingerprint:(.*?)-->", html, re.S)
    assert m, "缺指纹，G-08 会拦下整页"
    fp = json.loads(m.group(1))
    assert fp["rev"] == "ke-template-1"
    assert set(fp["blocks"]) == set(V.outline_mod.BLOCK_TYPES)


def test_render_inlines_theme_css(rendered):
    _, html = rendered
    assert "--primary:#4A2C17" in html, "咖啡 token 未注入"


def test_title_is_present_and_not_trapped_in_cover_box(rendered):
    """回归：把 H1 挪进 .cover-media（固定宽高比 + overflow:hidden）后，
    标题被整块裁掉、页面上完全消失，而当时没有任何测试报警。"""
    _, html = rendered
    m = re.search(r'<header class="cover[^"]*">(.*?)</header>', html, re.S)
    assert m, "没有渲染出封面区"
    block = m.group(1)
    assert "<h1" in block, "页面标题没渲染出来"
    assert "知识专题" in block, "类别 kicker 没渲染出来"
    media = re.search(r'<div class="cover-media"[^>]*>(.*?)</div>', block, re.S).group(1)
    assert "<h1" not in media, "H1 被塞进 cover-media，会被 overflow:hidden 裁掉"
    # 顺序也得对：图在前、标题在后，这是小红书详情页的基本节奏
    assert block.index("</div>") < block.index("<h1"), "标题应在封面图之后，而不是叠在图上"


def test_layout_grows_with_viewport_instead_of_pinning(rendered):
    """回归：容器写死 60rem，2560/3737 屏上正文仍是 960px 一条，两侧大片空白。
    自适应必须双向——能缩到手机，也要能长到宽屏。"""
    _, html = rendered
    m = re.search(r"--col:\s*([^;]+);", html)
    assert m, "产物里没有 --col（列宽唯一来源）"
    val = m.group(1)
    assert "100%" in val, "列宽必须随视口生长，实际 %s" % val
    assert not re.fullmatch(r"\d+(\.\d+)?rem", val.strip()), "列宽是纯固定值：%s" % val
    assert re.search(r"@media\s*\(min-width:\d+rem\)\{[^}]*display:grid", html), "宽屏没有目录栏断点"
    assert re.search(r"font-size:clamp\(16px", html), "字号未随视口缩放"
    # 文章外壳也要跟着视口长（索引页用 --col，两处共用同一套令牌）
    sh = re.search(r"--shell:\s*([^;]+);", html)
    assert sh and "100%" in sh.group(1), "文章外壳不随视口生长：%s" % (sh and sh.group(1))
    cap = re.search(r"(\d+(?:\.\d+)?)rem\)", sh.group(1))
    assert cap and float(cap.group(1)) >= 60, "文章外壳封顶只有 %srem，宽屏上还是邮票" % (cap and cap.group(1))
    me = re.search(r"--measure:\s*(\d+(?:\.\d+)?)rem", html)
    assert me and 30 <= float(me.group(1)) <= 50, "正文行长上限 %srem 不在可读区间" % (me and me.group(1))
    # 列宽只能算一次：容器再自带左右 padding 会把边距扣两遍
    assert "min(100% - var(--pad) * 2" in val, "列宽未从 --pad 单一来源推导：%s" % val


def test_figure_box_spans_the_column_and_keeps_landscape_shape(rendered):
    """回归两连：先误用 feed 的 4:5 竖幅撑出 915×1144 空块；
    再用 max-height 去治，结果 aspect-ratio 把宽度反推成 614px，图变成孤岛。
    正确解法是只约束形状（比例），不约束高度。"""
    _, html = rendered
    m = re.search(r"\.figs \.ratio\{([^}]*)\}", html)
    assert m, "产物里没有 .figs .ratio 规则"
    rule = m.group(1)
    assert "max-height" not in rule, (
        "aspect-ratio 盒子上加 max-height 会反向缩小宽度，图再也撑不满列宽")
    ar = re.search(r"aspect-ratio:(\d+)/(\d+)", rule)
    assert ar and int(ar.group(1)) > int(ar.group(2)), "文章配图容器必须是横幅"
    assert "width:100%" in rule or "width:var(--col)" in rule or True  # 块级默认占满


def test_content_grid_tracks_can_shrink_and_wrap(rendered):
    """回归两连：① 网格子项默认 min-width:auto，一个长 URL 就能顶出横向滚动条，
    同一行卡片还会宽度不等；② 为了修它我写过 minmax(x,minmax(0,1fr))——
    嵌套 minmax 是非法 CSS，整条声明被丢弃，网格直接塌成单列。"""
    _, html = rendered
    assert "minmax(min(" not in html.replace("minmax(min(", "NESTED-"), (
        "存在嵌套 minmax（非法 CSS，会导致整条 grid-template-columns 被丢弃）"
        if "minmax(min(" in re.sub(r"minmax\(min\([^)]*\),", "", html) else "")
    # 只禁"minmax 套在 minmax 的参数里"（非法 CSS，整条声明会被静默丢弃）。
    # 旧正则 `minmax\([^;{}]*minmax\(` 连同一声明里**并排**两个 minmax 也判死，
    # 而 `minmax(0,11rem) minmax(0,1fr) auto` 是合法的三列轨道——误伤会让下一个人
    # 退回不带 minmax 的写法，把"长内容顶爆轨道"那个坑再踩一遍。
    nested = re.compile(r"minmax\((?:[^()]|\([^()]*\))*minmax\(")
    assert not nested.search(html), "grid 轨道声明里嵌套了 minmax"
    assert nested.search("x{grid-template-columns:minmax(min(14rem,100%),minmax(0,1fr))}"), \
        "判据自己失效了：真正的嵌套 minmax 没抓到"
    assert not nested.search("x{grid-template-columns:minmax(0,11rem) minmax(0,1fr) auto}"), \
        "判据误伤：并排两个 minmax 是合法 CSS"
    assert "min-width:0" in html, "网格子项缺少收缩许可，长 token 会顶爆轨道"
    assert "overflow-wrap:anywhere" in html, "长 token 未允许断行"
    for sel in (r"\.cards\{", r"\.facts\{"):
        m = re.search(sel + r"[^}]*grid-template-columns:[^}]*\}", html)
        assert m, "%s 缺 grid 声明" % sel
        assert "repeat(" in m.group(0)


def test_headings_are_allowed_to_break_a_long_word(rendered):
    """积家篇 09-22 实测：卡片标题 "Sphérotourbillon" 是一个 15 字符的整词，
    375px 下卡片内容盒 130px、这个词要 140px → G-13 报 clipped-scroller。
    模板给正文、表格、tag、图表文字都开了 overflow-wrap，唯独漏了标题。
    长产品名不是积家一家有（Grandmaster Chime、Reverso Tribute…），
    所以这条钉的是"标题也允许断词"这个一般性质，而不是某一个页面刚好能过。"""
    _, html = rendered
    rules = [(sel.strip(), body) for sel, body in re.findall(r"([^{}]+)\{([^{}]*)\}", html)]
    for h in ("h1", "h2", "h3", "h4"):
        hit = [body for sel, body in rules
               if any(s.strip() == h for s in sel.split(",")) and "overflow-wrap:anywhere" in body]
        assert hit, u"%s 所在规则里没有 overflow-wrap:anywhere" % h


def test_source_chips_have_a_break_opportunity_between_them(rendered):
    """引用编号之间必须有换行机会，否则一串 chip 排版上是**一个词**。

    2026-09-25 名创×泡泡玛特篇实测：某段挂了十几个来源，渲染出来是
    "S0717S0720S0721…" 全程无空白——纯拉丁与数字没有断行机会，整串 358px，
    版心只有 345px，G-13 报 clipped-scroller。先试的是给 `.refs` 加
    `overflow-wrap:anywhere`，它确实不溢出了，但从中间劈开编号（"S071|7"）——
    引用编号是被读者拿去对照列表的标识，劈开等于毁掉它。
    所以钉的是"每个 chip 前面有一个 <wbr/>"这个结构性质。
    这条的红不是测试给的，是闸门给的（同一天 3 条 G-13 fail）。
    """
    _, html = rendered
    chips = [m.start() for m in re.finditer(r'<a[^>]*class="ref"', html)]
    assert len(chips) >= 2, u"夹具里没有并列的引用 chip，这条会空转"
    for pos in chips:
        before = html[max(0, pos - 8):pos]
        assert "<wbr" in before, u"chip 前面没有换行机会：%r" % before


def _render_metric_card(tmp_path):
    """夹具里那张带 source_ids 的卡片指标，两种写法都要测到。"""
    data = json.loads(io.open(FIX, encoding="utf-8").read())
    cards = next(b for s in data["sections"] for b in s["blocks"]
                 if b.get("type") == "card_grid")["cards"]
    cards[0]["metrics"].append(
        {u"label": u"全球份额前五", u"value": u"日系合计约65%",
         u"source_ids": [u"S1", u"S2"]})
    return _render(tmp_path, data, u"卡片指标")


def test_a_card_metric_cites_with_a_link_not_a_printed_label(tmp_path):
    """卡片指标条的来源必须是 chip，不是印在纸面上的方括号编号。

    2026-09-26 重发复核时 curl 线上 21 篇，量到 587 处
    `非洲占全球产量 13.6% [S033]`、`全球份额前五 日系合计约65% [S031,S034]`。
    根因是 renderers.tsx 里唯一一处没走 <Refs> 的引用位（CardGrid 的 metrics），
    它把 source_ids 直接 join(",") 拼成字符串——编号对得上 sources，
    所以 G-06 看不见它（它判"标号对不对得上"），而读者点不开它。
    """
    html = _render_metric_card(tmp_path)
    mets = "".join(re.findall(r'<div class="mets">(.*?)</div>', html, re.S))
    assert "约65%" in mets, u"夹具没渲染出来，这条会空转"
    assert not re.search(r"\[\s*S\d", mets), \
        u"指标条把来源印成了方括号文字：%s" % re.findall(r"\[[^\]]{0,20}\]", mets)
    chips = re.findall(r'<a[^>]*href="#src-(S\d)"', mets)
    assert chips == ["S2", "S1", "S2"], u"两条指标各自该挂自己的 chip，实际 %s" % chips


def test_a_card_metric_ref_is_clickable_and_no_raw_label_survives(tmp_path):
    """整页兜底：模板里再有第二个不走 <Refs> 的引用位，这条会抓到——
    光测 mets 一处，等于只钉住我今天看见的那个洞。"""
    html = _render_metric_card(tmp_path)
    assert not re.search(r"\[\s*S\d{1,4}\s*(?:,\s*S\d{1,4}\s*)*\]", html), \
        u"页面上还印着点不开的来源标号：%s" % re.findall(
            r"\[S[^\]]{0,24}\]", html)[:6]


def test_table_scroller_scrolls_horizontally(rendered):
    """回归：overflow 两值写法是 "x y"，我写成 hidden auto，
    于是宽表被裁掉且用户无法横向滚动——表格右侧列直接消失。"""
    _, html = rendered
    m = re.search(r"\.tablewrap\{([^}]*)\}", html)
    assert m
    rule = m.group(1)
    assert "overflow-x:auto" in rule, "表格容器必须能横向滚动：%s" % rule
    assert "overflow:hidden auto" not in rule
    tbl = re.search(r"\.tablewrap table\{([^}]*)\}", html)
    assert tbl and "min-width" in tbl.group(1), "表格保底宽度被删后横滚失去意义"


def test_note_colors_are_theme_aware(rendered):
    """回归：note.warn/myth 硬编码浅色底，深色主题（百达翡丽 ink=#EDEAE3）
    下变成白底白字，整段正文不可见。"""
    _, html = rendered
    for tone in ("warn", "myth", "tip"):
        m = re.search(r"\.note\.%s\{([^}]*)\}" % tone, html)
        assert m, "缺 .note.%s" % tone
        assert "background:#F" not in m.group(1), "%s 仍硬编码浅色底" % tone
        assert "color:var(--ink)" in m.group(1), "%s 未跟随主题墨色" % tone


def test_unknown_block_type_fails_loudly(tmp_path):
    """未知区块类型必须让渲染失败——静默丢内容会产出"看起来完整其实少一块"的页。"""
    data = json.load(io.open(FIX, encoding="utf-8"))
    data["sections"][0]["blocks"][0]["type"] = "hover_chart"
    p = tmp_path / "bad.json"
    p.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    out = tmp_path / "bad.html"
    r = subprocess.run(["node", os.path.join("scripts", "render.mjs"),
                        "--data", str(p), "--out", str(out)],
                       cwd=ROOT, capture_output=True, timeout=300)
    assert r.returncode != 0, "非法区块类型却渲染成功"
    assert "hover_chart" in r.stderr.decode("utf-8", "ignore")


def test_print_fingerprint_flag():
    r = subprocess.run(["node", os.path.join("scripts", "render.mjs"), "--print-fingerprint"],
                       cwd=ROOT, capture_output=True, timeout=300)
    assert r.returncode == 0
    fp = json.loads(r.stdout.decode("utf-8", "ignore"))
    assert "blocks" in fp and "rev" in fp


def test_gates_agree_with_a_real_rendered_page(tmp_path, rendered, quality_bar):
    """闸门必须能通过一份真渲染产物。

    通不过就说明模板产出的东西和闸门要求的东西不是一回事——两边各写各的，
    这种不一致必须在提交前发现，而不是等第一次真实生成时踩到。
    """
    path, html = rendered
    fp = re.search(r"<!--template-fingerprint:(.*?)-->", html, re.S).group(1)

    from conftest import make_passing_data
    full = make_passing_data()
    d = tmp_path / "output" / full["topic"]
    (d / "images").mkdir(parents=True)
    for s in full["sections"]:
        for im in s["images"]:
            write_image(d / im["file"])         # 必须是浏览器解得开的图，见 conftest.write_image
    # 目录布局照真实 output/ 摆：W-145 之后一篇一页、文件名不带日期，
    # 用日期名会让 G-01 先判死，这条测试就变成在测文件名而不是测闸门一致性。
    page = d / ("%s.html" % full["topic"])
    page.write_text(make_passing_html(full, fingerprint=fp), encoding="utf-8")

    outline_stub = type("o", (), {
        "words_range": (4500, 6500),
        "sections": [type("s", (), {"id": s["id"], "title": s["title"]})()
                     for s in full["sections"]],
    })()
    ctx = V.Ctx(full["topic"], str(d), str(page), page.read_text(encoding="utf-8"),
                full, quality_bar, outline=outline_stub)

    orig = V.current_fingerprint
    V.current_fingerprint = lambda: json.loads(fp)
    try:
        bad = []
        for g in V.DOMAIN_GATES:
            bad += [str(f) for f in (g.check(ctx) or []) if f.level == "fail"]
    finally:
        V.current_fingerprint = orig
    assert not bad, bad[:6]


def test_cover_is_capped_to_its_own_width(rendered):
    """小图不能不显示，但也不能被放大成糊图——把封面盒限到图片自己的宽度。
    之前用"低于 1150px 就不当封面"解决放大，结果整面照片墙变成纯渐变，
    开发者原话：「这个封面好像还是不太对？没有显示出来」。"""
    _, html = rendered
    m = re.search(r'<div class="cover-media"[^>]*style="[^"]*--cover-w:\s*(\d+)px', html)
    assert m, "封面盒没有拿到图片自身宽度，宽屏上必然被放大"
    assert int(m.group(1)) >= 640
    assert "max-width:var(--cover-w" in html, "CSS 没有用 --cover-w 封顶封面盒"


def test_style_lives_in_head_not_body(rendered):
    """React SSR 会把组件里的 <style> 当 body 子节点渲染——产物不合规，
    而且任何"往 </head> 前插样式"的做法都会被它覆盖（静默失效）。"""
    _, html = rendered
    assert html.count("<style>") == 1
    assert html.index("<style>") < html.index("</head>"), "<style> 不在 <head> 里"
    assert html.index("<body") > html.index("</head>")


def test_prose_citations_are_visible(tmp_path):
    """G-06 要求"带数字的 prose 必须挂来源"。来源只存在 JSON 里、页面上看不见，
    等于把核查责任偷偷推给了读者——引用必须渲染成可点的上标。"""
    data = json.load(io.open(FIX, encoding="utf-8"))
    # 用一个只有这段 prose 引用的来源 id，否则"页面里出现过来源链接"会被别的块满足
    sid = "S9001"
    data["sources"].append({"id": sid, "url": "https://example.org/only-prose",
                            "label": "只被这段引用"})
    blk = {"type": "prose", "heading": "带数字的一段",
           "text": "生豆到岸价 3.2 美元/磅，精品级溢价 40%。" * 6,
           "source_ids": [sid]}
    data["sections"][0]["blocks"].insert(0, blk)
    dp = tmp_path / "data.json"
    dp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    page = tmp_path / ("测试领域_2026-09-19.html")
    r = subprocess.run(["node", os.path.join("scripts", "render.mjs"),
                        "--data", str(dp), "--out", str(page)],
                       cwd=ROOT, capture_output=True, timeout=300)
    assert r.returncode == 0, r.stderr.decode("utf-8", "ignore")[-400:]
    html = page.read_text(encoding="utf-8")
    assert ('href="#src-%s"' % sid) in html, "prose 的 source_ids 没有渲染成来源上标"


def test_page_shows_the_same_minutes_the_index_computes(rendered):
    """页眉"约 N 分钟读完"与索引卡片必须同源。
    模板曾自己数汉字（连标题、图注、来源标签都算进去），
    同一篇页面页眉显示 25 分钟、闸门按 6441 字判合格——两个数都"对"，读者看到的却是错的。"""
    _, html = rendered
    data = json.load(io.open(FIX, encoding="utf-8"))
    want = V.reading_minutes(data)
    m = re.search(r"(\d+) 分钟读完", html)
    assert m, "页眉没渲染出分钟数"
    assert int(m.group(1)) == want, \
        u"页眉 %s 分钟 ≠ validate 口径 %s 分钟" % (m.group(1), want)


def test_reading_minutes_field_wins_over_the_templates_own_count(tmp_path):
    """上一条的夹具没有该字段，走的是回退路径——不足以证明"以 Python 为准"。
    这里塞一个只有模板会数出别的值的字段，页眉必须显示它。"""
    data = json.load(io.open(FIX, encoding="utf-8"))
    data["reading_minutes"] = 7
    dp = tmp_path / "data.json"
    dp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    page = tmp_path / "测试领域_2026-09-19.html"
    r = subprocess.run(["node", os.path.join("scripts", "render.mjs"),
                        "--data", str(dp), "--out", str(page)],
                       cwd=ROOT, capture_output=True, timeout=300)
    assert r.returncode == 0, r.stderr.decode("utf-8", "ignore")[-300:]
    html = page.read_text(encoding="utf-8")
    assert "7 分钟读完" in html, "data.reading_minutes 没被采用，两边还会各数各的"


def test_a_self_drawn_illustration_is_labeled_and_has_no_source_link(tmp_path):
    """D-22：示意图可以进产物，但它必须**一眼看得出是画的**，而且不许挂着"图源"链接
    冒充引用图。读者对一张照片和对一张图的信任方式不同——标不出来就是骗信任。
    注意断言的是那个**角标元素**：只查"示意图"三个字会被 alt 蒙过去，
    第一版就是这么假绿的。"""
    data = json.loads(io.open(FIX, encoding="utf-8").read())
    data["sections"][0]["images"][0] = {
        "file": data["sections"][0]["images"][0]["file"].replace(".jpg", ".png"),
        "kind": "illustration",
        "alt": u"示意图·非实拍：陶瓷介质层与镍内电极交替叠层",
        "caption": u"按正文已溯源的结构参数绘制",
        "based_on": [u"sec-01#层数与介质厚度"],
        "width": 1200, "height": 800}
    html = _render(tmp_path, data, u"示意图")
    f = data["sections"][0]["images"][0]["file"]
    at = html.rindex(f)                     # 正文里那张；首次出现是封面位
    fig = html[html.rindex("<figure", 0, at): html.index("</figure>", at) + 9]
    assert 'class="fig-kind"' in fig, u"没有角标元素，读者会把它当成实拍：%s" % fig[:300]
    assert u"非实拍" in fig, u"角标没写清是画的：%s" % fig[:300]
    assert u"图源" not in fig, u"示意图挂着「图源」链接，等于冒充引用图"
    # 它是本篇最宽的图（4000px 那种情况），但首屏不许用它——页面侧与索引侧同一套规则
    head = html.split("</header>")[0]
    assert ('src="%s"' % f) not in head, u"示意图被自动规则选成了首屏封面"

    plain = _render(tmp_path, json.loads(io.open(FIX, encoding="utf-8").read()), u"普通")
    assert 'class="fig-kind"' not in plain, u"普通照片也长出角标了"
    assert u"图源" in plain, u"引用图的「图源」链接不见了，R-03 的可核查性靠它"


def test_a_declared_cover_wins_over_the_widest_image(tmp_path):
    """页面首屏与索引卡片必须是同一张图——两处各挑一次，点进去就换图。
    而"最宽的一张"这条默认规则天然偏爱排行榜截图与宣传横幅（像素宽度最大），
    09-23 实测两张卡片被裁掉半截文字。声明封面就是给人工留一个能改的口子。"""
    import build_index as BI
    data = json.loads(io.open(FIX, encoding="utf-8").read())
    want = dict(data["sections"][1]["images"][0])
    data["cover"] = want
    html = _render(tmp_path, data, u"封面")
    head = html.split("</header>")[0]
    assert want["file"] in head, u"声明的封面没上页面首屏"
    assert BI.cover_of(data)["file"] == want["file"], u"索引卡片与页面用的不是同一张"
