# -*- coding: utf-8 -*-
"""摘一张图的入口（W-143）。

为什么需要脚本而不是手删：一张图活在三个地方——`images/` 的文件、`data.json` 的引用、
`images/manifest.json` 的记录。只删文件 → G-03 报破链；只删引用 → 文件变成孤儿，
而孤儿清理要等下一次成功换名才跑；只改 manifest → 下一次 `--redo-images` 以为它还在。
手删一次就迟早漏一处，所以给 `add_illustration.install` 配一个反向入口。
"""
import io
import json
import os

import drop_image as DI
from conftest import make_passing_data


def _domain(tmp_path, sections=2):
    out = tmp_path / "output" / "测试领域"
    (out / "images").mkdir(parents=True)
    data = make_passing_data(topic=u"测试领域", sections=sections)
    man = []
    for s in data["sections"]:
        for im in s["images"]:
            (out / im["file"]).write_bytes(b"\xff\xd8\xff\xe0" + bytes(4096))
            man.append(dict(im, source_page="https://example.com/a", title=im["alt"]))
    (out / "data.json").write_text(json.dumps(data, ensure_ascii=False, indent=1),
                                   encoding="utf-8")
    (out / "images" / "manifest.json").write_text(
        json.dumps(man, ensure_ascii=False, indent=1), encoding="utf-8")
    return out, data


def _files(d):
    return sorted(f for f in os.listdir(os.path.join(str(d), "images")) if f.endswith((".jpg", ".png")))


def test_dropping_clears_all_three_places(tmp_path):
    d, _ = _domain(tmp_path)
    _outline(tmp_path)          # 摘照片要有地方记来源页，大纲缺失一律报错
    target = "images/01_" + _files(d)[0].split("_", 1)[1]
    res = DI.drop(u"测试领域", target, root=str(d.parent), config_root=str(tmp_path), apply=True)

    assert not os.path.isfile(os.path.join(str(d), target)), u"文件还在盘上"
    data = json.loads(io.open(os.path.join(str(d), "data.json"), encoding="utf-8").read())
    refs = [im["file"] for s in data["sections"] for im in s.get("images") or []]
    assert target not in refs, u"data.json 还引用它 → G-03 会报破链"
    man = json.loads(io.open(os.path.join(str(d), "images", "manifest.json"),
                             encoding="utf-8").read())
    assert target not in [m["file"] for m in man], u"manifest 还记着它"


def test_default_is_a_dry_run_that_touches_nothing(tmp_path):
    """删文件是不可逆动作（产物目录里图片不在 git 里），默认必须只报告。"""
    d, _ = _domain(tmp_path)
    target = "images/" + _files(d)[0]
    DI.drop(u"测试领域", target, root=str(d.parent))

    assert os.path.isfile(os.path.join(str(d), target)), u"没加 --apply 就删了"
    data = json.loads(io.open(os.path.join(str(d), "data.json"), encoding="utf-8").read())
    refs = [im["file"] for s in data["sections"] for im in s.get("images") or []]
    assert target in refs, u"dry-run 不该改 data.json"


def test_a_name_that_matches_nothing_is_an_error(tmp_path):
    """打错一个字的文件名如果静默"成功"，人会以为那张图已经摘掉了。
    这条来自 publish_public 的教训：一条都没排除掉却报告"残留 0"。"""
    d, _ = _domain(tmp_path)
    import pytest
    with pytest.raises(DI.DropError):
        DI.drop(u"测试领域", "images/99_不存在的图.jpg", root=str(d.parent), apply=True)


def test_emptying_a_chapter_is_said_out_loud(tmp_path):
    """摘完最后一张图，这一章就变成空章。不拦（人可能就是想让示意图来填），
    但必须报出来——否则联络表上的空缺会被当成"还没抓图"而不是"刚被我摘空"。"""
    d, _ = _domain(tmp_path, sections=1)
    _outline(tmp_path)
    data = json.loads(io.open(os.path.join(str(d), "data.json"), encoding="utf-8").read())
    sec = data["sections"][0]
    assert len(sec["images"]) == 1
    res = DI.drop(u"测试领域", sec["images"][0]["file"], root=str(d.parent), config_root=str(tmp_path), apply=True)

    assert res["emptied_sections"] == [sec["id"]], u"没报告哪一章被摘空：%s" % (res,)


def _outline(tmp_path, topic=u"测试领域"):
    """大纲放在 config/topics 下，drop 要往它的 image_exclude_pages 里写来源页。"""
    d = tmp_path / "config" / "topics"
    d.mkdir(parents=True)
    (d / (topic + u".json")).write_text(json.dumps(
        {"topic": topic, "sections": [], "image_exclude_pages": []}, ensure_ascii=False),
        encoding="utf-8")
    return d


def test_dropping_leaves_the_source_page_in_the_outline(tmp_path):
    """09-26 的教训：摘图时没留来源页，manifest 记录随删除一起消失，
    那 15 个来源页**再也拿不回来**——下一次 `--redo-images` 会把同样的垃圾原样抓回。
    删除动作必须顺手留下凭证，否则它就是这个仓库里唯一能抹掉证据的操作。"""
    d, _ = _domain(tmp_path)
    _outline(tmp_path)
    target = "images/" + _files(d)[0]
    man = json.loads(io.open(os.path.join(str(d), "images", "manifest.json"), encoding="utf-8").read())
    src = [m for m in man if m["file"] == target][0]["source_page"]

    DI.drop(u"测试领域", target, root=str(d.parent), config_root=str(tmp_path), apply=True)

    cfg = json.loads(io.open(str(tmp_path / "config" / "topics" / "测试领域.json"),
                             encoding="utf-8").read())
    assert src in cfg["image_exclude_pages"], \
        u"来源页没进排除表，下次重做会把同一张垃圾抓回来：%s" % cfg["image_exclude_pages"]


def test_a_dry_run_writes_neither_the_product_nor_the_outline(tmp_path):
    """报告模式不许碰大纲——排除表是长期状态，写进去就等于已经摘了图。"""
    d, _ = _domain(tmp_path)
    _outline(tmp_path)
    before = (tmp_path / "config" / "topics" / "测试领域.json").read_text(encoding="utf-8")
    DI.drop(u"测试领域", "images/" + _files(d)[0], root=str(d.parent), config_root=str(tmp_path))
    assert (tmp_path / "config" / "topics" / "测试领域.json").read_text(encoding="utf-8") == before


def test_an_illustration_adds_no_exclusion(tmp_path):
    """自画示意图没有来源页可排除（R-03 禁止它带 source_page）。
    这里要保证的是：别给它写一个空字符串进排除表。"""
    d, _ = _domain(tmp_path)
    _outline(tmp_path)
    dp = os.path.join(str(d), "data.json")
    data = json.loads(io.open(dp, encoding="utf-8").read())
    data["sections"][0]["images"].append(
        {"file": "images/90_drawn.png", "kind": "illustration", "alt": u"示意图·非实拍：剖面",
         "caption": u"按正文绘制", "based_on": [u"sec-01#层数"]})
    io.open(dp, "w", encoding="utf-8").write(json.dumps(data, ensure_ascii=False, indent=1))
    (d / "images" / "90_drawn.png").write_bytes(b"\x89PNG\r\n\x1a\n" + bytes(4096))

    DI.drop(u"测试领域", "images/90_drawn.png", root=str(d.parent), config_root=str(tmp_path),
            apply=True)
    cfg = json.loads(io.open(str(tmp_path / "config" / "topics" / "测试领域.json"),
                             encoding="utf-8").read())
    assert cfg["image_exclude_pages"] == [], u"示意图被写进了排除表：%s" % cfg["image_exclude_pages"]
