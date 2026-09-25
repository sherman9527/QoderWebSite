# -*- coding: utf-8 -*-
"""大模型与加密货币篇的示意图（示意图通道，D-22）。

为什么这一篇要画十张：配图实测只有四个活簇（比特币、OpenAI、Anthropic、椭圆曲线
点名有图），其余 22 条诚实检索词**全部零点名**。而机制章的论点照片在结构上承载不了——
"验证链条断在哪一环""同涨的三种解释""该问的问题矩阵"没有哪张照片画得出来。
照片只留在两章它真是证据的地方：椭圆曲线那张教科书图、比特币本身。
**第一章也没有照片**——`OpenAI` 召回 35 条、35 条全部点名 OpenAI，内容全是融资、
996 作息表、o3 发布、语音模式：整池 100% 命名、0% 相关。排除表救不了这种池子，
要排除的是整条词。而"一个数学结果的宣布"本来就没有可拍的东西。

图上**不写任何数字与日期**（D-22）：2030/2035/2029 那串年份、公钥暴露比例、
Mosca 不等式、agent 数量与算力成本，全是可核查的量化断言，
已经带来源地活在正文的 timeline 与 fact_strip 里。烧进图片就绕过了 R-02——
图片没有"图源"链接可点。所以时间轴只画**先后与结构**，不画刻度。
同理 `three_explanations` **不画价格曲线**：曲线要口径，口径写进图里就是没有来源的量化断言。

`_panel` 是这一篇新增的：文字框高度按内容量出来再画框。前九张第一版是手写高度，
实测三张溢出（"地方""面"被裁在框外、底行压在边框上）——手写的框迟早溢出，量出来的不会。
"""
import os
import re

import _common

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = os.path.join(ROOT, ".probe", "drawn")

# 主题 graphite-ultramarine，抄 web/src/tokens/index.ts
BG = "#F6F5F2"
SURFACE = "#E9E8E3"
INK = "#141619"
MUTED = "#5E626E"
RULE = "#DCDAD3"
GRAPHITE = "#22252B"     # primary
ULTRA = "#1F3193"        # accent
SOFT = "#DDE2F0"

font, canvas, label, leader = _common.make(
    {"bg": BG, "ink": INK, "accent": ULTRA})


def _box(d, x, y, w, h, edge, fill=BG, width=2, radius=12):
    d.rounded_rectangle([x, y, x + w, y + h], radius=radius,
                        fill=fill, outline=edge, width=width)
    return (x, y, w, h)


def _arrow(d, p0, p1, color=None, width=3, head=11):
    c = color or GRAPHITE
    d.line([p0, p1], fill=c, width=width)
    x, y = p1
    d.polygon([(x, y), (x - head, y - head // 2), (x - head, y + head // 2)], fill=c)


def _dash(d, p0, p1, color=None, width=3, step=16):
    c = color or MUTED
    x0, y0 = p0
    x1, y1 = p1
    n = max(int(((x1 - x0) ** 2 + (y1 - y0) ** 2) ** 0.5) // step, 1)
    dx, dy = (x1 - x0) / float(n), (y1 - y0) / float(n)
    for i in range(0, n, 2):
        d.line([(x0 + i * dx, y0 + i * dy),
                (x0 + (i + 1) * dx, y0 + (i + 1) * dy)], fill=c, width=width)


_CHUNK = re.compile(u"[A-Za-z0-9_\-–—/×.+]+|\s|.", re.U)


def _fit(text, size, maxw):
    """按像素宽度折行。CJK 逐字可断，但拉丁词与数字整体不拆——
    第一版逐字断，把 "agent" 断成 "ag / ent"、"Lean" 断成 "形 / 式化验证" 那种东西。
    行首也不留收尾标点。"""
    f = font(size)
    lines, cur = [], u""
    for ch in _CHUNK.findall(text):
        trial = cur + ch
        if f.getlength(trial) > maxw and cur.strip():
            lines.append(cur.rstrip())
            cur = ch if not ch.isspace() else u""
        else:
            cur = trial
    if cur.strip():
        lines.append(cur.rstrip())
    # 把落在行首的收尾标点拉回上一行，否则出现"…看得见它 。"那种断法
    for i in range(1, len(lines)):
        while lines[i][:1] in (u"。", u"，", u"、", u"）", u"」", u"？", u"！", u"：", u"；"):
            lines[i - 1] = lines[i - 1] + lines[i][:1]
            lines[i] = lines[i][1:]
        if not lines[i]:
            lines[i] = u""
    return [ln for ln in lines if ln != u""] or [u""]


def _lh(size):
    return int(size * 1.45)


def _ph(rows, w, pad):
    """不画出来，只问这块内容要多高。同一排的几个框要等高时用它。"""
    return _measure([r if len(r) > 3 else (r[0], r[1], r[2], None) for r in rows],
                    w, pad) + 2 * pad


def _measure(rows, w, pad):
    """ rows = [(text, size, color, marker)] → 这段内容要多高。"""
    maxw = w - 2 * pad
    h = 0
    for i, r in enumerate(rows):
        text, size = r[0], r[1]
        marker = r[3] if len(r) > 3 else None
        n = len(_fit(text, size, maxw - (34 if marker else 0)))
        h += n * _lh(size)
        if i:
            h += r[4] if len(r) > 4 else 8
    return h


def _panel(d, x, y, w, rows, edge=RULE, fill=SURFACE, width=2, pad=26,
           min_h=0, radius=12):
    """量出来再画框。返回 (x, y, w, h)，调用方据此排下一块。

    rows 每项：(text, size, color) 或 (text, size, color, marker)
    marker ∈ {None, 'dot', 'cross', 'dash'}
    """
    body = [r if len(r) > 3 else (r[0], r[1], r[2], None) for r in rows]
    h = max(min_h, _measure(body, w, pad) + 2 * pad)
    _box(d, x, y, w, h, edge, fill=fill, width=width, radius=radius)
    cy = y + pad
    for text, size, color, marker in body:
        tx = x + pad
        if marker:
            mx = x + pad
            if marker == "dot":
                d.ellipse([mx, cy + size // 3, mx + 13, cy + size // 3 + 13], fill=color)
            elif marker == "cross":
                d.line([(mx, cy + 4), (mx + 13, cy + 4 + 13)], fill=color, width=3)
                d.line([(mx, cy + 4 + 13), (mx + 13, cy + 4)], fill=color, width=3)
            else:
                _dash(d, (mx, cy + size // 2), (mx + 16, cy + size // 2), color, 3, 8)
            tx = x + pad + 30
        for ln in _fit(text, size, w - 2 * pad - (30 if marker else 0)):
            d.text((tx, cy), ln, fill=color, font=font(size))
            cy += _lh(size)
        cy += 8
    return (x, y, w, h)


def _foot(d, w, h, text):
    label(d, (w // 2, h - 34), text, 21, MUTED, anchor=u"ma")


def proof_gate():
    """verifiable：可信来自"有东西能验"，不是模型聪明。

    第一版把链条画成一条直线，读起来像"机器检查完就可信了"——正是本章反对的话。
    真正的形状是：链条末端有一个**人来做**的岔口，而密码学那一侧没有这台检查器。
    """
    img, d = canvas(1500, 880)
    label(d, (90, 52), u"示意图·非实拍：可验证性在哪一侧", 32, INK)

    steps = [(u"自然语言的证明", u"人读，会累、会信错", RULE, SURFACE, 2),
             (u"翻译成形式化命题", u"每一步都得是可检查的对象", RULE, SURFACE, 2),
             (u"机器检查器", u"不接受「看起来对」", ULTRA, SOFT, 3)]
    x, y, bw, gap = 90, 132, 396, 48
    for i, (t, sub, edge, fill, lw) in enumerate(steps):
        _, _, _, h = _panel(d, x, y, bw, [(t, 27, INK), (sub, 22, MUTED)],
                            edge=edge, fill=fill, width=lw)
        if i < 2:
            _arrow(d, (x + bw, y + h // 2), (x + bw + gap, y + h // 2), GRAPHITE)
        x += bw + gap

    # 岔口：从第三个框的底边正中，垂直落一条虚线到下面那块
    fork_y = y + h + 74
    _dash(d, (90 + 2 * (bw + gap) + bw // 2, y + h),
          (90 + 2 * (bw + gap) + bw // 2, fork_y), MUTED, 2, 10)
    _, _, _, fh = _panel(d, 620, fork_y, 790, [
        (u"剩下这一步仍然是人做的：确认「检查器里被证明为真的那个命题」"
         u"就是数学家原本想证的那件事。", 24, INK),
        (u"形式化只保证推理不出错，不保证问题问得对。", 23, ULTRA)],
        edge=ULTRA, fill=BG, width=3, pad=28)

    ry = fork_y + fh + 56
    _, _, _, lh_ = _panel(d, 90, ry, 620, [
        (u"加密体制这一侧，没有这台检查器", 27, GRAPHITE),
        (u"没有哪个验证器能判定「这攻破了那条曲线」。安全性是归约到一个困难问题"
         u"假设上的论证，不是可机器复检的产物。", 23, INK),
        (u"唯一的检验就是真的把它攻破——而攻破的那一刻，全世界都能看到。",
         24, INK)], edge=RULE, fill=BG, pad=28)
    _panel(d, 790, ry, 620, [
        (u"所以这两件事之间没有张力", 27, ULTRA),
        (u"数学那边快，是因为产物可验证；加密这边没动静，是因为它要的不是"
         u"「验证一个产物」而是「做成一件事」。", 23, INK),
        (u"把前者当成后者的前兆，是这一篇要拆掉的那个推论。", 24, GRAPHITE)],
        edge=ULTRA, fill=SOFT, width=3, pad=28)

    _foot(d, 1500, 880, u"结构按正文的可验证性论证绘制；项目、日期与量化断言见正文带来源的条目")
    return img


def category_wall():
    """complexity：底层原因是类别差异，不是量的差距。

    中间那道墙**不画桥也不画箭头**——第一版在墙顶画了个箭头，读起来像"翻过去就行"，
    而这一章要说的是：能翻过去的不是更大的模型，是改变渐近复杂度的新算法，
    它要的是另一台机器。
    """
    img, d = canvas(1500, 830)
    label(d, (90, 52), u"示意图·非实拍：证明存在，和把它算出来", 32, INK)

    left = [u"结论的形状是「存在这样一组条件，使解在有限时间失稳」",
            u"它不产出一个可以运行的算法",
            u"也不构造一个具体实例去「算」出答案",
            u"产物是一段可复检的推理——所以它能被机器接住"]
    right = [u"结论的形状是「破解所需工作量按密钥长度这样增长」",
             u"它说的是一个计算任务的代价，不是一段论证的真假",
             u"已知最好的经典攻击停在亚指数与指数两档",
             u"产物是一次成功的执行——半成功等于没成功"]
    rows_l = [(u"这一类：存在性结论", 28, GRAPHITE)] + [
        (t, 23, INK, "dot" if i == 3 else "dash") for i, t in enumerate(left)]
    rows_r = [(u"这一类：困难性假设", 28, GRAPHITE)] + [
        (t, 23, INK, "cross" if i == 3 else "dash") for i, t in enumerate(right)]

    ly = 128
    # 两栏等高：不等高时中间那道墙和下面的结论框会各按一边对齐，读起来是歪的
    hh = max(_ph(rows_l, 600, 26), _ph(rows_r, 600, 26))
    _panel(d, 90, ly, 600, rows_l, edge=RULE, fill=SURFACE, pad=26, min_h=hh)
    _panel(d, 810, ly, 600, rows_r, edge=RULE, fill=SURFACE, pad=26, min_h=hh)

    wx = 720
    for i in range(8):
        d.rounded_rectangle([wx, ly + 20 + i * (hh - 40) // 8,
                             wx + 60, ly + 20 + (i + 1) * (hh - 40) // 8 - 8],
                            radius=6, fill=GRAPHITE)
    label(d, (wx + 30, ly + hh + 26), u"类别差异", 24, MUTED, anchor=u"ma")

    _panel(d, 90, ly + hh + 62, 1320, [
        (u"能把右边那一类降下来的，是改变渐近复杂度的算法——那一类算法要的是另一台机器"
         u"（容错、能跑量子线路的机器），不是更多的参数。", 24, INK),
        (u"模型变强改变的是「人在给定难度里，搜索与组合已知技巧」的效率。", 24, ULTRA),
        (u"这两句的差别，就是这一章存在的全部理由。", 23, MUTED)],
        edge=ULTRA, fill=BG, width=3, pad=28)

    _foot(d, 1500, 830, u"只画问题类别；复杂度阶与算法名称见正文带来源的段落，图上刻意不写")
    return img


def migration_shape():
    """pqc：真正在动的是迁移。年份全部留在正文时间线，这里只画先后与两类暴露。"""
    img, d = canvas(1500, 860)
    label(d, (90, 52), u"示意图·非实拍：迁移的先后，和链上两类暴露", 32, INK)

    stages = [(u"清点", u"先知道自己用了哪些算法、在哪些地方", RULE, SURFACE, 2),
              (u"高风险的先迁", u"寿命长、暴露面大的那一批排在前面", ULTRA, SOFT, 3),
              (u"全量完成", u"退出表上的老算法一个不留", RULE, SURFACE, 2)]
    x, y, bw, gap = 90, 126, 400, 55
    # 三段等高：第一段的说明折了两行，不等高时"顺序是确定的"那行会压在它底边上
    hh = max(_ph([(t, 27, INK), (s, 22, MUTED)], bw, 24) for t, s, _, _, _ in stages)
    for i, (t, sub, edge, fill, lw) in enumerate(stages):
        _panel(d, x, y, bw, [(t, 27, INK), (sub, 22, MUTED)],
               edge=edge, fill=fill, width=lw, pad=24, min_h=hh)
        if i < 2:
            _arrow(d, (x + bw, y + hh // 2), (x + bw + gap, y + hh // 2), GRAPHITE)
        x += bw + gap

    ny = y + hh + 26
    label(d, (90, ny), u"顺序是确定的；每一段的截止年份是目标日期，不是技术里程碑——"
                       u"年份在正文时间线里，带来源。", 22, MUTED)

    ty = ny + 54
    label(d, (90, ty), u"链上要分两类看，因为「签名」和「加密」坏的方式不同", 27, GRAPHITE)

    cy = ty + 50
    long_rows = [
        (u"长期暴露", 26, ULTRA),
        (u"公钥早就写在链上了：收过款、发过交易的账户，"
         u"签名本身就把公钥交了出去。", 23, INK),
        (u"要问的是：这个地址的公钥暴露了多久，它还要活多久。", 23, MUTED)]
    short_rows = [
        (u"短期暴露", 26, GRAPHITE),
        (u"交易在内存池里等待确认的那几分钟，公钥随交易一起公开。", 23, INK),
        (u"要问的是：确认要等多久，这段时间里谁看得见它。", 23, MUTED)]
    lh_ = max(_ph(long_rows, 620, 26), _ph(short_rows, 620, 26))
    _panel(d, 90, cy, 620, long_rows, edge=RULE, fill=BG, pad=26, min_h=lh_)
    _panel(d, 790, cy, 620, short_rows, edge=RULE, fill=BG, pad=26, min_h=lh_)

    _panel(d, 90, cy + lh_ + 40, 1320, [
        (u"两条链的签名跑在同一族曲线上，区别只在暴露时长。所以真问题不是"
         u"「历史签名能否被回退」——认证只在发生的当下有效。", 24, INK)],
        edge=ULTRA, fill=SOFT, width=3, pad=26)

    _foot(d, 1500, 860, u"图上不写年份与比例：那些是量化断言，带来源地活在正文时间线里")
    return img


def three_explanations():
    """correlation：同涨是事实，因果不是。画解释结构，不画曲线。"""
    img, d = canvas(1500, 900)
    label(d, (90, 52), u"示意图·非实拍：同时上涨能被三种解释接住", 32, INK)

    _, _, _, oh = _panel(d, 90, 122, 1320, [
        (u"观察到的事实：某一阶段里，AI 相关标的、BTC、稳定币相关标的同向。", 25, INK)],
        edge=GRAPHITE, fill=SURFACE, pad=24)
    label(d, (90, 122 + oh + 34),
          u"这句话能被三种互不相同的解释接住，它们要的证据不是一回事：", 25, INK)

    rows = [
        (u"一、直接因果", u"钱从一类资产流进另一类",
         u"要看的是资金路径与换手，不是两条曲线的形状。多数说法给不出这一层。",
         RULE, SURFACE, 2),
        (u"二、共同驱动", u"同一件事同时抬高两边",
         u"风险偏好、利率预期、算力资本开支——两边都涨，可以完全不需要彼此。",
         ULTRA, SOFT, 3),
        (u"三、区间巧合", u"挑的窗口刚好重叠",
         u"换一段区间、换一个基准，同向就消失。所以口径必须先于结论公开。",
         RULE, SURFACE, 2),
    ]
    y = 122 + oh + 76
    for t, mid, sub, edge, fill, lw in rows:
        _, _, _, hh = _panel(d, 90, y, 1320, [
            (t + u"　" + mid, 25, INK), (sub, 22, MUTED)],
            edge=edge, fill=fill, width=lw, pad=24)
        y += hh + 20

    _panel(d, 90, y + 6, 1320, [
        (u"这一章只做到「把三种解释分开」为止。哪一种才是主因，要的是资金流与"
         u"分区间的数据——那不在本篇能溯源的范围内，所以不给方向。", 24, ULTRA)],
        edge=ULTRA, fill=BG, width=3, pad=26)

    _foot(d, 1500, 900, u"刻意不画价格曲线：曲线要口径，口径与区间见正文，图上带不了来源")
    return img


def spread_not_model():
    """stablecoin：论点是"涨的是利差与清算"，所以要画出那条**不存在**的边。"""
    img, d = canvas(1500, 900)
    label(d, (90, 52), u"示意图·非实拍：两条来钱的路，和一条不存在的边", 32, INK)

    def chain(y, a, b, mid, tag, last, note):
        _, _, _, hh = _panel(d, 90, y, 380, [(a, 25, INK), (b, 21, MUTED)],
                             edge=RULE, fill=SURFACE, pad=22)
        _arrow(d, (470, y + hh // 2), (530, y + hh // 2), GRAPHITE)
        _panel(d, 530, y, 380, [(mid, 25, INK), (tag, 21, MUTED)],
               edge=RULE, fill=SURFACE, pad=22)
        _arrow(d, (910, y + hh // 2), (970, y + hh // 2), GRAPHITE)
        _panel(d, 970, y, 440, [(last, 25, INK), (note, 22, ULTRA)],
               edge=ULTRA, fill=SOFT, width=3, pad=22)
        return hh

    h1 = chain(126, u"储备资产", u"短端票据与回购那一类", u"短期利率",
               u"由货币政策定，与模型无关", u"发行方的利息收入", u"规模 × 利差")
    chain(126 + h1 + 40, u"支付与结算量", u"跨境、场内撮合、链上换手", u"清算的摩擦",
          u"时效、可拆分性、营业时间", u"被省下的那一段成本", u"这条线的收入来源")

    by = 126 + h1 + 40 + h1 + 46
    _, _, _, bh = _panel(d, 90, by, 380, [(u"模型能力", 25, GRAPHITE),
                                          (u"参数量、推理成本、智能水位", 21, MUTED)],
                         edge=GRAPHITE, fill=BG, pad=22)
    _dash(d, (470, by + bh // 2), (970, by + bh // 2), MUTED, 3)
    cx, cy2 = 720, by + bh // 2
    d.line([(cx - 24, cy2 - 24), (cx + 24, cy2 + 24)], fill=MUTED, width=6)
    d.line([(cx - 24, cy2 + 24), (cx + 24, cy2 - 24)], fill=MUTED, width=6)
    _panel(d, 970, by, 440, [(u"这一格是空的", 25, MUTED),
                             (u"上面两条链里都没有它的一环", 21, MUTED)],
           edge=RULE, fill=BG, pad=22)

    _panel(d, 90, by + bh + 36, 1320, [
        (u"所以「AI 变强」和「稳定币变大」同时发生，不需要任何一方推动另一方："
         u"它们的共同点只是同一段时间、同一组宏观条件。", 24, INK),
        (u"真要问这条线的风险，问的是储备结构与赎回顺序，不是模型。", 24, ULTRA)],
        edge=ULTRA, fill=BG, width=3, pad=26)

    _foot(d, 1500, 900, u"链条按正文的利差与清算论证绘制；规模与利率数字见正文带来源的条目")
    return img


def three_layers():
    """regulation：只列发布出来的文件与性质——所以"草案"和"生效"必须画成两栏。"""
    img, d = canvas(1500, 760)
    label(d, (90, 52), u"示意图·非实拍：监管动的是哪三层，各是什么性质", 32, INK)

    cols = [
        (u"披露", u"要求公开：用了哪些算法、迁移计划是什么、什么时候交清单",
         u"约束的是「说不说」，不判定资产本身", RULE, SURFACE, 2),
        (u"分类", u"把某类资产归进某个既有制度：证券、支付、电子货币、托管",
         u"决定的是适用哪套规则，不创设新义务", RULE, SURFACE, 2),
        (u"授权", u"发放或拒绝牌照，附带条件与罚则",
         u"唯一真正卡住「谁能做生意」的那一层", ULTRA, SOFT, 3),
    ]
    x, y, w = 90, 126, 420
    hh = max(_ph([(t, 29, INK), (m, 23, GRAPHITE), (s, 22, MUTED)], w, 26)
             for t, m, s, _, _, _ in cols)
    for i, (t, mid, sub, edge, fill, lw) in enumerate(cols):
        _panel(d, x, y, w, [(t, 29, INK), (mid, 23, GRAPHITE), (sub, 22, MUTED)],
               edge=edge, fill=fill, width=lw, pad=26, min_h=hh)
        if i < 2:
            _arrow(d, (x + w, y + hh // 2), (x + w + 18, y + hh // 2), GRAPHITE, 2)
        x += w + 20

    dy = y + hh + 46
    _, _, _, nh = _panel(d, 90, dy, 1320, [
        (u"同一层里还要分性质，否则会把「说了要管」当成「已经在管」", 25, INK)],
        edge=RULE, fill=BG, pad=24)
    # 两栏各自两行：合成一行会互相撞字（第一版"征求意见"压在"已生效"上面）
    _dash(d, (118, dy + nh + 40), (640, dy + nh + 40), MUTED, 3, 10)
    label(d, (118, dy + nh + 56), u"草案 / 建议 / 路线图", 24, MUTED)
    label(d, (118, dy + nh + 94), u"可以改措辞、可以延期、可以永远停在征求意见", 22, MUTED)
    _dash(d, (760, dy + nh + 40), (1410, dy + nh + 40), ULTRA, 3, 10)
    label(d, (760, dy + nh + 56), u"已生效的强制要求", 24, ULTRA)
    label(d, (760, dy + nh + 94), u"走完程序，且带罚则", 22, ULTRA)
    label(d, (118, dy + nh + 150),
          u"判断只看两件事：文件有没有走完程序，义务有没有罚则。", 24, INK)

    _foot(d, 1500, 760, u"只画层次与性质；具体文件、机构与日期见正文带来源的清单")
    return img


def sim_boundary():
    """simulation：先问它模拟的是什么。图的全部信息量在那条边界上。"""
    img, d = canvas(1500, 760)
    label(d, (90, 52), u"示意图·非实拍：仿真平台能回答什么，边界在哪", 32, INK)

    inner = [(u"在模型之内", 26, GRAPHITE),
             (u"协议步骤与状态机", 23, INK, "dot"),
             (u"符号层面的等价性", 23, INK, "dot"),
             (u"算法的工作量假设", 23, INK, "dot"),
             (u"参数变了会怎样", 23, INK, "dot"),
             (u"这些可以反复跑，跑错了不伤人。", 22, MUTED)]
    outer = [(u"在模型之外", 26, GRAPHITE),
             (u"实现与侧信道", 23, INK, "cross"),
             (u"密钥怎么生成、怎么存", 23, INK, "cross"),
             (u"真实算力、电价与硬件", 23, INK, "cross"),
             (u"人：流程、失误、内鬼", 23, INK, "cross"),
             (u"这些不在模型里，所以平台给不出答案。", 22, MUTED)]
    lh_ = max(_ph(inner, 420, 26), _ph(outer, 420, 26))
    _panel(d, 90, 126, 420, inner, edge=RULE, fill=BG, pad=26, min_h=lh_)
    _panel(d, 560, 126, 380, [
        (u"仿真 / 形式化平台", 27, ULTRA),
        (u"输入：协议模型、符号化的攻击者能力、参数化的代价函数", 22, INK),
        (u"输出：在这个模型里这条路径走不通，或者要走这么多步", 22, INK),
        (u"它擅长的是「在给定假设下穷举与剪枝」", 22, MUTED)],
        edge=ULTRA, fill=SOFT, width=3, pad=26, min_h=lh_)
    _panel(d, 990, 126, 420, outer, edge=RULE, fill=BG, pad=26, min_h=lh_)

    _arrow(d, (510, 126 + lh_ // 2), (556, 126 + lh_ // 2), GRAPHITE)
    # 右边这条是虚线**加叉**：模型之外的东西进不了平台，光一条虚线读成"连过去了"
    _dash(d, (940, 126 + lh_ // 2), (986, 126 + lh_ // 2), MUTED, 3)
    cx, cy2 = 963, 126 + lh_ // 2
    d.line([(cx - 16, cy2 - 16), (cx + 16, cy2 + 16)], fill=MUTED, width=5)
    d.line([(cx - 16, cy2 + 16), (cx + 16, cy2 - 16)], fill=MUTED, width=5)

    _, _, _, bh = _panel(d, 90, 126 + lh_ + 44, 1320, [
        (u"所以「会不会出现模拟破解的平台」这个问题，答案分两半：模型内的版本早就有了——"
         u"符号验证与代价估算本来就是密码学工程的日常；它替代不了的那一半，"
         u"恰恰是「真的做成一次」必须碰到的东西。", 24, INK),
        (u"一句判据：平台报「不破」，说的是这个模型里不破；平台报「要很久」，"
         u"说的是这个代价函数下要很久。两句都不等于现实里安全。", 24, ULTRA)],
        edge=ULTRA, fill=BG, width=3, pad=26)

    _foot(d, 1500, 760, u"按正文对「模拟的是什么」的拆解绘制；不指任何具体工具或实现")
    return img


def question_matrix():
    """incumbents：给该问的问题，不给结论。

    行**必须照正文那五条判据走**。第一版自己另起了"资产类型/生命周期/迁移能力"
    三行分类，看着比正文整齐，但读者拿它对不上正文的 1–5——示意图一旦发明一套
    和正文并行的分类法，它就不再是"画正文"，而是另写了一遍正文。
    """
    img, d = canvas(1500, 1010)
    label(d, (90, 52), u"示意图·非实拍：五条判据，两栏问句", 32, INK)

    x0, y0, cw, gap = 300, 140, 505, 30
    label(d, (x0 + cw // 2, y0 - 26), u"自己保管密钥", 25, GRAPHITE, anchor=u"ma")
    label(d, (x0 + cw + gap + cw // 2, y0 - 26), u"托管 / 交易所持有", 25, GRAPHITE,
          anchor=u"ma")

    rows = [
        (u"一、退出时间表",
         u"我依赖的签名与曲线，谁为它公布过退出时间表？那是谁的口径、约束得到谁？",
         u"平台给出的是时间表，还是一句说法？"),
        (u"二、换算法要不要换地址",
         u"我个人换得掉算法吗，还是要等协议本身引入新版本？",
         u"平台换算法时我要不要动？动的时候谁替我签名？"),
        (u"三、承诺与已上线",
         u"哪些已经上线、哪些只是承诺？这两样我分得开吗？",
         u"它公布的是修复完成，还是评分与工作流？"),
        (u"四、公钥露出来多久",
         u"花过的那个地址，公钥已经在链上了——这部分占我多少余额？",
         u"默认地址类型是什么？历史上露过公钥的那批归谁负责？"),
        (u"五、迁移带来的地址变更",
         u"换地址在本辖区算不算应税事件？问过持牌税务顾问吗？",
         u"资产登记在哪个受监管实体名下？赔付条款写在哪一份文件里？"),
    ]
    y = y0
    for name, a, b in rows:
        h = max(_measure([(a, 23, INK)], cw, 24), _measure([(b, 23, INK)], cw, 24)) + 48
        _panel(d, 90, y, 190, [(name, 23, INK)], edge=GRAPHITE, fill=SURFACE,
               pad=20, min_h=h)
        _panel(d, x0, y, cw, [(a, 23, INK)], edge=RULE, fill=BG, pad=24, min_h=h)
        _panel(d, x0 + cw + gap, y, cw, [(b, 23, INK)], edge=RULE, fill=BG,
               pad=24, min_h=h)
        y += h + 16

    _panel(d, 90, y + 4, 1320, [
        (u"这张表刻意不给任何一格填「安全」或「不安全」。", 24, ULTRA),
        (u"能问出这五类问题、并且拿到公开文件当答案的人，才谈得上判断；"
         u"替他下结论，这一篇就越界了。", 24, INK)],
        edge=ULTRA, fill=SOFT, width=3, pad=26)

    _foot(d, 1500, 1010, u"五条判据与问句按正文 incumbents 一节整理；不构成对任何具体资产或平台的评价")
    return img


def falsify_axis():
    """falsify：什么信号出现这篇就该改写。每条信号都要连到它推翻本篇哪一节。"""
    img, d = canvas(1500, 1000)
    label(d, (90, 52), u"示意图·非实拍：四类信号，各推翻本篇一个论断", 32, INK)

    ay = 178
    _arrow(d, (110, ay), (1390, ay), GRAPHITE, 4, 16)
    label(d, (110, ay - 40), u"已经发生", 23, MUTED)
    label(d, (750, ay - 40), u"现在", 23, MUTED, anchor=u"ma")
    label(d, (1390, ay - 40), u"出现即改写本篇", 24, ULTRA, anchor=u"ra")
    d.ellipse([742, ay - 9, 758, ay + 9], fill=GRAPHITE)

    sigs = [
        (u"算法层面的突破",
         u"有人把分解或离散对数的复杂度阶真正降下来，哪怕在经典机器上。"
         u"推翻的是「类别差异」那一节。"),
        (u"硬件量级跃迁",
         u"容错逻辑量子比特从演示规模跨到能跑这些线路的规模。"
         u"推翻的是「另一台机器，不是更大模型」。"),
        (u"链上签名真的换了",
         u"某条链把签名方案换掉并跑通迁移。"
         u"推翻的是「迁移只是时间表与暴露时长」。"),
        (u"文件从草案走到生效",
         u"带罚则的强制要求落地。推翻的是「监管只动披露与分类」这一节的克制表述。"),
    ]
    y = 232
    for t, sub in sigs:
        _, _, _, hh = _panel(d, 90, y, 1320, [(t, 25, INK), (sub, 22, MUTED)],
                             edge=ULTRA, fill=BG, width=2, pad=22)
        y += hh + 16

    _panel(d, 90, y + 4, 1320, [
        (u"这四条都是可以被别人证伪的形式。反过来，「模型又变强了」不属于任何一条——"
         u"它不指明本篇哪一句被推翻，所以它不是信号，只是噪声。", 24, GRAPHITE)],
        edge=RULE, fill=SURFACE, pad=24)

    _foot(d, 1500, 1000, u"信号与所推翻的论断一一对应正文各节；图上不写任何规模数字")
    return img


def announcement_map():
    """what-happened：这一章的任务是**把对的部分和不对的部分分开**，所以图要画"谁说了什么"。

    为什么这一章没有照片：`OpenAI` 这条词实测召回 35 条、35 条全部点名 OpenAI，
    内容全是融资、996 作息表、o3 发布、语音模式——**整池 100% 命名、0% 相关**。
    排除表救不了这种池子（要排除的是整条词，不是几个页面），而"一个数学结果的宣布"
    本来就没有可拍的东西。所以画归属图，不硬配一张公司新闻照。
    """
    img, d = canvas(1500, 900)
    label(d, (90, 52), u"示意图·非实拍：同一件事，三方各自说了什么", 32, INK)

    _, _, _, th = _panel(d, 90, 122, 1320, [
        (u"宣布的内容：一组 agent 找到了三维 Navier–Stokes 方程的奇点解——"
         u"这是一个存在性结论，而且已经用 Lean 形式化验证。", 24, INK)],
        edge=GRAPHITE, fill=SURFACE, pad=24)

    cols = [
        (u"宣布方", u"强调规模与成本，也强调这是自主 agent 的一次跨越。",
         u"报道同时记下：优先权不在它这一边。", RULE, SURFACE, 2),
        (u"更早宣布的一方", u"公开质疑对方收到的机器证明质量，"
         u"并暗示自己的工作可能被用作了素材。",
         u"这两句是全篇最硬的能力边界证据——比任何评论都硬。", RULE, SURFACE, 2),
        (u"方法的真正来源", u"不用计算机的解析方法（无限层联立）属于这两位数学家；"
         u"agent 补上的是最后那道坎。",
         u"其中一位的原话是：我不用 AI，我有同事。", ULTRA, SOFT, 3),
    ]
    x, y, w = 90, th + 122 + 30, 420
    hh = max(_ph([(t, 28, INK), (m, 22, GRAPHITE), (s, 22, MUTED)], w, 26)
             for t, m, s, _, _, _ in cols)
    for i, (t, mid, sub, edge, fill, lw) in enumerate(cols):
        _panel(d, x, y, w, [(t, 28, INK), (mid, 22, GRAPHITE), (sub, 22, MUTED)],
               edge=edge, fill=fill, width=lw, pad=26, min_h=hh)
        if i < 2:
            _dash(d, (x + w, y + hh // 2), (x + w + 20, y + hh // 2), MUTED, 2, 8)
        x += w + 20

    _, _, _, fh = _panel(d, 90, y + hh + 40, 1320, [
        (u"报道自己的措辞是「如果该结果经得起进一步审查」，"
         u"而争议在于谁先做出来的，不在于对不对。", 24, INK)],
        edge=ULTRA, fill=BG, width=3, pad=24)

    _panel(d, 90, y + hh + fh + 44, 1320, [
        (u"还有一条限定必须和前面三栏同时给出：这没有直接实用后果。"
         u"真实流体由分子构成、不是完美光滑的，结论只在理想化意义上成立。", 24, MUTED)],
        edge=RULE, fill=SURFACE, pad=24)

    _foot(d, 1500, 900, u"三方说法与两条限定按正文带来源的引语整理；规模、时长与成本数字见正文，图上不写")
    return img


JOBS = [
    ("announcement_map.png", announcement_map),
    ("proof_gate.png", proof_gate),
    ("category_wall.png", category_wall),
    ("migration_shape.png", migration_shape),
    ("three_explanations.png", three_explanations),
    ("spread_not_model.png", spread_not_model),
    ("three_layers.png", three_layers),
    ("sim_boundary.png", sim_boundary),
    ("question_matrix.png", question_matrix),
    ("falsify_axis.png", falsify_axis),
]


def main():
    if not os.path.isdir(OUT):
        os.makedirs(OUT)
    for name, fn in JOBS:
        p = os.path.join(OUT, name)
        fn().save(p, "PNG")
        print("%s  %d KB" % (p, os.path.getsize(p) // 1024))


if __name__ == "__main__":
    main()
