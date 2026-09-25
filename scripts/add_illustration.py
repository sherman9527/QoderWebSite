# -*- coding: utf-8 -*-
"""把一张自画的示意图装进产物：文件、data.json、manifest 三处一起写。

为什么要有这个脚本而不是手改 data.json：一张图同时活在三个地方。
少写一处会分别以三种方式坏掉——没文件 → G-03 报破链；data.json 没引用 →
G-03 报孤儿图片；manifest 没记 → 下一次 `--redo-images` 把它当成没抓过的东西。
手改一次就迟早漏一处，这正是 `generate.image_ref()` 存在的理由（W-115 的教训）。

红线 R-03 改后的形状（D-22，开发者 2026-09-24 授权）：引用图必须有 `source_page`；
自画示意图必须有 `based_on`（画的是正文哪几条已溯源事实）而且**禁止**带 `source_page`
——带了就能冒充引用图。所以这里写死的记录形态就是那条规则本身。
"""
import argparse
import io
import json
import os
import re
import shutil
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAGIC = (b"\x89PNG\r\n\x1a\n", b"\xff\xd8\xff", b"GIF87a", b"GIF89a", b"RIFF")


class IllustrationError(Exception):
    pass


def _slug(text):
    s = re.sub(r"[^\w一-鿿]+", u"_", unicode_(text)).strip(u"_")
    return s[:40] or u"illustration"


def unicode_(v):
    return v if isinstance(v, type(u"")) else str(v)


def _inspect(path):
    """验 magic bytes 与真实尺寸，不验扩展名。
    这条纪律来自下载侧：Bing 会返回 404 而字节是合法 JPEG，也会返回合法 HTML 却叫 .jpg。"""
    if not os.path.isfile(path):
        raise IllustrationError(u"文件不存在：%s" % path)
    head = io.open(path, "rb").read(12)
    if not any(head.startswith(m) for m in MAGIC):
        raise IllustrationError(u"%s 不是真图片（magic bytes 不匹配），不能装进产物" % path)
    try:
        from PIL import Image
        w, h = Image.open(path).size
    except Exception as e:
        raise IllustrationError(u"读不出图片尺寸：%s（%s）" % (path, type(e).__name__))
    if w < 320 or h < 240:
        raise IllustrationError(u"示意图只有 %dx%d，正文栏宽下会糊成一团" % (w, h))
    return w, h


def _next_slot(domain_dir, data):
    used = set()
    for f in os.listdir(os.path.join(domain_dir, "images")):
        m = re.match(r"(\d{2})_", f)
        if m:
            used.add(int(m.group(1)))
    for s in data.get("sections") or []:
        for im in s.get("images") or []:
            m = re.match(r"images/(\d{2})_", im.get("file") or "")
            if m:
                used.add(int(m.group(1)))
    n = 1
    while n in used or n > 99:
        n += 1
    if n > 99:
        raise IllustrationError(u"编号已用满 99 张，先清理或改命名规则")
    return n


def install(topic, section_id, src, alt, caption=u"", based_on=(), slug=None, root=None):
    """返回写进 data.json 的那条记录。"""
    root = root or os.path.join(ROOT, "output")
    domain_dir = os.path.join(root, topic)
    dp = os.path.join(domain_dir, "data.json")
    if not os.path.isfile(dp):
        raise IllustrationError(u"没有 %s：先跑 generate.py %s" % (dp, topic))
    data = json.load(io.open(dp, encoding="utf-8"))
    sec = next((s for s in data.get("sections") or [] if s.get("id") == section_id), None)
    if sec is None:
        raise IllustrationError(u"%s 没有章节 %r，可用：%s" % (
            topic, section_id, u"、".join(s.get("id") or "?" for s in data["sections"])))
    refs = [unicode_(b) for b in (based_on or []) if unicode_(b).strip()]
    if not refs:
        raise IllustrationError(
            u"示意图必须写 based_on（画的是正文哪几条已溯源事实）。"
            u"没有它，画错了没人能指出它声称画的是什么——那正是放行示意图要先解决的问题。")
    if not unicode_(alt).strip():
        raise IllustrationError(u"示意图必须有 alt")

    w, h = _inspect(src)
    n = _next_slot(domain_dir, data)
    ext = os.path.splitext(src)[1].lower() or ".png"
    name = u"%02d_%s%s" % (n, _slug(slug or alt), ext)
    dest = os.path.join(domain_dir, "images", name)
    if os.path.exists(dest):
        raise IllustrationError(u"目标已存在，不覆盖：%s" % dest)
    shutil.copyfile(src, dest)

    rec = {"file": u"images/%s" % name, "kind": "illustration",
           "alt": unicode_(alt), "caption": unicode_(caption or alt),
           "based_on": refs, "width": w, "height": h}
    sec.setdefault("images", []).append(rec)
    from generate import _save
    _save(dp, data)

    mp = os.path.join(domain_dir, "images", "manifest.json")
    man = []
    if os.path.isfile(mp):
        try:
            man = json.load(io.open(mp, encoding="utf-8"))
        except ValueError:
            man = []
    man.append(dict(rec, source_page=u"", title=unicode_(alt)))
    io.open(mp, "w", encoding="utf-8").write(json.dumps(man, ensure_ascii=False, indent=1) + u"\n")
    return rec


def main(argv=None):
    ap = argparse.ArgumentParser(description=u"把自画示意图装进产物（kind=illustration）")
    ap.add_argument("topic")
    ap.add_argument("section_id")
    ap.add_argument("--from", dest="src", required=True, help=u"生成好的 png/jpg 路径")
    ap.add_argument("--alt", required=True, help=u"alt 文本，建议以「示意图·非实拍：」开头")
    ap.add_argument("--caption", default=u"", help=u"图注")
    ap.add_argument("--based-on", action="append", default=[],
                    help=u"可重复。画的是正文哪几条已溯源事实，形如 章节id#要点")
    ap.add_argument("--slug", default=None, help=u"文件名用的短名，默认从 alt 取")
    a = ap.parse_args(argv)
    try:
        rec = install(a.topic, a.section_id, a.src, alt=a.alt, caption=a.caption,
                      based_on=a.based_on, slug=a.slug)
    except IllustrationError as e:
        sys.stderr.write(u"✗ %s\n" % e)
        return 2
    sys.stdout.write(u"✓ 已装入 %s/%s → %s\n" % (a.topic, a.section_id, rec["file"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
