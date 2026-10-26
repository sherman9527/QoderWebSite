# -*- coding: utf-8 -*-
"""W-190：闸门开始读 `retrieved`，页面开始印「核对于」。

发现过程（10-04 查证，不是猜）：29 篇**全部**带逐条来源的 `retrieved`，
而 `grep -n "retrieved" scripts/validate.py` 一条都没有——14 条闸门里没有任何一条看日期。
所以"这批站点是长期资产"这件事在质量线上完全隐形：
页面写满了「截至 2026-09-xx」「公价」「同比」，发布之后没有任何东西回头说"这条该重核了"。

三条形态决定（本轮由 agent 裁决，开发者可改 `config/quality_bar.json` 的阈值）：
· 阈值**不按类别**，按该篇自带的时点断言密度——类别名钉进代码会随大纲漂移，密度由文本自己说；
· 过期只 **warn** 不 fail（W-158 的教训：防呆判据在第二种成因下会变成阻塞器）；
· 核对日**印给读者**（页面上本来就有"数据时点/生成于"两个日期，缺的正是第三个）。
"""
import datetime as dt
import io
import json
import os
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import freshness as F  # noqa: E402
import validate as V   # noqa: E402

BAR = json.load(io.open(os.path.join(ROOT, "config", "quality_bar.json"), encoding="utf-8"))
FIX = os.path.join(ROOT, "tests", "fixtures", "mini_data.json")


def _data(retrieved, marks):
    d = json.load(io.open(FIX, encoding="utf-8"))
    # 只改日期、不换来源清单：夹具里的正文按 S1 标号引用，整表替掉会让渲染报错找不到标号
    for s in d.get(u"sources") or []:
        s[u"retrieved"] = retrieved
    # 时点标记：往每章第一个区块塞 `marks` 个"截至"，用来造密度
    for s in d.get(u"sections") or []:
        blocks = s.get(u"blocks") or []
        if blocks:
            blocks[0][u"text"] = (blocks[0].get(u"text") or u"") + u"截至 " * marks
    return d


def _gate(data, tmp_path):
    """用真产物形状跑 G-15：闸门要读 HTML 与 data，所以得把 data.json 落盘。"""
    out_dir = tmp_path / u"output" / u"新鲜度"
    out_dir.mkdir(parents=True)
    io.open(str(out_dir / u"data.json"), u"w", encoding=u"utf-8").write(
        json.dumps(data, ensure_ascii=False))
    page = out_dir / u"新鲜度.html"
    page.write_text(u"<html><body><h1>x</h1></body></html>", encoding="utf-8")
    ctx = V.Ctx(u"新鲜度", str(out_dir), str(page), u"<html><body><h1>x</h1></body></html>",
                data, BAR)
    gate = [g for g in V.DOMAIN_GATES if g.id == u"G-15"]
    assert gate, u"G-15 没登记进闸门表"
    return list(gate[0].check(ctx))


def test_a_stale_dense_article_is_due():
    today = dt.date.today()
    old = (today - dt.timedelta(days=45)).isoformat()
    v = F.verdict(_data(old, 12), BAR, today=today)
    assert v[u"due"], v


def test_a_fresh_article_is_not_due():
    today = dt.date.today()
    v = F.verdict(_data((today - dt.timedelta(days=3)).isoformat(), 12), BAR, today=today)
    assert not v[u"due"], v


def test_the_threshold_comes_from_density_not_from_the_category():
    """同一篇、同样 45 天：时点标记密就该到期，稀疏就不该——
    阈值若按类别写死，这一对就分不开（而它们类别相同）。"""
    today = dt.date.today()
    old = (today - dt.timedelta(days=45)).isoformat()
    dense = F.verdict(_data(old, 12), BAR, today=today)
    sparse = F.verdict(_data(old, 0), BAR, today=today)
    assert dense[u"limit_days"] < sparse[u"limit_days"], (dense, sparse)
    assert dense[u"due"] and not sparse[u"due"], (dense, sparse)


def test_no_retrieved_date_at_all_counts_as_due_not_as_forever_fresh():
    today = dt.date.today()
    d = _data((today - dt.timedelta(days=1)).isoformat(), 3)
    for s in d[u"sources"]:
        s.pop(u"retrieved", None)
    v = F.verdict(d, BAR, today=today)
    assert v[u"due"] and v[u"last_retrieved"] is None, v


def test_G15_warns_and_never_fails(tmp_path):
    today = dt.date.today()
    findings = _gate(_data((today - dt.timedelta(days=400)).isoformat(), 12), tmp_path)
    assert findings, u"过期 400 天一条都没报"
    assert all(f.level == u"warn" for f in findings), [str(f) for f in findings]


def test_G15_is_silent_for_a_fresh_page(tmp_path):
    today = dt.date.today()
    findings = _gate(_data((today - dt.timedelta(days=1)).isoformat(), 12), tmp_path)
    assert not findings, [str(f) for f in findings]


def test_an_offline_rerender_does_not_move_the_data_as_of_label(tmp_path, monkeypatch):
    """`--offline` 一个来源都没重新核，就不许把"数据时点"抬到新月份。

    `generate.py` 里 `created_date` 上面那行注释刚说清楚"`--offline` 重跑不许改写它"，
    下一行的 `data_as_of` 用的却是直接赋值 —— 同一个坑就在警告下面一行。
    后果不是抽象的：改一次模板要全站重渲染（G-08 逼的），于是 32 篇的
    「数据时点」被集体抬到渲染那个月，而页面上另一行「核对于 <真实日期>」没动，
    **同一页自相矛盾**，且说谎的那一行正是声称新鲜度的那一行。
    """
    import generate as G

    d = tmp_path / u"时点"
    d.mkdir()
    dp = d / "data.json"
    dp.write_text(json.dumps({u"topic": u"时点", u"data_as_of": u"2026-09"},
                             ensure_ascii=False), encoding="utf-8")
    data = json.loads(dp.read_text(encoding="utf-8"))
    today = "2026-10-26"

    G._stamp_dates(data, today, offline=True)
    assert data["data_as_of"] == u"2026-09", \
        u"--offline 把数据时点从 2026-09 抬到了 %s，可一个来源都没重新核" % data["data_as_of"]
    G._stamp_dates(data, "2026-11-05", offline=False)
    assert data["data_as_of"] == u"2026-11", u"真跑了研究还不更新时点，那这字段就没意义了"


def test_no_published_page_claims_a_data_vintage_newer_than_its_last_check():
    """扫真实仓库：任何一篇的「数据时点」都不许晚于它的「最后核对日」。

    页面上这两个日期并排印着，晚于就是同屏自相矛盾。10-26 量到全站 32 篇
    全都 `data_as_of=2026-10`，而多数最后核对在 9 月——因为 `--offline` 重渲染
    会按"渲染当月"改写它（见上一条测试）。这条扫全量，修不干净就一直红。
    """
    root = os.path.join(ROOT, "output")
    bad = []
    checked = 0
    for topic in sorted(os.listdir(root)):
        dp = os.path.join(root, topic, "data.json")
        if not os.path.isfile(dp):
            continue
        data = json.load(io.open(dp, encoding="utf-8"))
        as_of = data.get("data_as_of")
        last = F.last_retrieved(data)
        if not as_of or not last:
            continue                      # 没有可比的两端，交给别的判据管
        checked += 1
        try:
            claimed = dt.date.fromisoformat(as_of + "-01")
        except ValueError:
            bad.append((topic, as_of, str(last), u"时点不是 YYYY-MM"))
            continue
        if claimed > last:
            bad.append((topic, as_of, str(last), u"时点晚于最后核对"))
    assert checked >= 30, u"只量到 %d 篇，这条扫的不是全站" % checked
    assert not bad, u"%d 篇的数据时点比它自己的核对日更新，页面同屏矛盾：%s" % (
        len(bad), "；".join("%s(%s>%s)" % (b[0], b[1], b[2]) for b in bad[:6]))


def test_the_page_prints_the_last_check_date(tmp_path):
    """读者看得见的第三个日期。前两个（数据时点、生成于）早就有，
    缺的正是"这些来源最后一次逐条核对是哪天"。"""
    data = _data(u"2026-09-20", 0)
    data[u"sources"].append({u"id": u"S002", u"url": u"https://example.com/b",
                             u"label": u"另一条", u"retrieved": u"2026-09-28"})
    d = tmp_path / u"核对于"
    d.mkdir()
    (d / u"images").mkdir()
    dp = d / u"data.json"
    dp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    out = d / u"核对于.html"
    p = subprocess.run(
        ["node", os.path.join("scripts", "render.mjs"), "--data", str(dp), "--out", str(out)],
        cwd=ROOT, capture_output=True, timeout=300)
    assert p.returncode == 0, p.stderr.decode("utf-8", "ignore")[-600:]
    html = io.open(str(out), encoding="utf-8").read()
    assert u"核对于 2026-09-28" in html, u"页面上没有印出最后核对日（应取最晚那条 retrieved）"
    assert u"2026-09-20" not in html.split(u"核对于")[1][:20], u"印成了最早那条"
