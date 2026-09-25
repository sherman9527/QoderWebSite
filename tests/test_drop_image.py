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
    target = "images/01_" + _files(d)[0].split("_", 1)[1]
    res = DI.drop(u"测试领域", target, root=str(d.parent), apply=True)

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
    data = json.loads(io.open(os.path.join(str(d), "data.json"), encoding="utf-8").read())
    sec = data["sections"][0]
    assert len(sec["images"]) == 1
    res = DI.drop(u"测试领域", sec["images"][0]["file"], root=str(d.parent), apply=True)

    assert res["emptied_sections"] == [sec["id"]], u"没报告哪一章被摘空：%s" % (res,)
