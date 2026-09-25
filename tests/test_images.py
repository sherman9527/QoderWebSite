# -*- coding: utf-8 -*-
"""配图管线（specs/image-sourcing）。用录制的 Bing 页面做 fixture，不打网络。"""
import io
import json
import os
import struct

import pytest

import images as I

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

FIX = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")


@pytest.fixture
def bing_html():
    return io.open(os.path.join(FIX, "bing_images.html"), encoding="utf-8",
                   errors="ignore").read()


@pytest.fixture
def bar(quality_bar):
    return quality_bar["images"]


def test_parse_real_bing_page(bing_html):
    cands = I.parse_bing(bing_html)
    assert len(cands) >= 10, "录制的页面应能解析出足量候选，实际 %d" % len(cands)
    assert all(c.murl or c.turl for c in cands)
    assert any(c.purl for c in cands), "解析不到来源页就无法人工复核"


def test_parse_tolerates_garbage():
    assert I.parse_bing("not html at all") == []
    assert I.parse_bing("") == []
    assert I.parse_bing('<div class="iusc" m="{坏 JSON">') == []


def test_search_url_carries_query_and_size_filter():
    u = I.search_url("咖啡 烘焙")
    assert "cn.bing.com" in u and "q=" in u and "imagesize-large" in u


# ------------------------------------------------------------------ 字节判定

def png_bytes(w, h):
    ihdr = struct.pack(">II", w, h)
    return (b"\x89PNG\r\n\x1a\n" + b"\x00\x00\x00\x0dIHDR" + ihdr
            + b"\x08\x06\x00\x00\x00" + b"\x00" * 20)


def jpg_bytes():
    body = b"\xff\xc0\x00\x11\x08\x01\x90\x02\x80\x03\x01\x22\x02\x00" + b"\x00" * 30000
    return b"\xff\xd8\xff\xe0" + b"\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00" + body + b"\xff\xd9"


def test_sniff_rejects_html_even_with_200():
    """反爬占位页会以 200 返回 HTML，必须按字节判失败。"""
    page = (b"<!DOCTYPE html><html><head><title>forbidden</title></head></html>")
    assert I.sniff(page) is None
    assert I.sniff(b"x" * 4) is None
    assert I.sniff(b"") is None


def test_sniff_accepts_real_formats():
    assert I.sniff(jpg_bytes()) == "jpg"
    assert I.sniff(png_bytes(800, 600)) == "png"
    assert I.sniff(b"GIF89a" + b"\x00" * 20) == "gif"


def test_dimensions_read_from_bytes():
    assert I.dimensions(png_bytes(800, 600), "png") == (800, 600)
    w, h = I.dimensions(jpg_bytes(), "jpg")
    assert (w, h) == (640, 400)


def test_accept_rejects_small_width_and_tiny_bytes(bar):
    ok, fmt, w, h, why = I.accept_image(png_bytes(320, 240), bar)
    assert not ok and "宽度" in why

    small = png_bytes(1200, 900)
    ok, fmt, w, h, why = I.accept_image(small, bar)
    assert not ok and "体积" in why

    big = jpg_bytes() + b"\x00" * 60000
    ok, fmt, w, h, why = I.accept_image(big, bar)
    assert ok, why


def test_http_error_body_is_still_rescued():
    """实测：Bing 缩略图端点返回 404，但响应体是合法 JPEG。

    所以取字节这层必须把错误体带回来交给 sniff 判定，
    不能因为状态码就判死——也不能反过来只看状态码。
    """
    import urllib.error

    body = jpg_bytes() + bytes(60000)
    err = urllib.error.HTTPError("https://ts4.mm.bing.net/th", 404, "Not Found", None,
                                 io.BytesIO(body))

    orig = I.urllib.request.urlopen

    def fake(*a, **k):
        raise err

    I.urllib.request.urlopen = fake
    try:
        data = I._urlopen_bytes("https://ts4.mm.bing.net/th?id=x")
    finally:
        I.urllib.request.urlopen = orig
    assert data and I.sniff(data) == "jpg"


def test_download_swallows_hard_failures():
    """彻底取不到时返回 None，让上层换下一个候选，而不是整页崩。"""
    def boom(url, timeout=25):
        raise OSError("connection reset")
    assert I.download("https://x/y.jpg", opener=boom) is None


# ------------------------------------------------------------------ 打分

def _cand(title, purl="https://example.com/a", murl="https://cdn/x.jpg"):
    return I.Candidate(murl=murl, turl="https://ts/x", purl=purl, title=title)


def _distinct(url):
    """每张图的字节必须不同：collect 按内容哈希认回已落盘的文件，
    夹具要是返回同一份字节，第二轮的"重复"就被哈希挡掉了，
    这条测试会去测一个根本不存在的形状。"""
    pad = 90000 + (sum(ord(c) for c in url) % 5000)
    return jpg_bytes() + bytes(pad)


def test_a_candidate_that_cannot_pass_is_never_downloaded(tmp_path, bar, monkeypatch):
    """score() 里所有 -999 的判据只看标题与 URL，像素从不参与否决
    （尺寸/体积只影响加分）。所以这些候选**不该先下载几 MB 再被丢掉**。
    09-23 实测代价：坏窗口里一章 30 条候选有 28 条死在这几条上，
    娇兰篇的配图阶段因此跑了 4 小时只拿到 2 张图（2017 次丢弃）。"""
    junk = [_cand(u"咖啡 高清图 壁纸 下载", murl="https://699pic.com/x/1.jpg",
                  purl="https://699pic.com/tupian-1.html")]        # 素材站
    junk += [_cand(u"某行政区划图", murl="https://other.example/2.jpg",
                   purl="https://other.example/2")]                 # 不点名领域
    good = [_cand(u"咖啡 手冲 实操", murl="https://coffee.example/3.jpg",
                  purl="https://coffee.example/3")]
    monkeypatch.setattr(I, "search", lambda q, count=20, opener=None: junk + good)
    fetched = []

    def dl(url, timeout=25, opener=None):
        fetched.append(url)
        return jpg_bytes() + bytes(90000)

    got = I.collect([u"咖啡 手冲"], str(tmp_path), bar, keywords=[u"咖啡", u"手冲"],
                    subject={u"咖啡"}, downloader=dl)
    assert len(got) == 1, u"该拿到的那张没拿到：%s" % [g["file"] for g in got]
    assert fetched == ["https://coffee.example/3.jpg"],         u"明知会被否决的候选还是去下载了：%s" % fetched


def test_one_source_page_does_not_become_the_pages_visual_identity(tmp_path, bar, monkeypatch):
    """09-23 全站点联络表肉眼抽查抓到的：浪琴有 5 个章节的图来自同一个购表作业相册页，
    爱马仕 4 章、LV 3 章同源于一个页面。全站点 211 张里 17 个来源页跨章复用。
    同一个页面翻出来的照片风格、机位、水印都一样，读者连着看到就是"这图怎么又出现一次"。

    判据要 crisp：按**来源页 URL** 数，不用感知哈希——8×8 aHash 在汉明距离 6 以内
    会把"两张不同的黑白人像"也算成重复（劳斯莱斯 Charles Rolls vs 戴姆勒那对就是这样），
    那种阈值当闸门就是给肉眼找麻烦。
    """
    same = [_cand(u'咖啡 手冲 步骤 图 %d' % i, murl="https://cdn.same/%d.jpg" % i,
                  purl="https://gallery.example/one") for i in range(6)]
    other = [_cand(u'咖啡 烘焙 场景 %d' % i, murl="https://cdn/other/%d.jpg" % i,
                   purl="https://gallery.example/two") for i in range(3)]

    def fake_search(q, count=20, opener=None):
        return list(same) + list(other)

    monkeypatch.setattr(I, "search", fake_search)
    used = {}
    first = I.collect([u'咖啡 手冲'], str(tmp_path), bar, keywords=[u'咖啡', u'手冲'],
                      subject={u'咖啡'}, max_per_source_page=2, used_pages=used,
                      downloader=lambda url, timeout=25, opener=None: _distinct(url))
    second = I.collect([u'咖啡 烘焙'], str(tmp_path), bar, keywords=[u'咖啡', u'烘焙'],
                       subject={u'咖啡'}, max_per_source_page=2, used_pages=used,
                       downloader=lambda url, timeout=25, opener=None: _distinct(url))
    assert len(first) == 2, u"第一轮该拿 2 张：%s" % len(first)
    assert second, u"第二个章节本该从另一个来源页拿到图，却空手"
    assert {g["source_page"] for g in second} == {"https://gallery.example/two"},         u"第二个章节还在从已经用满（2 张）的来源页拿图：%s" %         [g["source_page"] for g in second]


def test_fallback_tries_the_reversed_word_order(tmp_path, bar, monkeypatch):
    """09-23 实测（每组重复四次，全部稳定复现，不是抖动）：

        咖啡 手冲   点名 [0,0,0,0]      手冲 咖啡   点名 [35,35,35,35]
        咖啡 烘焙   点名 [35,35,35,35]  烘焙 咖啡   点名 [0,0,0,0]

    同一个引擎、同一批词，只是换了顺序，结果从"整页不相干"变成"整页点名领域"。
    方向没有规律（既不是主语在前也不是主语在后），所以没法靠改写大纲一次做对——
    但**换序是零成本的第二种形态**，值得在降粒度之前先试一次。
    """
    good = [_cand(u'手冲 咖啡 教程 步骤', murl="https://cdn/b.jpg", purl="https://coffee.example/1")]
    tried = []

    def fake_search(q, count=20, opener=None):
        tried.append(q)
        return list(good) if q == u'手冲 咖啡' else []

    monkeypatch.setattr(I, "search", fake_search)
    got = I.collect([u'咖啡 手冲'], str(tmp_path), bar, keywords=[u'咖啡', u'手冲'],
                    subject={u'咖啡'},
                    downloader=lambda url, timeout=25, opener=None: _distinct(url))
    assert u'手冲 咖啡' in tried, u"没试过换序形态：%s" % tried[:8]
    assert got, u"换序之后明明有点名领域的结果，却没拿到图：%s" % tried[:8]


def test_a_generic_infrastructure_abbreviation_is_never_a_subject_name(tmp_path):
    """主语闸门允许两三个字母的 ASCII 词按"整词"匹配（LV 篇必须这样才收得下
    "LV Monogram 手袋"）。但**整词的边界只挡拉丁字母与数字，不挡中文**，
    所以 `ai` 会命中 "AI创作图…壁纸" 与 "…-ai格式-千图网"，
    `arm` 会命中任何写了 "arm" 的页面。
    09-25 实测这不是孤例：AI制药 的主语集里有裸 `ai`，AI眼镜 有 `ai/ar1/jbd`，
    大模型 有 `llm/gpt/tpu/glm`，Muse 甚至有 `kvm/asn/nat/amd/arm/aws`——
    那些是基础设施缩写，是从 fact_prompts 混进 aliases 的**章节词**，不是主语。
    后果是实打实的：AI制药 篇 `实验室 自动化 液体处理` 召到的两张"点名"图，
    全是千图网的免抠素材，只因为标题里有 "ai格式"。
    """
    import outline as O

    class Cfg:
        topic = u"AI制药"
        aliases = [u"AI 制药", u"AlphaFold", u"英矽智能", u"ARM", u"NAT", u"KVM"]
        sections = []

    subj = I.subject_tokens(Cfg())
    for bad in (u"ai", u"arm", u"nat", u"kvm"):
        assert bad not in subj, u"%s 不该当主语名：%s" % (bad, u"、".join(subj))
    # 真正的品牌词必须留下——收紧不能把闸门焊死
    for good in (u"alphafold", u"英矽智能"):
        assert good in subj, u"%s 被误删：%s" % (good, u"、".join(subj))


def test_a_multiword_latin_product_name_is_never_reversed(tmp_path, bar, monkeypatch):
    """换序那条重试**只有两个中文词的实测依据**（`咖啡 手冲`↔`手冲 咖啡`，方向无规律）。
    三个词的拉丁产品名反过来不是"换个问法"，是另一个问题：09-24 骁龙笔电篇
    `Snapdragon X Elite` 降粒度时问出了 `Elite X Snapdragon`，Bing 就老实去找 "Elite"，
    配回来一张留学机构 logo、一张模特大赛舞台照、一张游戏截图——三张都"点名"，
    因为 alias 里有 `Snapdragon X`，而标题里真有这几个字。"""
    tried = []

    def fake_search(q, count=20, opener=None):
        tried.append(q)
        return []

    monkeypatch.setattr(I, "search", fake_search)
    I.collect([u'Snapdragon X Elite'], str(tmp_path), bar,
              keywords=[u'骁龙笔电'], subject={u'snapdragon x elite'},
              downloader=lambda url, timeout=25, opener=None: _distinct(url))
    assert u'Elite X Snapdragon' not in tried, \
        u"产品名被整个倒装了，这是在搜 Elite：%s" % (tried[:10],)


def test_a_multiword_latin_product_name_is_never_split_into_single_words(tmp_path, bar, monkeypatch):
    """换序与降粒度这两条重试，**实测依据都是两个词的中文短语**
    （`咖啡 手冲`↔`手冲 咖啡`；`Attention Is All You Need 论文` 拆词时有 STOP_TOKENS 兜着）。
    纯拉丁的产品名不适用：`Snapdragon X Elite` 拆出的 `Elite`、`Plus` 是通用英文词，
    09-24 实测配回来的是商标查询页（aiqicha 的 "Elite" 注册商标）与
    Pixabay 的加号素材图——都"点名"，因为标题里真有那几个字。"""
    tried = []

    def fake_search(q, count=20, opener=None):
        tried.append(q)
        return []

    monkeypatch.setattr(I, "search", fake_search)
    I.collect([u'Snapdragon X Elite'], str(tmp_path), bar,
              keywords=[u'骁龙笔电'], subject={u'snapdragon x elite'},
              downloader=lambda url, timeout=25, opener=None: _distinct(url))
    for q in tried:
        assert q.strip().lower() not in (u'elite', u'plus', u'snapdragon'), \
            u"产品名被拆成通用英文单词单独去搜了：%s" % (tried[:10],)


def test_granularity_fallback_never_turns_an_english_stopword_into_a_query(tmp_path, bar, monkeypatch):
    """降粒度重试把 `Attention Is All You Need 论文` 逐词拆开时，
    Is / All / You / Need 这些虚词也会各自变成一次检索请求。
    09-22 实测代价：大模型篇 training 一章打了 44 次检索，其中十几次的检索词
    就是 "You"、"Need" 这种词，Bing 回的是《The Hate U Give》的电影海报与语录站——
    每次都是一个 HTTP 往返加一轮下载，预算（4×词数）全烧在噪声上，一章磨了 30 分钟。
    虚词不携带任何检索信号，这是结构事实，不是给某个样本调参。"""
    tried = []

    def fake_search(q, count=20, opener=None):
        tried.append(q)
        return []

    monkeypatch.setattr(I, "search", fake_search)
    I.collect([u"Attention Is All You Need 论文"], str(tmp_path), bar,
              keywords=[u"论文"], subject={u"大模型"})
    bare = {q for q in tried if q.strip().lower() in
            {"is", "all", "you", "need", "the", "of", "and", "a", "in", "to"}}
    assert not bare, u"虚词被当成检索词发出去了：%s" % sorted(bare)
    assert any(u"论文" in q for q in tried), u"实词该被试过：%s" % tried[:6]
    assert any("Attention" in q for q in tried), u"实词该被试过：%s" % tried[:6]


def test_granularity_fallback_keeps_the_subject_word(tmp_path, bar, monkeypatch):
    """降粒度重试（实测多词查询常还回一整页垃圾，必须拆开重查）不能降成裸词。
    "也门""起源"这种单词搜回来的页面必然不提领域本身，
    于是主语那一档结构上永远满足不了——两级机制互相打架：
    咖啡篇第一章 6 条查询全灭，一张图都没取到。"""
    searched = []
    good = jpg_bytes() + bytes(90000)

    def fake_search(q, count=20, opener=None):
        searched.append(q)
        if len(str(q).split()) > 2:
            return []          # 多词整串：实测 Bing 常还回一整页垃圾
        if u"咖啡" not in q:
            return []          # 裸词不点名主语：召回来的全是别的主题
        return [_cand(u"咖啡樱桃采摘现场", murl="https://cdn/g", purl="https://a.example/g")]

    monkeypatch.setattr(I, "search", fake_search)
    got = I.collect([u"起源 埃塞俄比亚 咖啡樱桃"], str(tmp_path), bar,
                    keywords=[u"咖啡", u"起源"], subject=(u"咖啡",),
                    downloader=lambda url, timeout=25, opener=None:
                    good if url.endswith("/g") else None,
                    log=lambda m: None)
    assert u"咖啡 起源" in searched, u"降级查询把主语丢了：%s" % searched
    assert got, u"点名主语的降级重试没能让这一章拿到图：%s" % searched


def test_granularity_fallback_also_tries_the_bare_token(tmp_path, bar, monkeypatch):
    """补主语和降粒度是两股反向的力：实测咖啡篇"磨豆机 咖啡"只召回 1 条候选，
    而单词"咖啡机"召回 35 条、其中 30 条可用——Bing CN 对多词中文查询经常召不回东西。
    把降级词一律补成"咖啡 磨豆机"就等于把查询重新变回那个查不到东西的形态。
    所以两种形态都要试：先点名主语的（准），再裸词（广）——
    裸词搜回来的候选照样要过主语闸门，精度并没有被放弃。"""
    searched = []

    def fake_search(q, count=20, opener=None):
        searched.append(q)
        # 只有裸词这一形态召得回真图
        if q != u"磨豆机":
            return []
        return [_cand(u"手摇咖啡磨豆机 锥刀 特写", murl="https://cdn/g", purl="https://a.example/g")]

    monkeypatch.setattr(I, "search", fake_search)
    got = I.collect([u"磨豆机 咖啡 刀盘"], str(tmp_path), bar,
                    keywords=[u"咖啡", u"磨豆机"], subject=(u"咖啡",),
                    downloader=lambda url, timeout=25, opener=None:
                    (jpg_bytes() + bytes(90000)) if url.endswith("/g") else None,
                    log=lambda m: None)
    assert u"磨豆机" in searched, u"没试过裸词形态：%s" % searched
    assert got, u"裸词召回的相关图没能入库：%s" % searched


def test_ensure_subject_does_not_push_a_query_past_three_tokens():
    """补主语是为了提精度，但 Bing CN 的召回随词数崩塌：
    实测 "LV Monogram"→35 条、"路易威登 手袋"→35 条，
    而 "路易威登 LV Monogram 花纹 细节"→1 条（还是印尼的工程机械壁纸）。
    LV 篇 22 张图被重做成 1 张、10 章空掉，就是把每条检索词都拼长了 1 个词。
    所以只在补完仍 ≤3 个词时补；本来就长的检索词交给降粒度那条路去召回。"""
    subj = (u"路易威登", u"vuitton")
    assert I.ensure_subject(u"手袋 老花", subj) == u"路易威登 手袋 老花"
    long_q = u"Monogram 花纹 细节 特写"
    assert I.ensure_subject(long_q, subj) == long_q, u"4 词的检索词不该再被拼长"
    assert I.ensure_subject(u"路易威登 古董 旅行箱", subj) == u"路易威登 古董 旅行箱"


def test_short_latin_abbreviation_matches_as_a_word_not_a_substring():
    """LV 篇两个方向都翻过车："lv" 当子串会命中 involve / resolve，
    等于什么图都算点名；干脆不认 "lv" 又把真图全判跑题——
    中文图片标题里最常见的写法就是 "LV Monogram 手袋"，
    只认"路易威登/vuitton"时 22 张图重做成 1 张、10 章空掉。
    所以短 ASCII 主语按整词匹配，其余按子串；补进查询的仍必须是全名。"""
    import outline as O
    cfg = O.load_for_topic(u"LV", root=ROOT)
    subj = I.subject_tokens(cfg)
    assert u"lv" in subj, u"缩写得先进主语集合，才谈怎么匹配：%s" % (subj,)
    assert I.names_subject(u"lv monogram 手袋 老花细节", subj), u"真图被判跑题"
    assert I.names_subject(u"路易威登 speedy 评测", subj), u"中文全称必须算点名"
    assert not I.names_subject(u"how to resolve and involve customers", subj), \
        u"'lv' 当子串会把英文普通词算成点名"
    assert I.ensure_subject(u"手袋 老花", subj).startswith(u"路易威登"), \
        u"拿缩写去拼查询召不回中文页：%s" % I.ensure_subject(u"手袋 老花", subj)


def test_declared_aliases_join_the_subject_set(tmp_path, monkeypatch):
    """推导只能推出"在 ≥3 章检索词里露过面的拉丁词"，所以劳力士推不出 rolex、
    爱马仕推不出 hermes（各只出现在 2 章），降到 2 章又会把咖啡篇的"巴拿马"
    当主语收进来。品牌英文名本来就是领域数据，让它写在 config/topics/*.json 里。
    同时主语集合的第一位必须是领域名本身——ensure_subject 拿 subject[0] 去补查询，
    排到前面的若是别名，补出来的查询就不是人写的那种形态。"""
    import outline as O
    import types
    cfg = O.load_for_topic(u"劳力士", root=ROOT)
    bare = types.SimpleNamespace(topic=cfg.topic, sections=cfg.sections, aliases=[])
    derived = I.subject_tokens(bare)
    assert u"劳力士" in derived and u"rolex" not in derived, \
        u"这个测试的前提变了（不声明 aliases 时推导结果 %s）" % (derived,)
    monkeypatch.setattr(cfg, "aliases", [u"Rolex", u"  "], raising=False)
    subj = I.subject_tokens(cfg)
    assert u"rolex" in subj, u"声明的别名没进主语集合：%s" % (subj,)
    assert subj[0] == u"劳力士", u"主语第一位必须是领域名，否则补出来的查询形态不对：%s" % (subj,)
    assert u"" not in subj, u"空白名不能进主语集合（会让所有图都算点名）：%s" % (subj,)


def test_the_fallback_word_is_the_one_the_outline_actually_searches():
    """`primary_subject` 原本只看形状（第一个够长或含中文的词），于是它必然挑中领域名——
    13 个领域恰好都对，因为领域名本身就是最好的品牌词。
    `Muse` 与 `Muse产业逻辑` 不对：这两篇 11 章检索词里**一条都没写过裸 `muse`**，
    人写检索词时赌的是「月之暗面 / 阿里云 / 中际旭创」这些物体在图里会出现。
    覆盖率是这件事唯一免费的证据（不用联网、不用新字段），所以领域名没人搜过时换成它。
    只在覆盖率=0 时才换，是为了不惊动已经上架的 13 篇——换词会改变它们以后重做配图的结果。"""
    import outline as O
    for t in (u"Muse", u"Muse产业逻辑"):
        cfg = O.load_for_topic(t, root=ROOT)
        subj = I.subject_tokens(cfg)
        prim = I.primary_subject(subj)
        cov = [sum(1 for s in cfg.sections
                   if I.names_subject(u" ".join(map(str, s.image_queries or [])).lower(), [p]))
               for p in subj]
        assert cov[subj.index(prim)] > 0, \
            u"%s 的品牌词 %r 在本篇检索词里零覆盖，说明它不是这门生意的搜索词：%s" % (t, prim, subj[:6])
    # 领域名本来就在被搜的领域，一个字都不该动
    for t in (u"积家", u"咖啡", u"LV", u"娇兰", u"香奈儿"):
        cfg = O.load_for_topic(t, root=ROOT)
        assert I.primary_subject(I.subject_tokens(cfg)) == I.primary_subject(
            I._subject_tokens(cfg)), u"%s 的品牌词被这条规则改动了" % t


def test_the_brand_tier_prefers_this_chapters_own_two_word_phrase():
    """本篇 19 张里，裸词档带回来的 10 张有 5 张是我看联络表摘掉的（字标、优惠入口、
    钢板网广告），而章节原词 16 张只摘掉 3 张——**裸词的跑题率是章节词的 3 倍**。
    所以「这一章自己的词召不到图」时，先把它自己的两词短语再问一遍，
    而不是退到一个全领域共用的裸词上（那个词对这一章往往毫无关系）。"""
    subj = [u"中际旭创", u"润泽科技", u"muse"]
    assert I.brand_phrase([u"中际旭创 光模块 参数 对比"], subj) == u"中际旭创 光模块"
    assert I.brand_phrase([u"800G 硅光 芯片", u"润泽科技 数据中心 航拍"], subj) == u"润泽科技 数据中心"
    assert I.brand_phrase([u"电源 设备 参数 表 规格"], subj) is None, \
        u"章内没有点名主语的短语时不许硬造一个词"
    assert I.brand_phrase([], subj) is None


def test_a_domain_can_declare_the_brand_word_the_fallback_searches():
    """三档重试的第二档「品牌单词」搜的就是 `primary_subject`。
    `Muse产业逻辑` 拆完短语之后 primary 是 `muse`，而 muse 在中文图搜里是英国摇滚乐队
    与一家同名手术机器人——它们标题里确实有 muse，点名闸门会放行，只能靠人眼再逐张排除，
    这是让排除表一直长下去的循环。所以领域可以自己声明这一档（以及补检索词）用哪个名字。
    声明的词必须本来就在主语集合里，否则等于开后门让任意图进门。"""
    import types
    declared = types.SimpleNamespace(topic=u"Muse产业逻辑", sections=[], aliases=[u"Meta Muse"],
                                     image_primary_subject=u"Meta Muse")
    subj = I.subject_tokens(declared)
    assert I.primary_subject(subj) == u"meta muse", \
        u"声明了品牌词却没生效，第二档还会去搜 `muse`：%s" % (I.primary_subject(subj),)
    assert subj[0] == u"meta muse", u"补检索词用的是第 0 位，顺序没变等于没生效：%s" % (subj,)

    bare = types.SimpleNamespace(topic=u"Muse产业逻辑", sections=[], aliases=[u"Meta Muse"])
    assert I.primary_subject(I.subject_tokens(bare)) == u"muse", \
        u"没声明时行为必须不变（本篇 11 章里 5 章的第二档就是靠默认值）"

    ghost = types.SimpleNamespace(topic=u"Muse产业逻辑", sections=[], aliases=[u"Meta Muse"],
                                  image_primary_subject=u"不存在的名字")
    assert I.primary_subject(I.subject_tokens(ghost)) == u"muse", \
        u"声明一个不在主语集合里的词不该被接受"


def test_a_phrase_domain_name_is_split_before_it_reaches_a_query():
    """领域名可以是短语（`Muse产业逻辑`），但图搜里没有 "muse产业逻辑" 这种词。
    不拆的话它就是主语集合的第 0 位，也是 primary_subject 挑中的那一个——
    凡是没点名、又短于 3 词的检索词都会被拼上这个搜不动的短语，
    那一章的点名档等于白跑一轮。中英分界拆开后，拿去补查询的才是搜得动的名字。"""
    import types
    bare = types.SimpleNamespace(topic=u"Muse产业逻辑", sections=[], aliases=[])
    subj = I.subject_tokens(bare)
    assert u"muse产业逻辑" not in subj, u"短语整体不该当一个主语：%s" % (subj,)
    assert u"muse" in subj and u"产业逻辑" in subj, \
        u"拆开后两半都要留在主语集合里，点名匹配才不丢：%s" % (subj,)
    primary = I.primary_subject(subj)
    assert primary in (u"muse", u"产业逻辑"), \
        u"补查询用的主语必须搜得动，拿到 %r 这一章必然零点名" % (primary,)
    q = I.ensure_subject(u"深圳证券交易所 建筑", subj)
    assert u"muse产业逻辑" not in q, u"补出来的检索词里不许出现短语整体：%s" % (q,)
    assert I.subject_tokens(types.SimpleNamespace(
        topic=u"LV", sections=[], aliases=[])) == [u"lv"], u"纯拉丁名不该被拆坏"
    assert u"百达翡丽" in I.subject_tokens(types.SimpleNamespace(
        topic=u"百达翡丽", sections=[], aliases=[])), u"纯中文名不该被拆坏"


def test_outline_schema_permits_aliases():
    """`aliases` 要能写进大纲：topic_outline.schema.json 是 additionalProperties:false，
    没在 schema 里声明的字段会让大纲加载直接失败。"""
    import json as _json
    path = os.path.join(ROOT, "config", "topic_outline.schema.json")
    s = _json.loads(io.open(path, encoding="utf-8").read())
    assert "aliases" in s["properties"], "大纲 schema 不认 aliases，配置里写了也白写"
    assert s["properties"]["aliases"]["items"]["type"] == "string"
    assert "aliases" not in s.get("required", []), "aliases 必须是可选的"


def test_score_penalises_stock_illustration_sites():
    """"咖啡 意式浓缩" 实测会返回 58pic / 千图 的设计素材，必须扣分。"""
    kw = ["咖啡", "浓缩"]
    stock = _cand("科技元素AI咖啡插画矢量素材_58pic", purl="https://www.58pic.com/newpic/1.html")
    real = _cand("意大利咖啡馆里的浓缩咖啡机实拍", purl="https://news.example.com/report")
    assert I.score(real, 1200, 800, 300000, kw) > I.score(stock, 1200, 800, 300000, kw)
    assert I.score(stock, 1200, 800, 300000, kw) == -999, "素材站应被直接否掉"


def test_stock_site_veto_covers_every_tld_of_that_site():
    """真产物里漏进来的一张："咖啡摄影图__西餐美食_摄影图库_昵享网nipic.cn"。
    黑名单写的是 nipic.com，同一个站的 .cn 域名就这么过去了——
    域名黑名单漏一个后缀等于没写。"""
    kw = [u"咖啡", u"咖啡 摄影"]
    for url in ("https://www.nipic.cn/show/1.html", "https://sohu.nipic.com/x",
                "https://www.58pic.com/newpic/2.html", "https://qiantu.com/3",
                # 09-24 骁龙笔电篇漏进来的一张：`pixabay.com/images/search/plus`，
                # 检索词 `Plus` 命中的加号素材图。全球最大素材站之一原本不在表里。
                "https://pixabay.com/images/search/plus"):
        assert I.score(_cand(u"咖啡摄影图__西餐美食_摄影图库_昵享网", purl=url),
                       1600, 1000, 300000, kw) == -999, u"素材站没被拦住：%s" % url


def test_score_rewards_relevance_hits():
    kw = ["铂金包", "工坊"]
    hit = _cand("工坊里的铂金包手工缝制")
    miss = _cand(" unrelated landscape photo ")
    assert I.score(hit, 900, 900, 120000, kw) > I.score(miss, 900, 900, 120000, kw)


def test_off_topic_images_rejected_even_without_naming_the_subject():
    """从已生成的咖啡篇 + 香奈儿篇共 34 张图里挑出来的真实跑题样本。
    它们共同的特征是：复述了检索词里那个"既是产区/品类又是地名"的通用词，
    但整篇讲的是另一件事——也门铁是盆栽、巴拿马展园是世博会、
    欧洲三大半岛是地理。判据不是"命中几个词"，而是"有没有提到领域本身"。"""
    cases = [
        (u"巴拿马展园：一条运河流经世界十字路口，历史古城与日俱新",
         [u"咖啡", u"巴拿马 咖啡 庄园 瑰夏"], (u"咖啡",)),
        (u"也门铁修剪,也门,也门在哪(第19页)_大山谷图库",
         [u"咖啡", u"也门 摩卡 咖啡"], (u"咖啡",)),
        (u"中国行政区划介绍 - 知乎", [u"咖啡", u"中国 云南 咖啡 产区"], (u"咖啡",)),
        (u"50张经典的肖像摄影作品欣赏！",
         [u"香奈儿", u"Coco Chanel 肖像 历史"], (u"香奈儿", u"chanel")),
        (u"欧洲三大半岛是哪些（伊比利亚半岛、亚平宁半岛和巴尔干半岛）",
         [u"香奈儿", u"香奈儿 涨价 欧洲"], (u"香奈儿", u"chanel")),
        (u"什么是 Vintage 古着？只要二手旧东西都是 Vintage 吗 - 知乎",
         [u"香奈儿", u"香奈儿 中古 二手 保值"], (u"香奈儿", u"chanel")),
    ]
    for title, kw, subj in cases:
        # 2000px 大图：收紧前它靠尺寸加分赢过一切，正是它把跑题图顶到第一的
        assert I.score(_cand(title), 2000, 1200, 400000, kw, subject=subj) == -999, \
            u"跑题图被放行：%s" % title


def test_naming_the_subject_is_enough_to_keep_an_image():
    """反向闸门：真正在讲这个领域的图常常只命中"领域名"这一个词。
    上一版用"至少命中两个词"当相关性，第一批就误杀了
    "正确解读咖啡的各种好处""CHANEL 带着女士城堡穿越到上海了"
    "香奈儿珠宝简介"——咖啡篇只剩 3/12、香奈儿篇只剩 1/22 张图能用。"""
    cases = [
        (u"正确解读咖啡的各种好处 中国咖啡网", [u"咖啡", u"咖啡 好处 健康"], (u"咖啡",)),
        (u"CHANEL，带着“女士城堡”穿越到上海了",
         [u"香奈儿", u"香奈儿 上海 活动"], (u"香奈儿", u"chanel")),
        (u"香奈儿珠宝简介_Chanel珠宝知识及历史|腕表之家-珠宝",
         [u"香奈儿", u"香奈儿 珠宝 高级 历史"], (u"香奈儿", u"chanel")),
        (u"咖啡的完全入门指南 - ANTAICOFFEE广州安泰咖啡食品有限公司",
         [u"咖啡", u"咖啡 入门 指南"], (u"咖啡",)),
    ]
    for title, kw, subj in cases:
        assert I.score(_cand(title), 1200, 800, 200000, kw, subject=subj) > 0, \
            u"点名的相关图被误杀：%s" % title


def test_the_subject_free_tier_needs_two_keyword_hits():
    """"至少命中两个词"这条规则本身没错，错在上一次把它用在了点名主语那一档。
    实测 output/*/data.json 里已采用的 134 张：没点名主语的 13 张，关键词命中数
    **全部 ≤1**（中华万年历 app、圆角和倒角-CSDN、无人机保养、重型工作台…）；
    而点名主语的 121 张里有 37 张只命中 1 个词。
    所以这个下限只能收在"放弃主语要求"的那一档——两件事各有归属，不冲突。"""
    kw = [u"百达翡丽", u"万年历 机芯 腕表"]
    one = _cand(u"中华万年历官方下载-中华万年历 app 最新版本免费下载-应用宝官网")
    two = _cand(u"百达翡丽超级复杂功能时计系列万年历腕表")
    assert I.score(one, 1600, 1000, 300000, kw) > 0, u"对照组失效：它本来会被放宽档放行"
    assert I.score(one, 1600, 1000, 300000, kw, min_hits=I.RELAXED_MIN_HITS) == -999, \
        u"只蹭到一个词的页面还是被放宽档收进来了"
    assert I.score(two, 1600, 1000, 300000, kw, min_hits=I.RELAXED_MIN_HITS) > 0, \
        u"命中两个词的图被误杀"


def test_long_queries_get_a_short_sibling_that_names_the_subject():
    """实测 315 条大纲检索词里有 124 条**永远进不了点名档**：
    既不含品牌词，本身又 ≥3 词，而 ensure_subject 因为"补完就 4 词、Bing 召回崩塌"
    拒绝补主语（5 词实测只回 1 条）。这种词在点名档等于不存在，
    整章只能落到放宽档收"中华万年历 app""重型工作台"那种垃圾。
    修法是给它们补一条"品牌 + 前两个词"的短兄弟，不替换原词。"""
    subj = (u"劳力士", u"rolex")
    qs = I.gated_queries([u"天文台认证 COSC 证书", u"腕表 保养"], subj)
    assert u"天文台认证 COSC 证书" in qs, u"原词被换掉了，放宽档就没得用了"
    named = [q for q in qs if I.names_subject(q.lower(), subj)]
    assert named, u"补完之后仍然没有一条点名主语：%s" % qs
    for q in named:
        assert len(q.split()) <= 3, u"点名用的检索词超过 3 词，召回会崩：%s" % q
    # 已经点名的不该被多塞一条；短词由 ensure_subject 补主语，也不算"兄弟"
    assert I.gated_queries([u"劳力士 天文台 认证"], subj) == [u"劳力士 天文台 认证"]
    assert I.gated_queries([u"腕表 保养"], subj) == [u"劳力士 腕表 保养"], \
        u"两词的短词应该被补上主语，而不是再补一条兄弟"


def test_subject_tokens_are_derived_from_the_outline_not_hardcoded():
    """大纲里没人写过"chanel"这个字段，但它出现在香奈儿篇 6/11 章的检索词里，
    所以它就是主语；2.55、reissue、vintage 只在单章出现，是章节词不是主语。
    写死一张品牌别名表 = 每加一个领域都要改代码，违反"新增领域只加 JSON"。"""
    import outline as O
    cfg = O.load_for_topic(u"香奈儿", root=ROOT)
    subj = I.subject_tokens(cfg)
    assert u"香奈儿" in subj, u"领域名本身必须在主语里：%s" % (subj,)
    assert u"chanel" in subj, u"拉丁文品牌名要从检索词里推出来：%s" % (subj,)
    for noise in (u"vintage", u"reissue", u"巴拿马"):
        assert noise not in subj, u"%r 是章节词，不该进主语表" % noise
    coffee = I.subject_tokens(O.load_for_topic(u"咖啡", root=ROOT))
    assert u"咖啡" in coffee and u"也门" not in coffee, u"产区名混进主语就会放行旅游图：%s" % (coffee,)


# ------------------------------------------------------------------ collect

def test_collect_end_to_end_offline(tmp_path, bar, monkeypatch):
    """注入假检索与假下载，验证命名、来源留痕与素材站过滤全都生效。"""
    cands = [
        _cand(u"相关实拍 咖啡烘焙", murl="https://cdn.one/1.jpg", purl="https://a.example/1"),
        _cand(u"素材站咖啡插画", murl="https://cdn.one/2.jpg", purl="https://www.58pic.com/2"),
        _cand(u"另一张咖啡烘焙相关实拍", murl="https://cdn.one/3.jpg", purl="https://b.example/3"),
    ]
    monkeypatch.setattr(I, "search", lambda q, count=20, opener=None: list(cands))

    def dl(url, timeout=25, opener=None):
        return jpg_bytes() + url.encode() + bytes(90000)  # 每张内容不同，避免误判去重

    got = I.collect(["咖啡 烘焙"], str(tmp_path), bar, keywords=["咖啡", "烘焙"], downloader=dl)
    assert len(got) == 2, "素材站图应被滤掉，实际 %d 张" % len(got)
    assert all("58pic" not in g["source_page"] for g in got)
    for g in got:
        assert os.path.isfile(os.path.join(str(tmp_path), g["file"]))
        assert g["source_page"], "缺来源页的图不允许进产物"
        assert g["file"].startswith("images/")
    assert len({g["file"] for g in got}) == len(got)


def test_collect_dedupes_identical_bytes(tmp_path, bar, monkeypatch):
    same = jpg_bytes() + bytes(90000)
    cands = [_cand(u"咖啡 烘焙现场 %d" % i, murl="https://cdn/%d" % i,
                   purl="https://a.example/%d" % i) for i in range(3)]
    monkeypatch.setattr(I, "search", lambda q, count=20, opener=None: list(cands))
    got = I.collect(["咖啡"], str(tmp_path), bar, keywords=["咖啡", "烘焙"],
                    downloader=lambda url, timeout=25, opener=None: same)
    assert len(got) == 1, "相同内容未去重：%s" % [g["file"] for g in got]


def test_collect_never_overwrites_a_file_that_already_exists(tmp_path, bar, monkeypatch):
    """`collect` 的下一个编号是 len(seen_hash)+数字文件数，是**计数不是最大值+1**。
    重做几轮之后文件名会有空洞（退回、孤儿清理都会留下跳号），
    于是算出来的名字可以正好落在一个已存在的文件上，而写入分支是
    `open(name,"wb")`——没有存在性检查，直接把别人的图盖掉。
    被盖掉的那张很可能正被已落盘的 data.json 指着；
    而 `_rollback_images` 只在 `not isfile(dst)` 时才从快照恢复，
    文件在（只是内容变了），所以它永远不会被写回来——静默、永久。
    09-22 code review 实测：22 个文件编号 45..66 时，idx 算到 44，
    第一条新图就叫 `45_咖啡_烘焙.jpg`，正好盖住同名旧图。"""
    img = tmp_path / "images"
    img.mkdir()
    q = u"咖啡 起源 埃塞俄比亚"
    # 上一轮同一条检索词写出来的文件就叫 `<NN>_<slug(q)>.jpg`。
    # 这一轮编号漂到同一个 NN，名字就一模一样——写入分支没有存在性检查，直接盖。
    victim = img / ("45_%s.jpg" % I._slug(q, "img"))
    original = jpg_bytes() + bytes(90000)
    victim.write_bytes(original)
    for n in range(46, 67):
        (img / ("%d_fill.jpg" % n)).write_bytes(jpg_bytes() + bytes(90000 + n))
    assert len(list(img.glob("*.jpg"))) == 22

    cands = [_cand(u"咖啡 起源 埃塞俄比亚 新图", murl="https://cdn.one/new",
                   purl="https://a.example/new")]
    monkeypatch.setattr(I, "search", lambda q_, count=20, opener=None: list(cands))

    def dl(url, timeout=25, opener=None):
        return jpg_bytes() + b"different-bytes" + bytes(90000)

    got = I.collect([q], str(tmp_path), bar, keywords=[u"咖啡", u"起源"], downloader=dl)
    assert got, u"这条检索词本该出一张图，测试前提塌了"
    assert victim.read_bytes() == original, \
        u"collect 把已存在的 %s 盖掉了（这轮产出 %s），而它可能正被 data.json 指着" % (
            victim.name, [g["file"] for g in got])


def test_collect_records_when_the_engine_answers_an_unrelated_query(tmp_path, bar, monkeypatch):
    """09-22 23:15 实测：`积家 腕表 专柜` 召回 34 条，标题全是汉语字典里「积」字的
    笔顺动画与康熙字典页——**零条点名领域**。同一时刻 `劳力士 手表`、`百达翡丽 鹦鹉螺`
    却是完好的结果页。所以这不是"积家没有图"，也不是"检索词没点名"，
    而是引擎对这条词给了不相干的结果集。
    三种情况必须分开记：W-98 正站在岔口上，判成"供给稀薄"就会去砍已经花过额度的章节，
    判成"引擎答非所问"则只是换个时间重试（D-14）。
    """
    q = u"积家 腕表 专柜"
    junk = [_cand(u"积的意思,积的解释,积的拼音-汉语国学",
                  murl="https://cdn/junk%d.png" % i, purl="https://dict.example/%d" % i)
            for i in range(4)]
    monkeypatch.setattr(I, "search", lambda q_, count=20, opener=None: list(junk))
    stats = {}
    got = I.collect([q], str(tmp_path), bar, keywords=[u"积家", u"腕表"],
                    subject={u"积家", u"jaeger"},
                    downloader=lambda url, timeout=25, opener=None: b"", stats=stats)
    assert not got, u"全是字典页，本来就不该出图"
    assert stats.get(q) == {"offered": 4, "named": 0},         u"没记下「引擎答非所问」这个形状：%s" % stats


def test_the_recall_stats_lowercase_the_title_before_naming(tmp_path, bar, monkeypatch):
    """`MLCC`、`LV`、`TDK`、`GPU` 这类主语词本来就是大写的，而主语集合统一存小写。
    统计如果拿原文去比大小写敏感的子串，`named` 会恒为 0，
    于是 `_answered_off_subject` 判定「引擎答非所问」，整章被留空——
    而真正的点名闸门（`_reject`）是 `text.lower()` 之后再比的，图本来能过。
    两个地方判据不一致，报错的还是产物。"""
    q = u"MLCC 电容器"
    good = [_cand(u"MLCC多层陶瓷电容器规格书下载", murl="https://cdn/a.jpg",
                  purl="https://part.example/1"),
            _cand(u"什么是MLCC？一文看懂贴片电容", murl="https://cdn/b.jpg",
                  purl="https://part.example/2")]
    monkeypatch.setattr(I, "search", lambda q_, count=20, opener=None: list(good))
    stats = {}
    I.collect([q], str(tmp_path), bar, keywords=[u"MLCC", u"电容器"],
              subject={u"mlcc", u"电容器"},
              downloader=lambda url, timeout=25, opener=None: b"", stats=stats)
    assert stats.get(q, {}).get("named") == 2, \
        u"标题里明明有 MLCC，统计却报 named=%s——大小写没统一：%s" % (
            stats.get(q, {}).get("named"), stats)


def test_a_healthy_query_is_recorded_as_naming_the_subject(tmp_path, bar, monkeypatch):
    """反向钉住：同一套统计在正常召回时必须报 named>0，
    否则"引擎答非所问"会变成一条永远为真的分类，那和没有分类一样。"""
    q = u"劳力士 手表"
    good = [_cand(u"【劳力士手表价格及图片】Rolex劳力士手表官网型号查询",
                  murl="https://cdn/ok.jpg", purl="https://watch.example/1")]
    monkeypatch.setattr(I, "search", lambda q_, count=20, opener=None: list(good))
    stats = {}
    I.collect([q], str(tmp_path), bar, keywords=[u"劳力士"], subject={u"劳力士", u"rolex"},
              downloader=lambda url, timeout=25, opener=None: b"", stats=stats)
    assert stats.get(q, {}).get("named") == 1, stats


def test_an_adopted_existing_file_is_marked_not_fresh(tmp_path, bar, monkeypatch):
    """collect 按内容哈希认回上一轮已落盘的同一张图时，必须标 fresh=False。
    调用方靠这个标记决定"这张能不能删"：认回来的文件是上一轮的产物，
    而上一轮的 data.json 可能还指着它——09-21 深夜 LV 重做就是这么断了两张图。"""
    same = jpg_bytes() + bytes(90000)
    cands = [_cand(u"咖啡 烘焙现场", murl="https://cdn/1", purl="https://a.example/1")]
    monkeypatch.setattr(I, "search", lambda q, count=20, opener=None: list(cands))

    def dl(url, timeout=25, opener=None):
        return same

    first = I.collect(["咖啡"], str(tmp_path), bar, keywords=["咖啡", "烘焙"], downloader=dl)
    assert first and first[0]["fresh"] is True, "本轮新写的文件要标成 fresh"
    again = I.collect(["咖啡"], str(tmp_path), bar, keywords=["咖啡", "烘焙"], downloader=dl)
    assert again, "第二次应当认回已落盘的那张，而不是空手"
    assert again[0]["file"] == first[0]["file"], "认回就该复用同一个文件名"
    assert again[0]["fresh"] is False, "认回的旧文件被标成可删，重做进行中就会断图"


def test_collect_survives_search_failure(tmp_path, bar, monkeypatch):
    """单章检索挂掉不能拖垮整页：返回已取得的部分，不抛异常。"""
    def boom(q, count=20, opener=None):
        raise OSError("net down")
    monkeypatch.setattr(I, "search", boom)
    assert I.collect(["x"], str(tmp_path), bar) == []


def test_manifest_roundtrip(tmp_path, bar):
    entries = [{"file": "images/01_a.jpg", "source_page": "https://a.example/1"}]
    os.makedirs(os.path.join(str(tmp_path), "images"))
    I.write_manifest(str(tmp_path), entries)
    assert I.load_manifest(str(tmp_path)) == entries


def test_rejects_anatomy_diagram_even_at_high_resolution():
    """回归：用户截图里的"咖啡"封面其实是脊髓解剖图（brainmed 医学图解）。
    它分辨率高、来源页也真实，只有内容性质能识破。"""
    kw = [u"咖啡", u"手冲", u"烘焙"]
    diagram = _cand(u"Posterior horn dorsal root 脊髓 示意图 Alpha运动神经元",
                    purl="https://www.brainmed.com/info/detail?id=34736")
    assert I.score(diagram, 1280, 609, 200000, kw) == -999
    off_topic = _cand(u"kitchen interior design", purl="https://real.example/x")
    assert I.score(off_topic, 1280, 609, 200000, kw) == -999, "零关键词命中必须直接不要"


def test_slug_falls_back():
    assert I._slug(u"咖啡 意式浓缩!", "fb") == u"咖啡_意式浓缩"
    assert I._slug("///", "fb") == "fb"


def test_keyword_matching_tokenizes_multi_word_queries(bar):
    """keywords 里塞的是整条检索词（"咖啡 阿拉比卡 生豆"）。
    把整串当一个子串去比对图片标题，几乎必然 0 命中，而 hit==0 直接 -999。
    真实后果：咖啡 12 章里 10 章被判"没有相关图"，整站只收到 7 张图。"""
    cand = I.Candidate(title=u"阿拉比卡 咖啡 果实 晾晒 现场",
                        murl="https://img.example/a.jpg", turl="",
                        purl="https://blog.example/post-1")
    got = I.score(cand, 1400, 900, 180 * 1024, [u"咖啡 阿拉比卡 生豆"])
    assert got >= 0, u"命中了两个词却被判无关：%s" % got


def test_unrelated_image_still_rejected(bar):
    cand = I.Candidate(title=u"汽车发动机拆装教程",
                        murl="https://img.example/b.jpg", turl="",
                        purl="https://blog.example/post-2")
    assert I.score(cand, 1400, 900, 180 * 1024, [u"咖啡 阿拉比卡 生豆"]) < 0


def test_rerun_reuses_images_already_on_disk(tmp_path, bar, monkeypatch):
    """重跑时目录里已经有上一轮的图：原实现把"字节已存在"当成"这张不要了"，
    于是每一章都拿不到图——咖啡第三轮实测 12 章只有 2 章有配图。
    去重要防的是同一轮里重复，不是让重跑变没图。"""
    same = jpg_bytes() + bytes(90000)
    cands = [_cand(u"咖啡 烘焙现场 %d" % i, murl="https://cdn/%d" % i,
                   purl="https://a.example/%d" % i) for i in range(2)]
    monkeypatch.setattr(I, "search", lambda q, count=20, opener=None: list(cands))
    first = I.collect([u"咖啡"], str(tmp_path), bar, keywords=[u"咖啡", u"烘焙"],
                      downloader=lambda url, timeout=25, opener=None: same)
    assert len(first) == 1
    second = I.collect([u"咖啡"], str(tmp_path), bar, keywords=[u"咖啡", u"烘焙"],
                       downloader=lambda url, timeout=25, opener=None: same)
    assert len(second) == 1, "重跑一章图都没拿到"
    assert second[0]["file"] == first[0]["file"], "复用了别的文件名，会留下孤儿图"
    assert len(os.listdir(os.path.join(str(tmp_path), "images"))) == 1


def test_two_sections_never_share_one_image_file(tmp_path, bar, monkeypatch):
    """两章拿到同一个文件 = G-03"配图重复"判死，而且读者会在两章看到同一张图。
    跨轮复用只能复用"没被任何章节认领"的文件。"""
    same = jpg_bytes() + bytes(90000)
    cands = [_cand(u"咖啡 烘焙 现场", murl="https://cdn/x", purl="https://a.example/x")]
    monkeypatch.setattr(I, "search", lambda q, count=20, opener=None: list(cands))
    first = I.collect([u"咖啡"], str(tmp_path), bar, keywords=[u"咖啡", u"烘焙"],
                      downloader=lambda url, timeout=25, opener=None: same)
    again = I.collect([u"咖啡"], str(tmp_path), bar, keywords=[u"咖啡", u"烘焙"],
                      downloader=lambda url, timeout=25, opener=None: same,
                      claimed={first[0]["file"]})
    assert again == [], u"已被别的章节认领的文件又被发了一次：%s" % [g["file"] for g in again]


def test_collect_falls_back_to_single_tokens(tmp_path, bar, monkeypatch):
    """实测：Bing CN 对多词图检索词经常返回一整页兜底垃圾（旅游榜单、施工方案、
    利物浦海报），同一个词换成单检索词才召得回真图。
    所以整串查不到时，必须自己降粒度重试，而不是让这一章没图。"""
    good = jpg_bytes() + bytes(90000)
    junk = _cand(u"20个著名世界旅游胜地清单", murl="https://cdn/junk", purl="https://junk.example/1")
    real = _cand(u"咖啡树 上 成熟 的 咖啡果", murl="https://cdn/good", purl="https://good.example/1")

    def fake_search(q, count=20, opener=None):
        return [junk] if u" " in q else [real]

    monkeypatch.setattr(I, "search", fake_search)
    got = I.collect([u"阿拉比卡 咖啡树 叶片"], str(tmp_path), bar,
                    keywords=[u"咖啡", u"咖啡树"],
                    downloader=lambda url, timeout=25, opener=None:
                    good if u"good" in url else None)
    assert len(got) == 1, u"整串失败后没有降级到单词重试：%s" % [g["file"] for g in got]
    assert u"咖啡" in got[0]["query"] or got[0]["query"]


def test_a_source_page_a_human_excluded_stays_out_of_every_later_redo(tmp_path, bar, monkeypatch):
    """手工从 data.json 摘掉的图会被下一次重做原样抓回来——09-23 实测：
    18:35 摘掉爱马仕那张橙色字标面板，22:40 重做时它又回来了，只是换了个章节。
    评分与闸门都拦不住它：标题里有品牌词、没有 logo 词（D-17 量过按关键词否决会误杀 27 张好图）。
    所以给人眼结论留一个**按来源页 URL 排除**的声明位：不猜语义，误杀面是零。"""
    banned = [_cand(u"咖啡 烘焙 车间 广告图", murl="https://ad.example/1.jpg",
                    purl="https://ad.example/promo-1")]
    ok = [_cand(u"咖啡 烘焙 滚筒 实拍", murl="https://roaster.example/2.jpg",
                purl="https://roaster.example/2")]
    monkeypatch.setattr(I, "search", lambda q, count=20, opener=None: banned + ok)
    fetched = []

    def dl(url, timeout=25, opener=None):
        fetched.append(url)
        return jpg_bytes() + bytes(90000)

    got = I.collect([u"咖啡 烘焙"], str(tmp_path), bar, keywords=[u"咖啡", u"烘焙"],
                    subject={u"咖啡"}, downloader=dl,
                    exclude_pages=["https://ad.example/promo-1"])
    assert [g["source_page"] for g in got] == ["https://roaster.example/2"], \
        u"被人工排除的来源页还是进了产物：%s" % [g["source_page"] for g in got]
    assert fetched == ["https://roaster.example/2.jpg"], \
        u"排除要发生在下载之前（同 W-113 那条）：%s" % fetched


def test_excluding_a_site_prefix_excludes_its_pages_too(tmp_path, bar, monkeypatch):
    """排除要能写成整站：一个只发宣传图的站，它每一页都是宣传图。
    逐页列 URL 会让这个声明位变成一次性劳动。"""
    site = [_cand(u"咖啡 拉花 教程 %d" % i, murl="https://adsite.example/%d.jpg" % i,
                  purl="https://adsite.example/t/%d" % i) for i in range(3)]
    ok = [_cand(u"咖啡 拉花 实拍", murl="https://real.example/9.jpg",
                purl="https://real.example/9")]
    monkeypatch.setattr(I, "search", lambda q, count=20, opener=None: site + ok)
    got = I.collect([u"咖啡 拉花"], str(tmp_path), bar, keywords=[u"咖啡", u"拉花"],
                    subject={u"咖啡"}, downloader=lambda u, **k: jpg_bytes() + bytes(90000),
                    exclude_pages=[u"https://adsite.example/"])
    assert [g["source_page"] for g in got] == ["https://real.example/9"], \
        u"前缀排除没生效：%s" % [g["source_page"] for g in got]
