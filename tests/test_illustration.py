# -*- coding: utf-8 -*-
"""装一张自画示意图进产物（D-22 放行示意图之后的唯一入口）。

为什么要有这个脚本而不是手改 data.json：一张图同时活在三个地方——
`images/` 里的文件、`data.json` 的引用、`images/manifest.json` 的记录。
少一个就分别以三种方式坏掉：没文件 → G-03 报破链；没记录 → 被下一次
`--redo-images` 当成没抓过的东西；data.json 有而文件没引用 → G-03 报孤儿图片。
手改过一次就迟早漏一处，这正是 `image_ref()` 存在的理由（W-115 的教训）。
"""
import io
import json
import os

import add_illustration as AI
import outline as O
from conftest import make_passing_data

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _domain(tmp_path, sections=2):
    out = tmp_path / "output" / "测试领域"
    (out / "images").mkdir(parents=True)
    data = make_passing_data(topic=u"测试领域", sections=sections)
    for s in data["sections"]:
        for im in s["images"]:
            (out / im["file"]).write_bytes(b"\xff\xd8\xff\xe0" + bytes(4096))
    (out / "data.json").write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    (out / "images" / "manifest.json").write_text("[]", encoding="utf-8")
    return out


def _png(tmp_path, w=1200, h=800):
    from PIL import Image
    p = tmp_path / "drawn.png"
    Image.new("RGB", (w, h), (255, 255, 255)).save(str(p), "PNG")
    return p


def test_installing_updates_all_three_places(tmp_path):
    d = _domain(tmp_path)
    rec = AI.install(u"测试领域", "sec-01", str(_png(tmp_path)),
                     alt=u"示意图·非实拍：交错内电极", caption=u"按正文绘制",
                     based_on=[u"sec-01#层数"], root=str(d.parent))
    assert rec["kind"] == "illustration" and "source_page" not in rec, \
        u"示意图记录不该带 source_page（带了就能冒充引用图）：%s" % (rec,)
    assert rec["based_on"] == [u"sec-01#层数"]

    out = d
    assert os.path.isfile(os.path.join(str(out), rec["file"])), u"文件没落盘"
    data = json.loads(io.open(os.path.join(str(out), "data.json"), encoding="utf-8").read())
    sec = [s for s in data["sections"] if s["id"] == "sec-01"][0]
    assert rec["file"] in [im["file"] for im in sec["images"]], u"data.json 没引用它"
    man = json.loads(io.open(os.path.join(str(out), "images", "manifest.json"),
                             encoding="utf-8").read())
    assert rec["file"] in [m["file"] for m in man], u"manifest 没记，下次重做会把它当没抓过的"


def test_the_file_name_follows_the_numbered_convention(tmp_path):
    """文件名必须是 `images/NN_名.png`——G-03 与闸门都按这个 pattern 认图。"""
    d = _domain(tmp_path)
    rec = AI.install(u"测试领域", "sec-01", str(_png(tmp_path)),
                     alt=u"示意图", caption=u"画的", based_on=[u"sec-01#x"],
                     slug=u"交错内电极剖面", root=str(d.parent))
    assert rec["file"].startswith("images/") and rec["file"].endswith(".png")
    head = rec["file"].split("/")[1]
    assert head[:2].isdigit(), u"没编号：%s" % (rec["file"],)


def test_an_unknown_section_is_refused(tmp_path):
    d = _domain(tmp_path)
    import pytest
    with pytest.raises(AI.IllustrationError):
        AI.install(u"测试领域", "sec-99", str(_png(tmp_path)),
                   alt=u"示意图", caption=u"画的", based_on=[u"x#y"], root=str(d.parent))


def test_a_file_that_is_not_actually_an_image_is_refused(tmp_path):
    """不能只看扩展名——这条纪律是图片下载那套的根（Bing 会返回 404 但字节是合法 JPEG，
    反过来也会返回合法 HTML 却叫 .jpg）。装图这一步同样要验 magic bytes。"""
    d = _domain(tmp_path)
    fake = tmp_path / "fake.png"
    fake.write_bytes(b"<html><body>not an image</body></html>")
    import pytest
    with pytest.raises(AI.IllustrationError):
        AI.install(u"测试领域", "sec-01", str(fake),
                   alt=u"示意图", caption=u"画的", based_on=[u"sec-01#x"], root=str(d.parent))


def test_an_illustration_needs_something_to_be_based_on(tmp_path):
    """`based_on` 是这张图的追责路径：画错了要能指出它声称画的是正文哪几条事实。
    空着就等于放行一张没人能对证的图。"""
    d = _domain(tmp_path)
    import pytest
    with pytest.raises(AI.IllustrationError):
        AI.install(u"测试领域", "sec-01", str(_png(tmp_path)),
                   alt=u"示意图", caption=u"画的", based_on=[], root=str(d.parent))


def test_redoing_images_leaves_the_illustrations_alone(tmp_path):
    """`--redo-images` 清引用是为了让采集器重找，但采集器只会找回**照片**——
    把手画的剖面图引用一起清掉，等于把它交给渲染后的孤儿清理删掉。
    这条是 D-19「非破坏」不变量在示意图通道上的延续：09-24 开这个通道时漏了它，
    于是"重做配图"与"抹掉自画图"是同一个动作。"""
    import generate as G
    data = make_passing_data(topic=u"测试领域", sections=1)
    sec = data["sections"][0]
    sec["images"] = [
        {"file": "images/01_photo.jpg", "alt": u"实拍", "caption": u"实拍",
         "source_page": "https://example.com/a"},
        {"file": "images/02_drawn.png", "alt": u"示意图·非实拍：交错内电极",
         "caption": u"按正文绘制", "kind": "illustration", "based_on": [u"sec-01#层数"]},
    ]
    cleared = G._clear_image_refs(data, lambda *a, **k: None)

    left = [im["file"] for im in sec["images"]]
    assert left == ["images/02_drawn.png"], u"清完引用后该只剩示意图：%s" % (left,)
    assert cleared == 1, u"日志要说真话：清掉的是 1 张照片，不是 2 张：%s" % (cleared,)
