# -*- coding: utf-8 -*-
"""合站：组包、两级指纹、组粒度的账本（memo D-34 授权的那次改动）。

这批测试要钉住的是合站**新引入**的失败形态，不是把 test_publish.py 再抄一遍：

· 一篇一站时"这篇的指纹"就是"这个站的指纹"，一个数够用。
  合站之后它们会分叉：改一次模板，落地页变了而每篇的字节都没变。
  只有一级指纹的话，线上那一组是旧的、每一篇都说自己新，谁都不响。
· 落地页会引用成员声明的封面，而文章页不一定引用它。
  少一项不是少一张卡片，是整组卡片都破，而 pack 全绿。
· 深链由"组地址 + 组内路径"两段拼出来，任何一段错了都是线上 404，
  而账上写着"一致"。所以 record 两段都要查，且**整名相等**不许退化成前缀。
"""
import io
import json
import os

import pytest

import publish as P
import build_index as B

PROJECT = u"01a0d6cd-4074-721d-b827-e9ee83c8de56"


SLUGS = {u"咖啡": "coffee", u"茶": "tea"}


def _topic(root, topic, cover=None, slug=None):
    """output/<领域>/ 的最小可信形状：一页 + 三张图 + data.json + 大纲里的 slug。

    slug 是**必须**的：组包里的目录名与深链路径段都是它（`<slug>/<slug>.html`），
    不用中文领域名——那会把公开地址变成一串百分号编码，
    而"slug 是人写下来的、不许从领域名转写"这条规矩就没有落点了。

    `cover` 指向一张**文章页没引用**的图（`03_cover.jpg`）。
    这一点是测试的要害：我第一版让封面复用文章里已有的 `02_b.jpg`，
    于是 `topic_files` 本来就会把它带进包，把 `cover_files` 整行删掉测试照样绿——
    一条钉"整组卡片不许破"的测试空过了。
    """
    d = root / "output" / topic
    (d / "images").mkdir(parents=True)
    (d / "images" / "01_a.jpg").write_bytes(b"\xff\xd8\xff\xe0" + b"a" * 3000)
    (d / "images" / "02_b.jpg").write_bytes(b"\xff\xd8\xff\xe0" + b"b" * 3000)
    (d / "images" / "03_cover.jpg").write_bytes(b"\xff\xd8\xff\xe0" + b"c" * 3000)
    page = (u'<html><body><a class="backhome-link" href="../index.html">返回</a>'
            u'<img src="images/01_a.jpg" alt="x"/><img src="images/02_b.jpg" alt="y"/>'
            u"</body></html>")
    (d / ("%s.html" % topic)).write_text(page, encoding="utf-8")
    data = {"topic": topic, "category": u"腕表", "sections": [], "sources": []}
    if cover:
        data["cover"] = cover
    (d / "data.json").write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    cfg = root / "config" / "topics"
    cfg.mkdir(parents=True, exist_ok=True)
    (cfg / (topic + ".json")).write_text(
        json.dumps({"topic": topic, "slug": slug or SLUGS.get(topic, topic.lower())},
                   ensure_ascii=False),
        encoding="utf-8")
    return d


def _groups(root, spec):
    (root / "config").mkdir(exist_ok=True)
    (root / "config" / "site_groups.json").write_text(
        json.dumps({"groups": spec}, ensure_ascii=False, indent=1), encoding="utf-8")
    return root


def _g(*members):
    return {"display_name": u"腕表", "members": list(members), "project_id": None,
            "site_id": None, "url": None, "access": "private",
            "published_date": None, "group_sha": None}


def _landing(root, group, extra_refs=()):
    """手写一份落地页。测试里不跑 node：pack_group(render=False) 直接吃它。"""
    dest = root / "dist" / group
    dest.mkdir(parents=True, exist_ok=True)
    imgs = u"".join(u'<img src="%s" alt="c"/>' % r for r in extra_refs)
    (dest / "index.html").write_text(
        u'<html><body><a class="card" href="coffee/coffee.html">咖啡</a>%s</body></html>' % imgs,
        encoding="utf-8")
    return dest / "index.html"


# ------------------------------------------------------------------ 组的身份

def test_group_of_reads_the_config_not_the_category(tmp_path):
    """category 是内容的属性，会随编辑判断改；组名进了 URL。
    要是从 category 推组，改一次分类描述就等于把所有已分享的深链判死刑。"""
    _topic(tmp_path, u"咖啡")
    _groups(tmp_path, {"watches": _g(u"咖啡")})
    assert P.group_of(u"咖啡", str(tmp_path)) == "watches"
    data = json.loads((tmp_path / "output" / u"咖啡" / "data.json").read_text(encoding="utf-8"))
    data["category"] = u"饮料"
    (tmp_path / "output" / u"咖啡" / "data.json").write_text(
        json.dumps(data, ensure_ascii=False), encoding="utf-8")
    assert P.group_of(u"咖啡", str(tmp_path)) == "watches", u"组跟着 category 动了"


def test_members_of_refuses_an_unknown_group(tmp_path):
    _groups(tmp_path, {"watches": _g(u"咖啡")})
    with pytest.raises(P.PublishError):
        P.members_of("coffee", str(tmp_path))


# ------------------------------------------------------------------ 两级指纹

def test_own_sha_is_unchanged_when_the_group_changes(tmp_path):
    """D-b 的整个前提：组怎么重组，成员自己的指纹不许跟着动。

    做不到的话，一次分类调整就会把 29 篇全部推成"线上是旧版"，
    而那份"旧"其实只是我改了个 JSON 里的归属。
    """
    _topic(tmp_path, u"咖啡")
    _groups(tmp_path, {"watches": _g(u"咖啡")})
    before = P.own_sha(u"咖啡", str(tmp_path / "output"), str(tmp_path))
    _groups(tmp_path, {"food": _g(u"咖啡"), "watches": _g()})
    after = P.own_sha(u"咖啡", str(tmp_path / "output"), str(tmp_path))
    assert before == after


def test_own_sha_follows_the_packed_bytes(tmp_path):
    _topic(tmp_path, u"咖啡")
    _groups(tmp_path, {"watches": _g(u"咖啡")})
    before = P.own_sha(u"咖啡", str(tmp_path / "output"), str(tmp_path))
    p = tmp_path / "output" / u"咖啡" / "images" / "01_a.jpg"
    p.write_bytes(b"\xff\xd8\xff\xe0" + b"z" * 3000)
    assert P.own_sha(u"咖啡", str(tmp_path / "output"), str(tmp_path)) != before


def test_group_sha_moves_when_only_the_landing_page_changed(tmp_path):
    """这是合站**新**出来的那种坏：落地页变了，每一篇自己的字节都没变。

    只有一级指纹时它完全隐形——线上那一组是旧的，而 pending 一篇都不列。
    """
    _topic(tmp_path, u"咖啡")
    _groups(tmp_path, {"watches": _g(u"咖啡")})
    output = str(tmp_path / "output")
    _landing(tmp_path, "watches")
    sha1 = P.group_sha("watches", str(tmp_path), output)
    assert P.own_sha(u"咖啡", output, str(tmp_path)) == P.own_sha(u"咖啡", output, str(tmp_path))
    _landing(tmp_path, "watches", extra_refs=(u"coffee/images/02_b.jpg",))
    sha2 = P.group_sha("watches", str(tmp_path), output)
    assert sha1 != sha2, u"落地页变了而 group_sha 不动，那这条指纹没有意义"


def test_adding_a_member_moves_the_group_sha(tmp_path):
    _topic(tmp_path, u"咖啡")
    _topic(tmp_path, u"茶")
    _groups(tmp_path, {"watches": _g(u"咖啡")})
    _landing(tmp_path, "watches")
    output = str(tmp_path / "output")
    one = P.group_sha("watches", str(tmp_path), output)
    _groups(tmp_path, {"watches": _g(u"咖啡", u"茶")})
    assert P.group_sha("watches", str(tmp_path), output) != one


# ------------------------------------------------------------------ 组包

def test_group_package_carries_the_landing_page_covers(tmp_path):
    """落地页引用一张**文章页没引用**的封面时，它仍必须进包。

    `data.cover` 可以指向一张没进任何章节的图；文章页的 `<img src>` 里没有它，
    于是按"页面引用了什么"收集清单就会漏掉——线上是整组卡片破图，而 pack 报成功。
    """
    cover = {"file": "images/03_cover.jpg", "width": 800, "height": 600}
    _topic(tmp_path, u"咖啡", cover=cover)
    _groups(tmp_path, {"watches": _g(u"咖啡")})
    _landing(tmp_path, "watches", extra_refs=(u"coffee/images/03_cover.jpg",))
    rel = u"coffee/images/03_cover.jpg"
    # 先自证这张图确实"文章页没引用"，否则这条测试会像第一版那样空过
    page_refs = {r for r, _ in P.topic_files(u"咖啡", str(tmp_path / "output"),
                                             str(tmp_path / "config" / "topics"))}
    assert rel not in page_refs, u"fixture 没造出「只在落地页出现」的封面"
    rels = {r for r, _ in P.group_package_files(
        "watches", str(tmp_path), str(tmp_path / "output"))}
    assert rel in rels
    assert u"index.html" in rels


def test_pack_refuses_a_landing_page_whose_links_do_not_resolve(tmp_path):
    """这条测试对应一次真事故：落地页照抄 `output/` 的布局链到 `咖啡/咖啡.html`，
    而包里文章住在 `coffee/coffee.html`。`pack` 全绿、文件都搬对了，
    线上每一张卡却都 404——**搬文件那一步看不见链接指哪儿**。
    """
    _topic(tmp_path, u"咖啡")
    _groups(tmp_path, {"watches": _g(u"咖啡")})
    _landing(tmp_path, "watches")
    page = tmp_path / "dist" / "watches" / "index.html"
    page.write_text(u'<html><body><a class="card" href="咖啡/咖啡.html">咖啡</a>'
                    u"</body></html>", encoding="utf-8")
    files = P.group_package_files("watches", str(tmp_path), str(tmp_path / "output"))
    bad = P.landing_link_problems(files)
    assert bad and u"咖啡/咖啡.html" in bad[0], bad
    with pytest.raises(P.PublishError):
        P.pack_group("watches", root=str(tmp_path), output=str(tmp_path / "output"),
                     render=False)
    assert not os.path.isfile(str(tmp_path / "dist" / "watches" / ".packed-sha")), \
        u"半成品留在盘上会被下一次 prepare_site 直接传上去"


def test_a_real_landing_page_links_resolve_after_render(tmp_path):
    """反向也要成立：真正渲染出来的落地页，链接必须全部在包内解析得到。
    只测"坏例子会被抓"不够——那可能只是断言写得松。"""
    _topic(tmp_path, u"咖啡")
    _groups(tmp_path, {"watches": _g(u"咖啡")})
    _landing(tmp_path, "watches", extra_refs=(u"coffee/images/01_a.jpg",))
    files = P.group_package_files("watches", str(tmp_path), str(tmp_path / "output"))
    assert P.landing_link_problems(files) == []


def test_pack_group_prunes_a_member_it_no_longer_has(tmp_path):
    """成员被摘出去（或改了 slug）之后，旧目录还留在 `dist/<组>/` 里，
    `prepare_site` 会把它一起上传——线上多出一页谁都不链接的旧内容，
    而它可能正是某个人收藏着的那个地址。"""
    _topic(tmp_path, u"咖啡")
    _topic(tmp_path, u"茶")
    _groups(tmp_path, {"watches": _g(u"咖啡", u"茶")})
    _landing(tmp_path, "watches", extra_refs=(u"coffee/images/01_a.jpg",))
    P.pack_group("watches", root=str(tmp_path), output=str(tmp_path / "output"),
                 render=False)
    assert os.path.isdir(str(tmp_path / "dist" / "watches" / "tea"))
    _groups(tmp_path, {"watches": _g(u"咖啡")})
    _landing(tmp_path, "watches", extra_refs=(u"coffee/images/01_a.jpg",))
    P.pack_group("watches", root=str(tmp_path), output=str(tmp_path / "output"),
                 render=False)
    assert not os.path.isdir(str(tmp_path / "dist" / "watches" / "tea")), \
        u"被摘出去的成员目录还留在包里，会被下一次 prepare_site 一起传上去"
    assert os.path.isfile(str(tmp_path / "dist" / ".packed" / "watches.sha")), \
        u"marker 搬到包里之外之后，清理逻辑不该再碰它——它不在被清理的那棵树里"


def test_the_package_directory_holds_nothing_but_the_package(tmp_path):
    """包目录里的文件集合必须**恰好等于**包清单。多一个就删。

    `.packed-sha` 与落地页的 `index.html.srchash` 都曾被留在 `dist/<组>/` 里，
    而 `prepare_site` 拿的是**整个目录**——于是这两个内部文件出现在公网上（W-184）。
    它们和 `manifest.json` 那批是同一类东西（页面不引用的实现细节），
    但"往排除清单里再加两个名字"是一条**会漏的规矩**：下一个内部文件照样漏。
    所以这条不写名字，写结构不变量。
    """
    _topic(tmp_path, u"咖啡")
    _groups(tmp_path, {"watches": _g(u"咖啡")})
    _landing(tmp_path, "watches", extra_refs=(u"coffee/images/01_a.jpg",))
    d = tmp_path / "dist" / "watches"
    (d / "index.html.srchash").write_text(u"deadbeef\n", encoding="utf-8")
    (d / "coffee").mkdir(exist_ok=True)     # 真包里文章目录由 pack 铺，这里先摆好
    (d / "coffee" / "coffee.html.srchash").write_text(u"deadbeef\n", encoding="utf-8")
    P.pack_group("watches", root=str(tmp_path), output=str(tmp_path / "output"),
                 render=False)
    have = {os.path.relpath(os.path.join(r, f), d).replace(os.sep, "/")
            for r, _, fs in os.walk(d) for f in fs}
    want = {rel for rel, _ in P.group_package_files(
        "watches", str(tmp_path), str(tmp_path / "output"))}
    assert have == want, u"包目录里有 %d 个不属于包的文件：%s" % (
        len(have - want), sorted(have - want))

    # 第二次打包走"指纹未变，跳过重铺"那条路。清理必须**在那条分叉之前**，
    # 否则真渲染时刚写出的 srchash 会从旁路活下来——而旁路才是 AGENTS 第 5 步的常态。
    (d / "index.html.srchash").write_text(u"deadbeef\n", encoding="utf-8")
    again = P.pack_group("watches", root=str(tmp_path), output=str(tmp_path / "output"),
                         render=False)
    assert again["skipped"] is True, u"这条断言要走的正是跳过那条分叉"
    assert not os.path.isfile(str(d / "index.html.srchash")), \
        u"跳过重打包的时候没清理，打包器自己的文件又留在包里了"


def test_pack_group_does_not_rebuild_when_nothing_changed(tmp_path):
    """跳过重打包的前提是**marker 还在**。
    上一版先 `rmtree(dest)` 再判跳过，于是 marker 刚被自己删掉，
    那道优化永远命中不了——AGENTS 第 5 步一次要重渲染 29 篇，每篇都白铺一遍。"""
    _topic(tmp_path, u"咖啡")
    _groups(tmp_path, {"watches": _g(u"咖啡")})
    _landing(tmp_path, "watches", extra_refs=(u"coffee/images/01_a.jpg",))
    first = P.pack_group("watches", root=str(tmp_path), output=str(tmp_path / "output"),
                         render=False)
    assert first["skipped"] is False
    second = P.pack_group("watches", root=str(tmp_path), output=str(tmp_path / "output"),
                          render=False)
    assert second["skipped"] is True, u"内容没变却还是重铺了一遍"
    assert os.path.isfile(os.path.join(second["dir"], "coffee", "coffee.html")), \
        u"跳过的时候把包里的文件删了——跳过不等于清空"


# ------------------------------------------------------------- 组落地页的结构检查

def test_check_group_is_quiet_when_the_package_matches_the_members(tmp_path):
    _topic(tmp_path, u"咖啡")
    _groups(tmp_path, {"watches": _g(u"咖啡")})
    _landing(tmp_path, "watches", extra_refs=(u"coffee/images/01_a.jpg",))
    assert P.check_group("watches", str(tmp_path), str(tmp_path / "output")) == []


def test_check_group_says_nothing_when_nothing_is_packed(tmp_path):
    """没打包是**正常状态**（发布前才打包）。
    把它判成问题会让 `validate --all` 每次发布前都红一片，那是逼人去关闸门。"""
    _topic(tmp_path, u"咖啡")
    _groups(tmp_path, {"watches": _g(u"咖啡")})
    assert P.check_group("watches", str(tmp_path), str(tmp_path / "output")) == []


def test_check_group_names_a_member_with_no_card(tmp_path):
    """少一张卡 = 那篇的深链已经记在账上，而组站里点不到它。"""
    _topic(tmp_path, u"咖啡")
    _topic(tmp_path, u"茶")
    _groups(tmp_path, {"watches": _g(u"咖啡", u"茶")})
    _landing(tmp_path, "watches", extra_refs=(u"coffee/images/01_a.jpg",))
    msgs = P.check_group("watches", str(tmp_path), str(tmp_path / "output"))
    assert any(u"少一张卡" in m and u"tea" in m for m in msgs), msgs


def test_check_group_names_an_extra_card(tmp_path):
    """多一张卡 = 链到一页不在成员集合里的东西，通常是刚被摘出去的成员。"""
    _topic(tmp_path, u"咖啡")
    _topic(tmp_path, u"茶")
    _groups(tmp_path, {"watches": _g(u"咖啡")})
    _landing(tmp_path, "watches",
             extra_refs=(u"coffee/images/01_a.jpg",))
    page = tmp_path / "dist" / "watches" / "index.html"
    page.write_text(page.read_text(encoding="utf-8").replace(
        u"</body>", u'<a class="card" href="tea/tea.html">x</a></body>'),
        encoding="utf-8")
    msgs = P.check_group("watches", str(tmp_path), str(tmp_path / "output"))
    assert any(u"多一张卡" in m for m in msgs), msgs


def test_check_group_catches_the_layout_mismatch_that_pack_reported_as_success(tmp_path):
    """这次事故的原样：落地页链 `咖啡/咖啡.html`（output 的布局），
    包里文章住在 `coffee/coffee.html`（组包的布局）。
    `pack` 全绿、文件都搬对了，线上每张卡都 404。"""
    _topic(tmp_path, u"咖啡")
    _groups(tmp_path, {"watches": _g(u"咖啡")})
    _landing(tmp_path, "watches")          # _landing 默认写的就是 coffee/coffee.html
    page = tmp_path / "dist" / "watches" / "index.html"
    page.write_text(page.read_text(encoding="utf-8").replace(
        u"coffee/coffee.html", u"咖啡/咖啡.html"), encoding="utf-8")
    msgs = P.check_group("watches", str(tmp_path), str(tmp_path / "output"))
    assert msgs, u"落地页链到包外的一页，check_group 却没说话"
    assert any(u"找不到" in m or u"少一张卡" in m for m in msgs), msgs


# ---------------------------------------------------------------- 哪些旧站能删

def test_absorbed_sites_lists_only_the_published_group_members(tmp_path):
    """这条测试的存在理由是我差点删错站：
    《大模型与加密货币》属于 `ai-industry` 组而不是 `ai-compute`，
    在只发了 ai-compute 时删掉它的旧站，等于把一篇线上文章删了。
    而 record-group 已经把 site.url 覆盖成深链，旧地址在 data.json 里查不到——
    所以"能删哪些"必须由规则算出来，不能靠记忆。"""
    _topic(tmp_path, u"咖啡")
    _topic(tmp_path, u"茶")
    _groups(tmp_path, {"watches": _g(u"咖啡"), "food": _g(u"茶")})
    _landing(tmp_path, "watches", extra_refs=(u"coffee/images/01_a.jpg",))
    assert P.absorbed_sites("watches", str(tmp_path)) == [], u"组没发布就不该列出任何可删的站"
    P.record_group("watches", u"https://watches%s/" % P.HOST_SUFFIX,
                   root=str(tmp_path), project_id=PROJECT, published_date="2026-10-04",
                   output=str(tmp_path / "output"))
    rows = P.absorbed_sites("watches", str(tmp_path))
    assert [r["topic"] for r in rows] == [u"咖啡"], \
        u"把别的组的成员也列进来了：删了就少一篇线上文章"
    assert rows[0]["old_host"] == u"coffee" + P.HOST_SUFFIX


def test_absorbed_sites_skips_a_member_whose_old_host_is_the_group_host(tmp_path):
    """slug 恰好等于组名时旧站就是组站本身，列出来等于让人去删刚发好的那个站。"""
    _topic(tmp_path, u"咖啡", slug="watches")
    _groups(tmp_path, {"watches": _g(u"咖啡")})
    _landing(tmp_path, "watches")
    P.record_group("watches", u"https://watches%s/" % P.HOST_SUFFIX,
                   root=str(tmp_path), project_id=PROJECT, published_date="2026-10-04",
                   output=str(tmp_path / "output"))
    assert P.absorbed_sites("watches", str(tmp_path)) == []


def test_pack_group_lays_out_articles_under_their_own_slug_dir(tmp_path):
    """包内目录名是 slug 而不是中文领域名：深链里不该出现一串百分号编码。"""
    _topic(tmp_path, u"咖啡")
    _groups(tmp_path, {"watches": _g(u"咖啡")})
    _landing(tmp_path, "watches")
    info = P.pack_group("watches", root=str(tmp_path), output=str(tmp_path / "output"),
                        render=False)
    dest = info["dir"]
    assert os.path.isfile(os.path.join(dest, "index.html"))
    assert os.path.isfile(os.path.join(dest, "coffee", "coffee.html"))
    assert os.path.isfile(os.path.join(dest, "coffee", "images", "01_a.jpg"))


def test_pack_group_refuses_a_member_with_no_declared_slug(tmp_path):
    """slug 决定公开地址，必须是人写下来的。缺了就报错，不从中文领域名转写。"""
    d = _topic(tmp_path, u"咖啡")
    (tmp_path / "config" / "topics" / u"咖啡.json").unlink()
    _groups(tmp_path, {"watches": _g(u"咖啡")})
    _landing(tmp_path, "watches")
    with pytest.raises(P.NoSlug):
        P.pack_group("watches", root=str(tmp_path), output=str(tmp_path / "output"),
                     render=False)


def test_pack_group_refuses_when_over_the_working_limit(tmp_path):
    """超线就拒绝并说该分裂。**不许**在这里悄悄压图——
    那等于发一份比闸门验过的更差的产物，而且没人知道图被压过。"""
    _topic(tmp_path, u"咖啡")
    _groups(tmp_path, {"watches": _g(u"咖啡")})
    _landing(tmp_path, "watches")
    with pytest.raises(P.TooLarge) as e:
        P.pack_group("watches", root=str(tmp_path), output=str(tmp_path / "output"),
                     max_mib=0, render=False)
    assert u"分裂" in str(e.value)


def test_pack_group_does_not_rewrite_the_back_home_link(tmp_path):
    """一篇一站时代要改写 `../index.html`（否则它指回自己）。
    合站之后它正好指向同一个包里的落地页，**一个字节都不该动**。
    这条测试钉的是"那套字符串契约真的退场了"，不是它以前对不对。"""
    _topic(tmp_path, u"咖啡")
    _groups(tmp_path, {"watches": _g(u"咖啡")})
    _landing(tmp_path, "watches")
    info = P.pack_group("watches", root=str(tmp_path), output=str(tmp_path / "output"),
                        render=False)
    got = io.open(os.path.join(info["dir"], "coffee", "coffee.html"),
                  encoding="utf-8").read()
    src = io.open(str(tmp_path / "output" / u"咖啡" / u"咖啡.html"), encoding="utf-8").read()
    assert got == src
    assert u'href="../index.html"' in got


# ---------------------------------------------------------------- 落地页不许少一页

def test_landing_page_refuses_a_member_it_had_to_drop(tmp_path, monkeypatch):
    """`_publishable` 会静默跳过闸门未过的领域。全站主页少一篇是正常状态，
    **组落地页少一个成员不是**：那篇的深链已经记在账上，线上就是 404，
    而 `validate --all` 全绿——因为它自己被判死了，本来就不该上架。"""
    _topic(tmp_path, u"咖啡")
    _topic(tmp_path, u"茶")
    monkeypatch.setattr(B, "_publishable", lambda t, r: [] if t == u"咖啡" else [u"G-99 假 fail"])
    with pytest.raises(RuntimeError) as e:
        B.collect(topics=[u"咖啡", u"茶"], output_dir=str(tmp_path / "output"))
    assert u"茶" in str(e.value)


def test_home_page_may_skip_a_topic_with_no_group(tmp_path, monkeypatch):
    """同一件事的另一半：还没分组的篇，主页跳过就行。
    10-03 那次就是这条把整张主页冻住的（D-33：防呆判据在第二种成因下变成阻塞器）。"""
    _topic(tmp_path, u"咖啡")
    _groups(tmp_path, {"watches": _g(u"咖啡")})
    monkeypatch.setattr(B, "_publishable", lambda t, r: [])
    entries = B.collect(topics=[u"咖啡"], output_dir=str(tmp_path / "output"))
    assert [e["topic"] for e in entries] == [u"咖啡"]


# ---------------------------------------------------------- 组名即公开地址


def test_a_group_name_the_platform_cannot_host_is_refused(tmp_path):
    """组名**就是**公开地址的前缀，所以它得先是个合法的地址段。

    真实成因（2026-10-04）：`ai` 只有两个字符，平台下限是 3，
    `check_subdomain` 直接回 `sites_invalid_subdomain`。而 `prepare_site` **不报错**——
    它静默退化成十六进制前缀（实测拿到 `5d8a0008…`）。后果不是"地址丑一点"：
    `deep_link()` 按组名拼出的每一条卡片链接从第一天起就是 404，
    `record` 的整名相等校验只会说"你拼错了"，而本地闸门全绿。
    所以这条必须在**读配置**时炸，而不是等到 curl。
    """
    _groups(tmp_path, {"ai": _g(u"咖啡")})
    with pytest.raises(P.PublishError) as e:
        P.group_host("ai")
    assert u"3" in str(e.value)


def test_load_groups_refuses_it_before_anything_else(tmp_path):
    """`group_host` 只是其中一条出口。`pack`、`playbook`、`check` 都会先读组表，
    所以判据也得放在读的地方——只放在拼地址处，等于让"还没拼地址"的路径放过坏名字。"""
    _groups(tmp_path, {"watches": _g(u"咖啡"), "ab": _g(u"茶")})
    with pytest.raises(P.PublishError):
        P.load_groups(root=str(tmp_path))


def test_a_group_name_of_52_characters_is_refused(tmp_path):
    """上限同样是平台给的：前缀 3–51，后面还要拼 `-gtqdc11h6po.qoder.website`。
    只守下限的话，一个长名字要到 `prepare_site` 才被发现——那已经是不可逆的一步。"""
    _groups(tmp_path, {"g" * 52: _g(u"咖啡")})
    with pytest.raises(P.PublishError):
        P.group_host("g" * 52)
    assert P.group_host("g" * 51)         # 边界内就该过，别把合法值一起挡了


# ------------------------------------------------------------------ record

def _recorded(tmp_path, group="watches", members=(u"咖啡",)):
    for m in members:
        _topic(tmp_path, m)
    _groups(tmp_path, {group: _g(*members)})
    _landing(tmp_path, group)


def test_record_accepts_a_deep_link_only_for_its_own_group(tmp_path):
    _recorded(tmp_path)
    url = u"https://watches%s/coffee/coffee.html" % P.HOST_SUFFIX
    site = P.record(u"咖啡", url, project_id=PROJECT, published_date="2026-10-04",
                    root=str(tmp_path), output=str(tmp_path / "output"))
    assert site["group"] == "watches"
    assert site["path"] == u"/coffee/coffee.html"


def test_record_refuses_a_link_into_another_group(tmp_path):
    _recorded(tmp_path)
    _topic(tmp_path, u"茶")
    _groups(tmp_path, {"watches": _g(u"咖啡"), "food": _g(u"茶")})
    _landing(tmp_path, "watches")
    url = u"https://food%s/coffee/coffee.html" % P.HOST_SUFFIX
    with pytest.raises(P.PublishError) as e:
        P.record(u"咖啡", url, project_id=PROJECT, published_date="2026-10-04",
                 root=str(tmp_path), output=str(tmp_path / "output"))
    assert u"主机名" in str(e.value)


def test_record_refuses_a_host_that_merely_starts_like_ours(tmp_path):
    """整名相等，不许退化成前缀——`startswith(group + "-")` 等于
    `watches-anything.evil.tld` 也收，而这条检查存在的理由就是我真拼错过地址。"""
    _recorded(tmp_path)
    url = u"https://watches-anything.evil.tld/coffee/coffee.html"
    with pytest.raises(P.PublishError):
        P.record(u"咖啡", url, project_id=PROJECT, published_date="2026-10-04",
                 root=str(tmp_path), output=str(tmp_path / "output"))


def test_record_refuses_the_right_host_but_the_wrong_path(tmp_path):
    """只查主机名不够：把成员记到同组的**另一篇**上，深链就是线上 404，
    而账上写着"一致"，check 自己发现不了。"""
    _recorded(tmp_path, members=(u"咖啡", u"茶"))
    url = u"https://watches%s/tea/tea.html" % P.HOST_SUFFIX
    with pytest.raises(P.PublishError) as e:
        P.record(u"咖啡", url, project_id=PROJECT, published_date="2026-10-04",
                 root=str(tmp_path), output=str(tmp_path / "output"))
    assert u"路径" in str(e.value)


def test_record_refuses_a_topic_in_no_group(tmp_path):
    """一篇一站的时代结束了。没分组就没有地址可记，必须说清楚，
    而不是凭 slug 拼一个已经不再存在的站名。"""
    _topic(tmp_path, u"咖啡")
    _groups(tmp_path, {"watches": _g()})
    with pytest.raises(P.PublishError) as e:
        P.record(u"咖啡", u"https://coffee%s/" % P.HOST_SUFFIX, project_id=PROJECT,
                 published_date="2026-10-04", root=str(tmp_path),
                 output=str(tmp_path / "output"))
    assert u"site_groups" in str(e.value)


def test_record_group_writes_every_member_with_the_same_project(tmp_path):
    """一次记一组：它们本来就是同一个站。
    一篇一篇记会给出一组自相矛盾的账——A 有地址而 B 没有。"""
    _recorded(tmp_path, members=(u"咖啡", u"茶"))
    url = u"https://watches%s/" % P.HOST_SUFFIX
    P.record_group("watches", url, project_id=PROJECT, published_date="2026-10-04",
                   root=str(tmp_path), output=str(tmp_path / "output"))
    for m in (u"咖啡", u"茶"):
        site = json.loads((tmp_path / "output" / m / "data.json")
                          .read_text(encoding="utf-8"))["site"]
        assert site["project_id"] == PROJECT
        assert site["group"] == "watches"
        stem = SLUGS[m]
        assert site["url"].endswith(u"/%s/%s.html" % (stem, stem))
        assert site["path"] == u"/%s/%s.html" % (stem, stem)


# ------------------------------------------------------------------ 账本与 pending

def test_pending_groups_names_a_stale_landing_page(tmp_path):
    """group_sha 与记录不一致 → 整组要重发。这一条不在 `pending()` 里，
    因为那里按篇看，而这里没有任何一篇是旧的。"""
    _recorded(tmp_path)
    output = str(tmp_path / "output")
    P.record_group("watches", u"https://watches%s/" % P.HOST_SUFFIX, project_id=PROJECT,
                   published_date="2026-10-04", root=str(tmp_path), output=output)
    assert P.pending_groups(root=str(tmp_path), output=output) == []
    _landing(tmp_path, "watches", extra_refs=(u"coffee/images/02_b.jpg",))
    rows = P.pending_groups(root=str(tmp_path), output=output)
    assert [r["group"] for r in rows] == ["watches"]
    assert not any(x["topic"] == u"咖啡" for x in P.pending(root=str(tmp_path), output=output)), \
        u"落地页变了却被算成某一篇的问题——两级指纹的意义就是分清是谁变的"


def test_ledger_carries_a_site_column(tmp_path):
    """一行仍是一篇，但**站点**那一列才是发布单位。
    没有它，读者看到 29 行会以为要发 29 次。"""
    _recorded(tmp_path)
    P.record_group("watches", u"https://watches%s/" % P.HOST_SUFFIX, project_id=PROJECT,
                   published_date="2026-10-04", root=str(tmp_path),
                   output=str(tmp_path / "output"))
    text = P.ledger_text(root=str(tmp_path), output=str(tmp_path / "output"))
    assert u"| 领域 | 站点 |" in text
    assert u"| 咖啡 | watches |" in text
