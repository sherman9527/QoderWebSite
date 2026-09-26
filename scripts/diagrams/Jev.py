# -*- coding: utf-8 -*-
"""Jev 篇的示意图（示意图通道，D-22）。

为什么这八章必须画：图片阶段跑完，`not-generating`、`how-to-judge`、`quant-feasible`、
`why-no-followers`、`three-routes`、`what-it-cannot`、`check-list`、`what-changes-mind`
一张图都没拿到（G-03 判空章）。这不是采集器坏，是**这些论点没有照片承载得了**：
"输出被选项集合封住""阈值换覆盖率""哪一段链路吃毫秒""三条路线各交付什么"。
而且这篇的主角是一个**没有界面的 API**——Bing 能还给它的，只有 TypeSafe 商标与
一堆不相干的电视剧剧照（实测：全站只捞到 3 张合格图，其余检索词召回 0）。
教训还是那条：**抽象章先想画什么，别先想拍什么。**

图上**不写任何数字与日期**（D-22）：延迟、价格、倍数、席位数、百分比都是可核查的
量化断言，已经带来源地活在正文与表格里。烧进图片就绕过了 R-02——图片没有"图源"可点。
所以这里只画**形状与关系**：曲线的弯法、集合的内外、链路的分段、闭环的次序。

三条从上一篇带过来的写法（都是被真实缺陷逼出来的）：
  * `_panel` / `_row` 先量内容再画框——手写的框迟早溢出；
  * 折行宽度按**该栏自己的可用宽度**量，不按整块面板量；
  * 页脚画在内容结束处，`_trim` 才裁得掉空白。
"""
import os
import re
import sys

import _common

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = os.path.join(ROOT, ".probe", "drawn")

# 主题 jev-choice，抄 web/src/tokens/index.ts
BG = "#F7F8F3"
SURFACE = "#ECEFE3"
INK = "#1A1E14"
MUTED = "#5C6353"
RULE = "#DCE0D1"
OLIVE = "#526F20"     # primary
PURPLE = "#872BB6"    # accent
SOFT = "#E6EBD8"

font, canvas, label, leader = _common.make({"bg": BG, "ink": INK, "accent": OLIVE})

_CHUNK = re.compile(u"[A-Za-z0-9_\\-–—/×.+·()%、:：]+|\\s|.", re.U)
W = 1500


def _box(d, x, y, w, h, edge, fill=BG, width=2, radius=12):
    d.rounded_rectangle([x, y, x + w, y + h], radius=radius,
                        fill=fill, outline=edge, width=width)


def _fit(text, fnt, maxw):
    lines, cur, w = [], u"", 0
    for tk in _CHUNK.findall(text):
        bb = fnt.getbbox(tk)
        tw = bb[2] - bb[0]
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
    bb = fnt.getbbox(u"国Hgp")
    return int((bb[3] - bb[1]) * 1.42)


def _panel(d, x, y, w, title, body, edge=None, fill=BG, tsize=26, bsize=21, pad=16, mark=None):
    edge = edge or OLIVE
    tf, bf = font(tsize), font(bsize)
    tl = _fit(title, tf, w - pad * 2)
    bl = _fit(body, bf, w - pad * 2) if body else []
    h = pad * 2 + _lh(tf) * len(tl) + _lh(bf) * len(bl)
    _box(d, x, y, w, h, edge, fill=fill)
    if mark:
        d.rectangle([x, y, x + 7, y + h], fill=mark)
    cy = y + pad
    for ln in tl:
        label(d, (x + pad + 8, cy), ln, size=tsize, color=edge)
        cy += _lh(tf)
    for ln in bl:
        label(d, (x + pad + 8, cy), ln, size=bsize, color=INK)
        cy += _lh(bf)
    return y + h


def _row(d, y, name, why, left=45, width=1410, name_w=360, fill=BG, mark=OLIVE):
    nf, wf = font(23), font(21)
    nl = _fit(name, nf, name_w)
    wl = _fit(why, wf, width - (name_w + 90) - 24)
    h = 32 + max(_lh(nf) * len(nl), _lh(wf) * len(wl))
    _box(d, left, y, width, h, RULE, fill=fill)
    d.rectangle([left, y, left + 7, y + h], fill=mark)
    cy = y + 15
    for ln in nl:
        label(d, (left + 26, cy), ln, size=23, color=mark)
        cy += _lh(nf)
    cy = y + 16
    for ln in wl:
        label(d, (left + name_w + 90, cy), ln, size=21, color=INK)
        cy += _lh(wf)
    return y + h + 12


def _head(d, title, sub):
    y = 34
    for ln in _fit(title, font(34), W - 90):
        label(d, (45, y), ln, size=34, color=OLIVE)
        y += _lh(font(34))
    for ln in _fit(sub, font(20), W - 90):
        label(d, (45, y), ln, size=20, color=MUTED)
        y += _lh(font(20))
    return y + 14


def _foot(d, y, text):
    for i, ln in enumerate(_fit(text, font(19), W - 90)):
        label(d, (45, y + i * 26), ln, size=19, color=MUTED)


def _trim(img, margin=26):
    bg = img.getpixel((4, img.height - 4))
    last = 0
    for y in range(img.height - 1, -1, -1):
        row = [img.getpixel((x, y)) for x in range(0, img.width, 7)]
        if any(abs(p[0] - bg[0]) + abs(p[1] - bg[1]) + abs(p[2] - bg[2]) > 12 for p in row):
            last = y
            break
    return img.crop((0, 0, img.width, min(img.height, last + margin)))


def _chip(d, x, y, w, h, text, on=False, fnt=None):
    fnt = fnt or font(19)
    fill = PURPLE if on else SURFACE
    edge = PURPLE if on else RULE
    txt = INK if on else MUTED
    d.rounded_rectangle([x, y, x + w, y + h], radius=8, fill=fill, outline=edge, width=2)
    label(d, (x + w / 2, y + h / 2), text, size=19, color=(BG if on else txt), anchor="mm")


# ── 1 ────────────────────────────────────────────────────────────────────
def output_paths():
    img, d = canvas(W, 1000)
    y = _head(d, u"两条输出通路：一条打开词表，一条锁在选项里",
              u"差别不在模型大小，在接口形状——左边每次吐一个 token，右边只在给定候选中点亮一个")
    colw = (W - 90 - 30) / 2
    x1, x2 = 45, 45 + colw + 30
    y1 = _panel(d, x1, y, colw, u"自回归语言模型", u"", edge=OLIVE, fill=SURFACE)
    yy = y1 + 14
    for i, t in enumerate([u"输入 prompt", u"整个词表上的下一 token 分布", u"采样挑一个 token",
                           u"接回输入，再来一次", u"吐出：任意长度文本"]):
        _chip(d, x1 + 20, yy, colw - 40, 44, u"%d. %s" % (i + 1, t), on=(i == 4))
        if i < 4:
            d.line([x1 + colw / 2, yy + 44, x1 + colw / 2, yy + 56], fill=OLIVE, width=2)
        yy += 58
    y2 = _panel(d, x2, y, colw, u"Jev 这类非生成模型", u"", edge=PURPLE, fill=SURFACE)
    yy = y2 + 14
    for i, t in enumerate([u"输入：结构化 state + 预设问题", u"候选 = 人给定的那几个选项",
                           u"每个候选一个概率与置信度", u"点亮一条，不产文本"]):
        _chip(d, x2 + 20, yy, colw - 40, 44, u"%d. %s" % (i + 1, t), on=(i == 2))
        if i < 3:
            d.line([x2 + colw / 2, yy + 44, x2 + colw / 2, yy + 56], fill=PURPLE, width=2)
        yy += 58
    yy += 6
    for j, (lab, on) in enumerate([(u"是不是", True), (u"挑选项", False), (u"打分", False)]):
        _chip(d, x2 + 20 + j * ((colw - 60) / 3), yy, (colw - 60) / 3 - 12, 40, lab, on=on)
    yy += 56
    _foot(d, yy + 8, u"右边那条通路的「格式不会错」来自选项集合是封闭的；"
                     u"同一件事也意味着：集合之外的答案它永远给不出。")
    return _trim(img)


# ── 2 ────────────────────────────────────────────────────────────────────
def threshold_coverage():
    img, d = canvas(W, 1000)
    y = _head(d, u"判断它挑得对不对：别看一个准确率，看这两条线",
              u"左：愿意放弃多少题，换多少正确率；右：说「九成把握」的那些题，实际中了多少")
    colw = (W - 90 - 40) / 2
    lx, rx = 45, 45 + colw + 40
    # 两栏的标题各占一行，图从标题下面再起——上一版把标题装进面板、图压在面板下沿，
    # 结果轴标签与标题叠成一片（这类"框是框、图是图"的错位只有肉眼看得见）。
    tf = font(24)
    for x0, ttl, edge in [(lx, u"阈值—覆盖率：往右要覆盖，往左要把握", OLIVE),
                          (rx, u"校准：置信度兑现了没有", PURPLE)]:
        label(d, (x0, y), ttl, size=24, color=edge)
    top = y + _lh(tf) + 26
    px, py, pw, ph = lx, top, colw - 60, 300
    d.line([px, py + ph, px + pw, py + ph], fill=MUTED, width=2)
    d.line([px, py, px, py + ph], fill=MUTED, width=2)
    pts = [(0.02, 0.99), (0.18, 0.97), (0.38, 0.93), (0.60, 0.86), (0.80, 0.76), (0.97, 0.63)]
    d.line([(px + int(a * pw), py + int((1 - b) * ph)) for a, b in pts],
           fill=OLIVE, width=4, joint="curve")
    label(d, (px + 10, py + 10), u"只答最稳的一部分", size=18, color=MUTED)
    label(d, (px + pw, py + ph + 10), u"愿意答的比例 →", size=18, color=MUTED, anchor="ra")
    qx, qy, qw, qh = rx, top, colw - 60, 300
    d.line([qx, qy + qh, qx + qw, qy + qh], fill=MUTED, width=2)
    d.line([qx, qy, qx, qy + qh], fill=MUTED, width=2)
    d.line([qx, qy + qh, qx + qw, qy], fill=RULE, width=3)
    # 柱**压在对角线下方**：自报置信度高于实际命中，才是"把没把握说成有把握"。
    # 上一版画到了线上方，而图下注释写的是下方——图文各说一件事，比不画更坏。
    bars = [(0.12, 0.07), (0.32, 0.22), (0.55, 0.40), (0.74, 0.55), (0.90, 0.66)]
    for cx, ch in bars:
        bx = qx + int(cx * qw) - 12
        d.rectangle([bx, qy + qh - int(ch * qh), bx + 24, qy + qh], fill=PURPLE)
    label(d, (qx + 10, qy + 10), u"实际命中率", size=18, color=MUTED)
    label(d, (qx + qw, qy + qh + 10), u"模型自报置信度 →", size=18, color=MUTED, anchor="ra")
    yb = py + ph + 52
    # 两行说明各自的颜色要跟它讲的那张图一致：柱是紫（右），曲线是橄榄（左）。
    # 上一版串了色——读者按颜色去找图，就找错了一半。
    yb = _row(d, yb, u"柱整体压在对角线下方", u"→ 它把「没把握」说成了「有把握」，阈值要按实际命中重新定",
              mark=PURPLE)
    yb = _row(d, yb, u"曲线掉得比同行快", u"→ 覆盖一上去准确率就崩，这类题不适合让它独立答", mark=OLIVE)
    _foot(d, yb + 10, u"两图都只画形状，不画数值——任何具体百分比都该来自你自己那批带标注的题，"
                      u"并且随版本重测。Score 类输出只能过阈值或排序，不能当量级读。")
    return _trim(img)


# ── 3 ────────────────────────────────────────────────────────────────────
def pipeline_latency():
    img, d = canvas(W, 1000)
    y = _head(d, u"交易链路分段：哪一段真吃毫秒，哪一段吃的是研究",
              u"「快」只有在闸门与撮合这一段才直接换算成收益；信号那一段的瓶颈从来不是延迟")
    segs = [(u"行情接收与解析", u"订阅、归一化、跨所对齐——时间敏感", True),
            (u"信号 / 研究判断", u"假设、数据、回测——瓶颈是想法与证据，不是算力", False),
            (u"风控闸门", u"仓位约束、自成交与操纵类规则、异常行情降级——每次调用都在关键路径上", True),
            (u"下单与撮合", u"订单类型、路由、确认——毫秒级竞争最激烈的一段", True),
            (u"清算与对账", u"成交回报、账务、留痕审计——要的是可追溯，不是快", False)]
    yy = y + 8
    for name, why, hot in segs:
        yy = _row(d, yy, name, why, mark=(PURPLE if hot else OLIVE),
                  fill=(SOFT if hot else BG)) + 0
    yy += 10
    _foot(d, yy, u"本篇不给任何标的、方向或买卖建议。图上深色三段是「延迟确实有意义」的环节；"
                 u"浅色那两段里，一个非生成模型能做的只是**在给定选项里挑**，不会替你产生假设。")
    return _trim(img)


# ── 4 ────────────────────────────────────────────────────────────────────
def moat_layers():
    img, d = canvas(W, 1000)
    y = _head(d, u"为什么没有同类涌现：先分清哪几层容易抄、哪一层抄不走",
              u"发布到今天只有一个多星期——这个长度本身不构成任何证据")
    easy = [(u"任务收窄", u"只做封闭选项判断，不做生成"),
            (u"输出契约", u"答案锁在调用方给的选项里"),
            (u"部署形态", u"小、快、便宜，按调用计费")]
    hard = [(u"评测与数据生态", u"谁有带标注的题集、谁能证明校准度、下游愿不愿接"),
            (u"既有的替代品", u"小模型微调分类器、规则引擎、传统 ML 早已占住这个位置")]
    yy = _panel(d, 45, y, W - 90, u"容易被复制的三层", u"", edge=OLIVE, fill=SURFACE) + 12
    for n, w2 in easy:
        yy = _row(d, yy, n, w2, mark=OLIVE) + 0
    yy += 14
    yy = _panel(d, 45, yy, W - 90, u"抄不走的两层（真正的门槛在这）", u"", edge=PURPLE, fill=SURFACE) + 12
    for n, w2 in hard:
        yy = _row(d, yy, n, w2, mark=PURPLE) + 0
    _foot(d, yy + 10, u"所以「没有第二个」有两种完全不同的解释：门槛真高，或者窗口太短、"
                      u"也可能这个位置本来就被上面那些替代品占着。区分它们要看有没有公开的架构与训练细节可抄。")
    return _trim(img)


# ── 5 ────────────────────────────────────────────────────────────────────
def three_routes():
    img, d = canvas(W, 1000)
    y = _head(d, u"三条路线争的不是谁更强，是智能该以什么交付",
              u"交付一段文字 / 交付一份可微调的权重 / 交付一次可嵌进流程的判断")
    # 三栏的宽度要按「三栏 + 两个间距」算。上一版写成 /2.5，第三栏直接画到画布外，
    # 而截图看着"满了"——溢出到右边的东西肉眼在第一眼是看不见的。
    gap = 22
    colw = (W - 90 - gap * 2) / 3
    items = [(u"自回归继续 scaling", u"一段文字",
              u"成本与延迟随长度涨；格式与幻觉要另治", OLIVE),
             (u"开源与蒸馏 MoE", u"一份权重",
              u"得自己养推理与评测，省的是授权费不是工程", PURPLE),
             (u"非生成快速决策", u"一次判断",
              u"只能在你列出的选项里挑，说不出口也解释不出", OLIVE)]
    bottoms = []
    x = 45
    for ttl, give, weak, edge in items:
        yy = _panel(d, x, y, colw, ttl, u"", edge=edge, fill=SURFACE, tsize=24) + 10
        yy = _panel(d, x, yy, colw, u"交付：" + give, u"", edge=edge, fill=BG, tsize=21) + 8
        yy = _panel(d, x, yy, colw, u"自己承认的软肋", weak, edge=MUTED, fill=BG,
                    tsize=20, bsize=19, mark=edge)
        bottoms.append(yy)
        x += colw + gap
    _foot(d, max(bottoms) + 26, u"三条各自的可核对事实，与「谁更优」的裁决是两件事：这里只画交付什么与"
                                 u"各家自己承认的短板。要判断哪条适合你的流程，拿上一张图那两条曲线去测，"
                                 u"而不是看谁的发布会响。")
    return _trim(img)


# ── 6 ────────────────────────────────────────────────────────────────────
def option_set():
    img, d = canvas(W, 1000)
    y = _head(d, u"封闭选项的另一面：圈外的答案它永远选不到",
              u"格式不会错与看不见圈外，是同一条设计的两面")
    cx, cy2, r = 430, y + 250, 250
    d.ellipse([cx - r, cy2 - r, cx + r, cy2 + r], outline=OLIVE, width=3, fill=SURFACE)
    label(d, (cx, cy2 - r + 26), u"调用方给定的选项集合", size=21, color=OLIVE, anchor="ma")
    for i, ang in enumerate([210, 300, 30, 150, 90]):
        import math
        px = cx + int((r - 78) * math.cos(math.radians(ang)))
        py = cy2 + int((r - 78) * math.sin(math.radians(ang)))
        _chip(d, px - 62, py - 20, 124, 40, u"候选 %d" % (i + 1), on=(i == 2))
    ox, oy = cx + r + 190, cy2 - r + 60
    d.ellipse([ox - 13, oy - 13, ox + 13, oy + 13], outline=PURPLE, width=3)
    leader(d, (ox - 13, oy), (cx + r - 24, cy2 - 40), color=RULE)
    label(d, (ox + 26, oy - 8), u"你没列进去的那个正确答案", size=21, color=PURPLE)
    label(d, (ox + 26, oy + 22), u"对它来说不存在——不是选错，是无从选起", size=19, color=MUTED)
    yy = cy2 + r + 30
    yy = _row(d, yy, u"高置信度地选错", u"错法从「明显胡说」变成「看起来很有把握」，下游更难发现", mark=PURPLE) + 0
    _foot(d, yy + 10, u"另外几件它做不到的事都源于同一处：按字面读措辞而非意图；不擅长数数与算术；"
                      u"读日期、比颜色会错；不出文本，也就给不出「为什么」。")
    return _trim(img)


# ── 7 ────────────────────────────────────────────────────────────────────
def verification_loop():
    img, d = canvas(W, 1000)
    y = _head(d, u"自己验一遍的闭环：拿你的题集，别拿它的成绩单",
              u"每一环都防一种具体的失败，缺任一环，剩下的环就在给没测过的东西背书")
    steps = [(u"自建带标注题集", u"含边界题与「选项里没有正确答案」的题"),
             (u"同时出三张图", u"准确率、阈值—覆盖率、校准度——单点准确率不作结论"),
             (u"统计弃权表现", u"无答案题它会不会硬选一个；转人工的比例是多少"),
             (u"算每单总成本", u"推理费 + 重试 + 人审 + 错判代价，而不是只算省下的 token"),
             (u"留人审兜底与回滚", u"闸门可以关掉，且关掉之后流程仍能跑"),
             (u"存档并随版本重跑", u"模型或选项一改，前面四步全部重来")]
    yy = y + 6
    for i, (n, w2) in enumerate(steps):
        yy = _row(d, yy, u"%d. %s" % (i + 1, n), w2, mark=(PURPLE if i in (1, 3) else OLIVE)) + 0
    _foot(d, yy + 10, u"闭环里最容易被跳过的是第 3 与第 5 步：它们不提升任何指标，"
                      u"只在模型自信地选错时替你兜住。")
    return _trim(img)


# ── 8 ────────────────────────────────────────────────────────────────────
def watch_points():
    img, d = canvas(W, 1000)
    y = _head(d, u"接下来盯什么：五个能证伪它的观察点",
              u"不预测趋势，只写「如果……则说明……」，并给出推翻本篇的条件")
    rows = [(u"第三方带方法学的复算", u"出现 → 数字开始可信；只有转述 → 仍是厂商口径"),
            (u"第二个团队发布同形态模型并公开架构", u"出现 → 这是一条路线；缺席 → 更像一个产品定位"),
            (u"持牌机构披露用于实盘风控或合规闸门", u"出现 → 快速决策段被接受；否则量化用途仍是想象"),
            (u"官方给出可复现的评测协议与基线", u"出现 → 可以横向比；否则只能各说各话"),
            (u"有人因接入它而整段撤掉人审", u"出现 → 它真在改流程；这也是错判代价开始显形的时候")]
    yy = y + 6
    for n, w2 in rows:
        yy = _row(d, yy, n, w2) + 0
    _foot(d, yy + 10, u"推翻本篇判断的条件：若第 1 项复算显示厂商口径明显偏高，"
                      u"或第 4 项给出的协议表明它的评测集与真实任务无关，"
                      u"那么「适合当决策层」这个结论就要降级为「适合当受控的分类器」。")
    return _trim(img)


def agent_slot():
    img, d = canvas(W, 1000)
    y = _head(d, u"它站在流程的哪一格：请求进来之后，谁在哪一步被调用",
              u"深色三段是它目前的用法——拦一道、分一次流、读一次档；大模型仍在下游写内容")
    steps = [(u"用户请求 / 事件", u"带上下文进来", False),
             (u"Jev：闸门", u"这次调用能不能自动放行？高风险就转人工", True),
             (u"Jev：路由", u"按难易决定交给哪个模型、要不要开思考", True),
             (u"Jev：分类", u"进线分诊、邮件归档、工单打标", True),
             (u"大模型", u"生成回答、写代码、出报告——它不做这段", False),
             (u"工具与外部系统", u"下单、查库、改配置", False),
             (u"返回与留痕", u"谁答的、走没走人审，都要记下来", False)]
    yy = y + 6
    for i, (n, w2, hot) in enumerate(steps):
        yy = _row(d, yy, u"%d. %s" % (i + 1, n), w2,
                  mark=(PURPLE if hot else OLIVE), fill=(SOFT if hot else BG)) + 0
    _foot(d, yy + 10, u"这张图取代了原先放的一张 LangChain 检索流程图：那画的是 RAG 的管线，"
                      u"与本段论点无关，留着会把读者引到「Jev 是检索组件」上去。"
                      u"省下来的钱与延迟发生在第 2–4 步；第 5 步之后仍然是一次完整生成。")
    return _trim(img)


JOBS = [
    ("jev_output_paths.png", output_paths),
    ("jev_threshold_coverage.png", threshold_coverage),
    ("jev_pipeline_latency.png", pipeline_latency),
    ("jev_moat_layers.png", moat_layers),
    ("jev_three_routes.png", three_routes),
    ("jev_option_set.png", option_set),
    ("jev_verification_loop.png", verification_loop),
    ("jev_watch_points.png", watch_points),
    ("jev_agent_slot.png", agent_slot),
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
