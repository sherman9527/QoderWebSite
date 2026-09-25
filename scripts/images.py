# -*- coding: utf-8 -*-
"""配图：检索 → 下载 → 校验 → 去重 → 落盘 → manifest。

环境事实（见 memo.md）：本网络只有 cn.bing.com/images/async 可达，Wikimedia /
DuckDuckGo / Baidu 图搜全部不可用，所以这里不写多源抽象层，就一个源 + 严格校验。

⚠️ 两条踩过的坑，都写进了闸门：
  1. Bing 缩略图端点会返回 404 却给出合法 JPEG 字节 —— 判成败必须看字节，不能看状态码。
  2. 中文短词会混进素材站插画（实测"咖啡 意式浓缩"返回 58pic / 千图 的设计素材）——
     所以有域名黑名单与相关性打分，而不是"取第一条"。
"""
import hashlib
import html as html_mod
import io
import json
import os
import re
import ssl
import struct
import urllib.error
import urllib.parse
import urllib.request

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")
BING_ASYNC = "https://cn.bing.com/images/async"
_CTX = ssl.create_default_context()  # 保持证书与主机名校验：实测 bing 与其图床均验证通过

# 素材/壁纸/图标站：画的是"概念插画"，不是这个领域里真实存在的东西。
STOCK_DOMAINS = (
    # 这类站只有一个域名、换后缀还是同一个站，所以条目一律写"去掉 TLD 的词干"：
    # 实测 nipic.com 在黑名单里，同一张图从 www.nipic.cn 就漏过去了。
    "58pic", "qiantu", "千图", "tupian", "ibaotu", "tubaicdn",
    "818ps", "tuguaishou", "设计素材", "nipic", "huitu", "veer",
    "zhengtu", "tooopen", "suc6", "findmd", "wallpaper", "壁材", "sohuimg",
    "upaiimages", "laotu", "7140图片", "picmix", "iconfont", "flaticon",
    "pixabay",
    "brainmed", "dxy.cn", "yiigle", "medlive", "a-ai6", "39hospital",
)
# 教学图解 / 解剖图 / 矢量示意图：分辨率再高也不是"这个领域里真实存在的东西"。
DIAGRAM_HINTS = (
    u"图解", u"示意图", u"解剖", u"结构图", u"原理图", u"流程图", u"思维导图", u"课件",
    u"矢量", u"插画", u"图标", u"素材", u"模板", u"png免抠", u"抠图",
    "diagram", "schematic", "anatomy", "anterior horn", "dorsal root",
    "vector", "illustration", "icon", "clipart", "infographic", "flowchart",
)
# 红线 R-04：品牌 logo、桌面壁纸、广告大片、海报——分辨率再高也不告诉读者任何事，
# 而且是最典型的版权雷区。只看标题，不看 URL，免得把正常页面误杀。
DECOR_HINTS = (
    u"logo", u"壁纸", u"海报", u"广告", u"宣传", u"大片", u"裱框", u"装饰画",
    "wallpaper", "poster", "key visual", "ad campaign", "backdrop", "sticker",
)
IUSC_RE = re.compile(r'class="iusc"[^>]*\bm="([^"]+)"')

# 实测抓到的"图片不可用"占位图：它是合法 JPEG、800×600、8.7KB，
# 格式/尺寸/体积三道检查全过，唯一露馅的是信息密度（见 accept_image 的 B/px 下限）。
# 命中哈希直接拒，密度兜底防没见过的占位图变体。
PLACEHOLDER_SHA256 = {
    "74daaa107f00212b862de223895f7a22a4e3bfe64c17688aeb8dc9a9169b8b2c",  # tests/fixtures/placeholder_bing.jpg
}


class Candidate(object):
    def __init__(self, murl=None, turl=None, purl=None, title=None):
        self.murl = murl
        self.turl = turl
        self.purl = purl
        self.title = title or ""

    def as_dict(self):
        return {"murl": self.murl, "turl": self.turl, "purl": self.purl, "title": self.title}

    def __repr__(self):
        return "<Candidate %s>" % (self.murl or self.turl)


# ---------------------------------------------------------------- 解析

def parse_bing(html_text):
    """从 Bing 异步结果页解析候选。返回按页面顺序的 Candidate 列表。"""
    out = []
    for m in IUSC_RE.finditer(html_text or ""):
        raw = html_mod.unescape(m.group(1))
        try:
            d = json.loads(raw)
        except ValueError:
            continue
        if not (d.get("murl") or d.get("turl")):
            continue
        out.append(Candidate(
            murl=d.get("murl"), turl=d.get("turl"),
            purl=d.get("purl"), title=d.get("t"),
        ))
    return out


def search_url(query, count=20):
    return BING_ASYNC + "?" + urllib.parse.urlencode({
        "q": query, "first": 0, "count": count,
        "qft": "filterui:imagesize-large", "form": "IRFLTR",
    })


def search(query, count=20, timeout=25, opener=None):
    op = opener or _urlopen
    html_text = op(search_url(query, count), timeout=timeout)
    return parse_bing(html_text)


def _urlopen(url, timeout=25, headers=None):
    req = urllib.request.Request(url, headers=_hdr(headers))
    with urllib.request.urlopen(req, timeout=timeout, context=_CTX) as r:
        return r.read().decode("utf-8", "ignore")


def _hdr(extra=None):
    h = {"User-Agent": UA, "Accept-Language": "zh-CN,zh;q=0.9",
         "Referer": "https://cn.bing.com/"}
    h.update(extra or {})
    return h


# ---------------------------------------------------------------- 字节校验

MAGIC = [(b"\xff\xd8\xff", "jpg"), (b"\x89PNG\r\n\x1a\n", "png"),
         (b"GIF87a", "gif"), (b"GIF89a", "gif"), (b"RIFF", "webp")]


def sniff(data):
    """返回格式或 None。判成败的唯一依据是字节，不是 HTTP 状态码。"""
    if not data or len(data) < 16:
        return None
    for magic, fmt in MAGIC:
        if data.startswith(magic):
            if fmt == "webp" and data[8:12] != b"WEBP":
                return None
            return fmt
    head = data[:512].lower()
    if b"<!doctype html" in head or b"<html" in head:
        return None
    return None


def dimensions(data, fmt):
    """读图片宽高，只用标准库。返回 (w, h) 或 (None, None)。"""
    try:
        if fmt == "png":
            w, h = struct.unpack(">II", data[16:24])
            return int(w), int(h)
        if fmt == "gif":
            w, h = struct.unpack("<HH", data[6:10])
            return int(w), int(h)
        if fmt == "webp":
            tag = data[12:16]
            if tag == b"VP8X":
                w = int.from_bytes(data[24:27], "little") + 1
                h = int.from_bytes(data[27:30], "little") + 1
                return w, h
            if tag == b"VP8L":
                bits = struct.unpack("<I", data[21:25])[0]
                return (bits & 0x3FFF) + 1, ((bits >> 14) & 0x3FFF) + 1
            if tag == b"VP8 ":
                w, h = struct.unpack("<HH", data[26:30])
                return w & 0x3FFF, h & 0x3FFF
            return None, None
        if fmt == "jpg":
            i = 2
            n = len(data)
            while i < n - 9:
                if data[i] != 0xFF:
                    i += 1
                    continue
                marker = data[i + 1]
                if marker in (0xD8, 0x01) or 0xD0 <= marker <= 0xD7:
                    i += 2
                    continue
                if 0xC0 <= marker <= 0xCF and marker not in (0xC4, 0xC8, 0xCC):
                    h, w = struct.unpack(">HH", data[i + 5:i + 9])
                    return int(w), int(h)
                seg = struct.unpack(">H", data[i + 2:i + 4])[0]
                i += 2 + seg
            return None, None
    except (struct.error, IndexError, ValueError):
        pass
    return None, None


def accept_image(data, bar):
    """按质量线判定一张图。返回 (ok, fmt, w, h, reason)。"""
    fmt = sniff(data)
    if not fmt:
        return False, None, None, None, "返回的不是图片（可能是反爬占位页）"
    w, h = dimensions(data, fmt)
    if w and w < bar["min_width"]:
        return False, fmt, w, h, "宽度 %s < %s" % (w, bar["min_width"])
    if len(data) < bar["min_bytes"]:
        return False, fmt, w, h, "体积 %d < %d" % (len(data), bar["min_bytes"])
    if w is None and len(data) < bar["preferred_bytes"]:
        return False, fmt, None, None, "读不到尺寸且体积偏小"
    if _sha(data) in PLACEHOLDER_SHA256:
        return False, fmt, w, h, "已知占位图（图片不可用提示图）"
    if w and h:
        bpp = len(data) / float(w * h)
        floor = bar.get("min_bytes_per_pixel", 0.03)
        if bpp < floor:
            return False, fmt, w, h, (
                "信息密度过低 %.3f B/px < %.2f，疑似占位图或过度压缩" % (bpp, floor))
    return True, fmt, w, h, ""


def download(url, timeout=25, opener=None):
    """下载原始字节。opener(url)->bytes 可注入，便于测试。

    注意：状态码异常时也要看返回体——Bing 缩略图会 404 但给真图。
    """
    if not url:
        return None
    op = opener or _urlopen_bytes
    try:
        return op(url, timeout=timeout)
    except Exception:
        return None


def _urlopen_bytes(url, timeout=25):
    """取字节。HTTP 错误也尽量把响应体带回来——Bing 缩略图会 404 却返回真图，
    成败交给 sniff() 按字节判断，不在这里按状态码下结论。"""
    req = urllib.request.Request(url, headers=_hdr())
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=_CTX) as r:
            return r.read()
    except urllib.error.HTTPError as e:
        try:
            return e.read()
        except Exception:
            return None


# ---------------------------------------------------------------- 打分

TOKEN_SPLIT = r"[\s,，、/|（）()【】\[\]：:；;]+"

# 领域名内部再按"拉丁串 / 非拉丁串"分块。`Muse产业逻辑` 这类短语领域名整体
# 在图搜里搜不动，但它两半都是能搜的名字。
NAME_PARTS = re.compile(u"[A-Za-z0-9]+|[^\x00-\x7f]+")

# 放弃"必须点名领域"那一档的关键词下限。判据是实测分布，不是猜的：
# 已采用的 134 张里，没点名主语的 13 张命中数全部 ≤1
# （"中华万年历 app 下载"、"圆角和倒角-CSDN"、"无人机保养10大技巧"、"重型工作台"），
# 而点名主语的 121 张里有 37 张只命中 1 个词——所以这条线只能画在放宽档。
RELAXED_MIN_HITS = 2
# 降粒度重试时的英文虚词表：它们不携带任何检索信号，每次却是一个 HTTP 往返
# 加一轮下载（09-22 实测："You"、"Need" 各自搜出一页电影海报与语录站）。
# 只收虚词，不收领域名词——GPU、芯片、机芯这类必须留下。
STOP_TOKENS = {"a", "an", "the", "and", "or", "of", "to", "in", "on", "at", "by",
               "for", "with", "is", "are", "was", "were", "be", "been",
               "you", "your", "it", "its", "this", "that", "these", "those",
               "all", "any", "one", "two", "new", "vs", "how", "what", "why",
               "need", "make", "makes", "get", "got", "de", "la", "le", "les"}

# 不当主语名的短 ASCII 缩写。**只收实测撞到的，不靠想象扩充**——
# 与 STOP_TOKENS 是两张表、两条判据：那张管"拆检索词时哪些虚词不该单独成词"，
# 明确保留 GPU/芯片这类领域名词；这张管"哪些词即使整词命中也不能算领域自己的名字"。
# 判据：它是通用技术缩写，不是任何一个具体领域的品牌。
# 09-25 实测来源：AI制药 裸 `ai`（命中"AI创作图…壁纸"与"…-ai格式-千图网"）、
# AI眼镜 `ai/ar1/jbd`、大模型 `tpu/glm`、Muse `kvm/asn/nat/amd/arm/aws`。
# `llm`/`gpt` 故意不收——对大模型篇它们确实是主语名，收了就是把闸门焊死。
SUBJECT_STOP = {"ai", "ar1", "jbd", "tpu", "glm", "kvm", "asn", "nat",
                "amd", "arm", "aws"}


def subject_tokens(cfg, min_chapters=3):
    """这个领域"自己的名字"，顺序有意义：第 0 个能搜的词就是品牌词。

    领域名自己没人拿去搜过时，换成"本大纲检索词里覆盖章数最多"的那个词。
    判据是免费的：人写 `image_queries` 就是在赌「这个物体在图片里会出现」，
    一条都没写过裸 `muse` 的 11 章，说明 muse 不是这篇的搜索词——
    而它恰好是英国乐队与一家同名手术机器人的名字。
    **只在领域名零覆盖时才换**，所以已经上架的 13 篇行为一个字都不变。
    """
    out = _subject_tokens(cfg, min_chapters=min_chapters)
    declared = str(getattr(cfg, "image_primary_subject", "") or "").strip().lower()
    if declared in out:
        # 只挪位置，不新增词：新增等于给点名闸门开后门，让任意图进门。
        out.remove(declared)
        out.insert(0, declared)
        return out
    cov = {t: _coverage(cfg, t) for t in out}
    head = primary_subject(out)
    if not head or cov.get(head):
        return out
    ranked = sorted((t for t in out if searchable(t) and cov[t]),
                    key=lambda t: (-cov[t], out.index(t)))
    if ranked:
        out.remove(ranked[0])
        out.insert(0, ranked[0])
    return out


def _coverage(cfg, tok):
    """这个词出现在本大纲多少章的检索词里。"""
    n = 0
    for sec in getattr(cfg, "sections", None) or []:
        text = u" ".join(str(q) for q in (sec.image_queries or [])).lower()
        if names_subject(text, [tok]):
            n += 1
    return n


def _subject_tokens(cfg, min_chapters=3):
    """主语集合的原始顺序：领域名 → 声明的 aliases → 检索词里反复出现的拉丁词。

    香奈儿篇的检索词写的是 "Coco Chanel 肖像 历史"、"Karl Lagerfeld 香奈儿 秀场"，
    所以 Chanel 会在 ≥3 章里出现，而 2.55、reissue、vintage 这类只出现一次——
    它们是章节词，不是主语。只要主语，不要章节词，才能既放行
    "CHANEL 带着女士城堡穿越到上海"又拦下"欧洲三大半岛是哪些"。
    拉丁词还要卡 len>=4：LV 篇里 "lv" 这种两字母串当子串会误配一大片。

    推导只能收到"露过面"的名字：劳力士的 rolex、爱马仕的 hermes 各只在 2 章检索词里
    出现，收不进来；把 min_chapters 降到 2 又会把咖啡篇的"巴拿马"当主语。
    所以品牌名由 config/topics/*.json 的 aliases 声明——那是领域数据，不是代码。

    最后一道是 SUBJECT_STOP：两三个字母的 ASCII 缩写一律不当主语名。
    names_subject 对短词用的是"整词"匹配，而那个边界只挡拉丁字母与数字、**不挡中文**，
    所以 `ai` 会命中 "AI创作图…壁纸" 与 "…-ai格式-千图网"。09-25 实测四个领域
    都中招（AI制药 裸 `ai`、AI眼镜 `ai/ar1/jbd`、大模型 `llm/gpt/tpu/glm`、
    Muse `kvm/asn/nat/amd/arm/aws`）——后两组明显是从 fact_prompts 混进
    aliases 的基础设施缩写，是章节词不是主语。
    """
    out = []

    def add(tok):
        tok = str(tok or "").strip().lower()
        if len(tok) < 2 or tok in out:
            return
        if len(tok) < 4 and tok.isascii() and tok in SUBJECT_STOP:
            return
        out.append(tok)

    for tok in re.split(TOKEN_SPLIT, str(cfg.topic or "")):
        for part in re.findall(NAME_PARTS, tok) or [tok]:
            add(part)
    for alias in getattr(cfg, "aliases", None) or []:
        add(alias)
    per_chapter = {}
    for sec in cfg.sections:
        seen = set()
        for q in sec.image_queries or []:
            for tok in re.split(TOKEN_SPLIT, str(q)):
                t = tok.lower()
                if len(t) >= 4 and t.isascii() and t.isalpha():
                    seen.add(t)
        for t in seen:
            per_chapter[t] = per_chapter.get(t, 0) + 1
    for t, n in sorted(per_chapter.items()):
        if n >= min_chapters:
            add(t)
    return out


def names_subject(text, subject):
    """候选是否点名了领域。短的纯 ASCII 主语（"LV"）按**整词**匹配，
    其余按子串匹配。

    两字母缩写不能当子串——"lv" 是 involve / resolve 的一部分，那样等于
    什么图都算点名。但也不能干脆不要：中文图片标题里 LV 篇最常见的写法
    就是 "LV Monogram 手袋"，只认 "路易威登/vuitton" 会把真图全判跑题，
    LV 篇 22 张重做成 1 张就有这一份。整词匹配同时避开这两个坑。"""
    for tok in subject or ():
        if len(tok) < 4 and tok.isascii():
            if re.search(r"(?<![a-z0-9])%s(?![a-z0-9])" % re.escape(tok), text):
                return True
        elif tok in text:
            return True
    return False


def searchable(tok):
    """这个词拿去拼查询有没有意义：够长，或含中文。
    拿 "lv" 去拼查询召不回中文页，但 "lv" 仍是合法的主语匹配词（整词匹配）。
    拼查询与匹配图片是两件事，各自有唯一归属，别互相借用。"""
    return bool(tok) and (len(tok) >= 4 or not tok.isascii())


def primary_subject(subject):
    """主语集合里适合拿去拼检索词的那一个（顺序由 subject_tokens 定）。"""
    return next((s for s in (subject or ()) if searchable(s)), None)


def brand_phrase(queries, subject, already=()):
    """这一章**自己的**两词短语（点名主语的那一对）。
    本篇 19 张图里，裸词档带回来的 10 张有 5 张是看联络表摘掉的（字标、优惠入口、
    钢板网广告），章节原词 16 张只摘掉 3 张——裸词跑题率是章节词的 3 倍。
    所以"这一章的词召不到图"时，先把它自己的两词短语再问一遍（`中际旭创 光模块 参数 对比`
    → `中际旭创 光模块`），而不是退到一个与这一章无关的全领域裸词上。
    两词是实测的甜点位：三词以上召回崩塌，单词精度撑不住。"""
    tried = {str(q or "").strip().lower() for q in already or ()}
    for q in queries or ():
        toks = [t for t in re.split(TOKEN_SPLIT, str(q or "")) if t]
        for a, b in zip(toks, toks[1:]):
            cand = u"%s %s" % (a, b)
            low = cand.lower()
            if low in tried:
                continue
            if names_subject(low, subject):
                return low
    return None


def ensure_subject(text, subject):
    """让一条检索词点名领域本身。唯一归属：查询构造和降粒度重试都要用它，
    两边各写一遍迟早又会打架（主语闸门要求点名、降粒度偏发裸词，
    结果是每一章都只能靠放宽档出图）。

    但只在补完仍 ≤3 个词时才补。Bing CN 的召回随词数崩塌：实测
    "LV Monogram"→35 条、"路易威登 手袋"→35 条，
    而 "路易威登 LV Monogram 花纹 细节"→1 条（还是印尼工程机械壁纸）。
    LV 篇 22 张图被重做成 1 张、10 章空掉，就是把每条检索词都拼长了 1 个词。
    本来就长的检索词不拼，交给降粒度那条路去召回。"""
    t = str(text or "").strip()
    if not subject or any(s in t.lower() for s in subject):
        return t
    if len(t.split()) >= 3:
        return t
    primary = primary_subject(subject)
    if not primary:
        return t
    return u"%s %s" % (primary, t)


def gated_queries(queries, subject):
    """点名档要用的检索词集合——"能不能点名主语"这件事的唯一归属。

    一条词要么本身点名领域，要么短到能被 `ensure_subject` 补上主语。
    两条都不满足的词在点名档等于不存在：实测 315 条大纲检索词里有 124 条这样，
    于是这些章只能落到放宽档，配回"中华万年历 app 下载""重型工作台"那种垃圾。
    对这种词补一条「品牌 + 前两个词」的短兄弟（不是替换——原词在放宽档还有用）。
    为什么不直接把长词硬拼上主语：Bing CN 的召回随词数崩塌（5 词实测只回 1 条）。
    """
    primary = primary_subject(subject)
    out = []

    def add(q):
        if q and q not in out:
            out.append(q)

    for q in queries or ():
        # 先走 ensure_subject：短词补上主语就能用（它自己会守住"补完 ≤3 词"）
        add(ensure_subject(str(q or "").strip(), subject))
        q = str(q or "").strip()
        low = q.lower()
        if not primary or len(q.split()) <= 2:
            continue
        if any(t in low for t in (subject or ())):
            continue
        add(u"%s %s" % (primary, u" ".join(q.split()[:2])))
    return [q for q in out if q]


def _query_tokens(keywords):
    """把 keywords（含整串检索词与章节标题）切成可匹配的短词。

    整串当子串比对必然 0 命中，于是 hit==0 会把绝大多数真图判成无关。
    冒号/分号也要切：章节标题形如"品牌史：从康朋街女帽店到战后重生"，
    不切就是一个 15 字的整串，永远命中不了。
    """
    tokens = []
    for k in keywords or ():
        for tok in re.split(TOKEN_SPLIT, str(k or "")):
            if len(tok) >= 2 and tok not in tokens:
                tokens.append(tok)
    return tokens


def text_hits(text, keywords):
    """一段文本（标题/图注/来源页拼出来的）撞上了几个检索词。"""
    low = (text or u"").lower()
    return sum(1 for tok in _query_tokens(keywords) if tok in text or tok.lower() in low)


def _hit_count(cand, keywords):
    text = (cand.title or "") + " " + (cand.purl or "") + " " + (cand.murl or "")
    return text_hits(text, keywords)


def reject_reason(cand, keywords, subject=(), min_hits=1):
    """只要标题与 URL 就能判掉的否决项，返回原因字符串；None 表示"得下载了才知道"。

    拆出来的理由很实际：`score()` 里所有 -999 都不看像素（尺寸与体积只参与加分），
    而 collect 原先是**先下载几 MB 再打分**。坏窗口里一章 30 条候选有 28 条
    死在这几条否决上，于是 09-23 娇兰篇的配图阶段跑了 4 小时只拿到 2 张图。
    先问一句再下载，判据一字未改，省掉的是整轮白 fetch。
    """
    text = (cand.title or "") + " " + (cand.purl or "") + " " + (cand.murl or "")
    low = text.lower()
    if any(d in low for d in STOCK_DOMAINS):
        # 素材站给的是"概念插画"，不是这个领域里真实存在的东西。
        # 高分辨率救不了它，所以直接否掉而不是扣分。
        return u"素材站"
    low_title = (cand.title or "").lower()
    if any(d in low_title or d in (cand.purl or "").lower() for d in DIAGRAM_HINTS):
        return u"示意图/图纸页"
    if any(d in low_title for d in DECOR_HINTS):
        return u"装修装饰页"
    # 命中不够就不是"这张图稍微偏一点"，而是根本不知道它是什么，直接不要。
    # 默认 1：点名主语那一档另有 `subject` 把关，要求两个词会误杀真图
    # （实测"正确解读咖啡的各种好处"只剩 3/12、"CHANEL 带着女士城堡…"只剩 1/22）。
    # 放弃主语要求那一档由调用方传 RELAXED_MIN_HITS 把线抬回来——
    # 13 张跑题图全部命中 ≤1，而 121 张真图里有 37 张命中 1，两档判据不冲突。
    if _hit_count(cand, keywords) < min_hits:
        return u"关键词命中不足"
    # 命中了检索词却没提领域本身 → 讲的是同一个词的另一件事。
    # 判据来自 34 张真产物配图：跑题的那 15 张，没有一张提到"咖啡/香奈儿/Chanel"。
    if subject and not names_subject(low, subject):
        return u"没点名领域"
    return None


def score(cand, w, h, nbytes, keywords, subject=(), min_hits=1):
    """候选打分。低于 0 不采用。

    subject: 领域自己的名字（见 reject_reason）。不要求它命中，实测就会让
    "巴拿马展园""也门铁修剪""中国行政区划"进咖啡篇——它们全都只是复述了
    检索词里那个既是产区又是地名的通用词。
    """
    if reject_reason(cand, keywords, subject=subject, min_hits=min_hits) is not None:
        return -999
    s = 0
    # 尺寸优先：封面要铺到 1536px，原图不够大就是糊图。同等相关度下永远选大的。
    if w and w >= 1600:
        s += 6
    elif w and w >= 1150:
        s += 4
    elif w and w >= 800:
        s += 3
    elif w and w >= 640:
        s += 2
    if nbytes >= 200 * 1024:
        s += 3
    elif nbytes >= 80 * 1024:
        s += 2
    elif nbytes >= 40 * 1024:
        s += 1
    s += min(3, _hit_count(cand, keywords))
    if not cand.purl:
        s -= 2
    return s


def _slug(text, fallback):
    out = re.sub(r"[^0-9A-Za-z一-鿿]+", "_", (text or "").strip())
    return out.strip("_")[:28] or fallback


# ---------------------------------------------------------------- 主流程

def page_excluded(page, exclude_pages):
    """人眼结论落成数据的唯一形状：**按来源页 URL 前缀排除**。

    为什么不用关键词：09-23 摘掉的那三张错图（MUSE 手术机器人的会议照、Meta 字标、
    爱马仕橙色 logo 面板）标题里都带着品牌词、没有一个是「logo/广告」词——
    D-17 量过按关键词否决要赔 27 张好图。前缀匹配不猜语义，误杀面是零；
    写成前缀而不是整条 URL，是因为一个只发宣传图的站，它每一页都是宣传图。
    """
    if not page or not exclude_pages:
        return False
    p = page.split("#")[0]
    return any(p.startswith(str(e).strip()) for e in exclude_pages
               if str(e or "").strip())


def collect(queries, dest_dir, bar, keywords=None, count=20, max_per_query=2,
            log=None, opener=None, downloader=None, claimed=None, subject=(),
            min_hits=1, stats=None, max_per_source_page=None, used_pages=None,
            exclude_pages=None):
    """按检索词取图，落到 dest_dir/images/，返回 manifest 条目列表。

    queries: [str]；keywords: 相关性判据（通常是章节标题与领域名）。
    claimed: 已被其它章节认领的 "images/xxx" 集合——同一张图不能发给两章。
    subject: 领域自己的名字（见 score）。这一章实在找不到提到主语的图时，
             调用方可以不带 subject 再要一轮——G-03 要求每章都有图，
             宁可退一步也不能让整章空着。
    max_per_source_page / used_pages: 同一个来源页最多给几章用、已经给了几张。
           09-23 全站点联络表抽查：浪琴有 5 章的图来自同一个购表作业相册页，
           爱马仕 4 章、LV 3 章同源。同一页翻出来的照片机位、风格、水印都一样，
           读者连着看到就是"这图怎么又出现一次"。判据按来源页 URL 数，
           不用感知哈希——8×8 aHash 会把两张不同的黑白人像也算成重复，那种阈值不配当规则。
    stats: 传一个 dict 就按**大纲原词**记 {"offered": 召回条数, "named": 其中点名的条数}。
           降粒度重试的变体（裸词、补主语）算进原词那一格，取各轮最大值。
           这份统计存在的理由只有一个：空章有两种成因，处置完全相反——
           offered>0 且 named==0 是**引擎答非所问**（09-22 实测：`积家 腕表 专柜`
           召回 34 条全是「积」字的字典笔顺页），换个时间重试就好；
           有点名却拿不到图才是供给问题。混在一起就会去砍花过额度的章节（W-98）。
    """
    # seen_hash 存的是文件名（不带 images/ 前缀），认领集合也归一到同一形态
    claimed = {os.path.basename(f) for f in (claimed or ())}
    log = log or (lambda *a: None)
    keywords = list(keywords or [])
    images_dir = os.path.join(dest_dir, "images")
    if not os.path.isdir(images_dir):
        os.makedirs(images_dir)
    seen_hash = {}
    for fn in os.listdir(images_dir):
        p = os.path.join(images_dir, fn)
        if fn.lower().endswith((".jpg", ".jpeg", ".png", ".gif", ".webp")):
            seen_hash.setdefault(_sha(open(p, "rb").read()), fn)

    taken = []
    idx = len(seen_hash) + sum(1 for f in os.listdir(images_dir) if f.startswith(tuple("0123456789")))
    # 编号是"算"出来的（计数 + 数字前缀文件数），不是"已有最大值 +1"。
    # 重做几轮之后编号会漂高并留空洞，于是算出来的名字可以正好等于一个已存在的文件，
    # 而下面是 open(...,"wb")——会把那张图原地盖掉。被盖的很可能正被已落盘的
    # data.json 指着，且 `_rollback_images` 只在文件不存在时才从快照恢复，
    # 所以它永远不会被写回来。09-22 code review 实测复现过。
    used_names = set(os.listdir(images_dir))
    dl = downloader or download
    emitted = set()
    tried = set()
    roots = {}          # 变体词 -> 大纲原词（统计要归到人说的那条词上）
    queue = [q for q in queries if q and q.strip()]
    # 降粒度重试的预算：不设上限的话，一章能打出几十次检索请求。
    # 每个词有"补主语""裸词"两种形态，整串再加一种"换序"形态（见下面 got==0 处），
    # 所以按 5 倍留量（实测一章 3 条检索词最坏约 15 次检索；
    # 每次只是一个 HTTP GET，不花模型额度）。
    budget = 5 * max(1, len(queue))
    while queue:
        q = queue.pop(0)
        if q in tried:
            continue
        tried.add(q)
        try:
            cands = search(q, count=count, opener=opener)
        except Exception as e:
            log("  图片检索失败：%s（%s）" % (q, e))
            continue
        if stats is not None:
            root = roots.get(q, q)
            named = sum(1 for c in cands
                        if names_subject((c.title or u"").lower(), subject))
            st = stats.setdefault(root, {"offered": 0, "named": 0})
            st["offered"] = max(st["offered"], len(cands or ()))
            st["named"] = max(st["named"], named)
        got = 0
        for c in cands:
            if got >= max_per_query:
                break
            # 来源页配额要在**下载之前**查：一次下载是几 MB 与一次往返，
            # 而这一条判据只看 URL，先问一句能省下整轮抓取。
            page = (c.purl or "").split("#")[0]
            # 人工排除排在配额之前：它是一条都不想要这个站，配额是「少要几张」。
            if page_excluded(page, exclude_pages):
                log(u"  丢弃（人工排除的来源页）：%s" % page)
                continue
            page = (c.purl or "").split("#")[0]
            if max_per_source_page and used_pages is not None:
                if used_pages.get(page, 0) >= max_per_source_page:
                    log(u"  丢弃（同一来源页已用满 %d 张）：%s" % (max_per_source_page, page))
                    continue
            why = reject_reason(c, keywords + [q], subject=subject, min_hits=min_hits)
            if why is not None:
                # 没下载就被否掉的候选也要留数：不然报表上"丢弃 2000 次"
                # 看不出是引擎给了 2000 页垃圾，还是我们的判据太严。
                log(u"  丢弃（未下载·%s）：%s" % (why, c.purl or c.murl or u""))
                continue
            for url in (c.murl, c.turl):  # 原图优先，Bing 缩略图兜底
                data = dl(url)
                if not data:
                    continue
                ok, fmt, w, h, why = accept_image(data, bar)
                if not ok:
                    continue
                digest = _sha(data)
                # 这张图是不是本轮新落到盘上的，决定调用方能不能删它：
                # 命中 seen_hash 时复用的是**上一轮**的文件名，而上一轮的 data.json
                # 可能还指着它——09-21 深夜 LV 重做就是这么把两张在用的图删掉的。
                wrote = digest not in seen_hash
                if score(c, w, h, len(data), keywords + [q], subject=subject,
                         min_hits=min_hits) < 0:
                    log("  丢弃（评分过低/素材站）：%s" % (c.purl or url))
                    continue
                if digest in seen_hash:
                    # 磁盘上已有这张图：
                    #   已被某章认领 → 换下一张候选（两章共用一张图会被 G-03 判死）
                    #   没人认领（上一轮遗物）→ 直接adopt，重跑才不会整章没图
                    name = seen_hash[digest]
                    if name in emitted or name in claimed:
                        continue
                else:
                    idx += 1
                    name = "%02d_%s.%s" % (idx, _slug(q, "img"), fmt)
                    while name in used_names:
                        idx += 1
                        name = "%02d_%s.%s" % (idx, _slug(q, "img"), fmt)
                    with open(os.path.join(images_dir, name), "wb") as fh:
                        fh.write(data)
                    seen_hash[digest] = name
                    used_names.add(name)
                emitted.add(name)
                if used_pages is not None:
                    used_pages[page] = used_pages.get(page, 0) + 1
                got += 1
                taken.append({
                    "file": "images/" + name,
                    "query": q,
                    "alt": "",
                    "caption": "",
                    "width": w,
                    "height": h,
                    "bytes": len(data),
                    "format": fmt,
                    "source_page": c.purl,
                    "source_image": url,
                    "title": c.title,
                    "fresh": wrote,
                })
                break
        if got == 0:
            log("  未取得合格配图：%s" % q)
            # 实测：Bing CN 对多词图检索词经常返回一整页兜底垃圾
            # （旅游榜单、施工方案、球赛海报），换成单词才召得回真图。
            # 所以整串查不到就降一级粒度重试，而不是让这一章空着。
            if len(tried) < budget:
                toks = [x.strip() for x in
                        re.split(r"[\s,，、/|()（）：:；;]+", q) if x.strip()]
                # 换序与降粒度这两条重试，**实测依据都是中文短语**：
                # `咖啡 手冲` 点名 0 条而 `手冲 咖啡` 35 条；`咖啡 烘焙` 好而 `烘焙 咖啡` 坏
                # ——方向没有规律，所以不能靠改写大纲一次做对，但换序是零成本的第二种问法。
                # 纯拉丁的多词串不适用：那**是一个产品名**，拆出来的片段是通用英文词。
                # 09-24 骁龙笔电篇把 `Snapdragon X Elite` 倒装成 `Elite X Snapdragon`、
                # 又拆成裸 `Elite` / `Plus`，配回来的是留学机构 logo、模特大赛舞台照、
                # 游戏截图、"Elite" 注册商标查询页与 Pixabay 的加号素材图——
                # 五张全都"过了点名闸门"，因为标题里确实有那几个字。
                splittable = any(u'一' <= ch <= u'鿿' for ch in q)
                rev = u' '.join(reversed(toks))
                if (splittable and len(toks) == 2 and rev != q
                        and rev not in tried and rev not in queue):
                    roots[rev] = roots.get(q, q)
                    queue.append(rev)
                for tok in ([] if not splittable else toks):
                    tok = tok.strip()
                    if len(tok) < 2 or tok in tried:
                        continue
                    if tok.lower() in STOP_TOKENS:
                        continue
                    # 两种形态都排进来：补了主语的（"咖啡 磨豆机"）保证搜回来的页面
                    # 大概率点名领域；裸词（"磨豆机"）保证召得回东西——实测 Bing CN 对
                    # 多词中文查询经常只给 1 条候选，单词能给 35 条。
                    # 裸词搜回来的候选照样要过 score() 的主语闸门，精度没有被放弃。
                    for alt in (ensure_subject(tok, subject), tok):
                        if alt and alt not in tried and alt not in queue:
                            roots[alt] = roots.get(q, q)
                            queue.append(alt)
    return taken


def write_manifest(dest_dir, entries):
    p = os.path.join(dest_dir, "images", "manifest.json")
    with io.open(p, "w", encoding="utf-8") as fh:
        json.dump(entries, fh, ensure_ascii=False, indent=1)
    return p


def load_manifest(dest_dir):
    p = os.path.join(dest_dir, "images", "manifest.json")
    if not os.path.isfile(p):
        return []
    return json.load(io.open(p, encoding="utf-8"))


def _sha(b):
    return hashlib.sha256(b).hexdigest()
