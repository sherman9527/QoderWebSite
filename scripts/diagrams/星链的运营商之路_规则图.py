# -*- coding: utf-8 -*-
"""生意篇补的三张机制图（D-22：图上不写任何数字）。

为什么这三章只能自画：本轮配图检索给这三章的照片分别是
LED 点阵屏（挂在「频谱拍卖」下）、中国检测公司的 FCC 认证广告（挂在「FCC 案卷」下）、
以及一张名实不符的发射照。三章讲的都不是某个物体，而是**规则的形状**：
一条业务线不是一个产品、两种牌照身份不是一张纸、六个信号各自要越哪条线。
照片说不清规则，硬配只会配出一张看不出所以然的图（W-200 与本轮都实测过）。
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


def arrow_r(d, x1, y, x2):
    d.line([x1, y, x2 - 14, y], fill=C["hot"], width=4)
    d.polygon([(x2, y), (x2 - 16, y - 9), (x2 - 16, y + 9)], fill=C["hot"])


def one_satellite_four_shelves():
    img, d = canvas()
    label(d, (750, 64), u"「星链」不是一个产品，是四条业务线", 34, C["ink"], anchor="ma")
    label(d, (750, 116), u"问「它革谁的命」之前，先问说的是哪一条", 22, C["muted"], anchor="ma")

    cols = [
        (u"住宅宽带", u"自己面向消费者", u"对手是固网与移动家庭套餐"),
        (u"企业 / 海事 / 航空", u"高单价、地面够不着", u"对手是专用网与卫星电视"),
        (u"移动性回传", u"卖给运营商，不面向用户", u"对手是光纤与微波"),
        (u"直连手机", u"容量批发给持牌运营商", u"对手是地面小区的余量"),
    ]
    y = 180
    for title, who, rival in cols:
        box(d, 90, y, 300, 120, edge=C["main"])
        label(d, (240, y + 24), title, 26, C["main"], anchor="ma")
        label(d, (240, y + 74), who, 20, C["ink"], anchor="ma")
        arrow_r(d, 400, y + 60, 470)
        box(d, 486, y, 830, 120, edge=C["rule"], fill=C["surface"], width=2)
        label(d, (516, y + 28), u"监管与经营身份：", 21, C["muted"])
        label(d, (516, y + 66), rival, 23, C["ink"])
        y += 148

    box(d, 90, 786, 1226, 96, edge=C["hot"], fill=C["bg"], width=3)
    label(d, (703, 816), u"四条线共用一套天上资产，但牌照、客户与对手完全不同", 25, C["hot"], anchor="ma")
    label(d, (703, 858), u"各条线的官方定义、定价与准入国清单见正文带来源的对照表", 19, C["muted"], anchor="ma")
    return img, u"星链是四条业务线.png"


def two_license_identities():
    img, d = canvas()
    label(d, (750, 64), u"同一段频率，两种业务身份", 34, C["ink"], anchor="ma")
    label(d, (750, 116), u"买了其中一种，不等于拿到另一种的经营权", 22, C["muted"], anchor="ma")

    box(d, 110, 190, 560, 330, edge=C["main"])
    label(d, (390, 230), u"地面蜂窝身份", 28, C["main"], anchor="ma")
    y = 296
    for t in [u"发给本国运营商", u"按国家划分覆盖义务", u"手机直接注册在这套编号下"]:
        d.ellipse([150, y - 6, 161, y + 5], fill=C["hot"])
        label(d, (174, y - 8), t, 22, C["ink"])
        y += 56
    label(d, (390, 470), u"这一侧的门槛是密度与站址", 21, C["muted"], anchor="ma")

    box(d, 730, 190, 560, 330, edge=C["main"])
    label(d, (1010, 230), u"卫星移动身份", 28, C["main"], anchor="ma")
    y = 296
    for t in [u"另一套业务代码与授权", u"覆盖按波束足迹画", u"落地仍要逐国批准"]:
        d.ellipse([770, y - 6, 781, y + 5], fill=C["hot"])
        label(d, (794, y - 8), t, 22, C["ink"])
        y += 56
    label(d, (1010, 470), u"这一侧的门槛是预算与准入", 21, C["muted"], anchor="ma")

    d.line([700, 200, 700, 510], fill=C["hot"], width=4)
    label(d, (700, 548), u"两者可以共用频率，但共用要协调", 24, C["hot"], anchor="ma")

    box(d, 110, 620, 1180, 250, edge=C["rule"], fill=C["surface"], width=2)
    label(d, (700, 656), u"所以「买频谱」买到的到底是什么", 27, C["main"], anchor="ma")
    label(d, (700, 712), u"一段可使用的频率权利 + 一种业务身份 + 一堆建设义务与期限", 22, C["ink"], anchor="ma")
    label(d, (700, 760), u"手机能不能合法连上它，还取决于终端支持的频段与各国的准入", 22, C["ink"], anchor="ma")
    label(d, (700, 818), u"具体频段代号、金额、审批条件与建设义务全部在正文带来源的表格里，图上不写", 19, C["muted"], anchor="ma")
    return img, u"两种牌照身份.png"


def six_scorecards():
    img, d = canvas()
    label(d, (750, 64), u"六个信号，每个都有一条改结论的线", 33, C["ink"], anchor="ma")
    label(d, (750, 116), u"结论不是信念，是可以被这六格逐季度推翻的判断", 22, C["muted"], anchor="ma")

    items = [
        (u"频谱审批", u"批了没有、附什么条件"),
        (u"合作结构", u"谁面向用户、谁持有牌照"),
        (u"单星功率", u"是否出现量级跃升"),
        (u"运力兑现", u"目标与已入轨是否对齐"),
        (u"各国准入", u"是否收紧或要求数据本地化"),
        (u"对手里程碑", u"按期发射义务是否兑现"),
    ]
    # 三列 × 400 宽必须留在 1500 内：上一版从 1150 起排，右边界 1550 直接出画布。
    xs = [60, 545, 1030]
    ys = [180, 470]
    i = 0
    for y in ys:
        for x in xs:
            title, note = items[i]
            # 卡片高度要容得下"两行说明 + 一行结论线"：上一版 220 高时
            # 第二行说明与底部 cyan 行只差 34px，字号 21 直接压字（眼验才发现）。
            box(d, x, y, 400, 240, edge=C["main"])
            label(d, (x + 200, y + 38), u"%d · %s" % (i + 1, title), 25, C["main"], anchor="ma")
            d.line([x + 40, y + 80, x + 360, y + 80], fill=C["rule"], width=2)
            for j, ln in enumerate(note.split(u"、")):
                label(d, (x + 200, y + 108 + j * 34), ln, 21, C["ink"], anchor="ma")
            label(d, (x + 200, y + 206), u"越线就改结论", 19, C["hot"], anchor="ma")
            i += 1

    box(d, 90, 730, 1320, 140, edge=C["rule"], fill=C["surface"], width=2)
    label(d, (750, 768), u"六格里有两格最容易读混", 26, C["main"], anchor="ma")
    label(d, (750, 820), u"「官方目标」与「已实现」不是同一格；「申报规模」与「已入轨」也不是", 21, C["ink"], anchor="ma")
    label(d, (750, 856), u"每格的当前读数、来源与统计日期见正文带来源的清单", 19, C["muted"], anchor="ma")
    return img, u"六个信号记分卡.png"


def main():
    if not os.path.isdir(OUT):
        os.makedirs(OUT)
    for fn in (one_satellite_four_shelves, two_license_identities, six_scorecards):
        img, name = fn()
        path = os.path.join(OUT, name)
        img.save(path, "PNG", optimize=True)
        print("已出图 %s（%dx%d）" % (path, img.width, img.height))


if __name__ == "__main__":
    main()
