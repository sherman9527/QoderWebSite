# -*- coding: utf-8 -*-
"""W-189 来源原文层：`sources[].cache` 指得到 `.research-scratch/text/<sha16>.txt`。

这一层的价值不在"多一份副本"，在于它让三类问题第一次有了可查的答案：
· 这个数到底在不在来源原文里（W-164 的 308 行、W-162 的 383 条从此可判）；
· 删一条引用需要"证明来源不含该断言"，摘要证明不了，原文可以；
· 数字匹配反复被骗（撞号/派生数/量级词），根因是没有原文就只能拿字符串当证据。

四条测试钉的是四处会各自漂移的地方：schema、`SOURCE_KEYS`、清理逻辑、抽取。
"""
import io
import json
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import sourcecache as SC   # noqa: E402
import prune_scratch as PS  # noqa: E402
import generate as G       # noqa: E402

SCHEMA = json.load(io.open(os.path.join(ROOT, "config", "topic_data.schema.json"),
                           encoding="utf-8"))


def _data_with_source(cache=None):
    d = json.load(io.open(os.path.join(ROOT, "tests", "fixtures", "mini_data.json"),
                          encoding="utf-8"))
    s = {u"id": u"S1", u"url": u"https://example.com/a", u"label": u"某来源",
         u"retrieved": u"2026-10-05"}
    if cache is not None:
        s[u"cache"] = cache
    d[u"sources"] = [s]
    return d


def test_an_optional_cache_field_is_allowed_by_the_schema():
    d = _data_with_source(u"text/0123abcd5678ef90.txt")
    errs = G._schema_errors(d)
    assert not errs, u"合法 cache 指针被 schema 拒了：%s" % errs[:2]


def test_a_cache_pointing_at_nothing_is_rejected():
    """指针形状钉死：只认 `text/<16 位十六进制>.txt`。
    自由字符串等于允许"随便写个看起来像的路径"，而这一层的全部意义是可回溯。"""
    for bad in (u"other/x.txt", u"text/XYZ.txt", u"https://example.com/page", u"7" * 16):
        errs = G._schema_errors(_data_with_source(bad))
        assert errs, u"坏指针 %r 被放过" % bad


def test_the_source_key_list_in_code_equals_the_schema():
    """schema、`SOURCE_KEYS`、`w157_hand` 的 newsrc 三处各列一份就是三次漂移，
    G-10 为此判死过整篇。这条测试让加字段必须一次改全。"""
    props = set(SCHEMA[u"properties"][u"sources"][u"items"][u"properties"].keys())
    assert props == set(SC.SOURCE_KEYS), (sorted(props), sorted(SC.SOURCE_KEYS))


def test_newsrc_in_w157_hand_accepts_the_cache_field():
    """工具里的断言与 schema 同一份名单——它原来自己列了一遍，
    所以加了 schema 字段不改这里，`newsrc` 会拒绝一条合法来源。"""
    sys.path.insert(0, os.path.join(ROOT, "audit", "tools"))
    src = io.open(os.path.join(ROOT, "audit", "tools", "w157_hand.py"),
                  encoding="utf-8").read()
    assert u"SOURCE_KEYS" in src, u"w157_hand 还在用自己的字段清单，会漂"


def test_extract_text_keeps_words_and_drops_scripts():
    html = (u"<html><head><style>.x{color:red}</style>"
            u"<script>var tracking = 'beacon';</script></head>"
            u"<body><h1>标题</h1><p>正文里有 28.9% 这个数字。</p></body></html>")
    t = SC.extract_text(html)
    assert u"28.9%" in t and u"标题" in t
    assert u"beacon" not in t and u"color:red" not in t, u"脚本与样式混进了正文：%s" % t[:80]


def test_a_thin_page_stores_no_pointer(tmp_path, monkeypatch):
    """抓到一个 JS 空壳时**不许**写指针：留一个指空文件的 cache 比没有更坏——
    后面每一个按 cache 判的闸门都会以为查过了。"""
    monkeypatch.setattr(SC, "SCRATCH", str(tmp_path))
    monkeypatch.setattr(SC, "INDEX", str(tmp_path / "text" / "index.json"))
    idx = {}
    rel = SC.put(u"https://example.com/empty", u"<html><body><p>短</p></body></html>",
                 topic=u"空壳", index=idx)
    assert rel is None
    assert idx[u"https://example.com/empty"][u"status"] == u"thin"


def test_research_caches_every_source_it_registers(tmp_path, monkeypatch):
    """登记来源的那一步就要落原文——晚一步就再也没有机会（页面会改、会撤、会 404）。
    这条测试用假 opener，所以它同时钉住：抓到了才写指针。"""
    calls = []

    def fake_fetch(url, timeout=25):
        calls.append(url)
        return u"<html><body>" + u"<p>这一段记着一个数 28.9%。</p>" * 40 + u"</body></html>"

    monkeypatch.setattr(SC, "fetch", fake_fetch)
    monkeypatch.setattr(SC, "SCRATCH", str(tmp_path))
    monkeypatch.setattr(SC, "INDEX", str(tmp_path / "text" / "index.json"))
    monkeypatch.delenv("KE_SOURCE_CACHE", raising=False)

    entry = {}
    G._cache_source(u"https://example.com/clinical", entry, u"测试篇")
    assert calls == [u"https://example.com/clinical"]
    assert SC.is_cache_ref(entry.get(u"cache")), entry
    assert u"28.9%" in SC.read(u"https://example.com/clinical")


def test_a_dead_source_registers_without_a_pointer(tmp_path, monkeypatch):
    """抓不到时 `sources[]` 照旧登记，只是没有 cache 键：取证失败不许把研究带崩。"""
    def boom(url, timeout=25):
        raise IOError(u"404")

    monkeypatch.setattr(SC, "fetch", boom)
    monkeypatch.setattr(SC, "SCRATCH", str(tmp_path))
    monkeypatch.setattr(SC, "INDEX", str(tmp_path / "text" / "index.json"))
    monkeypatch.delenv("KE_SOURCE_CACHE", raising=False)
    entry = {}
    G._cache_source(u"https://gone.example.com/x", entry, u"测试篇")
    assert entry == {}, u"抓不到却写了字段：%s" % entry


def test_the_cache_switch_is_honoured(tmp_path, monkeypatch):
    monkeypatch.setenv("KE_SOURCE_CACHE", "0")
    seen = []
    monkeypatch.setattr(SC, "fetch", lambda url, timeout=25: seen.append(url) or u"")
    entry = {}
    G._cache_source(u"https://example.com/a", entry, u"测试篇")
    assert not seen and not entry, u"--no-source-cache 关不掉联网"


def test_a_308_redirect_still_gets_its_text(monkeypatch):
    """urllib 默认跟 301/302/303/307，**不跟 308**。cerebras.ai/pricing 就是这么掉出覆盖率的：
    少跟一次跳转，这条来源就永远没有原文，而"没有原文"在下游等于"无法核对"。"""
    import images as IM
    import urllib.error as UER

    seen = []

    def fake(url, timeout=25):
        seen.append(url)
        if len(seen) == 1:
            err = UER.HTTPError(url, 308, u"Permanent Redirect", {"Location": "/price-new"}, None)
            raise err
        return u"<html><body>" + u"<p>定价页正文。</p>" * 40 + u"</body></html>"

    monkeypatch.setattr(IM, "_urlopen", fake)
    html = SC.fetch(u"https://cerebras.ai/pricing")
    assert u"定价页正文" in html
    assert seen == [u"https://cerebras.ai/pricing", u"https://cerebras.ai/price-new"], seen


def test_the_index_is_rebuildable_from_the_products(tmp_path, monkeypatch):
    """`sources[].cache` 才是权威指针，`index.json` 只是地图。
    并行补覆盖率时多个进程各自整表回写，后写的会盖掉先写的——
    所以必须能从产物重建，否则"地图丢了"会被误报成"原文丢了"。"""
    scratch = tmp_path / "scratch"
    (scratch / "text").mkdir(parents=True)
    rel = SC.cache_rel(u"https://example.com/a")
    (scratch / rel.replace("/", os.sep)).write_text(u"一段正文内容" * 40, encoding="utf-8")
    out = tmp_path / "output" / "T"
    out.mkdir(parents=True)
    json.dump({u"topic": u"T", u"sources": [{u"id": u"S1", u"url": u"https://example.com/a",
                                             u"label": u"x", u"cache": rel}]},
              io.open(str(out / "data.json"), "w", encoding="utf-8"))
    monkeypatch.setattr(SC, "SCRATCH", str(scratch))
    monkeypatch.setattr(SC, "INDEX", str(scratch / "text" / "index.json"))

    assert SC.rebuild(str(tmp_path / "output")) == 1
    rec = SC.load_index()[u"https://example.com/a"]
    assert rec[u"file"] == rel and rec[u"status"] == u"ok" and rec[u"topic"] == u"T"

    # 指针在、文件没了 ⇒ 必须报成 map_only，而不是装作还有原文
    os.remove(str(scratch / rel.replace("/", os.sep)))
    SC.rebuild(str(tmp_path / "output"))
    assert SC.load_index()[u"https://example.com/a"][u"status"] == u"map_only"


def test_rebuild_keeps_the_records_that_have_no_file(tmp_path, monkeypatch):
    """「抓失败」与「抽不出中文」是**没有文件**的记录，而第一版 rebuild 只从有文件的
    指针重建——于是覆盖度报表变成「试过 11、拒绝 无」，把失败说成没发生过。"""
    scratch = tmp_path / "s"
    (scratch / "text").mkdir(parents=True)
    monkeypatch.setattr(SC, "SCRATCH", str(scratch))
    monkeypatch.setattr(SC, "INDEX", str(scratch / "text" / "index.json"))
    SC._save_index({u"https://gone.example.com/x": {u"file": None, u"status": u"fetch_failed"},
                    u"https://ir.example.com/a.pdf": {u"file": None, u"status": u"pdf_no_cjk"}})
    out = tmp_path / "out" / (u"T")
    out.mkdir(parents=True)
    json.dump({u"topic": u"T", u"sources": [{u"id": u"S1", u"url": u"https://x.example.com/b",
                                             u"label": u"x"}]},
              io.open(str(out / "data.json"), "w", encoding="utf-8"))
    SC.rebuild(str(tmp_path / "out"))
    idx = SC.load_index()
    assert idx[u"https://gone.example.com/x"][u"status"] == u"fetch_failed"
    assert idx[u"https://ir.example.com/a.pdf"][u"status"] == u"pdf_no_cjk"


def test_prune_protects_the_source_layer_by_default(tmp_path, monkeypatch):
    """`prune_scratch.py` 管的就是这个目录，而它默认按"7 天没动过"删。
    原文层默认整体免死：清一次就把全站 `sources[].cache` 全变成指空文件的死指针。"""
    scratch, out = _fixture(tmp_path, monkeypatch)
    keep, junk, old = _paths(scratch)
    assert PS.main([u"--keep-days", u"1", u"--apply"]) == 0
    assert keep.is_file() and junk.is_file(), u"text/ 默认就该整体免死"
    assert not old.is_file(), u"别的目录照旧要清，不然这条改动等于给清理逻辑装了个总开关"


def test_prune_with_include_text_still_keeps_referenced_files(tmp_path, monkeypatch):
    """显式 `--include-text` 只放开"没被任何产物引用的"那部分。"""
    scratch, out = _fixture(tmp_path, monkeypatch)
    keep, junk, old = _paths(scratch)
    assert PS.main([u"--keep-days", u"1", u"--apply", u"--include-text"]) == 0
    assert keep.is_file(), u"被 data.json 引用的原文被删掉了——这条指针从此指空文件"
    assert not junk.is_file(), u"放开之后没被引用的旧文本还留着，--include-text 成了空话"


def _fixture(tmp_path, monkeypatch):
    scratch = tmp_path / "scratch"
    tdir = scratch / "text"
    tdir.mkdir(parents=True)
    keep = tdir / ("0" * 16 + u".txt")
    junk = tdir / ("f" * 16 + u".txt")
    other = scratch / "raw"
    other.mkdir()
    old = other / "stale.json"
    for p in (keep, junk, old):
        p.write_text(u"内容", encoding="utf-8")
        os.utime(str(p), (0, 0))
    out = tmp_path / "output" / u"被引用"
    out.mkdir(parents=True)
    json.dump({u"sources": [{u"id": u"S1", u"url": u"https://example.com/a",
                             u"cache": u"text/%s.txt" % (u"0" * 16)}]},
              io.open(str(out / "data.json"), "w", encoding="utf-8"))
    monkeypatch.setattr(PS, "SCRATCH", str(scratch))
    monkeypatch.setattr(PS, "OUTPUT_OVERRIDE", str(tmp_path / "output"))
    return scratch, out


def _paths(scratch):
    tdir = scratch / "text"
    return (tdir / ("0" * 16 + u".txt"), tdir / ("f" * 16 + u".txt"),
            scratch / "raw" / "stale.json")
