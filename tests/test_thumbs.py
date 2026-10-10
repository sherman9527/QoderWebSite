# -*- coding: utf-8 -*-
"""`scripts/thumbs.py`：主页卡片缩略图的缓存必须**按内容寻址**。

为什么单独钉这一条：缓存键如果用文件路径或文件名，改了封面图之后主页会**继续用旧图**——
而这是主页，是读者点进来的第一屏，旧封面看起来完全正常，没有任何一处会报错。
本项目为"一处东西活在几个地方迟早不一致"已经付过两次学费（示意图三处、封面声明），
所以这里不许出现"按名字缓存"。
"""
import io
import os

import pytest

import thumbs as T

pytest.importorskip("PIL", reason="缩略图依赖 Pillow（缺位时主页退到原图并喊一声）")


def _src(tmp_path, color=(200, 60, 60), name=u"01_a.jpg"):
    from PIL import Image
    p = tmp_path / name
    Image.new("RGB", (1600, 1000), color).save(str(p), "JPEG")
    return p


def test_the_same_bytes_reuse_one_thumbnail(tmp_path):
    p = _src(tmp_path)
    a = T.thumb_for(str(p), 700, cache=str(tmp_path / ".thumbs"))
    b = T.thumb_for(str(p), 700, cache=str(tmp_path / ".thumbs"))
    assert a == b and os.path.isfile(a)
    assert len(os.listdir(str(tmp_path / ".thumbs"))) == 1, "同一份字节生成了两份缓存"


def test_changed_source_bytes_get_a_new_thumbnail_not_the_stale_one(tmp_path):
    """封面换图之后主页**必须**跟上——按路径缓存就会在这里骗人。"""
    p = _src(tmp_path)
    old = T.thumb_for(str(p), 700, cache=str(tmp_path / ".thumbs"))
    old_bytes = io.open(old, "rb").read()

    p.write_bytes(b"")                       # 先清空再重写，确保 mtime 与内容都变
    from PIL import Image
    Image.new("RGB", (1600, 1000), (60, 60, 200)).save(str(p), "JPEG")

    new = T.thumb_for(str(p), 700, cache=str(tmp_path / ".thumbs"))
    assert new != old, "换了封面却拿回同一份缓存（键里没有内容哈希）"
    assert io.open(new, "rb").read() != old_bytes


def test_the_thumbnail_is_capped_at_the_requested_width(tmp_path):
    from PIL import Image
    out = T.thumb_for(str(_src(tmp_path)), 700, cache=str(tmp_path / ".thumbs"))
    assert Image.open(out).width <= 700


def test_an_upscaling_request_is_refused_rather_than_blown_up(tmp_path):
    """源图比目标还窄时**不许放大**：放大不省字节，只会让卡片上的图发虚。"""
    from PIL import Image
    p = tmp_path / "small.jpg"
    Image.new("RGB", (300, 200), (10, 10, 10)).save(str(p), "JPEG")
    out = T.thumb_for(str(p), 700, cache=str(tmp_path / ".thumbs"))
    assert out == str(p), "把 300px 的图放大成 700px 了"
    assert Image.open(out).width == 300
