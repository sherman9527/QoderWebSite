# -*- coding: utf-8 -*-
"""清理联网研究的中间文件（W-42b）。

`.research-scratch/` 是无头 CLI 抓网页的落盘点（红线 R-08 把它关在这里）。
可追溯性不靠这些副本——`data.json` 与 `images/manifest.json` 里已经记了
`source_page` / `source_image` 的原始 URL。所以这里的文件是纯中间产物。

默认只报告不删（--dry-run 是默认值）：删文件是不可逆动作，要显式加 --apply。
"""
import argparse
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRATCH = os.environ.get("KE_SCRATCH") or os.path.join(ROOT, ".research-scratch")


def stale_files(directory, keep_days):
    cutoff = time.time() - keep_days * 86400
    out = []
    for base, _dirs, files in os.walk(directory):
        for f in files:
            p = os.path.join(base, f)
            try:
                if os.path.getmtime(p) < cutoff:
                    out.append(p)
            except OSError:
                continue
    return out


def size_of(directory):
    total = 0
    for base, _dirs, files in os.walk(directory):
        for f in files:
            try:
                total += os.path.getsize(os.path.join(base, f))
            except OSError:
                pass
    return total


def main(argv=None):
    ap = argparse.ArgumentParser(description=u"清理 .research-scratch/ 中间文件")
    ap.add_argument("--keep-days", type=int, default=7, help=u"保留最近 N 天（默认 7）")
    ap.add_argument("--apply", action="store_true", help=u"真的删；不加就只列出来")
    args = ap.parse_args(argv)

    if not os.path.isdir(SCRATCH):
        print(u"没有 %s，无需清理" % SCRATCH)
        return 0
    victims = stale_files(SCRATCH, args.keep_days)
    print(u"%s 共 %.1f MB，%d 个文件早于 %d 天" % (
        SCRATCH, size_of(SCRATCH) / 1048576.0, len(victims), args.keep_days))
    if not args.apply:
        for p in victims[:10]:
            print(u"  (dry-run) %s" % os.path.relpath(p, ROOT))
        if len(victims) > 10:
            print(u"  …另有 %d 个" % (len(victims) - 10))
        print(u"未删除。要删请加 --apply")
        return 0
    freed = 0
    for p in victims:
        try:
            freed += os.path.getsize(p)
            os.remove(p)
        except OSError as e:
            print(u"  删除失败 %s：%s" % (p, e))
    print(u"已删除 %d 个文件，释放 %.1f MB" % (len(victims), freed / 1048576.0))
    return 0


if __name__ == "__main__":
    sys.exit(main())
