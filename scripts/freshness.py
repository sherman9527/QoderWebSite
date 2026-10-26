# -*- coding: utf-8 -*-
"""W-190 新鲜度：一个页面最后一次逐条核对来源是哪天，今天到期了没有。

数据早就有——每条来源在研究阶段都写了 `retrieved`（29 篇全有），
但 `validate.py` 从来没有读过它，所以"站点是长期资产"这件事在质量线上是隐形的。

这里只做两件事，都不做自动重抓：
1. 把 `retrieved` 读出来，算出**龄期**与**该篇自带多少时点断言**，合成一张到期清单；
2. 给闸门一个可判的形状（warn，不 fail）。

为什么不自动重抓：Bing/EDGAR 的召回方差会把"变了"与"没抓到"混在一起，
W-158 已经为这类 A/B 拒过一次（`memo.md`，量了五次才敢报数）。
为什么不 fail：一条只与时间有关的判据把产物钉住，等于用闸门逼一次全量重研，
那是成本而不是质量——W-158 的第三条教训正是"防呆判据在第二种成因下变成阻塞器"。

阈值不按类别手抄一张表：13 个中文类别名钉进代码，改一次大纲就漏一条。
改成**由文本自己说**：这一章有多少个"截至 2026-09"「公价」「同比」这类时点标记，
密度越高过期越快。数字放在 `config/quality_bar.json` 的 `freshness`，可调不改码。
"""
from __future__ import unicode_literals

import datetime as dt
import io
import json
import os
import re
import sys

# Windows 上 stdout 默认按 ANSI 码页（这台机器是 GBK）编码，而本仓库的输出里全是
# 中文与 ⇒/≠/· 这类非 GBK 字符。少这道守卫不是显示难看，是**直接崩**：
# 10-26 就是 validate.py 打印一条 G-15 告警里的 ⇒ 时抛 UnicodeEncodeError，
# 把 9 篇渲染打成 rc=1 —— 看着像质量闸门拦的，其实是编码。守卫本身由
# tests/test_contract.py 那条"会 print 的脚本必须钉住输出编码"守住。
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 时点标记：一句断言里"这个数是有时限的"的信号。
# 只数显式信号，不做语义判断——这条指标的作用是把 300 篇次的注意力排个序，
# 不是判对错（W-162/W-164 的教训：字符串匹配分不开"同一个数、同一件事"）。
DATEISH = re.compile(
    u"20\\d{2}[-/年]\\s?\\d{1,2}|20\\d{2}\\s?年|截至|今年以来|截至目前|最新|"
    u"公价|报价|市盈率|市销率|同比|环比|上季度|本季度|本季|去年|今年|"
    u"currently|as of|updated|year-over-year", re.I)


def _parse(d):
    if not d or not isinstance(d, str):
        return None
    try:
        return dt.date.fromisoformat(d[:10])
    except ValueError:
        return None


def dated_marks(data):
    """全篇的时点标记数。按区块的 JSON 串数，不重排文本——
    表格里 "2026 Q2" 与正文里 "截至 2026 年" 是同一类信号，都值得盯。"""
    n = 0
    for sec in data.get(u"sections") or []:
        for b in sec.get(u"blocks") or []:
            n += len(DATEISH.findall(json.dumps(b, ensure_ascii=False)))
    return n


def last_retrieved(data):
    """最晚的一条 `retrieved`。这就是"本页最后一次逐条核对来源"的日子。
    没有任何一条带日期时返回 None（调用方必须把它当成缺陷，不是当成"永远新"）。"""
    ds = [_parse(s.get(u"retrieved")) for s in (data.get(u"sources") or [])]
    ds = [d for d in ds if d]
    return max(ds) if ds else None


def density(data):
    secs = len(data.get(u"sections") or []) or 1
    return dated_marks(data) / float(secs)


def threshold_days(dens, bar):
    fb = bar.get(u"freshness") or {}
    for band in fb.get(u"bands") or []:
        if dens >= band.get(u"min_dated_per_section", 0):
            return int(band[u"days"])
    return int(fb.get(u"fallback_days") or 90)


def verdict(data, bar, today=None):
    today = today or dt.date.today()
    last = last_retrieved(data)
    dens = density(data)
    limit = threshold_days(dens, bar)
    v = {u"topic": data.get(u"topic") or u"",
         u"sources": len(data.get(u"sources") or []),
         u"last_retrieved": last.isoformat() if last else None,
         u"dated_marks": dated_marks(data),
         u"dated_per_section": round(dens, 2),
         u"limit_days": limit}
    if last is None:
        v[u"age"] = None
        v[u"due"] = True
        v[u"reason"] = u"没有任何来源记 retrieved，新鲜度无法判"
        return v
    age = (today - last).days
    v[u"age"] = age
    v[u"due"] = age > limit
    v[u"pressure"] = round(age * dens, 1)
    v[u"reason"] = u"最新核对距今 %d 天 > 阈值 %d 天（每章 %.1f 个时点标记）" % (age, limit, dens)
    return v


def scan(root=None, bar=None):
    root = root or os.path.join(ROOT, "output")
    if bar is None:
        bar = json.load(io.open(os.path.join(ROOT, "config", "quality_bar.json"),
                                encoding="utf-8"))
    out = []
    for name in sorted(os.listdir(root)):
        p = os.path.join(root, name, "data.json")
        if not os.path.isfile(p):
            continue
        out.append(verdict(json.load(io.open(p, encoding="utf-8")), bar))
    out.sort(key=lambda v: -(v.get(u"pressure") or 0.0))
    return out


def main(argv=None):
    rows = scan()
    due = [v for v in rows if v[u"due"]]
    print(u"到期 %d / %d 篇（按 龄期 × 每章时点标记数 排序）" % (len(due), len(rows)))
    print(u"篇\t最新核对\t龄期\t阈值\t每章时点数\t压力")
    for v in rows:
        print(u"%s\t%s\t%s\t%s\t%s\t%s%s" % (
            v[u"topic"], v[u"last_retrieved"] or u"-",
            u"-" if v[u"age"] is None else v[u"age"], v[u"limit_days"],
            v[u"dated_per_section"], v.get(u"pressure", u"-"),
            u"\t← 到期" if v[u"due"] else u""))
    if argv and u"--json" in argv:
        print(json.dumps(rows, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
