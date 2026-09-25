# -*- coding: utf-8 -*-
"""Claude Opus 5.5 篇的示意图（示意图通道，D-22）。

为什么这五章必须画：图片阶段跑完，`coding-boundary`、`safety-as-measure`、
`hardware-demand`、`roadmap-implication`、`how-to-read` **一张图都没拿到**——
G-03 直接判"本章至少配图"。这不是采集器坏，是这些论点没有照片承载得了：
"评测分三层，第三层没有可信公开评测""风险半径由工具权限决定"
"参数量级怎么推到功耗""一个发布证明了什么、证伪了什么"。
（同一件事在加密篇、名创篇各撞过一次，教训是：**抽象章先想画什么，别先想拍什么**。）

图上**不写任何数字与日期**（D-22）：单价、上下文长度、评测分数、FLOP、席位、
参数量级都是可核查的量化断言，已经带来源地活在正文的 keyvalue_table 与 fact_strip 里。
烧进图片就绕过了 R-02——图片没有"图源"可点。所以推导链只画**链条与环节**，
不画任何一级的大小；三层评测只画**哪一层有公开评测、哪一层没有**。

三条从上一篇带过来的写法（都是被真实缺陷逼出来的）：
  * `_panel` 先量内容再画框——手写的框迟早溢出；
  * 折行宽度按**该栏自己的可用宽度**量，不按整块面板量；
  * 页脚画在内容结束处，`_trim` 才裁得掉空白。
"""
import os
import re
import sys

import _common

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = os.path.join(ROOT, ".probe", "drawn")

# 主题 petrol-amber，抄 web/src/tokens/index.ts
BG = "#F5F8F9"
SURFACE = "#EBEEF6"
INK = "#131A1E"
MUTED = "#5C6B72"
RULE = "#D6E1E6"
NAVY = "#124559"       # primary
AMBER = "#F2A65A"      # accent
SOFT = "#DCE9EE"

font, canvas, label, leader = _common.make({"bg": BG, "ink": INK, "accent": NAVY})

_CHUNK = re.compile(u"[A-Za-z0-9_\\-–—/×.+·()%]+|\\s|.", re.U)
W, H = 1500, 1150


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


def _panel(d, x, y, w, title, body, edge=None, fill=BG, tsize=27, bsize=22, pad=18, mark=None):
    edge = edge or NAVY
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


def _row(d, y, name, why, name_w=340, left=45, width=1410, fill=BG, mark=NAVY):
    """左栏定宽、右栏从固定 x 起——两栏各折各的宽，才不会叠字。"""
    nf, wf = font(24), font(22)
    nl = _fit(name, nf, name_w)
    wl = _fit(why, wf, width - (name_w + 90) - 24)
    h = 34 + max(_lh(nf) * len(nl), _lh(wf) * len(wl))
    _box(d, left, y, width, h, RULE, fill=fill)
    d.rectangle([left, y, left + 7, y + h], fill=mark)
    cy = y + 16
    for ln in nl:
        label(d, (left + 26, cy), ln, size=24, color=NAVY)
        cy += _lh(nf)
    cy = y + 17
    for ln in wl:
        label(d, (left + name_w + 90, cy), ln, size=22, color=INK)
        cy += _lh(wf)
    return y + h + 14


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


def coding_layers():
    img, d = canvas(W, H)
    label(d, (45, 34), u"写代码的三层，只有两层有可信评测", size=38, color=NAVY)
    label(d, (45, 92), u"演示永远挑最像成功的那一层——所以先问「这是哪一层」。",
          size=23, color=MUTED)
    y = 150
    y = _row(d, y, u"第一层：补全与单函数",
             u"早已商品化。看起来最「像在用」，但提升幅度与体感差别都不大，"
             u"拿它当证据说明不了什么。", fill=SURFACE)
    y = _row(d, y, u"第二层：跨文件改动 + 跑通既有测试",
             u"近年的跳变发生在这一层。判据不是「生成看起来对的 diff」，"
             u"而是「在真实仓库里让既有测试变绿」——这一层有公开评测，但样本小、任务不可复用。",
             fill=BG, mark=AMBER)
    y = _row(d, y, u"第三层：架构改动与长期维护",
             u"基本没有可信的公开评测。任何断言都要标注「证据缺失」，"
             u"而不是引用一段演示视频。", fill=SURFACE)
    y = _panel(d, 45, y + 8, 1410, u"还有一层经常被算进「模型能力」：工具链",
               u"IDE 集成、代码检索、CI 反馈、评审流程。同一模型换一套脚手架，"
               u"结果能差出十几个百分点——那部分是工程，不是智力。", edge=AMBER, fill=BG)
    _foot(d, y + 26, u"示意图·非实拍：只画分层与判据，不含任何分数、通过率或版本号")
    return img


def risk_radius():
    img, d = canvas(W, H)
    label(d, (45, 34), u"风险半径不是模型属性，是「模型 × 权限 × 部署」", size=38, color=NAVY)
    label(d, (45, 92), u"同一个模型，三行配置下的事故范围差一个量级。", size=23, color=MUTED)
    y = 150
    y = _row(d, y, u"模型本身：会说错什么",
             u"对齐评测按类别看，不看一个总分。「拒绝率下降」既可能是更贴合需求，"
             u"也可能是更松——必须看是哪一类降的。", fill=SURFACE)
    y = _row(d, y, u"权限：能替你做什么",
             u"只读检索、能改文件、能发请求、能花钱——每上一档，同一个错误的后果大一档。"
             u"提示注入真正打开的就是这一档。", fill=BG, mark=AMBER)
    y = _row(d, y, u"部署：出错时谁被通知",
             u"有没有人工确认关口、能不能回滚、日志留在哪、谁的凭据在跑。"
             u"这一行决定了前两行是「质量问题」还是「事故」。", fill=SURFACE)
    y = _panel(d, 45, y + 8, 1410, u"读安全章节时真正有用的三个问题",
               u"①失败时谁被通知、能不能撤销？②哪些动作需要人确认，确认是默认开还是默认关？"
               u"③权限边界是按会话、按工具、还是按凭据划的？"
               u"——比问「它更安全了吗」可回答得多。", edge=AMBER, fill=BG)
    _foot(d, y + 26, u"示意图·非实拍：只描述机制与现状，不含任何绕过方法、提示模板或工具选型")
    return img


def hardware_chain():
    img, d = canvas(W, H)
    label(d, (45, 34), u"从参数量级推到功耗：一条链，每一环都要标来源", size=38, color=NAVY)
    label(d, (45, 92), u"能被引用的只有链条结构；任何一环的数字都要注明是披露还是估算。",
          size=23, color=MUTED)
    steps = [
        (u"参数量级", u"多数不披露；有披露也要问是总参数还是激活参数"),
        (u"每 token 前向算力", u"量级由参数量推出，是估算不是测量"),
        (u"一次请求的 token", u"含思考预算——这一环最容易被忽略，也最能放大成本"),
        (u"吞吐与延迟目标", u"首 token 延迟与并发决定要留多少余量"),
        (u"显存：权重 + KV 缓存", u"KV 随上下文长度与并发增长，长上下文时它可能比权重大"),
        (u"带宽与互联", u"推理多为访存受限：算力买不来带宽"),
        (u"功耗与机房", u"供电、冷却、PUE——最后卡在电和水上"),
    ]
    y = 150
    for i, (name, why) in enumerate(steps):
        y = _row(d, y, u"%d. %s" % (i + 1, name), why,
                 fill=(SURFACE if i % 2 == 0 else BG),
                 mark=(AMBER if i in (2, 4) else NAVY))
    y = _panel(d, 45, y + 6, 1410, u"为什么「训练侧」和「推理侧」不是同一件事",
               u"训练看互联与显存池（一个大作业），推理看带宽、单位成本与部署密度"
               u"（无数个小请求）。推理时算力把需求从前者推向后者——"
               u"这也是为什么「算力不够了」这句话必须说清是哪一侧。", edge=AMBER, fill=BG)
    _foot(d, y + 26, u"示意图·非实拍：只画推导链与口径要求，不含任何参数、FLOP、显存或功耗数值")
    return img


def evidence_tiers():
    img, d = canvas(W, H)
    label(d, (45, 34), u"一次发布改变的是「带口径的观测」，不是「关于能力的判断」",
          size=36, color=NAVY)
    label(d, (45, 92), u"讨论里最常见的错位：把第三层当前两层用。", size=23, color=MUTED)
    y = 150
    y = _row(d, y, u"第一层：观测",
             u"某个评测、某个子集、某个预算下的分数。可复现、可打脸。", fill=SURFACE)
    y = _row(d, y, u"第二层：机制解释",
             u"为什么这个数会变——通常只能给假设，因为训练细节不披露。", fill=BG)
    y = _row(d, y, u"第三层：叙事",
             u"「范式转移」「某某已死」。它不需要证据，也永远不会被证伪。",
             fill=SURFACE, mark=AMBER)
    y = _panel(d, 45, y + 8, 1410, u"这一版让哪三类说法变了",
               u"证据变强：可验证任务上「多给推理预算换更高正确率」（多方独立观测）。"
               u"看起来变强其实没有：「规模到头」「数据是唯一瓶颈」——依赖不可核的训练细节。"
               u"留下新问题：评测该怎么报口径、成本该怎么算、agent 的权限边界由谁定。",
               edge=AMBER, fill=BG)
    _foot(d, y + 26, u"示意图·非实拍：只画证据分层与判断归属，不含分数与版本号")
    return img


def ten_questions():
    img, d = canvas(W, H)
    label(d, (45, 34), u"下次模型发布，先问这十个问题", size=38, color=NAVY)
    label(d, (45, 92), u"每一条都对应本篇某一章的真实卡点——不是礼仪清单。",
          size=23, color=MUTED)
    qs = [
        u"分数是哪个子集、给了多少思考预算？",
        u"对比对象用的是同一套脚手架吗？",
        u"有第三方复现吗，还是只有厂商自报？",
        u"价格报的是原价，还是含缓存折扣？限速多少？",
        u"长任务评测判的是终态还是过程？失败怎么算？",
        u"编码评测跑的是真实仓库测试，还是看起来对的输出？",
        u"「自我改进」的说法里，人类监督点在哪一步？",
        u"安全数据是否按类别拆？有没有人工确认关口？",
        u"硬件数字是披露还是估算？假设是什么？",
        u"哪些说法只有转述、没有一手来源？",
    ]
    y = 150
    for i, q in enumerate(qs):
        col = i % 2
        row = i // 2
        x = 45 + col * 712
        if col == 0 and i > 0:
            y += 96
        _box(d, x, y, 690, 84, RULE, fill=(SURFACE if row % 2 == 0 else BG))
        d.ellipse([x + 18, y + 22, x + 62, y + 66], outline=NAVY, width=3)
        label(d, (x + 27, y + 28), str(i + 1), size=24, color=NAVY)
        for k, ln in enumerate(_fit(q, font(22), 690 - 96)):
            label(d, (x + 78, y + 20 + k * 30), ln, size=22, color=INK)
    y += 108
    _foot(d, y, u"示意图·非实拍：问题清单，不含任何数值、分数与结论性判断")
    return img


JOBS = [
    ("coding_layers.png", coding_layers),
    ("risk_radius.png", risk_radius),
    ("hardware_chain.png", hardware_chain),
    ("evidence_tiers.png", evidence_tiers),
    ("ten_questions.png", ten_questions),
]


def main():
    if not os.path.isdir(OUT):
        os.makedirs(OUT)
        pass
    only = sys.argv[1:] or None
    for name, fn in JOBS:
        if only and name not in only:
            continue
        p = os.path.join(OUT, name)
        _trim(fn()).save(p, "PNG")
        print("%s  %d KB" % (p, os.path.getsize(p) // 1024))


if __name__ == "__main__":
    main()
