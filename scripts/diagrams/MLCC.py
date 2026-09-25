# -*- coding: utf-8 -*-
"""画 MLCC 篇的四张示意图（示意图通道的产物源，D-22）。

为什么脚本进 git：线条图是确定性的——同一份代码永远出同一张图，能进 git diff。
这个理由只有在脚本本身进版本库时才成立，所以它从 .probe/（gitignored）搬到了这里。
好不好看仍然由人眼定：装进产物之前先跑本脚本，再看 .probe/drawn/ 下的输出，
进产物一律走 `scripts/add_illustration.py`（它同时写文件、data.json、manifest）。

为什么不用生成模型：这四张的价值全在**标注正确**——层与电极谁接哪一端、
电流从母线到芯片经过哪几段。生成图给不出正确的拓扑，还会把文字画成乱码。

图上**不写任何数字**（D-22）：层数量级、电压、容值、良率这些是可核查的量化断言，
必须走带 source 的结构化区块，不能烧进图片——烧进去就绕过了 R-02。
"""
import os

import _common

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = os.path.join(ROOT, ".probe", "drawn")   # 输出仍是临时物，进产物要走 add_illustration.py

# 主题 mlcc-ceramic 的身份色，直接抄 web/src/tokens/index.ts
BG = "#FBF9F7"
BRICK = "#9C3F27"      # primary：烧结陶瓷
STEEL = "#4E6B7A"      # accent：镍电极 / 金属
INK = "#2B201A"
SOFT = "#E7DFD4"
SURFACE = "#F2EAE4"

font, canvas, label, leader = _common.make(
    {"bg": BG, "ink": INK, "accent": STEEL})


def legend(d, items, y, cx=750, size=24):
    """底部色块图例。不用引线：引线要么指错对象（第一版"陶瓷介质层"
    指到了一条电极条上），要么把标签挤出画布——图例两样都不会犯。"""
    widths = []
    for color, text in items:
        widths.append(26 + font(size).getlength(text) + 46)
    total = sum(widths) - 46
    x = cx - total / 2.0
    for (color, text), w in zip(items, widths):
        d.rounded_rectangle([x, y - 13, x + 26, y + 13], radius=4, fill=color)
        d.text((x + 34, y), text, fill=INK, font=font(size), anchor="lm")
        x += w


def cross_section():
    """MLCC 剖面：陶瓷介质层与镍内电极交替叠层，相邻电极分别朝两端引出。
    交错才成电容，对齐就是短路——这张图要让人一眼看见"交错"。"""
    img, d = canvas()
    x0, x1 = 330, 1170
    y0, y1 = 175, 700
    term_w = 54
    n = 19
    step = (y1 - y0) / n
    plate_h = max(7, int(step * 0.40))

    d.rounded_rectangle([x0, y0, x1, y1], radius=10, fill=SOFT, outline=INK, width=2)
    d.rounded_rectangle([x0 - term_w, y0, x0, y1], radius=8, fill=BRICK)
    d.rounded_rectangle([x1, y0, x1 + term_w, y1], radius=8, fill=BRICK)

    for i in range(n):
        cy = y0 + step * (i + 0.5)
        if i % 2 == 0:                       # 接左端
            ax, bx = x0 - 6, x1 - 170
        else:                                # 接右端
            ax, bx = x0 + 170, x1 + 6
        d.rectangle([ax, cy - plate_h / 2.0, bx, cy + plate_h / 2.0], fill=STEEL)

    label(d, (750, 100), u"MLCC 剖面：介质层与内电极交替叠层", 34, INK, anchor="ma")
    # 两端各自标在端电极旁边——它们就在图上，不需要引线
    d.text((x0 - term_w / 2, y1 + 30), u"端电极", fill=BRICK, font=font(23), anchor="mm")
    d.text((x1 + term_w / 2, y1 + 30), u"端电极", fill=BRICK, font=font(23), anchor="mm")

    legend(d, [(SOFT, u"陶瓷介质层"), (STEEL, u"镍内电极（逐层交替接两端）"),
               (BRICK, u"铜/锡端电极")], 800)
    d.line([(330, 852), (1170, 852)], fill=SURFACE, width=2)
    label(d, (750, 886),
          u"相邻两层分别朝两个端头引出——交错才成电容，对齐就是短路",
          26, STEEL, anchor="ma")
    return img


def power_path():
    """AI 供电这一路：母线 → 供电模块（多相）→ 输出电容贴近芯片。
    这一章的论点全在"位置"上：电容离芯片越近越好，所以它们挤在芯片四周。"""
    img, d = canvas()
    label(d, (750, 100), u"板级供电的一跳再一跳：电容为什么必须贴着芯片", 34, INK, anchor="ma")

    d.rounded_rectangle([150, 180, 1350, 700], radius=18, outline=INK, width=2, fill=BG)

    d.rectangle([200, 230, 240, 650], fill=STEEL)
    d.text((220, 672), u"高压母线", fill=INK, font=font(23), anchor="mm")

    d.rounded_rectangle([360, 300, 620, 580], radius=12, fill=SURFACE, outline=BRICK, width=3)
    label(d, (490, 340), u"供电模块", 27, BRICK, anchor="ma")
    label(d, (490, 378), u"（多相）", 22, INK, anchor="ma")
    for i in range(4):
        y = 420 + i * 36
        d.line([(400, y), (580, y)], fill=BRICK, width=3)

    d.line([(240, 440), (355, 440)], fill=BRICK, width=4)
    d.polygon([(355, 431), (373, 440), (355, 449)], fill=BRICK)

    cx0, cy0, cx1, cy1 = 800, 330, 1030, 560
    d.rectangle([cx0, cy0, cx1, cy1], fill=INK)
    label(d, ((cx0 + cx1) / 2, (cy0 + cy1) / 2), u"加速卡芯片", 28, BG, anchor="mm")

    for i in range(4):
        y = 380 + i * 52
        d.line([(620, y), (cx0 - 6, y)], fill=BRICK, width=3)
        d.polygon([(cx0 - 16, y - 7), (cx0 - 2, y), (cx0 - 16, y + 7)], fill=BRICK)

    # 输出电容：紧贴芯片四边，位置由这里算出来，图例再指一次
    import math
    mx, my = (cx0 + cx1) / 2, (cy0 + cy1) / 2
    spots = []
    for ang in range(0, 360, 20):
        px = mx + 148 * math.cos(math.radians(ang))
        py = my + 148 * math.sin(math.radians(ang)) * 0.86
        d.ellipse([px - 10, py - 10, px + 10, py + 10], fill=STEEL)
        spots.append((px, py))

    legend(d, [(STEEL, u"输出电容（贴着芯片放）"), (BRICK, u"相线"), (INK, u"负载")], 745)
    d.line([(150, 797), (1350, 797)], fill=SURFACE, width=2)
    label(d, (750, 831),
          u"每一跳都要就近退耦：电容离芯片越远，瞬态响应越差、损耗越大",
          26, STEEL, anchor="ma")
    label(d, (750, 875),
          u"图上不标电压与容值——那些是可核查的量化断言，走正文里带来源的表格",
          21, u"#8A8078", anchor="ma")
    return img


def process_chain():
    """中游工艺链。这一章是配图阶段唯一"实拍给不出"的章：`mlcc 产线`、
    `贴片电容 工厂`、`mlcc 工厂` 全部 0 点名（Bing 只会回 PCB 与电解电容厂）。
    工序本身是正文里逐步溯源过的，画成链条比堆一张无关厂房照诚实。
    两步用强调色（叠层、烧结）——正文的论点就是"壁垒在这两步的良率"，
    这是**观点**，所以图注里写明是按正文观点绘制，不是客观事实。"""
    img, d = canvas()
    label(d, (750, 100), u"MLCC 工艺链：设备买得到，良率买不到", 34, INK, anchor="ma")

    steps = [(u"①", u"配料流延", u"介质膜做到微米级\n且厚度一致", False),
             (u"②", u"内电极印刷", u"镍浆对位与连续性", False),
             (u"③", u"叠层", u"上千层对齐\n一层错整块废", True),
             (u"④", u"切割分离", u"单颗尺寸与断面", False),
             (u"⑤", u"还原气氛烧结", u"镍不能氧化\n收缩率要匹配", True),
             (u"⑥", u"端电极", u"铜/银层与结合力", False),
             (u"⑦", u"电镀", u"镍/锡可焊层", False),
             (u"⑧", u"测试分选", u"容值耐压与老化", False)]

    box_w, box_h, gap_x, gap_y = 300, 178, 40, 46
    x0 = (1500 - (box_w * 4 + gap_x * 3)) / 2
    y0 = 170
    CIRCLED = "①②③④⑤⑥⑦⑧"
    for idx, (mark, title, note, hot) in enumerate(steps):
        row, col = divmod(idx, 4)
        # 第二行从右往左走，箭头才不会把两行"读"成两列
        col = col if row == 0 else 3 - col
        x = x0 + col * (box_w + gap_x)
        y = y0 + row * (box_h + gap_y)
        edge = BRICK if hot else STEEL
        d.rounded_rectangle([x, y, x + box_w, y + box_h], radius=12,
                            fill=SURFACE if hot else BG, outline=edge, width=4 if hot else 2)
        d.text((x + box_w / 2, y + 34), mark, fill=edge, font=font(30), anchor="mm")
        d.text((x + box_w / 2, y + 76), title, fill=INK, font=font(27), anchor="mm")
        for li, line in enumerate(note.split("\n")):
            d.text((x + box_w / 2, y + 118 + li * 27), line, fill=STEEL, font=font(20), anchor="mm")
        # 连接箭头
        nxt = idx + 1
        if nxt < len(steps):
            nrow, ncol = divmod(nxt, 4)
            ncol = ncol if nrow == 0 else 3 - ncol
            if nrow == row:
                ay = y + box_h / 2
                if ncol > col:                 # 往右走
                    ax = x + box_w
                    d.line([(ax + 4, ay), (ax + gap_x - 6, ay)], fill=BRICK, width=3)
                    d.polygon([(ax + gap_x - 6, ay - 7), (ax + gap_x + 2, ay),
                               (ax + gap_x - 6, ay + 7)], fill=BRICK)
                else:                          # 蛇形回折：第二行从右往左，箭头必须跟着反向
                    ax = x
                    d.line([(ax - 4, ay), (ax - gap_x + 6, ay)], fill=BRICK, width=3)
                    d.polygon([(ax - gap_x + 6, ay - 7), (ax - gap_x - 2, ay),
                               (ax - gap_x + 6, ay + 7)], fill=BRICK)
            else:                              # 第一行末 → 第二行首（同一侧往下）
                bx = x + box_w / 2
                d.line([(bx, y + box_h + 4), (bx, y + box_h + gap_y - 6)], fill=BRICK, width=3)
                d.polygon([(bx - 7, y + box_h + gap_y - 6), (bx, y + box_h + gap_y + 2),
                           (bx + 7, y + box_h + gap_y - 6)], fill=BRICK)

    legend(d, [(BRICK, u"正文认为的壁垒所在（良率与配方）"), (STEEL, u"其余工序")], 660)
    d.line([(150, 706), (1350, 706)], fill=SURFACE, width=2)
    label(d, (750, 740),
          u"每步的失败模式不同：流延看厚度一致，叠层看对齐，烧结看氧化与开裂",
          26, STEEL, anchor="ma")
    label(d, (750, 786),
          u"按正文工序逐步绘制；强调色标的是该篇的判断，不是客观分级。图上不含任何产能与良率数字",
          21, u"#8A8078", anchor="ma")
    return img


def part_number():
    """规格章的配图。实拍给不出这一章要的东西：`贴片电容` 回的是同一堆
    无标注的料卷特写，而规格章的论点是"料号五段各管一件事，读错一段就选错一颗"。
    所以画成一条可拆读的料号带。
    图上**不写任何码值对应**（D-22）：0805 等于多大、104 等于几微法，
    这些是可核查的量化断言，走正文里带来源的表格；画进图里就绕过了 R-02。"""
    img, d = canvas()
    label(d, (750, 100), u"料号怎么读：五段各管一件事", 34, INK, anchor="ma")

    fields = [(u"尺寸码", u"占板面积\n与耐弯折"),
              (u"介质", u"温度稳定性\n与损耗"),
              (u"容值", u"退耦能覆盖\n的频段"),
              (u"误差", u"要不要\n留裕量"),
              (u"耐压", u"降额曲线\n与寿命")]

    box_w, gap = 250, 25
    x0 = (1500 - (box_w * 5 + gap * 4)) / 2
    bar_y, bar_h = 190, 78
    box_y, box_h = 330, 226
    for i, (name, governs) in enumerate(fields):
        x = x0 + i * (box_w + gap)
        hot = i in (0, 1)
        edge = BRICK if hot else STEEL
        d.rounded_rectangle([x, bar_y, x + box_w, bar_y + bar_h], radius=10,
                            fill=SURFACE if hot else BG, outline=edge, width=3 if hot else 2)
        d.text((x + box_w / 2, bar_y + bar_h / 2), name,
               fill=INK, font=font(29), anchor="mm")
        if i < 4:
            d.line([x + box_w + 6, bar_y + bar_h / 2, x + box_w + gap - 6, bar_y + bar_h / 2],
                   fill=u"#B9AE9F", width=2)
        d.rounded_rectangle([x, box_y, x + box_w, box_y + box_h], radius=12,
                            fill=BG, outline=u"#CFC4B6", width=2)
        d.line([x + box_w / 2, bar_y + bar_h, x + box_w / 2, box_y],
               fill=u"#B9AE9F", width=2)
        for li, line in enumerate(governs.split("\n")):
            d.text((x + box_w / 2, box_y + 92 + li * 40), line,
                   fill=STEEL, font=font(24), anchor="mm")

    label(d, (750, 610),
          u"读法：从左边两段选可靠度，从右边三段配电路——尺寸与介质是"
          u"「能不能用」，容值误差耐压是「够不够用」",
          26, STEEL, anchor="ma")
    label(d, (750, 658),
          u"按正文的料号结构绘制；图上刻意不写码值对应——那是可核查的量化断言，走正文里带来源的表格",
          21, u"#8A8078", anchor="ma")
    return img


def main():
    if not os.path.isdir(OUT):
        os.makedirs(OUT)
    jobs = [("mlcc_cross_section.png", cross_section),
            ("process_chain.png", process_chain),
            ("power_path.png", power_path),
            ("part_number.png", part_number)]
    for name, fn in jobs:
        p = os.path.join(OUT, name)
        fn().save(p, "PNG")
        print("%s  %d KB" % (p, os.path.getsize(p) // 1024))


if __name__ == "__main__":
    main()
