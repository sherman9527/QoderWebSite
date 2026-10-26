# -*- coding: utf-8 -*-
"""W-189 来源原文层：把"这条来源到底写了什么"存下来。

为什么需要：`sources[]` 只有 `url` + 人写的 `label` 摘要，**没有页面正文**。于是三件
本来该有确定答案的事永远只能停在"缩范围"：
· W-164 的 308 行、W-162 的 383 条——是真没出处，还是 label 没写全？答不出；
· 改指针只能"加"不能"换"：删一条引用要证明来源**不含**该断言，摘要证明不了；
· 数字匹配类判据反复被同一件事骗（撞号、派生数、量级词）——没有原文可查，只能拿字符串当证据。

这一层只做最小可用形态：抓到页面就把正文落到 `.research-scratch/text/<sha16(url)>.txt`，
并让 `sources[].cache` 指得到它。不含摘要、不改判据——"这个数在不在来源原文里"
是下一步（有了这层才谈得上自动化）。

三条硬约束：
1. 只在**本地**，不进版本库（`.research-scratch/` 已在 .gitignore，R-08 把这个目录关在这里）；
2. `prune_scratch.py` 管的就是这个目录，所以它必须知道 `text/` 是证据不是垃圾——
   被产物引用的原文永不删（见 `scripts/prune_scratch.py`）；
3. 抓取失败不能污染数据：拿不到就**不写 `cache` 字段**，绝不写一个指空文件的指针。
"""
from __future__ import unicode_literals

import collections
import hashlib
import io
import json
import os
import re
import sys
import threading
import time

# Windows 上 stdout 默认按 ANSI 码页（这台机器是 GBK）编码，而本仓库的输出里全是
# 中文与 ⇒/≠/· 这类非 GBK 字符。少这道守卫不是显示难看，是**直接崩**：
# 10-26 就是 validate.py 打印一条 G-15 告警里的 ⇒ 时抛 UnicodeEncodeError，
# 把 9 篇渲染打成 rc=1 —— 看着像质量闸门拦的，其实是编码。守卫本身由
# tests/test_contract.py 那条"会 print 的脚本必须钉住输出编码"守住。
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRATCH = os.environ.get("KE_SCRATCH") or os.path.join(ROOT, ".research-scratch")
TEXT_DIR = os.path.join(SCRATCH, "text")
INDEX = os.path.join(TEXT_DIR, "index.json")
_LOCK = threading.Lock()

# 与 config/topic_data.schema.json 的 $defs/source.properties 必须一致。
# 这里列一份、schema 列一份、w157_hand 的 newsrc 再列一份就是三处漂移，
# 而 G-10 为此判死过整篇（`additionalProperties:false`）。测试钉住它们相等。
SOURCE_KEYS = (u"id", u"url", u"label", u"publisher", u"retrieved", u"cache")

CACHE_RE = re.compile(r"^text/[0-9a-f]{16}\.txt$")

_TAG = re.compile(r"<[^>]+>")
_SCRIPT = re.compile(r"<(script|style|noscript)\b[^>]*>.*?</\1>", re.I | re.S)
_WS = re.compile(r"[ \t\u3000]+")
_BLANK = re.compile(r"\n{3,}")

# 正文短到这个程度基本等于"抓到一个 JS 空壳"，存下来也回答不了任何数字。
MIN_CHARS = 200

# 不是网页的来源不抓：`images._urlopen` 按 utf-8 解码字节，PDF/Excel 进去就是乱码。
# PDF 有专门的支路（`put_pdf`，W-191），剩下这些仍然不抓。
SKIP_EXT = (u".xlsx", u".xls", u".doc", u".docx", u".ppt", u".pptx",
            u".zip", u".gz", u".csv", u".png", u".jpg", u".jpeg", u".gif", u".webp")
PDF_EXT = (u".pdf",)
PDF_MAGIC = b"%PDF-"
_CJK = re.compile(u"[\u4e00-\u9fff]")
# \u5df2\u7ecf\u5224\u8fc7"\u8fd9\u4e00\u4efd\u8bfb\u4e0d\u4e86"\u7684\u7ec8\u6001\uff1a\u4e0b\u6b21\u4e0d\u518d\u91cd\u4e0b\u8f7d\u3001\u4e0d\u518d\u91cd\u62d2\u3002
# `fetch_failed` \u4e0d\u5728\u8fd9\u91cc\u2014\u2014\u90a3\u662f\u77ac\u65f6\u6545\u969c\uff0c\u8be5\u91cd\u8bd5\u3002
TERMINAL_REFUSAL = (u"pdf_no_cjk", u"not_html", u"pdf_error", u"not_pdf")


def _which(exe):
    """单独一个函数而不是直接用 shutil.which：抽取路径的选择是要测的，
    而测试里必须能把"这台机器有没有 poppler"换掉。"""
    import shutil
    return shutil.which(exe)


def _run(cmd, **kw):
    import subprocess
    p = subprocess.run(cmd, capture_output=True, timeout=kw.get("timeout", 180))
    return p.returncode, p.stdout.decode("utf-8", "ignore")


def _temp_pdf(raw):
    import tempfile
    fd, path = tempfile.mkstemp(suffix=u".pdf")
    with os.fdopen(fd, u"wb") as f:
        f.write(raw)
    return path


def _extract_pdf(raw):
    """返回 (正文, 用的哪条路)。

    主次是量出来的，不是按"哪个库更出名"排的：同一份 hkexnews 中文公告，
    poppler 抽出 6,661 个汉字、pypdf 前 12 页只有 312 个。所以 poppler 优先、pypdf 兜底。
    """
    exe = _which(u"pdftotext")
    path = _temp_pdf(raw)
    try:
        if exe:
            rc, text = _run([exe, u"-enc", u"UTF-8", u"-layout", path, u"-"])
            if rc == 0 and (text or u"").strip():
                return text, u"pdftotext"
        import pypdf
        reader = pypdf.PdfReader(path)
        text = u"".join((pg.extract_text() or u"") for pg in reader.pages)
        return text, u"pypdf"
    finally:
        try:
            os.remove(path)
        except OSError:
            pass


def fetch_bytes(url, timeout=60):
    """PDF 走字节版：文本版 `_urlopen` 会把字节按 utf-8 解码，那是这份层要避免的事。"""
    import images as IM
    return IM._urlopen_bytes(url, timeout=timeout)


def put_pdf(url, raw, label=None, topic=None, index=None):
    """PDF 支路。三条拒绝线，任何一条命中都不写指针：
    ① 魔数不对（HTTP 200 不等于拿到了 PDF）；
    ② 抽出来太短；
    ③ **标签是中文而正文一个汉字都没有**——名创 2026 IRA 就是这种：4.5 万字符、0 汉字，
       子集字体没有 ToUnicode，抽出来的"原文"读不了，存下来只会伪装成"已经查过了"。
    """
    idx = index if index is not None else load_index()
    rec = {u"at": dt_today(), u"topic": topic, u"kind": u"pdf",
           u"label_cjk": bool(_CJK.search(label or u""))}
    if not (raw or b"").startswith(PDF_MAGIC):
        rec.update({u"file": None, u"status": u"not_pdf"})
        idx[url] = rec
        if index is None:
            _save_index(idx)
        return None
    try:
        text, via = _extract_pdf(raw)
    except Exception as e:
        rec.update({u"file": None, u"status": u"pdf_error", u"error": unicode_short(repr(e))})
        idx[url] = rec
        if index is None:
            _save_index(idx)
        return None
    text = _WS.sub(u" ", text or u"").strip()
    cjk = len(_CJK.findall(text))
    if len(text) < MIN_CHARS:
        rec.update({u"file": None, u"status": u"pdf_thin", u"chars": len(text), u"via": via})
        idx[url] = rec
        if index is None:
            _save_index(idx)
        return None
    if rec[u"label_cjk"] and cjk == 0:
        rec.update({u"file": None, u"status": u"pdf_no_cjk", u"chars": len(text), u"via": via})
        idx[url] = rec
        if index is None:
            _save_index(idx)
        return None
    rel = cache_rel(url)
    abs_path = os.path.join(SCRATCH, rel.replace("/", os.sep))
    d = os.path.dirname(abs_path)
    if not os.path.isdir(d):
        os.makedirs(d)
    if not os.path.isfile(abs_path):
        with io.open(abs_path, "w", encoding="utf-8") as f:
            f.write(text)
    rec.update({u"file": rel, u"chars": len(text), u"cjk": cjk, u"via": via,
                u"bytes": os.path.getsize(abs_path), u"status": u"ok", u"kind": u"pdf"})
    idx[url] = rec
    if index is None:
        _save_index(idx)
    return rel


def cache_key(url):
    return hashlib.sha1(url.encode("utf-8")).hexdigest()[:16]


def cache_rel(url):
    return u"text/%s.txt" % cache_key(url)


def is_cache_ref(value):
    return bool(value) and isinstance(value, str) and bool(CACHE_RE.match(value))


def extract_text(html):
    """粗暴但可核对：去掉 script/style/noscript 与标签，压空白。
    不做正文抽取（那是另一门学问，而且会引入"抽掉了什么"的新问题）。"""
    s = _SCRIPT.sub(u" ", html or u"")
    s = _TAG.sub(u" ", s)
    try:
        import html as _html
        s = _html.unescape(s)
    except Exception:
        pass
    s = s.replace(u"\r\n", u"\n").replace(u"\r", u"\n")
    s = _WS.sub(u" ", s)
    s = _BLANK.sub(u"\n\n", s)
    return s.strip()


def load_index(path=None):
    p = path or INDEX
    if not os.path.isfile(p):
        return {}
    try:
        return json.load(io.open(p, encoding="utf-8"))
    except ValueError:
        return {}


def _save_index(idx, path=None):
    p = path or INDEX
    d = os.path.dirname(p)
    if not os.path.isdir(d):
        os.makedirs(d)
    tmp = p + u".tmp"
    with io.open(tmp, "w", encoding="utf-8") as f:
        json.dump(idx, f, ensure_ascii=False, sort_keys=True, indent=1)
    # os.replace 不是 os.rename：后者在 Windows 上撞到已存在的目标会抛 FileExistsError，
    # 而这条路径每次都撞到"索引已经存在"那一支。
    os.replace(tmp, p)


def put(url, html, topic=None, index=None):
    """存一份正文，返回相对 `.research-scratch/` 的路径（就是 sources[].cache 的值）。
    太短（JS 空壳）或抓不到 → 返回 None，**不写指针**。"""
    text = extract_text(html)
    own = index is None
    idx = index if not own else load_index()
    rel = cache_rel(url)
    if len(text) < MIN_CHARS:
        idx[url] = {u"file": None, u"chars": len(text), u"status": u"thin",
                    u"at": dt_today(), u"topic": topic}
        if own:
            _save_index(idx)
        return None
    abs_path = os.path.join(SCRATCH, rel.replace("/", os.sep))
    d = os.path.dirname(abs_path)
    if not os.path.isdir(d):
        os.makedirs(d)
    if not os.path.isfile(abs_path):
        with io.open(abs_path, "w", encoding="utf-8") as f:
            f.write(text)
    idx[url] = {u"file": rel, u"chars": len(text),
                u"bytes": os.path.getsize(abs_path),
                u"status": u"ok", u"at": dt_today(), u"topic": topic}
    if own:
        # 研究阶段是线程池（--workers），地图是共享文件：读-改-写不加锁就会丢条目，
        # 丢的那条正好是"某个来源有没有原文"——而这层的全部意义。
        with _LOCK:
            merged = load_index()
            merged[url] = idx[url]
            _save_index(merged)
    return rel


def dt_today():
    import datetime as _dt
    return _dt.date.today().isoformat()


def read(url):
    rel = load_index().get(url, {}).get(u"file")
    if not rel:
        return None
    p = os.path.join(SCRATCH, rel.replace("/", os.sep))
    if not os.path.isfile(p):
        return None
    return io.open(p, encoding="utf-8").read()


def fetch(url, timeout=25):
    """复用配图那套请求头（`images._urlopen` 自带 UA 与 Referer，走的是本机实测可达的路）。
    不自己拼 urllib：本项目已经因为"只看状态码不看字节"踩过一次（AGENTS.md §4）。

    手动跟一次 308：urllib 默认处理 301/302/303/307，**不处理 308**，
    而 cerebras.ai/pricing 就是这么把一条正文来源判成"抓不到"的——
    少跟一次跳转，那条来源就永远没有原文。
    """
    import images as IM
    try:
        return IM._urlopen(url, timeout=timeout)
    except Exception as e:
        code = getattr(e, "code", None)
        loc = None
        try:
            loc = e.headers.get("Location") if getattr(e, "headers", None) else None
        except Exception:
            loc = None
        if code in (301, 302, 303, 307, 308) and loc:
            import urllib.parse as UP
            return IM._urlopen(UP.urljoin(url, loc), timeout=timeout)
        raise


def backfill(topic_data, topic=None, limit=None, sleep=0.6, opener=None, index=None):
    """给 data.json 里还没有 cache 的每条来源补原文。返回改动条数（就地改 dict）。"""
    op = opener or fetch
    idx = index if index is not None else load_index()
    changed = 0
    srcs = topic_data.get(u"sources") or []
    todo = [s for s in srcs if s.get(u"url") and not s.get(u"cache")]
    for s in todo[:limit]:
        url = s[u"url"]
        rec = idx.get(url) or {}
        # 地图里有正文、产物里却漏了指针：直接补指针，不重抓。
        # （并行补覆盖率时地图被盖掉过，这一支也让 `rebuild` 之后能自愈。）
        if rec.get(u"file"):
            s[u"cache"] = rec[u"file"]
            changed += 1
            continue
        # 上次已经判过"这一份读不了"的（中文子集字体、非 HTML），本轮不再下载第二遍。
        # 不这么做的话，AI制药 那 47 条缺项里有一半是**同一批 PDF 反复下、反复拒**——
        # 覆盖度涨不了，时间全花在重演已知失败上。抓失败不在此列：那是瞬时故障，该重试。
        if rec.get(u"status") in TERMINAL_REFUSAL:
            continue
        low = url.split(u"#")[0].split(u"?")[0].lower()
        if low.endswith(PDF_EXT):
            # W-191：财报/年报是 PDF，而"查不到"与"没原文"必须是两件事。
            # 「地图里已有正文就先接指针」那条在上方统一处理了，这里只管下载与拒收。
            try:
                raw = fetch_bytes(url)
            except Exception as e:
                idx[url] = {u"file": None, u"status": u"fetch_failed", u"kind": u"pdf",
                            u"error": unicode_short(repr(e)), u"at": dt_today(), u"topic": topic}
                time.sleep(sleep)
                continue
            if put_pdf(url, raw, label=s.get(u"label"), topic=topic, index=idx):
                s[u"cache"] = idx[url][u"file"]
                changed += 1
            time.sleep(sleep)
            continue
        if low.endswith(SKIP_EXT):
            # 记一笔"为什么没有原文"，否则下一次谁再来查覆盖度，
            # 只会看到一个说不清的缺项。
            idx.setdefault(url, {u"file": None, u"status": u"not_html",
                                 u"at": dt_today(), u"topic": topic})
            continue
        if url in idx and idx[url].get(u"file"):
            s[u"cache"] = idx[url][u"file"]
            changed += 1
            continue
        try:
            html = op(url)
        except Exception as e:
            idx[url] = {u"file": None, u"status": u"fetch_failed",
                        u"error": unicode_short(repr(e)), u"at": dt_today(), u"topic": topic}
            time.sleep(sleep)
            continue
        rel = put(url, html, topic=topic, index=idx)
        if rel:
            s[u"cache"] = rel
            changed += 1
        time.sleep(sleep)
    if index is None:
        _save_index(idx)
    return changed


def unicode_short(s, n=160):
    return s[:n]


def referenced_files(output_dir=None):
    """产物引用到的每一个 cache 路径。`prune_scratch.py` 用它做免死名单。"""
    output_dir = output_dir or os.path.join(ROOT, "output")
    out = set()
    for name in sorted(os.listdir(output_dir)):
        p = os.path.join(output_dir, name, "data.json")
        if not os.path.isfile(p):
            continue
        try:
            d = json.load(io.open(p, encoding="utf-8"))
        except ValueError:
            continue
        for s in d.get(u"sources") or []:
            c = s.get(u"cache")
            if is_cache_ref(c):
                out.add(c)
    return out


def rebuild(output_dir=None):
    """从产物反推索引：`sources[].cache` 才是权威指针，`index.json` 只是地图。

    为什么不许把这张地图当唯一真相：并行补覆盖率时每个进程都是"整表读—改—写"，
    后落盘的会把先落盘的盖掉（锁只在单进程内有效，跨进程锁不住，也不想为这个
    引入文件锁）。所以跑完必须能重建，重建不出来才算真丢。
    """
    out = output_dir or os.path.join(ROOT, u"output")
    old = load_index()
    idx = {}
    for name in sorted(os.listdir(out)):
        dp = os.path.join(out, name, u"data.json")
        if not os.path.isfile(dp):
            continue
        try:
            d = json.load(io.open(dp, encoding="utf-8"))
        except ValueError:
            continue
        for s in d.get(u"sources") or []:
            url, rel = s.get(u"url"), s.get(u"cache")
            if not url or not is_cache_ref(rel):
                continue
            p = os.path.join(SCRATCH, rel.replace(u"/", os.sep))
            prev = old.get(url) or {}
            if not os.path.isfile(p):
                idx[url] = {u"file": None, u"status": u"map_only", u"topic": name,
                            u"at": prev.get(u"at") or dt_today()}
                continue
            t = io.open(p, encoding="utf-8").read()
            idx[url] = {u"file": rel, u"chars": len(t), u"bytes": os.path.getsize(p),
                        u"status": u"ok", u"topic": name,
                        u"at": prev.get(u"at") or dt_today(),
                        u"kind": prev.get(u"kind"), u"via": prev.get(u"via")}
    # 「没有文件」的那些记录（fetch_failed / thin / not_html / pdf_no_cjk）**必须留下**：
    # 它们正是"为什么这条来源没有原文"的答案。第一版 rebuild 只从有文件的指针重建，
    # 结果覆盖度报表上一行「试过 11、拒绝 无」——拒绝记录被自己抹掉了，
    # 这比没有地图更坏：它把失败说成没发生过。
    for url, v in old.items():
        if url in idx or v.get(u"file"):
            continue
        idx[url] = v
    _save_index(idx)
    return len(idx)


def coverage(topic=None):
    rows = []
    out = os.path.join(ROOT, "output")
    for name in sorted(os.listdir(out)):
        p = os.path.join(out, name, "data.json")
        if not os.path.isfile(p):
            continue
        if topic and name != topic:
            continue
        d = json.load(io.open(p, encoding="utf-8"))
        srcs = d.get(u"sources") or []
        have = sum(1 for s in srcs if s.get(u"cache"))
        rows.append((name, len(srcs), have))
    return rows


def main(argv=None):
    argv = list(argv or sys.argv[1:])
    if argv and argv[0] == u"rebuild":
        n = rebuild()
        print(u"索引已从产物重建：%d 条来源有原文指针" % n)
        return 0
    if argv and argv[0] == u"coverage":
        rows = coverage(argv[1] if len(argv) > 1 else None)
        tot = sum(r[1] for r in rows)
        got = sum(r[2] for r in rows)
        idx = load_index()
        skipped = sum(1 for v in idx.values() if v.get(u"status") == u"not_html")
        failed = sum(1 for v in idx.values() if v.get(u"status") in (u"fetch_failed", u"thin"))
        pdfs = [v for v in idx.values() if v.get(u"kind") == u"pdf"]
        pdf_ok = sum(1 for v in pdfs if v.get(u"file"))
        refusals = collections.Counter(v.get(u"status") for v in pdfs if not v.get(u"file"))
        for name, n, have in rows:
            print(u"%-24s %4d 条来源，有原文 %4d（%.0f%%）" % (name, n, have,
                                                             100.0 * have / max(n, 1)))
        print(u"合计 %d / %d（%.1f%%）；非网页跳过 %d、抓失败或空壳 %d" % (
            got, tot, 100.0 * got / max(tot, 1), skipped, failed))
        print(u"PDF 支路：入库 %d / 试过 %d；拒绝 %s" % (
            pdf_ok, len(pdfs),
            u"、".join(u"%s %d" % (k, v) for k, v in refusals.most_common()) or u"无"))
        print(u"注意：PDF 抽不出中文时拒绝入库（status=pdf_no_cjk）——"
              u"这类来源的查不到仍然不等于没出处")
        return 0
    topic = argv[0] if argv else None
    if not topic:
        # 这一句必须排在拼路径之前：原来先 join(ROOT,"output",None) 再判 None，
        # 于是"不带参数敲它"报的是 TypeError 而不是用法。
        # （coverage / rebuild 两个子命令在上面就 return 了，走到这里只可能是领域名）
        print(u"用法：python scripts/sourcecache.py coverage | rebuild | <领域>")
        return 2
    limit = int(os.environ.get("KE_CACHE_LIMIT") or 0) or None
    dp = os.path.join(ROOT, "output", topic, "data.json")
    if not os.path.isfile(dp):
        print(u"没有这个领域的产物：%s" % topic)
        return 2
    data = json.load(io.open(dp, encoding="utf-8"))
    n = backfill(data, topic=topic, limit=limit)
    # 产物文件不许就地覆写：崩在中途就是一份坏 data.json，而它是渲染的唯一输入。
    tmp = dp + u".tmp"
    with io.open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    os.replace(tmp, dp)
    print(u"%s：补上 %d 条原文（共 %d 条来源）" % (topic, n, len(data.get(u"sources") or [])))
    return 0


if __name__ == "__main__":
    sys.exit(main())
