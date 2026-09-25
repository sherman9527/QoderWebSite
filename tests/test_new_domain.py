# -*- coding: utf-8 -*-
"""W-28：新增一个领域到底要不要改代码。

设计承诺（AGENTS.md 第 5 节）：新增领域 = 加一个 `config/topics/<领域>.json`。
这条测试就是钉住这个承诺——它造一个全新的、种子清单里没有的领域，
只写 JSON，不改任何 .py/.ts/.tsx，然后要求大纲层与模板层都认它。
"""
import copy
import io
import json
import os
import re
import subprocess

import outline
import validate as V
from test_gates import by_id

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIX = os.path.join(ROOT, "tests", "fixtures", "mini_data.json")


def _new_topic_cfg(base_dir):
    """照抄咖啡大纲，改名与章节 id——这正是 AGENTS.md 让人做的"抄一个改改"。"""
    src = json.load(io.open(os.path.join(ROOT, "config", "topics", u"咖啡.json"),
                            encoding="utf-8"))
    cfg = copy.deepcopy(src)
    cfg["topic"] = u"抹茶"
    cfg["category"] = u"饮食风物"
    cfg["tags"] = [u"抹茶", u"茶道", u"粉体"]
    for i, s in enumerate(cfg["sections"]):
        s["id"] = "sec-%02d" % i
    d = os.path.join(base_dir, "config", "topics")
    os.makedirs(d, exist_ok=True)
    io.open(os.path.join(d, u"抹茶.json"), "w", encoding="utf-8").write(
        json.dumps(cfg, ensure_ascii=False))
    return cfg


def test_a_new_domain_needs_only_a_json(tmp_path):
    _new_topic_cfg(str(tmp_path))
    cfg = outline.load_for_topic(u"抹茶", root=str(tmp_path))
    assert cfg.topic == u"抹茶"
    assert cfg.category == u"饮食风物" and cfg.tags[:1] == [u"抹茶"]
    assert len(cfg.sections) >= 5
    assert u"抹茶.json" in os.listdir(os.path.join(str(tmp_path), "config", "topics"))


def test_new_domain_data_renders_and_clears_gates(tmp_path):
    """大纲认了还不够：模板必须能在没有新代码的情况下把它排好版。"""
    _new_topic_cfg(str(tmp_path))
    data = json.load(io.open(FIX, encoding="utf-8"))
    data["topic"] = u"抹茶"
    data["category"] = u"饮食风物"
    data["tags"] = [u"抹茶", u"茶道"]
    d = tmp_path / u"抹茶"
    (d / "images").mkdir(parents=True)
    for s in data["sections"]:
        for im in s.get("images") or []:
            im.setdefault("width", 1600)
            im.setdefault("height", 900)
            (d / im["file"]).write_bytes(b"\xff\xd8\xff\xe0" + bytes(60000))
    dp = d / "data.json"
    dp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    page = d / (u"抹茶_2026-09-19.html")
    r = subprocess.run(["node", os.path.join("scripts", "render.mjs"),
                        "--data", str(dp), "--out", str(page)],
                       cwd=ROOT, capture_output=True, timeout=300)
    assert r.returncode == 0, r.stderr.decode("utf-8", "ignore")[-400:]
    html = page.read_text(encoding="utf-8")
    assert u"抹茶" in html
    assert not re.search(r'<(script|link)\b[^>]*\b(?:src|href)=["\']https?://', html, re.I)
    g13 = [f for f in (by_id("G-13").check(
        V.Ctx(u"抹茶", str(d), str(page), html, data, V._bar())) or [])
        if f.level == "fail"]
    assert not g13, u"新领域页面几何不合格：%s" % [str(f)[:90] for f in g13]
