# -*- coding: utf-8 -*-
"""把一篇产物的配图拼成一张带标签的联络表，用眼睛看闸门量不出来的东西。

为什么要有这条命令：这个项目的验收规则是「闸门绿了还要人眼过一遍图」，
而它已经被证伪过一次——09-22 百达翡丽 `validate` 全绿，页面上却挂着
常柴柴油机和重型工作台（W-99）；09-23 积家我手工恢复回来的 6 张，
闸门同样一声不响，联络表一看是木工坊、永乐大钟、西铁城机芯（W-115）。
**「没点名领域」是可以机器判的，「这张图配不配得上这一章」不能**，
所以这一步必须留一个给人看的产物，而不是让 agent 自我宣布通过。

标签用系统里的中文字体画，退到 PIL 默认字体时中文会变方块——
那种情况下宁可少画一行标签，也不要把表画成看不懂的乱码。
"""
import argparse
import io
import json
import os
import sys

from PIL import Image, ImageDraw, ImageFont

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FONTS = [r"C:\Windows\Fonts\msyh.ttc", r"C:\Windows\Fonts\simhei.ttf",
         "/System/Library/Fonts/PingFang.ttc",
         "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc"]
TW, TH, PAD, LAB, COLS = 320, 240, 10, 62, 3


def clip(font, text, max_px):
    """PIL 不折行：超宽的标签会一路画进右边两列，再被下一行的图压住。
    按像素裁，不按字数裁——中文 13px 一个字 13 px，拉丁词宽得多，字数说不清。"""
    s = str(text or "")
    if font is None or font.getlength(s) <= max_px:
        return s
    while s and font.getlength(s + u"…") > max_px:
        s = s[:-1]
    return s + u"…"


def load_images(domain_dir):
    """返回 [(章节 id, 图片对象)]，按 data.json 里的章节顺序。"""
    data = json.load(io.open(os.path.join(domain_dir, "data.json"), encoding="utf-8"))
    out = []
    for s in data.get("sections") or []:
        for im in s.get("images") or []:
            out.append((s.get("id"), im))
    return out


def build(domain_dir, items, dest):
    rows = (len(items) + COLS - 1) // COLS
    sheet = Image.new("RGB", (COLS * (TW + PAD) + PAD, rows * (TH + LAB + PAD) + PAD),
                      (24, 24, 28))
    d = ImageDraw.Draw(sheet)
    font = None
    for path in FONTS:
        if os.path.isfile(path):
            try:
                font = ImageFont.truetype(path, 13)
                break
            except Exception:
                pass

    def text(xy, s, fill=(230, 230, 230)):
        if font is not None:
            d.text(xy, s, fill=fill, font=font)

    for i, (sid, im) in enumerate(items):
        r, c = divmod(i, COLS)
        x = PAD + c * (TW + PAD)
        y = PAD + r * (TH + LAB + PAD)
        rel = im.get("file") or ""
        p = os.path.join(domain_dir, rel.replace("/", os.sep))
        if os.path.isfile(p):
            try:
                pic = Image.open(p).convert("RGB")
                pic.thumbnail((TW, TH))
                sheet.paste(pic, (x, y))
            except Exception as e:
                text((x + 4, y + 4), u"读不出：%s" % type(e).__name__, (255, 90, 90))
        else:
            text((x + 4, y + 4), u"文件不在：%s" % rel, (255, 90, 90))
        text((x + 2, y + TH + 3), clip(font, u"[%s] %s" % (
            sid, os.path.basename(rel)), TW - 6))
        text((x + 2, y + TH + 21), clip(font, im.get("alt") or im.get("caption") or u"", TW - 6),
             (215, 215, 215))
        text((x + 2, y + TH + 39), clip(font, u"q=%s  src=%s" % (
            im.get("query") or u"-", im.get("source_page") or u"-"), TW - 6),
            (170, 200, 240))
    sheet.save(dest)
    return dest


def main(argv=None):
    ap = argparse.ArgumentParser(description=u"配图联络表（人眼验收用）")
    ap.add_argument("topics", nargs="+", help=u"领域名，可多个")
    ap.add_argument("--out", default=os.path.join(ROOT, ".probe"),
                    help=u"输出目录（默认 .probe/，不进产物）")
    args = ap.parse_args(argv)
    if not os.path.isdir(args.out):
        os.makedirs(args.out)
    rc = 0
    for topic in args.topics:
        domain_dir = os.path.join(ROOT, "output", topic)
        dp = os.path.join(domain_dir, "data.json")
        if not os.path.isfile(dp):
            print(u"✗ 没有 %s" % os.path.relpath(dp, ROOT).replace("\\", "/"))
            rc = 2
            continue
        items = load_images(domain_dir)
        dest = os.path.join(args.out, "sheet_%s.png" % topic)
        build(domain_dir, items, dest)
        print(u"%s：%d 张 → %s" % (topic, len(items), dest))
    return rc


if __name__ == "__main__":
    sys.exit(main())
