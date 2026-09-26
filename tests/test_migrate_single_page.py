# -*- coding: utf-8 -*-
"""W-145 单页化迁移：只留最新版，同时把"第一次上架是哪天"从文件名搬进 data.json。

这条脚本干的是**不可逆的一半**（删 36 个日期页），所以它的测试要先把
"哪些信息会在删除时永久丢失"钉住：日期页的名字是创建时间的唯一来源，
删之前不回填进 `created_date`，索引的排序依据就没了（W-128 那条性质会静默破掉）。
"""
import io
import json
import os

import pytest

import migrate_single_page as M


def _topic(out, topic, dates, created=None):
    d = out / topic
    (d / "images").mkdir(parents=True)
    for dt in dates:
        (d / ("%s_%s.html" % (topic, dt))).write_text(
            u'<html><body><img src="images/a.jpg"/></body></html>', encoding="utf-8")
    (d / "images" / "a.jpg").write_bytes(b"\xff\xd8\xff\xe0" + b"0" * 1000)
    data = {"topic": topic, "generated_date": dates[-1], "sections": [], "sources": []}
    if created:
        data["created_date"] = created
    (d / "data.json").write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return d


@pytest.fixture
def out(tmp_path):
    return tmp_path / "output"


def test_dry_run_deletes_nothing_and_writes_nothing(out, capsys):
    """默认必须只报不改。这条不是形式主义：迁移一旦跑错，日期页就没了，
    而日期页是创建时间唯一的来源——没有第二次机会。"""
    _topic(out, u"咖啡", [u"2026-09-20", u"2026-09-24"])
    before = sorted(os.listdir(str(out / u"咖啡")))
    rc = M.main([str(out)])
    assert rc == 0
    assert sorted(os.listdir(str(out / u"咖啡"))) == before, u"dry-run 动了磁盘"
    data = json.loads(io.open(str(out / u"咖啡" / "data.json"), encoding="utf-8").read())
    assert "created_date" not in data, u"dry-run 写了 data.json"
    err = capsys.readouterr().out
    assert u"咖啡" in err


def test_created_date_is_taken_from_the_oldest_dated_page_before_anything_is_deleted(out):
    """**先回填再删**，顺序不能反。

    删掉旧日期页之后，"这篇第一次上架是哪天"就永久无从查起了。
    取最早那篇（不是最新那篇）：那才是 W-128 定的口径。
    """
    d = _topic(out, u"咖啡", [u"2026-09-19", u"2026-09-22", u"2026-09-24"])
    assert M.main([str(out), "--apply"]) == 0
    data = json.loads(io.open(str(d / "data.json"), encoding="utf-8").read())
    assert data["created_date"] == u"2026-09-19", \
        u"创建时间取错了那一篇：%s" % data.get("created_date")


def test_only_the_newest_page_survives_and_it_has_the_stable_name(out):
    """留最新那页，名字改成 `<领域>.html`，其余日期页删掉。
    内容必须逐字节不变——迁移只动名字和数量，不动一个字节。"""
    d = _topic(out, u"咖啡", [u"2026-09-20", u"2026-09-24"])
    newest = io.open(str(d / u"咖啡_2026-09-24.html"), encoding="utf-8").read()
    assert M.main([str(out), "--apply"]) == 0
    pages = sorted(f for f in os.listdir(str(d)) if f.endswith(".html"))
    assert pages == [u"咖啡.html"], u"目录里剩下的页不对：%s" % pages
    assert io.open(str(d / u"咖啡.html"), encoding="utf-8").read() == newest, \
        u"迁移改了页面内容——它只该改名字"


def test_an_existing_created_date_is_never_overwritten(out):
    """已经回填过的领域不许被重跑改掉：`created_date` 的语义是"第一次"，
    重跑一次就变成一个"最近一次跑迁移的日子"，那和没有一样坏。"""
    d = _topic(out, u"咖啡", [u"2026-09-20", u"2026-09-24"], created=u"2026-08-01")
    assert M.main([str(out), "--apply"]) == 0
    data = json.loads(io.open(str(d / "data.json"), encoding="utf-8").read())
    assert data["created_date"] == u"2026-08-01"


def test_apply_tells_the_operator_a_rerender_must_follow(out, capsys):
    """删掉旧日期页之后，只被它们引用的图立刻变成 G-03 孤儿 → 那几篇闸门不过 →
    `_publishable` 把它们从索引里静默跳过。09-25 实测索引从 19 掉到 14。

    清理要交给重渲染（判据与 G-03 同源，不在迁移脚本里另写一遍），
    但**这一步不能靠人记得**：脚本必须把下一步喊出来。
    """
    _topic(out, u"咖啡", [u"2026-09-20", u"2026-09-24"])
    assert M.main([str(out), "--apply"]) == 0
    out_text = capsys.readouterr().out
    assert u"--offline" in out_text, u"迁移没提示还要重渲染，索引会静默缩水"


def test_a_topic_with_no_dated_page_is_skipped_not_crashed(out):
    """只搬有日期页的领域。没有 data.json 的目录（比如 index 的临时目录）
    不该让整条迁移挂掉——挂在一半的状态最难收拾。"""
    (out / "杂项目录").mkdir(parents=True)
    _topic(out, u"咖啡", [u"2026-09-24"])
    assert M.main([str(out), "--apply"]) == 0
    assert os.path.isdir(str(out / "杂项目录"))


def test_the_migration_writes_data_json_in_the_canonical_format(out):
    """`data.json` 只有一个作者：`generate._save`（原子写、indent=1）。
    迁移脚本自己 `io.open(...).write(json.dumps(indent=2))`，犯的是它要修的那类错——
    一次迁移把 19 份 data.json 全部重排，git 里几千行噪声，真正改的字段看不见。
    非原子写更阴：中途被杀就留一个半截 JSON，而它旁边那些日期页**已经删了**。"""
    import generate as G
    d = _topic(out, u"测试领域", [u"2026-01-01", u"2026-01-09"])
    plan = M.plan(str(out))[0]
    M.apply_plan(plan, lambda *a, **k: None)

    after = io.open(str(d / "data.json"), "rb").read()
    twin = str(out / "twin.json")
    G._save(twin, json.loads(after.decode("utf-8")))
    assert after == io.open(twin, "rb").read(), \
        u"迁移写的不是 _save 那套格式：整份文件被重排"
