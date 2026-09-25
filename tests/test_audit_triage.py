# -*- coding: utf-8 -*-
"""W-95 的回归测试：体检器的分诊必须能区分「大纲没点名」与「大纲点名了但没搜到」。
写这个测试不用真大纲——判据只依赖 cfg 的形状，用假 cfg 才能把两个分支各自钉住。
"""
import os

import audit_images as A
import outline as O
from types import SimpleNamespace

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _cfg(pairs):
    """pairs = [(section_id, [image_queries])]。用真的 Section 构造器造大纲，
    这样字段名一改，这条测试就会响，而不是悄悄测了个假对象。"""
    secs = [O.Section({"id": sid, "title": sid, "angle": u"角度",
                       "block_types": ["prose"], "image_queries": qs,
                       "fact_prompts": [u"某条事实"]}, i)
            for i, (sid, qs) in enumerate(pairs)]
    return SimpleNamespace(topic=u"积家", aliases=[u"Jaeger"], sections=secs)


def _data(sid, caption, query):
    return {"sections": [{
        "id": sid, "title": sid, "blocks": [],
        "images": [{"file": "images/x.jpg", "caption": caption, "alt": caption,
                    "source_page": "https://other.example/1",
                    "width": 1200, "height": 800, "query": query}],
    }]}


def test_a_naming_outline_that_came_back_empty_is_not_blamed_on_the_outline():
    """大纲这条章**已经**给了点名领域的检索词，图却还是没点名的——
    那是点名档空手、引擎把词拆成裸词之后从放宽档捞回来的，
    改大纲救不了它。09-22 实测：积家 27 条检索词全部点名之后，
    体检器仍报「8 张检索词可救」，把开发者的注意力往错方向带（W-95）。"""
    cfg = _cfg([("movements", [u"积家 机芯", u"积家 Duomètre"])])
    r = A.audit_data(cfg, _data("movements", u"某缝纫机图纸", u"机芯"))
    assert r["unnamed"] == ["images/x.jpg"], u"没点名的图本该被抓出来"
    assert not r["fixable"], u"大纲已经点名了，不该再算成「改大纲有救」：%s" % r["fixable"]
    assert [f for f, _ in r["starved"]] == ["images/x.jpg"], \
        u"应归入「点名档空手」：%s" % sorted(r)


def test_a_section_with_no_naming_query_is_still_fixable_by_the_outline():
    """反过来：这条脏图用的**就是大纲给过的原词**，而那个原词没点名领域——
    这才是真的改大纲有救。两个分支都要钉住，否则分诊只是换了个方向猜。"""
    cfg = _cfg([("history", [u"大钟 显示 装置", u"山谷 工坊 历史"])])
    r = A.audit_data(cfg, _data("history", u"某行政区划图", u"大钟 显示 装置"))
    assert [f for f, _ in r["fixable"]] == ["images/x.jpg"], \
        u"大纲给过的不点名原词应当算可救：%s" % sorted(r)
    assert not r["starved"]


def test_an_empty_chapter_is_blamed_on_the_engine_when_it_answered_off_subject():
    """空章有两种成因，处置完全相反：
    引擎答非所问（召回一堆但零条点名）→ 换时间重试；大纲没给对词 → 改 config。
    不分开就会拿着错误的结论去砍花过额度的章节（W-98 的岔口，09-22 实测）。"""
    cfg = _cfg([("movements", [u"积家 腕表 专柜"])])
    stats = {u"积家 腕表 专柜": {"offered": 34, "named": 0}}
    r = A.audit_data(cfg, {"sections": [{"id": "movements", "title": u"机芯",
                                         "blocks": [], "images": []}]},
                     search_stats=stats)
    causes = dict(r["empty_causes"])
    assert causes.get(u"机芯") == "engine", r["empty_causes"]
    assert not r["fixable"]


def test_an_empty_chapter_with_naming_offers_is_a_supply_problem_not_the_engine():
    """反过来：召回里有点名的页，图却还是没拿到（尺寸/评分/下载刷掉），
    这时报"引擎答非所问"就是冤枉引擎，真正该看的是供给质量。"""
    cfg = _cfg([("collections", [u"积家 大师系列"])])
    stats = {u"积家 大师系列": {"offered": 30, "named": 7}}
    r = A.audit_data(cfg, {"sections": [{"id": "collections", "title": u"系列",
                                         "blocks": [], "images": []}]},
                     search_stats=stats)
    assert dict(r["empty_causes"]).get(u"系列") == "supply", r["empty_causes"]


def test_an_empty_chapter_without_any_stats_is_reported_as_unknown_not_guessed():
    """没有统计就是没有统计。猜成"引擎问题"或"供给问题"都会把人支到错的方向上——
    这正是 W-95 那条「没有 query 不等于没点名」的同一个错误。"""
    cfg = _cfg([("prices", [u"积家 价格"])])
    r = A.audit_data(cfg, {"sections": [{"id": "prices", "title": u"价格",
                                         "blocks": [], "images": []}]},
                     search_stats={})
    assert dict(r["empty_causes"]).get(u"价格") == "unknown", r["empty_causes"]


def test_the_report_prints_why_a_chapter_is_empty_not_just_that_it_is():
    """报表是给人做决定看的。只报"空章 4"，人就会去猜"这个品牌没图"（W-98 三条路里
    有两条是砍章/下架）。所以每一章的成因必须打在行里。"""
    rows = [{"topic": u"积家", "total": 9, "unnamed": [], "empty": [u"机芯", u"价格"],
             "empty_causes": [(u"机芯", "engine"), (u"价格", "supply")],
             "fixable": [], "starved": [], "dirty": [], "unknown": [], "subject": set()}]
    buf = []
    A.report(rows, log=buf.append)
    line = chr(10).join(buf)
    assert u"引擎答非所问 1" in line, line
    assert u"供给 1" in line, line


def test_the_health_probe_calls_a_subject_naming_answer_healthy():
    """体检器说"健康"的时候必须真的是健康，否则它会成为下一个"永远为绿的闸门"。"""
    import bing_health as H
    rows = [(u"劳力士", u"劳力士 手表", 34, 34), (u"宾利", u"宾利 汽车", 25, 21)]
    assert H.verdict(rows)[0] == "healthy"


def test_the_health_probe_calls_an_all_off_subject_answer_dead():
    """09-22 23:40 的真实形状：召回很多，点名 0。"""
    import bing_health as H
    rows = [(u"积家", u"积家 机芯", 34, 0), (u"咖啡", u"咖啡 手冲", 35, 0)]
    state, why = H.verdict(rows)
    assert state == "dead"
    assert u"34" in why or u"69" in why, why


def test_the_health_probe_reports_partial_without_calling_it_healthy():
    import bing_health as H
    rows = [(u"劳力士", u"劳力士 手表", 34, 34), (u"积家", u"积家 机芯", 34, 0)]
    assert H.verdict(rows)[0] == "partial"


def test_wait_healthy_stops_polling_once_the_engine_is_usable():
    """`--wait-healthy` 的全部意义是"别在坏窗口里空跑几小时"。
    判据用注入的 probe，不碰网络——否则这条测试会变成一条慢且不稳的联网测试。"""
    import bing_health as H
    calls = []
    answers = [[(u"劳力士", u"q", 30, 0), (u"宾利", u"q", 30, 0)],   # dead
               [(u"劳力士", u"q", 30, 30), (u"宾利", u"q", 30, 28)]]  # healthy

    def probe():
        r = answers[min(len(calls), len(answers) - 1)]
        calls.append(1)
        return r

    assert H.wait_until_healthy(probe, sleep=lambda s: None, max_wait=9999) is True
    assert len(calls) == 2, u"第 2 次已经健康却还在轮询：%d 次" % len(calls)


def test_wait_healthy_gives_up_instead_of_looping_forever():
    import bing_health as H
    slept = []
    ok = H.wait_until_healthy(lambda: [(u"积家", u"q", 30, 0)],
                              sleep=slept.append, max_wait=600)
    assert ok is False, u"到点必须放弃并报告，不能让调用方永远等"
    assert sum(slept) >= 600, u"没按 max_wait 收口：%s" % slept


# -------------------------------------------------- W-114 按品牌的饿死判定

def test_topic_controls_ask_about_the_domain_being_generated():
    """控制词只有别的品牌，就会说"引擎健康"——而娇兰那 8 章照样一张图都拿不到。
    要判"现在能不能给**这个**领域跑图"，探针里必须有这个领域自己的词。"""
    import bing_health as H
    qs = [q for _t, q in H.topic_controls(u"娇兰", root=ROOT)]
    assert len(qs) >= 2, qs
    assert all(u"娇兰" in q or "guerlain" in q.lower() for q in qs), qs


def test_a_starved_brand_is_not_reported_as_a_bad_window():
    """09-23 实测（.probe/brand_probe.txt）：同一分钟
    兰蔻/古驰/爱马仕/香奈儿 香水 全部 召回 25–35 / 点名过半，
    而 娇兰 28/0、Guerlain 1/0、娇兰 香水 35/0。
    别的品牌都活、只有它全灭 = 品牌饿死，不是坏窗口——等下去等不来。
    同一个"零点名"形状在引擎整体死掉时只是坏窗口，所以判据必须是比较，不能只看自己。"""
    import bing_health as H
    glob = [(u"兰蔻", u"兰蔻 香水", 35, 35), (u"古驰", u"古驰 香水", 25, 25)]
    own = [(u"娇兰", u"娇兰", 28, 0), (u"娇兰", u"娇兰 香水", 35, 0)]
    assert H.verdict(glob)[0] == "healthy"
    assert H.compare(glob, own)[0] == "starved"
    all_dead = [(u"积家", u"积家 机芯", 34, 0), (u"咖啡", u"咖啡 手冲", 35, 0)]
    assert H.compare(all_dead, own)[0] == "window"


def test_a_brand_with_no_answer_now_is_not_written_off_for_good():
    """参照组活着、这个领域零点名 = 此刻搜不到，但**不等于**永远搜不到：
    13:00 我用 娇兰 / 娇兰 创始人 / Guerlain 香水瓶 1853 探到 0 点名，
    13:06 开跑的那轮却补上了 6 章。所以这里既不能放行，也不能收工——
    只能继续等到 max_wait，让"换时间"这条唯一已验证有效的杠杆留着。"""
    import bing_health as H
    healthy_glob = lambda: [(u"劳力士", u"劳力士 手表", 35, 35)]
    starved_own = lambda: [(u"娇兰", u"娇兰", 28, 0)]
    slept = []
    ok = H.wait_until_healthy(healthy_glob, sleep=slept.append, max_wait=600,
                              topic_probe=starved_own, topic=u"娇兰")
    assert ok is False, u"本领域零点名却放行，等于让配图阶段空跑几小时"
    assert sum(slept) >= 600, u"不该提前放弃等待：%s" % slept


def test_the_domain_naming_its_own_subject_is_the_go_signal():
    """闸门要看的是"我要跑的那个品牌现在点得到名吗"，不是别的品牌。
    13:06 实测：参照组里 积家/咖啡/LV 三条全灭（整体 partial），
    同一时刻 娇兰 自己的检索词 33/35 点名，那一轮就从空章 8 降到 2。
    按旧的"整体健康才放行"就会白等一个其实能干活的时间片。"""
    import bing_health as H
    dead_glob = lambda: [(u"积家", u"积家 机芯", 35, 0), (u"咖啡", u"咖啡 手冲", 35, 0)]
    good_own = lambda: [(u"娇兰", u"Guerlain Shalimar", 35, 33)]
    slept = []
    ok = H.wait_until_healthy(dead_glob, sleep=slept.append, max_wait=7200,
                              topic_probe=good_own, topic=u"娇兰")
    assert ok is True, u"本领域点得到名却还在等，是把别的品牌的病算在它头上"
    assert slept == [], u"放行不该花掉任何一个轮询间隔：%s" % slept


def test_the_topic_probe_spreads_across_chapters_not_one_chapter():
    """探针要问的是「这篇现在能不能配图」，所以得各章取一条。
    全取自第一章会两种错法：那一章恰好词形不好 → 整篇被判不能跑；
    那一章恰好好 → 其余十章的坑一个没探到。
    领域名本身也不该当探针：`Muse产业逻辑` 是个短语，图搜里没有这种东西。"""
    import bing_health as H
    qs = [q for _t, q in H.topic_controls(u"Muse产业逻辑", root=ROOT)]
    assert len(qs) >= 3, qs
    assert u"muse产业逻辑" not in [q.lower() for q in qs], \
        u"拿领域全名当探针，必然零点名：%s" % qs
    第一章 = u"Meta 发布会 现场"
    assert sum(1 for q in qs if q == 第一章) <= 1, u"三条都取自第一章：%s" % qs
