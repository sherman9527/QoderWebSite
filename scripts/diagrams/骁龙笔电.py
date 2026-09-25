# -*- coding: utf-8 -*-
"""画 骁龙笔电 篇的四张机制示意图（示意图通道，D-22）。

为什么这篇比 MLCC 更需要示意图：词形实测四批共 38 条，活池只有两簇
（`Snapdragon X*` 与 `Surface Laptop`），要喂 11 章。而这四章本来就不是
"少一张照片"的问题——架构与功耗档的关系、生态的三层、两个价格口径之间隔着什么、
三约束取最短，照片一张都说不清。硬配只会配出一台看不出区别的笔记本。

图上**不写任何数字**（D-22）：TOPS、瓦特、售价、吞吐都是可核查的量化断言，
必须走带 source 的结构化区块，烧进图片就绕过了 R-02。
凡是"哪一块是短板""曲线在哪交叉"这类**本篇的判断**，图注里写明是按正文绘制。
"""
import os

import _common

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = os.path.join(ROOT, ".probe", "drawn")

# 主题 snapdragon-obsidian，抄 web/src/tokens/index.ts
BG = "#FAFAFC"
SURFACE = "#ECEEF4"
INK = "#141619"
MUTED = "#646B78"
RULE = "#DFE3EA"
NAVY = "#101A33"       # primary：曜石靛
MAGENTA = "#BD0598"    # accent：电光品红
SOFT = "#DDE4F0"

font, canvas, label, leader = _common.make(
    {"bg": BG, "ink": INK, "accent": NAVY})


def _box(d, x, y, w, h, edge, fill=BG, width=2, radius=12):
    d.rounded_rectangle([x, y, x + w, y + h], radius=radius,
                        fill=fill, outline=edge, width=width)


def _interp(pts, t):
    """两端都要夹住。第一版只匹配"落在某段上"的 t，落到定义域之外就返回**最后一个值**，
    于是在 t<0.02 处凭空造出一个符号变化——交点标记被画到了曲线起点，
    而这条曲线真正的交点在 t≈0.62。一张讲"在哪个档位换阵营"的图标错交点，比不标更坏。"""
    if t <= pts[0][0]:
        return pts[0][1]
    if t >= pts[-1][0]:
        return pts[-1][1]
    for (t0, v0), (t1, v1) in zip(pts, pts[1:]):
        if t0 <= t <= t1:
            return v0 + (v1 - v0) * (t - t0) / (t1 - t0)
    return pts[-1][1]


def _cross(a, b, steps=400):
    """两条折线的第一交点**算出来**，不是手填的。
    第一版把交叉标记画在 t=0.50，而曲线实际交在 t≈0.62——一张"按正文论点绘制"的图
    把论点的转折点画错位置，比不画更坏。
    符号变化要**双向**判：这里 a 起步在 b 之上、结束在 b 之下，只写
    `prev <= 0 < s` 会一个都找不到，标记直接消失（第二版就是这么坏的）。"""
    prev = None
    for i in range(steps + 1):
        t = float(i) / steps
        s = _interp(a, t) - _interp(b, t)
        if prev is not None and (prev[1] <= 0.0 < s or prev[1] >= 0.0 > s):
            return t, _interp(a, t)
        prev = (t, s)
    return None


def perf_profile():
    """架构章。这一章的论点是"性能释放不是芯片的属性，是功耗档的函数"，
    所以画的不是两条柱状对比，而是同一根 x 轴上两条随功耗上升的曲线，
    以及它们在哪个档位交叉——交叉点就是"什么时候该选谁"。"""
    img, d = canvas()
    label(d, (750, 92), u"性能释放是功耗档的函数，不是芯片的属性", 34, INK, anchor="ma")

    arm = [(0.02, 0.30), (0.20, 0.60), (0.38, 0.74), (0.60, 0.82), (0.96, 0.88)]
    x86 = [(0.02, 0.16), (0.20, 0.38), (0.38, 0.62), (0.60, 0.84), (0.96, 0.99)]

    x0, y0, w, h = 210, 200, 1080, 500
    d.line([x0, y0 + h, x0 + w, y0 + h], fill=RULE, width=3)
    d.line([x0, y0, x0, y0 + h], fill=RULE, width=3)

    for name, a, b in [(u"静音档", 0.0, 0.33), (u"均衡档", 0.33, 0.66), (u"性能档", 0.66, 1.0)]:
        xa, xb = x0 + a * w, x0 + b * w
        d.rectangle([xa, y0, xb, y0 + h], outline=RULE, width=1)
        label(d, ((xa + xb) / 2, y0 + h + 16), name, 24, MUTED, anchor="ma")

    def curve(pts, color):
        d.line([(x0 + t * w, y0 + h - v * h) for t, v in pts], fill=color, width=6)

    curve(arm, MAGENTA)
    curve(x86, NAVY)

    # 图例放绘图区左上角：那里两条曲线都还没爬上来，是真空着的一块。
    # 第一版把它挤在标题下面，两行字贴在一起。
    label(d, (x0 + 34, y0 + 34), u"— 低档就接近上限的一类平台", 23, MAGENTA, anchor="lm")
    label(d, (x0 + 34, y0 + 70), u"— 要靠档位换性能的一类平台", 23, NAVY, anchor="lm")

    hit = _cross(arm, x86)
    if hit:
        cx, cy = x0 + hit[0] * w, y0 + h - hit[1] * h
        d.ellipse([cx - 13, cy - 13, cx + 13, cy + 13], outline=INK, width=3)
        # 标记旁只写"交点"两个字：整句注释放这里必然有一侧被画布切掉，
        # 含义交给下面的"读法"行说。
        label(d, (cx, cy - 34), u"交点", 23, INK, anchor="mm")

    label(d, (750, 786),
          u"读法：交点以左安静的一方占优，以右才轮到「用功耗换性能」的一方",
          25, INK, anchor="ma")
    label(d, (750, 824),
          u"所以问「谁快」之前先问：在哪一档、允许吃多少瓦、要不要风扇",
          25, INK, anchor="ma")
    label(d, (750, 872),
          u"按正文的定性结论绘制；轴上刻意不标 TOPS / 瓦特 / 分数——那些走正文里带来源的表格",
          21, MUTED, anchor="ma")
    return img


def eco_layers():
    """生态章。"生态不行"是一句什么都没说的话，这一章把它拆成三层，
    并指出三层的时间尺度不同：应用层以季度补，驱动层以年计，开发者层决定前两层
    以后会不会自己长出来。所以图的重点是"哪一层最薄、为什么它最慢"。"""
    img, d = canvas()
    label(d, (750, 96), u"生态缺口分三层看：越往下越慢，也越决定上面两层", 34, INK, anchor="ma")

    layers = [
        (u"应用层", u"浏览器 / 办公 / 通讯 / 创作工具",
         u"原生版本在补，头部应用基本到位；长尾靠转译顶", False, 200),
        (u"驱动层", u"打印机 / 老外设 / 厂商私有驱动",
         u"最薄的一层：没有替代路径，转译帮不上驱动的忙", True, 430),
        (u"开发者层", u"跨平台框架、CI、运行时对 ARM64 的支持",
         u"决定前两层以后会不会自己长出来", False, 660),
    ]
    for name, members, note, hot, y in layers:
        edge = MAGENTA if hot else NAVY
        _box(d, 150, y, 1200, 190, edge, fill=SURFACE if hot else BG,
             width=4 if hot else 2)
        label(d, (190, y + 34), name, 30, edge, anchor="lm")
        label(d, (190, y + 84), members, 23, INK, anchor="lm")
        label(d, (190, y + 128), note, 23, MUTED, anchor="lm")
        if hot:
            label(d, (1310, y + 40), u"本篇认为的瓶颈", 22, MAGENTA, anchor="rm")

    for y in (390, 620):
        d.line([(750, y - 8), (750, y + 32)], fill=MUTED, width=2)
        d.polygon([(742, y + 24), (758, y + 24), (750, y + 38)], fill=MUTED)

    label(d, (750, 886),
          u"强调色标的是该篇的判断（哪一层最卡），不是客观分级；逐条原生支持状态见正文带来源的清单",
          21, MUTED, anchor="ma")
    return img


def price_channels():
    """价格章。"骁龙笔电贵/便宜"这种说法必然误导，因为芯片口径与整机口径之间
    隔着授权、内存绑定、渠道与品牌好几段。图画成一条链，两端是两个口径——
    这一章的论点就是"这两端之间没有稳定的换算关系"。

    连线只画在格子**之间**：第一版画了一条贯穿的长线，线从三个方框中间穿过去，
    读起来像"它们是一条带子上的三段"，正好说反了。"""
    img, d = canvas()
    label(d, (750, 96), u"芯片口径与整机口径之间隔着好几段，没有稳定换算", 34, INK, anchor="ma")

    nodes = [(u"芯片报价", u"口径：单颗 / 批量", 250, "end"),
             (u"平台授权", u"", 190, "mid"),
             (u"内存绑定", u"", 190, "mid"),
             (u"渠道与规格档", u"", 190, "mid"),
             (u"整机零售价", u"口径：一台 / 含屏幕内存", 250, "hot")]
    box_y, box_h = 220, 150
    gap = 52
    total = sum(n[2] for n in nodes) + gap * (len(nodes) - 1)
    x = (1500 - total) / 2
    edges = []
    for name, sub, w, kind in nodes:
        edge = MAGENTA if kind == "hot" else NAVY
        _box(d, x, box_y, w, box_h, edge,
             fill=SURFACE if kind == "hot" else BG, width=4 if kind == "hot" else 2)
        label(d, (x + w / 2, box_y + (58 if sub else box_h / 2)), name, 27, INK, anchor="mm")
        if sub:
            label(d, (x + w / 2, box_y + 100), sub, 20, MUTED, anchor="mm")
        edges.append((x, x + w))
        x += w + gap
    for (a_left, a_right), (b_left, _b_right) in zip(edges, edges[1:]):
        d.line([(a_right, box_y + box_h / 2), (b_left - 12, box_y + box_h / 2)],
               fill=MUTED, width=2)
        d.polygon([(b_left - 14, box_y + box_h / 2 - 6), (b_left - 14, box_y + box_h / 2 + 6),
                   (b_left - 3, box_y + box_h / 2)], fill=MUTED)

    # 只在**两个口径之间**放一个不等号。第一版每个间隔都放一个，
    # 读起来变成"这一段也和那一段无关"，把链子的意思说反了。
    span_y = 460
    left_c = (edges[0][0] + edges[0][1]) / 2
    right_c = (edges[-1][0] + edges[-1][1]) / 2
    d.line([(left_c, span_y), (right_c, span_y)], fill=MAGENTA, width=3)
    for cx in (left_c, right_c):
        d.line([(cx, span_y - 14), (cx, span_y + 14)], fill=MAGENTA, width=3)
    label(d, (750, span_y - 46), u"两端之间没有稳定换算", 25, MAGENTA, anchor="mm")
    label(d, (750, span_y + 22), u"≠", 30, MAGENTA, anchor="mm")

    notes = [(u"为什么可能更低", u"少风扇、少独立供电、板载颗粒省主板面积", 150),
             (u"为什么可能更高", u"同配置只给到高端档、屏幕与内存起步就高", 775)]
    for head, body, nx in notes:
        _box(d, nx, 560, 575, 150, RULE, fill=BG, width=2)
        label(d, (nx + 30, 596), head, 25, INK, anchor="lm")
        label(d, (nx + 30, 650), body, 22, MUTED, anchor="lm")

    label(d, (750, 800),
          u"读法：看到「骁龙机型更便宜 / 更贵」先问是哪一口径、比的是同配置还是同价位档",
          26, INK, anchor="ma")
    label(d, (750, 848),
          u"图上不写任何价格；逐条官方售价与统计时点见正文带来源的表格（R-02）",
          21, MUTED, anchor="ma")
    return img


def three_constraints():
    """本地 agent 章。这一章反对的是单变量说法（"有 NPU 就能跑"），
    主张 NPU 算力 / 内存带宽 / 功耗墙 三约束取最短那块。
    第一版把它画成木桶装水，结果水面矩形把最短那块**整个盖住了**——
    图的论点恰好是不可见的。改成柱状加一条短板线：谁都不能被遮住。"""
    img, d = canvas()
    label(d, (750, 96), u"能跑多大的模型，由三个约束里最短那块定", 34, INK, anchor="ma")

    bars = [(u"NPU 算力", 0.86, False), (u"内存带宽", 0.44, True), (u"功耗墙", 0.68, False)]
    base_y, bar_w, bar_gap = 660, 250, 90
    x0 = (1500 - (bar_w * 3 + bar_gap * 2)) / 2
    full_h = 420
    limit = min(b[1] for b in bars)

    for i, (name, ratio, hot) in enumerate(bars):
        x = x0 + i * (bar_w + bar_gap)
        hgt = full_h * ratio
        edge = MAGENTA if hot else NAVY
        # 先铺"装得下"的底色到短板线，再画柱框：柱框永远在最上层，不会被遮
        d.rectangle([x, base_y - full_h * limit, x + bar_w, base_y], fill=SOFT)
        _box(d, x, base_y - hgt, bar_w, hgt, edge, fill=None,
             width=4 if hot else 2)
        label(d, (x + bar_w / 2, base_y - hgt + 38), name, 27, INK, anchor="mm")
        if hot:
            label(d, (x + bar_w / 2, base_y - hgt - 28), u"最短的一块", 23, MAGENTA, anchor="mm")

    d.line([x0 - 40, base_y - full_h * limit, x0 + bar_w * 3 + bar_gap * 2 + 40,
            base_y - full_h * limit], fill=MAGENTA, width=4)
    d.line([x0 - 40, base_y, x0 + bar_w * 3 + bar_gap * 2 + 40, base_y], fill=RULE, width=3)
    label(d, (x0 - 56, base_y - full_h * limit),
          u"三约束的交集\n= 可常驻的模型规模", 22, INK, anchor="rm")

    label(d, (750, 760),
          u"读法：换指令集换的是柱子的材质，不是最短那根；只报 NPU 标称算力的说法，"
          u"在这里会被另外两根一起限住", 25, INK, anchor="ma")
    label(d, (750, 812),
          u"按正文的三约束论证绘制；哪一块最短是本篇判断，"
          u"实测吞吐与内存占用见正文带来源与测试条件的表格", 21, MUTED, anchor="ma")
    return img


def falsify_map():
    """可证伪章。这一章的论点是"死亡信号不是跑分，是兼容欠债到期"，
    而且它已经发生过两次（Windows RT 与 Chromebook 的 ARM 尝试）。
    正文里的监控清单是列表，画成图只会重复；这张图补的是**时间形状**：
    左边两次已发生的退场，右边本篇当前依赖的三个前提各配一个推翻信号。

    图上只出现年份——年份是这一章论证的骨架且正文逐条带来源，
    性能与份额数字仍然一律不进图（D-22）。"""
    img, d = canvas()
    label(d, (750, 96), u"该改写的信号不是跑分变差，而是兼容欠债到期", 34, INK, anchor="ma")

    axis_y = 300
    d.line([(120, axis_y), (1380, axis_y)], fill=RULE, width=3)
    label(d, (120, axis_y - 26), u"已经发生", 21, MUTED, anchor="lm")
    label(d, (1380, axis_y - 26), u"现在", 21, MUTED, anchor="rm")

    past = [(240, u"2012", u"Chromebook ARM", u"十余年后被报告 Linux 容器层\n仍只走 x86 路径"),
            (560, u"2013", u"Surface RT 退场", u"跑不了既有 x86 桌面程序\n开发者与 OEM 先散场")]
    for x, year, name, note in past:
        d.ellipse([x - 9, axis_y - 9, x + 9, axis_y + 9], fill=NAVY)
        label(d, (x, axis_y - 52), year, 26, NAVY, anchor="mm")
        label(d, (x, axis_y + 34), name, 24, INK, anchor="mm")
        for li, line in enumerate(note.split(u"\n")):
            label(d, (x, axis_y + 72 + li * 30), line, 20, MUTED, anchor="mm")

    # 分隔线放在"已发生的两次退场"与"本篇依赖的前提"之间，
    # 而不是压在时间轴右端——第一版把"已经发生"写在右边，整条轴读反了。
    d.line([(860, axis_y - 66), (860, axis_y + 66)], fill=MAGENTA, width=3)
    label(d, (872, axis_y - 78), u"兼容欠债还没到期：下面三条是本篇目前站的前提",
          21, MAGENTA, anchor="lm")
    d.ellipse([1240 - 9, axis_y - 9, 1240 + 9, axis_y + 9], outline=MAGENTA, width=3)
    label(d, (1240, axis_y + 34), u"2026-09", 24, INK, anchor="mm")

    now = [(u"前提一：同电池更长的轻载续航", u"被推翻于：续航横评里 x86 追平或反超"),
           (u"前提二：常连接待机与无线模块", u"被推翻于：x86 阵营靠固件补齐待机"),
           (u"前提三：运行时持续出 ARM64 构建", u"被推翻于：某次发版不再带 Windows ARM64")]
    y = 430
    for head, signal in now:
        _box(d, 620, y, 760, 116, NAVY, fill=BG, width=2)
        label(d, (650, y + 32), head, 24, INK, anchor="lm")
        label(d, (650, y + 80), signal, 22, MUTED, anchor="lm")
        y += 136

    label(d, (750, 858),
          u"两个年份与两条退场见正文带来源的段落；季度与事件两类监控清单也在正文，图上不重复",
          21, MUTED, anchor="ma")
    return img


def main():
    if not os.path.isdir(OUT):
        os.makedirs(OUT)
    jobs = [("perf_profile.png", perf_profile),
            ("eco_layers.png", eco_layers),
            ("price_channels.png", price_channels),
            ("three_constraints.png", three_constraints),
            ("falsify_map.png", falsify_map)]
    for name, fn in jobs:
        p = os.path.join(OUT, name)
        fn().save(p, "PNG")
        print("%s  %d KB" % (p, os.path.getsize(p) // 1024))


if __name__ == "__main__":
    main()
