# -*- coding: utf-8 -*-
"""M0 地基：治理文档与目录结构存在性。AGENTS.md 是冷启动入口，缺它整个记忆机制失效。"""
import os

REQUIRED_DOCS = [
    "AGENTS.md",
    "rule.md",
    "memo.md",
    "HANDOVER.md",
    "requirement.txt",
]

REQUIRED_DIRS = [
    "config/topics",
    "scripts",
    "tests",
    "web/src/template",
    "web/src/tokens",
    "output",
    "openspec/changes",
]

GATE_IDS = [
    "proposal.md",
    "design.md",
    "tasks.md",
]


def test_required_docs_exist_and_nonempty(root):
    for rel in REQUIRED_DOCS:
        path = os.path.join(root, rel)
        assert os.path.isfile(path), "缺少治理文档：%s" % rel
        assert os.path.getsize(path) > 200, "治理文档疑似空壳：%s" % rel


def test_required_dirs_exist(root):
    for rel in REQUIRED_DIRS:
        assert os.path.isdir(os.path.join(root, rel)), "缺少目录：%s" % rel


def test_contracts_present(root):
    for rel in [
        "config/quality_bar.json",
        "config/topic_outline.schema.json",
        "config/topic_data.schema.json",
        "requirements.txt",
        "pytest.ini",
    ]:
        assert os.path.isfile(os.path.join(root, rel)), "缺少配置：%s" % rel


def test_active_red_lines_are_declared(root):
    """需求 6：默认没有红线，但文件必须显式声明这一状态，防止被误读为"忘了写"。"""
    text = open(os.path.join(root, "rule.md"), encoding="utf-8").read()
    assert "当前生效红线" in text
    assert "候选红线" in text


def test_change_artifacts_exist(root):
    changes = os.path.join(root, "openspec", "changes")
    found = [
        d
        for d in os.listdir(changes)
        if d != "archive" and all(
            os.path.isfile(os.path.join(changes, d, f)) for f in GATE_IDS
        )
    ]
    assert found, "没有任何完整的 openspec change（需 proposal/design/tasks）"
