# -*- coding: utf-8 -*-
"""W-164 的 chip 动作：非 rows 块型（fact_strip / bar_chart / timeline / steps）
的行级改指针。

为什么单独测：`fixrow` 只走 `block["rows"]`，而 W-164 量出来可机械修的 92 条里
过半长在别的数组上。那种行要么报错，要么**悄悄什么都不改**——改指针静默失败最坏，
账上写着"已修"，线上还是错的。所以这里连"没改成就得响"一起测。
"""
import io
import json
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "audit", "tools"))
import w157_hand as H  # noqa: E402


TOPIC = u"测试篇"


def _write(tmp_path, block):
    dp = tmp_path / "output" / TOPIC / "data.json"
    dp.parent.mkdir(parents=True)
    data = {
        "topic": TOPIC,
        "sources": [
            {u"id": u"S001", u"label": u"官方定价页：缓存读 0.20 美元、输入 4 美元"},
            {u"id": u"S002", u"label": u"发布会实录，通篇没有单价"},
        ],
        "sections": [{u"id": u"price", u"title": u"价格", u"blocks": [block]}],
    }
    io.open(str(dp), "w", encoding="utf-8").write(json.dumps(data, ensure_ascii=False))
    (tmp_path / "audit" / "records").mkdir(parents=True)
    io.open(str(tmp_path / "audit" / "records" / "w157_debt.json"),
            "w", encoding="utf-8").write("[]")
    return dp


def _read(dp):
    return json.load(io.open(str(dp), encoding="utf-8"))


def _run(monkeypatch, tmp_path, decs):
    monkeypatch.setattr(H, "ROOT", str(tmp_path))
    monkeypatch.setattr(H, "DEBT", str(tmp_path / "audit" / "records" / "w157_debt.json"))
    monkeypatch.setattr(H, "LOG", str(tmp_path / "audit" / "records" / "w157_decisions.jsonl"))
    pf = tmp_path / "dec.json"
    io.open(str(pf), "w", encoding="utf-8").write(json.dumps(decs, ensure_ascii=False))
    monkeypatch.setattr(sys, "argv", ["w157_hand.py", str(pf), "--apply"])
    return H.main()


def _fact_strip():
    return {u"type": u"fact_strip", u"source_ids": [u"S002"], u"facts": [
        {u"value": u"$0.20", u"label": u"缓存读每百万 token", u"source_ids": [u"S002"]},
        {u"value": u"$4", u"label": u"输入每百万 token", u"source_ids": [u"S002"]},
    ]}


def test_a_fact_strip_row_can_be_repointed(monkeypatch, tmp_path):
    dp = _write(tmp_path, _fact_strip())
    _run(monkeypatch, tmp_path, [{
        u"topic": TOPIC, u"section": u"price", u"blk": 0, u"action": u"chip",
        u"loc": u"fact_strip[0]", u"starts_with": u"$0.20", u"ids": [u"S001"],
        u"because": u"0.20 只有官方定价页记着，发布页通篇没有单价"}])
    facts = _read(dp)[u"sections"][0][u"blocks"][0][u"facts"]
    assert facts[0][u"source_ids"] == [u"S001"]
    assert facts[1][u"source_ids"] == [u"S002"], u"改一行不许连带改别的行"


def test_a_locator_that_does_not_point_at_that_row_is_refused(monkeypatch, tmp_path):
    dp = _write(tmp_path, _fact_strip())
    with pytest.raises(AssertionError):
        _run(monkeypatch, tmp_path, [{
            u"topic": TOPIC, u"section": u"price", u"blk": 0, u"action": u"chip",
            u"loc": u"fact_strip[1]", u"starts_with": u"$0.20", u"ids": [u"S001"],
            u"because": u"定位写错了：这行不是 $0.20 那行"}])
    facts = _read(dp)[u"sections"][0][u"blocks"][0][u"facts"]
    assert facts[0][u"source_ids"] == [u"S002"], u"被拒之后磁盘上必须还是原样"


def test_an_unknown_source_id_is_refused(monkeypatch, tmp_path):
    _write(tmp_path, _fact_strip())
    with pytest.raises(AssertionError):
        _run(monkeypatch, tmp_path, [{
            u"topic": TOPIC, u"section": u"price", u"blk": 0, u"action": u"chip",
            u"loc": u"fact_strip[0]", u"starts_with": u"$0.20", u"ids": [u"S999"],
            u"because": u"这来源不存在"}])


def test_rerunning_a_chip_logs_it_once(monkeypatch, tmp_path):
    _write(tmp_path, _fact_strip())
    dec = [{u"topic": TOPIC, u"section": u"price", u"blk": 0, u"action": u"chip",
            u"loc": u"fact_strip[0]", u"starts_with": u"$0.20", u"ids": [u"S001"],
            u"because": u"幂等：重跑不许在决策日志里写两遍"}]
    _run(monkeypatch, tmp_path, dec)
    _run(monkeypatch, tmp_path, dec)
    log = io.open(str(tmp_path / "audit" / "records" / "w157_decisions.jsonl"),
                  encoding="utf-8").read().strip().splitlines()
    assert len(log) == 1, u"决策日志 %d 行，重跑把它写脏了" % len(log)

def _prose_block():
    return {u"type": u"prose", u"text": u"名创同时在纽交所与港交所（9896）上市。",
            u"source_ids": [u"S002"]}


def test_a_prose_block_can_gain_a_source_without_losing_the_old(monkeypatch, tmp_path):
    """块级补挂：已有来源还要留着，只是再挂一条真的记着这个数的来源。

    为什么不能复用 attach：attach 断言"这块本来没挂过"，专治空芯片；
    而 W-162 量的正是**挂了但盖不住**的那种，补挂必须保留原引用。
    """
    dp = _write(tmp_path, _prose_block())
    _run(monkeypatch, tmp_path, [{
        u"topic": TOPIC, u"section": u"price", u"blk": 0, u"action": u"addids",
        u"starts_with": u"名创", u"ids": [u"S002", u"S001"],
        u"because": u"9896 这个数在 S001 的 label 里逐字出现，S002 没有"}])
    b = _read(dp)[u"sections"][0][u"blocks"][0]
    assert b[u"source_ids"] == [u"S002", u"S001"], u"应当保留原引用再补新的"


def test_addids_refuses_to_reorder_or_drop_an_existing_source(monkeypatch, tmp_path):
    """补挂只能"加"：把旧来源挤掉，就等于用摘要证明不了的东西删了引用。"""
    _write(tmp_path, _prose_block())
    with pytest.raises(AssertionError):
        _run(monkeypatch, tmp_path, [{
            u"topic": TOPIC, u"section": u"price", u"blk": 0, u"action": u"addids",
            u"starts_with": u"名创", u"ids": [u"S001"],
            u"because": u"这条把 S002 丢了，必须拒"}])


def test_rerunning_addids_is_a_no_op(monkeypatch, tmp_path):
    _write(tmp_path, _prose_block())
    dec = [{u"topic": TOPIC, u"section": u"price", u"blk": 0, u"action": u"addids",
            u"starts_with": u"名创", u"ids": [u"S002", u"S001"],
            u"because": u"幂等：重跑不许写两遍决策日志"}]
    _run(monkeypatch, tmp_path, dec)
    _run(monkeypatch, tmp_path, dec)
    log = io.open(str(tmp_path / "audit" / "records" / "w157_decisions.jsonl"),
                  encoding="utf-8").read().strip().splitlines()
    assert len(log) == 1, u"决策日志 %d 行" % len(log)



def test_renaming_a_source_label_does_not_care_what_the_block_is(monkeypatch, tmp_path):
    """`relabel` 动的是 `sources[]`，与块型无关——原来那行 prose 断言把它挡在表格外。

    10-06 真实经过：名创《两把尺子》一块 keyvalue_table 补挂之后要顺手把 label 写全，
    工具报「blk6 不是 prose」。同一份代码里 `newsrc` 早就免检（它连块都不碰），
    `relabel` 漏了——**同一个理由只应用了一半**。
    """
    dp = _write(tmp_path, _fact_strip())
    _run(monkeypatch, tmp_path, [{
        u"topic": TOPIC, u"section": u"price", u"blk": 0, u"action": u"relabel",
        u"src_id": u"S002", u"new_label": u"发布会实录，通篇没有单价（已逐段核对）",
        u"because": u"label 原来转述错了原页用词"}])
    srcs = _read(dp)[u"sources"]
    assert srcs[1][u"label"].endswith(u"（已逐段核对）"), u"label 没改成"
    assert srcs[0][u"label"] == u"官方定价页：缓存读 0.20 美元、输入 4 美元", u"改标签不许连带改别的来源"


def _card_grid():
    return {u"type": u"card_grid", u"cards": [
        {u"kicker": u"Phantom Dragon", u"title": u"双龙",
         u"body": u"木镶嵌 4 种木材、297 片拼出双龙，星空顶手排 768 根红、576 根白光纤。",
         u"metrics": [
             {u"label": u"木镶嵌", u"value": u"297 片", u"source_ids": [u"S001"]},
             {u"label": u"光纤", u"value": u"1,344 根", u"source_ids": [u"S001"]}]}]}


def test_fixrow_reaches_a_card_grid_metric_and_rewrites_its_value(tmp_path, monkeypatch):
    """`fixrow` 原来只走 `block["rows"]`（cells 或 k/v），**碰不到 card_grid 的 metrics[]**。

    10-09 量到的真实一格：劳斯莱斯 Phantom Dragon 的来源写「768 根红、576 根白」，
    页面把它汇总成「光纤 1,344 根」。这个数不是欠账，是**算式没出现在同一格里**——
    而要把算式写进去，唯一的落点就是这条 metric；`fixrow` 报错说找不到行，
    下一轮就只能手改 data.json（手改一处就漏一处，而漏掉的那处看起来像已修）。
    """
    dp = _write(tmp_path, _card_grid())
    _run(monkeypatch, tmp_path, [{
        u"topic": TOPIC, u"section": u"price", u"blk": 0, u"action": u"fixrow",
        u"row_starts": u"光纤", u"cells": [u"光纤", u"1,344 根（768 红＋576 白）"],
        u"because": u"把来源里已有的两个操作数写进这一格，让它是本行算得出来的派生数"}])
    m = _read(dp)[u"sections"][0][u"blocks"][0][u"cards"][0][u"metrics"][1]
    assert m[u"value"] == u"1,344 根（768 红＋576 白）", m
    assert m[u"source_ids"] == [u"S001"], u"改文案不许顺手动指针"


def _strip_block():
    return {u"type": u"fact_strip", u"source_ids": [u"S001"], u"facts": [
        {u"value": u"195.3", u"label": u"第三方实测中位速度最高",
         u"hint": u"tokens/s，Multiverse", u"source_ids": [u"S001"]},
        {u"value": u"$0.10", u"label": u"输入每百万 token", u"source_ids": [u"S001"]}]}


def test_dropslot_removes_the_addressed_fact_and_keeps_its_sibling(tmp_path, monkeypatch):
    """W-193 剩下的那批数，正解是**删掉那一格**，而工具原来只能改不能删。

    已核实的例子：Artificial Analysis 今天给的是 `#4 Multiverse Computing 190.1 t/s`，
    正文里 `195.3` 对不上任何现在的值，而我们缓存的 S016 是 JS 壳、无从证明当初是什么。
    这种"无法证明也不可信"的主张按 R-02 不该留在页面上。
    """
    dp = _write(tmp_path, _strip_block())
    _run(monkeypatch, tmp_path, [{
        u"topic": TOPIC, u"section": u"price", u"blk": 0, u"action": u"dropslot",
        u"loc": u"fact_strip[0]", u"must_contain": u"195.3",
        u"because": u"官方聚合页现为 190.1，195.3 无出处"}])
    facts = _read(dp)[u"sections"][0][u"blocks"][0][u"facts"]
    assert [f[u"value"] for f in facts] == [u"$0.10"], u"删错格或没删掉：%s" % facts


def test_dropslot_refuses_when_the_index_does_not_point_at_that_content(tmp_path, monkeypatch):
    """删是不可逆的，所以**指到哪**必须用内容再验一遍。

    这条不是仪式感：`w157_hand` 的 chip 就靠 `starts_with` 防过同类事故——
    人抄错下标时，改错一行只是难看，**删错一行是把对的内容删掉**。
    """
    dp = _write(tmp_path, _strip_block())
    import pytest as _pt
    with _pt.raises(AssertionError):
        _run(monkeypatch, tmp_path, [{
            u"topic": TOPIC, u"section": u"price", u"blk": 0, u"action": u"dropslot",
            u"loc": u"fact_strip[1]", u"must_contain": u"195.3",
            u"because": u"下标写错了：195.3 在第 0 格"}])
    facts = _read(dp)[u"sections"][0][u"blocks"][0][u"facts"]
    assert len(facts) == 2, u"报错之前就已经删了"


def test_dropslot_refuses_to_empty_a_block(tmp_path, monkeypatch):
    """整块只剩一格时不许删：删空之后页面会留一个空章节，闸门 G 系列未必看得见。"""
    blk = _strip_block()
    blk[u"facts"] = [blk[u"facts"][0]]
    dp = _write(tmp_path, blk)
    import pytest as _pt
    with _pt.raises(AssertionError):
        _run(monkeypatch, tmp_path, [{
            u"topic": TOPIC, u"section": u"price", u"blk": 0, u"action": u"dropslot",
            u"loc": u"fact_strip[0]", u"must_contain": u"195.3",
            u"because": u"这是最后一格"}])
