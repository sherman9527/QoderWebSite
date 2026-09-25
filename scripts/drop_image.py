# -*- coding: utf-8 -*-
"""把一张图从产物里摘掉：文件、data.json 的引用、manifest 的记录三处一起清。

`add_illustration.install` 的反向操作，存在的理由同一条（W-143）：一张图同时活在三个地方，
手删一次就迟早漏一处。默认 dry-run——`output/<领域>/images/` 不在 git 里，删了拿不回来。
"""
import argparse
import io
import json
import os
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class DropError(Exception):
    pass


def _norm(target):
    t = unicode_(target).strip().replace("\\", "/")
    return t if t.startswith("images/") else u"images/" + t


def unicode_(v):
    return v if isinstance(v, type(u"")) else str(v)


def _load(path, default):
    if not os.path.isfile(path):
        return default
    try:
        return json.load(io.open(path, encoding="utf-8"))
    except ValueError:
        return default


def drop(topic, target, root=None, apply=False):
    """摘一张图。返回 {"file", "section", "emptied_sections", "applied"}。

    名字打错一律报错，不静默跳过：一次"成功"的误删报告比删错更难查。
    """
    root = root or os.path.join(ROOT, "output")
    domain_dir = os.path.join(root, topic)
    dp = os.path.join(domain_dir, "data.json")
    if not os.path.isfile(dp):
        raise DropError(u"没有 %s：先跑 generate.py %s" % (dp, topic))
    want = _norm(target)

    data = _load(dp, {})
    hit = None
    for sec in data.get("sections") or []:
        for im in sec.get("images") or []:
            if _norm(im.get("file") or u"") == want:
                hit = (sec, im)
                break
        if hit:
            break
    if hit is None:
        have = [im.get("file") for s in data.get("sections") or [] for im in s.get("images") or []]
        raise DropError(u"%s 里没有引用 %s。可摘的：%s" % (
            topic, want, u"、".join(unicode_(h) for h in have) or u"（一张图都没有）"))
    sec, rec = hit

    mp = os.path.join(domain_dir, "images", "manifest.json")
    man = _load(mp, [])
    in_man = any(_norm(m.get("file") or u"") == want for m in man)
    if not apply:
        return {"file": want, "section": sec.get("id"), "emptied_sections": [],
                "applied": False, "in_manifest": in_man}

    sec["images"] = [im for im in sec["images"] if _norm(im.get("file") or u"") != want]
    emptied = [s.get("id") for s in data.get("sections") or [] if not (s.get("images") or [])]

    from generate import _save
    _save(dp, data)

    if in_man:
        man = [m for m in man if _norm(m.get("file") or u"") != want]
        io.open(mp, "w", encoding="utf-8").write(
            json.dumps(man, ensure_ascii=False, indent=1) + u"\n")

    fp = os.path.join(domain_dir, want)
    if os.path.isfile(fp):
        os.remove(fp)

    return {"file": want, "section": sec.get("id"), "emptied_sections": emptied,
            "applied": True, "in_manifest": in_man}


def main(argv=None):
    ap = argparse.ArgumentParser(description=u"把一张图从产物里摘掉（三处一起清）")
    ap.add_argument("topic")
    ap.add_argument("files", nargs="+", help=u"images/NN_xxx.jpg，可给多个")
    ap.add_argument("--apply", action="store_true", help=u"真的删；默认只报告")
    a = ap.parse_args(argv)
    emptied = []
    try:
        for t in a.files:
            res = drop(a.topic, t, apply=a.apply)
            emptied += res["emptied_sections"]
            sys.stdout.write(u"%s %s ← 章节 %s%s\n" % (
                u"已摘" if res["applied"] else u"将摘", res["file"], res["section"],
                u"（摘完这章就没图了）" if res["emptied_sections"] else u""))
    except DropError as e:
        sys.stderr.write(u"✗ %s\n" % e)
        return 2
    if emptied and not a.apply:
        sys.stdout.write(u"! 若全部执行，这些章会变空：%s\n" % u"、".join(emptied))
    if not a.apply:
        sys.stdout.write(u"（dry-run，什么都没动；加 --apply 才删）\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
