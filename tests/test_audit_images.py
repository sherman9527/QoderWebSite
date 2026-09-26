# -*- coding: utf-8 -*-
"""配图体检器本身要能被证伪。

它存在的唯一理由是：质量闸门量形式，跑题是语义，闸门结构上看不见——
今天有两篇 `0 fail / 0 warn` 的页面里混着"中国行政区划介绍"和"圆糯米"。
所以这道检查如果自己也漏，就等于没有。
"""
import io
import json
import os

import pytest

import audit_images as A
import outline as O

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _sec(sid, title, images):
    return {"id": sid, "title": title, "blocks": [], "images": images}


def _img(fn, caption, src):
    return {"file": fn, "caption": caption, "alt": caption,
            "source_page": src, "width": 1200, "height": 800}


@pytest.fixture(scope="module")
def cfg():
    return O.load_for_topic(u"咖啡", root=ROOT)


def test_a_self_drawn_illustration_is_listed_separately_not_as_off_topic(cfg):
    """示意图没有来源页，`names_subject(caption + source_page)` 必然落空——
    但那不是"跑题"，是我们自己画的。它必须单列出来给人复核，
    而不是混进 unnamed，让人去"修一张本来没坏的图"。"""
    data = {"sections": [_sec("history", u"咖啡史", [
        {"file": "images/01_剖面.png", "kind": "illustration",
         "alt": u"示意图·非实拍：介质层与内电极交替叠层", "caption": u"按正文绘制",
         "based_on": [u"history#层数"], "width": 1200, "height": 800},
        _img("images/b.jpg", u"也门铁修剪,也门,也门在哪", "https://dashangu.com/2"),
    ])]}
    r = A.audit_data(cfg, data)
    assert r["unnamed"] == ["images/b.jpg"], \
        u"示意图被当成跑题图报了，真脏图反而被淹掉：%s" % (r["unnamed"],)
    assert r["drawn"] == ["images/01_剖面.png"], u"示意图没被单列：%s" % (r,)


def test_audit_catches_the_real_off_topic_images(cfg):
    """样本全是今天从真产物里抓出来的脏图：也门铁是盆栽、行政区划是地理。"""
    data = {"sections": [
        _sec("history", u"咖啡史", [_img("images/a.jpg", u"正确解读咖啡的各种好处 中国咖啡网",
                                    "https://gafei.com/1")]),
        _sec("origins", u"种植带", [_img("images/b.jpg", u"也门铁修剪,也门,也门在哪",
                                    "https://dashangu.com/2")]),
        _sec("brands", u"品牌版图", [_img("images/c.jpg", u"中国行政区划介绍 - 知乎",
                                    "https://zhuanlan.zhihu.com/3")]),
    ]}
    r = A.audit_data(cfg, data)
    assert r["total"] == 3
    assert sorted(r["unnamed"]) == ["images/b.jpg", "images/c.jpg"], \
        u"脏图没被抓出来：%s" % r


def test_audit_flags_a_chapter_without_an_image(cfg):
    """G-03 要求每章有图；体检器必须同样看得见空章，否则两个尺子又分家。"""
    data = {"sections": [
        _sec("history", u"咖啡史", [_img("images/a.jpg", u"咖啡的完全入门指南",
                                    "https://antaicoffee.com/1")]),
        _sec("grinders", u"器具与咖啡机", []),
    ]}
    r = A.audit_data(cfg, data)
    assert r["empty"] == [u"器具与咖啡机"]
    assert r["unnamed"] == []


def test_audit_passes_a_clean_page(cfg):
    data = {"sections": [
        _sec("history", u"咖啡史", [_img("images/a.jpg", u"咖啡的完全入门指南",
                                    "https://antaicoffee.com/1")]),
        _sec("brewing", u"冲煮", [_img("images/b.jpg", u"手冲咖啡从器具到手法",
                                  "https://post.smzdm.com/2")]),
    ]}
    r = A.audit_data(cfg, data)
    assert r["total"] == 2 and not r["unnamed"] and not r["empty"], u"干净页面被误报：%s" % r


def test_audit_triages_off_topic_images_by_query_provenance(cfg):
    """光说"这张跑题"不够，得说清能不能靠重做救回来：
    检索词是**大纲给过的原词**且没点名领域 → 改大纲有救；
    检索词点名了却还是脏图 → 引擎的锅，重做一百次也是脏的；
    没有 query 就只能推理（09-21 判百达翡丽时正是这样）。
    09-22 补第三个分支（W-95）：词不是大纲给过的，而是 collect 降粒度时拆出来的裸词——
    改大纲改不到它头上，得单列，否则会把人支去改一份已经没毛病的大纲。"""
    data = {"sections": [
        _sec("history", u"咖啡史", [
            dict(_img("images/c.jpg", u"某手表促销", "https://shop.example/3"),
                 query=u"咖啡 烘焙 程度"),
        ]),
        _sec("grinders-machines", u"器具与咖啡机", [
            # "磨豆机" 是这份大纲 grinders-machines 的原词，且不含"咖啡"——
            # 这一条才是真的"改 config 有救"（改成 "咖啡 磨豆机"）。
            dict(_img("images/b.jpg", u"也门铁修剪,也门,也门在哪", "https://dashangu.com/2"),
                 query=u"磨豆机"),
        ]),
    ]}
    r = A.audit_data(cfg, data)
    assert [f for f, _ in r["fixable"]] == ["images/b.jpg"], \
        u"大纲给过的不点名检索词应算可救：%s" % r["fixable"]
    assert [f for f, _ in r["dirty"]] == ["images/c.jpg"], \
        u"检索词点名了还跑题的才是引擎脏：%s" % r["dirty"]


def test_an_image_without_provenance_is_not_counted_as_fixable(cfg):
    """没有 query 就说不出"改检索词能救"——把缺失当证据，报告就会指着一个没依据的方向。
    百达翡丽 17 张全部 q=None（那轮跑在 query 字段落地之前），
    体检器却报「检索词可救 12」，我差点据此去改大纲检索词。"""
    data = {"sections": [_sec("history", u"咖啡史", [
        _img("images/b.jpg", u"也门铁修剪,也门,也门在哪", "https://dashangu.com/2"),
    ])]}
    r = A.audit_data(cfg, data)
    assert r["unnamed"] == ["images/b.jpg"]
    assert not r["fixable"], u"没有来路的图被算成「改检索词能救」：%s" % r["fixable"]
    assert [f for f, _ in r["unknown"]] == ["images/b.jpg"], \
        u"没来路的必须单独成一类：%s" % r


def test_report_and_exit_code_agree(tmp_path, monkeypatch, capsys):


    """报告里打 ✗ 的领域，必须就是让退出码非 0 的那批——否则 CI 会绿着放过脏页面。"""
    rows = [
        {"topic": u"咖啡", "subject": [u"咖啡"], "total": 2, "unnamed": [], "empty": []},
        {"topic": u"香奈儿", "subject": [u"香奈儿"], "total": 3,
         "unnamed": ["images/x.jpg"], "empty": []},
    ]
    bad = A.report(rows)
    out = capsys.readouterr().out
    assert bad == [u"香奈儿"]
    assert out.splitlines()[0].startswith(u"✓") and out.splitlines()[1].startswith(u"✗"), out


def test_reuse_is_reported_as_a_fact_and_merges_case_variants(cfg):
    """W-142 的处置：把"同一条检索词挂在几章"做成一行**事实**，不判好坏、不参与 --fix。
    两条词面判据都量过、都不成立（判据①误判 98%，判据②会误伤单产品领域），
    所以这一维不升格成闸门——但当时要是有这一行，我就看不见自己把 `OpenAI` 挂了 5 章。
    `anthropic` 与 `Anthropic` 是同一条词：分开数会把复用度算低，恰好违背这条的存在理由。
    没有 `query` 字段的图（那轮跑在字段落地之前）一律不计——
    不知道来路就说不知道，不猜。"""
    def q(img, query):
        img = dict(img)
        img["query"] = query
        return img

    data = {"sections": [
        _sec("a", u"甲章", [q(_img("images/01.jpg", u"OpenAI 总部", "https://openai.com/news"), u"OpenAI")]),
        _sec("b", u"乙章", [q(_img("images/02.jpg", u"OpenAI 融资", "https://openai.com/blog"), u"OpenAI")]),
        _sec("c", u"丙章", [q(_img("images/03.jpg", u"openai 模型", "https://openai.com/api"), u"openai")]),
        _sec("d", u"丁章", [_img("images/04.jpg", u"别的", "https://example.com/x")]),
    ]}
    r = A.audit_data(cfg, data)
    top = dict(r["reused"])
    assert top, u"有 query 的图该量出复用：%s" % (r["reused"],)
    assert len(top) == 1, u"大小写变体被拆成两条：%s" % (r["reused"],)
    assert list(top.values()) == [3], u"复用章数算错了（无 query 的那张不该计入）：%s" % (r["reused"],)
    assert not r["empty"], u"这条只是事实展示，不该改变合格判定"
