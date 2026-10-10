# -*- coding: utf-8 -*-
"""W-196①：`w162_rows.tsv` 的 `定位` 必须**带上行下标**。

原来所有行都写成 `块型[-]`。同一张价表的 9 行于是共用一个 key，
下游按 `(章, 块, 定位)` 取 `行文本` 时字典里留下的是**最后一行**那一格——
`缺的数` 来自别的行，`行文本` 却是最后一行，两个不相关的东西配成一对。
后果不是难看，是会做错事：`split_derived()` 拿这一行的数去配对判「是不是本行算出来的」，
operand 错了就把每毫升单价（娇兰 `1.62` = 48.50÷30）判成「不是派生」，
让它漏进「按 R-02 该删」那一档。

块级的那种（prose/quote，本来就没有行）继续写 `[-]`，它走 `addids` 不走 `chip`。
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "audit", "tools"))
import w162_measure as M  # noqa: E402


def _slots(b):
    """统一成 [(定位, 行文本, 挂着来源)]，这样测试与写入方看到的是同一个约定。"""
    out = []
    for u in M.units(b):
        assert len(u) == 3, u"units() 必须产出 (定位, 行文本, source_ids)，现在是 %r" % (u,)
        out.append(u)
    return out


def test_two_cited_rows_of_one_price_table_get_two_different_locs():
    b = {u"type": u"price_table", u"rows": [
        {u"cells": [u"一千零一夜 EDP", u"30ml", u"52.99 €", u"1.77 €"], u"source_ids": [u"S071"]},
        {u"cells": [u"Mon Guerlain EDP", u"100ml", u"93.76 €", u"0.94 €"], u"source_ids": [u"S073"]}]}
    got = _slots(b)
    assert [x[0] for x in got] == [u"price_table[0]", u"price_table[1]"], \
        u"两张不同行的出处撞成同一个定位：%s" % [x[0] for x in got]
    assert u"52.99" in got[0][1] and u"93.76" in got[1][1], \
        u"定位带了下标却仍拿着同一格的文本（配对会串到别行去）"


def test_a_fact_strip_row_and_a_timeline_item_each_carry_their_own_index():
    strip = {u"type": u"fact_strip", u"facts": [
        {u"value": u"377.7 亿欧元", u"label": u"时装与皮具营收", u"source_ids": [u"S111"]},
        {u"value": u"132.1 亿欧元", u"label": u"该部门经常性利润", u"source_ids": [u"S111"]}]}
    line = {u"type": u"timeline", u"items": [
        {u"title": u"2020-06", u"text": u"劳力士平均成交额 8,897 美元", u"source_ids": [u"S071"]},
        {u"title": u"2022-12", u"text": u"跌到 11,785 美元", u"source_ids": [u"S071"]}]}
    assert [x[0] for x in _slots(strip)] == [u"fact_strip[0]", u"fact_strip[1]"]
    assert [x[0] for x in _slots(line)] == [u"timeline[0]", u"timeline[1]"]


def test_a_block_level_prose_still_locates_at_the_block():
    """prose 没有行下标，定位必须**保持** `prose[-]`：它走 `addids`（块级补挂），
    chip 那条路要行级 loc，给它编一个假下标会让 `w157_hand` 改到不存在的行。"""
    p = {u"type": u"prose", u"text": u"毛利率 74%，同比 −3 个百分点。", u"source_ids": [u"S111"]}
    got = _slots(p)
    assert [x[0] for x in got] == [u"prose[-]"], [x[0] for x in got]
