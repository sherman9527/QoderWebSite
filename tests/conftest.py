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

# 同一件事的第二处，10-16 被自己绊出来的：G-13 的死因捕获默认落在 `.probe/g13-deaths.jsonl`，
# 而验"工具死了必须判 fail"的那几条单测**每次跑都会往那个文件里写几行假死亡**。
# 第一次 `validate --all` 报 0 fail、那个文件却有 12 行——对不上的那一刻才发现：
# 仪表记的不是它在名字上说的那件事。所以测试一律把捕获改道到临时目录
# （`setdefault`：单测自己 monkeypatch 过的仍然生效）。
os.environ.setdefault(
    "KE_G13_DEATH_LOG", os.path.join(tempfile.gettempdir(), "ke-test-g13-deaths.jsonl"))

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


_FP_CACHE = {}


def current_fp_json():
    """模板指纹向 conftest 要，不在这里手抄一份。

    原先这里写死了一份区块清单，而它**已经和模板差了一个 bar_chart**——
    于是 passing_ctx 一直红着 G-08，所有"夹具应该全绿"的隐含假设都是假的。
    这正是 W-163 说的形状：抄一份判据，抄的那一份迟早会旧。
    """
    if "fp" not in _FP_CACHE:
        import validate as V
        _FP_CACHE["fp"] = json.dumps(V.current_fingerprint(), ensure_ascii=False)
    return _FP_CACHE["fp"]


def make_passing_html(data, fingerprint=None):
    """从 data 里把图片抄成 <img>，造一份"看起来由模板渲染"的 HTML。"""
    fp = fingerprint or current_fp_json()
    imgs = []
    for s in data["sections"]:
        for im in s.get("images", []):
            imgs.append('<img src="%s" alt="%s" loading="lazy">' % (im["file"], im["alt"]))
    # `img{max-width:100%}` 不是装饰：真实模板把图包在 `.figs .ratio` 里，
    # 宽度由容器定。夹具以前写的是裸 `<img>`，而图又是解不开的字节，
    # 于是"图会不会把页面顶出横向滚动条"这条检查从来没在夹具上跑过。
    # 09-26 让 G-13 真的去量图之后，它立刻以 `clipped-scroller` 红了——
    # 红的是夹具缺那条约束，不是产物有问题。
    return ("<!DOCTYPE html>\n<html lang=\"zh-CN\"><head><meta charset=\"UTF-8\">"
            "<!--template-fingerprint:%s-->\n"
            "<style>:root{--bg:#fff}img{max-width:100%%;height:auto;display:block}</style>\n</head>"
            "<body><section>%s</section></body></html>" % (fp, "".join(imgs)))


def write_image(path, w=1500, h=950):
    """写一张**浏览器真能解码**的图。

    以前各处夹具直接 `write_bytes(b"\\xff\\xd8\\xff\\xe0" + bytes(50000))`——
    那是一串 NUL，不是 JPEG。G-13 里所有量图的检查都写着
    `if (!im.complete || !im.naturalWidth) continue`，于是这些检查
    **在整个测试套件的历史上从来没有跑过一次**。
    09-26 把「图没加载成」从静默跳过改成报失败，五道测试立刻红——
    红的是夹具，不是产物。尺寸取真实产物那一档（1500×950），
    免得夹具比产物更宽容，检查又变成空转。
    """
    from PIL import Image
    img = Image.new("RGB", (w, h), (196, 188, 176))
    p = str(path)
    img.save(p, "JPEG" if p.lower().endswith((".jpg", ".jpeg")) else "PNG")
    return p


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
            write_image(out_dir / im["file"])
    page = out_dir / ("%s.html" % topic)
    page.write_text(make_passing_html(data), encoding="utf-8")
    # 夹具模拟的是"刚渲染完的页面"，所以模板源哈希侧车也得有（W-163）。
    # 少写这一行，passing_ctx 会在 G-08 上永远红着。
    import validate as _V
    (out_dir / (page.name + ".srchash")).write_text(_V.current_sources_hash() + chr(10), encoding="utf-8")
    # 注入只带 words_range 的假大纲，避免测试依赖 config/topics/ 下的真实领域
    stub = SimpleNamespace(
        words_range=(quality_bar["words"]["min_chars"], quality_bar["words"]["max_chars"]),
        sections=[SimpleNamespace(id=s["id"], title=s["title"]) for s in data["sections"]],
    )
    page_text = page.read_text(encoding="utf-8")
    return V.Ctx(topic, str(out_dir), str(page), page_text, data, quality_bar, outline=stub)
