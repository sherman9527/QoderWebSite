# -*- coding: utf-8 -*-
"""W-192 的形：不装 OCR，改用「机器定位页码 + 人眼看页面图」。

依据是 10-05 的两条实测：
· 四篇试点 13 份 PDF 里 9 份抽不出汉字（子集字体没有 ToUnicode），
  但**数字照样抽得出来**（`4,335 4,522` 这种原样在）；
· 缺的能力不是"认字"，是"这一行左边写的是什么"——那由看一张页面图来解决。
PyMuPDF 是 wheel，能直接光栅化，不需要 tesseract/poppler/任何系统安装。
"""
import io
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import pdfpage as PP  # noqa: E402

fitz = pytest.importorskip("fitz", reason="这台机器没装 PyMuPDF 时整条支路不适用")


@pytest.fixture
def tiny_pdf(tmp_path):
    """现场造一份两页 PDF：第一页没有目标数，第二页有。
    数字用 ASCII——正因为汉字在真案例里会丢，测试不许依赖汉字能抽出来。"""
    doc = fitz.open()
    for text in (u"Some unrelated table 12.34 here", u"Share-based payment expenses 3.679 million"):
        pg = doc.new_page()
        pg.insert_text((72, 120), text, fontsize=14)
    p = str(tmp_path / "tiny.pdf")
    doc.save(p)
    doc.close()
    return p


def test_find_pages_locates_the_page_by_its_number_layer(tiny_pdf):
    hits = PP.find_pages(u"local://tiny", [u"3.679"], src=tiny_pdf)
    assert hits and hits[0][0] == 2, u"数字层没能把页码定位出来：%s" % hits


def test_the_rendered_page_is_a_real_png(tmp_path, monkeypatch):
    doc = fitz.open()
    pg = doc.new_page()
    pg.insert_text((72, 120), u"Hello 3.679 million", fontsize=14)
    p = str(tmp_path / "one.pdf")
    doc.save(p)
    doc.close()
    monkeypatch.setattr(PP, "PAGES", str(tmp_path / "pages"))
    out, n = PP.render(u"file://one", 1, src=p)
    assert n == 1
    raw = io.open(out, "rb").read()
    assert raw[:8] == b"\x89PNG\r\n\x1a\n", u"渲染出来的不是 PNG"
    assert len(raw) > 1000, u"页面图只有 %d 字节，多半是空白" % len(raw)


def test_a_page_out_of_range_is_refused_with_the_page_count(tmp_path, monkeypatch):
    doc = fitz.open()
    doc.new_page()
    p = str(tmp_path / "one.pdf")
    doc.save(p)
    doc.close()
    monkeypatch.setattr(PP, "PAGES", str(tmp_path / "pages"))
    with pytest.raises(RuntimeError) as e:
        PP.render(u"file://one", 9, src=p)
    assert u"共 1 页" in str(e.value), str(e.value)


def test_without_an_engine_it_says_what_is_missing_and_does_not_install_ocr(monkeypatch):
    monkeypatch.setitem(sys.modules, u"fitz", None)
    with pytest.raises(RuntimeError) as e:
        PP._fitz()
    msg = str(e.value)
    assert u"pymupdf" in msg.lower() and u"OCR" in msg, msg
