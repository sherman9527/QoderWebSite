# -*- coding: utf-8 -*-
"""示意图脚本共用的画图原语。

为什么抽出来：每篇的示意图都要"字体兜底 + 主题底色画布 + 居中文本 + 引线"这四件小事，
而配色每篇不同（抄 `web/src/tokens/index.ts` 的那一套身份色，不能自己另调）。
把不变的部分放这里，变的部分（调色板）当参数传。

搬这里的代码要守住一条：**产物必须逐字节可复现**。改完先跑到临时目录，
与已装进 `output/<领域>/images/` 的那几张比 md5，不一致就是改坏了。
"""
import os

from PIL import Image, ImageDraw, ImageFont

FONTS = [r"C:\Windows\Fonts\msyh.ttc", r"C:\Windows\Fonts\simhei.ttf"]


def make(palette):
    """返回 (font, canvas, label, leader)。palette 至少给 bg / ink / accent。"""
    bg = palette["bg"]
    ink = palette["ink"]
    accent = palette.get("accent", ink)

    def font(size):
        for p in FONTS:
            if os.path.isfile(p):
                return ImageFont.truetype(p, size)
        return ImageFont.load_default()

    def canvas(w=1500, h=950):
        img = Image.new("RGB", (w, h), bg)
        return img, ImageDraw.Draw(img)

    def label(d, xy, text, size=26, color=None, anchor="la"):
        d.text(xy, text, fill=color or ink, font=font(size), anchor=anchor)

    def leader(d, p_from, p_to, color=None):
        c = color or accent
        d.line([p_from, p_to], fill=c, width=2)
        d.ellipse([p_to[0] - 4, p_to[1] - 4, p_to[0] + 4, p_to[1] + 4], fill=c)

    return font, canvas, label, leader
