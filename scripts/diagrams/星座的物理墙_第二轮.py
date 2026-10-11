# -*- coding: utf-8 -*-
"""《星座的物理墙》补的第二轮五张（配图数下限 8 张，每章一张只有 5 张）。

凑数不是理由，这三处各有一个**只有画出来才看得清**的结构：
· 「容量 / 覆盖 / 并发」是三个不同的量，正文里最容易被人拿一个去顶另一个；
· 太阳翼的功率是**一路扣下来的**，账面值与手上可用差着四道，而阴影期决定要按哪一档配；
· 三条式子各锁一条硬边界，缺输入时唯一诚实的答案是「算不出来」。

后两张是**替换**来的，不是新增：原来那两张引用图一张登记在内容农场镜像页上
（greenbeltmapboise.github.io，图上有 SpaceX 水印但来源不可核），一张是媒体转述的
Release-19 幻灯片，而这一章正文写的恰恰是「认编号不认转述」。来源站不住的引用图，
不如换成有 based_on 的自画图。
D-22：图上不写任何数字。瓦、公斤、平方米、百分比一律留在正文带来源的段落里。
"""
import os

import _common

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = os.path.join(ROOT, ".probe", "drawn")
C = dict(bg="#F3F2F7", surface="#E7E5EF", ink="#17161D", muted="#5F5C6E",
         rule="#DAD7E4", main="#5D1772", hot="#F2873F", soft="#E2E7F0")

font, canvas, label, _leader = _common.make({"bg": C["bg"], "ink": C["ink"], "accent": C["main"]})


def box(d, x, y, w, h, edge=None, fill=None, width=3, radius=14):
    d.rounded_rectangle([x, y, x + w, y + h], radius=radius,
                        fill=fill or C["bg"], outline=edge or C["main"], width=width)


def arrow_r(d, x1, y, x2, col=None):
    c = col or C["hot"]
    d.line([x1, y, x2 - 16, y], fill=c, width=4)
    d.polygon([(x2, y), (x2 - 18, y - 10), (x2 - 18, y + 10)], fill=c)


def lines(d, xy, texts, size=20, color=None, lh=None, anchor="la"):
    x, y = xy
    step = lh or int(size * 1.45)
    for t in texts:
        label(d, (x, y), t, size, color or C["ink"], anchor=anchor)
        y += step
    return y


def three_rulers():
    img, d = canvas()
    label(d, (750, 64), u"容量、覆盖、并发是三把不同的尺", 33, C["ink"], anchor="ma")
    label(d, (750, 116), u"三个词各算一遍：手上有什么数、缺什么数、缺了会算出什么假数", 22, C["muted"], anchor="ma")

    cards = [
        (u"容量", [
            (u"手上有", [u"单星设计值", u"代际之间的倍率"]),
            (u"缺的是", [u"每星可用波束数", u"单波束带宽", u"每波束 EIRP"]),
            (u"所以", [u"总量只能自己乘", u"乘出来也不成立"]),
        ]),
        (u"覆盖", [
            (u"手上有", [u"波束足迹等值线", u"足迹内人口"]),
            (u"缺的是", [u"同一时刻能被", u"服务的用户数"]),
            (u"所以", [u"「覆盖多少人」", u"是几何，不是服务"]),
        ]),
        (u"并发", [
            (u"手上有", [u"订户总数", u"一条线路算一个"]),
            (u"缺的是", [u"同时在线的比例", u"波束与时窗调度"]),
            (u"所以", [u"容量不能跨波束", u"调拨给拥堵的一格"]),
        ]),
    ]
    xs = [90, 560, 1030]
    for x, (head, groups) in zip(xs, cards):
        box(d, x, 170, 430, 430, edge=C["rule"], fill=C["surface"], width=2)
        label(d, (x + 215, 202), head, 30, C["main"], anchor="ma")
        y = 262
        for tag, ts in groups:
            label(d, (x + 26, y), tag, 20, C["main"])
            y += 30
            y = lines(d, (x + 26, y), ts, 20, C["ink"], lh=29)
            y += 14

    box(d, 90, 640, 1370, 240, edge=C["rule"], fill=C["soft"], width=2)
    label(d, (775, 682), u"同一道除法，换个输入就差一个量级", 28, C["main"], anchor="ma")
    label(d, (775, 740), u"差的全是输入，不是结论——所以先对齐口径，再比数字", 22, C["ink"], anchor="ma")
    label(d, (775, 790), u"订户不等于人，覆盖不等于服务，峰值不等于此刻", 22, C["main"], anchor="ma")
    label(d, (775, 840), u"图上不写任何数量、速率与日期；逐项数字见正文带来源的口径表", 19, C["muted"], anchor="ma")
    return img, u"三把尺.png"


def power_deductions():
    img, d = canvas()
    label(d, (750, 60), u"电从哪来：从组件账面到手上可用，一路都在扣", 33, C["ink"], anchor="ma")
    label(d, (750, 110), u"扣完才是转发器、波束成形、姿控与推进能分的功率", 22, C["muted"], anchor="ma")

    nodes = [
        (u"组件账面", [u"电池片本体", u"厂商标最高档"]),
        (u"整阵", [u"基板与展开机构", u"一起算比功率"]),
        (u"入射角", [u"姿态与轨道", u"吃掉的余弦"]),
        (u"辐照与温度", [u"寿命初期标称", u"逐年往下扣"]),
    ]
    xs = [70, 350, 630, 910]
    for i, (x, (head, sub)) in enumerate(zip(xs, nodes)):
        box(d, x, 160, 240, 150, edge=C["main"])
        label(d, (x + 120, 196), head, 26, C["main"], anchor="ma")
        lines(d, (x + 120, 236), sub, 19, C["muted"], lh=27, anchor="ma")
        if i < 3:
            arrow_r(d, x + 244, 235, x + 276, C["rule"])
    box(d, 1190, 160, 240, 150, edge=C["hot"], width=4)
    label(d, (1310, 196), u"手上可用", 26, C["main"], anchor="ma")
    lines(d, (1310, 236), [u"能分的功率", u"没有官方分项"], 19, C["muted"], lh=27, anchor="ma")
    arrow_r(d, 1154, 235, 1186, C["rule"])

    label(d, (90, 372), u"阴影期决定按哪一档配", 25, C["main"])
    box(d, 90, 410, 1370, 62, edge=C["rule"], fill=C["soft"], width=2)
    d.rounded_rectangle([96, 416, 894, 466], radius=10, fill=C["hot"])
    label(d, (495, 430), u"日照：一边带负载，一边把电池回充", 21, C["main"], anchor="ma")
    label(d, (1135, 430), u"地影：只出不进", 21, C["ink"], anchor="ma")
    lines(d, (90, 496), [
        u"影的那段有多长由高度与 β 角定：β 够大可以整圈不见影，β 为零最坏。",
        u"阵列按最坏的那一圈配，不是按平均配；推进点火只能排在日照期——一点火，用户波束就得让电。",
    ], 21, C["ink"], lh=34)

    box(d, 90, 604, 1370, 204, edge=C["rule"], fill=C["surface"], width=2)
    label(d, (775, 636), u"想涨功率就得铺面积，而面积同时是三件事", 25, C["main"], anchor="ma")
    cols = [
        (u"产能", u"越大越多"),
        (u"阻力", u"越低越拖"),
        (u"体积", u"要塞进整流罩"),
    ]
    cx = [200, 775, 1350]
    for x, (t, sub) in zip(cx, cols):
        label(d, (x, 690), t, 24, C["main"], anchor="ma")
        label(d, (x, 728), sub, 21, C["ink"], anchor="ma")
    label(d, (775, 772), u"更大、更低、点得更勤，都进同一张账单", 20, C["muted"], anchor="ma")

    box(d, 90, 824, 1370, 100, edge=C["rule"], fill=C["soft"], width=2)
    label(d, (775, 852), u"单星功率不公开，分项比例是缺项——只能给量级，不能给结论", 22, C["ink"], anchor="ma")
    label(d, (775, 894), u"图上不写瓦、公斤、平方米与百分比", 19, C["muted"], anchor="ma")
    return img, u"功率扣减链.png"


def three_formulas():
    img, d = canvas()
    label(d, (750, 60), u"三条式子，各锁一条硬边界", 33, C["ink"], anchor="ma")
    label(d, (750, 110), u"它们只回答「这句话物理上可能吗」，不复算商业指标", 22, C["muted"], anchor="ma")

    rows = [
        (u"自由空间损耗", u"输入：频率 + 距离", u"锁住链路预算的下限",
         [u"距离由轨道高度加最低仰角算；缺仰角只能报区间。", u"它给的是「至少损耗这么多」，不是「只能这么多」。"]),
        (u"辐射排热上限", u"输入：面积 × 发射率 × 温度⁴", u"锁住能排掉多少热",
         [u"真空里没有对流，辐射不是「不行」，是唯一的路。", u"不扣太阳直射、地球反照与漏热，就算高了。"]),
        (u"每平方公里容量", u"输入：数量 × 单位容量 ÷ 面积", u"逼两边用同一个单位",
         [u"地面按小区算，天上按波束算，都退回带宽 × 谱效。", u"把任何一边换成「覆盖人口」，比较当场作废。"]),
    ]
    y = 160
    for head, inp, lock, notes in rows:
        box(d, 90, y, 1370, 176, edge=C["rule"], fill=C["surface"], width=2)
        box(d, 118, y + 34, 300, 108, edge=C["main"])
        label(d, (268, y + 62), head, 24, C["main"], anchor="ma")
        label(d, (268, y + 100), inp, 16, C["muted"], anchor="ma")
        arrow_r(d, 430, y + 88, 486)
        box(d, 500, y + 34, 380, 108, edge=C["hot"], width=4)
        label(d, (690, y + 76), lock, 24, C["main"], anchor="ma")
        lines(d, (916, y + 46), notes, 19, C["ink"], lh=32)
        y += 196

    box(d, 90, 764, 1370, 150, edge=C["rule"], fill=C["soft"], width=2)
    label(d, (775, 796), u"官方数字多是申报或宣传口径：备案填请求参数，授权书写许可上限，新闻稿给最好情况", 22, C["main"], anchor="ma")
    label(d, (775, 842), u"填一个猜测值，后面每一步都在替它背书；宁可写「算不出来」", 21, C["main"], anchor="ma")
    label(d, (775, 888), u"图上不写任何具体数值；可照抄的式子与出处清单在正文", 19, C["muted"], anchor="ma")
    return img, u"三条硬边界.png"


def coverage_three():
    img, d = canvas()
    label(d, (750, 60), u"覆盖、人口、同时可服务，是三件事", 33, C["ink"], anchor="ma")
    label(d, (750, 110), u"一张覆盖图只能回答第一件；后两件要波束数与调度", 22, C["muted"], anchor="ma")

    cols = [
        (u"足迹", u"怎么得到", [u"几何上看得见", u"的范围"],
         [u"备案里的等值线", u"就能画出来"], u"答：哪里看得见"),
        (u"足迹里住了多少人", u"它只是", [u"把行政区划", u"叠上去"],
         [u"可能性的上限", u"不是使用者数量"], u"答：最多多少人可能"),
        (u"同一时刻能被服务", u"卡在哪", [u"波束数 × 单波束", u"容量 ÷ 面积"],
         [u"缺波束数与调度", u"就算不出来"], u"答：真正分得到多少"),
    ]
    xs = [90, 560, 1030]
    for i, (x, (head, tag, how, gap, ans)) in enumerate(zip(xs, cols)):
        box(d, x, 170, 430, 400, edge=C["main"] if i == 2 else C["rule"],
            fill=C["surface"] if i < 2 else C["bg"], width=3 if i == 2 else 2)
        label(d, (x + 215, 206), head, 26, C["main"], anchor="ma")
        y = lines(d, (x + 215, 268), how, 22, C["ink"], lh=32, anchor="ma")
        y += 18
        label(d, (x + 215, y), tag, 19, C["muted"], anchor="ma")
        y = lines(d, (x + 215, y + 28), gap, 21, C["ink"], lh=31, anchor="ma")
        box(d, x + 30, 470, 370, 70, edge=C["hot"] if i == 2 else C["rule"], fill=C["soft"], width=3)
        label(d, (x + 215, 492), ans, 21, C["main"] if i == 2 else C["ink"], anchor="ma")
        if i < 2:
            label(d, (x + 450, 350), u"≠", 40, C["muted"], anchor="ma")

    box(d, 90, 610, 1370, 270, edge=C["rule"], fill=C["soft"], width=2)
    label(d, (775, 650), u"把第二件当成第三件，是这类说法最常见的滑法", 28, C["main"], anchor="ma")
    label(d, (775, 710), u"「覆盖 N 亿人」说的是足迹里住了多少人，不是同一时刻能被服务的人", 22, C["ink"], anchor="ma")
    label(d, (775, 758), u"一座体育馆、一场演唱会的人均需求，落在第三件上，不落在第一件上", 22, C["ink"], anchor="ma")
    label(d, (775, 812), u"图上不写任何数量、速率与人口数字；三项口径见正文带来源的对照表", 19, C["muted"], anchor="ma")
    return img, u"覆盖三件事.png"


def four_sources():
    img, d = canvas()
    label(d, (750, 60), u"四个能查的出处，各答什么、不答什么", 33, C["ink"], anchor="ma")
    label(d, (750, 110), u"四类文件都不是「此刻在轨的实际」——先问它属于哪一类", 22, C["muted"], anchor="ma")

    cards = [
        (u"频轨与轨道备案", u"申报的请求参数、协调状态", u"此刻在轨的实际",
         u"协调中的网络可改、可撤"),
        (u"规范编号（3GPP）", u"频段、信道带宽、接口要求", u"实测速率与体验",
         u"认编号，不认转述"),
        (u"热控工程手册", u"设计口径、公式与试验件参数", u"在轨工作温度",
         u"给的是怎么设计，不是跑成什么样"),
        (u"发布方官方稿", u"发布方自己的立场与承诺", u"转载里多出的数字",
         u"只取发布方页面，二手不加信"),
    ]
    pos = [(90, 170), (775, 170), (90, 470), (775, 470)]
    for (x, y), (head, can, cannot, note) in zip(pos, cards):
        box(d, x, y, 635, 260, edge=C["rule"], fill=C["surface"], width=2)
        label(d, (x + 30, y + 34), head, 26, C["main"])
        d.line([x + 30, y + 78, x + 605, y + 78], fill=C["rule"], width=2)
        label(d, (x + 30, y + 100), u"能答", 19, C["muted"])
        label(d, (x + 108, y + 100), can, 21, C["ink"])
        label(d, (x + 30, y + 148), u"不答", 19, C["muted"])
        label(d, (x + 108, y + 148), cannot, 21, C["main"])
        label(d, (x + 30, y + 200), note, 19, C["muted"])

    box(d, 90, 770, 1370, 110, edge=C["rule"], fill=C["soft"], width=2)
    label(d, (775, 800), u"备案填的是请求参数，授权书写的是许可上限，新闻稿给的是最好情况", 23, C["main"], anchor="ma")
    label(d, (775, 846), u"三者都不含此刻在轨实际——缺输入就写「算不出来」，不填猜测值", 21, C["ink"], anchor="ma")
    return img, u"四个出处.png"


def three_routes_to_power():
    img, d = canvas()
    label(d, (750, 60), u"单星功率没人公布：三条独立的路去反推", 33, C["ink"], anchor="ma")
    label(d, (750, 110), u"三条路各量一件事，交在同一个量级上；分项比例仍然全空", 22, C["muted"], anchor="ma")

    routes = [
        (u"路一 · 测光与反照", [u"从天光亮度与", u"反照率反推面积"],
         [u"能给：受照面积", u"不能给：转成多少电"]),
        (u"路二 · 已建系统折算", [u"拿现成大型阵列的", u"面积与总功率除一除"],
         [u"能给：一个可校准的", u"单位面积量级", u"不能给：这一颗的分配"]),
        (u"路三 · 厂商账面", [u"组件级的比功率", u"与单位面积出力"],
         [u"能给：上限", u"不能给：装上卫星之后"]),
    ]
    xs = [90, 560, 1030]
    for x, (head, how, caps) in zip(xs, routes):
        box(d, x, 170, 430, 340, edge=C["rule"], fill=C["surface"], width=2)
        label(d, (x + 215, 208), head, 25, C["main"], anchor="ma")
        d.line([x + 40, 250, x + 390, 250], fill=C["rule"], width=2)
        y = lines(d, (x + 215, 276), how, 22, C["ink"], lh=32, anchor="ma")
        y += 26
        lines(d, (x + 215, y), caps, 20, C["muted"], lh=30, anchor="ma")

    box(d, 90, 600, 1370, 120, edge=C["main"], width=3)
    label(d, (775, 630), u"三条路交在同一个量级——但「万瓦级」是量级，不是账面数字", 24, C["main"], anchor="ma")
    label(d, (775, 678), u"转发器、波束成形、姿控、推进各占多少，公开材料里全空；全空就写全空", 21, C["ink"], anchor="ma")

    box(d, 90, 750, 1370, 130, edge=C["rule"], fill=C["soft"], width=2)
    label(d, (775, 780), u"有一句可以当场验算：官方按「每吨多少千瓦」给轨道数据中心配功率", 23, C["main"], anchor="ma")
    label(d, (775, 826), u"它等于整星比功率的目标值，而整阵比功率贴的那条线远低于它——不用等官方给数就能判断方向", 21, C["ink"], anchor="ma")
    return img, u"三条反推路.png"


def main():
    if not os.path.isdir(OUT):
        os.makedirs(OUT)
    for fn in (three_rulers, power_deductions, three_formulas, coverage_three, four_sources,
               three_routes_to_power):
        img, name = fn()
        p = os.path.join(OUT, name)
        img.save(p, "PNG", optimize=True)
        print("saved %s (%dx%d)" % (name, img.width, img.height))


if __name__ == "__main__":
    main()
