# -*- coding: utf-8 -*-
"""从 `images.prev/records.json` 把被打断的配图引用拼回去。

为什么需要这么一步：`--redo-images` / `--only` 会先清掉章节的配图引用再重抓，
中途硬杀（taskkill、休眠、Ctrl+C 都不走 finally）留下的就是
「data.json 引用 0 张、图躺在 images.prev/、已发布页面一排破链」这个形状。
09-21 百达翡丽与 09-22 上午的同一篇都是这个形状，两次都是我**手写脚本**
从 manifest 把引用拼回去的——W-85b 落盘的 records.json 当时没有任何消费者。
没有消费者的凭据等于假保险，所以补上这一步。

判据只有三条，宁可少补也不能补错：
1. 凭据必须来自 records.json。`images/manifest.json` 没有 `section` 字段，
   拿它猜章节会把图发给错的章节，而且猜不出来时它会安静地产出一个
   "看起来恢复了"的 data.json。
2. 已经有图的章节一律不动。那些图可能是这一轮新抓的、更好的那批
   （W-100/W-101 修的正是"新引用把旧文件毁掉"这一类破坏）。
3. 从说明到来源页都没点名领域的记录不补（要补加 --force）——快照存的是
   **重做之前**那批图，而那批可能是主语闸门上线前的脏基线（W-115）。

默认只报不改，`--apply` 才写 data.json——与 prune_scratch / audit_images 同一条约定。
"""
import argparse
import io
import json
import os
import shutil
import sys

if hasattr(sys.stdout, "reconfigure"):
    # 报表里有 ✗/✓，重定向到日志时 Python 会用控制台编码（本机 cp936）直接崩掉。
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import generate as G
import images
import outline as O

ROOT = G.ROOT
OUTPUT = G.OUTPUT


def _log(msg):
    print(msg)


def load_records(prev_dir):
    """读快照记录。没有就返回 None，让调用方去解释"为什么不能拿 manifest 凑"。"""
    path = os.path.join(prev_dir, "records.json")
    if not os.path.isfile(path):
        return None
    try:
        rows = json.load(io.open(path, encoding="utf-8"))
    except ValueError:
        return []
    return [r for r in rows if isinstance(r, dict) and r.get("file")]


def plan(records, data, domain_dir, subject=None):
    """算出「哪几章能补回几张」。返回 ({章节 id: [图片对象]}, 说明列表)。

    说明列表是给人看的账，也是 dry-run 的全部内容：一张图补不回来时必须说得出为什么。

    subject 传进来就多做一道点名判断（W-115）：快照里混着的是**重做之前**那批图，
    而那批可能正是主语闸门上线前的脏基线。09-23 我给积家补回 6 张，
    联络表一看全是木工坊、永乐大钟、西铁城机芯——恢复工具不判点名，
    就是把脏基线当资产搬回来，而 W-109 拦的正是这件事。
    """
    sections = {s.get("id"): s for s in (data.get("sections") or [])}
    notes = []
    groups = {}
    for r in records:
        sid = r.get("section")
        if sid not in sections:
            notes.append(u"跳过 %s：记录写着章节 %s，当前 data.json 里没有这一章" % (
                r["file"], sid or u"（空）"))
            continue
        groups.setdefault(sid, []).append(r)

    out = {}
    for sid, rows in sorted(groups.items()):
        sec = sections[sid]
        if sec.get("images"):
            notes.append(u"跳过 %s：这一章已经有 %d 张图，不用旧快照盖掉" % (
                sid, len(sec["images"])))
            continue
        refs = []
        for r in rows:
            if subject:
                text = u"%s %s %s" % (r.get("caption") or u"", r.get("alt") or u"",
                                      r.get("source_page") or u"")
                if not images.names_subject(text.lower(), subject):
                    notes.append(u"%s 不补：从说明到来源页都没点名领域（%s）——"
                                 u"补回来就是拿别家的东西配本篇" % (
                                     r["file"], (r.get("alt") or u"")[:34]))
                    continue
            rel = r["file"]
            base = os.path.basename(rel)
            if os.path.isfile(os.path.join(domain_dir, rel.replace("/", os.sep))):
                pass
            elif not os.path.isfile(os.path.join(os.path.join(domain_dir, G.SNAP_DIR), base)):
                notes.append(u"%s 补不回来：images/ 与快照位都没有这个文件" % rel)
                continue
            refs.append(G.image_ref(r))
        if refs:
            out[sid] = refs
    return out, notes


def apply(domain_dir, data, planned):
    """先拷文件、后写引用：顺序反了就可能出现"data.json 指着不存在的文件"，
    那正是这条命令要修的故障。"""
    img_dir = os.path.join(domain_dir, "images")
    prev_dir = os.path.join(domain_dir, G.SNAP_DIR)
    sections = {s.get("id"): s for s in (data.get("sections") or [])}
    n = 0
    for sid, refs in sorted(planned.items()):
        if not os.path.isdir(img_dir):
            os.makedirs(img_dir)
        kept = []
        for ref in refs:
            rel = ref["file"]
            dst = os.path.join(domain_dir, rel.replace("/", os.sep))
            if not os.path.isfile(dst):
                src = os.path.join(prev_dir, os.path.basename(rel))
                try:
                    shutil.copy2(src, dst)
                except (OSError, shutil.Error) as e:
                    print(u"  ! 拷不回来 %s：%s" % (rel, e))
                    continue
            kept.append(ref)
        if kept:
            sections[sid]["images"] = kept
            n += len(kept)
    return n


def main(argv=None, log=None):
    log = log or _log
    ap = argparse.ArgumentParser(description=u"从快照记录恢复被打断的配图引用")
    ap.add_argument("topic", help=u"领域名")
    ap.add_argument("--output", default=OUTPUT, help=u"产物根目录（默认 output/）")
    ap.add_argument("--apply", action="store_true", help=u"真的写 data.json 并拷回文件")
    ap.add_argument("--force", action="store_true",
                    help=u"连「没点名领域」的记录也补（默认不补）")
    args = ap.parse_args(argv)

    domain_dir = os.path.join(args.output, args.topic)
    data_path = os.path.join(domain_dir, "data.json")
    if not os.path.isfile(data_path):
        log(u"✗ 没有 %s，无从恢复" % os.path.relpath(data_path, ROOT).replace("\\", "/"))
        return 2
    records = load_records(os.path.join(domain_dir, G.SNAP_DIR))
    if records is None:
        log(u"✗ %s/%s/records.json 不在——这份凭据只有跑过 --redo-images / --only 才会留下。" % (
            args.topic, G.SNAP_DIR))
        log(u"  不拿 images/manifest.json 凑：它没有 section 字段，猜出来的归属会把图发给错的章节。")
        return 2
    if not records:
        log(u"%s：快照里没有任何记录，没什么可恢复的" % args.topic)
        return 0

    data = json.load(io.open(data_path, encoding="utf-8"))
    subject = None
    if not args.force:
        try:
            subject = images.subject_tokens(O.load_for_topic(args.topic, root=ROOT))
        except Exception:
            log(u"! 没有 config/topics/%s.json，判不了「点名」——这一趟按原样补，"
                u"补回来的图要自己看过联络表" % args.topic)
    planned, notes = plan(records, data, domain_dir, subject=subject)
    total = sum(len(v) for v in planned.values())
    log(u"%s：快照记录 %d 条，可补 %d 张（涉及 %d 章）" % (
        args.topic, len(records), total, len(planned)))
    for sid, refs in sorted(planned.items()):
        log(u"  %s +%d 张：%s" % (sid, len(refs), u"、".join(r["file"] for r in refs)))
    for note in notes:
        log(u"  - %s" % note)
    if not total:
        log(u"没有可补的图，data.json 不动")
        return 0
    if not args.apply:
        log(u"未改动任何文件（默认只报，要写加 --apply）")
        return 0

    n = apply(domain_dir, data, planned)
    G._save(data_path, data)
    log(u"✓ 已补回 %d 张引用；接着要 --offline 重渲染，页面才会真的用上图" % n)
    return 0 if n else 2


if __name__ == "__main__":
    sys.exit(main())
