# -*- coding: utf-8 -*-
"""端到端集成：五阶段跑通，零真实模型、零真实图片请求（tasks 8.4）。

这一层存在的理由：真实生成一次要几十分钟还花额度，没人会频繁跑它。
用替身把全流程压到几秒，开发者才真的会跑——跑不动的回归测试等于没有。
"""
import io
import json
import os
import re

import pytest

import generate as G
import images as images_mod
import llm
import outline as outline_mod
import validate as V

TOPIC = u"咖啡"


def _payload(sec, n):
    """一份能通过全部闸门的章节内容，字段形态与真实模型输出一致。"""
    body = (u"这一节的正文用来满足篇幅与信息密度要求，讲的是该章特有的具体取舍，"
            u"而不是可以套在任何章节上的空泛道理，也不反复抄写同一句话来凑字数。") * 7
    return {
        "sources": [{"id": "S1", "url": "https://src.example/%d" % n, "label": u"来源 %d" % n}],
        "blocks": [
            {"type": "prose", "heading": sec.title,
             "text": body + u"｜章节：%s" % sec.id},
            {"type": "fact_strip", "facts": [
                {"value": "1932", "label": u"关键年份", "source_ids": ["S1"]}]},
            {"type": "price_table", "as_of": "2026-09", "columns": [u"项目", u"数值"],
             "rows": [{"cells": [u"示例项", u"3.2 万元"], "source_ids": ["S1"]}]},
            {"type": "timeline", "items": [
                {"year": "1931", "text": u"起点事件的发生及其对行业的影响说明。",
                 "source_ids": ["S1"]},
                {"year": "1983", "text": u"转折事件的发生及其对行业的影响说明。",
                 "source_ids": ["S1"]}]},
            {"type": "note", "tone": "tip",
             "text": u"一条足够长的实操建议，用于验证 note 区块能贯通渲染与闸门。"},
        ],
    }


@pytest.fixture
def stubs(monkeypatch, tmp_path):
    """把 LLM 与图片检索换成替身，产物落到 tmp，不污染真实 output/。"""
    cfg = outline_mod.load_for_topic(TOPIC, root=G.ROOT)
    by_title = {s.title: s for s in cfg.sections}
    state = {"llm": [], "img": []}

    def fake_call(prompt, **kw):
        m = re.search(u"本章标题：(.+)", prompt or "")
        sec = by_title.get(m.group(1).strip()) if m else None
        assert sec, "提示词里认不出章节标题，prompt 模板与解析脱节了"
        state["llm"].append(sec.id)
        return json.dumps(_payload(sec, len(state["llm"])), ensure_ascii=False)

    monkeypatch.setattr(llm, "call", fake_call)

    n = {"i": 0}

    def fake_collect(queries, dest_dir, bar, keywords=None, log=None, **kw):
        out = []
        os.makedirs(os.path.join(dest_dir, "images"), exist_ok=True)
        for q in queries[:1]:   # 真实 collect 也是"每条检索词一张"，替身不能超发
            n["i"] += 1
            rel = "images/%02d_stub.jpg" % n["i"]
            open(os.path.join(dest_dir, rel.replace("/", os.sep)), "wb").write(
                b"\xff\xd8\xff\xe0" + bytes(50000))
            out.append({"file": rel, "query": q, "alt": q, "caption": q,
                        "width": 1200, "height": 800, "bytes": 50004, "format": "jpg",
                        "source_page": "https://page.example/%d" % n["i"],
                        "source_image": "https://cdn.example/%d" % n["i"], "title": q,
                        # 替身必须实现被替换函数的契约，不只是返回值形状：
                        # 真 collect 会标 fresh（本轮是否真的写了盘），
                        # 清理逻辑按它决定能不能删。替身不填 = 永远不删 = 孤儿测试全空转。
                        "fresh": True})
        state["img"].append(len(out))
        return out

    monkeypatch.setattr(images_mod, "collect", fake_collect)
    # 产物落 tmp，但保留 output/<领域>/ 这层结构——G-01 就是校验它的，绕开等于没测
    out_root = tmp_path / "output"
    out_root.mkdir(exist_ok=True)
    monkeypatch.setattr(G, "OUTPUT", str(out_root))
    monkeypatch.setattr(V, "OUTPUT", str(out_root))
    state["out"] = out_root
    return state


def test_pipeline_runs_all_five_stages(stubs, tmp_path):
    """完整跑通：每个章节都被生成过、产物存在、闸门全绿。"""
    rc = G.main([TOPIC, "--workers", "3"])
    assert rc == 0, "流水线未通过，退出码 %d" % rc
    assert sorted(stubs["llm"]) == sorted(s.id for s in
                                          outline_mod.load_for_topic(TOPIC, root=G.ROOT).sections)
    d = stubs["out"].joinpath(TOPIC)
    page = list(d.glob("咖啡.html"))
    assert page, "没有产出 HTML"
    # 发布成功之后不该留下任何换名残骸：`.pending` 是没过闸门的现场，
    # `.prev` 是回滚目标，两者都只在"这一篇还没发出去"的时候存在。
    leftovers = sorted(p.name for p in d.iterdir()
                       if p.name.endswith((".html.pending", ".html.prev")))
    assert not leftovers, "发布成功却留着换名残骸：%s" % leftovers
    html = page[0].read_text(encoding="utf-8")
    assert "template-fingerprint" in html
    assert not re.search(r'<(script|link)\b[^>]*https?://', html, re.I)
    data = json.loads(stubs["out"].joinpath(TOPIC, "data.json").read_text(encoding="utf-8"))
    assert len(data["sections"]) >= 12
    assert data["sources"], "没有来源就无法复核任何数字"


def test_gates_reject_a_tampered_product(stubs, tmp_path):
    """跑通之后故意破坏：闸门必须真的会拦，而不是只在好输入上"通过"。"""
    assert G.main([TOPIC, "--workers", "3"]) == 0
    dp = stubs["out"].joinpath(TOPIC, "data.json")
    data = json.loads(dp.read_text(encoding="utf-8"))
    for s in data["sections"]:
        s["images"] = []          # 抽掉全部配图
    dp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    findings, checked, _ = V.run(domains=[TOPIC])
    assert any(f.level == "fail" for f in findings), "抽掉配图后闸门居然没报错"


def test_failed_section_keeps_progress_for_resume(tmp_path, monkeypatch, stubs):
    """某节失败时，已成功的中间结果要留在 data.json 里，供 --only 续跑。"""
    def boom(prompt, **kw):
        if u"种植带" in prompt:
            raise llm.LlmError("该节模型超时")
        return stubs and json.dumps(_payload(
            type("s", (), {"id": "x", "title": u"替代"})(), 1), ensure_ascii=False)

    monkeypatch.setattr(llm, "call", boom)
    rc = G.main([TOPIC, "--workers", "1"])
    assert rc == 1, "有章节失败却报告成功"
    assert not list(stubs["out"].joinpath(TOPIC).glob("咖啡_*.html")),         "半成品页面被当作完成产出了"


def test_unknown_domain_explains_next_step(tmp_path, monkeypatch, capsys):
    """未配置领域：非 0 退出 + 说清下一步，且不产出任何空页面。"""
    monkeypatch.setattr(G, "OUTPUT", str(tmp_path / "output"))
    assert G.main([u"根本没有这个领域"]) == 2
    out = capsys.readouterr().err
    assert "config/topics" in out
    assert not os.path.exists(os.path.join(str(tmp_path), "output", u"根本没有这个领域"))


def test_offline_reuses_data_without_calling_llm(stubs, tmp_path, monkeypatch):
    """--offline 只重跑渲染与验收，不再花模型额度。"""
    assert G.main([TOPIC, "--workers", "3"]) == 0
    before = len(stubs["llm"])

    def no_call(*a, **k):
        raise AssertionError("--offline 不该再调模型")

    monkeypatch.setattr(llm, "call", no_call)
    monkeypatch.setattr(images_mod, "collect", no_call)
    assert G.main([TOPIC, "--offline"]) == 0
    assert len(stubs["llm"]) == before


def test_sources_cap_truncates_research_questions(monkeypatch):
    """--sources-per-section 是唯一真正决定单次耗时的开关（实测每章抓 ~12 个网页）。
    它必须落到提示词里那条"需要查证的问题"清单上，否则就是个假旗标。"""
    import generate as G
    import outline as O
    cfg = O.load_for_topic(u"咖啡", root=G.ROOT)
    sec = cfg.sections[0]
    assert len(sec.fact_prompts) >= 3, "大纲本身问题太少，这个测试就没意义了"
    bar = V._bar()
    monkeypatch.delenv("KE_SOURCES_PER_SECTION", raising=False)
    full = G.section_payload(cfg, sec, cfg.reader, u"", bar)
    monkeypatch.setenv("KE_SOURCES_PER_SECTION", "2")
    capped = G.section_payload(cfg, sec, cfg.reader, u"", bar)
    n_full = full.split("需要查证的问题")[-1].split("3. 每个数字型断言")[0].count("\n   - ")
    n_cap = capped.split("需要查证的问题")[-1].split("3. 每个数字型断言")[0].count("\n   - ")
    assert n_cap == 2 and n_cap < n_full, u"上限没生效：%s → %s" % (n_full, n_cap)


def test_default_tier_is_high_quality(monkeypatch):
    """开发者定的默认：不限制来源。快档必须显式声明才降级。"""
    import generate as G
    monkeypatch.delenv("KE_SOURCES_PER_SECTION", raising=False)
    assert G.sources_per_section() == 0, "默认就在偷偷限来源"


def test_image_queries_name_the_subject_without_being_lengthened(stubs, monkeypatch):
    """大纲的检索词大多不提品牌名——劳力士篇 33 条里只有 9 条提。
    不点名去搜，Bing 还回的是"COSC 认证证书""建筑结构基础知识"这类通用页，
    于是 images.score() 的"必须点名主语"这一档永远满足不了，只能退回放宽档。
    劳力士篇真就这么配上了"圆糯米""无人机保养10大技巧"。

    但补主语不能无条件拼长检索词：LV 篇把每条拼成 5 词之后，
    Bing 召回从 35 条崩到 1 条，22 张图重做成 1 张、10 章空掉。
    所以契约是"点名领域，或者本来就够长就别再加词"，不是"必须含领域名"。"""
    seen = []

    def spy(queries, dest_dir, *a, **k):
        seen.extend(queries)
        # 真的 collect 一定会建 images/ 目录，替身不建就会测到别的东西上
        os.makedirs(os.path.join(dest_dir, "images"), exist_ok=True)
        return []

    monkeypatch.setattr(images_mod, "collect", spy)
    G.main([TOPIC, "--workers", "2"])
    assert seen, "根本没发起图片检索"
    import images as IM
    cfg = outline_mod.load_for_topic(TOPIC, root=G.ROOT)
    subj = IM.subject_tokens(cfg)
    original = {q for s in cfg.sections for q in s.image_queries}
    silent = [q for q in seen
              if not any(s in q.lower() for s in subj) and len(q.split()) < 3]
    assert not silent, u"这些短检索词既没点名领域、也没被补上：%s" % silent[:4]
    # 允许的形态只有四种：大纲原文、"品牌名 + 原文"（≤3 词）、品牌单词（第三档兜底，
    # 见 test_brand_word_is_tried_before_the_subject_gate_is_dropped），
    # 以及**这一章自己检索词里相邻的两个词**（裸词跑题率实测是章节词的 3 倍，先问短的章节词）。
    primary = images_mod.primary_subject(subj)

    def from_outline_pair(q):
        toks = q.split()
        if len(toks) != 2:
            return False
        joined = u" ".join(t.lower() for t in toks)
        return any(joined in u" ".join(str(x).lower().split())
                   or joined in str(x).lower()
                   for s in cfg.sections for x in s.image_queries)

    invented = [q for q in seen if q not in original and q != primary
                and not (q.startswith(subj[0] + u" ") and len(q.split()) <= 3)
                and not from_outline_pair(q)]
    assert not invented, u"造出了不该有的检索词形态：%s" % invented[:4]


def test_redo_images_recollects_sections_that_already_have_images(stubs, monkeypatch):
    """配图相关性规则改了以后，已生成的领域要能只重做第 3 阶段。
    do_images 平时会跳过"已经够图"的章节——不显式清空，--redo-images 就是假旗标：
    跑完还是原来那批跑题图，而日志看起来一切正常。"""
    assert G.main([TOPIC, "--workers", "2"]) == 0
    data_path = os.path.join(str(stubs["out"]), TOPIC, "data.json")
    files_before = {im["file"] for s in
                    json.load(io.open(data_path, encoding="utf-8"))["sections"]
                    for im in (s.get("images") or [])}
    assert files_before, "首轮就没图，这个测试就没内容了"

    calls = []
    inner = images_mod.collect

    def spy(*a, **k):
        calls.append(a[0] if a else k.get("queries"))
        return inner(*a, **k)

    monkeypatch.setattr(images_mod, "collect", spy)
    assert G.main([TOPIC, "--workers", "2", "--redo-images"]) == 0
    assert calls, "--redo-images 一次图片检索都没发起"
    data = json.load(io.open(data_path, encoding="utf-8"))
    files_after = {im["file"] for s in data["sections"] for im in (s.get("images") or [])}
    assert files_after, "重做之后反而没图了"
    # 真换了一批：旧图不在了，才不会是"跳过已够图的章节"那条老路径假装重做了一遍
    assert not (files_after & files_before), u"还在用旧图：%s" % sorted(files_after & files_before)


def test_a_generated_domain_does_not_rewrite_the_real_index(stubs, monkeypatch):
    """跑一次集成测试就把入库产物 `output/index.html` 改了：索引自己算路径
    （`build_index.OUTPUT`），而夹具只 patch 了 `G.OUTPUT` / `V.OUTPUT`。
    后果不只是工作区脏：测试与真批量生成会互相覆盖同一个文件，
    而索引是"闸门全绿才重建"的东西，被测试写过一次就等于替坏页面盖了个绿章。"""
    real = os.path.join(G.ROOT, "output", "index.html")
    before = io.open(real, encoding="utf-8").read() if os.path.isfile(real) else None

    assert G.main([TOPIC, "--workers", "2"]) == 0

    after = io.open(real, encoding="utf-8").read() if os.path.isfile(real) else None
    assert after == before, u"集成测试改写了仓库里的 output/index.html"
    # 不是"根本没建索引"蒙过去的：索引确实建了，只是建在临时产物目录里
    assert os.path.isfile(os.path.join(str(stubs["out"]), "index.html")), \
        u"索引没建到临时目录，这条测试就成了空断言"


def test_a_crashing_redo_cannot_take_the_page_down_with_it(stubs, monkeypatch):
    """`--redo-images` 是先清空再抓。Bing CN 在同一条检索词上就能从 35 条掉到 5 条
    （今天实测两次），积家篇那轮更是整段 getaddrinfo failed。
    清空之后碰上抖动，就是把一篇 22 张图、闸门全绿的页面押上去赌一次网络——
    LV 篇真就这么从 22 张掉到 1 张、10 章空掉。
    重做可以没收获，但不能把没让它负责的东西一起赔进去。"""
    assert G.main([TOPIC, "--workers", "2"]) == 0
    dpath = os.path.join(str(stubs["out"]), TOPIC, "data.json")

    def refs():
        d = json.load(io.open(dpath, encoding="utf-8"))
        return [im["file"] for s in d["sections"] for im in (s.get("images") or [])]

    before = refs()
    assert len(before) >= 8, u"样本只有 %d 张图，撑不起这个断言" % len(before)

    calls = {"n": 0}
    inner = images_mod.collect

    def flaky(*a, **k):
        calls["n"] += 1
        # 只有第一次检索召回到东西，其余全灭——就是一次网络抖动的形状
        return inner(*a, **k) if calls["n"] == 1 else []

    monkeypatch.setattr(images_mod, "collect", flaky)
    assert G.main([TOPIC, "--workers", "2", "--redo-images"]) == 0
    after = refs()
    assert len(after) == len(before), \
        u"重做没收获，却把配图从 %d 张删成了 %d 张" % (len(before), len(after))
    img_dir = os.path.join(str(stubs["out"]), TOPIC)
    for f in after:
        p = os.path.join(img_dir, f.replace("/", os.sep))
        assert os.path.isfile(p), u"%s 只是引用回来了，文件已经不在了" % f
    # 备份位不能留着：output/ 是入库产物，留一份等于把整个图片目录复制进 git
    assert not os.path.exists(os.path.join(str(stubs["out"]), TOPIC, "images.prev"))


def test_a_useful_redo_keeps_the_new_images_and_loses_the_backup(stubs):
    """退路不能变成赖着不走的第二份真身：重做有收获时用上新图，备份当场删掉。"""
    assert G.main([TOPIC, "--workers", "2"]) == 0
    dpath = os.path.join(str(stubs["out"]), TOPIC, "data.json")
    before = {im["file"] for s in json.load(io.open(dpath, encoding="utf-8"))["sections"]
              for im in (s.get("images") or [])}
    assert G.main([TOPIC, "--workers", "2", "--redo-images"]) == 0
    data = json.load(io.open(dpath, encoding="utf-8"))
    after = {im["file"] for s in data["sections"] for im in (s.get("images") or [])}
    assert not (after & before), u"有收获却还在用旧图"
    prev = os.path.join(str(stubs["out"]), TOPIC, "images.prev")
    assert not os.path.exists(prev), "重做成功后备份目录还留着"


# --- W-85：上面那两条的退路都挂在 finally 上，硬杀不走 finally ------------------------
# 09-21 实测就是这个形状：百达翡丽被杀在配图阶段中途，data.json 引用 0 张、
# images/ 里躺着 19 张、images.prev/ 里 17 张、已发布页面里 18 个破链。
# 恢复要人手工从 manifest 拼记录。判据因此必须是"**任何时刻**"，不是"跑完之后"。

def _disk_refs(dpath):
    d = json.load(io.open(dpath, encoding="utf-8"))
    return [im["file"] for s in d["sections"] for im in (s.get("images") or [])]


def test_a_hard_kill_in_the_middle_of_the_redo_leaves_the_page_whole(stubs, monkeypatch):
    """重做刚开始抓图的那一刻——进程随时可能被打断——旧图必须还在盘上、
    已落盘的 data.json 必须还指着它们。先删后抓做不到这一点。"""
    assert G.main([TOPIC, "--workers", "2"]) == 0
    out = os.path.join(str(stubs["out"]), TOPIC)
    dpath = os.path.join(out, "data.json")
    before = _disk_refs(dpath)
    assert before, u"样本没有配图，这条测试会空转"

    seen = {}
    inner = images_mod.collect

    def watch(*a, **k):
        if not seen:
            seen["refs"] = _disk_refs(dpath)
            seen["files"] = set(f for f in os.listdir(os.path.join(out, "images")))
            snap = os.path.join(out, "images.prev")
            seen["snapshot"] = sorted(os.listdir(snap)) if os.path.isdir(snap) else []
        return inner(*a, **k)

    monkeypatch.setattr(images_mod, "collect", watch)
    G.main([TOPIC, "--workers", "2", "--redo-images"])

    assert seen["refs"] == before, \
        u"重做进行中落盘的 data.json 已经丢了旧引用：%d 张 → %d 张，此刻被硬杀就回不来" % (
            len(before), len(seen["refs"]))
    gone = [f for f in before if os.path.basename(f) not in seen["files"]]
    assert not gone, u"重做进行中旧图已被删除，此刻硬杀就是线上断图：%s" % gone[:3]
    # 快照记录要落盘：只在内存里的那份，进程一没就只剩文件、拼不回引用
    assert "records.json" in seen["snapshot"], \
        u"images.prev/ 只有文件没有记录，硬杀后要人手工从 manifest 拼回来"


def test_a_redo_never_deletes_a_file_the_published_data_still_uses(stubs, monkeypatch):
    """W-85 只堵住了 `_drop_images` 那一处删除，还有第二处：
    `collect` 按内容哈希"认回"上一轮已落盘的同一张图（复用旧文件名），
    而 do_images 结尾会把"抓到了却没派上用场"的图删掉——认回来的那张也在名单里，
    可它不是本轮产物，它可能正被已落盘的 data.json 指着。
    09-21 深夜实测抓到现行：LV 重做进行中，`04_路易威登.gif`、`08_Neverfull.jpg`
    被这样删掉，而那一刻 data.json 的引用还指着它们（页面 2 个破链）。"""
    assert G.main([TOPIC, "--workers", "2"]) == 0
    out = os.path.join(str(stubs["out"]), TOPIC)
    dpath = os.path.join(out, "data.json")
    before = _disk_refs(dpath)
    assert before, u"样本没有配图，这条测试会空转"

    calls = {"n": 0}
    holes = []

    def adopting_collect(queries, dest_dir, bar, **kw):
        calls["n"] += 1
        gone = [f for f in before
                if not os.path.isfile(os.path.join(out, f.replace("/", os.sep)))]
        if gone:
            holes.append((calls["n"], gone))
        fresh = "images/%02d_new.jpg" % calls["n"]
        with open(os.path.join(dest_dir, "images", os.path.basename(fresh)), "wb") as fh:
            fh.write(b"\xff\xd8\xff\xe0" + bytes(50000))
        def row(file, page, wrote):
            return {"file": file, "query": queries[0], "alt": u"标题", "caption": u"图注",
                    "source_page": page, "width": 1200, "height": 800, "fresh": wrote}
        # 第一条是本轮新下载的、会被用上；第二条"认回"旧文件、超出 need 所以会被丢弃
        return [row(fresh, "https://p.example/%d" % calls["n"], True),
                row(before[0], "https://p.example/old", False)]

    monkeypatch.setattr(images_mod, "collect", adopting_collect)
    G.main([TOPIC, "--workers", "2", "--redo-images"])
    assert not holes, u"重做进行中删掉了已落盘引用还指着的文件：%s" % holes[:2]


def test_rollback_does_not_restore_images_that_never_named_the_subject(stubs, monkeypatch):
    """逐章退回的判据是"这一章变少了没有"，它只看数量。
    09-23 实测这就是百达翡丽页面上还挂着柴油机、Calatrava 建筑、万年历 APP 的原因：
    新一轮引擎答非所问、这一章拿到 0 张，于是旧那批"根本没点名领域"的图被当成
    "没变差"整章退回来。空章会被 G-03 拦住（页面就不上架），
    脏图却能上架骗读者——所以退回必须只看**还值得看的那些**。
    """
    assert G.main([TOPIC, "--workers", "2"]) == 0
    dpath = os.path.join(str(stubs["out"]), TOPIC, "data.json")
    data = json.load(io.open(dpath, encoding="utf-8"))
    # 把第一章的旧图改成"不点名领域"的遗留记录（百达翡丽 09-22 的真实形状：无 query）
    first = data["sections"][0]
    first["images"] = [{"file": "images/01_stub.jpg", "alt": u"某行政区划图",
                        "caption": u"中国行政区划图", "source_page": "https://other.example/1",
                        "width": 1200, "height": 800}]
    G._save(dpath, data)

    def empty(*a, **k):
        return []

    monkeypatch.setattr(images_mod, "collect", empty)
    assert G.main([TOPIC, "--workers", "2", "--redo-images"]) != 0
    after = json.load(io.open(dpath, encoding="utf-8"))
    got = [im["file"] for s in after["sections"] for im in (s.get("images") or [])]
    assert "images/01_stub.jpg" not in [g for g in got
                                        if g.endswith("01_stub.jpg")] or         after["sections"][0]["images"], u"第一章被整章退回了不点名的旧图"
    assert not after["sections"][0]["images"],         u"这一章的旧图根本没点名领域，退回它等于用脏图换掉空章：%s" % after["sections"][0]["images"]


def test_the_snapshot_records_keep_the_query_that_found_them(stubs, monkeypatch):
    """落盘的快照记录必须带 query，否则从它恢复回来的图在体检器眼里
    又是"没有来路"，白恢复一次。"""
    assert G.main([TOPIC, "--workers", "2"]) == 0
    snap_dir = os.path.join(str(stubs["out"]), TOPIC, "images.prev")
    caught = {}
    inner = images_mod.collect

    def watch(*a, **k):
        p = os.path.join(snap_dir, "records.json")
        if not caught and os.path.isfile(p):
            caught["rows"] = json.load(io.open(p, encoding="utf-8"))
        return inner(*a, **k)

    monkeypatch.setattr(images_mod, "collect", watch)
    G.main([TOPIC, "--workers", "2", "--redo-images"])
    rows = caught.get("rows")
    assert rows, u"没在 images.prev/records.json 里抓到快照记录"
    assert all(r.get("section") for r in rows), u"快照记录没带章节，恢复时挂不回原章"
    assert all(r.get("query") for r in rows), \
        u"快照记录丢了来路（query），恢复回来的图会被体检器判成不可分诊"


def test_a_redo_cannot_steal_a_later_sections_picture_before_its_turn(stubs, monkeypatch):
    """重做时先处理的章节不许把**还没轮到**的章节的旧图认走。
    09-22 实测百达翡丽：history 这轮什么都没抓到，而它原来那两张被排在前面的章节
    按哈希认走了；轮到 history 退回时，W-92 的防撞规则只能判"不退"，
    于是那一章直接空掉——重复图的失败被换成了空章的失败，G-03 照样红。
    真正的修法是别在抓取阶段制造这种抢占：把未处理章节的旧图预留住。"""
    assert G.main([TOPIC, "--workers", "2"]) == 0
    out = os.path.join(str(stubs["out"]), TOPIC)
    dpath = os.path.join(out, "data.json")
    before = json.load(io.open(dpath, encoding="utf-8"))["sections"]
    own = {s["id"]: [im["file"] for im in (s.get("images") or [])] for s in before}
    own = {k: v for k, v in own.items() if v}
    assert len(own) >= 3, u"样本章节配图太少，撑不起这个断言"

    order = {"n": 0}
    ids = [s["id"] for s in before if own.get(s["id"])]
    victim_section, stolen = ids[1], own[ids[1]][0]

    def steal_then_starve(queries, dest_dir, bar, claimed=(), **kw):
        """第一章把第二章的旧图认走，其余章节这轮什么都抓不到——
        这就是百达翡丽 history 那轮的形状：它自己的图被前面章节认走，
        轮到它时只能空着。
        `claimed` 要照真 collect 的语义处理（被认领的文件不再给出），
        否则替身会绕过预留机制，这条测试就测不到修的那一半。"""
        order["n"] += 1
        taken = {os.path.basename(str(f)) for f in (claimed or ())}
        if order["n"] == 1 and os.path.basename(stolen) not in taken:
            return [{"file": stolen, "query": queries[0], "alt": u"图", "caption": u"注",
                     "source_page": "https://p.example/steal", "width": 1200, "height": 800,
                     "fresh": False}]
        return []

    monkeypatch.setattr(images_mod, "collect", steal_then_starve)
    G.main([TOPIC, "--workers", "2", "--redo-images"])

    data = json.load(io.open(dpath, encoding="utf-8"))
    by_id = {s["id"]: (s.get("images") or []) for s in data["sections"]}
    files = [im["file"] for s in data["sections"] for im in (s.get("images") or [])]
    assert len(files) == len(set(files)), u"退回之后仍有两章共用一张图"
    assert by_id.get(victim_section), \
        u"%s 本来有图，却被前面章节认走旧图、自己这轮又抓不到，最后空章" % victim_section


def test_snapshot_survives_two_sections_sharing_one_image(tmp_path):
    """两章共用一张图时，快照会把同一张文件第二次复制到它自己上 → shutil.SameFileError。
    `_prev_files` 先查 `images.prev/` 再查 `images/`，所以第一张复制进去之后，
    第二条记录找到的就是刚放进去的那个路径，copy2(src, dst) 里 src==dst。
    09-22 上午百达翡丽的重做就是这么在起跑线上退 1 的——它带着 W-92 留下的 3 张重复图。"""
    out = str(tmp_path)
    img = os.path.join(out, "images")
    os.makedirs(img)
    with open(os.path.join(img, "01_shared.jpg"), "wb") as fh:
        fh.write(b"\xff\xd8\xff\xe0" + bytes(3000))

    def rec():
        return {"file": "images/01_shared.jpg", "alt": u"图", "caption": u"注",
                "source_page": "https://p.example/1", "width": 1200, "height": 800,
                "query": u"检索词"}

    data = {"sections": [{"id": "A", "images": [rec()]}, {"id": "B", "images": [rec()]}]}
    seen = []
    snap = G._snapshot_images(out, {"A", "B"}, data, seen.append)
    assert set(snap) == {"A", "B"}, u"两章都该有快照，实际 %s" % sorted(snap)
    prev = os.path.join(out, "images.prev")
    assert os.path.isfile(os.path.join(prev, "01_shared.jpg")), "旧图没进快照位"
    assert os.path.isfile(os.path.join(prev, "records.json")), "快照记录没落盘"


def test_a_used_image_is_never_deleted_because_another_row_pointed_at_it(tmp_path, monkeypatch):
    """删除的安全性是**文件**的属性，不是**行**的属性。
    同一个文件可能在一次 do_images 里出现两次：第一次是"本轮新写的、但候选没有来源页"
    所以被丢掉（fresh=True），第二次是放宽档按哈希认回同一份字节、这次有来源页，于是被采用
    （fresh=False）。清理循环按行判断，`g in usable` 因为两个字典的 fresh 不同而判不相等，
    于是把**正在被采用的那张图删了**。09-22 code review 实测复现。"""
    out = str(tmp_path)
    img = os.path.join(out, "images")
    os.makedirs(img)
    cfg = outline_mod.load_for_topic(TOPIC, root=G.ROOT)
    data = {"topic": TOPIC, "sections": [{"id": cfg.sections[0].id,
                                          "title": cfg.sections[0].title, "blocks": [],
                                          "images": []}],
            "sources": []}
    F = "images/01_咖啡_起源.jpg"
    calls = {"n": 0}

    def two_faces(queries, dest_dir, bar, **kw):
        calls["n"] += 1
        if calls["n"] == 1:          # 本轮写的，但这条候选没有来源页 → 会被丢弃
            open(os.path.join(dest_dir, F), "wb").write(b"\xff\xd8\xff\xe0" + bytes(50000))
            return [{"file": F, "query": queries[0], "alt": u"图", "caption": u"注",
                     "source_page": "", "width": 1200, "height": 800, "fresh": True}]
        # 第二档按内容哈希认回同一个文件：这次这条候选有来源页，于是它会被**采用**
        return [{"file": F, "query": queries[0], "alt": u"图", "caption": u"注",
                 "source_page": "https://p.example/1", "width": 1200, "height": 800,
                 "fresh": False}]

    monkeypatch.setattr(images_mod, "collect", two_faces)
    G.do_images(cfg, data, out)

    refs = [im["file"] for s in data["sections"] for im in (s.get("images") or [])]
    assert F in refs, u"测试前提塌了：这张图本该被某一章采用，refs=%s" % refs
    assert os.path.isfile(os.path.join(out, F)), \
        u"正在被采用的图被另一行（同文件、fresh=True、被丢弃的那行）的清理逻辑删了"


def test_a_rolled_back_image_cannot_collide_with_another_section(tmp_path):
    """W-72 的逐章退回只问"这一章变少没有"，没问"这张图是不是已经被别的章节用走了"。
    重做时 B 章正好抓到 A 章的旧图，A 章这一章没收获又整章退回去 → 同一张图发给两章，
    G-03 的"配图重复：被 2 个章节共用"当场判死。
    09-22 实测百达翡丽就是这么红了 3 条（印记 / 价格表 / 博物馆三张 gif）。"""
    out = str(tmp_path)
    os.makedirs(os.path.join(out, "images"))
    os.makedirs(os.path.join(out, "images.prev"))
    with open(os.path.join(out, "images.prev", "01_a.jpg"), "wb") as fh:
        fh.write(b"x")

    def rec(f):
        return {"file": f, "alt": u"图注", "caption": u"说明",
                "source_page": "https://p.example/1", "width": 1200, "height": 800,
                "query": u"检索词"}

    data = {"sections": [
        {"id": "A", "images": []},                       # 本轮没收获，等着被退回
        {"id": "B", "images": [rec("images/01_a.jpg")]},  # 本轮 B 恰好抓到 A 的旧图
    ]}
    snap = {"A": [rec("images/01_a.jpg")]}

    G._rollback_images(out, data, snap, lambda m: None)

    files = [im["file"] for s in data["sections"] for im in s["images"]]
    assert len(files) == len(set(files)), u"同一张图被两章共用：%s" % files
    assert any(s["id"] == "B" and s["images"] for s in data["sections"]), \
        u"B 章的图被抢回去了——冲突该让给已经拿到图的那一章"


def test_rollback_skips_old_images_the_current_queries_would_reject(tmp_path):
    """改了检索词之后重做，"变少"是预期结果，不是召回崩了——回滚却只看数量。

    09-25 实测（大模型与加密货币篇）：把「稳定币」那章的检索词从我写错的
    `OpenAI`（领域里最热的实体之一）换成这一章真正在讲的 稳定币/储备/清算 之后重跑，
    该章 0 张合格，回滚按"变少了"把上一轮那张 `OpenAI放开ChatGPT限制` 原封退了回来，
    跑章图原地复活，还造成两章共用一张 → G-03 两条 fail。

    判据不是"撞上几个词"——我第一版那么写，撞 1 个太松（`学习软件编程` 里那个"软件"
    让一张椭圆曲线科普图回到 Lean 章），抬到 2 又比采集器本身还严（点名档允许 1 个命中），
    把 `test_a_crashing_redo_cannot_take_the_page_down_with_it` 弄红了。
    判据是**这张图当初是哪条词找出来的**：旧记录带着 `query`，只要它仍是这一章现在会发出的词
    （含采集器自己补主语的兄弟词与拆词重试），就是"这一章的旧图"；词已经不在了，
    它就是别的章的图。不立任何新阈值。
    """
    out = str(tmp_path)
    os.makedirs(os.path.join(out, "images"))
    os.makedirs(os.path.join(out, "images.prev"))
    for name in ("01_a.jpg", "02_b.jpg", "03_c.jpg"):
        with open(os.path.join(out, "images.prev", name), "wb") as fh:
            fh.write(b"x")

    def rec(f, cap, q):
        return {"file": f, "alt": cap, "caption": cap,
                "source_page": "https://p.example/1", "width": 1200, "height": 800,
                "query": q}

    stale = rec("images/01_a.jpg", u"比特币稳定币与储备资产说明", u"OpenAI")
    kept = rec("images/02_b.jpg", u"比特币稳定币储备资产审计报告", u"稳定币 储备 资产")
    sibling = rec("images/03_c.jpg", u"比特币稳定币储备资产清单", u"比特币 稳定币 储备")

    data = {"sections": [{"id": "stable", "images": []}]}
    snap = {"stable": [stale, kept, sibling]}
    queries = {"stable": [u"稳定币 储备 资产 公告", u"支付 清算 系统 机房"]}

    G._rollback_images(out, data, snap, lambda m: None,
                       subject={u"比特币"}, queries=queries)

    files = [im["file"] for im in data["sections"][0]["images"]]
    assert "images/01_a.jpg" not in files, \
        u"这张图当初是 `OpenAI` 找出来的，而这一章现在不发那条词——退回来就是别的章的图"
    assert "images/02_b.jpg" in files, \
        u"词没变、图也没坏，回滚必须保住它（召回崩了就靠这一条兜底）：%s" % files
    assert "images/03_c.jpg" in files, \
        u"补主语的兄弟词是采集器自己拼出来的，不该被当成别的章的词：%s" % files


def test_a_green_page_leaves_a_ready_package(stubs, monkeypatch, tmp_path):
    """闸门全绿、索引更新之后，这一篇的**待发包必须已经在 dist/ 里等着**。

    "新增文章自动带上 URL"这条链路里，脚本能做的就到这一步：
    发布要 agent 调托管工具（没有受支持的脚本发布路径），但包、指纹、清单
    都是确定性的，不该等人手工去拼。
    """
    import publish as PUB
    monkeypatch.setattr(G, "PUBLISH_DIST", str(tmp_path / "dist"))
    assert G.main([TOPIC, "--workers", "2"]) == 0
    pkg = tmp_path / "dist" / "coffee"
    assert (pkg / "index.html").is_file(), u"发布成功却没留下待发布的包"
    assert (pkg / "images").is_dir()


def test_repacking_is_skipped_when_the_content_did_not_change(stubs, monkeypatch, tmp_path):
    """同一篇重渲染两遍，第二遍不该重新出包。

    AGENTS 第 5 步改一次模板要把 19 篇全部 `--offline` 重渲染；
    朴素挂钩的代价就是 19 次打包 + 19 条"待发布"，而内容一个字都没变。
    判据是指纹，不是"这次跑没跑过"。
    """
    monkeypatch.setattr(G, "PUBLISH_DIST", str(tmp_path / "dist"))
    assert G.main([TOPIC, "--workers", "2"]) == 0
    first = (tmp_path / "dist" / "coffee" / "index.html").read_bytes()
    os.remove(str(tmp_path / "dist" / "coffee" / "index.html"))
    assert G.main([TOPIC, "--workers", "2", "--offline"]) == 0
    gone = tmp_path / "dist" / "coffee" / "index.html"
    assert not gone.exists(), \
        u"内容没变却又出了一次包——那 pending 清单会永远不为空"
    assert first, u"前提塌了：第一轮根本没出包"


def test_a_failed_gate_leaves_no_package(stubs, monkeypatch, tmp_path):
    """闸门没过就不该有包。半成品被下一次 `prepare_site` 误用，
    等于把一份没验证过的东西发上公网。"""
    monkeypatch.setattr(G, "PUBLISH_DIST", str(tmp_path / "dist"))
    monkeypatch.setattr(G, "verify", lambda *a, **k: 1)
    assert G.main([TOPIC, "--workers", "2"]) != 0
    assert not (tmp_path / "dist").exists() or not list((tmp_path / "dist").iterdir())


def test_a_failed_render_keeps_the_images_the_published_page_uses(stubs, monkeypatch):
    """渲染失败时不许已经把旧图清干净：新页面还没出生就删掉老页面的图，
    等于用一个失败的重做换来一次断图事故。"""
    assert G.main([TOPIC, "--workers", "2"]) == 0
    out = os.path.join(str(stubs["out"]), TOPIC)
    page = [f for f in os.listdir(out) if f.endswith(".html")]
    assert page, u"第一轮没产出页面，这条测试会空转"
    src = io.open(os.path.join(out, page[0]), encoding="utf-8").read()
    used = set(re.findall(r'src="images/([^"]+)"', src))
    assert used, u"页面里没有配图，断言撑不起来"

    def boom(*a, **k):
        raise RuntimeError("渲染替身故意失败")

    monkeypatch.setattr(G, "render", boom)
    assert G.main([TOPIC, "--workers", "2", "--redo-images"]) != 0
    still = set(f for f in os.listdir(os.path.join(out, "images"))
                if f.lower().endswith((".jpg", ".jpeg", ".png", ".webp", ".gif")))
    missing = used - still
    assert not missing, u"新页面没渲出来，老页面引用的图却已经没了：%s" % sorted(missing)[:3]


def test_a_failed_gate_keeps_the_images_the_published_page_uses(stubs, monkeypatch):
    """闸门比渲染更靠后，所以它更危险：新页面已经落盘，旧图在这一步之前就被当
    孤儿清了，而索引只在闸门全绿后才换到新页面——入口页还指着那张已经断图的旧页面。

    W-145 之前这条要跨日期才看得见（同一天重做会原地覆盖同一个文件名，旧页根本不存在）。
    一篇只留一页之后，兜底换成了换名协议：**闸门没过就不换名**，`.pending` 不是产物。
    判的性质没变（"索引指着的那一页必须打得开、图必须还在"），变的只是它靠什么成立。
    """
    assert G.main([TOPIC, "--workers", "2"]) == 0
    out = os.path.join(str(stubs["out"]), TOPIC)
    page = os.path.join(out, "%s.html" % TOPIC)
    assert os.path.isfile(page), u"第一轮没产出页面，这条测试会空转"
    before = io.open(page, encoding="utf-8").read()
    used = set(re.findall(r'src="images/([^"]+)"', before))
    assert used, u"页面里没有配图，断言撑不起来"

    monkeypatch.setattr(G, "verify", lambda *a, **k: 1)
    assert G.main([TOPIC, "--workers", "2", "--redo-images"]) != 0, \
        u"闸门替身没生效，这条测试会空转"
    assert io.open(page, encoding="utf-8").read() == before, \
        u"闸门没过，已发布页却被换掉了——那 .pending 这道关卡就是假的"
    still = set(f for f in os.listdir(os.path.join(out, "images"))
                if f.lower().endswith((".jpg", ".jpeg", ".png", ".webp", ".gif")))
    missing = used - still
    assert not missing, \
        u"闸门没过、索引还指着这一页，它引用的图却没了：%s" % sorted(missing)[:3]


def test_redoing_a_section_leaves_no_orphan_images(stubs, tmp_path):
    """重做一章会把那章的 images 清空再抓新的，旧文件却留在磁盘上——
    G-03 的"孤儿图片：产物未引用"就是判这个的，于是 `--only` 一用就必挂。
    这条不是为了让测试变绿而加的：它防的是"我们自己造的脏文件让闸门误报"，
    那种红没人愿意再看第二眼，久而久之闸门就没人信了。"""
    assert G.main([TOPIC, "--workers", "2"]) == 0
    target = stubs["llm"][0]
    assert G.main([TOPIC, "--only", target, "--workers", "1"]) == 0, \
        u"重做一章之后闸门没过——多半是旧图成了没人引用的孤儿"

    img_dir = os.path.join(str(stubs["out"]), TOPIC, "images")
    data_path = os.path.join(str(stubs["out"]), TOPIC, "data.json")
    data = json.load(io.open(data_path, encoding="utf-8"))
    referenced = set(os.path.basename(im["file"])
                     for s in data["sections"] for im in (s.get("images") or []))
    on_disk = set(f for f in os.listdir(img_dir)
                  if f.lower().endswith((".jpg", ".jpeg", ".png", ".webp", ".gif")))
    assert on_disk == referenced, u"磁盘上留着没人引用的图：%s" % sorted(on_disk - referenced)


def test_only_redoes_a_section_that_already_exists(stubs):
    """`--only` 的帮助写着"只重做某一节"，AGENTS.md 也这么教。
    但 todo 的过滤条件是 `s.id not in done`——已经存在的章节永远不会被重做，
    这个旗标实际上只能"补缺"。今天拿它去重写一段被 schema 拒掉的正文，
    结果一个字没动、还照样跑完配图与闸门，看起来像成功了一样。"""
    assert G.main([TOPIC, "--workers", "2"]) == 0
    first = list(stubs["llm"])
    assert len(first) > 1, "夹具没写满整篇，这个测试就没有对照"
    target = first[0]
    del stubs["llm"][:]

    assert G.main([TOPIC, "--only", target, "--workers", "1"]) == 0
    assert stubs["llm"] == [target], \
        u"--only %s 应当只重做这一章，实际调了：%s" % (target, stubs["llm"])


def test_only_with_unknown_section_id_fails_loudly(stubs, tmp_path, monkeypatch, capsys):
    """`--only` 打错一个字母就静默什么都不做：todo 过滤后为空，
    于是日志照跑、配图照抓、退出码只反映后面的闸门——
    你以为重做了那一章，其实一个字没动（今天真踩了一次 --only sections-3，
    真实 id 是 complications）。拼错的参数必须当场报错，而不是假装成功。"""
    assert G.main([TOPIC, "--workers", "2"]) == 0
    data_path = os.path.join(str(stubs["out"]), TOPIC, "data.json")
    before = io.open(data_path, encoding="utf-8").read()

    calls = []
    monkeypatch.setattr(images_mod, "collect",
                        lambda *a, **k: calls.append(1) or [])
    rc = G.main([TOPIC, "--only", "sections-3", "--workers", "2"])
    assert rc == 2, u"未知章节 id 却返回 %s，等于告诉调用者「已经跑过了」" % rc
    err = capsys.readouterr().err
    assert "history" in err, u"报错里没列出可用的章节 id：%s" % err[:200]
    assert not calls, u"参数都错了还去抓图：%s" % calls
    assert io.open(data_path, encoding="utf-8").read() == before, "错参数还改了产物"


def _jpg():
    """一张能过 accept_image 的真字节：640x400 + 120KB。小于 min_bytes 的假字节会让两档都拿不到图，那条测试就成了空转——它测不到"放宽档会不会放进来"。"""
    from test_images import jpg_bytes
    return jpg_bytes() + bytes(90000)


def _offsubject_cands(n=6):
    """点名"机芯"却不点名"积家"的一页候选——正是放宽档会收、闸门档会拒的形状。
    09-22 实测引擎对 `积家 机芯` 回的是汉语字典里「积」字的笔顺页，
    而降粒度重试拆出的裸词「机芯」能召回到 ETA 机芯对比文这类**别人的**页面。"""
    return [images_mod.Candidate(murl="https://watch.example/%d.jpg" % i,
                                 turl="https://ts.example/%d" % i,
                                 purl="https://watch.example/page%d" % i,
                                 title=u"双陀飞轮机芯拆解与Duomètre结构解析 %d" % i)
            for i in range(n)]


def test_an_off_subject_answer_does_not_unlock_the_relaxed_tier(tmp_path, monkeypatch):
    """引擎回的全是不点名领域的页面时，放宽主语要求等于**保证跑题**：
    一张点名的图都没有，还非要填满这一章，填进来的必是别人的图。
    百达翡丽那两张（常柴柴油机、重型工作台）就是这个形状进来的。
    这一轮宁可让章空着——空章过不了 G-03，但脏图会直接上架骗读者。"""
    import outline as outline_lib
    cfg = outline_lib.load_for_topic(u"积家", root=G.ROOT)
    sec = [s for s in cfg.sections if s.id == "movements"][0]
    data = {"topic": u"积家", "sources": [],
            "sections": [{"id": sec.id, "title": sec.title, "anchor": sec.anchor,
                          "blocks": [{"type": "prose", "heading": sec.title,
                                      "text": u"正文" * 60}], "images": []}]}
    out = str(tmp_path / u"积家")
    os.makedirs(os.path.join(out, "images"))
    monkeypatch.setattr(images_mod, "search",
                        lambda q, count=20, opener=None: _offsubject_cands())
    monkeypatch.setattr(images_mod, "download",
                        lambda url, timeout=25, opener=None: _jpg())
    lines = []
    monkeypatch.setattr(G, "log", lambda m=None: lines.append(str(m)))
    G.do_images(cfg, data, out)
    got = [im["file"] for s in data["sections"] for im in (s.get("images") or [])]
    assert not got, u"引擎答非所问却仍然放宽了主语要求，配进来 %s" % got[:2]
    assert any(u"答非所问" in L for L in lines),         u"日志必须说清为什么不放宽，否则看日志的人以为检索词还要再改：%s" % lines[-3:]
    stats = json.load(io.open(os.path.join(out, "images", "search-stats.json"),
                              encoding="utf-8"))
    assert any(v["offered"] and not v["named"] for v in stats.values()),         u"召回统计没落盘，下次还是分不出成因：%s" % list(stats.items())[:2]


def test_brand_word_is_tried_before_the_subject_gate_is_dropped(stubs, monkeypatch):
    """配图三档的顺序必须是"点名主语 > 品牌单词 > 放弃主语"。
    实测：积家篇 9 条检索词全灭时，"宾利"这个单词能召回 10 张里 8 张点名品牌的可用图；
    而直接放弃主语就会捞回"中国行政区划""圆糯米"那种东西。
    所以先试品牌单词，最后才放宽。
    品牌单词那一档内部的顺序另有实测：裸词档 10 张里摘掉 5 张，章节原词 16 张摘掉 3 张，
    所以**这一章自己的两词短语要排在全领域裸词前面**。"""
    seen = []

    def spy(queries, dest_dir, *a, **k):
        seen.append((list(queries), bool(k.get("subject"))))
        os.makedirs(os.path.join(dest_dir, "images"), exist_ok=True)
        return []

    monkeypatch.setattr(images_mod, "collect", spy)
    G.main([TOPIC, "--workers", "2", "--redo-images"])

    gated = [i for i, (q, has) in enumerate(seen)
             if has and u"咖啡" in [str(x).lower() for x in q]]
    ungated = [i for i, (q, has) in enumerate(seen) if not has]
    assert gated, u"没有一档是「搜品牌单词、仍要求点名主语」：%s" % seen[:3]
    assert not ungated or min(ungated) > min(gated), \
        u"放弃主语的那一档排在了品牌单词前面，会先捞脏图"
    phrase_first = [q for i, (q, has) in enumerate(seen)
                    if has and u"咖啡" in [str(x).lower() for x in q]
                    and str(q[0]).lower() != u"咖啡"]
    assert phrase_first, u"品牌单词档没有先问这一章自己的两词短语：%s" % seen[:4]


def test_the_relaxed_tier_carries_the_keyword_floor(stubs, monkeypatch):
    """三档的最后一档放弃"必须点名领域"，但不能连"这张图在讲本章"都不要了。
    百达翡丽 12 张跑题图全部是这一档收进来的，且关键词命中数都 ≤1
    （"中华万年历 app 下载"、"圆角和倒角-CSDN"、"重型工作台"）。
    下限的值归 images.RELAXED_MIN_HITS，这条测试只钉"放宽档必须带上它"——
    同一个规则写在两处而互相看不见，是这个仓库反复翻车的原因。"""
    seen = []

    def spy(queries, dest_dir, *a, **k):
        seen.append((bool(k.get("subject")), k.get("min_hits")))
        os.makedirs(os.path.join(dest_dir, "images"), exist_ok=True)
        return []

    monkeypatch.setattr(images_mod, "collect", spy)
    G.main([TOPIC, "--workers", "2"])
    relaxed = [hits for gated, hits in seen if not gated]
    assert relaxed, u"根本没跑到放宽那一档：%s" % seen[:3]
    assert all(hits == images_mod.RELAXED_MIN_HITS for hits in relaxed), \
        u"放宽档没带关键词下限：%s" % relaxed
    assert all(h in (None, 1) for gated, h in seen if gated), \
        u"点名档被误加了下限，会重演误杀真图那次翻车"


def test_section_images_keep_the_query_that_found_them(stubs, tmp_path):
    """每张配图要留着"它是被哪条检索词搜出来的"。
    没有这个字段，一张跑题图就分不清是"检索词没点名领域"（改大纲能救）
    还是"点名了但 Bing 就给脏页"（改规则也没用）——
    今天判百达翡丽那 12 张跑题图时只能靠"哪个领域是哪段代码跑的"去推。
    collect() 本来就返回 query，是 do_images 写记录时把字段列表写死丢掉了。"""
    assert G.main([TOPIC, "--workers", "2"]) == 0
    data_path = os.path.join(str(stubs["out"]), TOPIC, "data.json")
    data = json.load(io.open(data_path, encoding="utf-8"))
    imgs = [im for s in data["sections"] for im in (s.get("images") or [])]
    assert imgs, "夹具没产出图，这个测试就没有对照"
    missing = [im["file"] for im in imgs if not (im.get("query") or "").strip()]
    assert not missing, u"这些配图没记来路：%s" % missing[:3]
    assert not G._schema_errors(data), u"加了 query 之后 data.json 不合 schema"
    man = json.load(io.open(os.path.join(str(stubs["out"]), TOPIC, "images",
                                         "manifest.json"), encoding="utf-8"))
    assert all((e.get("query") or "").strip() for e in man), "manifest 也该带来路"


def test_redo_images_persists_the_clear_before_recollecting(stubs, monkeypatch):
    """重做配图失败之后，data.json 里每一条引用都必须在磁盘上找得到文件。

    名字里的 persists the clear 是 W-85 之前的说法（那时真的先删图、先把空引用落盘）。
    现在的设计正好相反：清空只动内存、旧图一张不删，恢复靠 finally 里的逐章退回。
    名字留着是因为 HANDOVER 与 memo 里各有一条 09-20 的证据指针指着它——
    台账要能点开，比命名好看重要。
    """
    assert G.main([TOPIC, "--workers", "2"]) == 0
    data_path = os.path.join(str(stubs["out"]), TOPIC, "data.json")

    def boom(*a, **k):
        raise RuntimeError("检索挂了")

    monkeypatch.setattr(images_mod, "collect", boom)
    with pytest.raises(RuntimeError):
        G.main([TOPIC, "--workers", "2", "--redo-images"])

    data = json.load(io.open(data_path, encoding="utf-8"))
    img_dir = os.path.join(str(stubs["out"]), TOPIC)   # im["file"] 自带 images/ 前缀
    refs = [im["file"] for s in data["sections"] for im in (s.get("images") or [])]
    assert refs, "重做失败后把整页配图都丢了——回滚没生效"
    for f in refs:
        assert os.path.isfile(os.path.join(img_dir, f.replace("/", os.sep))), (
            u"data.json 还引用着一个磁盘上已经不存在的文件：%s" % f)


def test_save_keeps_the_last_good_data_when_a_write_fails(tmp_path):
    """data.json 是断点续跑的唯一凭据，所以写它必须要么全成要么不动。
    旧实现 io.open(path, "w") 先截断再序列化：进程被杀或中途抛错，
    文件就成了半截 JSON，前面十几章的研究成果一起报废——
    而防住这个只要一次 os.replace。"""
    p = str(tmp_path / "data.json")
    G._save(p, {"sections": [{"id": "timeline"}]})
    good = json.load(io.open(p, encoding="utf-8"))

    with pytest.raises(TypeError):
        G._save(p, {"bad": set([1])})          # set 无法 JSON 序列化

    assert json.load(io.open(p, encoding="utf-8")) == good, "失败的写覆盖了上一份好数据"
    assert os.listdir(str(tmp_path)) == ["data.json"], "临时文件没清掉"
