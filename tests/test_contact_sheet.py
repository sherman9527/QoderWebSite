# -*- coding: utf-8 -*-
"""`contact_sheet.py` 的回归。

这条命令是"闸门绿了之后人眼还得再看一遍"那条例程的载体（W-99 / W-115 两次都是
眼睛抓到、机器判据抓不到的），所以它坏掉的方式很特别：**不报错、画一张空表**，
看表的人以为没问题。测试钉的就是"每张图都得有一格、缺文件也得留一格并写清楚"。
"""
import io
import json
import os

import contact_sheet as C
from PIL import Image, ImageFont


def _domain(tmp_path, imgs):
    """imgs = [(章节 id, 文件名)]；只造这张表真正读的东西：data.json 的 sections/images。"""
    d = tmp_path / "output" / "测试领域"
    (d / "images").mkdir(parents=True)
    sections = {}
    for sid, name in imgs:
        sec = sections.setdefault(sid, {"id": sid, "title": sid, "images": []})
        sec["images"].append({"file": "images/%s" % name, "alt": name,
                              "caption": name, "source_page": "https://src/%s" % name,
                              "width": 1600, "height": 900, "query": u"某条检索词"})
        (d / "images" / name).write_bytes(b"\xff\xd8\xff\xe0" + bytes(2048))
    (d / "data.json").write_text(
        json.dumps({"topic": u"测试领域", "sections": list(sections.values())},
                   ensure_ascii=False), encoding="utf-8")
    return d


def test_every_image_gets_a_cell(tmp_path):
    d = _domain(tmp_path, [(u"sec-01", "a.jpg"), (u"sec-01", "b.jpg"),
                           (u"sec-02", "c.jpg")])
    items = C.load_images(str(d))
    assert [sid for sid, _im in items] == [u"sec-01", u"sec-01", u"sec-02"], items
    out = str(tmp_path / "sheet.png")
    C.build(str(d), items, out)
    pic = Image.open(out)
    # 3 张一行（COLS=3）→ 一行高；宽到第三列。尺寸不对就是格子算错了，表会画成一条缝
    assert pic.size[0] == C.COLS * (C.TW + C.PAD) + C.PAD
    assert pic.size[1] == C.TH + C.LAB + 2 * C.PAD


def test_a_label_cannot_wider_than_its_cell_is_clipped(tmp_path):
    """PIL 不折行：一条 52 字的中文 alt 在 13px 下有 600+ px，会一路画进右边两列，
    下一行的图又压上来——09-24 看 Muse产业逻辑 那张表时，标签互相叠成一片，
    我只能另写一张网格才看得清。看表这一步是验收本身，表看不清等于没有验收。
    所以标签必须先按格子宽度裁。"""
    font = None
    for path in C.FONTS:
        if os.path.isfile(path):
            font = ImageFont.truetype(path, 13)
            break
    if font is None:
        import pytest
        pytest.skip(u"这台机器没有中文字体，裁切无从量起")
    long_text = u"质量看得见 2026年厂家加工定制各种孔径厚度钢板网 马道平台钢板网-阿里巴巴 源头工厂"
    clipped = C.clip(font, long_text, C.TW - 8)
    assert font.getlength(clipped) <= C.TW - 8, \
        u"裁完还是超宽：%d px > %d px" % (font.getlength(clipped), C.TW - 8)
    assert clipped != long_text and clipped.endswith(u"…"), u"超宽的东西没被裁：%s" % (clipped,)
    assert C.clip(font, u"短标签", C.TW - 8) == u"短标签", u"没超宽的不该被动"


def test_the_sheet_labels_two_lines_without_colliding(tmp_path):
    """两行标签的间距必须大于字号的行高，否则第二行压在第一个字上（LAB=46 时实测就是这样）。"""
    assert C.LAB >= 2 * 19 + 2, u"两行 13px 文字塞不进 %d px" % C.LAB


def test_a_referenced_but_missing_file_still_shows_up_on_the_sheet(tmp_path):
    """破链是这套流程真实发生过的故障（硬杀在"删了旧图、还没写新引用"之间）。
    联络表把它跳过去，就等于替事故做掩护。"""
    d = _domain(tmp_path, [(u"sec-01", "a.jpg")])
    (d / "images" / "a.jpg").unlink()
    items = C.load_images(str(d))
    out = str(tmp_path / "sheet.png")
    C.build(str(d), items, out)          # 不抛异常
    assert os.path.isfile(out)
    assert Image.open(out).size[1] == C.TH + C.LAB + 2 * C.PAD
