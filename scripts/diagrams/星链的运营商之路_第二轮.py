# -*- coding: utf-8 -*-
"""生意篇补的第二轮两张（配图数下限是 8 张，每章一张只有 6 张）。

选这两张不是因为"要凑数"，而是这两处正文各有一个**只有画出来才看得清**的结构：
· 直连手机的两种合同结构——谁握着用户关系、谁握有牌照，决定了"革谁的命"这句话成不成立；
· 补网是一条常流而不是一次性投资——寿命一到就得重发，这个循环才是星座成本的真正形状。
D-22：图上不写任何数字。金额、寿命、速率、数量一律留在正文带来源的区块里。
"""
import os

import _common

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = os.path.join(ROOT, ".probe", "drawn")
C = dict(bg="#F1F3F6", surface="#E2E7EE", ink="#14171C", muted="#5C6672",
         rule="#D2D9E2", main="#16273F", hot="#2FD3C4", soft="#DCE7EF")

font, canvas, label, _leader = _common.make({"bg": C["bg"], "ink": C["ink"], "accent": C["main"]})


def box(d, x, y, w, h, edge=None, fill=None, width=3, radius=14):
    d.rounded_rectangle([x, y, x + w, y + h], radius=radius,
                        fill=fill or C["bg"], outline=edge or C["main"], width=width)


def arrow_r(d, x1, y, x2, col=None):
    c = col or C["hot"]
    d.line([x1, y, x2 - 14, y], fill=c, width=4)
    d.polygon([(x2, y), (x2 - 16, y - 9), (x2 - 16, y + 9)], fill=c)


def two_contracts():
    img, d = canvas()
    label(d, (750, 64), u"直连手机有两种签法，革的不是同一家的命", 33, C["ink"], anchor="ma")
    label(d, (750, 116), u"看谁握着用户关系，就知道竞争发生在哪一层", 22, C["muted"], anchor="ma")

    box(d, 90, 190, 600, 420, edge=C["rule"], fill=C["surface"], width=2)
    label(d, (390, 232), u"零售：自己面向用户", 28, C["main"], anchor="ma")
    y = 300
    for t in [u"自己收费、自己出账单", u"自己承担客服与合规", u"要一国的经营牌照", u"用户换网 = 换一家运营商"]:
        d.ellipse([130, y - 6, 141, y + 5], fill=C["muted"])
        label(d, (154, y - 8), t, 22, C["ink"])
        y += 58
    label(d, (390, 540), u"这一种才叫「革运营商的命」", 22, C["muted"], anchor="ma")

    box(d, 760, 190, 600, 420, edge=C["hot"], width=4)
    label(d, (1060, 232), u"批发：把容量卖给持牌方", 28, C["main"], anchor="ma")
    y = 300
    for t in [u"用户仍注册在运营商名下", u"账单、客服、合规归运营商", u"卫星方只负责天上这一段", u"用户换网 = 换一家运营商，不换卫星"]:
        d.ellipse([800, y - 6, 811, y + 5], fill=C["hot"])
        label(d, (824, y - 8), t, 22, C["ink"])
        y += 58
    label(d, (1060, 540), u"这一种是「多了一个上游供应商」", 22, C["hot"], anchor="ma")

    box(d, 90, 650, 1270, 220, edge=C["rule"], fill=C["surface"], width=2)
    label(d, (725, 688), u"所以判断只看一件事：用户关系在谁手里", 27, C["main"], anchor="ma")
    label(d, (725, 744), u"关系在运营商手里，卫星就是上游；关系在自己手里，才是同场竞争", 22, C["ink"], anchor="ma")
    label(d, (725, 792), u"本篇按公开公告判断当前落在哪一侧；逐条公告与合同结构描述见正文带来源的清单", 19, C["muted"], anchor="ma")
    label(d, (725, 832), u"图上不写任何金额、用户数与速率", 19, C["muted"], anchor="ma")
    return img, u"两种签法.png"


def replenish_loop():
    img, d = canvas()
    label(d, (750, 64), u"补网不是一次性投资，是一条常流", 33, C["ink"], anchor="ma")
    label(d, (750, 116), u"寿命一到就得重发——这条循环决定了星座的长期成本形状", 22, C["muted"], anchor="ma")

    # 上一版把环放到 cy=470/r=210：底部框的下沿 750 与箭头环 758 一起压进了 736 起的说明带。
    # 现在最下沿 710 + 箭头尖 730，说明带从 748 起，留 18px 缝。
    nodes = [u"造", u"发", u"用", u"退役"]
    cx, cy, r = 750, 440, 200
    import math
    for i, t in enumerate(nodes):
        a = -math.pi / 2 + i * math.pi / 2
        x = cx + r * math.cos(a)
        y = cy + r * math.sin(a)
        box(d, x - 120, y - 70, 240, 140, edge=C["hot"] if t == u"退役" else C["main"])
        label(d, (x, y - 22), t, 30, C["hot"] if t == u"退役" else C["main"], anchor="ma")
        hint = {u"造": u"产线化，成本按颗计", u"发": u"运力上限就是组网上限",
                u"用": u"容量在轨折旧，越用越少", u"退役": u"再入与替换，回到「造」"}[t]
        label(d, (x, y + 26), hint, 19, C["muted"], anchor="ma")
    for i in range(4):
        a0 = -math.pi / 2 + i * math.pi / 2 + 0.62
        a1 = -math.pi / 2 + (i + 1) * math.pi / 2 - 0.62
        pts = [(cx + (r + 78) * math.cos(a0 + (a1 - a0) * k / 24.0),
                cy + (r + 78) * math.sin(a0 + (a1 - a0) * k / 24.0)) for k in range(25)]
        d.line(pts, fill=C["rule"], width=3)
        ex, ey = pts[-1]
        px, py = pts[-2]
        dx, dy = ex - px, ey - py
        n = (dx * dx + dy * dy) ** 0.5 or 1.0
        dx, dy = dx / n, dy / n
        d.polygon([(ex + dx * 12, ey + dy * 12), (ex - dy * 8, ey + dx * 8), (ex + dy * 8, ey - dx * 8)],
                  fill=C["muted"])

    # 中心可用宽度只有左右两框之间那 180px：上一版放了两行长句，直接压到框上。
    label(d, (750, 462), u"没有出口", 26, C["ink"], anchor="ma")

    box(d, 90, 748, 1270, 154, edge=C["rule"], fill=C["surface"], width=2)
    label(d, (725, 782), u"和地面网络比的是「持续供给能力」，不是「一次建成」", 25, C["main"], anchor="ma")
    label(d, (725, 828), u"停一年，天上就少一年——这条循环没有终点，也没有退出选项", 21, C["hot"], anchor="ma")
    label(d, (725, 872), u"寿命年数、补网速率与两次失败案例的具体数字，见正文带来源的时间线与价格表", 19, C["muted"], anchor="ma")
    return img, u"补网是常流.png"


def main():
    if not os.path.isdir(OUT):
        os.makedirs(OUT)
    for fn in (two_contracts, replenish_loop):
        img, name = fn()
        p = os.path.join(OUT, name)
        img.save(p, "PNG", optimize=True)
        print("已出图 %s（%dx%d）" % (p, img.width, img.height))


if __name__ == "__main__":
    main()
