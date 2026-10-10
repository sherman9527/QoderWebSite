#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""一次性迁移：把已入库的图片压进 quality_bar 的体积策略。

为什么要有这个脚本而不是"下次重抓就好了"：全库 195.8 MB 里 97% 是图片，
不压就装不进任何一个站（单站上限 50 MiB，实测最大包 29.3 MB）。
而重抓意味着重跑配图阶段——Bing CN 的召回会突然跳水（memo 记过同一句检索词
一次给 5 条一次给 35 条），换回来的图还不是原来那批，等于把已经对的配图重做一遍。
**原地重编码只动字节，不动选图。**

三条自己定的规矩：
  · 保持原格式与原文件名。改扩展名要连带改 data.json 的 images[].file、cover、
    manifest、已落盘的页面引用，四处漏一处就是破图；省下的 8.8 MB 不值这个风险。
  · 示意图（kind=illustration）不做有损。上面是文字。
  · 每张压过的图都写一个 `<name>.srcsha`（**源图字节**的 sha256）。
    `collect()` 的去重拿盘上字节的哈希和下载到的原始字节比，压过之后两边永不相等，
    同一张图会以新名字再落一份，而 G-03 按文件判、看不见重复。
    `.srcsha` 不是图片扩展名，G-03 的孤儿筛天然放过它；`package_files` 按 `<img src>` 收集，
    天然不会把它打包上线。
    它还顺便让 `--apply` 可重跑：对不上源哈希的文件已经压过了，跳过而不是再压一层。

封面会跟着宽度变：`cover_of` 在没有声明封面时按"最宽的一张"挑，
压图改了宽度就可能换一张。所以脚本**压前先记、压后必比**，不一致就报出来。

默认 dry-run，动手要 `--apply`（沿用 prune_scratch.py 的约定）。
"""
import argparse
import io
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import images as I  # noqa: E402
import build_index as B  # noqa: E402
from generate import _save  # noqa: E402

EXTS = (".jpg", ".jpeg", ".png", ".gif", ".webp")


def _kinds(data):
    """file → kind。示意图与照片的压缩策略不同，判错一次就把一张带字的图糊掉。"""
    out = {}
    for s in data.get("sections") or []:
        for im in s.get("images") or []:
            out[os.path.basename(im.get("file") or u"")] = im.get("kind") or u"photo"
    cov = data.get("cover") or {}
    if cov.get("file"):
        out[os.path.basename(cov["file"])] = cov.get("kind") or u"photo"
    return out


def _srcsha_path(p):
    return p + u".srcsha"


def plan(topic_dir, bar, apply_=False):
    """返回 (逐文件结果, 压前封面解析, 压后封面解析)。"""
    dp = os.path.join(topic_dir, "data.json")
    if not os.path.isfile(dp):
        return [], None, None
    data = json.load(io.open(dp, encoding="utf-8"))
    before_cover = B.cover_of(data)
    kinds = _kinds(data)
    img_dir = os.path.join(topic_dir, "images")
    rows = []
    if not os.path.isdir(img_dir):
        return rows, before_cover, before_cover
    for fn in sorted(os.listdir(img_dir)):
        if not fn.lower().endswith(EXTS):
            continue
        p = os.path.join(img_dir, fn)
        raw = io.open(p, "rb").read()
        on_disk = I._sha(raw)
        existing = _srcsha_path(p)
        recorded = _read(existing)
        if recorded and recorded != on_disk:
            # 侧车记的源哈希和盘上字节对不上 = 这份已经是压过的结果。
            # 再喂一遍就是拿压缩产物当源，每跑一轮糊一层。跳过，并把"已压过"如实报出来。
            rows.append({"file": fn, "kind": kinds.get(fn, u"photo"), "before": len(raw),
                         "after": len(raw), "w": None, "h": None,
                         "note": u"已压过，跳过", "src_sha": recorded, "hit": False})
            continue
        src_sha = recorded or on_disk
        out, w, h, note = I.fit_bytes(raw, None, bar, kind=kinds.get(fn, u"photo"))
        rows.append({"file": fn, "kind": kinds.get(fn, u"photo"), "before": len(raw),
                     "after": len(out), "w": w, "h": h, "note": note,
                     "src_sha": src_sha, "hit": len(out) > bar.get("max_bytes", 1 << 30)})
        if not apply_ or out == raw:
            if apply_:
                _write(existing, src_sha)
            continue
        _write(p, out)
        _write(existing, src_sha)
        _sync_dims(topic_dir, fn, len(out), w, h)
    after_cover = None
    if apply_:
        after_cover = B.cover_of(json.load(io.open(dp, encoding="utf-8")))
    else:
        after_cover = before_cover
    return rows, before_cover, after_cover


def _read(p):
    if not os.path.isfile(p):
        return None
    return io.open(p, encoding="utf-8").read().strip()


def _write(p, text):
    if isinstance(text, bytes):
        io.open(p, "wb").write(text)
        return
    tmp = p + u".tmp"
    io.open(tmp, "w", encoding="utf-8", newline="\n").write(text)
    os.replace(tmp, p)


def _sync_dims(topic_dir, fn, nbytes, w, h):
    """宽度变了要同步三处：data.json 的 images[]、cover、manifest.json。

    为什么必须一起写：`cover_of` 按 width 挑封面，`add_illustration` 的 docstring
    早就说过"一张图活在几个地方，手改迟早漏一处"。这里漏了不会报错，
    只会让索引卡片和页面首图悄悄不是同一张。

    体积只进 manifest.json，**不进 data.json**：schema 的 images 条目是
    `additionalProperties: false`，写一个 `bytes` 进去 G-10 立刻判死整篇
    （10-03 实测：107 条 fail，全是我这一行造的）。
    这里顺手 pop，是为了让上一次误写跑过的仓库自己恢复，不用另写一个清理脚本。
    """
    dp = os.path.join(topic_dir, "data.json")
    d = json.load(io.open(dp, encoding="utf-8"))
    touched = False

    def _drop_bytes(entry):
        if "bytes" in entry:
            entry.pop("bytes")
            return True
        return False

    for s in d.get("sections") or []:
        for im in s.get("images") or []:
            if os.path.basename(im.get("file") or u"") == fn:
                if w and im.get("width") != w:
                    im["width"], im["height"] = w, h
                    touched = True
                if _drop_bytes(im):
                    touched = True
    cov = d.get("cover") or {}
    if cov.get("file") and os.path.basename(cov["file"]) == fn:
        if w and cov.get("width") != w:
            cov["width"], cov["height"] = w, h
            touched = True
        if _drop_bytes(cov):
            touched = True
    if touched:
        _save(dp, d)
    mp = os.path.join(topic_dir, "images", "manifest.json")
    if os.path.isfile(mp):
        try:
            man = json.load(io.open(mp, encoding="utf-8"))
        except ValueError:
            return
        hit = False
        for m in man:
            if os.path.basename(m.get("file") or u"") == fn:
                if w:
                    m["width"], m["height"] = w, h
                m["bytes"] = nbytes
                hit = True
        if hit:
            io.open(mp, "w", encoding="utf-8").write(json.dumps(man, ensure_ascii=False, indent=1) + u"\n")


def main(argv=None):
    ap = argparse.ArgumentParser(description=u"把已入库的图片压进体积策略（默认 dry-run）")
    ap.add_argument("topics", nargs="*", help=u"不给就是全部")
    ap.add_argument("--apply", action="store_true", help=u"真的写盘；不给就只报清单")
    ap.add_argument("--report", default=os.path.join(ROOT, ".probe", "shrink_images.txt"))
    a = ap.parse_args(argv)
    bar = json.load(io.open(os.path.join(ROOT, "config", "quality_bar.json"),
                            encoding="utf-8"))["images"]
    out_root = os.path.join(ROOT, "output")
    wanted = a.topics or sorted(d for d in os.listdir(out_root)
                                if os.path.isdir(os.path.join(out_root, d)))
    lines, tot_before, tot_after, hits, flips = [], 0, 0, 0, []
    for t in wanted:
        tdir = os.path.join(out_root, t)
        rows, c0, c1 = plan(tdir, bar, apply_=a.apply)
        if not rows:
            continue
        b = sum(r["before"] for r in rows)
        # dry-run 也要报**预计**压后体积，否则这个模式就没法用来判断值不值得动手
        after = sum(r["after"] for r in rows)
        tot_before += b
        tot_after += after
        n_hit = [r for r in rows if r["hit"]]
        hits += len(n_hit)
        f0 = (c0 or {}).get("file")
        f1 = (c1 or {}).get("file")
        if a.apply and f0 != f1:
            flips.append((t, f0, f1))
        changed = [r for r in rows if r["after"] != r["before"]]
        lines.append(u"%-14s %3d 张  %6.2f → %6.2f MB  改动 %d 张%s"
                     % (t, len(rows), b / 1048576.0, after / 1048576.0, len(changed),
                        (u"  未达标 " + u"、".join(r["file"] for r in n_hit)) if n_hit else u""))
        for r in n_hit:
            lines.append(u"      ! %-34s %7d → %7d B  %s" % (r["file"], r["before"], r["after"], r["note"]))
    head = (u"%s：图片 %d 篇，%.1f MB → %s %.1f MB；到不了 max_bytes 的 %d 张"
            % (u"已应用" if a.apply else u"dry-run", len(wanted),
               tot_before / 1048576.0,
               u"" if a.apply else u"（预计）", tot_after / 1048576.0, hits))
    text = head + u"\n" + u"\n".join(lines) + u"\n"
    if flips:
        text += u"\n!! 封面换图的篇目（cover_of 按宽度挑，压图改了宽度）：\n"
        for t, f0, f1 in flips:
            text += u"   %-14s %s → %s\n" % (t, f0, f1)
    if not a.apply:
        text += u"\n（dry-run，未写盘。确认清单后加 --apply）\n"
    sys.stdout.write(text)
    d = os.path.dirname(a.report)
    if not os.path.isdir(d):
        os.makedirs(d)
    io.open(a.report, "w", encoding="utf-8").write(text)
    return 1 if flips else 0


if __name__ == "__main__":
    sys.exit(main())
