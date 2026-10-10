# -*- coding: utf-8 -*-
"""W-168 的形态：点名判据只做体检，不做闸门。

10-05 量过（`.probe/w168_measure.py` → `.probe/w168_report.txt`）：全站 793 条
`image_queries` 里 645 条（**81.3%**）不含任何全名，且娇兰/咖啡/劳力士/爱马仕/百达翡丽/
香奈儿/宾利/浪琴 9 篇**一个全名别名都没有**。"每条检索词必须含 aliases 里的全名"
这条判据若上闸，是在惩罚已经上架的页面——而 W-162/W-164 的教训正是"判据没分类就上闸
会把假阳性变成阻塞器"（W-158 那次是 53/240 章被清空）。

所以这里钉三件事：全名的定义、两种成因必须分开说、以及"这条不是闸门"。
"""
import io
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import query_naming as QN  # noqa: E402
import validate as V       # noqa: E402


def test_the_full_name_rule_separates_a_surname_from_an_entity():
    assert QN.is_full_name(u"J.P. Morgan")
    assert QN.is_full_name(u"Morgan Stanley")
    assert QN.is_full_name(u"摩根士丹利")
    assert not QN.is_full_name(u"摩根")          # 两字是姓：Morgan 汽车、STANLEY 工具都姓这个
    assert not QN.is_full_name(u"Morgan")
    assert not QN.is_full_name(u"")


def test_naming_a_query_needs_the_full_name_in_the_query_itself():
    aliases = [u"摩根", u"Morgan Stanley", u"J.P. Morgan"]
    assert QN.names_a_full(u"Morgan Stanley 大楼 内部", aliases)
    assert not QN.names_a_full(u"摩根 大楼 内部", aliases)


def _outline(tmp_path, aliases, queries):
    p = tmp_path / u"大纲.json"
    p.write_text(json.dumps({u"topic": u"测试篇", u"aliases": aliases,
                             u"sections": [{u"id": u"s1", u"image_queries": queries}]},
                            ensure_ascii=False), encoding="utf-8")
    return str(p)


def test_two_causes_are_reported_apart(tmp_path):
    """「检索词没点名」是作者侧的活，「大纲里没有全名可用」是改 aliases 的活。
    混成一条"检索词不合格"，就会去改本该改不动的那一边（娇兰只有 1 个别名）。"""
    authored = QN.audit_outline(_outline(tmp_path, [u"某品牌", u"Some Brand Ltd"], [u"门店 外观"]))
    outline_blocked = QN.audit_outline(_outline(tmp_path, [u"娇兰"], [u"门店 外观"]))
    assert authored[u"unnamed"] == 1 and not authored[u"blocked_by_outline"]
    assert outline_blocked[u"unnamed"] == 1 and outline_blocked[u"blocked_by_outline"]
    assert outline_blocked[u"full_names"] == 0


def test_naming_is_not_a_gate():
    """这条明确不进闸门表：判据会清空已上架页面的配图（G-03 要求每章有图，宁缺毋滥判死）。
    点名这件事由采集期日志与 `python scripts/query_naming.py` 承担。"""
    src = io.open(os.path.join(ROOT, "scripts", "validate.py"), encoding="utf-8").read()
    assert u"query_naming" not in src, u"点名判据被接进了闸门——W-158 那条坑再来一次"
    assert all(g.id != u"G-16" for g in V.GATES)
