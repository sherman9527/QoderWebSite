# -*- coding: utf-8 -*-
"""W-145 一次性迁移：每篇只留最新版，页面名从 `<领域>_YYYY-MM-DD.html` 改成 `<领域>.html`。

为什么要有独立脚本而不是"顺手在 generate 里做掉"：这一步**不可逆**——日期页是
"这篇第一次上架是哪天"的唯一来源（`build_index.created_of` 读的就是最早那篇的文件名），
删掉之后没有第二次机会。所以它必须是一个能先看清单、再单独执行的东西。

顺序是这条脚本的全部要点：**先把 `created_date` 回填进 data.json，再删旧页**。
反过来做，索引的排序依据就永久丢了，而且丢得毫无征兆——卡片顺序照样看起来正常。
"""
import argparse
import io
import json
import os
import re
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATE_RE = re.compile(r"^(.+)_(\d{4}-\d{2}-\d{2})\.html$")


def _pages(d, topic):
    """这个领域目录下按日期排好的旧式日期页。"""
    out = []
    for f in sorted(os.listdir(d)):
        m = DATE_RE.match(f)
        if m and m.group(1) == topic:
            out.append((m.group(2), f))
    return out


def plan_for(d, topic):
    """一个领域要迁什么：回填哪天创建、留哪一页、删哪几页。

    没有 data.json 的目录不是"待迁移的领域"，是别的东西（索引临时目录、
    手工放的素材），跳过而不是报错——一条会在中途挂掉的迁移脚本最难收拾。
    """
    dp = os.path.join(d, "data.json")
    if not os.path.isfile(dp):
        return None
    pages = _pages(d, topic)
    if not pages:
        return None
    return {
        "topic": topic,
        "data_path": dp,
        "created": pages[0][0],                 # 最早那篇 = 第一次上架（W-128 的口径）
        "keep": pages[-1][1],                   # 最新那篇
        "drop": [f for _, f in pages[:-1]],
        "stable": "%s.html" % topic,
    }


def plan(root):
    if not os.path.isdir(root):
        return []
    out = []
    for topic in sorted(os.listdir(root)):
        d = os.path.join(root, topic)
        if not os.path.isdir(d):
            continue
        p = plan_for(d, topic)
        if p:
            out.append(p)
    return out


def _write_json(path, obj):
    io.open(path, "w", encoding="utf-8").write(json.dumps(obj, ensure_ascii=False, indent=2) + u"\n")


def apply_plan(p, log):
    data = json.load(io.open(p["data_path"], encoding="utf-8"))
    # 已有 created_date 就不动：它的语义是"第一次"，被重跑改成"最近一次跑迁移的日子"
    # 就等于没有，而且比没有更坏——看起来是有值的。
    if not data.get("created_date"):
        data["created_date"] = p["created"]
        _write_json(p["data_path"], data)
        log(u"      created_date ← %s" % p["created"])
    d = os.path.dirname(p["data_path"])
    src = os.path.join(d, p["keep"])
    dst = os.path.join(d, p["stable"])
    if src != dst:
        os.replace(src, dst)
    for f in p["drop"]:
        os.remove(os.path.join(d, f))
    log(u"      留 %s → %s，删掉 %d 篇旧日期页" % (p["keep"], p["stable"], len(p["drop"])))


def main(argv=None):
    ap = argparse.ArgumentParser(description=u"单页化迁移（默认 dry-run）")
    ap.add_argument("output_dir", nargs="?", default=os.path.join(ROOT, "output"),
                    help=u"产物根目录，默认 output/")
    ap.add_argument("--apply", action="store_true", help=u"真的改盘（不加就只报清单）")
    args = ap.parse_args(argv)

    plans = plan(args.output_dir)
    if not plans:
        sys.stderr.write(u"%s 下没有待迁移的日期页\n" % args.output_dir)
        return 0
    total_drop = sum(len(p["drop"]) for p in plans)
    log = lambda m: sys.stdout.write(m + u"\n")
    log(u"%s：%d 个领域待迁移，将删掉 %d 篇旧日期页"
        % (u"执行" if args.apply else u"dry-run", len(plans), total_drop))
    for p in plans:
        log(u"  %s  第一次上架 %s / 留 %s" % (p["topic"], p["created"], p["keep"]))
        if args.apply:
            apply_plan(p, log)
    if not args.apply:
        log(u"（只报告。真要在盘上改，加 --apply）")
        return 0
    # 迁移只是改了名字和数量，没碰图片。旧日期页一删，只被它们引用的图立刻变成
    # G-03 孤儿 → 那几篇闸门不过 → `_publishable` 把它们从索引里静默跳过
    # （09-25 实测：索引从 19 篇掉到 14 篇，而每一步的退出码都是 0）。
    # 清理交给重渲染做，是因为判据必须与 G-03 同源，不在这里另写一遍。
    log(u"")
    log(u"下一步必须做，否则索引会静默缩水（旧页一删，只被它们引用的图就成了 G-03 孤儿）：")
    log(u"  for t in $(ls config/topics | sed 's/.json//'); do python scripts/generate.py \"$t\" --offline; done")
    log(u"  python scripts/validate.py --all")
    return 0


if __name__ == "__main__":
    sys.exit(main())
