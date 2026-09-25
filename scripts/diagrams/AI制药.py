# -*- coding: utf-8 -*-
"""AI制药篇的示意图（示意图通道，D-22）。

只画两张，而且是有理由的：这两章的论点**照片在结构上承载不了**——
一张讲"一个酶系统由哪三部分组成"，一张讲"省下的时间在左边、还回去的在右边"。
其余章节的照片（药明康德/晶泰/英矽智能的园区、实验室、临床里程碑新闻图）
本身就是正文的证据对象，不该被图替掉。

图上**不写任何数字与日期**（D-22）：20 万/3,500/20/1 那串、NCT 编号、
各期启动与预计结束日期，全都是可核查的量化断言，已经带来源地活在正文的
fact_strip 与表格里。烧进图片就绕过了 R-02——图片没有"图源"链接可点。
"""
import os

import _common

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = os.path.join(ROOT, ".probe", "drawn")

# 主题 indigo-coral，抄 web/src/tokens/index.ts
BG = "#F7F6F3"
SURFACE = "#E8EAF1"
INK = "#1A1C22"
MUTED = "#5E626E"
RULE = "#D8DBE4"
INDIGO = "#3D4E8C"      # primary
CORAL = "#C24E1E"       # accent
SOFT = "#DFE3EF"

font, canvas, label, leader = _common.make(
    {"bg": BG, "ink": INK, "accent": INDIGO})


def _box(d, x, y, w, h, edge, fill=BG, width=2, radius=12):
    d.rounded_rectangle([x, y, x + w, y + h], radius=radius,
                        fill=fill, outline=edge, width=width)


def art_parts():
    """第一章。这一章的全部任务是**把传闻纠正回它本来的形状**：
    发现的是"一个此前未被刻画的酶系统"，不是药。

    版式上三段必须**画在同一条基因组线上**——第一版把标签框悬在轴线上方、
    重复单元又画到轴线底下，读者看不出那串小方块就是③。
    现在改成：轴线本身就是位置，三段是轴上的三个色块，名字用引线拉到上方。
    图上不写规模数字与日期（D-22），那些在正文里逐条带来源。"""
    img, d = canvas()
    label(d, (750, 92), u"ART：一个功能未知的酶系统，由三段组成", 34, INK, anchor="ma")
    label(d, (750, 140), u"三段都在同一段噬菌体 DNA 上，彼此相邻", 22, MUTED, anchor="ma")

    axis_y, axis_h = 400, 46
    d.rectangle([150, axis_y, 1350, axis_y + axis_h], fill=SURFACE, outline=RULE, width=2)

    segs = [(180, 250, INDIGO, u"① 逆转录酶", u"把 RNA 抄成 DNA 的一类酶"),
            (450, 170, INDIGO, u"② 伴侣基因", u"紧挨着它的伙伴基因\n功能同样未被刻画"),
            (640, 660, CORAL, u"③ 重复序列阵列", u"一长段间隔均匀的非编码重复\n这就是它「像 CRISPR」的地方")]
    for x, w, edge, name, note in segs:
        d.rectangle([x, axis_y, x + w, axis_y + axis_h], fill=SOFT, outline=edge, width=3)
        cx = x + w / 2
        # ③ 用一排竖条表示"重复单元"，直接画在轴上，不再另起一行
        if edge is CORAL:
            n = 12
            uw = w / n
            for i in range(n):
                bx = x + i * uw + 3
                d.rectangle([bx, axis_y + 6, bx + uw - 6, axis_y + axis_h - 6],
                            fill=SURFACE, outline=edge, width=2)
        d.line([(cx, axis_y - 8), (cx, axis_y - 46)], fill=edge, width=2)
        label(d, (cx, axis_y - 78), name, 26, edge, anchor="mm")
        for li, line in enumerate(note.split(u"\n")):
            label(d, (cx, axis_y - 42 + 0 + 96 + li * 30), line, 21, MUTED, anchor="mm")

    d.line([(150, axis_y + axis_h + 46), (1350, axis_y + axis_h + 46)], fill=RULE, width=2)
    label(d, (750, axis_y + axis_h + 66),
          u"原话：「我们还不知道它的功能」——理解 ART 主要功能的工作仍在进行",
          24, CORAL, anchor="ma")

    # 底部对照：起点 → 成品，中间那一步才是"药"与"传闻"的差距
    y2 = 700
    label(d, (180, y2), u"同一个起点形状", 23, MUTED, anchor="la")
    _box(d, 180, y2 + 40, 470, 92, INDIGO)
    label(d, (415, y2 + 86), u"CRISPR 最初也只是\n细菌 DNA 里一段不寻常的重复序列",
          22, INK, anchor="mm")
    _box(d, 850, y2 + 40, 470, 92, INDIGO)
    label(d, (1085, y2 + 86), u"多年之后才成为\n基因编辑类药物的基础", 22, INK, anchor="mm")
    d.line([(660, y2 + 86), (840, y2 + 86)], fill=MUTED, width=3)
    d.polygon([(830, y2 + 78), (830, y2 + 94), (846, y2 + 86)], fill=MUTED)
    label(d, (750, y2 + 158), u"中间隔着的是「被理解」这一步", 22, MUTED, anchor="ma")

    label(d, (750, 906),
          u"按正文对官方发布与 pre-print 的转述绘制；图上刻意不写规模数字与日期——"
          u"那些走正文里带来源的条目", 21, MUTED, anchor="ma")
    return img


def bottleneck_move():
    """第二章。全篇论点的形状图：**左边变便宜，右边一分没让**。
    照片在这里毫无用处——没有哪张照片能拍"瓶颈搬移"。
    刻意不画坐标、不写月数与年份：那些数字在正文的 fact_strip 里逐条带来源，
    画进图里就成了一张点不开来源的图表（R-02）。"""
    img, d = canvas()
    label(d, (750, 92), u"省下来的是算力，没省的是验证", 34, INK, anchor="ma")

    lanes = [
        (u"假设生成端", 0.34, INDIGO, u"扫描全库、排候选、各出一份人类可读报告", u"变便宜了"),
        (u"验证端", 1.00, CORAL, u"细胞 → 动物 → I/II/III 期 → 审评 → 准入", u"一格没让"),
    ]
    x0, full_w = 300, 980
    y = 210
    for name, ratio, edge, note, tag in lanes:
        _box(d, 150, y, 130, 130, RULE, fill=BG, width=2)
        label(d, (215, y + 65), name, 24, INK, anchor="mm")
        w = full_w * ratio
        _box(d, x0, y, w, 130, edge, fill=SURFACE if edge is INDIGO else BG,
             width=4 if edge is CORAL else 2)
        label(d, (x0 + 26, y + 42), note, 23, INK, anchor="lm")
        label(d, (x0 + 26, y + 92), tag, 25, edge, anchor="lm")
        y += 168

    # 右边：验证端长出来的那截，正是"要测的东西变多"
    d.line([(x0 + full_w * 0.34, y - 12), (x0 + full_w * 0.34, y + 40)], fill=MUTED, width=2)
    label(d, (x0 + full_w * 0.34 + 8, y + 4),
          u"左边多产出的每一份假设，都要在右边排队", 22, MUTED, anchor="lm")

    y2 = y + 76
    _box(d, 150, y2, 1200, 150, RULE, fill=BG, width=2)
    label(d, (180, y2 + 34),
          u"所以「能不能更快上市」不是一个可以回答「会 / 不会」的问题——", 25, INK, anchor="la")
    label(d, (180, y2 + 82),
          u"它问的是：瓶颈被搬走之后，压力先出现在验证队列、审评队列，还是支付准入。",
          25, INK, anchor="la")

    label(d, (750, y2 + 214),
          u"按正文的漏斗与成本论证绘制；两端的具体月数、期别与 NCT 编号见正文带来源的条目",
          21, MUTED, anchor="ma")
    return img


def main():
    if not os.path.isdir(OUT):
        os.makedirs(OUT)
    jobs = [("art_parts.png", art_parts),
            ("bottleneck_move.png", bottleneck_move)]
    for name, fn in jobs:
        p = os.path.join(OUT, name)
        fn().save(p, "PNG")
        print("%s  %d KB" % (p, os.path.getsize(p) // 1024))


if __name__ == "__main__":
    main()
