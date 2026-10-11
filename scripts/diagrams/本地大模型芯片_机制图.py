# -*- coding: utf-8 -*-
"""四章的配图替换：照片说不清机制，就自画（D-22 通道）。

为什么这四章非要换：`audit_images.py` 报「全部合格」——它量的是点名、空章与复用，
量不到「一张看不出型号的笔记本」撑不撑得起这一章。人眼过联络表时这四张全是
通用笔记本渲染图或图库剪贴画，而四章讲的分别是：搬运与容量的分工、薄是怎么删出来的、
三笔钱各自落在哪个时间点、比数字前要对齐哪四项。照片一张都说不清，硬配只会配出
一台看不出区别的笔记本（骁龙笔电篇同样的处置）。

图上**不写任何数字**（D-22）：带宽、容量、瓦特、售价、tokens/s 都是可核查的量化断言，
必须走带 source 的结构化区块。判断（哪一条是瓶颈、哪一层被删）画在图上，
并在图注写明按正文绘制。
"""
import os

import _common

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = os.path.join(ROOT, ".probe", "drawn")

BG = "#F2F4F1"
SURFACE = "#E6EAE6"
INK = "#171A17"
MUTED = "#5E6660"
RULE = "#D5DBD6"
GREEN = "#125912"
COPPER = "#C87137"
SOFT = "#DFE9DC"

font, canvas, label, leader = _common.make({"bg": BG, "ink": INK, "accent": GREEN})


def _box(d, x, y, w, h, edge, fill=BG, width=3, radius=14):
    d.rounded_rectangle([x, y, x + w, y + h], radius=radius, fill=fill, outline=edge, width=width)


def _arrow(d, x1, y, x2, color=None, width=4):
    c = color or MUTED
    d.line([x1, y, x2 - 14, y], fill=c, width=width)
    d.polygon([(x2, y), (x2 - 16, y - 9), (x2 - 16, y + 9)], fill=c)


def _down(d, x, y1, y2, color=None, width=4):
    c = color or MUTED
    d.line([x, y1, x, y2 - 14], fill=c, width=width)
    d.polygon([(x, y2), (x - 9, y2 - 16), (x + 9, y2 - 16)], fill=c)


def decode_is搬运():
    """why-igpu-works：本地对话走的是「搬」这条路，不是「算」这条路。"""
    img, d = canvas()
    label(d, (750, 76), u"解码时每生成一个字，都要把权重重搬一遍", 33, INK, anchor="ma")
    label(d, (750, 126), u"所以三样东西各管一件事，管不到别人那格", 24, MUTED, anchor="ma")

    _box(d, 40, 210, 400, 330, GREEN)
    label(d, (240, 250), u"内存池", 30, GREEN, anchor="ma")
    label(d, (240, 306), u"容量决定", 25, INK, anchor="ma")
    label(d, (240, 350), u"装不装得下", 25, INK, anchor="ma")
    label(d, (240, 412), u"装不下就得推回主存", 23, MUTED, anchor="ma")
    label(d, (240, 456), u"那条高带宽总线当场作废", 23, MUTED, anchor="ma")

    _box(d, 550, 210, 400, 330, GREEN)
    label(d, (750, 250), u"搬运通道", 30, GREEN, anchor="ma")
    label(d, (750, 306), u"带宽决定", 25, INK, anchor="ma")
    label(d, (750, 350), u"每秒能搬多少", 25, INK, anchor="ma")
    label(d, (750, 412), u"核显与 CPU 共用这一段", 23, MUTED, anchor="ma")
    label(d, (750, 456), u"显示还要再占一层", 23, MUTED, anchor="ma")

    _box(d, 1060, 210, 400, 330, RULE)
    label(d, (1260, 250), u"计算单元", 30, MUTED, anchor="ma")
    label(d, (1260, 306), u"算力决定", 25, INK, anchor="ma")
    label(d, (1260, 350), u"一次能算多少", 25, INK, anchor="ma")
    label(d, (1260, 412), u"长提示词那一下才归它管", 23, MUTED, anchor="ma")
    label(d, (1260, 456), u"解码时它大多闲着", 23, MUTED, anchor="ma")

    _arrow(d, 448, 375, 542)
    _arrow(d, 958, 375, 1052)

    _box(d, 40, 600, 1420, 260, RULE, fill=SURFACE, width=2)
    label(d, (750, 638), u"本地对话走的是中间那一格", 29, COPPER, anchor="ma")
    label(d, (750, 700), u"比较的顺序是「同一个模型谁装得下」，不是「谁的跑分高」", 25, INK, anchor="ma")
    label(d, (750, 748), u"再堆算力不会更快；把通道拓宽、或让模型塞得进去，才会", 25, INK, anchor="ma")
    label(d, (750, 806), u"这就是核显能跑本地大模型的全部理由，也是它的全部边界", 23, MUTED, anchor="ma")
    return img, u"解码是搬运不是计算.png"


def thin_is_deletion():
    """thin-and-light：薄不是磨出来的，是删掉三样东西换来的。"""
    img, d = canvas()
    label(d, (750, 76), u"厚度从哪来：独显机上有三层，SoC 方案把它们删了", 32, INK, anchor="ma")
    label(d, (750, 126), u"删掉的同时，也把散热的余量一起删了", 24, MUTED, anchor="ma")

    rows = [
        (u"独立显存颗粒与它的供电", u"少一层板、少一组供电",
         u"颗粒焊在卡上，占板面也占厚度", u"这一层是三家的共同省法"),
        (u"独显那一级供电模组", u"整机功耗上限由芯片自己定",
         u"独显的瓦数是加上去的一段", u"SoC 的瓦数是整台的上限"),
        (u"独显那颗风扇与热管的余量", u"持续满载时先掉的是频率",
         u"出风通道与热管空间一起腾出来", u"代价与收益记在同一条账上"),
    ]
    y = 200
    for i, (what, gain, lose, note) in enumerate(rows):
        _box(d, 40, y, 660, 130, RULE, fill=SURFACE, width=2)
        label(d, (70, y + 34), u"删掉 · " + what, 26, INK)
        label(d, (70, y + 82), lose, 22, MUTED)
        _arrow(d, 716, y + 65, 800, color=COPPER)
        _box(d, 812, y, 648, 130, GREEN if i < 2 else COPPER)
        label(d, (1136, y + 40), gain, 26, GREEN if i < 2 else COPPER, anchor="ma")
        label(d, (1136, y + 88), note, 22, MUTED, anchor="ma")
        y += 160

    _box(d, 40, 700, 1420, 170, RULE, fill=SURFACE, width=2)
    label(d, (750, 738), u"所以「薄」不是一句赞美，是一张删了什么、留下什么的清单", 27, INK, anchor="ma")
    label(d, (750, 794), u"三台都还有风扇；被删掉的是余量，于是曲线变成每瓦频率斜率很陡", 24, MUTED, anchor="ma")
    return img, u"薄是删出来的.png"


def three_bills():
    """money：三笔钱落在三个不同的时间点，最容易只算第一笔。"""
    img, d = canvas()
    label(d, (750, 76), u"这台机器的钱，分三次付", 34, INK, anchor="ma")
    label(d, (750, 126), u"下单那一次最贵，但也最容易被单独比较", 24, MUTED, anchor="ma")

    d.line([120, 300, 1380, 300], fill=RULE, width=4)
    cols = [
        (240, u"下单时", [u"机型差价", u"内存容量一次定死", u"焊在主板上，错过就得整台换"]),
        (750, u"使用时", [u"电与噪音", u"长时间满载靠风扇顶", u"首次下载，体积随量化档涨"]),
        (1260, u"出手时", [u"残值", u"只有第三方口径可引", u"新形态还没有公开二手统计"]),
    ]
    for x, title, items in cols:
        d.ellipse([x - 12, 288, x + 12, 312], fill=GREEN)
        label(d, (x, 200), title, 30, GREEN, anchor="ma")
        y = 360
        for it in items:
            d.ellipse([x - 132, y - 8, x - 120, y + 4], fill=COPPER)
            label(d, (x - 108, y - 7), it, 23, INK)
            y += 62

    _box(d, 40, 620, 1420, 250, RULE, fill=SURFACE, width=2)
    label(d, (750, 658), u"三笔钱里，只有第二笔三家几乎一样", 28, COPPER, anchor="ma")
    label(d, (750, 716), u"电费是「功耗 × 小时 × 电价」一条乘法，量级远小于机型之间几千到上万的差", 24, INK, anchor="ma")
    label(d, (750, 762), u"第一笔里最容易被漏掉的是内存档位；第三笔只能引第三方口径，本篇不自己估", 24, INK, anchor="ma")
    label(d, (750, 812), u"逐条官方售价、差价与折旧口径，见正文带来源的价格表", 22, MUTED, anchor="ma")
    return img, u"三笔钱三个时间点.png"


def align_four_before_comparing():
    """head-to-head：四个口径不对齐，两边的数就不是同一件事。"""
    img, d = canvas()
    label(d, (750, 76), u"两个吞吐数字能比吗：先过四道门", 34, INK, anchor="ma")
    label(d, (750, 126), u"任何一道没过，这两张图就不该画进同一张", 24, MUTED, anchor="ma")

    gates = [
        (u"阶段", u"预填充还是解码", u"独显赢在前者，统一内存赢在后者"),
        (u"并发", u"单流还是多路", u"批量吞吐不是打字时的手感"),
        (u"精度档", u"FP4／FP8／FP16／INT8", u"是否含稀疏加速，各厂自己挑"),
        (u"框架版本", u"驱动与运行时那一版", u"名字相同不等于测量点相同"),
    ]
    y = 200
    for name, q, note in gates:
        _box(d, 40, y, 300, 120, GREEN)
        label(d, (190, y + 44), name, 29, GREEN, anchor="ma")
        label(d, (368, y + 24), u"这一道问的是：" + q, 26, INK)
        label(d, (368, y + 74), note, 23, MUTED)
        y += 140

    _box(d, 1040, 200, 420, 520, RULE, fill=SURFACE, width=2)
    label(d, (1250, 250), u"四道门全过", 28, GREEN, anchor="ma")
    label(d, (1250, 316), u"才进同一张对比图", 25, INK, anchor="ma")
    label(d, (1250, 396), u"过不了就各说各的", 25, INK, anchor="ma")
    label(d, (1250, 452), u"不做综合排名", 25, INK, anchor="ma")
    label(d, (1250, 540), u"算力那一栏尤其不能画等号", 22, COPPER, anchor="ma")
    label(d, (1250, 588), u"PFLOP、TOPS、TFLOPS 互不换算", 22, MUTED, anchor="ma")
    label(d, (1250, 640), u"倍数由厂商自己挑", 22, MUTED, anchor="ma")

    _box(d, 40, 760, 1420, 120, RULE, fill=BG, width=2)
    label(d, (750, 800), u"查不到的格子写「未公开」，不拿上一代或邻近型号顶替", 26, INK, anchor="ma")
    return img, u"比数字前先对齐四项.png"


def main():
    if not os.path.isdir(OUT):
        os.makedirs(OUT)
    for fn in (decode_is搬运, thin_is_deletion, three_bills, align_four_before_comparing):
        img, name = fn()
        path = os.path.join(OUT, name)
        img.save(path, "PNG", optimize=True)
        print("已出图 %s（%dx%d）" % (path, img.width, img.height))


if __name__ == "__main__":
    main()
