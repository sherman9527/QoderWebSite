# -*- coding: utf-8 -*-
"""两篇拆篇产物的机制示意图（D-22 通道：图上不写任何数字）。

为什么这五章非要自画：它们讲的都是**结构与取舍**，照片一张都说不清——
运营商能力栈、四笔成本的流向、频轨排队时钟、同一条消息走几百米与走五百公里的差别、
热从芯片到辐射器只有一条出路。硬配照片就会配成"一台看不出型号的笔记本"或
"一枚不像发射的火箭"（W-200 与本轮配图检索都实测过这个失败模式）。

图上不写数字（D-22）：分贝、Mbps、GW、美元、年份、百分比都是可核查的量化断言，
必须走带 source 的结构化区块；烧进图片就绕过了 R-02，也没人查得到。
「哪一层最卡」「哪一笔最贵」「哪一级是地面没有的」这类**本篇判断**用强调色标出，
并在图注写明按正文绘制。
"""
import os

import _common

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = os.path.join(ROOT, ".probe", "drawn")

# 星链的运营商之路 · orbital-midnight
B = dict(bg="#F1F3F6", surface="#E2E7EE", ink="#14171C", muted="#5C6672",
         rule="#D2D9E2", main="#16273F", hot="#2FD3C4", soft="#DCE7EF")
# 星座的物理墙 · vacuum-radiance（10-12 换过一次：原深靛紫+冷光青与同组姊妹篇两个通道都没拉开，
# G-11 判 fail；现在是深空紫 + 辐射琥珀。改主题色必须连这里一起改，图与页面不能两个色系）
P = dict(bg="#F3F2F7", surface="#E7E5EF", ink="#17161D", muted="#5F5C6E",
         rule="#DAD7E4", main="#5D1772", hot="#F2873F", soft="#E2E7F0")


def kit(c):
    font, canvas, label, _leader = _common.make({"bg": c["bg"], "ink": c["ink"], "accent": c["main"]})
    return font, canvas, label


def box(d, x, y, w, h, c, edge=None, fill=None, width=3, radius=14):
    d.rounded_rectangle([x, y, x + w, y + h], radius=radius,
                        fill=fill or c["bg"], outline=edge or c["main"], width=width)


def right_arrow(d, x1, y, x2, c, width=4):
    col = c["hot"]
    d.line([x1, y, x2 - 14, y], fill=col, width=width)
    d.polygon([(x2, y), (x2 - 16, y - 9), (x2 - 16, y + 9)], fill=col)


def down_arrow(d, x, y1, y2, c):
    col = c["muted"]
    d.line([x, y1, x, y2 - 14], fill=col, width=3)
    d.polygon([(x, y2), (x - 9, y2 - 16), (x + 9, y2 - 16)], fill=col)


# ---------------------------------------------------------------- 生意篇三张
def operator_stack():
    c = B
    font, canvas, label = kit(c)
    img, d = canvas()
    label(d, (750, 66), u"有信号不等于有经营：一张运营商的能力栈", 34, c["ink"], anchor="ma")
    label(d, (750, 118), u"越往下越是牌照之外的苦活，也是星链最缺的那几层", 23, c["muted"], anchor="ma")

    layers = [
        (u"天上：容量与波束", u"这一层它自己有", True),
        (u"落地：站址、回程与市电", u"要一国一国谈", False),
        (u"准入：牌照、普遍服务、数据合规", u"买频谱只解决其中一格", False),
        (u"经营：号码、鉴权、计费、客服、门店", u"目前多由合作运营商持有", False),
        (u"运维：全天候 SLA、故障与灾备", u"批发模式里由买方负责", False),
    ]
    y = 190
    for name, note, own in layers:
        box(d, 120, y, 900, 110, c, edge=c["hot"] if own else c["rule"],
            fill=c["surface"] if own else c["bg"], width=4 if own else 2)
        label(d, (150, y + 26), name, 26, c["ink"])
        label(d, (150, y + 68), note, 21, c["hot"] if own else c["muted"])
        y += 128

    box(d, 1060, 190, 320, 40 * 5 + 290, c, edge=c["rule"], fill=c["surface"], width=2)
    label(d, (1220, 226), u"两种活法", 27, c["main"], anchor="ma")
    label(d, (1220, 288), u"自己当完整运营商", 22, c["ink"], anchor="ma")
    d.line([1100, 330, 1340, 330], fill=c["rule"], width=2)
    label(d, (1220, 360), u"或：把容量批发给", 22, c["ink"], anchor="ma")
    label(d, (1220, 400), u"有牌照有客服有合规的一方", 21, c["ink"], anchor="ma")
    d.line([1100, 442, 1340, 442], fill=c["hot"], width=3)
    label(d, (1220, 472), u"目前证据指向后者", 23, c["hot"], anchor="ma")
    label(d, (1220, 520), u"（判断，非官方宣称）", 19, c["muted"], anchor="ma")

    box(d, 120, 690, 1260, 180, c, edge=c["rule"], fill=c["surface"], width=2)
    label(d, (750, 726), u"逐层可核查的问题只有一个：这一层谁持有", 27, c["main"], anchor="ma")
    label(d, (750, 782), u"把「革谁的命」换成「哪一层缺人」，答案就不再是口号", 22, c["ink"], anchor="ma")
    label(d, (750, 826), u"各层持有方的逐条出处见正文带来源的能力清单", 20, c["muted"], anchor="ma")
    return img, u"运营商能力栈.png"


def four_bills():
    c = B
    font, canvas, label = kit(c)
    img, d = canvas()
    label(d, (750, 66), u"一个星座的钱，分四笔流", 34, c["ink"], anchor="ma")
    label(d, (750, 118), u"只有第一笔被自家火箭压低了，后三笔谁也逃不掉", 23, c["muted"], anchor="ma")

    # 每行**手工断**，不按字数硬切：按 11 字切会把"内部化"切成"内部 / 化"。
    cols = [
        (u"造星", [u"产线化造星", u"寿命短，必须持续补网", u"单星成本定天花板"]),
        (u"发射", [u"自家运力压边际成本", u"一箭多星摊薄单价", u"运力上限=组网速度"]),
        (u"补网", [u"寿命到就得重发", u"失败与退场史都在这里", u"铱星、OneWeb 算过"]),
        (u"地面段", [u"网关站与频谱", u"每一国的落地权", u"没有技术捷径"]),
    ]
    xs = [70, 430, 790, 1150]
    for x, (title, items) in zip(xs, cols):
        box(d, x, 190, 300, 420, c, edge=c["main"])
        label(d, (x + 150, 232), title, 29, c["main"], anchor="ma")
        y = 300
        for it in items:
            d.ellipse([x + 26, y - 6, x + 37, y + 5], fill=c["hot"])
            label(d, (x + 50, y - 8), it, 21, c["ink"])
            y += 52
    for x in (370, 730, 1090):
        right_arrow(d, x, 400, x + 60, c)

    box(d, 70, 660, 1380, 200, c, edge=c["rule"], fill=c["surface"], width=2)
    label(d, (760, 698), u"和地面网络比的是「每平方公里承载多少人」，不是「谁的技术先进」", 26, c["main"], anchor="ma")
    label(d, (760, 754), u"密度高的地方地面小区永远更便宜；密度低的地方卫星是唯一选项", 23, c["ink"], anchor="ma")
    label(d, (760, 806), u"四笔钱的官方与第三方口径、以及两次失败案例，见正文带来源的时间线与价格表", 20, c["muted"], anchor="ma")
    return img, u"星座的四笔钱.png"


def orbit_clock():
    c = B
    font, canvas, label = kit(c)
    img, d = canvas()
    label(d, (750, 66), u"频轨是排队的时钟，不是下单的订单", 34, c["ink"], anchor="ma")
    label(d, (750, 118), u"申报只是拿到排队号，之后每一格都有期限与量化义务", 23, c["muted"], anchor="ma")

    steps = [u"申报\n拿到排队号", u"首星\n按期入轨", u"里程碑一\n完成一部分", u"里程碑二\n再完成一部分", u"全部兑现\n否则资源回收"]
    # 五格必须留在 1500 的画布内：上一版按 240 宽、300 步距排，
    # 最后一格右边界算到 1530，直接被画布切掉半格（眼验才发现）。
    w, pitch, x0 = 230, 276, 70
    for i, t in enumerate(steps):
        x = x0 + i * pitch
        box(d, x, 220, w, 150, c, edge=c["hot"] if i == 4 else c["main"],
            fill=c["surface"] if i == 4 else c["bg"])
        for j, ln in enumerate(t.split("\n")):
            label(d, (x + w / 2, 262 + j * 40), ln, 24, c["hot"] if i == 4 else c["ink"], anchor="ma")
        if i < 4:
            right_arrow(d, x + w + 6, 295, x + pitch - 8, c)

    label(d, (750, 430), u"三张星座各自走到哪一格，只按公开统计说", 26, c["main"], anchor="ma")
    rows = [(u"国网 / 星网", u"申报规模大，已入轨数量与计划在同一张表上对照"),
            (u"千帆（垣信）", u"组网发射已持续，节奏受运力约束"),
            (u"鸿鹄-3", u"申报与试验阶段，公开可核的入轨数有限")]
    y = 480
    for name, note in rows:
        box(d, 120, y, 1160, 84, c, edge=c["rule"], fill=c["surface"], width=2)
        label(d, (150, y + 26), name, 25, c["main"])
        label(d, (430, y + 30), note, 22, c["ink"])
        y += 96

    box(d, 120, 762, 1160, 130, c, edge=c["hot"], fill=c["bg"], width=3)
    label(d, (700, 800), u"公认瓶颈写在入轨速度上，不写在概念上", 25, c["hot"], anchor="ma")
    label(d, (700, 852), u"具体数量、日期与统计口径全部在正文表格与时间线里，图上不重复", 19, c["muted"], anchor="ma")
    return img, u"频轨排队时钟.png"


# ---------------------------------------------------------------- 物理篇二张
def two_paths():
    c = P
    font, canvas, label = kit(c)
    img, d = canvas()
    label(d, (750, 64), u"同一条消息的两条路：几百米，与几百公里", 33, c["ink"], anchor="ma")
    label(d, (750, 116), u"距离不是「慢一点」，它改变的是整条链路还剩多少余量", 22, c["muted"], anchor="ma")

    # 左：地面小区
    box(d, 80, 180, 620, 470, c, edge=c["rule"], fill=c["surface"], width=2)
    label(d, (390, 214), u"地面基站", 27, c["main"], anchor="ma")
    # 桅杆要画成"杆 + 天线头"。第一版在杆顶放了个三角形，读起来是一支向上的箭头，
    # 和旁边那条横向箭头打架——读者会以为图上指了两件事。
    d.rectangle([150, 476, 162, 560], fill=c["main"])
    d.ellipse([145, 452, 167, 474], outline=c["main"], width=3)
    d.rectangle([520, 500, 600, 545], fill=c["main"])
    right_arrow(d, 180, 520, 510, c)
    label(d, (345, 486), u"几百米", 22, c["hot"], anchor="ma")
    label(d, (156, 578), u"基站", 19, c["muted"], anchor="ma")
    label(d, (560, 578), u"手机", 19, c["muted"], anchor="ma")
    label(d, (390, 616), u"障碍是密度：靠分裂小区与干扰协调解决", 21, c["ink"], anchor="ma")
    label(d, (390, 300), u"手机功率几乎全用在数据上", 22, c["ink"], anchor="ma")
    label(d, (390, 348), u"上行通常不是问题", 22, c["ink"], anchor="ma")

    # 右：LEO
    box(d, 740, 180, 620, 470, c, edge=c["main"])
    label(d, (1050, 214), u"低轨卫星", 27, c["main"], anchor="ma")
    d.ellipse([980, 260, 1120, 330], outline=c["main"], width=3)
    d.ellipse([1040, 285, 1062, 307], fill=c["hot"])
    d.rectangle([1010, 500, 1090, 545], fill=c["main"])
    label(d, (1050, 578), u"手机", 19, c["muted"], anchor="ma")
    down_arrow(d, 1051, 335, 495, c)
    label(d, (1130, 410), u"几百到一千多公里", 21, c["hot"])
    label(d, (1050, 616), u"障碍是预算与几何：掠过、切换、低仰角遮挡", 20, c["ink"], anchor="ma")

    box(d, 80, 680, 1280, 190, c, edge=c["rule"], fill=c["surface"], width=2)
    label(d, (720, 716), u"于是瓶颈换了位置：星上限制是上行，地面限制是密度", 26, c["hot"], anchor="ma")
    label(d, (720, 772), u"手机发不出去，比卫星下不来更早发生；而波束再密也追不上体育馆里的人头", 21, c["ink"], anchor="ma")
    label(d, (720, 820), u"分贝数、倍率与实测口径全部在正文带来源的段落与图里，图上不写", 19, c["muted"], anchor="ma")
    return img, u"两条路径的预算.png"


def heat_one_way():
    c = P
    font, canvas, label = kit(c)
    img, d = canvas()
    label(d, (750, 64), u"热的出路只有一条：里面靠搬运，外面只能辐射", 32, c["ink"], anchor="ma")
    label(d, (750, 116), u"真空切断的是传导与对流，不是「散热」这件事本身", 22, c["muted"], anchor="ma")

    box(d, 100, 200, 420, 200, c, edge=c["main"])
    label(d, (310, 240), u"芯片与功放", 26, c["main"], anchor="ma")
    label(d, (310, 292), u"废热在这里产生", 21, c["ink"], anchor="ma")
    label(d, (310, 336), u"直流到射频的效率决定废热多少", 19, c["muted"], anchor="ma")

    box(d, 560, 200, 380, 200, c, edge=c["rule"], fill=c["surface"], width=2)
    label(d, (750, 240), u"内部：可以搬", 26, c["main"], anchor="ma")
    label(d, (750, 292), u"热管 / 均温板 / 泵驱动回路", 20, c["ink"], anchor="ma")
    label(d, (750, 336), u"这一级液体和相变都还在工作", 19, c["muted"], anchor="ma")

    box(d, 980, 200, 380, 200, c, edge=c["hot"], width=4)
    label(d, (1170, 240), u"外部：只能辐射", 26, c["hot"], anchor="ma")
    label(d, (1170, 292), u"辐射器面积 × 温度四次方", 20, c["ink"], anchor="ma")
    label(d, (1170, 336), u"没有空气可以带走热量", 19, c["muted"], anchor="ma")

    right_arrow(d, 526, 300, 554, c)
    right_arrow(d, 946, 300, 974, c)

    box(d, 100, 450, 620, 200, c, edge=c["rule"], fill=c["surface"], width=2)
    label(d, (410, 486), u"取舍一：想多排就得烧得更烫", 25, c["ink"], anchor="ma")
    label(d, (410, 536), u"温度上去排得多，但器件寿命与太阳翼效率先撑不住", 20, c["muted"], anchor="ma")
    label(d, (410, 580), u"所以辐射器温度是被反推出来的，不是被选出来的", 20, c["muted"], anchor="ma")

    box(d, 760, 450, 600, 200, c, edge=c["rule"], fill=c["surface"], width=2)
    label(d, (1060, 486), u"取舍二：涂层两头不能都要", 25, c["ink"], anchor="ma")
    label(d, (1060, 536), u"红外要发射率高（往外扔），太阳吸收要低（别晒热）", 20, c["muted"], anchor="ma")
    label(d, (1060, 580), u"这是一对光谱指标，不是颜色审美", 20, c["muted"], anchor="ma")

    box(d, 100, 690, 1260, 180, c, edge=c["main"])
    label(d, (730, 726), u"所以「太空没法散热」这句话错了：能散，只是只有一条路且有上限", 26, c["main"], anchor="ma")
    label(d, (730, 780), u"工程上的解法是把峰值功耗排到不冲突的时间窗，并给热容留缓冲", 21, c["ink"], anchor="ma")
    label(d, (730, 826), u"具体瓦数、面积、温度与涂层指标见正文带来源的表格；图上刻意不写", 19, c["muted"], anchor="ma")
    return img, u"热的唯一出路.png"


def main():
    if not os.path.isdir(OUT):
        os.makedirs(OUT)
    for fn in (operator_stack, four_bills, orbit_clock, two_paths, heat_one_way):
        img, name = fn()
        path = os.path.join(OUT, name)
        img.save(path, "PNG", optimize=True)
        print("已出图 %s（%dx%d）" % (path, img.width, img.height))


if __name__ == "__main__":
    main()
