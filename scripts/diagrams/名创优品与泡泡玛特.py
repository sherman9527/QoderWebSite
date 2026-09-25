# -*- coding: utf-8 -*-
"""名创 × 泡泡玛特篇的示意图（示意图通道，D-22）。

为什么这四章要画而不是拍：联络表人眼过下来，`align-the-rulers`（报表口径）、
`what-inflection-means`（拐点的三类定义）、`duan-yongping`（自述与披露的差别）、
`unit-economics`（同一道除法的两种分子）拿到的全是泡泡玛特的产品海报——
`q=泡泡玛特` 那条兜底词把整章喂饱了，**命名 100%、相关 0%**（与 W-139 加密篇的
`OpenAI` 池同一种坏）。这四章的论点在结构上没有照片承载得了：
"加回项是哪几项""什么条件出现才算拐点""自述与披露差几天"不是场景，是关系。
照片只留在它真是证据的地方：门店、货架、永辉招牌、盲盒陈列。

图上**不写任何数字与日期**（D-22）：每店平均收入、加回金额、回购股数、民调百分点
都是可核查的量化断言，已经带来源地活在正文的 keyvalue_table 与 fact_strip 里。
烧进图片就绕过了 R-02——图片没有"图源"可点。所以除法图只画分子分母的关系，
阶梯图只画"加回了哪一类"，时间线只画**自述与披露的先后与滞后**，不画刻度。

框高一律先量后画（`_panel`），不手写高度：加密篇九张里三张溢出，教训是
"手写的框迟早溢出，量出来的不会"。
"""
import os
import re
import sys

import _common

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = os.path.join(ROOT, ".probe", "drawn")

# 主题 shelf-vermilion，抄 web/src/tokens/index.ts
BG = "#FAF8F2"
SURFACE = "#EFEAE0"
INK = "#161C19"
MUTED = "#5F6A63"
RULE = "#DBD5C6"
GREEN = "#123B2E"       # primary：货架绿
GOLD = "#F2B705"        # accent：盲盒黄
SOFT = "#E4EBE4"

font, canvas, label, leader = _common.make(
    {"bg": BG, "ink": INK, "accent": GREEN})

# 拉丁词整块保留，中文按字断，空白单独一块——否则 "IFRS" 会被从中间劈开
_CHUNK = re.compile(u"[A-Za-z0-9_\\-–—/×.+·()（）%]+|\\s|.", re.U)


def _box(d, x, y, w, h, edge, fill=BG, width=2, radius=12):
    d.rounded_rectangle([x, y, x + w, y + h], radius=radius,
                        fill=fill, outline=edge, width=width)
    return (x, y, w, h)


def _arrow(d, p0, p1, color=None, width=3, head=11):
    c = color or GREEN
    d.line([p0, p1], fill=c, width=width)
    x, y = p1
    d.polygon([(x, y), (x - head, y - head // 2), (x - head, y + head // 2)], fill=c)


def _dash(d, p0, p1, color=None, width=3, step=14):
    c = color or MUTED
    x0, y0 = p0
    x1, y1 = p1
    n = max(int(((x1 - x0) ** 2 + (y1 - y0) ** 2) ** 0.5) // step, 1)
    for i in range(n + 1):
        if i % 2:
            continue
        t = float(i) / n
        d.ellipse([x0 + (x1 - x0) * t - 2, y0 + (y1 - y0) * t - 2,
                   x0 + (x1 - x0) * t + 2, y0 + (y1 - y0) * t + 2], fill=c)


def _fit(text, fnt, maxw):
    """按像素量着折行。返回行列表。"""
    lines, cur, w = [], u"", 0
    for tk in _CHUNK.findall(text):
        tw = fnt.getbbox(tk)[2] - fnt.getbbox(tk)[0]
        if cur and w + tw > maxw:
            lines.append(cur.strip())
            cur, w = (tk if tk.strip() else u""), (0 if not tk.strip() else tw)
        else:
            cur += tk
            w += tw
    if cur.strip():
        lines.append(cur.strip())
    return lines


def _lh(fnt):
    return int((fnt.getbbox(u"国Hgp")[3] - fnt.getbbox(u"国Hgp")[1]) * 1.42)


def _measure(d, lines, fnt, pad, lead=None):
    lead = lead or _lh(fnt)
    return pad * 2 + lead * len(lines)


def _panel(d, x, y, w, title, body, edge=None, fill=BG, tsize=27, bsize=22,
           pad=18, mark=None):
    """量出内容要多高再画框；返回框底 y，调用方按它排下一块。"""
    edge = edge or GREEN
    tf, bf = font(tsize), font(bsize)
    tl = _fit(title, tf, w - pad * 2)
    bl = _fit(body, bf, w - pad * 2) if body else []
    h = pad * 2 + _lh(tf) * len(tl) + (_lh(bf) * len(bl) if bl else 0)
    _box(d, x, y, w, h, edge, fill=fill)
    if mark:
        d.rectangle([x, y, x + 7, y + h], fill=mark)
    cy = y + pad
    for ln in tl:
        label(d, (x + pad + 6, cy), ln, size=tsize, color=edge)
        cy += _lh(tf)
    for ln in bl:
        label(d, (x + pad + 6, cy), ln, size=bsize, color=INK)
        cy += _lh(bf)
    return y + h


def _foot(d, w, y, text):
    """画在**内容结束的那一行**，不是画布底部。
    画在底部会让 _trim 看见最后一行有字、什么也裁不掉，图框下面永远空一块。"""
    f = font(19)
    for i, ln in enumerate(_fit(text, f, w - 90)):
        label(d, (45, y + i * 26), ln, size=19, color=MUTED)


def per_store_division():
    """单店：同一道除法，两种分子。"""
    img, d = canvas(1500, 1150)
    label(d, (45, 34), u"同一道除法，两种分子", size=38, color=GREEN)
    label(d, (45, 92), u"把收入除进门店数，得到的是一个看起来可比的商——它不可比。", size=23, color=MUTED)

    head_bottom = _panel(d, 45, 150, 1410, u"商 = 分子 ÷ 分母",
                         u"两家都能算出一个数，但两个数不是同一种钱。", mark=GOLD)
    top = head_bottom + 22
    y1 = _panel(d, 60, top, 665, u"名创优品：分子里有一部分不是零售额",
                u"直营确认门店零售；加盟与代理确认的是发给加盟商的批发收入——"
                u"货到了终端卖不卖得掉、以什么价卖，不在这笔收入里。"
                u"于是同一句「每店平均收入」，一部分店说的是批发，一部分店说的是零售。",
                edge=GREEN, fill=SURFACE)
    y2 = _panel(d, 765, top, 665, u"泡泡玛特：分子基本是零售额",
                u"海外以直营与自营电商为主，机器人商店另计。同样是「每店平均收入」，"
                u"它的分母是自营门店，分子是终端卖出的钱。", edge=GREEN, fill=SOFT)

    bottom = max(y1, y2) + 26
    end = _panel(d, 45, bottom, 1410, u"所以比较之前要先做的一件事",
                 u"把分母按模式拆开（直营 / 加盟 / 代理），或者干脆只比公司自己披露的运营指标"
                 u"（同店增速、线上占比、机器人商店数量）。缺的那一格留「未披露」——"
                 u"用推算填上，表就变成了一张假表。", edge=GOLD, fill=BG)
    _foot(d, 1500, end + 26, u"示意图·非实拍：只画收入确认的结构关系，不含任何金额与店数；"
                        u"具体数值见正文表格，逐条带来源")
    return img


def three_rulers():
    """三把尺子与「经调整」这个口袋。"""
    img, d = canvas(1500, 1150)
    label(d, (45, 34), u"三把尺子，和一个叫「经调整」的口袋", size=38, color=GREEN)
    label(d, (45, 92), u"流传的对比表多数不是数字错，是尺子混着用。", size=23, color=MUTED)

    x = 45
    w = 455
    y1 = _panel(d, x, 150, w, u"尺子一：IFRS（港股年报）",
                u"两家都有。名创在港交所上市地位下用这一套。", edge=GREEN)
    y2 = _panel(d, x + w + 25, 150, w, u"尺子二：US GAAP（美股 ADS）",
                u"同一家公司另一套报表。两套的「净利润」可以差出十几个百分点。",
                edge=GREEN, fill=SURFACE)
    y3 = _panel(d, x + (w + 25) * 2, 150, w, u"尺子三：非 GAAP / 经调整",
                u"公司自己定义的那一行。它不是造假，但它加回了什么必须逐项看见。",
                edge=GOLD, fill=SOFT)

    bottom = max(y1, y2, y3) + 30
    label(d, (45, bottom), u"「经调整」这一行通常加回的是这几类（逐项，不是笼统一句）：", size=24, color=INK)
    items = [
        (u"股份支付", u"发给人和团队的股票费用：与经营有关，长期摊在股东身上"),
        (u"投资的公允价值变动", u"持有的上市公司股份涨跌进了利润——门店没多卖一件，利润也能动"),
        (u"可换股债券的公允价值变动", u"融资工具的估值噪声，与卖货无关"),
        (u"一次性项目", u"重组、减值、诉讼和解：可能是常态的，也可能真是一次性"),
    ]
    cy = bottom + 46
    for name, why in items:
        h = 62
        _box(d, 45, cy, 1410, h, RULE, fill=BG)
        d.rectangle([45, cy, 52, cy + h], fill=GOLD)
        label(d, (72, cy + 16), name, size=25, color=GREEN)
        label(d, (430, cy + 18), why, size=22, color=INK)
        cy += h + 12
    _foot(d, 1500, cy + 10, u"示意图·非实拍：类别取自两家公司披露的调节表项目名，图上不写任何金额")
    return img


def inflection_three():
    """拐点拆成三类，各给观测条件。"""
    img, d = canvas(1500, 1150)
    label(d, (45, 34), u"「拐点」得拆成三个", size=38, color=GREEN)
    label(d, (45, 92), u"同一个词，三件事：只有第三类与价格有关，而它最常被误用。",
          size=23, color=MUTED)

    rows = [
        (u"经营拐点", u"同店增速 与 存货周转 同时转向",
         u"条件：至少连续两期同向。只转一期是噪声。"
         u"一家在放量、一家在收紧时，同一份报表里会有反向证据。"),
        (u"单店模型拐点", u"某个新市场的门店群，自身经营利润首次转正",
         u"难点：公司很少按这个粒度披露。查不到就写查不到——"
         u"「海外毛利高于国内」不等于「海外经营利润为正」，那是两件事。"),
        (u"估值拐点", u"把价格变动拆成 盈利修正 × 倍数变化",
         u"只有倍数那道反转才叫估值拐点。盈利被上调时的下跌不是「跌」，"
         u"是同一件事的另一半。价格跌了很多不是拐点的证据，只是价格的描述。"),
    ]
    # 左栏定宽 300、右栏从 400 起：第一版让标题与判据各写各的，两栏直接叠在一起
    nf, cf = font(22), font(22)
    cy = 150
    for i, (name, cond, note) in enumerate(rows):
        nl = _fit(note, nf, 1410 - 400 + 45 - 20)
        cl = _fit(cond, cf, 300)
        h = 36 + max(_lh(font(27)), _lh(cf) * len(cl), _lh(nf) * len(nl))
        _box(d, 45, cy, 1410, h, RULE, fill=BG if i % 2 == 0 else SURFACE)
        d.rectangle([45, cy, 52, cy + h], fill=GOLD if i == 2 else GREEN)
        label(d, (74, cy + 16), name, size=27, color=GREEN)
        ly = cy + 16 + _lh(font(27))
        for ln in cl:
            label(d, (74, ly), ln, size=22, color=MUTED)
            ly += _lh(cf)
        ny = cy + 18
        for ln in nl:
            label(d, (400, ny), ln, size=22, color=INK)
            ny += _lh(nf)
        cy += h + 16

    end = _panel(d, 45, cy + 6, 1410, u"本篇不给的东西",
                 u"不给方向、不给目标价、不说「该买/该卖」。不是因为谨慎，是因为方向不可证伪："
                 u"错了指不出错在哪个变量上。上面三行的观测条件都可以证伪，这才是能用的东西。",
                 edge=GOLD, fill=BG)
    _foot(d, 1500, end + 26, u"示意图·非实拍：只画判据结构与口径要求，不含任何阈值数值")
    return img


def disclosure_gap():
    """自述与披露之间隔着什么。"""
    img, d = canvas(1500, 1150)
    label(d, (45, 34), u"自述与披露，是两种性质的信息", size=38, color=GREEN)
    label(d, (45, 92), u"个人投资者没有强制披露义务时，外界看到的只有他愿意给的那一部分。",
          size=23, color=MUTED)

    # 两条带：色带里只放标签，点画在色带**下面**。第一版把点画在色带里，
    # 结果「他本人公开说的」那行字被圆点压住（截图自查才发现）。
    b1, b2 = 168, 310
    _box(d, 45, b1, 1410, 54, RULE, fill=SOFT)
    label(d, (64, b1 + 14), u"他本人公开说的（社媒发帖、截图流传）", size=24, color=GREEN)
    _box(d, 45, b2, 1410, 54, RULE, fill=SURFACE)
    label(d, (64, b2 + 14), u"监管口径下可核的（权益披露、持股比例变动）", size=24, color=GREEN)

    t1, t2 = b1 + 82, b2 + 82
    for x, t in [(150, u"表态"), (520, u"自述买入"), (900, u"再说一句"),
                 (1240, u"外界拼出的「时间线」")]:
        d.ellipse([x - 9, t1 - 9, x + 9, t1 + 9], fill=GOLD)
        label(d, (x - 24, t1 + 16), t, size=21, color=INK)
    for x, t in [(300, u"披露 A"), (760, u"披露 B"), (1180, u"披露 C")]:
        d.ellipse([x - 9, t2 - 9, x + 9, t2 + 9], fill=GREEN)
        label(d, (x - 24, t2 + 16), t, size=21, color=INK)
    _dash(d, (640, t1 + 12), (640, b2 - 2), color=MUTED)
    label(d, (656, t1 + 22), u"中间这段是空的", size=21, color=MUTED)

    cy = t2 + 66
    items = [
        (u"成本与时间尺度", u"他的进入价格在更早的位置、持有期以年计；你看到的是一句被截了图的话。"),
        (u"仓位规模与流动性", u"同样的比例，对个人是随时可退，对大资金本身就是价格。"),
        (u"披露滞后与选择性", u"自述发生在已经买了之后，而且只讲愿意讲的那一笔。"),
        (u"他自己的口径", u"他一贯公开说看不懂就不做——所以从他的一句话推不出他没说的话。"),
    ]
    for name, why in items:
        h = _measure(d, _fit(why, font(22), 1410 - 360), font(22), 18)
        h = max(h, 62)
        _box(d, 45, cy, 1410, h, RULE, fill=BG)
        d.rectangle([45, cy, 52, cy + h], fill=GREEN)
        label(d, (72, cy + 18), name, size=24, color=GREEN)
        ny = cy + 20
        for ln in _fit(why, font(22), 1410 - 360):
            label(d, (370, ny), ln, size=22, color=INK)
            ny += _lh(font(22))
        cy += h + 12
    _foot(d, 1500, cy + 10, u"示意图·非实拍：不指认任何具体交易、日期与金额；"
                        u"本篇只引用可核的披露记录与逐字原话，四条结构差与立场无关")
    return img


def _trim(img, margin=26):
    """按实际内容裁掉底部空白。

    画布高度是我手写的（950），内容到哪一行只有画完才知道——第一版四张里有两张
    下面空着两百多像素，放进 `.ratio` 的图框里就是一块没有内容的色。
    和 `_panel` 同一个道理：**量出来的不会错，手写的迟早错**。
    """
    bg = img.getpixel((4, img.height - 4))
    last = 0
    for y in range(img.height - 1, -1, -1):
        row = [img.getpixel((x, y)) for x in range(0, img.width, 7)]
        if any(abs(p[0] - bg[0]) + abs(p[1] - bg[1]) + abs(p[2] - bg[2]) > 12 for p in row):
            last = y
            break
    return img.crop((0, 0, img.width, min(img.height, last + margin)))


def five_moves():
    """怎么读这类对比：五个动作 + 一个不建议。"""
    img, d = canvas(1500, 1150)
    label(d, (45, 34), u"五个动作，和一个不建议", size=38, color=GREEN)
    label(d, (45, 92), u"可迁移的读法——每一条在本篇都用过，都能拿去读别的公司。",
          size=23, color=MUTED)

    moves = [
        (u"先对报告期与准则", u"两套准则的「净利润」不是同一个数；一家按半年、一家按季度披露时，"
         u"把两家的「最新」并排放会差一个季度。"),
        (u"把门店数除进收入", u"总量是宣传，每店平均才是能力。除之前还要问分子是什么钱"
         u"（零售额还是批发额）。"),
        (u"区分利润与现金流", u"看钱有没有变成货：存货增速跑赢收入增速时，利润是应计出来的。"),
        (u"把「经调整」逐项还原", u"加回的是股份支付，还是投资的公允价值变动？前者与经营有关，"
         u"后者与卖货无关。"),
        (u"把创始人在别处的动作当资本配置读", u"分拆、跨界、回购、增持——它们决定同样的收入"
         u"最后换成什么。不是新闻，是配置。"),
    ]
    cy = 150
    f22 = font(22)
    for i, (name, why) in enumerate(moves):
        # 折行宽度按**右栏自己的可用宽度**量：面板右边到 1455，正文从 540 起，
        # 第一版拿 1410-470 去算，第一条就在画布上被切掉了半句「并排」
        nl = _fit(why, f22, 1455 - 540 - 24)
        cl = _fit(name, font(25), 400)
        h = 34 + max(_lh(f22) * len(nl), _lh(font(25)) * len(cl))
        _box(d, 45, cy, 1410, h, RULE, fill=BG if i % 2 == 0 else SURFACE)
        d.ellipse([70, cy + 16, 104, cy + 50], outline=GREEN, width=3)
        label(d, (80, cy + 21), str(i + 1), size=24, color=GREEN)
        ny = cy + 16
        for ln in cl:
            label(d, (122, ny), ln, size=25, color=GREEN)
            ny += _lh(font(25))
        ny = cy + 18
        for ln in nl:
            label(d, (540, ny), ln, size=22, color=INK)
            ny += _lh(f22)
        cy += h + 14

    end = _panel(d, 45, cy + 8, 1410, u"不建议做的那一个动作：把「我看好了」当成分析",
                 u"看好不可证伪——错了指不出错在哪个变量上。上面五条都可以证伪，"
                 u"这也是本篇只留观测条件、不留方向的原因。", edge=GOLD, fill=BG)
    _foot(d, 1500, end + 26, u"示意图·非实拍：读法清单，不含任何数值与结论性判断")
    return img


JOBS = [
    ("per_store_division.png", per_store_division),
    ("three_rulers.png", three_rulers),
    ("inflection_three.png", inflection_three),
    ("disclosure_gap.png", disclosure_gap),
    ("five_moves.png", five_moves),
]


def main():
    if not os.path.isdir(OUT):
        os.makedirs(OUT)
    only = sys.argv[1:] or None
    for name, fn in JOBS:
        if only and name not in only:
            continue
        p = os.path.join(OUT, name)
        _trim(fn()).save(p, "PNG")
        print("%s  %d KB" % (p, os.path.getsize(p) // 1024))


if __name__ == "__main__":
    main()
