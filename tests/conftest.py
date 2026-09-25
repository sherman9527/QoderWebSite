# -*- coding: utf-8 -*-
"""共享 fixture：路径常量、质量线配置、最小合法大纲/数据样本。"""
import copy
import json
import os
import sys
import tempfile
from types import SimpleNamespace

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(ROOT, "scripts")
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)

# 测试里故意失败的调用也会 dump 被拒原文；别让它落进项目的 .research-scratch/。
os.environ.setdefault(
    "KE_REJECT_DIR", os.path.join(tempfile.gettempdir(), "ke-test-rejects"))

CONFIG_DIR = os.path.join(ROOT, "config")
OUTPUT_DIR = os.path.join(ROOT, "output")
WEB_DIR = os.path.join(ROOT, "web")
FIXTURES = os.path.join(ROOT, "tests", "fixtures")


def load_json(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


@pytest.fixture(scope="session")
def root():
    return ROOT


@pytest.fixture(scope="session")
def quality_bar():
    return load_json(os.path.join(CONFIG_DIR, "quality_bar.json"))


@pytest.fixture(scope="session")
def outline_schema():
    return load_json(os.path.join(CONFIG_DIR, "topic_outline.schema.json"))


@pytest.fixture(scope="session")
def data_schema():
    return load_json(os.path.join(CONFIG_DIR, "topic_data.schema.json"))


def _section(idx, **over):
    sec = {
        "id": "sec-%d" % idx,
        "title": "章节 %d" % idx,
        "anchor": "史",
        "angle": "第 %d 章的讲述角度，说明这章取舍什么" % idx,
        "block_types": ["prose"],
        "image_queries": ["测试 配图 %d" % idx],
        "fact_prompts": ["第 %d 章要查证的具体事实是什么" % idx],
    }
    sec.update(over)
    return sec


@pytest.fixture
def valid_outline():
    """6 节最小合法大纲（schema 要求 minItems=5）。"""
    return {
        "topic": u"测试领域",
        "category": u"测试类别",
        "tags": [u"测试", u"夹具", u"契约"],
        "subtitle": u"用于测试的最小大纲",
        "reader": "测试读者",
        "theme": {"token": "test-theme", "hero_motif": "test_motif"},
        "reading_target_minutes": 10,
        "sections": [_section(i) for i in range(1, 7)],
    }


@pytest.fixture
def valid_data():
    """与 valid_outline 对应的最小合法内容数据。"""
    def blk(idx):
        return [
            {"type": "prose", "text": "正" * 100 + "，第 %d 章的测试正文内容。" % idx},
            {
                "type": "fact_strip",
                "facts": [{"value": "1725", "label": "起始年份", "source_ids": ["S1"]}],
            },
        ]

    return {
        "topic": "测试领域",
        "generated_date": "2026-09-19",
        "theme": {"token": "test-theme"},
        "research_mode": "online",
        "data_as_of": "2026-09",
        "lede": "这是一段用于测试的页面导语。",
        "sections": [
            {
                "id": "sec-%d" % i,
                "title": "章节 %d" % i,
                "anchor": "史",
                "images": [
                    {
                        "file": "images/%02d_test.jpg" % i,
                        "alt": "第 %d 章测试配图" % i,
                        "caption": "图源：测试",
                        "source_page": "https://example.com/p%d" % i,
                    }
                ],
                "blocks": blk(i),
            }
            for i in range(1, 7)
        ],
        "sources": [
            {"id": "S1", "url": "https://example.com/1", "label": "测试来源一"}
        ],
    }


@pytest.fixture
def deep_copy(request):
    """给需要改字典的测试用：返回 fixture 值的深拷贝。"""
    return copy.deepcopy(request.getfixturevalue(request.param))


# ------------------------------------------------------------------ 闸门测试构造器
#
# 闸门同时看 data.json 与产物 HTML。这里造一份"应该全绿"的最小输入，
# 各测试再针对性地破坏某一项，确认对应闸门真的会红——只测正例等于没测。

import copy as _copy


def make_passing_data(topic=u"测试领域", sections=9, pad=560):
    """9 节 × 约 570 汉字，总量落在 4500–6500 目标带中段。"""
    src_ids = ["S%d" % i for i in range(1, 6)]
    body = (u"这段正文用于把篇幅填充到目标区间之内，同时尽量保持语义连贯，"
            u"而不是为了凑字数把同一句话反复抄写。") * 40
    secs = []
    for i in range(1, sections + 1):
        sid = src_ids[i % len(src_ids)]
        secs.append({
            "id": "sec-%02d" % i,
            "title": u"第 %d 章：测试章节标题" % i,
            "anchor": u"章",
            "intro": u"这一章验证闸门在合法输入上不应报错。",
            "images": [{
                "file": "images/%02d_test.jpg" % i,
                "alt": u"第 %d 章测试配图" % i,
                "caption": u"测试配图",
                "source_page": "https://example.com/page%d" % i,
            }],
            "blocks": [
                {"type": "prose", "heading": u"小节 %d" % i,
                 "text": body[:pad] + u"（第 %d 章）" % i},
                {"type": "price_table", "as_of": "2026-09",
                 "columns": [u"项目", u"数值"],
                 "rows": [{"cells": [u"入门", u"3.2 万元"], "source_ids": [sid]}]},
                {"type": "fact_strip", "facts": [
                    {"value": "1832", "label": u"起始年份", "source_ids": [sid]}]},
                {"type": "timeline", "items": [
                    {"year": "1931", "text": u"起点事件发生于这一年。", "source_ids": [sid]},
                    {"year": "1983", "text": u"转折事件发生于这一年。", "source_ids": [sid]}]},
                {"type": "note", "tone": "tip", "text": u"这是一条长度达标的实操建议文本。"},
            ],
        })
    return {
        "topic": topic,
        "category": u"测试类别",
        "tags": [u"测试", u"闸门", u"夹具"],
        "subtitle": u"闸门测试用页面",
        "lede": u"页面导语。",
        "generated_date": "2026-09-19",
        "theme": {"token": "coffee-roast"},
        "data_as_of": "2026-09",
        "research_mode": "online",
        "sections": secs,
        "sources": [{"id": s, "url": "https://example.com/%s" % s, "label": u"来源 " + s}
                    for s in src_ids],
    }


def make_passing_html(data, fingerprint=None):
    """从 data 里把图片抄成 <img>，造一份"看起来由模板渲染"的 HTML。"""
    fp = fingerprint or json.dumps({"blocks": [
        "prose", "keyvalue_table", "timeline", "price_table", "card_grid",
        "steps", "quote", "fact_strip", "compare", "note"], "rev": "ke-template-1"})
    imgs = []
    for s in data["sections"]:
        for im in s.get("images", []):
            imgs.append('<img src="%s" alt="%s" loading="lazy">' % (im["file"], im["alt"]))
    return ("<!DOCTYPE html>\n<html lang=\"zh-CN\"><head><meta charset=\"UTF-8\">"
            "<!--template-fingerprint:%s-->\n<style>:root{--bg:#fff}</style>\n</head>"
            "<body><section>%s</section></body></html>" % (fp, "".join(imgs)))


@pytest.fixture
def passing_ctx(tmp_path, quality_bar):
    """造一个应该通过全部闸门的 Ctx，并落好盘的图片文件。"""
    import validate as V

    data = make_passing_data()
    topic = data["topic"]
    out_dir = tmp_path / "output" / topic
    (out_dir / "images").mkdir(parents=True)
    for s in data["sections"]:
        for im in s["images"]:
            (out_dir / im["file"]).write_bytes(b"\xff\xd8\xff\xe0" + b"0" * 50000)
    page = out_dir / ("%s.html" % topic)
    page.write_text(make_passing_html(data), encoding="utf-8")
    # 注入只带 words_range 的假大纲，避免测试依赖 config/topics/ 下的真实领域
    stub = SimpleNamespace(
        words_range=(quality_bar["words"]["min_chars"], quality_bar["words"]["max_chars"]),
        sections=[SimpleNamespace(id=s["id"], title=s["title"]) for s in data["sections"]],
    )
    page_text = page.read_text(encoding="utf-8")
    return V.Ctx(topic, str(out_dir), str(page), page_text, data, quality_bar, outline=stub)
