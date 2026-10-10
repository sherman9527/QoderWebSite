# -*- coding: utf-8 -*-
"""W-189 的第二个坑：**命中要带语境**，否则大文档里全是假证据。

10-05 把 PDF 原文接进来之后实测到的（`.probe/w191_six.txt`）：名创那 6 个股份支付数
一个都没因此变可核，而裸搜 `0.189` / `2.790` 在 80 万字的财报与行情 JSON 里
撞进的是 `peggedUSD":0.18998100035449358`、`created":1784215858` 这种无关串。
字符串匹配分不开"同一个数、同一件事"与"同一个数、另一件事"——
W-162/W-164 已经两次得出这个结论，这次是它第一次**在原文层上重演**。

所以工具不许沉默地把这种命中算成证据：它必须自己标出来。
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "audit", "tools"))
import w164_evidence as E  # noqa: E402


def test_a_digit_hit_without_any_word_overlap_is_flagged_as_suspect():
    text = (u'"Plasma":{"current":{"peggedUSD":0.18998100035449358},'
            u'"circulatingPrevDay":{"peggedUSD":0.19}}')
    row = u"股份支付 0.189 亿元"
    found = E.hits(text, u"0.189", row)
    assert found, u"这条本来就是想复现「数字相同」的命中，结果连命中都没有"
    assert all(not strong for _w, strong, _s, _k in found), \
        u"既没有语境词、窗口里也没有单位声明，却被判成强证据 ⇒ 疑撞号这一档形同虚设"


def test_a_real_match_shares_words_with_the_row_and_is_not_flagged():
    text = u"截至 2025 年 12 月 31 日，本集团以股份为基础的支付开支为 0.189 亿元，计入管理费用。"
    row = u"以股份为基础的支付 0.189 亿元"
    found = E.hits(text, u"0.189", row)
    assert found and any(ctx for _w, ctx, _s, _k in found), \
        u"真命中也被标成疑撞号，这一档就成了噪声"


def test_a_cross_language_unit_hit_is_only_eyeballed_not_verified():
    """10-05 撞到的第五犯：正文「3.679 亿元」，S031 写 RMB367.9 million 且逐字标着
    equity-settled share-based payment expenses。换算这一半必须会，
    但中文行与英文原文永远不会有词面重合 ⇒ 这类命中**只进待眼验档**。
    尺子不许把自己没法核的标成已核：把单位词也算强证据的那一晚，
    Cerebras 61 个命中里 48 个只靠邻近一个 million，"零疑点"是规则造的假清爽。"""
    text = (u"there were eight items including (ii) equity-settled share-based payment "
            u"expenses of RMB367.9 million (US$52.6 million), (iii) interest expenses")
    row = u"权益结算的股份支付 3.679 亿元"
    found = E.hits(text, u"3.679", row)
    assert found, u"换算写法没被搜出来——这就是那 6 个数被误判成欠账的原因"
    assert any(scaled for _w, _v, scaled, _e in found), u"换算命中没被标出来"
    assert all(not verified for _w, verified, _s, _e in found), \
        u"跨语言的命中被判成已核 ⇒ 词面没重合，谁也没看见它是同一件事"
    assert any(eyeballed for _w, _v, _s, eyeballed in found), \
        u"降档之后它应当落进待眼验那一档，而不是消失"


def test_a_chinese_row_matched_by_a_chinese_source_line_is_verified():
    """同一件事实如果原文就用中文写着，那才算已核——降档不许把真证据一起埋掉。"""
    text = u"于2025年度，权益结算的股份支付费用为人民币3.679亿元，计入管理费用。"
    row = u"权益结算的股份支付 3.679 亿元"
    found = E.hits(text, u"3.679", row)
    assert found and any(verified for _w, verified, _s, _e in found), \
        u"中文对中文的真命中被判成未核：%s" % found[:1]


def test_emit_decision_only_accepts_a_row_whose_numbers_all_live_in_one_source():
    """生成器的三条门槛都要能单独失效：缺一条就不许生成。
    四篇跑出来 0 条，先要能证明这是事实而不是这里写错了。"""
    def row(toks, hits, cited):
        return {u"topic": u"T", u"章": u"s1", u"块": u"2", u"定位": u"keyvalue_table[0]",
                u"行文本": u"海外零售店销售 71.79 亿元 ÷ 185 店", u"toks": toks,
                u"hits_by_tok": hits, u"cited": set(cited), u"cur": list(cited)}

    both = row([u"71.79", u"185"], [[(u"S107", u"…", True, False, True)],
                                    [(u"S107", u"…", True, False, True)]], [u"S023"])
    out = E.emit_decision([both], u"T")
    assert len(out) == 1 and out[0][u"ids"] == [u"S023", u"S107"], out

    split = row([u"71.79", u"185"], [[(u"S107", u"…", True, False, True)],
                                     [(u"S063", u"…", True, False, True)]], [u"S023"])
    assert E.emit_decision([split], u"T") == [], u"两个数分属两条来源，不许生成"

    weak = row([u"71.79"], [[(u"S107", u"…", False, True, False)]], [u"S023"])
    assert E.emit_decision([weak], u"T") == [], u"待眼验的命中不许变成裁决"

    already = row([u"71.79"], [[(u"S023", u"…", True, False, True)]], [u"S023"])
    assert E.emit_decision([already], u"T") == [], u"数已在已挂来源里，不该再生成"

    # 派生数那一档：娇兰 1.77 €/ml = 52.99 ÷ 30ml，来源页里出现 1.77 是巧合
    d = row([u"1.77"], [[(u"S0914", u"…", True, False, True)]], [u"S071"])
    d[u"derived"] = [True]
    assert E.emit_decision([d], u"T") == [], u"本行算出来的数被当成原文里的证据"
    d2 = row([u"1.77"], [[(u"S0914", u"…", True, False, True)]], [u"S071"])
    d2[u"derived"] = [False]
    assert len(E.emit_decision([d2], u"T")) == 1, u"过滤太宽，把真命中也滤掉了"


def test_a_two_letter_fragment_is_not_context():
    """"词面重合"必须重：`US`、`AI`、`Q2`、`GB` 这种碎片在中英混排的表里到处都有。
    10-05 的第二次假清爽就是这么来的——把单位词降档之后"待眼验"仍是 0，
    因为 57 个命中都"重合"在两个字母上。"""
    assert E.row_words(u"美国 30 年期国债收益率 4.85%") == [u"美国", u"年期国债收益率"] or \
        u"美国" in E.row_words(u"美国 30 年期国债收益率 4.85%")
    assert not E.row_words(u"US AI Q2 GB 4.85%"), u"两字母碎片被当成了语境词"
    assert E.row_words(u"revenue grew 18.9%") == [u"revenue", u"grew"], E.row_words(u"revenue grew 18.9%")


def test_a_hit_that_shares_only_a_two_letter_token_is_eyeballed():
    text = u"US revenue for the segment was 8.15 billion, up 2.7% YoY, while the US$ figure rose to 8.15."
    row = u"亚太区 8.15 亿美元"          # 唯一"重合"的是 US 这种碎片 + 数字
    found = E.hits(text, u"8.15", row)
    assert found and all(not verified for _w, verified, _s, _e in found), \
        u"只重合在碎片上的命中被判成已核"
    assert any(eyeballed for _w, _v, _s, eyeballed in found), u"待眼验这一档没接住它"
    assert found, u"这条本来要复现的是碎片造成的假重合"
    assert all(not verified for _w, verified, _s, _e in found), \
        u"两字母碎片就把命中判成已核 ⇒ 语境档形同虚设"


def test_the_article_own_brand_name_is_not_a_context_word():
    """第三次假清爽就是它：一篇讲爱马仕的文章里每个窗口都含「爱马仕」，
    于是任何数字只要落在正文附近都算"词面重合、已核"。三条自动补挂就是这么挂错的
    （S034 是一篇讲配货的转载稿，与 €10,600 公价无关）——已用 w164_revert.py 回退。"""
    row = u"巴黎（欧元区专柜） €9,600 €10,600 较上年 +7.3%"
    keep = E.row_words(row, stop=[u"爱马仕", u"Hermès"])
    assert any(u"巴黎" in w for w in keep) and any(u"欧元区" in w for w in keep), keep
    assert not any(u"爱马仕" in w for w in keep), keep
    # 停用词只摘掉品牌本身，不许把整行的其它词一起抹掉（抹光等于没有语境档）
    assert len(keep) >= 2, keep


def test_version_numbers_and_dates_are_not_quantities():
    """第四个洞（10-06 全站扫完才露出来）：`1.2.6` 是版本号、`2027.12.31` 是日期，
    被当成"缺出处的数"之后，劳斯莱斯与 Muse产业逻辑 各背着几条根本不存在的欠账。
    形状判据：两个点以上 = 版本或日期；`20xx.n[.n]` = 日期。

    这里断的是**整个集合相等**而不是 `in / not in`：上一版写了两条 `... or True`，
    那是永远不会红的断言——而这条测试要钉的正是"哪些数算量"，含糊不得。
    （顺带钉住既有行为：个位/两位的裸数本来就不算 claim。）
    """
    import w164_measure as M
    assert M.claims(u"FrontierCode v1.2.6 榜单得分 71.4 分") == set([u"71.4"])
    assert M.claims(u"许可期自 2026.1.1 起至 2027.12.31 止，共 63 个月") == set()
    # 量级写法只有一个点，不许误伤
    assert M.claims(u"员工 1.2 万人") == set([u"1.2"])
    assert M.claims(u"市值 2,778.4 亿元") == set([u"2,778.4"])
    assert M.claims(u"增速 8.5%") == set([u"8.5%"])


def test_a_bare_number_without_a_unit_word_generates_no_scaled_forms():
    """第五个洞（10-06 摊窗口给人读时才露出来）：换算写法是从**裸值**除以每个单位词生成的，
    于是 `0.61` 除了 0.00061 还会生成 `1` 和 `0` 这种探针——它在**每一条**来源里都命中。
    Jev 一篇的一个 κ 数因此摊出 35 条"候选来源"，全都报"已核/按单位换算"。
    换算只该在有单位词时发生：`3.679 亿元` 有，`κ 0.61` 没有，`8.5%` 也没有。
    """
    assert E.scaled_forms(u"0.61", u"κ 按 Landis & Koch 分档，0.61–0.80 才算实质一致") == []
    assert E.scaled_forms(u"8.5%", u"增速 8.5%") == []
    assert E.scaled_forms(u"1.19", u"Score 各档位期望值 1.19，不能插值") == []
    # 而它原本要救的那一类不许一起死掉（第⑩洞之后它返回 `(写法, 因子集)`，
    # 因子是要带给 `hits()` 做「声明配套」用的）
    assert u"367.9" in [f for f, _fac in E.scaled_forms(u"3.679", u"股份支付 3.679 亿元")], \
        u"单位盲区那一档被这次修法打回了原形"


def test_a_tiny_probe_cannot_make_one_row_hit_every_source():
    """同一件事从命中侧钉住：`0.61` 不该在只写着 `1` / `61` 的原文里被判成已核。"""
    body = (u"An evidence cutoff of 1 splits them in half. The confident half is right "
            u"90% of the time; the other half, 40%. Landis and Koch table.")
    row = u"κ 按 Landis & Koch 的粗分档，0.61–0.80 才算实质一致"
    found = E.hits(body, u"0.61", row)
    assert not [f for f in found if f[1]], \
        u"裸小数被换算成 1/61 之后到处算已核：%s" % [f[0][:60] for f in found][:3]


def test_a_european_decimal_comma_page_is_the_same_number():
    """第六个洞（10-06 读 A 类欠账时撞出来的）：娇兰挂的是德语价页，页上写 `48,50 €`，
    正文写 `48.50 €`。`norm_spans()` 只治千分位，不管小数点分隔符，于是整张价表
    被报成"来源里没有这个数"——那不是欠账，是尺子少认一种写法。

    只放开**点+恰好两位数字**这一种对应（`48.50`↔`48,50`）：千分位组是三位，
    放开三位就会把英文的 `1,234` 当成小数，等于用一个新假阳性换一个假阴性。
    """
    body = (u"GUERLAIN Abeille Royale Cleansing Care-in-Mousse 36,29 € "
            u"UVP 63,00 € 30-Tage Bestpreis 48,50 € In den Warenkorb")
    row = u"单支 50ml Bestpreis 63.00 欧，另装 48.50 €"
    got = [f for f in E.hits(body, u"63.00", row) if f[1]]
    assert got, u"德语小数写法没被认成同一个数"
    assert u"63,00" in got[0][0]
    got2 = [f for f in E.hits(body, u"48.50", row) if f[1]]
    assert got2, u"第二个价也没认出来"


def test_the_label_judge_recognises_the_decimal_comma_but_not_a_thousands_group():
    """同一件事在 label 判据那一层：`63.00` 要认得页上的 `63,00`，
    但 `1.234` 不许认得 `1,234`——后者在英文里是 1234、在德文里是 1.234，
    纯字符串分不开，所以只在"点+恰好两位"这一种形状上放开，别的一律不猜。"""
    import w164_measure as M
    assert M.in_label(u"63.00", u"UVP 63,00 € 30-Tage Bestpreis")
    assert M.in_label(u"48.50", u"48,50 €In den Warenkorb")
    assert M.in_label(u"8.50%", u"Rabatt 8,50%")
    assert not M.in_label(u"1.234", u"共 1,234 件"), u"三位小数被当成欧洲小数点，会把 1234 认成 1.234"
    assert not M.in_label(u"63.00", u"UVP 630,00 €")


def test_a_per_million_token_rate_matches_the_per_token_price_in_the_source():
    """第七个洞：报价的**分母单位**。表头写"美元/百万 token"，正文写 `1.875`，
    而 OpenRouter 接口原样写 `"completion":"0.000001875"`——同一个价，差 1e6 倍。
    现有换算档只在数旁边有量级词时才换算（这是 W-162 假阳性的教训），
    而这一类的单位词在**表头**里，不在数旁边。

    所以判据必须是"这一列是每百万 token 的价"这句**显式声明**，不是"差 10 的幂就算同一数"。
    """
    body = (u'{"name":"DeepInfra","pricing":{"prompt":"0.00000015","completion":"0.000001875"},'
            u'"provider_name":"DeepInfra","quantization":"bf16"}')
    row = u"DeepInfra 输入 0.15 · 输出 1.875 · 上下文 262k · 量化 bf16"
    cap = u"同一份 Qwen3.8-27B 权重在不同平台的报价（美元/百万 token，2026-10-03）"
    # 洞本身：没有那句声明时，这个数在来源里"查不到"
    assert not E.hits(body, u"1.875", row), \
        u"没有「每百万 token」的声明也按 1e6 换算，等于把 W-162 那条松规则请回来"
    strong = [f for f in E.hits(body, u"1.875", row, unit_ctx=cap) if f[1]]
    assert strong, u"给了表头还是认不出 0.000001875"
    assert u"0.000001875" in strong[0][0]


def test_a_declared_rate_needs_a_window_wide_enough_to_see_whose_price_it_is():
    """窗口宽度也是判据的一部分：JSON 一条记录六七百字，`"0.000001875"` 离
    `"provider_name":"DeepInfra"` 有 130 字，而窗口只开 ±70 ⇒ 语境词一律落窗外，
    真命中被判成"没命中"（10-06 实测：S031 命中 0 处）。

    只对**声明过 rate 的探针**放宽窗口，普通探针仍按原宽度——
    放宽的是"看得见主语"，不是"降低证据门槛"。
    反向那条钉住这一点：数字相同但整段里没有这一行的主语，依旧不算已核。
    """
    rec = (u'{"name":"DeepInfra | qwen/qwen3.8-27b","context_length":262144,'
           u'"pricing":{"prompt":"0.00000015","completion":"0.000001875",'
           u'"input_cache_read":"0.0000000375","discount":0.25},'
           u'"provider_name":"DeepInfra","tag":"deepinfra/bf16","quantization":"bf16"}')
    row = u"DeepInfra 输入 0.15 · 输出 1.875 · 上下文 262k · 量化 bf16"
    cap = u"标价（美元/百万 token）"
    strong = [f for f in E.hits(rec, u"1.875", row, unit_ctx=cap) if f[1]]
    assert strong, u"rate 探针的窗口太窄，认不出这是 DeepInfra 自己的价"
    assert u"DeepInfra" in strong[0][0]
    other = rec.replace(u"DeepInfra", u"Wafer")
    assert not [f for f in E.hits(other, u"1.875", row, unit_ctx=cap) if f[1]], \
        u"同一个价属于另一家，窗口放宽之后仍不许算已核"


def test_the_source_side_unit_vocabulary_covers_millions_and_traditional_chinese():
    """第九个洞：来源侧的列示单位词太窄。

    实测三例（都在**该行已经挂着**的来源里）：
      · 晶泰控股 FY 公告（繁体）写 `537.9百萬元`，正文写 `5.379 亿元`；
      · 英特尔财报写 `$ 3,939`（列头声明 in millions），正文写 `39.39 亿美元`；
      · LVMH 新闻稿用百万欧元，正文写 `377.7 亿欧元`。
    `_scale_at` 的词典只有 千/万/亿，`百萬元`、`million`、繁体 `萬/億` 一律不认，
    于是这三条全被判成"来源里没有这个数"——和第六洞同族：**是写法，不是欠账**。

    反向也要钉住：没有单位词时不许凭"差 10 的幂"就认（那是 W-162 的老假阳性）。
    """
    import w164_measure as M
    assert M.covered(u"5.379", u"药物发现5.379亿元、同比增418.9%",
                     u"截至2025年12月31日止年度的收入为537.9百萬元，增加418.9%")
    assert M.covered(u"39.39", u"英特尔 DCAI · 2Q26 63 亿美元（2Q25 为 39.39 亿美元）",
                     u"DCAI revenue $ 7,871 $ 3,939 (in millions)")
    assert M.covered(u"377.7", u"时装与皮具营收 377.7 亿欧元",
                     u"Fashion & Leather Goods revenue 37,770 million euros")
    # 没有单位词的裸数不许被"凑"出来
    assert not M.covered(u"39.39", u"英特尔 DCAI 2Q25 为 39.39 亿美元",
                         u"the company reported 3939 orders")


def _pad():
    """HTML 抽出来的表格：每两格之间是一大段「空格 + 换行」。真实宽度要紧——
    ±WIN 是**原文**窗口，这段空白把列头与数值推开出几十字符。"""
    return (u" " + chr(10)) * 24


def test_a_scaled_number_is_covered_when_the_table_header_declares_the_unit():
    """第十个洞（10-07 逐条摊窗口读 A 类欠账读出来的，不是推的）。LVMH 两页原文就是这个形状：

        S113  Millions of euros … Revenue 42,169 41,060 37,770
        S111  Fashion & Leather Goods 41 060 37 770 -8% -5%   ← 千分位是 NBSP

    正文「377.7 亿欧元」= 表里的 37,770 百万。`scaled_forms()` 摊得出 `37770` 这个探针，
    但接受那一档要求窗口里有单位词，而 `unit_ok` 大小写敏感（`Millions` 不认 `million`）、
    又只看 ±WIN——量级声明写在**表头**，不写在格子旁边。于是财务页最主干的几个数被判成
    「来源里没这个数」，差点按 R-02 删掉。
    """
    lvmh = (u"Revenue by business group" + _pad() + u"Millions of euros" + _pad() +
            u"FASHION AND LEATHER GOODS 2023 2024 2025" + _pad() +
            u"Revenue" + _pad() + u"42,169" + _pad() + u"41,060" + _pad() + u"37,770")
    row = u"377.7 亿欧元 时装与皮具营收 占集团 47%"
    found = E.hits(lvmh, u"377.7", row)
    assert found, u"表头写着 Millions of euros、格子里就是 37,770，仍判成没这个数"
    assert all(not f[1] for f in found), u"与该行零词重合的换算命中被报成了已核"
    assert all(f[2] for f in found), u"这一档必须是换算写法，不是字面同一串"


def test_a_bare_table_of_numbers_without_any_declaration_is_still_missing():
    """放宽的那一半要配反例：**没有**任何量级声明时，一长串裸数字不算覆盖。
    只准认「有声明且量级配套」，不许认「旁边有数字」。"""
    body = u"Selected data" + _pad() + u"42,169" + _pad() + u"41,060" + _pad() + u"37,770"
    row = u"377.7 亿欧元 时装与皮具营收 占集团 47%"
    assert not E.hits(body, u"377.7", row), u"没有任何单位声明也算了换算命中"


def test_a_wrongly_declared_magnitude_does_not_cover_a_scaled_number():
    """第二条反例：**声明的量级必须和探针配套**。同样的 `3,939`，表头写 Billions
    就不是 39.39 亿。这条不挡住，「差 10 的幂就算同一个数」会原样回来
    （W-162 造出 31 个假阳性的就是那条松规则）。"""
    body = (u"Segment Results" + _pad() + u"In Billions Unaudited" + _pad() +
            u"Revenue" + _pad() + u"7,871" + _pad() + u"3,939")
    row = u"分部甲 2Q25 为 39.39 亿美元"
    assert not E.hits(body, u"39.39", row), u"量级不配套的表头声明也算了数"


def test_a_rounded_table_value_covers_the_row_that_rounded_it():
    """W-197 的第一例（已核实是**合法取整**）：LVMH S113 的部门表在百万那一档写着
    `Profit from recurring operations 16,836 15,230 13,209`，正文写「132.1 亿欧元」——
    13,209 百万＝132.09 亿，正文取一位小数。第⑩洞之后 `13210` 这个探针仍然对不上
    `13209`，因为尺子只会**逐字找**，不会问「这一格四舍五入到正文的位数是不是它」。
    """
    lvmh = (u"Revenue and profit by business group" + _pad() + u"Millions of euros" + _pad() +
            u"FASHION AND LEATHER GOODS 2024 2025" + _pad() +
            u"Profit from recurring operations" + _pad() + u"15,230" + _pad() + u"13,209")
    row = u"132.1 亿欧元 该部门经常性利润 占集团 74%"
    found = E.hits(lvmh, u"132.1", row)
    assert found, u"来源 13,209 百万就是正文的 132.1 亿，取整一档量测看不见"
    assert all(f[2] for f in found), u"这一档必须是换算写法"


def test_a_source_value_one_step_outside_the_rounding_interval_is_not_covered():
    """W-197 的反例（这条不给锁死，取整就会变成"凑"）：同一张表里若是 `13,159`，
    那是 131.59 亿 ⇒ 四舍五入到一位小数是 **131.6 亿**，不是 132.1 亿 ⇒ 不许算命中。
    区间宽窄由**正文自己写的小数位**定：`132.1` 是一位 ⇒ 半格＝0.05 亿＝5 百万。
    """
    lvmh = (u"Revenue and profit by business group" + _pad() + u"Millions of euros" + _pad() +
            u"FASHION AND LEATHER GOODS 2024 2025" + _pad() +
            u"Profit from recurring operations" + _pad() + u"15,230" + _pad() + u"13,159")
    row = u"132.1 亿欧元 该部门经常性利润 占集团 74%"
    assert not E.hits(lvmh, u"132.1", row), u"区间边缘外一格也被当成同一个数"


def test_a_row_more_precise_than_its_source_is_still_not_covered():
    """W-197 的方向判据：**只认来源细、正文粗**，反过来不认。
    币安 K 线接口返回 `86184.39000000` 这种裸数（没有百万/亿的表头声明），
    正文写 `86,209` —— 那不是取整，是**精度本身没出处**，必须继续挂在清单上。
    """
    body = u'"open","high","low","close"] 1758585600000 112650.99000000 86184.39000000 60024.00000000'
    row = u"BTCUSDT（币安现货） −23.0%（111,999 → 86,209）"
    assert not E.hits(body, u"86,209", row), u"正文比来源更精确也算成覆盖，取整就变成凑了"
