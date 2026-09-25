# -*- coding: utf-8 -*-
"""领域大纲解析（specs/topic-outline-config）。"""
import json
import os

import pytest

import outline as outline_mod


def test_load_valid_outline(root, valid_outline, tmp_path):
    p = tmp_path / "测试领域.json"
    p.write_text(json.dumps(valid_outline, ensure_ascii=False), encoding="utf-8")
    cfg = outline_mod.load(str(p))
    assert cfg.topic == "测试领域"
    assert len(cfg.sections) == 6
    assert cfg.words_range == (4500, 6500)


def test_words_range_follows_target_minutes(root, valid_outline, tmp_path):
    """10 分钟 → 4500–6500；改成 20 分钟必须等比放大，而不是写死。"""
    valid_outline["reading_target_minutes"] = 20
    p = tmp_path / "长文.json"
    p.write_text(json.dumps(valid_outline, ensure_ascii=False), encoding="utf-8")
    cfg = outline_mod.load(str(p))
    lo, hi = cfg.words_range
    assert lo > 4500 and hi > 6500


def test_missing_section_id_fails_with_location(root, valid_outline, tmp_path):
    del valid_outline["sections"][2]["id"]
    p = tmp_path / "缺字段.json"
    p.write_text(json.dumps(valid_outline, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(outline_mod.OutlineError) as ei:
        outline_mod.load(str(p))
    msg = str(ei.value)
    assert "缺字段.json" in msg
    assert "id" in msg
    assert "2" in msg  # 定位到具体第几节


def test_duplicate_section_id_fails(root, valid_outline, tmp_path):
    valid_outline["sections"][3]["id"] = valid_outline["sections"][1]["id"]
    p = tmp_path / "重复.json"
    p.write_text(json.dumps(valid_outline, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(outline_mod.OutlineError) as ei:
        outline_mod.load(str(p))
    assert "重复" in str(ei.value)


def test_unknown_block_type_fails(root, valid_outline, tmp_path):
    valid_outline["sections"][0]["block_types"] = ["prose", "hover_table"]
    p = tmp_path / "坏区块.json"
    p.write_text(json.dumps(valid_outline, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(outline_mod.OutlineError) as ei:
        outline_mod.load(str(p))
    assert "hover_table" in str(ei.value)


def test_topic_for_dir_name(root, valid_outline, tmp_path):
    p = tmp_path / "咖啡.json"
    p.write_text(json.dumps(valid_outline, ensure_ascii=False), encoding="utf-8")
    cfg = outline_mod.load(str(p))
    assert cfg.outline_dir_name == os.path.join("output", "测试领域")


def test_missing_topic_reports_actionable_hint(root, tmp_path, capsys):
    """specs/knowledge-page-generation：未配置领域必须给下一步动作，不能静默产空页。"""
    with pytest.raises(outline_mod.OutlineNotFound) as ei:
        outline_mod.load_for_topic("根本没这个领域", root=str(root))
    hint = str(ei.value)
    assert "config/topics" in hint
    assert "根本没这个领域" in hint


def test_seeds_ship_outlines(root):
    """需求 6：首批 10 个领域大纲必须存在，否则"批量生成"无从谈起。"""
    seeds = [
        "咖啡", "香奈儿", "爱马仕", "百达翡丽", "积家",
        "劳力士", "LV", "浪琴", "宾利", "劳斯莱斯",
    ]
    missing = [s for s in seeds if not os.path.isfile(os.path.join(root, "config", "topics", s + ".json"))]
    assert not missing, "缺少领域大纲：%s" % "、".join(missing)
