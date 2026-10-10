# -*- coding: utf-8 -*-
"""第 12 种区块 code 进闸门后的正反例（W-171）。

本文件的每一条都必须**同时**有正例：只测"坏了会报错"，闸门在永远返回空列表时
也能"通过"（tests/test_gates.py 开头那句话同样适用于这里）。
"""
import copy

import validate as V
from test_gates import by_id, run


def _code(code=u"client.chat.completions.create(\n    model=\"gpt-6\",  # 假设部署名\n)", **over):
    b = {
        "type": "code",
        "lang": "python",
        "heading": "一次非流式调用",
        "code": code,
    }
    b.update(over)
    return b


def _ctx_with_block(passing_ctx, block):
    data = copy.deepcopy(passing_ctx.data)
    data["sections"][0]["blocks"].append(block)
    ctx = copy.copy(passing_ctx)
    ctx.data = data
    return ctx


def test_G10_accepts_a_wellformed_code_block(passing_ctx):
    """正例先立住：合法代码块不该被 schema 判死，否则反例毫无信息量。"""
    ctx = _ctx_with_block(passing_ctx, _code())
    assert not run(by_id("G-10"), ctx), run(by_id("G-10"), ctx)[:2]


def test_G10_rejects_a_tab_in_a_code_block(passing_ctx):
    """制表符会让缩进随标签宽度变形，照着抄的人得到错位代码。"""
    ctx = _ctx_with_block(passing_ctx, _code(code=u"if x:\n\ty = 1"))
    assert run(by_id("G-10"), ctx), "代码块里的制表符没被 schema 拦住"


def test_G10_rejects_a_loose_lang_label(passing_ctx):
    """lang 是给人认门的标，写成 "Python 3.12" 会变成版面上的毛刺。"""
    ctx = _ctx_with_block(passing_ctx, _code(lang="Python 3.12"))
    assert run(by_id("G-10"), ctx), "松散的语言标没被拦住"


def test_G10_rejects_an_empty_code_body(passing_ctx):
    ctx = _ctx_with_block(passing_ctx, _code(code=u""))
    assert run(by_id("G-10"), ctx), "空代码块被放过了"


def test_G06_does_not_demand_sources_for_parameters_in_code(passing_ctx):
    """设计决策钉在这里：**代码不是断言载体**。

    示例里的端口、超时、max_output_tokens 是参数，不是可核查的事实。
    若让 G-06 对代码里的数字要来源，只会逼作者去编一个出处（R-02 的反面）。
    """
    ctx = _ctx_with_block(passing_ctx, _code(code=u"timeout = 30  # 秒\nport = 8000"))
    assert not run(by_id("G-06"), ctx), run(by_id("G-06"), ctx)[:2]


def test_a_code_blocks_own_numbers_do_not_escape_the_other_gates(passing_ctx):
    """但 caption/heading 里的数字仍走原规则：断言写在说明文字里就要来源。

    这条是给"把事实塞进代码块旁白来绕开引用"留的后路——旁白是 prose 性质。
    """
    ctx = _ctx_with_block(passing_ctx, _code(caption=u"这段返回 1,024 个 token"))
    assert run(by_id("G-06"), ctx), "写在 caption 里的数字一条警告都没有"


def test_data_text_includes_code_so_placeholders_are_visible(passing_ctx):
    """`<占位>`、TODO 这类字符串只可能在代码里出现。

    把它算进全文抽取，是让占位符类闸门（G-07 那一族）有机会看见它的前提；
    不算进去，"检查通过"就等于"没检查"。
    """
    ctx = _ctx_with_block(passing_ctx, _code(code=u"api-key = <你的密钥>  # TODO 换成 Entra Token"))
    text = V.data_text(ctx.data)
    assert u"<你的密钥>" in text and u"TODO" in text


# ── 加了 code 之后，三条"按全文量"的闸门需要分别决定要不要把代码算进去 ──────────
#
# 每一条**放宽**都必须配一条"仍然抓得住"的反测，否则改的就不是精度而是闸门。

def _tight_bar(ctx, hard):
    """把篇幅上限压到 hard，并且**不留软上限带**。

    留了软上限带的话，散文一过 `max_chars` 就出 warn，`assert not run(...)`
    会因为一条与本次断言无关的 warn 而红——第一版就是这么错的：
    它把夹具自带的六百多字当成"没超"，hard 设成 300，于是代码算不算都红。
    """
    import copy as _c
    bar = _c.deepcopy(ctx.bar)
    bar.setdefault(u"words", {})[u"hard_max_chars"] = hard
    bar[u"words"][u"min_chars"] = 10
    bar[u"words"][u"max_chars"] = hard          # 软=硬 ⇒ 只有"超硬上限"这一种失败
    c = _c.copy(ctx)
    c.bar = bar
    c._outline = type(u"o", (), {
        "words_range": (10, hard),
        "sections": ctx._outline.sections,
    })()
    return c


def _prose_cjk(ctx):
    return V.cjk_count(V.data_text(ctx.data, include_code=False))


def test_G05_does_not_charge_reading_time_for_code(passing_ctx):
    """读代码不是读汉字：625 字/分钟这个换算只对散文成立。

    教学篇一旦把代码算进篇幅，就会得到一条荒谬的激励——**少给代码来达标**。
    W-171 实测：全文 9641 汉字，其中 code 块贡献 1229，去掉之后 8369 在硬上限内。
    """
    ctx = _ctx_with_block(passing_ctx, _code(code=u"# " + u"注释" * 260))
    base = _prose_cjk(ctx)
    assert base > 100, u"夹具散文太短，这条测试量不出东西：%d" % base
    tight = _tight_bar(ctx, base + 20)          # 代码那 520 字一旦计入就必然越线
    assert not run(by_id("G-05"), tight), u"只有代码超长、散文没超，却被 G-05 判死"


def test_G05_still_rejects_prose_over_the_hard_cap(passing_ctx):
    """上一条的反测：把同样的量换成散文，必须照样判死。"""
    ctx = _ctx_with_block(passing_ctx, {
        "type": "prose", "text": u"正文" * 400, "source_ids": []})
    base = _prose_cjk(ctx)
    tight = _tight_bar(ctx, base - 100)         # 硬上限压到散文之下
    assert run(by_id("G-05"), tight), u"散文超硬上限却没报错，说明这条闸门被改废了"


def test_G05_treats_a_code_caption_like_a_figure_caption(passing_ctx):
    """代码块的旁白与图注是同一类东西：**标签**，不是正文。

    闸门本来就不把 `images[].caption` 算进篇幅（`data_text` 根本不读 images）。
    第一版我给 code 开了"旁白照算、正文不算"的半口径，于是同一篇里
    图注不计、代码注记，读者看不出这两者有什么原则上的差别。
    对齐成一条：**标签一律不进篇幅**。

    基线必须从**没有代码块的夹具**上取：写成"先量带块的数再压上限"的话，
    基线自己就把旁白算进去了，上限跟着一起涨——那条测试会永远绿而什么都没量到
    （第一版就是这么假绿的）。
    """
    import copy
    base = V.cjk_count(V.data_text(copy.deepcopy(passing_ctx.data), include_code=False))
    ctx = _ctx_with_block(passing_ctx, _code(
        heading=u"标签" * 25, caption=u"说明" * 25, code=u"x = 1"))
    tight = _tight_bar(ctx, base + 10)
    assert not run(by_id("G-05"), tight), u"代码旁白被当成正文计入了篇幅"


def test_a_code_caption_cannot_become_a_second_prose_channel(passing_ctx):
    """上一条的**补偿约束**：既然标签不计篇幅，标签就必须短到不能装正文。

    没有这条，"把散文挪进 caption" 就成了绕开红线的后门——
    图注那边有同样的风险，但图注一直是短的，代码旁白是新开的口子，得先钉住。
    """
    long_cap = u"很长的一段正文说明" * 30
    ctx = _ctx_with_block(passing_ctx, _code(caption=long_cap))
    assert run(by_id("G-10"), ctx), u"caption 长到能装下一段正文却没被 schema 拦住"


def test_G07_does_not_flag_json_closing_braces(passing_ctx):
    """`{"type":"object"}}}` 是 JSON，不是没展开的模板。

    `quality_bar.placeholders` 里那两条裸的 `{{` / `}}` 是在没有代码块的时代写的；
    有了 code 之后，任何一段 API 示例都会撞上它。真正的模板泄漏长这样：
    `{{ user_name }}`，而那条正则本来就能抓。
    """
    ctx = _ctx_with_block(passing_ctx, _code(
        code=u'{"type":"object","properties":{"a":{"type":"string"}}}'))
    assert not run(by_id("G-07"), ctx), run(by_id("G-07"), ctx)[:1]


def test_G07_still_catches_a_leaked_template(passing_ctx):
    """上一条的反测：`{{ 变量 }}` 这种没展开的模板必须照样红。"""
    ctx = _ctx_with_block(passing_ctx, {
        "type": "prose", "text": u"你好 {{ user_name }}，下面继续说别的。"})
    assert run(by_id("G-07"), ctx), u"模板变量没展开却没报错"


def test_G07_allows_the_word_placeholder_used_as_a_noun(passing_ctx):
    """教学篇会**谈论**占位符，这不等于页面上留了一个没填的空。

    实测撞上的原句是「尖括号全是占位符」——一句正当的说明被判成占位符残留。
    """
    ctx = _ctx_with_block(passing_ctx, {
        "type": "prose", "text": u"示例里的尖括号全是占位符，读者要换成自己的端点。"})
    assert not run(by_id("G-07"), ctx), run(by_id("G-07"), ctx)[:1]


def test_G07_still_catches_a_bracketed_placeholder(passing_ctx):
    """上一条的反测：**形状像占位**的那种要照样红（尖括号里写"占位"）。"""
    ctx = _ctx_with_block(passing_ctx, {
        "type": "prose", "text": u"请把 <占位> 换成真实值再运行，否则一定报错。"})
    assert run(by_id("G-07"), ctx), u"页面上真留着 <占位> 却没报错"
