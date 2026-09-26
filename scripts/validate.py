#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""质量闸门——本项目的唯一裁判。

本地手动、generate.py 的第 5 阶段、pre-commit 都必须调这里，不要在别处复制校验逻辑。
理由：规则写两处必然漂移，漂移就是回归漏洞的来源（见 memo.md D-05）。

用法：
  python scripts/validate.py --all                  # 扫 output/ 全部领域
  python scripts/validate.py --domain 咖啡           # 只扫一个
  python scripts/validate.py --gate G-05            # 只跑一条
  python scripts/validate.py --list                 # 列出闸门与对应 spec
"""
import argparse
import hashlib
import io
import json
import math
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import outline as outline_mod  # noqa: E402

try:
    from jsonschema import Draft202012Validator
except ImportError:  # pragma: no cover
    Draft202012Validator = None

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT = os.path.join(ROOT, "output")
CONFIG = os.path.join(ROOT, "config")


def _bar():
    return json.load(io.open(os.path.join(CONFIG, "quality_bar.json"), encoding="utf-8"))


class Finding(object):
    def __init__(self, gate, where, message, level="fail"):
        self.gate = gate
        self.where = where
        self.message = message
        self.level = level

    def __str__(self):
        return "[%s/%s] %s：%s" % (self.gate.id, self.level, self.where, self.message)


class Gate(object):
    # scope="domain" 逐领域跑；"global" 只看 output/ 整体（索引、跨领域配色）
    def __init__(self, gid, title, spec_ref, check, scope="domain"):
        self.id = gid
        self.title = title
        self.spec_ref = spec_ref
        self.check = check
        self.scope = scope


class Ctx(object):
    """一次校验所需的全部输入，闸门只读不写。

    outline 可注入：测试用合成大纲跑闸门，不必碰 config/topics/ 下的真实领域。
    """

    def __init__(self, topic, out_dir, page_path, html, data, bar, outline=None):
        self.topic = topic
        self.out_dir = out_dir
        self.page_path = page_path
        self.html = html
        self.data = data
        self.bar = bar
        self._outline = outline

    def get_outline(self):
        if self._outline is not None:
            return self._outline
        return outline_mod.load_for_topic(self.topic, root=ROOT)

    @property
    def rel_page(self):
        return os.path.relpath(self.page_path, ROOT).replace("\\", "/")


# ---------------------------------------------------------------- 工具

CJK_RE = re.compile(u"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]")
NUMBER_RE = re.compile(r"(?<![\w.])(?:\d{1,3}(?:[,，]\d{3})+|\d+(?:\.\d+)?)(?:\.\d+)?\s*"
                       r"(?:元|万元|万|亿|美元|美金| CHF|EUR|USD|EUR|fr\.|毫米|毫米|mm|cm|克|g|克拉|%"
                       r"|年|周年|只|只|枚|件|家|座|小时|分钟|秒|ms|米|公里|km|马力|匹|缸|升|L|bar|帕|Pa|Hz|振频|转)",
                       re.UNICODE)
# 只要出现两个以上连续数字就算"数字型断言"。早先要求带单位（元/年/mm），
# 结果 "1832" 这种裸年份绕过来源要求——那正是最需要来源的形态。
HAS_NUMBER_RE = re.compile(r"\d{2,}")

PLACEHOLDER_RES = [
    re.compile(r"TODO|FIXME|TBD", re.I),
    re.compile(u"待补充|待完善|占位|略\.{2,}"),
    re.compile(r"\{\{.*?\}\}"),
    re.compile(r"Lorem ipsum", re.I),
]


def cjk_count(text):
    """正文汉字数。中英混排时只数汉字，避免把型号编号算进篇幅。"""
    return len(CJK_RE.findall(text or ""))


def data_text(data):
    """把全部正文抽成一段纯文本，用于字数与占位符检查。"""
    buf = [data.get("lede") or "", data.get("subtitle") or ""]
    for s in data.get("sections", []):
        buf.append(s.get("title") or "")
        buf.append(s.get("intro") or "")
        for b in s.get("blocks", []):
            buf.append(_block_text(b))
    return "\n".join(x for x in buf if x)


def _block_text(b):
    t = b.get("type")
    if t == "prose":
        return b.get("text") or ""
    if t == "keyvalue_table":
        return "\n".join("%s %s" % (r.get("k", ""), r.get("v", "")) for r in b.get("rows", []))
    if t == "timeline":
        return "\n".join("%s %s %s" % (i.get("year", ""), i.get("title", ""), i.get("text", ""))
                         for i in b.get("items", []))
    if t == "price_table":
        return "\n".join(" ".join(str(c) for c in r.get("cells", [])) for r in b.get("rows", []))
    if t == "card_grid":
        out = []
        for c in b.get("cards", []):
            out.append(c.get("title", ""))
            out.append(c.get("body", ""))
            for m in c.get("metrics", []):
                out.append("%s %s" % (m.get("label", ""), m.get("value", "")))
        return "\n".join(out)
    if t == "steps":
        return "\n".join("%s %s %s" % (i.get("title", ""), i.get("text", ""), i.get("spec", ""))
                         for i in b.get("items", []))
    if t == "quote":
        return "%s %s %s" % (b.get("text", ""), b.get("who", ""), b.get("when", ""))
    if t == "fact_strip":
        return "\n".join("%s %s %s" % (f.get("value", ""), f.get("label", ""), f.get("hint", ""))
                         for f in b.get("facts", []))
    if t == "compare":
        out = []
        for side in ("left", "right"):
            s = b.get(side) or {}
            out.append(s.get("title", ""))
            out.extend(s.get("points", []))
        out.append(b.get("verdict", ""))
        return "\n".join(x for x in out if x)
    if t == "note":
        return "%s %s" % (b.get("title", ""), b.get("text", ""))
    return ""


_BRACKET_RE = re.compile(r"\[([^\]\[]{1,80})\]")
# 前后不接字母数字：`[SS1]` 里不能捞出 "S1"，`[1S]` 里不能捞出 "S"。
_SID_IN_BRACKET = re.compile(r"(?<![A-Za-z0-9])S\d{1,4}(?![0-9])")


def _inline_sids(text):
    """一段可见文字里出现的所有 `[Sxx]` 来源标号。

    要连 `[S031,S034]` 这种并列写法一起认——那是渲染器给 fact_strip 生成的形状，
    人写进正文也一样合法。只认 `\[S\d+\]` 会漏掉它，等于留了个后门。"""
    out = []
    for inner in _BRACKET_RE.findall(text or ""):
        out += _SID_IN_BRACKET.findall(inner)
    return out


def reading_minutes(data, bar=None):
    """「约 N 分钟读完」的唯一算法：正文汉字 ÷ 读速 + 每张图 0.15 分钟。

    之前 Python 索引与 React 模板各数各的——模板把标题、图注、来源标签全算进去，
    同一篇页眉显示 25 分钟、闸门却按 6441 字判它合格。
    现在由生成阶段算好写进 data.json，两边都只读这一个数。
    """
    bar = bar or _bar()
    per_min = float(bar["reading"]["assumed_chinese_chars_per_minute"])
    imgs = sum(len(s.get("images") or []) for s in data.get("sections", []))
    return max(1, int(round(cjk_count(data_text(data)) / per_min + imgs * 0.15)))


def hex_to_lab(hexc):
    """sRGB → CIE Lab（D65），用于判断两个领域的配色是否雷同。"""
    h = hexc.strip().lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    r, g, b = (int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4))

    def lin(c):
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

    R, G, B = lin(r), lin(g), lin(b)
    x = (R * 0.4124 + G * 0.3576 + B * 0.1805) / 0.95047
    y = R * 0.2126 + G * 0.7152 + B * 0.0722
    z = (R * 0.0193 + G * 0.1192 + B * 0.9505) / 1.08883

    def f(t):
        return t ** (1.0 / 3.0) if t > 0.008856 else 7.787 * t + 16.0 / 116.0

    fx, fy, fz = f(x), f(y), f(z)
    return (116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz))


def delta_e(c1, c2):
    L1, a1, b1 = hex_to_lab(c1)
    L2, a2, b2 = hex_to_lab(c2)
    return math.sqrt((L1 - L2) ** 2 + (a1 - a2) ** 2 + (b1 - b2) ** 2)


PALETTE_ROLES = ("bg", "primary", "accent")


def palette_of(topic):
    """从 web/src/tokens/index.ts 取该领域的色板签名，按 PALETTE_ROLES 的顺序返回。

    取不到的角色留 None 而不是滤掉：位置一旦会漂移，两套主题字段数不同时
    调用方就只能"跳过这一对"，那是把"没测"混进"测过且通过"。
    整个 token 找不到才返回 None（= 这不是一个领域）。
    """
    path = os.path.join(ROOT, "web", "src", "tokens", "index.ts")
    if not os.path.isfile(path):
        return None
    src = io.open(path, encoding="utf-8").read()
    tok = _token_of(topic)
    if not tok:
        return None
    m = re.search(r'"%s":\s*\{(.*?)\n  \}' % re.escape(tok), src, re.S)
    if not m:
        return None
    body = m.group(1)
    got = lambda k: (re.search(r"%s:\s*\"(#[0-9A-Fa-f]{3,6})\"" % k, body) or [None, None])[1]
    return [got(k) for k in PALETTE_ROLES]


_TOKEN_CACHE = {}


def _token_of(topic):
    if topic in _TOKEN_CACHE:
        return _TOKEN_CACHE[topic]
    p = os.path.join(CONFIG, "topics", topic + ".json")
    tok = None
    if os.path.isfile(p):
        try:
            tok = json.load(io.open(p, encoding="utf-8")).get("theme", {}).get("token")
        except Exception:
            tok = None
    _TOKEN_CACHE[topic] = tok
    return tok


def active_red_lines():
    """读 rule.md 的"当前生效红线"小节。默认无红线时返回空列表（不是错误）。"""
    p = os.path.join(ROOT, "rule.md")
    if not os.path.isfile(p):
        return []
    text = io.open(p, encoding="utf-8").read()
    m = re.search(r"##\s*一、当前生效红线(.*?)(?=\n##\s|\Z)", text, re.S)
    if not m:
        return []
    # 注释块里是"添加格式"示例，不是红线；不剥掉会把示例当成生效条目。
    body = re.sub(r"<!--.*?-->", "", m.group(1), flags=re.S)
    lines = []
    for raw in body.splitlines():
        s = raw.strip()
        if not s or s.startswith("<!--") or s.startswith("**（无）"):
            continue
        r = re.match(r"^-\s*\**\s*\[?\s*(R-?\d+)\s*\]?\s*\**\s*(.+)$", s)
        if r:
            lines.append((r.group(1), r.group(2).strip()))
    return lines


# ---------------------------------------------------------------- 十条闸门

def g01_naming(ctx):
    """G-01 产物命名与位置（specs/knowledge-page-generation）"""
    out = []
    raw = os.path.basename(ctx.page_path)
    # 换名协议判的是**候选页**（`<领域>.html.pending`）。名字规则要问的是
    # "它发布出去叫什么"，不是"它现在这个临时文件叫什么"——否则 G-01 会
    # 在每一次正常发布上都判死一次，而它抱怨的那个名字正是协议要求的样子。
    name = re.sub(r"\.(pending|prev)$", u"", raw)
    want = u"%s.html" % ctx.topic
    if name != want:
        out.append(Finding(g01_naming, ctx.rel_page,
                          u"文件名应为 %s（一篇只有一页，名字不带日期——"
                          u"日期名会让深层链接每天变一次），实际 %s" % (want, name)))
    expect_tail = "output/%s" % ctx.topic
    norm = ctx.page_path.replace("\\", "/")
    if ("/" + expect_tail + "/") not in ("/" + norm.lstrip("/")):
        out.append(Finding(g01_naming, ctx.rel_page,
                           u"应位于 %s/ 之下" % expect_tail))
    # 只留最新版这件事靠闸门守，不靠约定：多出来的一页长得和正常状态一模一样，
    # 没人会去看目录，于是日期页会在某次手工复制之后悄悄堆回来。
    extra = sorted(f for f in published_pages(ctx.out_dir) if f != want)
    if extra:
        out.append(Finding(g01_naming, expect_tail,
                           u"这个领域目录下有多余的页面，只允许 %s；多出来：%s"
                           % (want, u"、".join(extra))))
    return out


def g02_coverage(ctx):
    """G-02 章节覆盖率：大纲声明的每节都必须存在且非空（specs/topic-outline-config）"""
    out = []
    try:
        cfg = ctx.get_outline()
    except outline_mod.OutlineError as e:
        return [Finding(g02_coverage, ctx.topic, u"读不到大纲：%s" % e)]
    by_id = {s.get("id"): s for s in ctx.data.get("sections", [])}
    for want in cfg.sections:
        sec = by_id.get(want.id)
        if sec is None:
            out.append(Finding(g02_coverage, ctx.rel_page,
                               u"缺少章节 %s（%s）" % (want.id, want.title)))
            continue
        chars = cjk_count("\n".join(_block_text(b) for b in sec.get("blocks", [])))
        if chars < 60:
            out.append(Finding(g02_coverage, "%s#%s" % (ctx.rel_page, want.id),
                               u"章节正文过少（%d 汉字），视为未填充" % chars))
    extra = set(by_id) - {s.id for s in cfg.sections}
    for e in sorted(extra):
        out.append(Finding(g02_coverage, "%s#%s" % (ctx.rel_page, e),
                           u"产物出现大纲未声明的章节 %s" % e))
    return out


def _page_image_refs(out_dir):
    """这个领域里**当前页 + 回滚页**引用的图片文件名（并集）。

    孤儿判据要把它们全算成"还在用"。W-145 之前靠"所有历史日期页都算"来兜这个底；
    一篇只留一页之后，兜底换成了 `<领域>.html.prev`——它是换名协议里的回滚目标，
    此刻还没被索引确认，如果按"只有新页引用它"就删掉它，回滚就成一个断图的空壳。
    `.html.pending` 不参与：那是还没过闸门的候选，它的图不算数。
    """
    got = set()
    try:
        names = sorted(os.listdir(out_dir))
    except OSError:
        return got
    for nm in names:
        low = nm.lower()
        if not (low.endswith(".html") or low.endswith(".html.prev")):
            continue
        try:
            html = io.open(os.path.join(out_dir, nm), encoding="utf-8",
                           errors="replace").read()
        except OSError:
            continue
        got |= {os.path.basename(s) for s in
                re.findall(r'<img[^>]*\bsrc="([^"]+)"', html)}
    return got


def published_pages(out_dir):
    """这个领域目录下**已发布**的页面文件名（排序后）。

    W-145 之后只该有一个 `<领域>.html`。返回清单而不是布尔，是因为 G-01 要报出
    多出来的那些叫什么——"目录里有东西不对"这种话没法修。
    （以前它收一个从不使用的 `topic` 参数。签名骗人比签名难看更坏：
    读代码的人会以为这里按领域筛过，于是调用方也就不用自己筛了。）
    """
    try:
        names = os.listdir(out_dir)
    except OSError:
        return []
    return sorted(n for n in names if n.lower().endswith(".html"))


def g03_images(ctx):
    """G-03 图片：引用存在、有 alt、无孤儿、数量达标（specs/image-sourcing）"""
    out = []
    bar = ctx.bar["structure"]
    srcs = re.findall(r'<img[^>]*\bsrc="([^"]+)"', ctx.html)
    alts = re.findall(r'<img[^>]*\balt="([^"]*)"', ctx.html)
    if len(srcs) < bar["min_images"]:
        out.append(Finding(g03_images, ctx.rel_page,
                           u"配图 %d 张，少于要求的 %d 张" % (len(srcs), bar["min_images"])))
    if len(srcs) > bar["max_images"]:
        out.append(Finding(g03_images, ctx.rel_page,
                           u"配图 %d 张，超过上限 %d 张" % (len(srcs), bar["max_images"])))
    for s in srcs:
        if s.startswith("http"):
            out.append(Finding(g03_images, ctx.rel_page, u"图片用了远程地址：%s" % s))
            continue
        fp = os.path.join(ctx.out_dir, s.replace("/", os.sep))
        if not os.path.isfile(fp):
            out.append(Finding(g03_images, ctx.rel_page, u"引用的图片不存在：%s" % s))
    for a in alts:
        if not a.strip():
            out.append(Finding(g03_images, ctx.rel_page, u"存在空 alt 的图片"))
    if len(alts) != len(srcs):
        out.append(Finding(g03_images, ctx.rel_page,
                           u"有 %d 张 img 缺 alt 属性" % (len(srcs) - len(alts))))
    img_dir = os.path.join(ctx.out_dir, "images")
    if os.path.isdir(img_dir):
        referenced = {os.path.basename(s) for s in srcs} | _page_image_refs(ctx.out_dir)
        for f in sorted(os.listdir(img_dir)):
            # 按扩展名筛，不按"排除某个文件名"筛：images/ 里本来就有非图片的
            # 辅助文件（manifest.json、W-105 的 search-stats.json），
            # 而"孤儿图片"判的是图片。原先那句只放过 manifest 的特例
            # 每加一个辅助文件就会漏一次——09-23 实测把大模型篇整个判死。
            if not f.lower().endswith((".jpg", ".jpeg", ".png", ".webp", ".gif")):
                continue
            if f not in referenced:
                out.append(Finding(g03_images, "output/%s/images/%s" % (ctx.topic, f),
                                   u"孤儿图片：产物未引用"))
    for s in ctx.data.get("sections", []):
        if not s.get("images"):
            out.append(Finding(g03_images, "%s#%s" % (ctx.rel_page, s.get("id")),
                               u"该章节无配图，不满足图文并茂"))
    # 同一张图跨章复用 = "图文并茂"退化成"一张图配全文"。
    # 只比章节之间：封面本来就取章节图之一，那是设计意图不是重复。
    by_file = {}
    for s in ctx.data.get("sections", []):
        for im in s.get("images") or []:
            by_file.setdefault(im.get("file"), set()).add(s.get("id"))
    for f, secs in sorted(by_file.items()):
        if len(secs) > 1:
            out.append(Finding(g03_images, ctx.rel_page,
                               u"配图重复：%s 被 %d 个章节共用（%s）" % (
                                   f, len(secs), u"、".join(sorted(x for x in secs if x)))))
    return out


def g04_selfcontained(ctx):
    """G-04 自包含：零外部网络资源（specs/golden-template）"""
    out = []
    pats = [
        (r'<script[^>]+\bsrc\s*=\s*["\']https?://', u"外部 <script src>"),
        (r'<link[^>]+\bhref\s*=\s*["\']https?://[^"\']*(\.css|fonts\.google|font\.ionic)', u"外部样式/字体 <link>"),
        (r'<link[^>]+\brel\s*=\s*["\']stylesheet["\'][^>]+\bhref\s*=\s*["\']https?://', u"外链 stylesheet"),
        (r'@import\s+url\(\s*["\']?https?://', u"CSS @import 远程"),
        (r'url\(\s*["\']?https?://', u"CSS url() 远程资源"),
        (r'<img[^>]+\bsrc\s*=\s*["\']https?://', u"远程图片"),
    ]
    for pat, label in pats:
        hits = re.findall(pat, ctx.html, re.I)
        if hits:
            out.append(Finding(g04_selfcontained, ctx.rel_page,
                               u"发现 %d 处%s，产物必须离线自包含" % (len(hits), label)))
    return out


def g05_words(ctx):
    """G-05 篇幅：正文汉字数落在目标区间（specs/topic-outline-config；memo D-02）"""
    lo, hi = ctx.bar["words"]["min_chars"], ctx.bar["words"]["max_chars"]
    try:
        lo, hi = ctx.get_outline().words_range
    except outline_mod.OutlineError:
        pass
    n = cjk_count(data_text(ctx.data))
    if n < lo:
        return [Finding(g05_words, ctx.rel_page,
                        u"正文 %d 汉字，低于目标下限 %d（约 %d 分钟读不完）" % (n, lo, lo // 500))]
    if n > hi:
        # 软上限之上先量一下硬上限：开发者判定"稍微写超没关系，主要看质量"，
        # 所以超软上限只降级 warn（报告里仍然挂着），超硬上限才判死。
        hard = int(ctx.bar["words"].get("hard_max_chars", hi))
        if hard > hi and n > hard:
            return [Finding(g05_words, ctx.rel_page,
                            u"正文 %d 汉字，超过硬上限 %d（约 %d 分钟），已经不算稍微超" % (
                                n, hard, n // 500))]
        return [Finding(g05_words, ctx.rel_page,
                        u"正文 %d 汉字，超过目标上限 %d（约 %d 分钟读完），"
                        u"内容合格但偏长——可接受，但要确认不是灌水" % (n, hi, n // 500),
                        level="warn")]
    return []


def g06_sourcing(ctx):
    """G-06 数字必须有来源、价格必须有 `as_of` 时点（specs/content-grounding）"""
    out = []
    bar = ctx.bar["sourcing"]
    ids = {s.get("id") for s in ctx.data.get("sources", [])}
    blocked = [d.lower() for d in bar.get("blocked_source_domains", [])]
    for s in ctx.data.get("sources", []):
        url = (s.get("url") or "").lower()
        for d in blocked:
            if d in url:
                out.append(Finding(g06_sourcing, s.get("id", "?"),
                                   u"来源域名 %s 属于低可信黑名单，请换权威来源" % d))
    if not ctx.data.get("sources"):
        return [Finding(g06_sourcing, ctx.rel_page, u"全页没有登记任何来源")]

    def need_refs(where, obj):
        refs = obj.get("source_ids") or []
        if not refs:
            out.append(Finding(g06_sourcing, where,
                               u"含数字但无来源：%s" % (_block_text(obj)[:36] + "…")))
            return
        for r in refs:
            if r not in ids:
                out.append(Finding(g06_sourcing, where, u"引用了不存在的来源 id %s" % r))

    naked_prose = []
    for sec in ctx.data.get("sections", []):
        where0 = "%s#%s" % (ctx.rel_page, sec.get("id"))
        for bi, b in enumerate(sec.get("blocks", [])):
            where = "%s blk%d(%s)" % (where0, bi, b.get("type"))
            t = b.get("type")
            text = _block_text(b)
            # 无条件扫，不挂在"这块有没有数字"上：内嵌标号本身就是引用声明，
            # 一个不带数字的 `[S9]` 一样是在假装出处。
            # 放在 need_refs 里是不够的——那条只在带数字的块上被调用。
            for sid in dict.fromkeys(_inline_sids(text)):
                if sid not in ids:
                    out.append(Finding(
                        g06_sourcing, where,
                        u"正文内嵌的 [%s] 在 sources 里不存在。它印出来就是假凭证："
                        u"要么改成真实 id，要么删掉标号让块级 source_ids 承担引用" % sid))
            has_num = bool(HAS_NUMBER_RE.search(text))
            if t in ("price_table",):
                if bar.get("price_block_requires_as_of", True) and not re.match(
                        r"^\d{4}-\d{2}$", str(b.get("as_of") or "")):
                    out.append(Finding(g06_sourcing, where,
                                       u"价格表缺 as_of（应为 YYYY-MM）：实际 %r" % b.get("as_of")))
                for r in b.get("rows", []):
                    if not (r.get("source_ids") or []):
                        out.append(Finding(g06_sourcing, where,
                                           u"价格行无来源：%s" % "、".join(list(map(str, r.get("cells", [])))[:2])))
            elif t == "fact_strip":
                # 事实条的每一项都是断言，无条件要求来源
                for f in b.get("facts", []):
                    need_refs(where, f)
            elif t == "bar_chart":
                # 每一根柱子都是一个数字断言。图里的数字比正文更容易被读者当成
                # "官方数据"，所以无条件要来源——不看单位、不看是不是整数。
                # 不复用 need_refs：那条消息只会说"含数字但无来源"加一截文本，
                # 对图表来说没人知道是哪根柱子，等于让人回去数。
                for item in b.get("bars", []):
                    refs = item.get("source_ids") or []
                    if not refs:
                        out.append(Finding(g06_sourcing, where,
                                           u"柱子里这个数没有来源：%s = %s" % (
                                               item.get("label") or u"(无名)",
                                               item.get("value"))))
                    for r in refs:
                        if r not in ids:
                            out.append(Finding(g06_sourcing, where,
                                               u"柱子 %s 引用了不存在的来源 id %s" % (
                                                   item.get("label"), r)))
            elif t == "timeline":
                for i in b.get("items", []):
                    need_refs(where, i) if HAS_NUMBER_RE.search(str(i.get("text", ""))) else None
            elif t == "keyvalue_table":
                for r in b.get("rows", []):
                    if HAS_NUMBER_RE.search(str(r.get("v", ""))) and r.get("has_number", True):
                        need_refs(where, r)
            elif t == "quote" and has_num:
                need_refs(where, b)
            elif t == "card_grid":
                for c in b.get("cards", []):
                    for m in c.get("metrics", []):
                        if HAS_NUMBER_RE.search(str(m.get("value", ""))):
                            need_refs(where, m)
            elif t == "prose" and has_num and not b.get("source_ids"):
                # 纯叙述里夹带具体数字也要求可溯源。这里曾经是一个 `pass`：
                # 检测写对了，动作没写，于是全站 195 个 prose 块的欠账静默了两周。
                naked_prose.append(u"%s blk%d" % (sec.get("id"), bi))
    if naked_prose:
        # 一条带计数的 warn，不是每块一条：195 行的日志一周之内就会被人整段跳过，
        # 那和 `pass` 没有区别。要明细跑 `python scripts/validate.py <领域> --verbose`
        # 或直接看这条里的前 5 个。
        out.append(Finding(g06_sourcing, ctx.rel_page,
                           u"%d 个 prose 块带数字但没有块级 source_ids（前 5 个：%s）。"
                           u"数字未挂来源按 R-02 应当不写或改成明确区间" % (
                               len(naked_prose), u"、".join(naked_prose[:5])),
                           level="warn"))
    if ctx.data.get("research_mode") != "online":
        out.append(Finding(g06_sourcing, ctx.rel_page,
                           u"research_mode=%r，正文数字未经联网查证" % ctx.data.get("research_mode"),
                           level="warn"))
    return out


def g07_placeholders(ctx):
    """G-07 占位符残留（specs/content-grounding）"""
    out = []
    text = data_text(ctx.data)
    for pat in PLACEHOLDER_RES:
        for m in pat.finditer(text):
            snippet = text[max(0, m.start() - 18):m.end() + 18].replace("\n", " ")
            out.append(Finding(g07_placeholders, ctx.rel_page,
                               u"疑似占位符 %r：…%s…" % (m.group(0), snippet)))
            break
    for bad in ctx.bar.get("placeholders", []):
        if bad in text and not any(bad in p.pattern for p in PLACEHOLDER_RES):
            out.append(Finding(g07_placeholders, ctx.rel_page, u"出现占位文本 %r" % bad))
    return out


_FP_CACHE = {}


def current_fingerprint():
    """当前模板的指纹。跑一次 node 取，之后复用——测试里 monkeypatch 这个函数。"""
    if "v" not in _FP_CACHE:
        p = subprocess.run(
            [os.environ.get("NODE", "node"), os.path.join("scripts", "render.mjs"),
             "--print-fingerprint"],
            cwd=ROOT, capture_output=True, timeout=180,
        )
        _FP_CACHE["v"] = json.loads(p.stdout.decode("utf-8", "ignore").strip() or "{}")
    return _FP_CACHE["v"]


def g08_fingerprint(ctx):
    """G-08 模板指纹：产物必须由当前模板渲染（specs/golden-template）"""
    out = []
    m = re.search(r"<!--template-fingerprint:(.*?)-->", ctx.html, re.S)
    if not m:
        return [Finding(g08_fingerprint, ctx.rel_page,
                        u"产物无模板指纹，疑似手工编辑或绕过模板生成")]
    try:
        got = json.loads(m.group(1))
    except ValueError:
        return [Finding(g08_fingerprint, ctx.rel_page, u"模板指纹无法解析")]
    try:
        want = current_fingerprint()
    except Exception as e:
        return [Finding(g08_fingerprint, ctx.rel_page, u"无法取当前模板指纹：%s" % e, level="warn")]
    if got.get("blocks") != want.get("blocks"):
        out.append(Finding(g08_fingerprint, ctx.rel_page,
                           u"区块枚举与当前模板不一致（模板已改，产物需重渲染）"))
    if got.get("rev") != want.get("rev"):
        out.append(Finding(g08_fingerprint, ctx.rel_page,
                           u"模板版本 %s ≠ 当前 %s" % (got.get("rev"), want.get("rev"))))
    return out


def red_line_has_detector(rule):
    """红线有没有"可执行的下一步"。G-NN / 具体测试名 / 明确写了人工或流程，都算。"""
    return bool(re.search(r"G-\d+", rule)) or ("tests/" in rule)         or (u"人工" in rule) or (u"流程" in rule)


def g09_red_lines(ctx):
    """G-09 红线：检查 rule.md 每条生效红线是否还挂着有效的检测器。

    违规本身由各条红线指向的闸门报（validate 会跑全部闸门，这里不重复跑，
    免得一条 G-13 开两次浏览器）。这条闸门防的是另一种事故：
    红线写在文档里但解析不到 / 指向一条已不存在的闸门——那是静默失效。
    """
    out = []
    known = {g.id for g in GATES}
    for rid, rule in active_red_lines():
        ids = re.findall(r"G-\d+", rule)
        if not ids:
            if red_line_has_detector(rule):
                continue
            out.append(Finding(g09_red_lines, "rule.md",
                               u"红线 %s 没有检测器，需人工确认：%s" % (rid, rule[:60]),
                               level="warn"))
            continue
        for gid in ids:
            if gid not in known:
                out.append(Finding(g09_red_lines, "rule.md",
                                   u"红线 %s 指向不存在的闸门 %s" % (rid, gid)))
    return out


def g10_schema(ctx):
    """G-10 schema 合法性：data.json 与大纲（specs/quality-gates）"""
    out = []
    schema_p = os.path.join(CONFIG, "topic_data.schema.json")
    if Draft202012Validator is None or not os.path.isfile(schema_p):
        return out
    schema = json.load(io.open(schema_p, encoding="utf-8"))
    v = Draft202012Validator(schema)
    errs = sorted(v.iter_errors(ctx.data), key=lambda e: list(e.path))
    for e in errs[:12]:
        where = "/".join(str(p) for p in e.path) or "(根)"
        out.append(Finding(g10_schema, "%s @ %s" % (ctx.rel_page, where), e.message[:200]))
    return out


def g12_index(ctx):
    """G-12 索引主页：每张卡片的封面真实存在、链接可达、类别非空（specs/golden-template）"""
    out = []
    idx = os.path.join(OUTPUT, "index.html")
    if not os.path.isdir(OUTPUT):
        return out
    if not os.path.isfile(idx):
        return [Finding(g12_index, "output/", u"缺少索引主页 index.html")]
    html = io.open(idx, encoding="utf-8").read()
    hrefs = re.findall(r'<a class="card" href="([^"]+)"', html)
    if not hrefs:
        return [Finding(g12_index, "output/index.html", u"索引里没有任何卡片链接")]
    for h in hrefs:
        target = os.path.normpath(os.path.join(OUTPUT, h.replace("/", os.sep)))
        if not os.path.isfile(target):
            out.append(Finding(g12_index, "output/index.html",
                               u"卡片链接指向不存在的页面：%s" % h))
    covers = re.findall(r'<a class="card"[^>]*>.*?<img src="([^"]+)"', html, re.S)
    for c in covers:
        if c.startswith("http"):
            out.append(Finding(g12_index, "output/index.html", u"索引封面用了远程图：%s" % c))
        elif not os.path.isfile(os.path.normpath(os.path.join(OUTPUT, c.replace("/", os.sep)))):
            out.append(Finding(g12_index, "output/index.html", u"索引封面图不存在：%s" % c))
    # 类别必须"看得见"且"跳得到"：chip 是可见性，锚点是跳转目标
    chips = [c for c in re.findall(r'<span class="cat-chip">([^<]*)</span>', html) if c.strip()]
    groups = re.findall(r'<a class="card"[^>]*\s+id="cat-([^"]+)"', html)
    groups = [g for g in groups if g.strip()]
    if not chips:
        out.append(Finding(g12_index, "output/index.html", u"索引卡片没有类别标签"))
    missing_anchor = [c for c in set(chips) if c not in groups]
    if missing_anchor:
        out.append(Finding(g12_index, "output/index.html",
                           u"类别 %s 有卡片但没有锚点，顶部标签点了没反应" % u"、".join(sorted(missing_anchor))))
    for g in groups:
        if not g.strip():
            out.append(Finding(g12_index, "output/index.html", u"存在空类别分组"))
    if u"未归类" in chips:
        out.append(Finding(g12_index, "output/index.html",
                           u"有专题页没配 category，落进了未归类"))
    return out


# 显式绑定编号，不按位置自动编号——加一条闸门不该让别的闸门悄悄改号。
# G-11 保留给跨领域配色闸门（_ThemeGate），它不接单领域 Ctx。
def g13_layout(ctx):
    """G-13 布局几何：真开浏览器量产物（specs/golden-template）"""
    out = []
    script = os.path.join(ROOT, "scripts", "measure-layout.mjs")
    if not os.path.isfile(script):
        return [Finding(g13_layout, ctx.rel_page, u"缺少 measure-layout.mjs，几何检查未执行", level="warn")]
    try:
        pr = subprocess.run(
            [os.environ.get("NODE", "node"), script, "--file", ctx.page_path, "--json"],
            cwd=ROOT, capture_output=True, timeout=300)
        res = json.loads(pr.stdout.decode("utf-8", "ignore").strip() or "{}")
    except Exception as e:
        return [Finding(g13_layout, ctx.rel_page, u"几何检查无法运行：%s" % e, level="warn")]
    if res.get("browserUnavailable"):
        return [Finding(g13_layout, ctx.rel_page,
                        u"浏览器不可用，布局未被验证（%s）——不得当作通过" % res.get("error"),
                        level="fail")]
    for q in res.get("problems", []):
        out.append(Finding(g13_layout, "%s %s" % (ctx.rel_page, q.get("tag", "")),
                           u"%s：%s" % (q.get("gate"), q.get("detail"))))
    return out


def g14_ledger(ctx):
    """G-14 发布账实相符：`web_list.md` 必须等于由各篇 `data.json.site` 重算出来的那份。

    为什么值得开一条闸门：一份东西活在几处迟早会不一致，这条项目已经付过两次学费
    （示意图的三处、封面声明）。派生物一旦允许手改，它就会在某个时刻说出一个
    并不存在的事实，而没人会去怀疑一张清单。
    还没有任何发布时**保持沉默**——"还没有账本"和"账本错了"是两件事，
    把前者判死只会让人去关闸门。
    """
    if not os.path.isdir(OUTPUT):
        return []
    try:
        import publish as PUB
    except ImportError:
        return []
    out = []
    for msg in PUB.check(root=ROOT, output=OUTPUT):
        out.append(Finding(g14_ledger, "web_list.md", msg))
    # 线上是旧版不是"错"，但它是**读者会被骗**的那种状态：本地已经改了，
    # 卡片上的"在线看"还指向上一版。报 warn，不拦发布。
    for x in PUB.pending(root=ROOT, output=OUTPUT):
        if x.get("stale"):
            out.append(Finding(g14_ledger, "output/%s" % x["topic"],
                               u"线上是旧版（本地指纹 %s ≠ 已发布 %s）——"
                               u"重发这一篇，或把卡片上的发布日改到读者看得懂"
                               % (x.get("sha"), x.get("url")), level="warn"))
    # W-153：主页是读者唯一会点进去的那个链接，而 `dist/home/` 是 gitignore 的
    # 中间产物，以前没有任何一处盯着它是否过期。warn——没构建是正常状态。
    for msg in PUB.check_home(root=ROOT, output=OUTPUT):
        out.append(Finding(g14_ledger, "dist/home/index.html", msg, level="warn"))
    return out


GATE_DEFS = [
    (g01_naming, "G-01", "specs/knowledge-page-generation/spec.md"),
    (g02_coverage, "G-02", "specs/topic-outline-config/spec.md"),
    (g03_images, "G-03", "specs/image-sourcing/spec.md"),
    (g04_selfcontained, "G-04", "specs/golden-template/spec.md"),
    (g05_words, "G-05", "specs/topic-outline-config/spec.md"),
    (g06_sourcing, "G-06", "specs/content-grounding/spec.md"),
    (g07_placeholders, "G-07", "specs/content-grounding/spec.md"),
    (g08_fingerprint, "G-08", "specs/golden-template/spec.md"),
    (g09_red_lines, "G-09", "specs/quality-gates/spec.md"),
    (g10_schema, "G-10", "specs/quality-gates/spec.md"),
    (g12_index, "G-12", "specs/golden-template/spec.md", "global"),
    (g14_ledger, "G-14", "specs/golden-template/spec.md", "global"),
    (g13_layout, "G-13", "specs/golden-template/spec.md"),
]

GATES = []
for _def in GATE_DEFS:
    _fn, _gid, _spec = _def[0], _def[1], _def[2]
    _scope = _def[3] if len(_def) > 3 else "domain"
    _fn.id = _gid
    _fn.title = (_fn.__doc__ or "").split("：")[0].strip()
    GATES.append(Gate(_gid, _fn.title, _spec, _fn, _scope))

DOMAIN_GATES = [g for g in GATES if g.scope == "domain"]


# ---------------------------------------------------------------- 驱动

def build_ctx(topic, output_dir=None, page=None):
    """定位某个领域的产物并读出校验上下文。

    `page` 是给换名协议用的：新页先落在 `<领域>.html.pending`，闸门要在它**还没成为
    已发布页**的时候判它。不传就是判已发布的那一份。
    """
    out_dir = os.path.join(output_dir or OUTPUT, topic)
    if page is None:
        pages = published_pages(out_dir)
        if not pages:
            return None, [Finding(g01_naming, "output/%s" % topic, u"没有找到产物页面")]
        page = os.path.join(out_dir, pages[-1])
    data_p = os.path.join(out_dir, "data.json")
    if not os.path.isfile(data_p):
        return None, [Finding(g10_schema, "output/%s" % topic, u"缺少 data.json，无法校验内容层")]
    html = io.open(page, encoding="utf-8").read()
    data = json.load(io.open(data_p, encoding="utf-8"))
    return Ctx(topic, out_dir, page, html, data, _bar()), []


def run(gate_filter=None, domains=None, skip=(), output_dir=None, page=None):
    """跑闸门。`skip` 按闸门 id 排除（索引重建只要 G-01…G-12，
    G-13 要开真浏览器量七档视口，不值得为每个领域再等一遍——
    几何由 generate 的 verify 阶段拦，两处判据仍是同一个 run()）。
    `output_dir` 让调用方指到自己那套产物目录（测试与 --output 用）。
    `page` 只对单领域校验有效：换名协议要在候选页还是 `.pending` 时判它。
    """
    root = output_dir or OUTPUT
    bar = _bar()
    findings = []
    if domains is None:
        domains = sorted(
            d for d in os.listdir(root)
            if os.path.isdir(os.path.join(root, d))
        ) if os.path.isdir(root) else []
    checked = 0
    # `page` 只在单领域时有意义：换名协议要判的那个候选页，目录里还没有它的正式名。
    one_page = page if (domains and len(domains) == 1) else None
    for topic in domains:
        ctx, pre = build_ctx(topic, root, page=one_page)
        findings.extend(pre)
        if ctx is None:
            continue
        checked += 1
        for fn in DOMAIN_GATES:
            if gate_filter and fn.id != gate_filter:
                continue
            if fn.id in (skip or ()):
                continue
            try:
                findings.extend(fn.check(ctx) or [])
            except Exception as e:  # 闸门自身出错必须报，不能吞
                findings.append(Finding(fn, ctx.rel_page, u"闸门异常：%s" % e))

    # 全站级闸门只在"没有指定单一领域"时跑：单领域校验时索引可能还没建，
    # 把 G-11/G-12 拉进来会让第一次生成永远过不了、索引也就永远建不起来。
    whole_site = len(domains or []) != 1 or gate_filter in ("G-11", "G-12", "G-14")
    if whole_site:
        if not gate_filter or gate_filter == "G-11":
            findings.extend(_cross_domain_theme(bar))
        if not gate_filter or gate_filter == "G-12":
            findings.extend(g12_index(None))
        if not gate_filter or gate_filter == "G-14":
            findings.extend(g14_ledger(None))
        # 索引页是全站入口，它跑版没人发现——G-13 也要量它，不只是各专题页。
        if not gate_filter or gate_filter == "G-13":
            idx = os.path.join(OUTPUT, "index.html")
            if os.path.isfile(idx):
                ictx = Ctx(u"索引", OUTPUT, idx, "", {"sections": [], "sources": []}, bar)
                findings.extend(g13_layout(ictx) or [])

    return findings, checked, domains


def _cross_domain_theme(bar):
    """G-11 跨领域配色不得雷同（specs/golden-template；memo D-03）

    判据只看**身份色**（primary + accent），而且要求两个都近才算雷同：
    * 不看底色——底色是可读性约束，两套完全不同的主题共用一个纸白底是应该的。
      把 bg 平均进距离实测 42/55 对全灭（两片米白底之间 ΔE 只有 1.7），
      一个 90% 时间在响的闸门等于没有闸门：52 条真 G-03 fail 就被埋在里面。
    * 不用均值——一个极端色会替另一个蒙混过关。实测 劳斯莱斯 vs 积家
      primary ΔE 61.5 / accent ΔE 12.3，用均值就漏掉"两种几乎一样的金"。
    阈值来自真色板分布（不是先定数再找理由）：ΔE≈25 在 CIE76 下是
    "同一色系、只换了色调"，读者会把两页认成同一个牌子。
    """
    out = []
    limit = bar["theme"]["min_palette_distance"]
    dirs = sorted(
        d for d in os.listdir(OUTPUT)
        if os.path.isdir(os.path.join(OUTPUT, d)) and palette_of(d)
    ) if os.path.isdir(OUTPUT) else []
    sigs = {d: palette_of(d) for d in dirs}
    for d in dirs:
        _, prim, acc = sigs[d]
        if not prim or not acc:
            out.append(Finding(_theme_gate, d,
                               u"取不到身份色（primary=%s accent=%s），"
                               u"配色雷同这一项对它是空转" % (prim, acc)))
    for i in range(len(dirs)):
        for j in range(i + 1, len(dirs)):
            a, b = sigs[dirs[i]], sigs[dirs[j]]
            if not (a[1] and a[2] and b[1] and b[2]):
                continue        # 上面已经单独报过，不在这里重复
            pr = delta_e(a[1], b[1])
            ac = delta_e(a[2], b[2])
            if max(pr, ac) < limit:
                out.append(Finding(_theme_gate, "%s vs %s" % (dirs[i], dirs[j]),
                                   u"配色过于雷同（身份色 ΔE primary %.1f、accent %.1f，"
                                   u"两个都没拉开到 %.0f 以上）" % (pr, ac, limit)))
    return out


class _ThemeGate(object):
    id = "G-11"
    title = u"跨领域配色差异"
    spec_ref = "specs/golden-template/spec.md"
    check = staticmethod(lambda ctx: [])


_theme_gate = _ThemeGate


def main(argv=None):
    ap = argparse.ArgumentParser(description=u"知识专题页质量闸门（唯一裁判）")
    ap.add_argument("--all", action="store_true", help=u"扫描 output/ 下全部领域")
    ap.add_argument("--domain", help=u"只校验一个领域")
    ap.add_argument("--page", help=u"校验指定那一个页面文件（换名协议要在候选页还是 "
                                  u"`.pending` 时判它）；只在配 `--domain` 时有意义")
    ap.add_argument("--gate", help=u"只跑一条闸门，例如 G-05")
    ap.add_argument("--list", action="store_true", help=u"列出全部闸门")
    ap.add_argument("--json", action="store_true", help=u"以 JSON 输出结果")
    ap.add_argument("--warn-as-error", action="store_true")
    args = ap.parse_args(argv)

    if args.list:
        for fn in GATES:
            print("%s  %-14s  %s" % (fn.id, fn.title, fn.spec_ref))
        print("%s  %-14s  %s" % ("G-11", u"跨领域配色差异", "specs/golden-template/spec.md"))
        return 0

    known = {fn.id for fn in GATES} | {"G-11"}
    if args.gate and args.gate not in known:
        sys.stderr.write(u"未知闸门 %s，可用：%s\n" % (args.gate, ", ".join(sorted(known))))
        return 2

    findings, checked, domains = run(
        gate_filter=args.gate,
        domains=[args.domain] if args.domain else None,
        page=args.page,
    )
    fails = [f for f in findings if f.level == "fail"]
    warns = [f for f in findings if f.level != "fail"]

    if args.json:
        print(json.dumps({
            "checked": checked, "domains": domains,
            "fail": [str(f) for f in fails], "warn": [str(f) for f in warns],
            "gates": {f.id: f.spec_ref for f in GATES},
        }, ensure_ascii=False, indent=1))
    else:
        for f in fails:
            print(u"FAIL " + str(f))
        for f in warns:
            print(u"WARN " + str(f))
        print(u"—" * 60)
        print(u"%d 个领域，%d fail / %d warn（生效红线 %d 条）"
              % (checked, len(fails), len(warns), len(active_red_lines())))
        if not fails:
            print(u"质量闸门通过")

    if fails or (args.warn_as_error and warns):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
