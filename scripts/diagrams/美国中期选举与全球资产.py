# -*- coding: utf-8 -*-
"""美国中期选举与全球资产篇的示意图（示意图通道，D-22）。

为什么这一篇十一张全画：图片阶段抓回来的 15 张里，12 张是国会大厦外观，
其中多张来自旅游攻略页；一张是带商家水印的金条商品图；一张是人名头像卡
（文件名却叫"美联储总部建筑"）。根因不在引擎：`gated_queries` 会给每条章节词
补一个领域主语前缀（`美国国会 投票站 排队`），于是 11 章全部塌到同一个建筑上。
所以 15 张全摘，重画。**这一条是 W-142 的第二个实例**，机制比第一次清楚。

图上**不写任何数字与日期**（D-22）：席位、票数、税率、赤字率、传导率、日期
都是可核查的量化断言，已经带来源地活在正文的 keyvalue_table 与 fact_strip 里。
烧进图片就绕过了 R-02——图片没有"图源"可点。所以只画**结构与归属**：
哪一层把民意换成席位、一条工具的寿命由什么决定、哪条链条经过哪些可观测量。

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

# 主题 ballot-navy，抄 web/src/tokens/index.ts
BG = "#F7F8FB"
SURFACE = "#EBEEF6"
INK = "#12161F"
MUTED = "#5A6274"
RULE = "#DCE0EA"
NAVY = "#16326B"       # primary
GREEN = "#3FA34D"      # accent（两色不指定阵营，红线 R-09）
SOFT = "#E1EBE2"

font, canvas, label, leader = _common.make({"bg": BG, "ink": INK, "accent": NAVY})

_CHUNK = re.compile(u"[A-Za-z0-9_\\-–—/×.+·()%]+|\\s|.", re.U)
W, H = 1500, 1180


def _box(d, x, y, w, h, edge, fill=BG, width=2, radius=12):
    d.rounded_rectangle([x, y, x + w, y + h], radius=radius,
                        fill=fill, outline=edge, width=width)


_TAIL_OK = u"。，、；：？！）】」’”%·—–"


def _fit(text, fnt, maxw):
    """折行。收尾标点不许单独成行——中文里「。」独占一行比英文难看得多，
    而正文折行处一多就会撞上一个（实测在多处出现）。"""
    lines, cur, w = [], u"", 0
    for tk in _CHUNK.findall(text):
        bb = fnt.getbbox(tk)
        tw = bb[2] - bb[0]
        if cur and w + tw > maxw and (not tk.strip() or tk not in _TAIL_OK):
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


def _title(d, main, sub):
    label(d, (45, 34), main, size=37, color=NAVY)
    for i, ln in enumerate(_fit(sub, font(23), W - 90)):
        label(d, (45, 96 + i * 30), ln, size=23, color=MUTED)
    return 96 + _lh(font(23)) * len(_fit(sub, font(23), W - 90)) + 22


def _panel(d, x, y, w, title, body, edge=None, fill=BG, tsize=26, bsize=22, pad=18, mark=None):
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


def _row(d, y, name, why, left=45, width=1410, name_w=340, fill=BG, mark=NAVY, gap=90):
    """左栏定宽、右栏从固定 x 起——两栏各折各的宽，才不会叠字。"""
    nf, wf = font(24), font(22)
    nl = _fit(name, nf, name_w)
    wl = _fit(why, wf, width - (name_w + gap) - 24)
    h = 34 + max(_lh(nf) * len(nl), _lh(wf) * len(wl))
    _box(d, left, y, width, h, RULE, fill=fill)
    d.rectangle([left, y, left + 7, y + h], fill=mark)
    cy = y + 16
    for ln in nl:
        label(d, (left + 26, cy), ln, size=24, color=NAVY)
        cy += _lh(nf)
    cy = y + 17
    for ln in wl:
        label(d, (left + name_w + gap, cy), ln, size=22, color=INK)
        cy += _lh(wf)
    return y + h + 14


def _chip(d, x, y, w, text, size=22, color=NAVY, fill=SURFACE, pad=14, align="la"):
    f = font(size)
    lines = _fit(text, f, w - pad * 2)
    h = pad * 2 + _lh(f) * len(lines)
    _box(d, x, y, w, h, RULE, fill=fill, radius=10)
    cy = y + pad
    for ln in lines:
        bb = f.getbbox(ln)
        tw = bb[2] - bb[0]
        tx = x + (w - tw) // 2 if align == "ma" else x + pad
        label(d, (tx, cy), ln, size=size, color=color)
        cy += _lh(f)
    return y + h


def _foot(d, y, text):
    for i, ln in enumerate(_fit(text, font(19), W - 90)):
        label(d, (45, y + i * 26), ln, size=19, color=MUTED)


def _foot_h(text):
    return _lh(font(19)) * len(_fit(text, font(19), W - 90))


def _col_measure(head, anchor, body, w, pad=24, gap=12):
    """先量内容再画框。写死高度是这一篇 v1 唯一的系统性缺陷：
    三栏内容长短不一，框却等高，于是每栏底下都空出一截。"""
    hf, af, bf = font(28), font(22), font(20)
    hl = [head]
    al = _fit(anchor, af, w - pad * 2)
    bl = _fit(body, bf, w - pad * 2) if body else []
    h = pad * 2 + _lh(hf) * len(hl) + gap + _lh(af) * len(al) + gap + _lh(bf) * len(bl)
    return h, (hf, af, bf, hl, al, bl, pad, gap)


def _col_draw(d, x, y, w, head, anchor, body, edge, fill, pad=24, gap=12, h=None):
    hh, (hf, af, bf, hl, al, bl, pad, gap) = _col_measure(head, anchor, body, w, pad, gap)
    h = max(h or 0, hh)
    _box(d, x, y, w, h, edge, fill=fill)
    d.rectangle([x, y, x + 7, y + h], fill=edge)
    cy = y + pad
    for ln in hl:
        label(d, (x + pad + 6, cy), ln, size=28, color=edge)
        cy += _lh(hf)
    cy += gap
    for ln in al:
        label(d, (x + pad + 6, cy), ln, size=22, color=NAVY)
        cy += _lh(af)
    cy += gap
    for ln in bl:
        label(d, (x + pad + 6, cy), ln, size=20, color=INK)
        cy += _lh(bf)
    return y + h


def _cols(d, y, items, gap=26, left=45, width=1410):
    """items: [(head, anchor, body, edge, fill)]。等高，但高等于**最高那栏的内容**。"""
    n = len(items)
    cw = (width - gap * (n - 1)) // n
    hs = [_col_measure(it[0], it[1], it[2], cw)[0] for it in items]
    top = max(hs)
    x = left
    for head, anchor, body, edge, fill in items:
        _col_draw(d, x, y, cw, head, anchor, body, edge, fill, h=top)
        x += cw + gap
    return y + top


def _trim(img, margin=26):
    bg = img.getpixel((4, img.height - 4))
    last = 0
    for y in range(img.height - 1, -1, -1):
        row = [img.getpixel((x, y)) for x in range(0, img.width, 7)]
        if any(abs(p[0] - bg[0]) + abs(p[1] - bg[1]) + abs(p[2] - bg[2]) > 12 for p in row):
            last = y
            break
    return img.crop((0, 0, img.width, min(img.height, last + margin)))


def _arrow(d, x1, y1, x2, y2, color=None):
    c = color or NAVY
    d.line([x1, y1, x2, y2], fill=c, width=3)
    d.polygon([(x2, y2), (x2 - 13, y2 - 8), (x2 - 13, y2 + 8)], fill=c)


# ---------------------------------------------------------------- 1 民调读数
def poll_layers():
    img, d = canvas(W, H)
    y = _title(d, u"一条民调要凑齐四项，一个均值背后是三套算法",
               u"通用 ballot 量的是此刻的政党偏好。它离席位还隔着两步，而这两步都不是机械换算。")
    y = _row(d, y, u"第一条读数", u"抽样框（全体成人 / 注册选民 / 可能参选者）、调查时间窗、"
                                  u"样本量、误差幅度——缺一项的引用不成立。", fill=SURFACE)
    y = _row(d, y, u"汇总方的算法", u"有人做简单平均；有人先算机构影响力分数再把一贯偏差退回去；"
                                    u"有人对同一指标混用两种问法。均值长什么样，一半是算法决定的。",
             fill=BG, mark=GREEN)
    y = _row(d, y, u"报出来的均值", u"只描述当下偏好。领先幅度不超过误差幅度时，两党在统计上就是没差别。",
             fill=SURFACE)
    y = _panel(d, 45, y + 8, 1410, u"同一条民调里常混着两种问法",
               u"「你打算把本选区的票投给哪一党」与「你更希望哪一党控制国会」不是同一个问题。"
               u"同一批民意、三套算法，方向都能不同——所以看到「领先 N 个点」先问口径，"
               u"再问它凭什么换算成席位。", edge=GREEN, fill=BG)
    _foot(d, y + 26, u"示意图·非实拍：只画读数到均值的层级与口径要求，不含任何百分比、点数与机构排名")
    return img


# ---------------------------------------------------------------- 2 三层转换器
def converters():
    img, d = canvas(W, H)
    y = _title(d, u"民意要穿过三层转换器才变成席位",
               u"全国领先只是这三层的输入。跳过它们直接把民调换成资产配置，是这一篇要挡住的第一个错法。")
    y = _chip(d, 45, y, W - 90, u"全国政党偏好（通用 ballot 的均值）",
              size=26, color=BG, fill=NAVY, pad=18, align="ma") + 14
    _arrow(d, W // 2, y, W // 2, y + 44, color=GREEN)
    y += 58
    boxes = [
        (u"第一层：选区地图", u"票落在哪条边界",
         u"单一选区制下，边界决定一张票算不算数。重划、种族票斜诉讼、初选时点都在这层。",
         NAVY, SURFACE),
        (u"第二层：改选名单", u"哪批席位到期",
         u"参院每州两席、六年错开改选三分之一。哪批席位暴露、现任是否退休，与民意无关地先写好了。",
         NAVY, SURFACE),
        (u"第三层：投票规则", u"谁来投",
         u"州议会和州长跑。送达截止、身份核验、邮寄票范围——改的是「谁来投」，不是「谁得票」。",
         GREEN, SOFT),
    ]
    n = len(boxes)
    gap = 46
    cw = (1410 - gap * (n - 1)) // n
    hs = [_col_measure(b[0], b[1], b[2], cw)[0] for b in boxes]
    top = max(hs)
    x = 45
    for i, (head, anchor, body, edge, fill) in enumerate(boxes):
        _col_draw(d, x, y, cw, head, anchor, body, edge, fill, h=top)
        if i < n - 1:
            _arrow(d, x + cw + 6, y + top // 2, x + cw + gap - 6, y + top // 2)
        x += cw + gap
    y += top + 14
    _arrow(d, W // 2, y, W // 2, y + 44, color=GREEN)
    y += 58
    y = _chip(d, 45, y, W - 90, u"席位", size=27, color=BG, fill=NAVY, pad=18, align="ma") + 16
    y = _panel(d, 45, y, 1410, u"这三层的换算高度非线性",
               u"不能把净差乘个系数就换成席位。所以本篇先画三张表——换了哪些地图、"
               u"哪批席位到期、生效了哪几条规则——民调只在表上修正换算率。", edge=GREEN, fill=BG)
    _foot(d, y + 26, u"示意图·非实拍：只画三层转换器的归属与顺序，不含席位数、州名清单与任何读数")
    return img


# ---------------------------------------------------------------- 3 两类牌
def two_axes_cards():
    img, d = canvas(W, H)
    y = _title(d, u"一张牌要放在两个维度上看：谁能启动、谁能撤销",
               u"本章不评价主张好坏，只把工具摊开。制度性牌靠规则本身启动；议程性牌写进党纲不等于落地。")
    y = _cols(d, y, [
        (u"制度性牌", u"靠规则本身启动",
         u"规则就给：预算调和的辩论时限、委员会程序、行政令的签发即生效、州议会定规则。"
         u"但每一张都有边界——与指令无关、纯属附带、在窗口之外扩大赤字的条款"
         u"可被程序异议当场剔除，豁免本身仍要那道更高的门槛。", NAVY, SURFACE),
        (u"议程性牌", u"看它落在哪一层权限",
         u"党纲里的诉求要靠哪一层权限落地才算数。同一件工具，国会立法、行政令、"
         u"机构指南是三种完全不同的寿命与成本；写在纸上的那一版最便宜，也最容易撤。",
         GREEN, SOFT),
    ]) + 22
    y = _panel(d, 45, y, 1410, u"读任何一张牌时问三件事",
               u"谁能撤销它：下一任总统、下一届国会，还是法院。"
               u"多久见效：行政令当天，规则废改按月，法案要等生效日。"
               u"代价落在谁身上：进口价格、赤字条款，还是退税争议。", edge=GREEN, fill=BG)
    _foot(d, y + 26, u"示意图·非实拍：只画工具的分类维度与三问，不含票数、门槛值与法案编号")
    return img


# ---------------------------------------------------------------- 4 执行链
def enforcement_chain():
    img, d = canvas(W, H)
    y = _title(d, u"少数党的工具有一条执行链，链尾决定作用半径",
               u"传票不是「阻止」，是抬高成本、拖慢节奏、把文件沉进公开记录。差别就在链条走到哪一段。")
    steps = [
        (u"委员会", u"授权与签发写在议院规则里，靠委员会多数票"),
        (u"全院表决", u"藐视认定要再过一道全院"),
        (u"移送检察官", u"到这一步才算交到执行机关手上"),
        (u"起诉裁量", u"司法部主张自己有不起诉的裁量——链在这里断掉"),
    ]
    cw = (W - 90 - 3 * 40) // 4
    hf, bf = font(25), font(20)
    hs = [24 + _lh(hf) + 12 + _lh(bf) * len(_fit(w, bf, cw - 40)) + 24 for _, w in steps]
    top = max(hs)
    x = 45
    for i, (name, why) in enumerate(steps):
        edge = GREEN if i == 3 else NAVY
        _box(d, x, y, cw, top, edge, fill=(SOFT if i == 3 else SURFACE))
        d.rectangle([x, y, x + 7, y + top], fill=edge)
        label(d, (x + 20, y + 20), name, size=25, color=edge)
        cy = y + 20 + _lh(hf) + 12
        for ln in _fit(why, bf, cw - 40):
            label(d, (x + 20, cy), ln, size=20, color=INK)
            cy += _lh(bf)
        if i < 3:
            _arrow(d, x + cw + 6, y + top // 2, x + cw + 34, y + top // 2)
        x += cw + 40
    yy = y + top + 26
    yy = _row(d, yy, u"另一组牌不经过国会", u"州长、州总检察长、地方检察官。同一部州法，"
                                          u"可以选择不起诉，也可以排在最前面——"
                                          u"这种执行差异不受参院那道门槛约束。", fill=SURFACE)
    yy = _panel(d, 45, yy + 6, 1410, u"链上每一段的可撤销性不一样",
                u"几名委员联署索件的规则写在联邦法典里，但本届议院附加了"
                u"「联署人里要有委员会主席」，而主席在多数党手里——"
                u"这条附加要求能不能改写法律，法院没有结论。", edge=GREEN, fill=BG)
    _foot(d, yy + 26, u"示意图·非实拍：只画程序链与其归属，不含票数、人名与任何案件结论")
    return img


# ---------------------------------------------------------------- 5 四种寿命
def lifespans():
    """散点版第一版就废了：四个点的手写坐标互相压框，读者认不出哪个点配哪个标签，
    而且「位置」暗示了一条根本没有来源的连续刻度。改成表：档位用词，不用坐标。"""
    img, d = canvas(W, H)
    y = _title(d, u"同一句承诺有四种寿命：生效快慢与撤销代价互不对称",
               u"把一次选举结果读成「政策十年不变」，是常见的错法。四个工具放一起，两列档位差得很远。")
    left, width = 45, 1410
    name_w, col_w = 300, 430
    nf, bf, hf = font(24), font(21), font(22)
    hy = y
    _box(d, left, hy, width, 54, NAVY, fill=SURFACE, radius=10)
    label(d, (left + 26, hy + 14), u"工具", size=22, color=NAVY)
    label(d, (left + name_w + 40, hy + 14), u"生效要过什么", size=22, color=NAVY)
    label(d, (left + name_w + col_w + 80, hy + 14), u"撤销要花什么", size=22, color=NAVY)
    y = hy + 54 + 12

    rows = [
        (u"行政令 / 关税", u"签发即开征；须公布于联邦公报",
         u"一纸新令即可暂停或恢复——同一批措施可在几天内被改写过两次", True),
        (u"执行与解释环节", u"政治宣布之后还要补指南与纳品程序",
         u"下一任可直接改写；企业实际缴纳时点与退税争议由它决定", False),
        (u"机构立法性规则", u"公告—评论—最终规则，重大规则还要留审查窗口",
         u"重走一遍程序，或被法院推翻", False),
        (u"税法条款", u"要过国会，按应税年度落地",
         u"再赢一次投票；但调和产出的条款常自带日落，到期日写在法条里", True),
    ]
    for name, on, off, hl in rows:
        nl = _fit(name, nf, name_w)
        ol = _fit(on, bf, col_w - 40)
        fl = _fit(off, bf, col_w - 40)
        h = 30 + max(_lh(nf) * len(nl), _lh(bf) * len(ol), _lh(bf) * len(fl))
        edge = GREEN if hl else NAVY
        _box(d, left, y, width, h, RULE, fill=(SOFT if hl else BG))
        d.rectangle([left, y, left + 7, y + h], fill=edge)
        cy = y + 15
        for ln in nl:
            label(d, (left + 26, cy), ln, size=24, color=edge)
            cy += _lh(nf)
        cy = y + 16
        for ln in ol:
            label(d, (left + name_w + 40, cy), ln, size=21, color=INK)
            cy += _lh(bf)
        cy = y + 16
        for ln in fl:
            label(d, (left + name_w + col_w + 80, cy), ln, size=21, color=INK)
            cy += _lh(bf)
        y += h + 12
    y = _panel(d, left, y + 4, width, u"落点各不相同",
               u"同一目标走关税、走补贴还是走监管，落在通胀、赤字、汇率上的形态完全不同。"
               u"所以「第一天就定价完」是反着读的：第一个交易日反映的是概率变化，不是终局。"
               u"真正可核查的是税则号与报关时刻，而不是新闻稿的措辞。", edge=GREEN, fill=BG)
    _foot(d, y + 26, u"示意图·非实拍：档位说的是机制上的先后与难易，不是时间表；"
                     u"具体生效日、暂停期与到期年都在正文表格里，逐条带来源")
    return img


# ---------------------------------------------------------------- 6 五条链条
def channels():
    img, d = canvas(W, H)
    y = _title(d, u"先讲链条，再讲资产：中间隔着三个可观测的量",
               u"「谁赢就买什么」跳过了中间环节。顺序是：选举改政策，政策改观测量，观测量改价格变量。")
    chans = [
        (u"财政链条", u"赤字 → 净发债规模与期限结构 → 期限溢价。所有资产贴现率的分母。"),
        (u"关税链条", u"第一站是进口单价，不是 CPI。进口方与出口方各吸收一块，剩下的才进核心通胀。"),
        (u"制度可信度链条", u"最难量化，载体却是文件与日程：特别措施公告、停摆期间的发布取消、央行人事。"),
        (u"增长链条", u"不确定性作用在不可逆决策上：设备、厂房、招聘。表现为订单推迟，不是当期利润下滑。"),
        (u"流动性链条", u"发债与税款进出国库账户，直接挪动准备金；准备金一紧，短端利率分位先跳。"),
    ]
    for i, (name, why) in enumerate(chans):
        y = _row(d, y, name, why, fill=(SURFACE if i % 2 == 0 else BG),
                 mark=(GREEN if i in (2, 4) else NAVY))
    y = _panel(d, 45, y + 6, 1410, u"读数会缺席，所以先存基线",
               u"停摆期间统计发布可以整期取消、推迟回补还带缺口——制度链条就在这种日程上现形。"
               u"开票前先把各序列的当日读数存成基线；选后每次跳升都问一句："
               u"哪条链条动了、哪个数据在动。答不出来，就当噪声。", edge=GREEN, fill=BG)
    _foot(d, y + 26, u"示意图·非实拍：只画链条结构与观测量归属，不含任何比率、规模与日期")
    return img


# ---------------------------------------------------------------- 7 两数相乘
def price_split():
    img, d = canvas(W, H)
    y = _title(d, u"一次价格变化是两数相乘：盈利预期 × 倍数",
               u"选举夜里跳动的多数是后者。把倍数压缩说成「经济变差」，是最常见的误读。")
    cw = (W - 90 - 52) // 2
    b1 = _chip(d, 45, y, cw, u"盈利预期 · 市场认为一元盈利值多少",
               size=25, color=INK, fill=SURFACE, pad=26, align="ma")
    b2 = _chip(d, 45 + cw + 52, y, cw, u"倍数 · 为一元盈利愿付多少",
               size=25, color=BG, fill=NAVY, pad=26, align="ma")
    top = max(b1, b2)
    label(d, (45 + cw + 26, y + top // 2 - 24), u"×", size=44, color=GREEN, anchor="mm")
    yy = top + 22
    yy = _row(d, yy, u"只看指数涨跌幅", u"两个因子混在一起，说不清是谁在动。", fill=BG)
    yy = _row(d, yy, u"并排看三行公开日频数据", u"指数涨跌幅、盈利预期修正方向、长端国债收益率。"
                                             u"三者都是公开数，区分只需并排，不需要预测。",
              fill=SURFACE, mark=GREEN)
    yy = _panel(d, 45, yy + 6, 1410, u"敏感度看两张结构表，不看口号",
                u"收入端：按地域拆分的收入结构，决定美元强弱与海外需求收缩落在哪些公司。"
                u"成本端：按终用途发布的月度进口表，决定关税落在哪些行业。"
                u"两者只回答谁暴露在哪个变量下，不回答该买什么。", edge=NAVY, fill=BG)
    _foot(d, yy + 26, u"示意图·非实拍：只画分解方式与读数方法，不含任何指数点位、市盈率与收益率")
    return img


# ---------------------------------------------------------------- 8 两条资金通道
def two_flows():
    img, d = canvas(W, H)
    y = _title(d, u"给两边定价的钱不是同一笔：两条通道分开画",
               u"同一条选举新闻落到两个市场的机制不同，套用同一套结论就是把两条通道混成一条。")
    sides = [
        (u"A股：境内定价", [(u"主导资金", u"境内资金"),
                          (u"外资入口", u"北向通进出，但日常成交占比有限"),
                          (u"披露口径", u"盘中逐只实时净额已停披；收市后成交总额与前十大活跃证券仍公布"),
                          (u"传导入口", u"更多走出口链与内需链的预期差")], NAVY, SURFACE),
        (u"港股：离岸定价", [(u"估值锚", u"离岸美元流动性与联储利率"),
                          (u"本地资金", u"没有本地资金池托底"),
                          (u"内资入口", u"南向与港股通，按交易日公布统计"),
                          (u"传导入口", u"更多走汇率、美元与风险偏好")], GREEN, SOFT),
    ]
    cw = (W - 90 - 26) // 2
    kf, vf = font(22), font(21)
    key_w = 210

    def measure(rows):
        tot = 20 + _lh(font(27)) + 18
        for k, v in rows:
            tot = tot + max(_lh(kf), _lh(vf) * len(_fit(v, vf, cw - key_w - 46))) + 14
        return tot + 14

    top = max(measure(s[1]) for s in sides)
    for i, (head, rows, edge, fill) in enumerate(sides):
        x = 45 + i * (cw + 26)
        _box(d, x, y, cw, top, edge, fill=fill)
        d.rectangle([x, y, x + 7, y + top], fill=edge)
        label(d, (x + 26, y + 20), head, size=27, color=edge)
        cy = y + 20 + _lh(font(27)) + 18
        for k, v in rows:
            label(d, (x + 26, cy), k, size=22, color=NAVY)
            vy = cy
            for ln in _fit(v, vf, cw - key_w - 46):
                label(d, (x + key_w + 26, vy), ln, size=21, color=INK)
                vy += _lh(vf)
            cy = max(cy + _lh(kf), vy) + 14
    _foot(d, y + top + 26, u"示意图·非实拍：只画两条通道的构成，不含成交额、占比与任何政策时点")
    return img


# ---------------------------------------------------------------- 9 三个锚
def three_anchors():
    img, d = canvas(W, H)
    y = _title(d, u"三种资产被三样东西定价：先找锚，别看旗号",
               u"把「谁当选就买什么」当主线，等于拿一把尺子量三样东西。先判断这条链条会不会因选举而移动。")
    y = _cols(d, y, [
        (u"黄金", u"锚：实际利率 + 官方储备增减",
         u"持有它的机会成本看通胀保值债券隐含的实际利率；储备看各国央行与国际机构的申报，"
         u"未申报部分由机构估算。「避险所以涨」在历史数据里并不稳。", NAVY, SURFACE),
        (u"石油", u"锚：供给曲线，不是选票",
         u"选举几乎不移动供给曲线。真正改变它的是产油国集团的产量目标、"
         u"页岩企业的资本开支纪律，以及对增速与制造业景气的需求预期。", NAVY, BG),
        (u"数字货币", u"锚：制度变量，间接传导",
         u"对审批、费用、立法与税收处理高度敏感；与选举结果本身，"
         u"多数通过流动性和风险偏好间接传导。只报事实，不给方向，也不评价任何币种的安全性。",
         GREEN, SOFT),
    ]) + 22
    y = _panel(d, 45, y, 1410, u"为什么「口号」不可核查",
               u"口号把三把不同的尺子混成一把。可核查的做法是：先确认那个锚上的关键变量"
               u"有没有真的移动，再谈资产。", edge=GREEN, fill=BG)
    _foot(d, y + 26, u"示意图·非实拍：只画定价锚的归属，不含价格、吨数、持仓与任何方向判断")
    return img


# ---------------------------------------------------------------- 10 情景表
def scenario_grid():
    img, d = canvas(W, H)
    y = _title(d, u"情景表不是概率表：概率那一列是空的，且故意空着",
               u"民调只回答「现在谁领先」。把它换算成「谁赢就买什么」，概率只能来自没人复核的模型。")
    rows = [
        (u"守住两院", u"关税链与哪一党控制国会无关：开关在法条与法院手里，"
                      u"一处被判越权，同日就改按另一条法条征临时附加费，随后又被认定不满足法定要件。"),
        (u"失去一院", u"预算还能过，工具照旧用。一院通过撤销决议，"
                      u"另一院可以被议长设的特殊规则挡住，之后还有否决权。"),
        (u"两院易手（僵府）", u"僵府不等于财政收紧：分裂政府年份里赤字可以创纪录，"
                             u"因为发债由同一批程序决定。"),
    ]
    name_w = 300
    for i, (name, why) in enumerate(rows):
        y = _row(d, y, name, why, name_w=name_w, fill=(SURFACE if i % 2 == 0 else BG),
                 mark=(GREEN if i == 2 else NAVY))
    y = _panel(d, 45, y + 6, 1410, u"表里只填两栏",
               u"第一栏：钱走哪条链条。第二栏：要看到哪个指标动了，才算这条链真的动了"
               u"（再融资公告、赤字率、政策不确定性与地缘风险指数、"
               u"股通成交额、实际利率与央行购金、月度供需展望、现货 ETF 申赎）。",
               edge=NAVY, fill=BG)
    _foot(d, y + 26, u"示意图·非实拍：只画情景到机制的对应，不含概率、涨跌幅与任何配置建议")
    return img


# ---------------------------------------------------------------- 11 可证伪
def falsify_panel():
    img, d = canvas(W, H)
    y = _title(d, u"每条判断都绑一个查得到的数：这就是它可能被推翻的方式",
               u"选举年资产叙事最大的问题不是错，是不可证伪——涨了是信心修复，跌了是风险重估，"
               u"横着不动是在等结果，三句话互不打架，就没有一句能被驳回。")
    rows = [
        (u"财政链条的判断", u"驳回条件：期限溢价与月度累计赤字同时回落，且连续两个季度同向。"),
        (u"关税推高物价", u"驳回条件：核心通胀里关税相关商品环比持续低于公开研究的传导率区间，"
                        u"且连续如此。"),
        (u"实际利率是黄金的锚", u"驳回条件：官方净购金停止甚至转为净卖出，"
                              u"而同期实际利率上行、金价仍然同涨。"),
        (u"不确定性把开支推迟", u"驳回条件：不确定性指数上行，而私人固定投资与资本开支指引同步上行。"),
        (u"港股拆成两条通道", u"驳回条件：南向成交占比继续抬升，而指数与汇率的相关结构没有相应变化。"),
    ]
    for i, (name, why) in enumerate(rows):
        y = _row(d, y, name, why, name_w=380, fill=(SURFACE if i % 2 == 0 else BG),
                 mark=(GREEN if i % 2 else NAVY))
    y = _panel(d, 45, y + 6, 1410, u"你不必同意这些链条，但可以查它有没有动",
               u"五条各自绑到一个公开序列上，并写清口径与等待时间。"
               u"这就是「机制」与「故事」的差别。", edge=GREEN, fill=BG)
    _foot(d, y + 26, u"示意图·非实拍：只画驳回条件的形状，不含阈值数值与时间长度")
    return img


JOBS = [
    ("poll_layers.png", poll_layers),
    ("converters.png", converters),
    ("two_axes_cards.png", two_axes_cards),
    ("enforcement_chain.png", enforcement_chain),
    ("lifespans.png", lifespans),
    ("channels.png", channels),
    ("price_split.png", price_split),
    ("two_flows.png", two_flows),
    ("three_anchors.png", three_anchors),
    ("scenario_grid.png", scenario_grid),
    ("falsify_panel.png", falsify_panel),
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
