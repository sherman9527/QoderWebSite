# -*- coding: utf-8 -*-
"""W-168 检索词点名：一条检索词有没有点到"这个实体"，而不是点到它的姓。

起因（09-30 摩根篇）：领域名是共用姓氏时，主语闸门全线放行——22 张图里 15 张跑题，
而 14 条闸门 0 fail 0 warn。「摩根」同时是英国 Morgan 汽车、STANLEY 工具、
科幻作家 Kim Stanley Robinson 的姓。

10-05 量过才定形态（`.probe/w168_measure.py` → `.probe/w168_report.txt`）：
全站 793 条 image_queries 里 **645 条（81.3%）不含任何全名**，且 9 篇一个全名别名都没有
（娇兰/咖啡/劳力士/爱马仕/百达翡丽/香奈儿/宾利/浪琴/积家只有 0–1 个）。
所以"每条检索词必须含 aliases 里的全名"这条判据**不能当闸门**——
它是在惩罚已经上架的页面，而 W-162/W-164 的教训都是"判据没分类就上闸"会把假阳性变成阻塞。
最新的几篇（MLCC 0/16、骁龙笔电 0/22、Agent开发、开源权重）本来就按这个约定写的，
所以这条约定是真的，只是不能回溯性地钉死在 29 篇上。

这里的用途因此只有两个，都不阻塞：采集期在日志里说一声，体检报告里出一个数。
"""
from __future__ import unicode_literals

import io
import json
import os
import re
import sys

# 这个文件会 print 中文，Windows 上 stdout 默认是 GBK —— 没有这道守卫就直接崩
# （10-26 validate.py 打印 G-15 告警里的 ⇒ 就是这么把 9 篇渲染打成 rc=1 的）。
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

_HAS_LATIN = re.compile(r"[A-Za-z]")
_CJK = re.compile(u"[\u4e00-\u9fff]")


def is_full_name(alias):
    """"全名"的可操作定义。
    拉丁名：两个词以上（`J.P. Morgan`、`Morgan Stanley`），或长到不可能是姓（≥12 字符）；
    中文名：CJK 字数 ≥3——"摩根"两字是姓，"摩根士丹利"才是实体。
    """
    a = (alias or u"").strip()
    if not a:
        return False
    if _HAS_LATIN.search(a):
        return bool(re.search(r"[A-Za-z].*\s", a)) or len(a) >= 12
    return len(_CJK.findall(a)) >= 3


def full_names(aliases):
    return [a for a in (aliases or []) if isinstance(a, str) and is_full_name(a)]


def names_a_full(query, aliases):
    q = (query or u"").casefold()
    return any(a.casefold() in q for a in full_names(aliases))


def audit_outline(path):
    """一篇大纲的点名情况。返回 None 表示没有 image_queries 可判。"""
    d = json.load(io.open(path, encoding="utf-8"))
    aliases = d.get(u"aliases") or []
    fn = full_names(aliases)
    total = 0
    unnamed = []
    for s in d.get(u"sections") or []:
        for q in (s.get(u"image_queries") or []):
            if not (q or u"").strip():
                continue
            total += 1
            if not names_a_full(q, aliases):
                unnamed.append((s.get(u"id"), q))
    return {u"topic": d.get(u"topic") or os.path.basename(path)[:-5],
            u"aliases": len(aliases), u"full_names": len(fn),
            u"queries": total, u"unnamed": len(unnamed),
            u"examples": unnamed[:3],
            # 两种成因必须分开说：没点名是作者的事，没全名可用是大纲的事。
            # 混成一条"检索词不合格"就会去改本该改不动的那一边。
            u"blocked_by_outline": bool(total) and not fn}


def audit_all(topics_dir=None):
    d = topics_dir or os.path.join(ROOT, u"config", u"topics")
    return [audit_outline(os.path.join(d, f)) for f in sorted(os.listdir(d))
            if f.endswith(u".json")]


def main(argv=None):
    rows = [r for r in audit_all() if r and r[u"queries"]]
    tot = sum(r[u"queries"] for r in rows)
    bad = sum(r[u"unnamed"] for r in rows)
    print(u"检索词点名率：%d / %d 条含全名（未点名 %d，%.1f%%）"
          % (tot - bad, tot, bad, 100.0 * bad / max(tot, 1)))
    print(u"这条只做体检与采集期提示，不是闸门：%.1f%% 的既有检索词会被判不合格，"
          u"而那是在惩罚已上架的页面" % (100.0 * bad / max(tot, 1)))
    print(u"")
    print(u"篇\t条数\t未点名\t全名数\t成因")
    for r in sorted(rows, key=lambda r: -r[u"unnamed"]):
        why = u"大纲里没有全名可用（改 aliases）" if r[u"blocked_by_outline"] else u"作者侧：检索词没点名"
        print(u"%s\t%d\t%d\t%d\t%s" % (r[u"topic"], r[u"queries"], r[u"unnamed"],
                                       r[u"full_names"], why))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
