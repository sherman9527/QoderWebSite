# -*- coding: utf-8 -*-
"""`recover_images.py` 的回归。

这个命令存在的全部理由是：09-21 与 09-22 两次硬杀之后，我都得**手写脚本**
从 manifest 拼 data.json 的配图引用（W-99 那次就是这么救的，还把 redo3 的记录弄丢了）。
W-85b 已经把 records.json 落盘了，但没有消费者——没有消费者的凭据等于假保险。
所以这里的判据是"能不能真的把一篇拼回可发布状态"，不是"能不能读到那份 JSON"。
"""
import io
import json
import os

import pytest

import generate as G
import recover_images as R
from conftest import make_passing_data

TOPIC = u"咖啡"
WRECKED = ("sec-01", "sec-02")   # 假装这两章正好死在重做中途


def _rec(sid, name, query=u"咖啡 起源"):
    """`collect` 一行的形状：除了 schema 允许的七个键，还多带 source_image /
    title / bytes / format，以及为恢复而加的 section。
    alt/caption 里带上领域名是真实记录的常态——能进 data.json 的图本来就先过了
    点名闸门（W-99 之后），下面的测试正是拿这一点当默认基线。"""
    return {"file": "images/%s" % name, "alt": u"咖啡 %s 的配图" % name,
            "caption": u"咖啡 %s 说明" % name, "source_page": "https://src.example/%s" % name,
            "source_image": "https://cdn.example/%s" % name, "title": u"咖啡 %s 原页标题" % name,
            "width": 1600, "height": 900, "bytes": 50004, "format": "jpg",
            "query": query, "section": sid}


@pytest.fixture
def wrecked(tmp_path):
    """复现硬杀后的形状：data.json 引用 0 张，图与记录都留在 images.prev/。"""
    d = tmp_path / "output" / TOPIC
    (d / "images").mkdir(parents=True)
    (d / "images.prev").mkdir()
    recs = [_rec(WRECKED[0], "01_origins.jpg"),
            _rec(WRECKED[0], "02_yemen.jpg", u"也门 摩卡港"),
            _rec(WRECKED[1], "03_roast.jpg")]
    for r in recs:
        (d / "images.prev" / os.path.basename(r["file"])).write_bytes(
            b"\xff\xd8\xff\xe0" + bytes(50000))
    data = make_passing_data(topic=TOPIC)
    for s in data["sections"]:
        if s["id"] in WRECKED:
            s["images"] = []
    (d / "data.json").write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    (d / "images.prev" / "records.json").write_text(
        json.dumps(recs, ensure_ascii=False), encoding="utf-8")
    return d


def _data(d):
    return json.load(io.open(str(d / "data.json"), encoding="utf-8"))


def _refs(d):
    return {s["id"]: [im["file"] for im in s["images"]]
            for s in _data(d)["sections"] if s["id"] in WRECKED}


def test_a_hard_killed_domain_is_put_back_from_the_snapshot_records(wrecked):
    assert R.main([TOPIC, "--output", str(wrecked.parent), "--apply"]) == 0
    got = _refs(wrecked)
    assert got[WRECKED[0]] == ["images/01_origins.jpg", "images/02_yemen.jpg"]
    assert got[WRECKED[1]] == ["images/03_roast.jpg"]
    # 引用回来了、文件却没回来，等于亲手给闸门造一堆"引用的图片不存在"
    for sid, files in got.items():
        for f in files:
            assert (wrecked / f).is_file(), u"%s 指着不存在的文件" % f


def test_restored_refs_still_carry_the_query_or_the_audit_cannot_triage_them(wrecked):
    """体检器靠 query 分诊"检索词没点名"与"点名了还给脏图"（W-95）。
    恢复时丢了 query，这些图就永久变成不可分诊。"""
    R.main([TOPIC, "--output", str(wrecked.parent), "--apply"])
    ims = [s for s in _data(wrecked)["sections"] if s["id"] == WRECKED[0]][0]["images"]
    assert ims[1]["query"] == u"也门 摩卡港"


def test_the_record_only_shape_is_stripped_because_the_schema_forbids_it(wrecked):
    """records.json 存的是 `collect` 的整行，多带 source_image / title / bytes /
    format / section；而契约里图片对象是 `additionalProperties:false`，只认七个键
    （真产物每张图恰好只有那七个，见 output/咖啡/data.json）。
    照抄回去会让 G-10 当场判死——"恢复"就变成第二次事故。"""
    R.main([TOPIC, "--output", str(wrecked.parent), "--apply"])
    errs = G._schema_errors(_data(wrecked))
    assert not errs, u"恢复出来的 data.json 不合契约：%s" % errs[:3]
    allowed = {"file", "alt", "caption", "source_page", "width", "height", "query"}
    for s in _data(wrecked)["sections"]:
        for im in s["images"]:
            assert set(im) <= allowed, u"多带了 schema 不认的键：%s" % sorted(set(im) - allowed)


def test_a_section_that_still_has_images_is_not_touched(wrecked, tmp_path):
    """已有图的章节可能正是这一轮新抓的、更好的那批。恢复工具的活是补缺口，
    不是拿旧快照盖掉新成果——那正是 W-100 刚修过的那类破坏。"""
    data = _data(wrecked)
    fresh = _rec(WRECKED[0], "09_fresh.jpg")
    for s in data["sections"]:
        if s["id"] == WRECKED[0]:
            s["images"] = [G.image_ref(fresh)]
    (wrecked / "data.json").write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    (wrecked / "images" / "09_fresh.jpg").write_bytes(b"\xff\xd8\xff\xe0" + bytes(50000))
    R.main([TOPIC, "--output", str(wrecked.parent), "--apply"])
    got = _refs(wrecked)
    assert got[WRECKED[0]] == ["images/09_fresh.jpg"], u"新成果被旧快照盖掉了"
    assert got[WRECKED[1]] == ["images/03_roast.jpg"], u"空着的那一章没补，工具白跑一趟"


def test_a_record_whose_file_is_nowhere_is_not_restored(wrecked):
    (wrecked / "images.prev" / "03_roast.jpg").unlink()
    R.main([TOPIC, "--output", str(wrecked.parent), "--apply"])
    got = _refs(wrecked)
    assert got[WRECKED[1]] == []
    assert len(got[WRECKED[0]]) == 2, u"别的章节不该被这一张牵连"


def test_dry_run_is_the_default(wrecked):
    """与 prune_scratch / audit_images 同一条约定：默认只报不改。
    恢复要动的是已入库的 data.json，没人希望一次"先看看"就把它写了。"""
    before = (wrecked / "data.json").read_text(encoding="utf-8")
    assert R.main([TOPIC, "--output", str(wrecked.parent)]) == 0
    assert (wrecked / "data.json").read_text(encoding="utf-8") == before
    assert not (wrecked / "images" / "01_origins.jpg").exists()


def test_without_records_it_refuses_to_guess_from_the_manifest(wrecked, capsys):
    """manifest.json 没有 section 字段。凭它猜章节会把图发给错的章节，
    而猜不出来时它会安静地产出一个"看起来恢复了"的 data.json。"""
    (wrecked / "images.prev" / "records.json").unlink()
    (wrecked / "images" / "manifest.json").write_text(
        json.dumps([{"file": "images/01_origins.jpg", "url": "https://x/1"}]),
        encoding="utf-8")
    assert R.main([TOPIC, "--output", str(wrecked.parent), "--apply"]) != 0
    out = capsys.readouterr().out
    assert u"records.json" in out, u"报错没指路：该说清凭据在哪份文件里"
    assert _refs(wrecked) == {WRECKED[0]: [], WRECKED[1]: []}, u"没凭据却还是动了 data.json"


# ---------------------------------------- W-115：恢复也要过点名这道判据

def _with_junk_record(wrecked):
    """往快照记录里塞一条"从头到尾没点名领域"的图——积家 09-23 的真实形状。"""
    p = wrecked / "images.prev" / "records.json"
    recs = json.loads(p.read_text(encoding="utf-8"))
    bad = _rec(WRECKED[1], "13_机芯.jpg", u"机芯 清洗")
    bad["alt"] = u"冠蓝狮_机芯｜世界最牛逼的石英机芯？西铁城光动能Cal.0100机芯！"
    bad["caption"] = u"西铁城机芯清洗油渍"
    bad["source_page"] = "https://www.xbiao.com/20230112/70937.html"
    bad["title"] = bad["alt"]
    recs.append(bad)
    p.write_text(json.dumps(recs, ensure_ascii=False), encoding="utf-8")
    (wrecked / "images.prev" / "13_机芯.jpg").write_bytes(b"\xff\xd8\xff\xe0" + bytes(50000))
    return recs


def test_recovery_refuses_to_restore_images_that_never_named_the_subject(wrecked):
    """09-23 实测：积家重做后只剩 1 张图，我用这个命令把快照里的 6 张补了回去，
    拼成联络表用眼睛一看——木工坊、永乐大钟、西铁城机芯、江诗丹顿机芯、智能手表表盘。
    恢复工具不做点名判断，就会把"重做之前的脏基线"当成资产搬回来，
    而 W-109 专门就是为了不让回滚干这件事。"""
    _with_junk_record(wrecked)
    assert R.main([TOPIC, "--output", str(wrecked.parent), "--apply"]) == 0
    got = _refs(wrecked)
    assert "images/13_机芯.jpg" not in got[WRECKED[1]], u"没点名领域的图被补回来了"
    assert got[WRECKED[1]] == ["images/03_roast.jpg"], u"点名的那些也被连坐了"


def test_force_is_the_only_way_to_backfill_an_unnamed_record(wrecked):
    """留一条明路：人看过联络表、确认这张图其实配得上，就该能显式补回来。
    默认不补 + 要补得说 --force，比"默认补错、要躲得改代码"好。"""
    _with_junk_record(wrecked)
    assert R.main([TOPIC, "--output", str(wrecked.parent), "--apply", "--force"]) == 0
    assert "images/13_机芯.jpg" in _refs(wrecked)[WRECKED[1]]
