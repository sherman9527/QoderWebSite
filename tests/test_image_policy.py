# -*- coding: utf-8 -*-
"""图片入库压缩策略（images.fit_bytes）。

为什么单独一个文件、为什么用 PIL：这些判据量的是**内容**（颜色数、帧数、模式），
不是文件名也不是格式。手写 PNG 头喂不进这条路径。
Pillow 缺位时整个文件 skip——闸门本身仍然是 stdlib-only（`sniff`/`dimensions`）。

策略的来由是真事故：上一版按"格式"决定损失方式，非 alpha 的 PNG 一律上 256→64 色阶梯。
照片存成 PNG 时格式看着"无损友好"，内容却是连续的——皮肤压成色块、边缘起噪点。
更糟的是**那批图全都达标**，所以"未达标清单"一张都没抓到，是人眼在 1:1 裁图上看出来的。

写这批测试时自己又踩了两次同类的坑：
  · fixture 的宽度比 max_display_px 还窄，阶梯一步都没走，断言当然成立——测的是"什么都没发生"；
  · 把质量档挂在"缩了尺寸"之后，于是本来就窄的 JPEG 永远压不动（全库 62 张超线 JPEG 里的一部分）。
所以每条都过 `_geom()`：先断言几何真的按预期动了（或确实没动），再断言字节。
"""
import io
import json
import os
import random
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

Image = pytest.importorskip("PIL.Image", reason="fit_bytes 需要 Pillow（已在 requirements.txt）")

import images as I  # noqa: E402

# 从真配置起步再改旋钮，不另造一份 bar：`accept_image` 还要读 min_bytes /
# min_bytes_per_pixel，自己拼一个"看着够用"的 dict 会在跑到 collect 的那两条上
# 以 KeyError 崩掉——而崩在 fixture 上的测试什么也没测。
_CFG = json.load(io.open(os.path.join(ROOT, "config", "quality_bar.json"),
                         encoding="utf-8"))["images"]
# 故意把显示宽度设得比 fixture 窄，这样"换分辨率"这一档真的会走。
BAR = dict(_CFG, min_width=100, max_bytes=4000, best_effort_bytes=9000, max_display_px=400)
# 顶格高于 fixture 宽度：几何不动，只试格式内的损失。
NO_RESIZE = dict(BAR, max_display_px=4000)


def _photo(w=700, h=500, seed=7):
    """连续色调 + 轻微噪点，像真照片。

    fixture 的形状是要紧的：最早这版用 `(x*13 ^ y)` 这类高频异或图案，
    它**本身压得极好**，一 LANCZOS 重采样振铃就把可压性毁了——缩完反而更大，
    于是 fit_bytes 正确地保留原图，而测试以为阶梯没跑。
    合成图要合成成"真照片那样"，不然测的是图案学，不是压缩策略。
    """
    rnd = random.Random(seed)
    im = Image.new("RGB", (w, h))
    px = im.load()
    for y in range(h):
        for x in range(w):
            r = int(255.0 * x / w)
            g = int(255.0 * y / h)
            b = 128 + int(100.0 * ((x + y) % 7) / 7)
            px[x, y] = (min(255, max(0, r + rnd.randint(-6, 6))),
                        min(255, max(0, g + rnd.randint(-6, 6))),
                        min(255, max(0, b + rnd.randint(-6, 6))))
    return im


def _flat(w=700, h=500):
    """真·少色：4 种颜色。"""
    im = Image.new("P", (w, h))
    im.putpalette([0, 0, 0, 255, 0, 0, 0, 255, 0, 0, 0, 255])
    px = im.load()
    for y in range(h):
        for x in range(w):
            px[x, y] = (x // 50 + y // 50) % 4
    return im


def _bytes(im, fmt, **kw):
    buf = io.BytesIO()
    im.save(buf, fmt, **kw)
    return buf.getvalue()


def _colors(raw):
    """数颜色。`maxcolors` 必须给到"像素数"：`getcolors` 超过预算返回 None，
    而 None 被当成 0 就是把"颜色多到数不清"读成"一个颜色都没有"——
    第一版正好栽在这，断言变成 `0 > 256` 红得莫名其妙。"""
    im = Image.open(io.BytesIO(raw))
    n = max(1, im.width * im.height)
    return len(im.convert("RGB").getcolors(maxcolors=n) or [])


def _geom(raw, w, h, expect_resized):
    """先断言几何，再谈字节。空转的压缩测试比没有测试更糟。"""
    sw, sh = Image.open(io.BytesIO(raw)).size
    if expect_resized:
        assert (w, h) != (sw, sh), u"阶梯没动，这条测试是空过的"
    else:
        assert (w, h) == (sw, sh), u"以为不会缩，结果缩了"


def _jpeg_rungs(raw):
    """实现真正面对的候选：从**解码后的 raw** 再编码，不是从原始内存图。
    拿原始图算档位去断言重编码的结果对不上——转码是有损的，代际不同字节数就不同。"""
    im = Image.open(io.BytesIO(raw))
    return [len(_bytes(im, "JPEG", quality=q, optimize=True, progressive=True))
            for q in I.JPEG_LADDER]


# --------------------------------------------------------------- 一条都不许多动

def test_an_image_under_the_cap_is_not_touched_at_all():
    raw = _bytes(_photo(120, 90), "PNG")
    out, w, h, note = I.fit_bytes(raw, None, dict(BAR, max_bytes=10 ** 9), kind=u"photo")
    assert out == raw and note == u"" and (w, h) == (120, 90)


# ------------------------------------------------------- 照片不许砍颜色，少色图不许展开

def test_a_photo_png_is_never_palette_quantized():
    """这条就是 10-03 那次事故：照片 PNG 被压到 64 色，皮肤变成色块。

    判据不是"变小了没有"——它变小了，而且**达标**。判据是颜色还在不在。
    """
    raw = _bytes(_photo(), "PNG")
    out, w, h, note = I.fit_bytes(raw, None, BAR, kind=u"photo")
    _geom(raw, w, h, expect_resized=True)
    assert _colors(raw) > 256, u"fixture 本身就该是多色照片"
    assert _colors(out) > 256, u"多色照片被砍到 ≤256 色 = 上了调色板"
    assert Image.open(io.BytesIO(out)).mode != "P"


def test_a_graphic_that_needs_no_resize_is_not_expanded_to_rgb():
    """P 模式在"这一档不缩尺寸"时必须原样交回。
    展开成 RGB 再存 PNG 会让一张少色图**变大**——那是"看着在压，其实在搞坏"。"""
    raw = _bytes(_flat(300, 300), "PNG")
    out, w, h, note = I.fit_bytes(raw, None, dict(BAR, max_bytes=1), kind=u"photo")
    _geom(raw, w, h, expect_resized=False)
    assert len(out) <= len(raw)
    assert Image.open(io.BytesIO(out)).mode == "P"


def test_an_illustration_is_never_lossy_however_many_colors_it_has():
    """示意图上是文字。kind 优先于内容判断——它有一万种颜色也不许砍。"""
    raw = _bytes(_photo(900, 700), "PNG")
    out, w, h, note = I.fit_bytes(raw, None, dict(BAR, max_bytes=500), kind=u"illustration")
    _geom(raw, w, h, expect_resized=True)
    assert _colors(out) > 256
    assert u"损失" in note


# --------------------------------- 达标解里取最不清的那一个；到不了线也别往死里压

def test_the_first_rung_that_clears_the_cap_wins_not_the_smallest():
    raw = _bytes(_photo(), "JPEG", quality=98, optimize=True)
    rungs = _jpeg_rungs(raw)
    assert rungs[0] > rungs[-1], u"fixture 的质量阶梯没拉开"
    out, w, h, note = I.fit_bytes(raw, None, dict(NO_RESIZE, max_bytes=rungs[0]), kind=u"photo")
    _geom(raw, w, h, expect_resized=False)
    assert len(out) == rungs[0], u"能达标却多压了一档：白付了损失"


def test_an_unreachable_jpeg_stops_at_the_soft_bar_not_at_the_bottom_of_the_ladder():
    """到不了硬上限时，取"第一个够得着软上限的那一档"，而不是最小的一档。
    一路压到 q30 才停 = 反正不达标就往死里压，那是把数字看得比图重。"""
    raw = _bytes(_photo(), "JPEG", quality=98, optimize=True)
    rungs = _jpeg_rungs(raw)
    out, w, h, note = I.fit_bytes(
        raw, None, dict(NO_RESIZE, max_bytes=rungs[-1] - 1, best_effort_bytes=rungs[1] + 1),
        kind=u"photo")
    assert len(out) == rungs[1], u"够得着软上限却压到了更狠的一档"
    assert u"尽力而为" in note


def test_a_narrow_jpeg_still_gets_the_quality_ladder():
    """宽度已在显示线内时，质量档**照样要跑**。
    上一版把质量档挂在"缩了尺寸"之后，于是 700px 宽那张 417 KB 的永远压不动。"""
    raw = _bytes(_photo(700, 500), "JPEG", quality=98, optimize=True)
    cap = len(raw) // 3
    out, w, h, note = I.fit_bytes(raw, None, dict(NO_RESIZE, max_bytes=cap), kind=u"photo")
    _geom(raw, w, h, expect_resized=False)
    assert len(out) <= cap, u"没缩尺寸就一步都没压"


# ------------------------------------------------------------- 分辨率锚在显示宽度

def test_a_wide_image_is_capped_at_display_width_not_left_at_2400px():
    """正文 --measure:46rem = 736 CSS px，2 倍屏 1472。比这更宽的像素页面永远渲染不到。"""
    raw = _bytes(_photo(2400, 900), "PNG")
    bar = dict(BAR, max_bytes=200, max_display_px=1472, min_width=640)
    out, w, h, note = I.fit_bytes(raw, None, bar, kind=u"photo")
    assert 640 <= w <= 1472


def test_width_stops_at_min_width_and_never_goes_below():
    raw = _bytes(_photo(1600, 400), "PNG")
    out, w, h, note = I.fit_bytes(raw, None, dict(BAR, max_bytes=200), kind=u"photo")
    assert w >= BAR["min_width"]


# ------------------------------------------------------------- 到不了线就如实说

def test_nothing_helps_so_the_original_is_kept_and_said_so():
    """规则 ④：连 optimize 都挤不出一个字节时，保留原图并说明。
    必须喂一张**已经 optimize 过**的 PNG——否则重编码总能省掉几字节，
    走的是规则 ③，这条测试就什么也没测到（第一版就是这样空过的）。"""
    tiny = _bytes(_photo(60, 40), "PNG", optimize=True)
    out, w, h, note = I.fit_bytes(tiny, None, dict(BAR, max_bytes=1), kind=u"photo")
    assert out == tiny and note and u"保留原图" in note


def test_a_result_bigger_than_the_input_is_never_taken():
    """无条件按长边缩的那版，26 张本来就小的图被重编码得**更大**。
    压完变大不是"在压"，是搞坏。"""
    raw = _bytes(_photo(300, 300), "JPEG", quality=95, optimize=True)
    out, w, h, note = I.fit_bytes(raw, None, dict(BAR, max_bytes=1, min_width=640), kind=u"photo")
    assert len(out) <= len(raw)


def test_an_animated_gif_keeps_its_frames():
    """动图重编码只剩一帧。今天全库 0 张动图，所以这条只能在字节上防，不能靠"现在没有"。"""
    frames = [Image.new("P", (200, 200), c) for c in (0, 1, 2)]
    frames[0].putpalette([0, 0, 0, 255, 255, 255, 128, 128, 128])
    buf = io.BytesIO()
    frames[0].save(buf, "GIF", save_all=True, append_images=frames[1:], duration=80, loop=0)
    raw = buf.getvalue()
    assert getattr(Image.open(io.BytesIO(raw)), "n_frames", 1) > 1
    out, w, h, note = I.fit_bytes(raw, None, dict(BAR, max_bytes=1), kind=u"photo")
    assert out == raw and u"动图" in note


def test_the_note_names_the_rung_it_actually_used():
    raw = _bytes(_photo(900, 700), "PNG")
    out, w, h, note = I.fit_bytes(raw, None, dict(BAR, max_bytes=300), kind=u"photo")
    assert note, u"没达标却不吭声，就等于把'没压下去'伪装成'压好了'"


def test_undecodable_bytes_are_left_alone_rather_than_raising():
    """`accept_image` 只看 magic + 宽高 + 体积，一张截断的 JPEG 能过它，Pillow 却打不开。
    采集链在这里抛异常，代价是整章没图——比一张大图贵得多。"""
    fake = (b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"
            + bytes(9000))
    out, w, h, note = I.fit_bytes(fake, None, dict(BAR, max_bytes=1), kind=u"photo")
    assert out == fake and note


# ------------------------------- 入库时压：策略必须真的接在 accept_image 与落盘之间

def _cand(title=u"咖啡 烘焙现场"):
    return I.Candidate(title=title, murl="https://cdn/x", turl="",
                       purl="https://a.example/x")


def _one_shot(monkeypatch, cand=None):
    monkeypatch.setattr(I, "search", lambda q, count=20, opener=None: [cand or _cand()])


def test_collect_fits_an_oversized_image_before_writing_it(tmp_path, monkeypatch):
    """策略写在 fit_bytes 里不等于生效了：它得接在落盘之前。
    出包时再压会造出第二份字节，"包就是验证过的那份产物"当场作废。"""
    raw = _bytes(_photo(1600, 1100), "JPEG", quality=95, optimize=True)
    assert len(raw) > BAR["max_bytes"], u"fixture 本身就该超线"
    _one_shot(monkeypatch)
    rows = I.collect([u"咖啡"], str(tmp_path), dict(BAR, max_bytes=4000),
                     keywords=[u"咖啡", u"烘焙"],
                     downloader=lambda url, timeout=25, opener=None: raw)
    assert len(rows) == 1
    p = os.path.join(str(tmp_path), rows[0]["file"].replace("/", os.sep))
    assert os.path.getsize(p) <= 4000, u"落盘的还是原图：策略没接在写盘之前"
    assert rows[0]["width"] == Image.open(p).size[0], u"data.json 记的是压前的宽度"


def test_redo_images_does_not_duplicate_a_reencoded_file(tmp_path, monkeypatch):
    """去重键必须是**源图字节**的哈希。
    压过之后盘上字节永不再等于下载到的原始字节，于是同一张图会以新名字再落一份，
    而 G-03 按文件判、看不见重复——线上会安静地多养一张图。"""
    raw = _bytes(_photo(1600, 1100), "JPEG", quality=95, optimize=True)
    bar = dict(BAR, max_bytes=4000)
    _one_shot(monkeypatch)
    dl = lambda url, timeout=25, opener=None: raw
    first = I.collect([u"咖啡"], str(tmp_path), bar, keywords=[u"咖啡", u"烘焙"], downloader=dl)
    second = I.collect([u"咖啡"], str(tmp_path), bar, keywords=[u"咖啡", u"烘焙"], downloader=dl)
    imgs = [f for f in os.listdir(os.path.join(str(tmp_path), "images"))
            if f.lower().endswith((".jpg", ".jpeg", ".png", ".gif", ".webp"))]
    assert len(imgs) == 1, u"同一张图被当成两张落盘：%s" % imgs
    assert second and second[0]["file"] == first[0]["file"]
