# -*- coding: utf-8 -*-
"""契约测试：同一个枚举散在三处（JSON Schema / TypeScript / Python），必须一致。

这是"防漂移"的核心一手——三处各自都能自圆其说，只有对齐断言能发现它们分家了。
"""
import io
import json
import os
import re

import pytest

import outline as O

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _read(*p):
    return io.open(os.path.join(ROOT, *p), encoding="utf-8").read()


def test_every_section_has_a_query_the_subject_gate_can_use():
    """大纲数据与检索词构造规则必须对得上：一条既不含品牌词、本身又 ≥3 词的检索词，
    `ensure_subject` 拒绝补（补完 4 词，Bing 召回崩塌），在点名档等于不存在。
    实测 315 条里有 124 条这样——那些章只能落到放宽档，
    而放宽档正是"中华万年历 app 下载""重型工作台"进来的地方。
    两边各改一处就会红，这正是把它钉在契约层而不是记在脑子里的理由。"""
    import images as IM
    bad = []
    for f in sorted(os.listdir(os.path.join(ROOT, "config", "topics"))):
        if not f.endswith(".json"):
            continue
        cfg = O.load_for_topic(f[:-5], root=ROOT)
        subj = IM.subject_tokens(cfg)
        for s in cfg.sections:
            qs = IM.gated_queries(s.image_queries, subj)
            usable = [q for q in qs if IM.names_subject(q.lower(), subj)]
            if not usable:
                bad.append(u"%s/%s" % (cfg.topic, s.id))
    assert not bad, u"这些章没有任何一条点名档用得上的检索词：%s" % bad
    # 注意这条契约**不**限制词数：实测崩塌发生在 5 词（"路易威登 LV Monogram 花纹 细节"
    # 只回 1 条），而 6 个章节的检索词本来就是 4 词且点名正确
    # （"Marc Jacobs 路易威登 秀场"、"宾利 欧陆 GT Continental"）。
    # 词数上限只是 gated_queries 决定"要不要补一条短兄弟"的内部启发，不是合法性判据。


def test_every_outline_token_exists_in_the_typescript_themes():
    """大纲里写一个不存在的 token，模板会静默退回默认主题——于是"每个领域视觉不同"
    这条需求悄悄失效，而闸门全绿。色板真身在 TS 里（validate.palette_of 也读它），
    所以这里只钉一件事：每个大纲的 token 必须能在 THEMES 里找到。"""
    src = _read("web", "src", "tokens", "index.ts")
    keys = set(re.findall(r'^  "([a-z0-9-]+)": \{', src, re.M))
    assert len(keys) >= 10, u"没从 TS 里解析出主题，这个测试就没在测东西：%s" % sorted(keys)
    # 自检：解析不出来时不能一路绿灯地"全部通过"
    assert "definitely-not-a-token" not in keys

    missing = []
    for f in sorted(os.listdir(os.path.join(ROOT, "config", "topics"))):
        if not f.endswith(".json"):
            continue
        tok = (json.loads(_read("config", "topics", f)).get("theme") or {}).get("token")
        if tok not in keys:
            missing.append(u"%s → %r" % (f[:-5], tok))
    assert not missing, u"这些领域用了 TS 里不存在的主题 token：%s" % missing


def test_python_and_schema_block_enums_match():
    schema = json.loads(_read("config", "topic_data.schema.json"))
    want = set(schema["$defs"]["blockType"]["enum"])
    got = set(O.BLOCK_TYPES)
    assert got == want, "Python=%s ≠ schema=%s" % (sorted(got - want), sorted(want - got))


def test_typescript_and_schema_block_enums_match():
    """模板常量与 schema 必须一字不差。改了 schema 忘了改模板 = 静默丢区块。"""
    src = _read("web", "src", "template", "blocks.ts")
    m = re.search(r"BLOCK_TYPES\s*=\s*\[(.*?)\]", src, re.S)
    assert m, "blocks.ts 里找不到 BLOCK_TYPES"
    got = set(re.findall(r'"([^"]+)"', m.group(1)))
    schema = json.loads(_read("config", "topic_data.schema.json"))
    want = set(schema["$defs"]["blockType"]["enum"])
    assert got == want, "TS=%s ≠ schema=%s" % (sorted(got ^ want), "")


def test_outline_schema_enum_matches_python():
    schema = json.loads(_read("config", "topic_outline.schema.json"))
    assert set(schema["$defs"]["blockType"]["enum"]) == set(O.BLOCK_TYPES)


def test_the_shared_fixture_satisfies_the_data_contract():
    """`tests/fixtures/mini_data.json` 是大家抄的样板，它自己必须符合数据契约。
    09-21 之前它稳定违反两条（顶层 `cover` 不在契约里、quote 正文短于 minLength），
    而渲染测试只出页面、不跑 schema，所以这个漂移一直躺着——
    我照着它做图表预览时被它坑了两次才发现。
    危害不是"测试不干净"，是**照抄它写的 data.json 会被闸门判死**。"""
    import generate as G
    data = json.loads(_read("tests", "fixtures", "mini_data.json"))
    errs = G._schema_errors(data)
    assert not errs, u"样板夹具不合契约：%s" % errs[:3]


def test_tokens_cover_every_topic():
    """每个领域大纲指的 token 都必须真的存在，否则渲染时才炸。"""
    src = _read("web", "src", "tokens", "index.ts")
    have = set(re.findall(r'^\s{2}"([a-z0-9-]+)":\s*\{', src, re.M))
    for topic in O.available_topics(root=ROOT):
        cfg = O.load_for_topic(topic, root=ROOT)
        assert cfg.token in have, "%s 指向不存在的 token %r" % (topic, cfg.token)


def test_every_token_declares_full_palette():
    src = _read("web", "src", "tokens", "index.ts")
    blocks = re.findall(r'^\s{2}"([a-z0-9-]+)":\s*\{(.*?)\n\s{2}\},', src, re.S | re.M)
    assert blocks, "没解析出任何 token"
    need = ["bg", "surface", "ink", "muted", "rule", "primary", "accent", "soft",
            "displayFamily", "bodyFamily", "numFamily", "heroMotif"]
    for tid, body in blocks:
        for k in need:
            assert re.search(r"\b%s\s*:" % k, body), "token %s 缺字段 %s" % (tid, k)


def test_every_topic_has_its_own_hero_motif():
    """10 页各有一个不同的记忆点，这是"不雷同"要求的一部分。"""
    used = {}
    for topic in O.available_topics(root=ROOT):
        cfg = O.load_for_topic(topic, root=ROOT)
        motif = cfg.hero_motif
        assert motif, "%s 没声明 hero_motif" % topic
        used.setdefault(motif, []).append(topic)
    dupes = {m: t for m, t in used.items() if len(t) > 1}
    assert not dupes, "多个领域共用同一记忆点：%s" % dupes


def test_all_seven_capabilities_have_specs():
    base = os.path.join(ROOT, "openspec", "changes", "build-knowledge-html-generator", "specs")
    have = sorted(d for d in os.listdir(base) if os.path.isdir(os.path.join(base, d)))
    assert have == ["content-grounding", "golden-template", "image-sourcing",
                    "knowledge-page-generation", "project-governance",
                    "quality-gates", "topic-outline-config"]


DATA_SCHEMA = json.loads(_read("config", "topic_data.schema.json"))
# quote 早就有 source_ids；其余内容块也必须能挂——G-06 要求"带数字的 prose 要有来源"
CARRYING = ["prose", "keyvalueTable", "timeline", "priceTable", "cardGrid",
            "steps", "factStrip", "compare", "note"]


def _block_errors(def_name, blk):
    """按 $defs 里对应那一支验证一个区块——报的是"模型这样答行不行"，
    不是"正则长什么样"，否则改实现就会顺手改掉断言。"""
    from jsonschema import Draft202012Validator
    return list(Draft202012Validator(DATA_SCHEMA["$defs"][def_name]).iter_errors(blk))


@pytest.mark.parametrize("name", CARRYING)
def test_every_block_type_can_carry_source_ids(name):
    """2026-09-19 真实生成翻车点：G-06 逼着 prose 挂 source_ids，
    G-10 的 schema 又用 additionalProperties:false 把它禁掉。
    两条闸门互相矛盾时，模型怎么答都错——12 章里 10 章被判死。"""
    props = DATA_SCHEMA["$defs"][name]["properties"]
    assert "source_ids" in props, u"%s 不允许 source_ids，G-06 的要求就落不了地" % name


def test_prose_block_with_source_ids_validates():
    from jsonschema import Draft202012Validator
    blk = {"type": "prose", "heading": u"小标题", "text": u"咖啡属有上百个种。" * 20,
           "source_ids": ["S021", "S023"]}
    v = Draft202012Validator(DATA_SCHEMA["$defs"]["prose"])
    assert list(v.iter_errors(blk)) == []


def test_source_id_pattern_is_enforced_everywhere():
    """source_ids 必须长得像 S123，否则 G-06 的"数字有没有来源"永远是查不出问题。"""
    for name in ["prose", "quote"]:
        item = DATA_SCHEMA["$defs"][name]["properties"]["source_ids"]["items"]
        assert item.get("pattern") == "^S[0-9]{1,4}$", u"%s 的 source_ids 没约束格式" % name


def test_every_block_def_allows_an_optional_heading():
    """模型天然想给区块写小标题（劳力士篇给 timeline 加了 heading，
    整篇 11 章在闸门处被判死）。要么允许并渲染，要么明确拒绝——
    最糟的是"允许但不渲染"，那是静悄悄丢内容。
    与 test_render.py::test_no_block_type_silently_drops_its_heading 成对：
    那条证明模板真的会印出来，这条证明 schema 真的放行。"""
    for name in CARRYING + ["quote"]:
        props = DATA_SCHEMA["$defs"][name]["properties"]
        assert "heading" in props, u"%s 不允许 heading，模型写了就整页判死" % name
        assert props["heading"].get("type") == "string", u"%s 的 heading 类型不对" % name


def test_timeline_text_allows_a_terse_dated_fact():
    """timeline 的 text 和 steps 一样，是"某年一件具体的事"，不是段落。
    LV 篇被 10 字下限判死的四条都是这个形态：
    "33 色重绘老花""波点进产品线""男装秀尾段公布""1 月回归门店"。
    同一条错在 prose（80→40）和 steps（8→4）上各犯过一次——
    下限设在不该设的地方，只会把写得最紧的那几句挑出来杀。"""
    blk = {"type": "timeline", "items": [
        {"year": "2001", "title": u"Sprouse 涂鸦", "text": u"Monogram 首次被改写，即刻售罄"},
        {"year": "2003", "title": u"村上隆", "text": u"33 色重绘老花"},
        {"year": "2004", "title": u"波点", "text": u"波点进产品线"},
        {"year": "2014", "title": u"男装", "text": u"男装秀尾段公布"},
        {"year": "2021", "title": u"回归", "text": u"1 月回归门店"}]}
    assert _block_errors("timeline", blk) == [], u"真产物里的时间轴被 schema 判死了"
    stub = {"type": "timeline", "items": [
        {"year": "2001", "text": u"好"}, {"year": "2002", "text": u""}]}
    assert len(_block_errors("timeline", stub)) == 2, u"空/单字的时间轴条目必须还是被拦"


def test_every_configured_domain_has_a_usable_subject_name():
    """主语集合不能只剩一个两字母缩写：LV 篇的 topic 字段就是 "LV"，
    纯 ASCII 短于 4 被挡之后，如果 aliases 里再不写"路易威登"，
    这个领域就没有任何可用的主语名——中文标题的真图会全被当成跑题。
    所以每个领域都必须至少有一个"够长或含中文"的主语词。"""
    import glob
    import images as I
    import outline as O
    for path in sorted(glob.glob(os.path.join(ROOT, "config", "topics", "*.json"))):
        topic = os.path.basename(path)[:-len(".json")]
        cfg = O.load_for_topic(topic, root=ROOT)
        subj = I.subject_tokens(cfg)
        strong = [t for t in subj if (not t.isascii()) or len(t) >= 4]
        assert strong, u"%s 篇没有可用主语名（只有 %s），中文图会被全判跑题" % (topic, subj)
        if cfg.topic.isascii():
            # 领域名本身是拉丁缩写（LV），短到不能当主语 → 必须声明中文全称，
            # 否则"路易威登 手袋"这种真图会被判成跑题。
            cjk = [t for t in subj if not t.isascii()]
            assert cjk, u"%s 篇的领域名是拉丁缩写，aliases 里必须补中文全称：%s" % (topic, subj)


def test_per_section_budget_cannot_outrun_the_page_budget():
    """提示词按"每章多少字"要货，闸门按"整页多少字"验收。
    两边各写一套数字时，模型写得越认真越必挂——咖啡真实翻车：
    12 章 × 上限 1600 = 19200 字，而 G-05 的上限是 6500，实测产出 18107 字。"""
    import generate as G
    bar = json.loads(_read("config", "quality_bar.json"))
    for name in sorted(os.listdir(os.path.join(ROOT, "config", "topics"))):
        topic = name[:-5]
        cfg = O.load_for_topic(topic, root=ROOT)
        n = len(cfg.sections)
        lo, hi = G.section_budget(bar, n)
        assert n * hi <= bar["words"]["max_chars"] * 1.02, (
            u"%s：%d 章 × 每章上限 %d = %d，超过整页上限 %d" % (
                topic, n, hi, n * hi, bar["words"]["max_chars"]))
        assert n * lo >= bar["words"]["min_chars"] * 0.9, (
            u"%s：%d 章 × 每章下限 %d = %d，够不到整页下限 %d" % (
                topic, n, lo, n * lo, bar["words"]["min_chars"]))


def test_length_tolerance_matches_the_developers_number():
    """开发者 2026-09-19：「超出 2000 字以内可接受」。
    这句话现在钉在配置里：硬上限必须正好等于目标上限 + 2000。
    数字写两遍而不互相约束，下次改一个就会悄悄漂移。"""
    bar = json.loads(_read("config", "quality_bar.json"))
    w = bar["words"]
    assert w["hard_max_chars"] == w["max_chars"] + w["overrun_tolerance_chars"], \
        u"硬上限 %d ≠ 目标 %d + 容忍 %d" % (
            w["hard_max_chars"], w["max_chars"], w["overrun_tolerance_chars"])
    assert w["min_chars"] <= w["max_chars"] < w["hard_max_chars"]


def test_section_budget_follows_the_outline_not_just_the_config(tmp_path, monkeypatch):
    """G-05 的区间来自大纲（按 reading_target_minutes 缩放），
    每章预算却从 config 的固定字区间算——只有 10 分钟的大纲才碰巧一致。
    一旦 --minutes 改成 20 或 5，提示词与闸门又会各说各话（本轮已翻过一次车）。"""
    import generate as G
    import outline as O
    bar = json.loads(_read("config", "quality_bar.json"))
    src = json.loads(_read("config", "topics", u"咖啡.json"))
    src["reading_target_minutes"] = 20
    d = tmp_path / "config" / "topics"
    d.mkdir(parents=True)
    (d / u"长读.json").write_text(json.dumps(src, ensure_ascii=False), encoding="utf-8")
    cfg = O.load_for_topic(u"长读", root=str(tmp_path))
    lo, hi = cfg.words_range
    assert hi > bar["words"]["max_chars"], "20 分钟大纲的目标上限应当高于 10 分钟"
    slo, shi = G.section_budget(bar, len(cfg.sections), total=cfg.words_range)
    assert len(cfg.sections) * shi <= hi * 1.02, \
        u"每章上限 × 章数 %d 超过整页上限 %d" % (len(cfg.sections) * shi, hi)
    assert len(cfg.sections) * slo >= lo * 0.9


def test_reading_minutes_env_override_moves_both_sides(tmp_path, monkeypatch):
    """--minutes 的实现方式：环境变量喂给大纲，提示词与闸门共用同一个换算口。"""
    import outline as O
    monkeypatch.setenv("KE_READING_MINUTES", "5")
    cfg = O.load_for_topic(u"咖啡", root=ROOT)
    lo5, hi5 = cfg.words_range
    monkeypatch.delenv("KE_READING_MINUTES")
    cfg2 = O.load_for_topic(u"咖啡", root=ROOT)
    lo10, hi10 = cfg2.words_range
    assert hi5 < hi10 and lo5 < lo10, \
        u"改读时不改变换算区间：%s vs %s" % ((lo5, hi5), (lo10, hi10))


def test_the_data_contract_allows_the_published_site_block(data_schema):
    """`publish.py record` 会往 `data.json` 写 `site`，schema 必须收得下它。

    这条是被真实闸门逼出来的：`topic_data.schema.json` 是 `additionalProperties: false`，
    我加了字段却没同步 schema，`validate --all` 立刻把那一整篇判死（G-10）——
    而 G-10 判死会让索引静默跳过该篇，看起来像"发布把页面弄坏了"。
    写产物的代码和约束产物的契约必须同一次改。
    """
    props = data_schema["properties"]["site"]["properties"]
    for field in ("url", "slug", "content_sha", "published_date", "access", "project_id"):
        assert field in props, u"site 少了 %s" % field
    # 只记 URL 不记 projectId，等于让下一次更新靠记忆认站——我已经把策略改到错的站上去过
    assert "project_id" in data_schema["properties"]["site"]["required"], \
        u"project_id 必须是必填：一个 URL 说不出它属于哪个站"
    assert data_schema["properties"]["site"]["additionalProperties"] is False, \
        u"site 也要关紧：它是会被 G-14 当权威源读的字段，多一个没人知道的东西更糟"


def test_prose_floor_in_config_and_schema_is_one_number_not_two():
    """`prose_min_chars` 在 config、`prose.text.minLength` 在 schema，写两遍必然漂移：
    每章预算从 900–1400 降到 ~450 后，60–75 字的正常段落被 schema 判死，
    咖啡 12 章全写完了却出不了页面。"""
    bar = json.loads(_read("config", "quality_bar.json"))
    schema = json.loads(_read("config", "topic_data.schema.json"))
    assert schema["$defs"]["prose"]["properties"]["text"]["minLength"] == \
        bar["words"]["prose_min_chars"], "两处下限不一致，改一处等于没改"


@pytest.mark.parametrize("year", ["1931", "15世纪", "1960年代", "约1900", "1645", "8世纪",
                                  "2023/24", "前5世纪", "2022.11–2023.9", "1921年创立当天"])
def test_timeline_year_is_a_display_label_not_a_parseable_date(year):
    """这一格模板只是原样印在时间轴左栏（renderers.tsx 的 .yr），没有任何代码解析或排序它。
    用正则白名单"合法年份写法"是打地鼠：09-19 为了 2023/24 放宽过一次，
    香奈儿价格史又写出 "2022.11–2023.9"（一轮持续十个月的调价），照样判死。
    结构约束要的是"短"，不是"符合我目前见过的写法"。"""
    blk = {"type": "timeline", "items": [
        {"year": year, "text": u"这一格讲该年发生的具体事件，长度足够不被别的闸门拦下。"},
        {"year": "1931", "text": u"第二条只为满足 timeline 至少两项的结构要求。"}]}
    errs = _block_errors("timeline", blk)
    assert errs == [], u"%r 不该被拒：%s" % (year, errs[0].message if errs else u"")


def test_timeline_year_still_rejects_a_whole_sentence():
    """放宽成"短标签"不等于放开：整句话塞进年份栏会把左栏撑坏，这个必须还拦得住。"""
    blk = {"type": "timeline", "items": [
        {"year": u"1" * 40, "text": u"正常的一句话说明。" * 4},
        {"year": "1931", "text": u"正常的一句话说明。" * 4}]}
    assert _block_errors("timeline", blk), u"年份栏长到 40 字都拦不住，版式就交给 G-13 撞了才知道"


def test_steps_allow_a_one_line_craft_step():
    """steps 的设计目标就是"一帧一步"（香奈儿那一章的标题原话），一句话正是它该有的样子。
    8 字下限把"每片单独绗缝。"这种又对又密的步骤判死，等于逼模型往工艺步骤里灌水，
    而防灌水的闸门本来就是页面级的 G-05。"""
    good = {"type": "steps", "title": u"一道工序一步", "items": [
        {"n": 1, "title": u"分片", "text": u"每片单独绗缝。"},
        {"n": 2, "title": u"车格", "text": u"直针走满包身。"},
        {"n": 3, "title": u"装五金", "text": u"皮条手编穿链。"}]}
    assert _block_errors("steps", good) == [], u"真产物里的三步被 schema 判死了"
    stub = {"type": "steps", "items": [{"n": 1, "text": u"好"}, {"n": 2, "text": u""}]}
    assert len(_block_errors("steps", stub)) == 2, u"空/单字的步骤必须还是被拦"


def test_a_declared_cover_is_accepted_by_the_contract():
    """封面以前只能靠"最宽的一张"，索引卡片上就会出现排行榜截图与宣传横幅
    （09-23 实测：大模型篇封面是 3564px 宽的排行榜、AI 眼镜篇是 3840px 的光波导渲染图，
    两张都被 `object-fit:cover` 裁掉半截文字，卡片看着像坏了）。
    声明封面要三处都认：契约、模板、索引——少一处就是"写了不生效"。"""
    import json as _json
    import generate as G
    data = _json.loads(_read("tests", "fixtures", "mini_data.json"))
    data["cover"] = dict(data["sections"][1]["images"][0])
    errs = G._schema_errors(data)
    assert not errs, u"契约不接受声明封面：%s" % errs[:2]


def test_a_declared_cover_must_still_be_a_real_image_shape():
    """声明封面不是开后门：它仍然必须是同一套图片形状。
    否则"封面"会变成第二个不受契约管的图片来源（R-03 要求每张图有来源页）。"""
    import json as _json
    import generate as G
    data = _json.loads(_read("tests", "fixtures", "mini_data.json"))
    data["cover"] = {"file": "images/02_test_b.jpg"}   # 缺 alt 与 source_page
    errs = G._schema_errors(data)
    assert errs, u"缺 alt / source_page 的封面被放过了"


def test_the_outline_contract_carries_the_manual_image_exclusions():
    """W-120：人眼摘掉的图会被下一次重做原样抓回来，所以排除要能写进大纲。
    契约这里管两件事：字段存在，且值必须是 URL——
    写成裸域名或正则都会让「排除」静默失效，而那比没有排除更坏。"""
    import outline as O
    for t in (u"Muse", u"爱马仕", u"LV"):
        cfg = O.load_for_topic(t, root=ROOT)
        assert getattr(cfg, "image_exclude_pages", None), u"%s 没带上排除表" % t
        assert all(u.startswith("http") for u in cfg.image_exclude_pages)


def test_the_outline_contract_allows_declaring_the_image_primary_subject():
    """品牌单词档默认由「本大纲检索词的覆盖率」自动定（见 images.subject_tokens），
    但人可以覆盖它。要能写进大纲就得在 schema 里声明——`topic_outline.schema.json`
    是 `additionalProperties:false`，没声明的字段会让大纲加载直接失败（G-10）。
    同时钉住"不许给点名闸门开后门"：声明的词必须本来就在主语集合里。
    本篇**故意不声明**，让自动规则去挑，这样这条规则在真数据上是活的。"""
    import images as I
    import json as _json
    schema = _json.loads(_read("config", "topic_outline.schema.json"))
    assert "image_primary_subject" in schema["properties"], \
        u"schema 没声明这个字段，写进大纲就会被 G-10 判死"

    cfg = O.load_for_topic(u"Muse产业逻辑", root=ROOT)
    assert not getattr(cfg, "image_primary_subject", ""), \
        u"本篇该让自动规则选品牌词，声明会把它盖掉"
    subj = I.subject_tokens(cfg)
    prim = I.primary_subject(subj)
    cov = sum(1 for s in cfg.sections
              if I.names_subject(u" ".join(map(str, s.image_queries or [])).lower(), [prim]))
    assert cov >= 3, u"自动挑的品牌词 %r 只在 %d 章的检索词里出现过" % (prim, cov)

    for t in sorted(os.listdir(os.path.join(ROOT, "config", "topics"))):
        if not t.endswith(".json"):
            continue
        c = O.load_for_topic(t[:-5], root=ROOT)
        declared = getattr(c, "image_primary_subject", "")
        assert not declared or declared.lower() in I.subject_tokens(c), \
            u"%s 声明了一个不在主语集合里的品牌词：%s" % (t[:-5], declared)
