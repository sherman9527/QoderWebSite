# -*- coding: utf-8 -*-
"""W-192：PDF 的**数字层抽得出、标签抽不出**时，把那一页渲染成图给人看。

为什么不是 OCR（10-05 改的形）：开发者一句「你不是可以识别图片嘛」问对了。
真实分布也是这么说的——四篇试点试了 13 份 PDF，4 份能抽出中文、9 份不能，
但那 9 份里**数字全部原样抽得出来**（`4,335 4,522` 这种），丢的是汉字标签
（子集字体没有 ToUnicode）。所以缺的从来不是"识别字符"的能力，是"这一行左边写的
是什么"。而那个由多模态读一张页面图来做，比装一个中文 OCR 引擎更准、也更可核：
图就存在本地，谁都能重看；OCR 的错误会造出"看着像来源"的错数。

PyMuPDF（`fitz`）在这台机器上是 wheel 装好的，能直接把 PDF 页光栅化，
**不需要 tesseract、不需要 poppler、不需要装任何系统软件**。
"""
from __future__ import unicode_literals

import hashlib
import io
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRATCH = os.environ.get("KE_SCRATCH") or os.path.join(ROOT, ".research-scratch")
PAGES = os.path.join(SCRATCH, "text", "pages")

# Windows 上 stdout 默认按 ANSI 码页（这台机器是 GBK）编码，而本仓库的输出里全是
# 中文与 ⇒/≠/· 这类非 GBK 字符。少这道守卫不是显示难看，是**直接崩**：
# 10-26 就是 validate.py 打印一条 G-15 告警里的 ⇒ 时抛 UnicodeEncodeError，
# 把 9 篇渲染打成 rc=1 —— 看着像质量闸门拦的，其实是编码。守卫本身由
# tests/test_contract.py 那条"会 print 的脚本必须钉住输出编码"守住。
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def _fitz():
    """只有这一处 import：引擎不在就明确说缺什么，不悄悄退回去装 OCR。"""
    try:
        import fitz
    except ImportError:
        fitz = None
    if fitz is None:
        raise RuntimeError(
            u"渲染 PDF 需要 PyMuPDF（`pip install pymupdf`）。"
            u"这里走的是「数字层抽得出、标签由人眼看图确认」的路，不需要 OCR 引擎。")
    return fitz


def fetch_pdf(url, timeout=90):
    sys.path.insert(0, os.path.join(ROOT, "scripts"))
    import sourcecache as SC

    return SC.fetch_bytes(url, timeout=timeout)


def _sha(url):
    return hashlib.sha1((url or u"").encode("utf-8")).hexdigest()[:16]


def render(url, page, src=None, dpi=150):
    """渲染第 `page` 页（1 起）成 PNG，返回 (路径, 总页数)。

    `src` 是本地 PDF 路径；不给就按 url 现取一次（原件不进版本库，落在 scratch）。
    """
    fitz = _fitz()
    if src:
        doc = fitz.open(src)
    else:
        raw = fetch_pdf(url)
        if not (raw or b"").startswith(b"%PDF-"):
            raise RuntimeError(u"拿回来的不是 PDF（魔数不对）：%s" % url[:60])
        doc = fitz.open(stream=raw, filetype="pdf")
    try:
        n = doc.page_count
        if not (1 <= int(page) <= n):
            raise RuntimeError(u"页码超出范围：这份 PDF 共 %d 页，要的是 %s" % (n, page))
        pg = doc[int(page) - 1]
        pix = pg.get_pixmap(dpi=int(dpi))
        if not os.path.isdir(PAGES):
            os.makedirs(PAGES)
        out = os.path.join(PAGES, u"%s-p%03d.png" % (_sha(url), int(page)))
        pix.save(out)
        return out, n
    finally:
        doc.close()


def find_pages(url, numbers, min_words=1, src=None):
    """用**数字层**把页码定位出来。文本层丢了汉字，但数字还在，
    所以"哪一页可能有这个数"是机器能答的，"这一行说的是什么"才需要人眼。
    返回 [(页码, 命中数)]，按命中数降序。
    """
    fitz = _fitz()
    doc = fitz.open(src) if src else fitz.open(stream=fetch_pdf(url), filetype="pdf")
    hits = []
    try:
        for i, pg in enumerate(doc, 1):
            t = re.sub(u"[\\s,，]+", u"", pg.get_text() or u"")
            c = sum(1 for k in numbers if re.sub(u"[\\s,，]", u"", k) in t)
            if c >= min_words:
                hits.append((i, c))
    finally:
        doc.close()
    hits.sort(key=lambda x: -x[1])
    return hits


def main(argv=None):
    argv = list(argv if argv is not None else sys.argv[1:])
    if len(argv) < 1:
        print(__doc__)
        return 2
    if argv[0] == u"find":
        url = argv[1]
        nums = [n for n in argv[2:] if n]
        for page, c in find_pages(url, nums):
            print(u"  第 %d 页：命中 %d/%d 个数" % (page, c, len(nums)))
        return 0
    url = argv[0]
    page = argv[1] if len(argv) > 1 else 1
    src = argv[2] if len(argv) > 2 else None
    out, n = render(url, page, src=src)
    print(u"已渲染 %s（共 %d 页）→ %s" % (url[:60], n, os.path.relpath(out, ROOT)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
