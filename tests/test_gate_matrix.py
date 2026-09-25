# -*- coding: utf-8 -*-
"""闸门 ↔ 测试 ↔ spec 的三方对账。

防的是这种漂移：文档里写了十条闸门，代码里只有八条，测试里覆盖了六条，
剩下两条只在"看起来有"的状态下活着——真出问题时才发现没人实现。
"""
import io
import json
import os
import re

import pytest

import validate as V

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TESTS = os.path.join(ROOT, "tests")
CHANGE = os.path.join(ROOT, "openspec", "changes", "build-knowledge-html-generator")


def _gate_test_names():
    src = io.open(os.path.join(TESTS, "test_gates.py"), encoding="utf-8").read()
    named = set(re.findall(r"def test_(G\d\d)_", src))
    # 参数化基线 test_valid_input_passes_all_gates 覆盖全部闸门，但只有针对性反例
    # 才算"这条闸门真的会被触发"，所以要求显式命名的反例测试。
    return named


def test_every_gate_has_a_dedicated_negative_test():
    named = _gate_test_names()
    missing = [g.id for g in V.DOMAIN_GATES if g.id.replace("-", "") not in named]
    assert not missing, "这些闸门没有针对性反例测试：%s" % missing


def test_every_gate_has_spec_ref_that_exists():
    for g in V.DOMAIN_GATES:
        p = os.path.join(CHANGE, g.spec_ref)
        assert os.path.isfile(p), "%s 指向不存在的 spec：%s" % (g.id, g.spec_ref)


def test_gate_titles_are_documented_in_docstrings():
    for g in V.DOMAIN_GATES:
        assert g.title and len(g.title) > 3, "%s 缺中文说明" % g.id


def test_specs_have_scenarios_and_gates_cover_each_capability():
    base = os.path.join(CHANGE, "specs")
    caps = [d for d in os.listdir(base) if os.path.isdir(os.path.join(base, d))]
    total_scenarios = 0
    for cap in caps:
        text = io.open(os.path.join(base, cap, "spec.md"), encoding="utf-8").read()
        n = len(re.findall(r"^#### Scenario:", text, re.M))
        reqs = len(re.findall(r"^### Requirement:", text, re.M))
        assert n >= reqs, "%s 有 %d 条需求但只有 %d 个场景" % (cap, reqs, n)
        total_scenarios += n
    assert total_scenarios >= 30, "场景太少，不足以支撑 10 条闸门"


def test_validate_cli_lists_every_gate():
    out = io.StringIO()
    import contextlib
    import sys
    with contextlib.redirect_stdout(out):
        rc = V.main(["--list"])
    assert rc == 0
    listed = out.getvalue()
    for g in V.DOMAIN_GATES:
        assert g.id in listed, "%s 没出现在 --list 里" % g.id
    assert "G-11" in listed


def test_unknown_gate_is_rejected_not_ignored():
    assert V.main(["--gate", "G-99"]) == 2


def test_quality_bar_is_valid_json_with_all_sections():
    bar = json.load(io.open(os.path.join(ROOT, "config", "quality_bar.json"), encoding="utf-8"))
    for k in ("reading", "words", "structure", "images", "theme", "sourcing", "placeholders"):
        assert k in bar, "quality_bar 缺 %s" % k
    assert bar["words"]["min_chars"] < bar["words"]["max_chars"]


def test_red_lines_default_empty():
    """需求 6 的"默认没有红线"指的是：未经确认的候选不算规则。
    2026-09-19 开发者把裁决权交给 Agent（"3、4 你自己决定我只看效果"），
    生效红线不再为空——这里断言的是"确实解析到了"，而不是"文件没读出来"。"""
    ids = [rid for rid, _ in V.active_red_lines()]
    assert ids, "一条生效红线都没解析出来：rule.md 格式与 active_red_lines() 脱节"
    assert ids == sorted(set(ids)), "生效红线编号重复或乱序：%s" % ids


def test_candidate_red_lines_are_not_executed():
    """候选红线不得当规则用——只有"一、当前生效红线"里的条目才算。"""
    text = io.open(os.path.join(ROOT, "rule.md"), encoding="utf-8").read()
    cand = re.search(r"##\s*四、候选红线(.*?)(?=\n##\s|\Z)", text, re.S)
    assert cand and "候选-A" in cand.group(1)
    assert all(rid.startswith("R-") for rid, _ in V.active_red_lines()), \
        "候选条目被误当成生效红线"
