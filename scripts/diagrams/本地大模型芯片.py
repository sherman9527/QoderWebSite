# -*- coding: utf-8 -*-
"""画 本地大模型芯片 篇的两张机制示意图（示意图通道，D-22）。

为什么这两章要自画而不是找照片：
· `premise-check` 讲的是「同一个词根底下是两颗不同的芯片」——照片里看不出 GB10 与
  RTX Spark 的区别，硬配只会配出一台看不出型号的笔记本（第一版确实配成了
  Surface Laptop Studio，型号与本章论点无关，还带着一句没登记来源的价格，被 G-03 判死）。
· `how-to-verify` 讲的是一条方法链（算式 → 固定口径 → 填回对照表），
  这不是任何一台机器的外观，拍不出来。

图上**不写任何数字**（D-22）：带宽、容量、瓦特、售价、tokens/s 都是可核查的量化断言，
必须走带 source 的结构化区块；烧进图片就绕过了 R-02，也没人查得到。
「哪两个容易混」「先怀疑口径」这类**本篇的判断**，在图注里写明是按正文绘制。

产物要逐字节可复现：只画确定性的几何与文字，不取随机、不依赖时间。
"""
import os

import _common

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = os.path.join(ROOT, ".probe", "drawn")

# 主题 silicon-copper，抄 web/src/tokens/index.ts
BG = "#F2F4F1"
SURFACE = "#E6EAE6"
INK = "#171A17"
MUTED = "#5E6660"
RULE = "#D5DBD6"
GREEN = "#125912"      # primary：深硅绿
COPPER = "#C87137"     # accent：铜橙
SOFT = "#DFE9DC"

font, canvas, label, leader = _common.make({"bg": BG, "ink": INK, "accent": GREEN})


def _box(d, x, y, w, h, edge, fill=BG, width=3, radius=14):
    d.rounded_rectangle([x, y, x + w, y + h], radius=radius, fill=fill, outline=edge, width=width)


def _arrow(d, x1, y, x2, color=None, width=3):
    c = color or MUTED
    d.line([x1, y, x2, y], fill=c, width=width)
    d.polygon([(x2, y - 9), (x2, y + 9), (x2 - 16, y)], fill=c)


def two_sparks():
    """premise-check：一个词根，两颗不同的芯片，一台对得上的 Surface。"""
    img, d = canvas()
    label(d, (750, 78), u"「Spark」是一个词根，不是型号名", 34, INK, anchor="ma")
    label(d, (750, 128), u"核查只认两样：官方系列全名，和规格页上那行代号", 24, MUTED, anchor="ma")

    # 左：DGX Spark = 一台桌面小盒，里面那颗叫 GB10
    _box(d, 96, 210, 600, 330, GREEN)
    label(d, (396, 246), u"DGX Spark", 32, GREEN, anchor="ma")
    label(d, (396, 296), u"形态：桌上的小盒子", 25, INK, anchor="ma")
    label(d, (396, 340), u"里面那颗芯片叫 GB10", 25, INK, anchor="ma")
    label(d, (396, 384), u"CPU 与 GPU 片内互联", 25, INK, anchor="ma")
    label(d, (396, 428), u"配一整片统一内存", 25, INK, anchor="ma")
    label(d, (396, 476), u"不是笔电 SoC", 24, MUTED, anchor="ma")

    # 右：RTX Spark = 装进笔电的超级芯片
    _box(d, 804, 210, 600, 330, GREEN)
    label(d, (1104, 246), u"RTX Spark", 32, GREEN, anchor="ma")
    label(d, (1104, 296), u"形态：装进笔电的超级芯片", 25, INK, anchor="ma")
    label(d, (1104, 340), u"GPU 块 + CPU 块同封装", 25, INK, anchor="ma")
    label(d, (1104, 384), u"也配一整片统一内存", 25, INK, anchor="ma")
    label(d, (1104, 428), u"跑 Windows 那一侧", 25, INK, anchor="ma")
    label(d, (1104, 476), u"顶配另有自己的型号名", 24, MUTED, anchor="ma")

    # 中间那道「别混」的分隔：强调色是本篇判断，不是客观分级
    d.line([750, 214, 750, 536], fill=COPPER, width=4)
    label(d, (750, 572), u"两条产品线，名字只差一个词", 25, COPPER, anchor="ma")

    # 下方：Surface 这一支——只有一台对得上
    _box(d, 96, 630, 1308, 250, RULE, fill=SURFACE, width=2)
    label(d, (750, 668), u"那台 Surface：搭配成立，但只成立一台", 29, INK, anchor="ma")
    label(d, (750, 724), u"用 RTX Spark 的是 Surface Laptop Ultra 这一档", 25, GREEN, anchor="ma")
    label(d, (750, 770), u"标准版 Surface Laptop 的处理器清单里只有骁龙，没有 Spark 字样", 25, INK, anchor="ma")
    label(d, (750, 818), u"同名的还有一台放在桌上的开发盒，形态更接近 DGX Spark", 24, MUTED, anchor="ma")

    return img, u"两个Spark不是一个东西.png"


def _arrow(d, x1, y, x2, color=None, width=3):
    """箭头指向 x2。第一版把三角形的顶点画在 x2-16，于是整条箭头**指反了方向**——
    一张讲"三步顺序"的图，箭头从第三步指回第二步，比不画更坏。"""
    c = color or MUTED
    d.line([x1, y, x2 - 14, y], fill=c, width=width)
    d.polygon([(x2, y), (x2 - 16, y - 9), (x2 - 16, y + 9)], fill=c)


def verify_chain():
    """how-to-verify：三步复核法，每步只写要固定的口径，不写数。"""
    img, d = canvas()
    label(d, (750, 78), u"宣传数字变成自己能复核的三个动作", 34, INK, anchor="ma")
    label(d, (750, 128), u"任何一步缺口径，结论就只到「量级」为止", 24, MUTED, anchor="ma")

    bw, gap = 420, 80
    xs = [40, 40 + bw + gap, 40 + 2 * (bw + gap)]
    cols = [
        (u"一 · 算式", [
            u"上限 = 带宽 ÷ 每 token 字节数",
            u"每 token = 激活参数 × 位宽",
            u"再加每 token 的 KV cache",
            u"折扣要写清是谁给的口径"]),
        (u"二 · 跑一条命令", [
            u"量化档",
            u"上下文长度",
            u"批大小与线程数",
            u"重复次数",
            u"首 token 与解码分开还是合并"]),
        (u"三 · 填回对照表", [
            u"本机两个数各归各格",
            u"填不进去先怀疑口径",
            u"其次怀疑默认值截短",
            u"最后才怀疑硬件"]),
    ]
    for x, (title, items) in zip(xs, cols):
        _box(d, x, 200, bw, 470, GREEN if x != xs[2] else RULE)
        label(d, (x + bw / 2, 244), title, 30, GREEN, anchor="ma")
        y = 322
        for it in items:
            d.ellipse([x + 34, y - 9, x + 46, y + 3], fill=COPPER)
            label(d, (x + 62, y - 8), it, 22, INK)
            y += 62

    for a, b in [(xs[0] + bw + 8, xs[1] - 8), (xs[1] + bw + 8, xs[2] - 8)]:
        _arrow(d, a, 435, b)

    _box(d, 40, 720, 1420, 160, RULE, fill=SURFACE, width=2)
    label(d, (750, 758), u"名字相同，不等于测量点相同", 28, COPPER, anchor="ma")
    label(d, (750, 812), u"同一套参数来回两次的微小差异是噪声；插电、驻留、并发这三样不钉死，数就不算你的", 24, INK, anchor="ma")

    return img, u"三步复核法.png"


def main():
    if not os.path.isdir(OUT):
        os.makedirs(OUT)
    for fn in (two_sparks, verify_chain):
        img, name = fn()
        path = os.path.join(OUT, name)
        img.save(path, "PNG", optimize=True)
        print("已出图 %s（%dx%d）" % (path, img.width, img.height))


if __name__ == "__main__":
    main()
