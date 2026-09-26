# -*- coding: utf-8 -*-
"""配图体检：逐领域报"几张图、几张没点名领域、哪几章空着"，可选只修不合格的那些。

为什么要这么一步：质量闸门量的是形式（图是真的、够大、有来源、不重复），
跑题是语义问题，闸门结构上看不见——今天两篇 0 fail 0 warn 的页面里
混着"中国行政区划"和"圆糯米"。所以必须有一道专门看语义的检查。

默认只报不改。`--fix` 才重做，而且只重做不合格的那个领域：
体检本身不花额度也不碰网络，而无条件重跑等于把已经合格的页面也押上去赌一次网络。
"""
import argparse
import io
import json
import os
import subprocess
import sys

if hasattr(sys.stdout, "reconfigure"):
    # 报表里有 ✗/✓：stdout 重定向到日志文件时 Python 用控制台编码（本机 cp936），
    # 撞不上 GBK 能表示的字符就直接 UnicodeEncodeError 把整个体检崩掉。
    # 09-21 实测死在 report() 的第一行——体检器写不进日志，等于这道检查没人能留档。
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import images as I
import outline as O

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT = os.path.join(ROOT, "output")
CONFIG = os.path.join(ROOT, "config", "topics")


def _empty_cause(queries, stats):
    """一章空着，四种可能，处置各不相同。判据只用 collect 记下的召回统计。

    engine  —— 召回到东西却零条点名领域：引擎答非所问。换时间重试（D-14），别改大纲。
    recall  —— 所有词都零召回：网络/引擎抖动，同样别改大纲。
    supply  —— 有点名的页，但全死在尺寸/评分/下载：这才是供给质量问题。
    unknown —— 没有统计（旧产物或没传 stats）：就报"不知道"，不猜。
    """
    rows = [stats[q] for q in queries if q in stats]
    if not rows:
        return "unknown"
    if any(r.get("named") for r in rows):
        return "supply"
    if any(r.get("offered") for r in rows):
        return "engine"
    return "recall"


def load_search_stats(dest_dir):
    p = os.path.join(dest_dir, "images", "search-stats.json")
    if not os.path.isfile(p):
        return {}
    try:
        return json.load(io.open(p, encoding="utf-8"))
    except ValueError:
        return {}


def audit_data(cfg, data, search_stats=None):
    """纯判定：给定大纲与 data.json，返回配图数、没点名领域的文件、空章标题。
    单独拆出来是为了能被测试钉住——这道检查的全部价值就在于它抓得住真问题。"""
    subj = I.subject_tokens(cfg)
    # 分诊要能回答一个具体问题：这张脏图到底是"大纲没点名"还是"大纲点名了却没搜到"。
    # 判据是**这条检索词大纲给过没有**——给过且没点名，改 config 有救；
    # 没给过，那是 collect 降粒度时自己拆出来的裸词，改大纲改不到它头上。
    # （09-22 实测：积家 27 条检索词全部点名之后仍报「8 张检索词可救」，
    #   把注意力往错方向带，D-14 当年也把它归给过引擎——两头都错过，W-95。）
    offered = {}
    for s in cfg.sections:
        offered[s.id] = {str(q or "").strip().lower() for q in (s.image_queries or [])}
    # 空章的成因分类（引擎答非所问 / 供给刷掉 / 零召回 / 没有统计）。
    # 没有这一层，"积家 4 章拿不到图"就只能靠猜——猜成"品牌没供给"就会去砍章节，
    # 而 09-22 实测真因是引擎对那条词回了一整页「积」字字典页。
    stats = {}
    for k, v in (search_stats or {}).items():
        stats[str(k).strip().lower()] = v
    total = 0
    unnamed = []
    drawn = []
    empty = []
    empty_causes = []
    fixable = []
    dirty = []
    unknown = []
    starved = []
    # W-142 的处置：同一条检索词被几章复用，是一行**事实**，不是判据。
    # 09-25 我自己把 `OpenAI` 挂了 5 章，量了 18 篇才知道两条词面判据都不成立
    # （判据①误判 98%，判据②会误伤单产品领域），所以这里只报数、不判好坏、
    # 也不参与 `--fix` 的合格判定。它存在的意义是：当时要是有这一行，我不会看不见。
    reuse = {}
    for sec in data.get("sections") or []:
        ims = sec.get("images") or []
        if not ims:
            title = sec.get("title") or sec.get("id") or "?"
            empty.append(title)
            empty_causes.append((title, _empty_cause(
                [str(q or "").strip().lower() for q in
                 (dict((s.id, s.image_queries) for s in cfg.sections)
                  .get(sec.get("id"), []) or [])], stats)))
        for im in ims:
            total += 1
            if im.get("kind") == "illustration":
                # 自画示意图没有来源页可点名，硬去比 `caption + source_page` 必然落空，
                # 报成"没点名"会指着一个没坏的东西让人去修。它走人眼验收，单列出来。
                drawn.append(im.get("file") or "?")
                continue
            q0 = str(im.get("query") or "").strip()
            if q0:
                # 分组按小写，显示按原样：`anthropic` 与 `Anthropic` 是同一条词，
                # 分开数会把复用度算低——这条的存在理由恰恰是"别让我看不见复用"。
                reuse.setdefault(q0.lower(), [q0, set()])[1].add(sec.get("id") or "?")
            text = ("%s %s" % (im.get("caption") or im.get("alt") or "",
                               im.get("source_page") or "")).lower()
            if I.names_subject(text, subj):
                continue
            unnamed.append(im.get("file") or "?")
            # 有来路才能分诊：检索词本身没点名领域 → 改大纲/重做有救；
            # 检索词点名了却还是脏图 → 是检索引擎的问题，重做也白做。
            q = str(im.get("query") or "").strip().lower()
            if not q:
                # 没有 query 就是"不知道"，不是"没点名"。把缺失算进可救，
                # 报告就会指着一个没有依据的方向——百达翡丽 17 张全部 q=None
                # （那轮跑在 query 字段落地之前），却报"检索词可救 12"。
                unknown.append((im.get("file") or "?", u""))
            elif any(t in q for t in subj):
                dirty.append((im.get("file") or "?", im.get("query")))
            elif q in offered.get(sec.get("id"), ()):
                fixable.append((im.get("file") or "?", im.get("query")))
            else:
                starved.append((im.get("file") or "?", im.get("query")))
    return {"total": total, "unnamed": unnamed, "drawn": drawn, "empty": empty,
            "empty_causes": empty_causes, "subject": subj,
            "fixable": fixable, "dirty": dirty, "unknown": unknown,
            "starved": starved,
            "reused": sorted(((orig, len(secs)) for orig, secs in reuse.values()),
                             key=lambda x: (-x[1], x[0].lower()))[:3]}


def audit_topic(topic, root=ROOT):
    """返回 audit_data 的结果 + topic；data.json 缺失返回 None。"""
    domain_dir = os.path.join(root, "output", topic)
    dp = os.path.join(domain_dir, "data.json")
    if not os.path.isfile(dp):
        return None
    cfg = O.load_for_topic(topic, root=root)
    out = audit_data(cfg, json.load(io.open(dp, encoding="utf-8")),
                     search_stats=load_search_stats(domain_dir))
    out["topic"] = topic
    return out


CAUSE_CN = {"engine": u"引擎答非所问", "recall": u"零召回",
            "supply": u"供给", "unknown": u"未知"}


def _cause_summary(causes):
    """空章成因汇总成一行。顺序固定，报表可 diff。"""
    if not causes:
        return u""
    counts = {}
    for _, c in causes:
        counts[c] = counts.get(c, 0) + 1
    return u"（%s）" % u" / ".join(
        u"%s %d" % (CAUSE_CN.get(c, c), counts[c])
        for c in ("engine", "recall", "supply", "unknown") if c in counts)


def report(rows, log=lambda m: sys.stdout.write(m + chr(10))):
    bad = []
    for r in rows:
        if r is None:
            continue
        ok = (not r["unnamed"]) and (not r["empty"])
        if not ok:
            bad.append(r["topic"])
        log(u"%s %-6s 配图 %-3d 没点名 %d%s 空章 %d%s%s%s%s" % (
            u"✓" if ok else u"✗", r["topic"], r["total"], len(r["unnamed"]),
            u"（检索词可救 %d / 点名档空手 %d / 引擎脏 %d / 无来路 %d）" % (
                len(r.get("fixable") or []), len(r.get("starved") or []),
                len(r.get("dirty") or []), len(r.get("unknown") or [])) if r["unnamed"] else u"",
            len(r["empty"]),
            _cause_summary(r.get("empty_causes") or []),
            u"  ← %s" % u"、".join(r["empty"][:3]) if r["empty"] else u"",
            u"  自画示意图 %d（人眼看画得对不对）" % len(r.get("drawn") or [])
            if r.get("drawn") else u"",
            u"  复用最高：%s" % u"、".join(u"%s×%d章" % (q[:24], n)
                                          for q, n in (r.get("reused") or [])[:2])
            if r.get("reused") else u""))
    return bad


def redo(topic, log=lambda m: sys.stdout.write(m + "\n")):
    """只重做一个领域的配图（正文不重跑，不花模型额度）。

    进度**直接继承父进程 stdout**，不捕获。原来用 `capture_output=True` +
    只回显最后 4 行，于是一次 20–50 分钟的重做全程零输出（09-21 实测：日志
    51 分钟停在 587 字节，只能靠摸 `images/` 的 mtime 判断它还活着）；
    而且它按 utf-8 解码子进程输出，`generate.py` 重定向时写的是 cp936，
    那 4 行本身也是残缺的。判活不该靠猜编码。
    子进程用 PYTHONIOENCODING 强制 utf-8，两边写同一个句柄才不会一半 GBK 一半 UTF-8。
    """
    log(u"  重做 %s 的配图…" % topic)
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    r = subprocess.run([sys.executable, "-u", os.path.join("scripts", "generate.py"),
                        topic, "--redo-images", "--workers", "2"],
                       cwd=ROOT, env=env)
    log(u"  %s 重做退出码 %d" % (topic, r.returncode))
    return r.returncode


def main(argv=None):
    ap = argparse.ArgumentParser(description=u"配图语义体检")
    ap.add_argument("topics", nargs="*", help=u"默认全部 config/topics/*.json")
    ap.add_argument("--fix", action="store_true", help=u"只重做不合格的领域")
    args = ap.parse_args(argv)

    def log(m):
        sys.stdout.write(m + "\n")
        sys.stdout.flush()

    topics = args.topics or sorted(f[:-5] for f in os.listdir(CONFIG) if f.endswith(".json"))
    rows = [audit_topic(t) for t in topics]
    bad = report(rows, log)
    missing = [t for t, r in zip(topics, rows) if r is None]
    if missing:
        log(u"尚未生成（无 data.json）：%s" % u"、".join(missing))
    if not bad:
        log(u"全部合格。")
        return 0
    log(u"不合格：%s" % u"、".join(bad))
    if not args.fix:
        log(u"（只报告。要重做这些领域加 --fix）")
        return 1
    for t in bad:
        redo(t, log)
    log(u"重做后复查：")
    return 0 if not report([audit_topic(t) for t in bad], log) else 1


if __name__ == "__main__":
    sys.exit(main())
