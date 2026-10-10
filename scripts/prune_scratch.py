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
# 只有测试会改它：清理范围与"谁还引用着这些原文"的扫描范围必须同源，
# 否则测试里保护生效、真目录里保护不生效。
OUTPUT_OVERRIDE = None


def in_text_layer(p, scratch=None):
    """`.research-scratch/text/` 是 W-189 的来源原文层，不是中间垃圾：
    `sources[].cache` 指的就是这里。按"7 天没动过"把它清掉，等于让全站指针集体指空文件，
    而这正是这一层存在的唯一意义（可回溯）。"""
    rel = os.path.relpath(p, scratch or SCRATCH).replace("\\", "/")
    return rel.startswith(u"text/")


def referenced_texts(scratch=None):
    import sourcecache as SC
    outdir = OUTPUT_OVERRIDE or os.path.join(ROOT, u"output")
    base = scratch or SCRATCH
    out = set()
    for rel in SC.referenced_files(outdir):
        out.add(os.path.normpath(os.path.join(base, rel.replace("/", os.sep))))
    return out


def shield(p, refs, keep_text, scratch=None):
    """返回 (是否免死, 原因)。"""
    if os.path.normpath(p) in refs:
        return True, u"被产物引用"
    if in_text_layer(p, scratch) and (keep_text or os.path.basename(p) == u"index.json"):
        # index.json 是 url→文件 的地图，地图永远比它描述的正文留着
        return True, u"来源原文层"
    return False, u""


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
    ap.add_argument("--include-text", action="store_true",
                    help=u"连来源原文层一起清（只放开**没有被任何产物引用**的那些）")
    args = ap.parse_args(argv)

    if not os.path.isdir(SCRATCH):
        print(u"没有 %s，无需清理" % SCRATCH)
        return 0
    victims = stale_files(SCRATCH, args.keep_days)
    refs = referenced_texts(SCRATCH)
    shielded = [(p, shield(p, refs, not args.include_text)[1])
                for p in victims if shield(p, refs, not args.include_text)[0]]
    victims = [p for p in victims if os.path.normpath(p) not in
               {os.path.normpath(q) for q, _ in shielded}]
    print(u"%s 共 %.1f MB，%d 个文件早于 %d 天" % (
        SCRATCH, size_of(SCRATCH) / 1048576.0, len(victims) + len(shielded), args.keep_days))
    if shielded:
        import collections
        by = collections.Counter(w for _p, w in shielded)
        print(u"  其中 %d 个免死：%s" % (
            len(shielded), u"、".join(u"%s %d" % (k, v) for k, v in by.most_common())))
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
