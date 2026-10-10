# -*- coding: utf-8 -*-
"""W-193 的分诊判据：**「查不到」有两种，动作相反，混了就等于删掉有出处的正文。**

10-06 把换算那个洞补完之后重扫，第一次出现一批"在有原文的来源里都查不到"的行。
对着它们做删除是最自然的动作，也是最危险的：其中一些行挂着的来源是
`pdf_no_cjk`（中文子集字体抽不出汉字）或抓失败——**查不到只说明我们的抽取不行**，
不说明这句话没出处。这类只能取证（`scripts/pdfpage.py` 定位页 + 人眼读页面图）。

所以分类规则单独可测，并且把"状态未知"也归到不许删那一档。
"""
import os
import io
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "audit", "tools"))
import w193_triage as W  # noqa: E402


def test_no_missing_number_means_no_action():
    assert W.classify([], [u"S01"], {u"S01": u"readable"}) == u""


def test_a_row_that_never_cited_anything_is_C():
    assert W.classify([u"0.61"], [], {}) == u"C"


def test_all_cited_sources_readable_but_lack_the_number_is_A():
    """"补源或删数"只有这一档才准动手删。"""
    assert W.classify([u"0.61"], [u"S01"], {u"S01": u"readable"}) == u"A"


def test_one_unreadable_cited_source_moves_the_row_out_of_the_deletion_bucket():
    for st in (u"unreadable:pdf_no_cjk", u"unreadable:fetch_failed", u"unreadable:not_html",
               u"unreadable:thin"):
        got = W.classify([u"0.61"], [u"S01", u"S02"], {u"S01": u"readable", u"S02": st})
        assert got == u"B", u"%s 的来源读不到，却被归进可以删的那一档" % st
    assert W.classify([u"0.61"], [u"S09"], {u"S09": u"unreadable:fetch_failed"}) == u"B"


def test_unknown_source_state_fails_safe_to_B():
    """索引里查不到状态（并行盖地图、或那条来源从没进过索引）时，
    **不许**默认"读得到"——那会把没证据当成有证据的反面：把该留的正文删掉。"""
    assert W.classify([u"0.61"], [u"S09"], {}) == u"B"
    assert W.classify([u"0.61"], [u"S09"], {u"S09": None}) == u"B"


def test_a_currency_claim_whose_sources_have_no_currency_token_is_not_deletable():
    """W-196②：A/B 原来只问「正文抓到了吗」，没问「抓到的那部分含不含这一类的量」。
    ARC Prize 结果页 S044 实测 12,303 字、1,326 个数字块（多半是题号与 ✓/✗ 矩阵的十六进制串），
    但 `$`/`USD`/`dollar`/`元`/`€` 出现 **0 次**——那一页的每题成本是 JS 渲染的，壳抓到、表没抓到。
    这种**抽取失败**如果留在 A，下一轮就会按 R-02 把正确的成本数字删掉。
    方向只允许一个：这条只会把 A 降级成 B（不许删、先取证），永远不会反过来。
    """
    st = {u"S044": u"readable", u"S043": u"readable"}
    assert W.classify([u"0.120", u"0.641"], [u"S044"], st, fam_missing=True) == u"B"
    # 另一条来源里有货币字样 ⇒ 这一族看得见，仍然算 A（该动就得动）
    assert W.classify([u"0.120", u"0.641"], [u"S044", u"S043"], st, fam_missing=False) == u"A"


def test_the_family_gate_only_fire_when_the_row_actually_asserts_a_family():
    """`κ 0.61` 这种不声明任何量族的数，不许因为「来源里没有货币字样」就被降级——
    那等于给每条裸数都找一个不存在的族。"""
    assert W.claim_families([u"0.61"], u"κ 按 Landis & Koch 分档 0.61–0.80 才算实质一致") == set()
    assert W.classify([u"0.61"], [u"S01"], {u"S01": u"readable"}) == u"A"


def test_claim_families_reads_money_and_percent_from_the_number_itself():
    assert W.claim_families([u"0.120"], u"每题 0.120 美元") == set([u"货币"])
    assert W.claim_families([u"88.5%"], u"ARC-AGI-1 得分 88.5%") == set([u"百分比"])
    assert W.claim_families([u"377.7"], u"377.7 亿欧元 时装与皮具营收") == set([u"货币"])


def test_the_ledger_keeps_enough_row_text_for_the_derived_check():
    """账上留的 `行文本` 被截到 160/170 字，而**派生判据看的正是这一格**：
    Muse《单位经济》那段散文里 `6240 = 0.52 × 12000`、`8724 = 0.727 × 12000`，
    两个操作数都在同一块里，但一个在第 200 字、一个在第 330 字——
    截断之后 `split_derived()` 看不见操作数，就把**页面上自己算出来的数**报成「要补源或删数」。
    这类不是欠账，是台账把证据剪掉了。
    """
    import os
    p = os.path.join(W.ROOT, u"audit", u"records", u"w162_rows.tsv")
    if not os.path.isfile(p):
        pytest.skip(u"w162 明细表还没跑出来")
    rows = [l.rstrip(u"\n").split(u"\t") for l in io.open(p, encoding="utf-8")]
    head, rows = rows[0], rows[1:]
    i_text, i_miss, i_topic, i_sec = (head.index(k) for k in (u"行文本", u"缺的数", u"篇", u"章"))
    hit = [r for r in rows if len(r) == len(head) and r[i_topic] == u"Muse"
           and r[i_sec] == u"unit-economics" and u"6240" in r[i_miss]]
    assert hit, u"没找到那条 Muse 行——这条测试要跟着明细表改，别当通过"
    text = hit[0][i_text]
    dev, plain = W.split_derived([t for t in hit[0][i_miss].split(u"、") if t], text)
    assert u"6240" in dev, u"0.52×12000 就在同一格里却没被判成派生——行文本又被剪短了：%s" % text[-60:]
