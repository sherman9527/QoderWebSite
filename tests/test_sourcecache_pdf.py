# -*- coding: utf-8 -*-
"""W-191 来源原文层的 PDF 支路。

为什么这条要单独有判据：10-05 建层时 PDF 一律不抓（按 utf-8 解码字节只会存一份乱码），
代价当场显形——名创 `align-the-rulers` 整章 6 行数只指着两份财报 PDF，
"查不到"因此不等于"没出处"。

三件实测过的事（`audit/records/w191_pdf_more_pdfs.txt`、`audit/records/w191_pdf_extract_cmp.txt`，都是真文件）：
· **抽取质量取决于文件**：泡泡玛特 2025 年报 pdftotext 出 1,294,986 字符 / CJK 125,270；
  名创 2026 IRA 中文本出来 0 个汉字（子集字体没有 ToUnicode），pypdf 同样是 0。
· **pdftotext 比 pypdf 更能救 CJK**：同一份 hkexnews 中文公告，6,661 vs 312。
  所以主路径是 poppler，pypdf 只在没有 poppler 的机器上兜底。
· **一份"看起来有原文"的乱码正文比没有更坏**：下游每个按原文判的闸门都会以为查过了。
  所以这里宁可拒绝入库，也要把拒绝的原因记进索引。
"""
import io
import json
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import sourcecache as SC  # noqa: E402

PDF_HEAD = b"%PDF-1.7\n%\xe2\xe3\xcf\xd3\n"


@pytest.fixture
def scratch(tmp_path, monkeypatch):
    monkeypatch.setattr(SC, "SCRATCH", str(tmp_path))
    monkeypatch.setattr(SC, "INDEX", str(tmp_path / "text" / "index.json"))
    return tmp_path


def test_a_non_pdf_payload_is_not_stored(scratch):
    """魔数不认就不存。这是 AGENTS §4 那条硬约束在 PDF 支路上的翻版：
    不能只看 HTTP 200 就当下载成功。"""
    rel = SC.put_pdf(u"https://x.example.com/a.pdf", b"<html>not a pdf</html>" * 40,
                     label=u"名创 2026 年报", topic=u"名创优品与泡泡玛特")
    assert rel is None
    idx = SC.load_index()
    assert idx[u"https://x.example.com/a.pdf"][u"status"] == u"not_pdf"


def test_garbled_chinese_extraction_refuses_to_write_a_pointer(scratch, monkeypatch):
    """名创 IRA 那种文件：抽出来 4 万多字符但**一个汉字都没有**。
    标签是中文而正文没有中文 ⇒ 语言在抽取里丢了 ⇒ 这份"原文"回答不了任何问题。"""
    body = u" ".join(u"Mr. Si De 91,979,000 8,151 2026 6 30" for _ in range(200))
    monkeypatch.setattr(SC, "_extract_pdf", lambda raw: (body, u"pdftotext"))
    rel = SC.put_pdf(u"https://x.example.com/ira.pdf", PDF_HEAD + b"x" * 100,
                     label=u"名创优品 2026 中期報告", topic=u"名创优品与泡泡玛特")
    assert rel is None
    assert SC.load_index()[u"https://x.example.com/ira.pdf"][u"status"] == u"pdf_no_cjk"


def test_a_usable_pdf_writes_text_kind_and_the_extractor_used(scratch, monkeypatch):
    body = u"股份支付 3.679 亿元；以股份为基础的支付开支 2.790 亿元。" * 40
    monkeypatch.setattr(SC, "_extract_pdf", lambda raw: (body, u"pdftotext"))
    url = u"https://x.example.com/annual.pdf"
    rel = SC.put_pdf(url, PDF_HEAD + b"x" * 100, label=u"泡泡玛特 2025 年报", topic=u"名创优品与泡泡玛特")
    assert rel == SC.cache_rel(url)
    rec = SC.load_index()[url]
    assert rec[u"kind"] == u"pdf" and rec[u"via"] == u"pdftotext"
    assert u"3.679" in io.open(os.path.join(str(scratch), rel.replace("/", os.sep)),
                              encoding="utf-8").read()


def test_backfill_routes_pdf_urls_to_the_pdf_branch_not_skipping_them(scratch, monkeypatch):
    """原来 `.pdf` 一律记 not_html 跳过。现在要走 PDF 支路，
    而 FRED 的 .csv 那种仍然照旧跳过——两者不是一个东西。"""
    def fake_fetch_bytes(url, timeout=60):
        return PDF_HEAD + b"y" * 200

    monkeypatch.setattr(SC, "fetch_bytes", fake_fetch_bytes)
    monkeypatch.setattr(SC, "_extract_pdf",
                        lambda raw: (u"股份支付 16.88 亿元 " * 60, u"pypdf"))
    data = {u"sources": [
        {u"id": u"S031", u"url": u"https://ir.miniso.com/a.pdf", u"label": u"年报"},
        {u"id": u"S050", u"url": u"https://fred.stlouisfed.org/graph/fredgraph.csv?id=CPIAUCSL",
         u"label": u"CPI 序列"},
    ]}
    idx = {}
    changed = SC.backfill(data, topic=u"名创优品与泡泡玛特", index=idx, sleep=0)
    assert data[u"sources"][0].get(u"cache"), u"PDF 来源仍然没有原文指针"
    assert u"cache" not in data[u"sources"][1], u".csv 被当成 PDF 处理了"
    assert idx[data[u"sources"][1][u"url"]][u"status"] == u"not_html"
    assert changed == 1


def test_the_extractor_prefers_poppler_and_falls_back_to_pypdf(monkeypatch):
    """主路径的选择是量出来的（同一份中文公告 6,661 vs 312 个汉字），不是猜的。"""
    calls = {}

    def fake_run(cmd, **kw):
        calls["cmd"] = list(cmd)
        return 0, u"中文正文 " * 300

    monkeypatch.setattr(SC, "_which", lambda exe: u"/mingw64/bin/pdftotext" if exe == u"pdftotext" else None)
    monkeypatch.setattr(SC, "_run", fake_run)
    text, via = SC._extract_pdf(PDF_HEAD + b"z" * 50)
    assert via == u"pdftotext" and u"中文正文" in text

    monkeypatch.setattr(SC, "_which", lambda exe: None)
    import pypdf as _p
    monkeypatch.setattr(_p, "PdfReader", lambda raw: _FakeReader())
    text2, via2 = SC._extract_pdf(PDF_HEAD + b"z" * 50)
    assert via2 == u"pypdf", via2


class _FakeReader(object):
    """pypdf 的替身：只喂出几页文本，不碰真解析器。"""

    def __init__(self, *a, **k):
        self.pages = [type(u"P", (), {"extract_text": lambda s: u"股份支付 3.679 亿元"})()]

    def __len__(self):
        return len(self.pages)


def test_pypdf_is_declared_as_the_fallback_dependency():
    """兜底路径必须装得上，否则换台机器这条支路只剩 poppler 一条腿（R-07：依赖配置进库）。"""
    req = io.open(os.path.join(ROOT, "requirements.txt"), encoding="utf-8").read().lower()
    assert u"pypdf" in req, u"pypdf 没写进 requirements.txt，兜底抽取在新机器上直接消失"


def test_an_already_refused_pdf_is_not_downloaded_again(scratch, monkeypatch):
    """终态拒绝（抽不出中文、非 HTML）不再重下：覆盖度涨不了，时间全花在重演已知失败上。

    这条同时钉住 10-06 的一次真实事故：`backfill` 里引用了一个没定义的常量，
    29 篇的补抓循环**每一篇都 NameError 退出**，而覆盖率一行没动。
    判绿要看文件，不要看"循环跑完了"。
    """
    calls = []

    def boom(url, timeout=60):
        calls.append(url)
        raise AssertionError("已判读不了的 PDF 不该再下一遍")

    monkeypatch.setattr(SC, "fetch_bytes", boom)
    url = u"https://www1.hkexnews.hk/a.pdf"
    data = {u"sources": [{u"id": u"S031", u"url": url, u"label": u"中期報告"}]}
    idx = {url: {u"file": None, u"status": u"pdf_no_cjk", u"kind": u"pdf"}}
    changed = SC.backfill(data, topic=u"名创优品与泡泡玛特", index=idx, sleep=0)
    assert changed == 0 and u"cache" not in data[u"sources"][0]
    assert not calls, u"重复下载了 %s" % calls


def test_a_pdf_already_in_the_map_gets_its_pointer_without_a_refetch(scratch, monkeypatch):
    """地图里有正文、产物里漏了指针 ⇒ 直接接上，不重抓（并行把 index 盖掉之后要能自愈）。"""
    monkeypatch.setattr(SC, "fetch_bytes",
                        lambda url, timeout=60: (_ for _ in ()).throw(AssertionError("不该重抓")))
    url = u"https://ir.miniso.com/annual.pdf"
    rel = u"text/%016x.txt" % 1
    os.makedirs(os.path.join(str(scratch), u"text"), exist_ok=True)
    io.open(os.path.join(str(scratch), u"text", u"%016x.txt" % 1), "w",
            encoding="utf-8").write(u"股份支付 16.88 亿元 " * 60)
    data = {u"sources": [{u"id": u"S031", u"url": url, u"label": u"年报"}]}
    idx = {url: {u"file": rel, u"status": u"ok", u"kind": u"pdf"}}
    assert SC.backfill(data, topic=u"名创", index=idx, sleep=0) == 1
    assert data[u"sources"][0][u"cache"] == rel


def test_a_transient_fetch_failure_is_retried_next_time(scratch, monkeypatch):
    """与上一条相对：`fetch_failed` 是瞬时故障，**不许**进终态名单。"""
    seen = []

    def fake(url, timeout=60):
        seen.append(url)
        return PDF_HEAD + b"y" * 200

    monkeypatch.setattr(SC, "fetch_bytes", fake)
    monkeypatch.setattr(SC, "_extract_pdf",
                        lambda raw: (u"股份支付 16.88 亿元 " * 60, u"pypdf"))
    url = u"https://ir.miniso.com/b.pdf"
    data = {u"sources": [{u"id": u"S032", u"url": url, u"label": u"年报"}]}
    idx = {url: {u"file": None, u"status": u"fetch_failed", u"kind": u"pdf"}}
    SC.backfill(data, topic=u"名创", index=idx, sleep=0)
    assert seen == [url], u"抓失败过的来源被当成终态跳过了"
    assert data[u"sources"][0].get(u"cache"), u"重试之后没接上指针"
