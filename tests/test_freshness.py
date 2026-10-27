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
import re
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


# ────────────────────────────────────────────────────────────────────────────
# W-213（10-27）：到期重核的机械层。这三条钉的是"工作面怎么数"与"不许盖章"。

def _load_rc():
    import importlib.util
    p = os.path.join(ROOT, "audit", "tools", "resource_check.py")
    spec = importlib.util.spec_from_file_location("resource_check", p)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def test_the_due_worklist_counts_what_the_reader_can_see(tmp_path):
    """一条来源算不算"要重核"，判据是**页面上印出来了没有**，不是它有没有被区块引用。

    两个方向都会错：`data.json` 里一大半是研究阶段的爬虫残留，读者从来看不见（按它数会虚高）；
    而模板的 Refs 会列出比 `block.source_ids` 更多的条目，只按 source_ids 数会**少算**
    ——10-27 实测某篇区块引用 18 条、页面印出 78 条，差 4 倍的活。
    """
    RC = _load_rc()
    data = {u"sources": [
        {u"id": u"S001", u"url": u"https://a/1", u"label": u"承重的"},
        {u"id": u"S002", u"url": u"https://a/2", u"label": u"也被印出来了"},
        {u"id": u"S003", u"url": u"https://a/3", u"label": u"爬虫残留，没印"},
        {u"id": u"S004", u"url": u"https://a/4", u"label": u"页面上这个编号是假的"},
    ]}
    html = u"<p>S001 S002</p><ul><li>S003</li></ul>"
    # S003 印在页面上但……它印了就该核；S004 印了但 data 里没有 → 不算（不是本篇来源）
    assert RC.visible_ids(u"某篇", data, html) == [u"S001", u"S002", u"S003"]


def test_anchors_and_states_separate_a_changed_page_from_a_failed_fetch():
    """「抓不到」与「抓到了但不再说那句话」必须是两个状态——
    把它们混成一个，重核清单就会把反爬页面报成内容变了，
    而 W-158 的教训正是这类 A/B 混判（量了五次才敢报数）。"""
    RC = _load_rc()
    src = {u"id": u"S011", u"label": u"2026 年 9 月 25 日均值 +8 民主党，样本量 1,200"}
    good = b"<html>" + u"2026 年 9 月 +8 1,200".encode("utf-8") + b" " * 1300 + b"</html>"
    _id, st, anc, missing, why = RC.classify(src, good, u"")
    assert st == u"OK" and anc, u"原文里全找得到却报了别的状态：%s/%s" % (st, missing)
    gone = b"<html>" + u"2026 年 9 月 +8".encode("utf-8") + b" " * 1300 + b"</html>"
    _id2, st2, _, missing2, _ = RC.classify(src, gone, u"")
    assert st2 == u"CHANGED" and missing2 == [u"1,200"], \
        u"少了的那个锚点必须点名，否则判据层无从读起：%s/%s" % (st2, missing2)
    _id3, st3, _, _, why3 = RC.classify(src, b"", u"curl rc=6")
    assert st3 == u"FETCHFAIL", u"抓不到不能混进「内容变了」：%s" % st3
    _id4, st4, _, _, _ = RC.classify({u"id": u"S9", u"label": u"一句话没有数字"},
                                      b"<html>" + b"x" * 2000, u"")
    assert st4 == u"NOANCHOR", u"label 里没有可机械核对的片段时必须单列，不许假绿成 OK"


def test_the_refetch_tool_cannot_stamp_a_retrieval_date():
    """这条钉的是**设计**：核对器只产出读数，永远不许写 `retrieved`。

    10-26 刚拆掉那个谎（D-41）：没人重新核对任何一个网页，页面却声称数据时点是当月。
    如果这个脚本顺手加一个 `--apply` 把日期刷成今天，它就成了同一个谎的批量生产器——
    一次跑完，10 篇的 `data_as_of` 全部合法前进，而读者看到的还是没人读过的引用。
    所以"不许"要写成一条会红的测试，而不是文件头一句注释。
    """
    p = os.path.join(ROOT, "audit", "tools", "resource_check.py")
    src = io.open(p, encoding="utf-8").read()
    assert '["retrieved"] =' not in src and "['retrieved'] =" not in src, \
        u"核对器里出现了写 retrieved 的语句——那正是 D-41 拆掉的谎的批量版"
    assert u"--apply" not in src, u"加了 --apply 就等于把「只读」这个保证换成了一个参数"
    bad = [b.group(0) for b in re.finditer(r'open\([^)]{0,200}?\)', src)
           if re.search(r'["\'](w|a)t?["\']', b.group(0)) and u"data.json" in b.group(0)]
    assert not bad, u"不许以写模式打开 data.json：%s" % [x[:80] for x in bad]


def test_a_pdf_source_is_read_as_text_not_as_tag_soup():
    """govinfo 那三份联邦公报是 **PDF**。用"剥 HTML 标签"的办法读 PDF 字节，
    每一个锚点都会"找不到"——于是我的仪表读不出内容，被汇报成"来源不再这么说"。

    10-27 第一次跑这篇就是这么红的：78 条里 24 条 CHANGED，其中一大半是 PDF/CSV。
    不先修仪表就下"这些来源过期了"的结论，会把一次工具缺陷写成一次内容事故。
    """
    RC = _load_rc()
    fitz = pytest.importorskip("fitz")
    doc = fitz.open()
    pg = doc.new_page()
    pg.insert_text((72, 72), "14148 Initial Rescissions of Harmful Executive Orders Vol.90 No.17")
    raw = doc.tobytes()
    doc.close()
    text, how = RC.extract_text(
        raw, u"https://www.govinfo.gov/content/pkg/FR-2025-01-28/pdf/2025-01901.pdf")
    assert how == u"pdf", u"没认出这是 PDF（按 %s 读了）" % how
    assert u"14148" in text and u"Initial Rescissions" in text, \
        u"PDF 里的正文没被抽出来，锚点当然全都「找不到」：%s" % text[:120]


def test_a_csv_is_read_as_plain_text():
    """FRED 的 fredgraph.csv 是纯文本，别因为它不是 HTML 就当二进制丢掉。"""
    RC = _load_rc()
    text, how = RC.extract_text(b"DATE,DGS10\n2026-10-03,4.11\n", u"https://fred.stlouisfed.org/graph/fredgraph.csv?id=DGS10")
    assert u"4.11" in text and how == u"text", u"CSV 没按文本读：%s/%s" % (how, text[:80])


def test_a_chinese_summary_phrase_is_not_an_anchor_on_an_english_page():
    """label 是我写的**中文摘要**，页面是英文的。
    拿摘要里的中文短语当锚点去英文页面上找，**永远找不到**——
    于是仪表把自己的措辞当成来源的变动，第一轮那 24 条 CHANGED 里一大半是这个形状
    （S013「投给哪党候选人」、S046「州诉讼与总检察长活动数据库」、S027「选举日邮戳」）。

    判据：机械层只拿**语言中立**的片段当锚点——数字、百分比、日期、拉丁专名。
    中文短语只能在中文来源上核，那是另一件事（由人读）。
    """
    RC = _load_rc()
    anc = RC.anchors_of(u"Silver Bulletin 民调均值方法：优先采用 LV 版本，排除「投给哪党候选人」这种引导性问法")
    assert all(not re.search(u"[一-鿿]", a) for a in anc), \
        u"中文摘要短语被当成锚点了，英文页面必然报 CHANGED：%s" % anc
    assert u"Silver Bulletin" in anc, u"语言中立的专名锚点不能一起丢掉：%s" % anc
    # 「LV」这种两字母缩写故意不当锚点：它在任何英文页面里都可能偶然出现，
    # 用它判"来源还在这么说"会造出假绿——弱锚点比没锚点更坏。
    assert all(len(a) > 2 for a in anc), u"两字母缩写进了锚点：%s" % anc


def test_a_label_with_only_chinese_prose_is_reported_uncheckable_not_changed():
    """读不了要说"读不了"，不许说"变了"——这是 D-41 那类谎在工具层的同构。"""
    RC = _load_rc()
    src = {u"id": u"S046", u"label": u"州诉讼与总检察长活动数据库", u"url": u"https://a/x.html"}
    _id, st, anc, missing, why = RC.classify(src, b"<html>" + b"Attorney General multistate" * 90, u"")
    assert st == u"NOANCHOR", u"这条机械层根本无从判断，应报 NOANCHOR 而不是 CHANGED：%s/%s" % (st, anc)


def test_a_page_that_updated_is_not_the_same_as_a_source_that_stops_supporting_us():
    """来源自己更新了（民调页每天改数），而我们印的是**带着日期的那一版读数**——
    那一版的证据在我们手里的 `sources[].cache` 快照里，不在今天的页面上。
    把这两种情况都报成 CHANGED，剩下九篇会淹死在假红里：
    凡是逐日更新的页面，重核一遍就"全部过期"一次。
    """
    RC = _load_rc()
    src = {u"id": u"S012", u"url": u"https://x/y",
           u"label": u"均值页：10 月 5 日那版 D +8.9；10 月 26 日那版 D +9.2",
           u"cache": u"text/does-not-matter.txt"}
    fresh = (u"the average is D +9.2 as of October 26 " * 60).encode("utf-8")
    cached_old = u"the average was D +8.9 on October 5 " * 60
    out = RC.classify(src, fresh, u"", cached=cached_old)
    _id, st, anc, missing, why = out
    assert st == u"MOVED", u"今天页面没有 +8.9、但我们的 10-05 快照里有——这是「页面更新了」：%s/%s" % (st, missing)
    assert u"+8.9" in missing and u"+8.9" in why, u"要说清是哪个锚点退到了快照里：%s" % why
    # 两边都找不到才是真的不再支持我们
    out2 = RC.classify(src, fresh, u"", cached=u"nothing relevant " * 200)
    assert out2[1] == u"CHANGED", u"快照里也没有，就该是 CHANGED 而不是 MOVED：%s" % out2[1]
