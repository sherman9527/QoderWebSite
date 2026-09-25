# -*- coding: utf-8 -*-
"""健康闸门要按人眼排除表量，否则它报的是假健康。

为什么单独立一个文件：`bing_health.py --topic` 是"现在能不能跑这篇的图"的唯一裁判，
而它数点名候选时**不看 `image_exclude_pages`**。于是给 MLCC 加 7 条排除那一轮，
它照样报"召回健康"，`collect()` 那边可用候选却已经是 0——
`specs` 最后 0 图、被 G-03 拦下不上架。裁判放行了一次空章。

判据要量的是"这篇现在拿得到几张图"，不是"引擎返回了几条"。
人眼已经判死的来源页，不该再算进健康度。
"""
import os
import sys

import bing_health as BH
import images as I

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class _Cand(object):
    def __init__(self, title, purl, murl=""):
        self.title = title
        self.purl = purl
        self.murl = murl


class _Cfg(object):
    topic = u"测试领域"
    aliases = [u"测试领域"]
    image_exclude_pages = []

    class _Sec(object):
        image_queries = [u"测试领域 特写"]

    sections = [_Sec()]


def _stub(monkeypatch, cands, exclude=()):
    cfg = _Cfg()
    cfg.image_exclude_pages = list(exclude)
    monkeypatch.setattr(BH.O, "load_for_topic", lambda *a, **k: cfg)
    monkeypatch.setattr(I, "search", lambda q, count=20, opener=None: list(cands))
    return cfg


def test_a_candidate_from_an_excluded_page_is_reported_separately(monkeypatch):
    """三条都点名领域，其中两条的来源页已被人眼判死。
    引擎健康度按"点名"算（那是引擎的问题），可用数按"点名且未被排除"算（那是人的问题）。
    两者必须分开报：把排除算成引擎坏，会因为人挑得认真而把这篇判成不能跑。"""
    cands = [
        _Cand(u"测试领域 好图一", u"https://news.example/a"),
        _Cand(u"测试领域 广告图二", u"https://shop.example/b"),
        _Cand(u"测试领域 广告图三", u"https://shop.example/c"),
    ]
    _stub(monkeypatch, cands, exclude=[u"https://shop.example/"])
    rows = BH.probe([(u"测试领域", u"测试领域 特写")], root=ROOT)
    topic, q, offered, named, usable = rows[0]
    assert (offered, named, usable) == (3, 3, 1), \
        u"三个数分别是召回/点名/排除后可用，不该混：%s" % (rows[0],)
    st, why = BH.verdict(rows)
    assert st == "healthy", u"引擎明明能用却被排除表拖成不健康：%s" % why


def test_starved_by_exclusions_is_flagged_even_when_the_engine_is_healthy(monkeypatch):
    """MLCC 那次的真实形状：召回健康、点名健康，但可用的全在人眼排除表里，
    于是 `specs` 空章、被 G-03 拦下。裁判放行了一次空章，就是裁判的错——
    但修法是**加一条会喊的话**，不是把引擎判成坏。"""
    cands = [_Cand(u"测试领域 广告图", u"https://shop.example/b")]
    _stub(monkeypatch, cands, exclude=[u"https://shop.example/"])
    rows = BH.probe([(u"测试领域", u"测试领域 特写")], root=ROOT)
    assert BH.verdict(rows)[0] == "healthy", u"引擎这一侧没坏"
    starved = BH.starved_by_exclusions(rows)
    assert starved == [(u"测试领域", u"测试领域 特写")], \
        u"点名>0 而可用=0 的词形没被抓出来：%s" % (starved,)


def test_naming_is_judged_on_the_same_text_the_pipeline_uses(monkeypatch):
    """`reject_reason` 拿 title+purl+murl 判点名，健康探针原来只看 title。
    两边判据不一致时，探针会说"这篇没图可取"而采集器其实取到了图（反之亦然）。"""
    cands = [_Cand(u"某杂志的相册页",
                   u"https://news.example/album/测试领域特写", u"")]
    _stub(monkeypatch, cands)
    rows = BH.probe([(u"测试领域", u"测试领域 特写")], root=ROOT)
    assert rows[0][3] == 1, u"标题没提领域但来源页 URL 提了，管线会认这条，探针也该认"
