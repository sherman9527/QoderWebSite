# -*- coding: utf-8 -*-
"""W-146 发布半边：出包、账本、核对。

这批测试要钉住的是**"包就是验证过的那份产物"**这件事：
出包过程一旦允许改内容（改名、压图、重写 src），发出去的东西和闸门判过的东西
就不是同一个东西了，而"闸门全绿"这句话从此只对本地那份成立。

10-04 合站之后整体改写（memo D-34）。**改写而不是删除**，因为要钉的东西一条没少：

· 逐字节相同、只带页面引用的图、排除采集器自己的账本、超限就拒绝且不压图、
  非 ASCII 只报不改、record 必须带 projectId 与真实发布日、账本是派生物——全留。
· 退场的只有"改写「返回主页」"那一族：`test_pack_rewrites_the_back_home_link_*`
  与 `test_pack_refuses_when_the_back_home_marker_is_not_exactly_one`。
  它们钉的是"一篇一站时 `../index.html` 会指回自己"。合站之后那个相对路径
  正好指向同一个包里的组落地页，**没有任何东西需要改写**，
  于是"标记必须恰好出现一次"这条最脆的字符串契约（属性顺序一变就全线 pack 失败）
  随之作废。顶上它位置的是 `test_pack_copies_the_page_byte_for_byte`：
  现在**每一个**字节都不许动，这条第一次是全称的。
· 发布单位从"篇"变成"组"，所以 `pack` → `pack_group`、地址从站根变成深链。
"""
import io
import json
import os

import pytest

import publish as P

PROJECT = u"01a0d6cd-4074-721d-b827-e9ee83c8de56"   # 任意一个真实形状的 projectId，测试里只要求它被记下来
GROUP = "watches"
GROUP_URL = u"https://watches" + P.HOST_SUFFIX + u"/"
GOOD_URL = u"https://watches" + P.HOST_SUFFIX + u"/coffee/coffee.html"
DEEP = GOOD_URL


def _topic(root, topic, slug, images=("01_a.jpg", "02_b.jpg"), extra=()):
    """在 tmp_path 下摆出和真实仓库一样的四层：
    output/<领域>/、config/topics/、config/site_groups.json、（调用方摆的）dist/。"""
    d = root / "output" / topic
    (d / "images").mkdir(parents=True)
    refs = []
    for name in images:
        (d / "images" / name).write_bytes(b"\xff\xd8\xff\xe0" + name.encode() + b"0" * 3000)
        refs.append(u'<img src="images/%s" alt="x"/>' % name)
    for name in extra:                       # 不被任何页引用的文件
        (d / "images" / name).write_bytes(b"\xff\xd8\xff\xe0" + b"0" * 500)
    page = (u'<html><head><title>t</title></head><body>'
            u'<a class="backhome-link" href="../index.html">全部专题</a>%s</body></html>'
            % u"".join(refs))
    (d / ("%s.html" % topic)).write_text(page, encoding="utf-8")
    (d / "data.json").write_text(json.dumps({
        "topic": topic, "category": u"测试", "tags": [topic],
        "generated_date": "2026-09-25", "created_date": "2026-09-20",
        "theme": {"token": "coffee-roast"}, "sections": [], "sources": [],
    }, ensure_ascii=False), encoding="utf-8")
    cfg = root / "config" / "topics" / (topic + ".json")
    cfg.parent.mkdir(parents=True, exist_ok=True)
    cfg.write_text(json.dumps({"topic": topic, "slug": slug}, ensure_ascii=False),
                   encoding="utf-8")
    _add_member(root, topic)
    return d


def _groups_file(root, extra_groups=(GROUP,)):
    p = root / "config" / "site_groups.json"
    doc = json.loads(p.read_text(encoding="utf-8")) if p.is_file() else {"groups": {}}
    for g in extra_groups:
        doc["groups"].setdefault(g, {
            "display_name": g, "members": [], "project_id": None, "site_id": None,
            "url": None, "access": "private", "published_date": None, "group_sha": None})
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    return doc


def _add_member(root, topic, group=GROUP):
    doc = _groups_file(root)
    if topic not in doc["groups"][group]["members"]:
        doc["groups"][group]["members"].append(topic)
        (root / "config" / "site_groups.json").write_text(
            json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")


def _landing(root, group=GROUP, hrefs=()):
    """手写一份落地页。这些测试测的是"搬字节"，不跑 node：
    落地页本身对不对由 test_groups.py 与 shot.mjs 管。"""
    dest = root / "dist" / group
    dest.mkdir(parents=True, exist_ok=True)
    cards = u"".join(u'<a class="card" href="%s">x</a>' % h for h in hrefs)
    (dest / "index.html").write_text(u"<html><body>%s</body></html>" % cards,
                                     encoding="utf-8")
    return dest / "index.html"


def _pack(root, group=GROUP, **kw):
    kw.setdefault("render", False)
    return P.pack_group(group, root=str(root), **kw)


@pytest.fixture
def tree(tmp_path):
    return tmp_path          # 仓库根：下面有 output/、config/、web_list.md、dist/


# ---------------------------------------------------------------- 包就是那份产物

def test_pack_copies_the_page_byte_for_byte(tree):
    """包里那份 HTML 必须和 `output/` 里那份**逐字节相同**。

    改名、压图、重写 src 任何一个都算破约：闸门判的是本地那份，
    发出去的是"另一个版本"，那"闸门全绿"这句话就只对本地成立。
    合站之前这里还留着一个例外（「返回主页」那处要改写）。现在没有例外了。
    """
    d = _topic(tree, u"咖啡", "coffee")
    _landing(tree, hrefs=("coffee/coffee.html",))
    src = io.open(str(d / u"咖啡.html"), "rb").read()
    p = _pack(tree)
    assert io.open(os.path.join(p["dir"], "coffee", "coffee.html"), "rb").read() == src


def test_pack_images_stay_byte_for_byte(tree):
    d = _topic(tree, u"咖啡", "coffee")
    _landing(tree, hrefs=("coffee/coffee.html",))
    p = _pack(tree)
    for name in ("01_a.jpg", "02_b.jpg"):
        got = io.open(os.path.join(p["dir"], "coffee", "images", name), "rb").read()
        assert got == io.open(str(d / "images" / name), "rb").read()


def test_pack_carries_only_the_images_the_page_references(tree):
    _topic(tree, u"咖啡", "coffee", images=("01_a.jpg",), extra=("02_never_used.jpg",))
    _landing(tree, hrefs=("coffee/coffee.html",))
    p = _pack(tree)
    names = sorted(os.listdir(os.path.join(p["dir"], "coffee", "images")))
    assert names == ["01_a.jpg"], u"把没人引用的图也发出去了：%s" % names


def test_pack_excludes_the_collectors_own_ledgers(tree):
    """`manifest.json` / `search-stats.json` / `.srcsha` 是采集器的内部账本
    （检索词、召回统计、源图哈希），页面不引用它们，发出去只是把实现细节公开。"""
    d = _topic(tree, u"咖啡", "coffee",
               extra=("manifest.json", "search-stats.json", "01_a.jpg.srcsha"))
    (d / "images.prev").mkdir()
    (d / "images.prev" / "old.jpg").write_bytes(b"\xff\xd8\xff\xe0" + b"0" * 300)
    _landing(tree, hrefs=("coffee/coffee.html",))
    p = _pack(tree)
    all_files = [os.path.relpath(os.path.join(r, f), p["dir"]).replace(os.sep, "/")
                 for r, _, fs in os.walk(p["dir"]) for f in fs]
    assert not [f for f in all_files if "manifest" in f or "search-stats" in f
                or "images.prev" in f or f.endswith(".srcsha")], all_files


def test_group_sha_is_not_the_single_topic_sha(tree):
    """两级指纹（D-b）。组指纹必须**覆盖到单篇之外**的东西，
    否则落地页的变化（成员增减、模板改动）永远看不见——
    线上那一组是旧的，而每一篇都说自己新，谁都不报警。"""
    _topic(tree, u"咖啡", "coffee")
    _landing(tree, hrefs=("coffee/coffee.html",))
    p = _pack(tree)
    assert p["sha"] != P.own_sha(u"咖啡", str(tree / "output"), str(tree)), \
        u"组指纹退化成单篇指纹了"


def test_pack_reports_non_ascii_names_without_rewriting_them(tree):
    """文件名不是 ASCII 时**只报不改**。

    为什么不改：`sites_artifact_unsafe` 那次我同时改了体积和名字，没归因；
    在归因之前先造一套改名方案，等于把一个还没证实的假设焊进产物结构。
    """
    _topic(tree, u"咖啡", "coffee", images=(u"03_椭圆曲线.jpg",))
    _landing(tree, hrefs=("coffee/coffee.html",))
    p = _pack(tree)
    assert any(u"03_椭圆曲线.jpg" in r for r in p["non_ascii"]), p["non_ascii"]
    assert os.path.isfile(os.path.join(p["dir"], "coffee", "images", u"03_椭圆曲线.jpg")), \
        u"报告归报告，却悄悄把名字改了"


def test_pack_refuses_when_over_the_limit_and_does_not_compress(tree):
    """超工作上限就报错退出。绝不"顺手压一下图"——那等于发一份比验证过的更差的产物，
    而且没人会知道图被压过。压缩是**入库**那一步的事（`images.fit_bytes`）。"""
    d = _topic(tree, u"咖啡", "coffee")
    big = d / "images" / "01_a.jpg"
    big.write_bytes(b"\xff\xd8\xff\xe0" + b"0" * (2 * 1024 * 1024))
    _landing(tree, hrefs=("coffee/coffee.html",))
    with pytest.raises(P.TooLarge) as e:
        _pack(tree, max_mib=1)
    assert u"1 MiB" in str(e.value), \
        u"报的是写死的 50 MiB 而不是这次生效的上限，调小限制时人会看不懂为什么被拒"
    assert u"分裂" in str(e.value), u"只说了拒绝、没说出路（分裂这个组）"
    assert not os.path.isdir(str(tree / "dist" / GROUP)), \
        u"超限了还把成品包留在盘上——半成品会被下一次 prepare_site 误用"


def test_the_working_ceiling_is_below_the_documented_one():
    """40 而不是 50：我们真正上传过的最大包是 29.3 MB，50 MiB 是文档给的数、没实测过。
    留 20% 余量比贴着天花板跑稳——撞一次 `artifact_size_exceeded` 的代价是半个站。"""
    assert P.WORKING_LIMIT_MIB < P.LIMIT_MIB
    assert P.WORKING_LIMIT_MIB == 40


# ---------------------------------------------------------------------- pending

def test_pending_lists_a_topic_once_and_not_again_after_record(tree):
    """`pending` 是 agent 的工作清单：内容没变就不该再出现。

    这条防的是 AGENTS 第 5 步——改一次模板要把全部领域 `--offline` 重渲染，
    朴素挂钩的后果是几十次发布。所以判据必须是内容指纹，不是"跑过没有"。
    """
    _topic(tree, u"咖啡", "coffee")
    _landing(tree, hrefs=("coffee/coffee.html",))
    assert [x["topic"] for x in P.pending(root=str(tree))] == [u"咖啡"]
    P.record_group(GROUP, GROUP_URL, root=str(tree), project_id=PROJECT,
                   published_date=u"2026-09-25")
    assert P.pending(root=str(tree)) == [], u"记录过、内容也没变，还在待发布清单上"


def test_pending_tells_the_agent_which_project_to_update(tree):
    """`pending` 要带上 project_id 和组名：agent 才知道往哪个站更新、该重发哪个组。
    从没发过的篇 project_id 为空，走建新站那条路。"""
    _topic(tree, u"咖啡", "coffee")
    _topic(tree, u"香奈儿", "chanel")
    _landing(tree, hrefs=("coffee/coffee.html", "chanel/chanel.html"))
    P.record_group(GROUP, GROUP_URL, root=str(tree), project_id=PROJECT,
                   published_date=u"2026-09-25")
    page = tree / "output" / u"咖啡" / u"咖啡.html"
    page.write_text(page.read_text(encoding="utf-8") + u"<!--又改了一版-->",
                    encoding="utf-8")     # 刚记过的篇不在清单上，改了内容才回来
    items = {x["topic"]: x for x in P.pending(root=str(tree))}
    assert items[u"咖啡"]["project_id"] == PROJECT, \
        u"清单上没带 projectId，agent 只能凭记忆认站——错站事故的来源"
    assert items[u"咖啡"]["url"], u"已发布过的篇要标出旧地址，才看得出是更新不是新建"
    assert items[u"咖啡"]["group"] == GROUP, u"不说是哪个组，agent 不知道该重发哪个站"


# ---------------------------------------------------------------------- record

def test_record_writes_the_site_block_and_regenerates_the_ledger(tree):
    """`web_list.md` 是**派生物**：它只能由 `data.json` 重算出来。

    一份东西活在几处迟早不一致——这条教训已经付过两次学费
    （示意图的三处、封面声明）。所以这里连"手改一行"都要能被发现。"""
    _topic(tree, u"咖啡", "coffee")
    _landing(tree, hrefs=("coffee/coffee.html",))
    P.record_group(GROUP, GROUP_URL, root=str(tree), access=u"public",
                   project_id=PROJECT, published_date=u"2026-09-25")
    data = json.loads(io.open(str(tree / "output" / u"咖啡" / "data.json"),
                              encoding="utf-8").read())
    assert data["site"]["url"] == GOOD_URL
    assert data["site"]["published_date"]
    ledger = io.open(str(tree / "web_list.md"), encoding="utf-8").read()
    assert u"coffee/coffee.html" in ledger and u"咖啡" in ledger
    assert P.check(root=str(tree)) == [], u"刚写完就自相矛盾，说明两处不是一个来源"


def test_record_leaves_data_json_in_the_canonical_format(tree):
    """`data.json` 只有一个作者：`generate._save`（原子写、indent=1）。

    这不是洁癖。2026-09-25 我第一次 `record` 之后，那份文件在 git 里 diff 出
    1727 行——全是被缩进重排掉、内容一字未改的旧行。下次谁要看"这一篇到底改了
    什么"，就得在噪声里找；而噪声里找东西的结果是找漏。
    """
    import generate as G
    d = _topic(tree, u"咖啡", "coffee")
    dp = str(d / "data.json")
    G._save(dp, json.load(io.open(dp, encoding="utf-8")))   # 先交给正统作者过一遍
    canonical_text = io.open(dp, encoding="utf-8").read()
    _landing(tree, hrefs=("coffee/coffee.html",))
    P.record_group(GROUP, GROUP_URL, root=str(tree), project_id=PROJECT,
                   published_date=u"2026-09-25")
    after = io.open(dp, "rb").read()
    assert after != canonical_text.encode("utf-8"), u"record 什么都没写，这条测试是空转"

    # record 之后的**字节**必须就是 _save 会写出的字节。注意不能"再存一遍再比"——
    # 那会先把格式归一化掉，恰好把我要找的那个差异洗掉（我第一版就是这么自欺的）。
    twin = str(d / "twin.json")
    G._save(twin, json.loads(after.decode("utf-8")))
    assert after == io.open(twin, "rb").read(), \
        u"record 用的不是 _save 那套格式：整份文件被重排，git 里多出上千行噪声 diff"

    back = json.loads(canonical_text)
    body = json.loads(after.decode("utf-8"))
    body.pop("site", None)
    assert body == back, u"record 动的不止 site 那一个键"


def test_record_refuses_a_host_that_merely_starts_like_ours(tmp_path):
    """`https://watches-anything.evil.tld/` 从前是收的——检查写成了前缀匹配。

    这条检查存在的理由是我拼错过地址，而前缀匹配对"发到了别人的站"零防御。
    """
    _topic(tmp_path, u"咖啡", "coffee")
    _landing(tmp_path, hrefs=("coffee/coffee.html",))
    with pytest.raises(P.PublishError):
        P.record(u"咖啡", u"https://watches-anything.evil.tld/coffee/coffee.html",
                 sha=u"x" * 16, root=str(tmp_path), project_id=PROJECT,
                 published_date=u"2026-09-25")


def test_record_refuses_to_invent_a_publish_date(tmp_path):
    """发布日不能拿渲染日顶：`--offline` 重跑一次 generated_date 就变一次，
    公开账本里那一列会变成会自己改口的数字。"""
    _topic(tmp_path, u"咖啡", "coffee")
    with pytest.raises(P.PublishError):
        P.record(u"咖啡", GOOD_URL, sha=u"x" * 16, root=str(tmp_path),
                 project_id=PROJECT)


def test_record_refuses_a_site_without_a_project_id(tree):
    """不给 projectId 就拒绝记账。宁可一条都不记，也不要一条"知道 URL、不知道
    是哪个站"的记录——那种记录会让下一次更新凭记忆认站。"""
    _topic(tree, u"咖啡", "coffee")
    with pytest.raises(P.PublishError):
        P.record(u"咖啡", GOOD_URL, sha="deadbeef", root=str(tree),
                 published_date=u"2026-09-25")


def test_record_rejects_a_url_that_is_not_the_groups_address(tree):
    """地址必须由**组**认得出来。

    真实事故（2026-09-25）：我把 18 条 URL 拼成 `https://<slug>/<suffix>`
    （多一个斜杠、少一个连字符），`check` 照样报"账实一致"——因为账本和
    data.json 是同一个错处生成的，两处自洽不等于正确。
    """
    _topic(tree, u"咖啡", "coffee")
    _landing(tree, hrefs=("coffee/coffee.html",))
    with pytest.raises(P.PublishError):
        P.record(u"咖啡", u"https://watches/gtqdc11h6po.qoder.website/coffee/coffee.html",
                 sha="x", root=str(tree), project_id=PROJECT,
                 published_date=u"2026-09-25")
    P.record(u"咖啡", GOOD_URL, sha="x", root=str(tree), project_id=PROJECT,
             published_date=u"2026-09-25")


def test_site_record_carries_the_project_it_belonged_to(tree):
    """账上光有 URL 不够，必须记下**这是哪个站**（projectId）。

    真实事故：我报告"已把站点设为 public"，那次 `update_access_policy` 打的是
    早先建的另一个草稿站（`llm-crypto-notes`），不是刚发布的那个。多站并存时，
    只写 URL 等于下一次更新靠记忆认站——而记忆会认错。
    """
    _topic(tree, u"咖啡", "coffee")
    _landing(tree, hrefs=("coffee/coffee.html",))
    P.record_group(GROUP, GROUP_URL, root=str(tree), project_id=PROJECT,
                   published_date=u"2026-09-25")
    data = json.loads(io.open(str(tree / "output" / u"咖啡" / "data.json"),
                              encoding="utf-8").read())
    assert data["site"]["project_id"] == PROJECT
    assert data["site"]["group"] == GROUP


def test_check_notices_a_hand_edited_ledger(tree):
    _topic(tree, u"咖啡", "coffee")
    _landing(tree, hrefs=("coffee/coffee.html",))
    P.record_group(GROUP, GROUP_URL, root=str(tree), project_id=PROJECT,
                   published_date=u"2026-09-25")
    path = str(tree / "web_list.md")
    s = io.open(path, encoding="utf-8").read()
    io.open(path, "w", encoding="utf-8").write(
        s + u"\n| 手工加的 | 组 | 假链接 | x | y | z |\n")
    drift = P.check(root=str(tree))
    assert drift, u"手改了账本却没人发现——那它就不是派生物，是第二份真相"


def test_slug_is_declared_not_inferred(tree):
    """slug 决定公开地址（合站之后它是深链的路径段），必须是人写下来的东西。

    从中文领域名自动转写（拼音/哈希）会让地址没人能念、也没人能预期，
    而一旦发出去就改不掉（改名等于换 URL）。缺 slug 就报错，不猜。
    """
    _topic(tree, u"咖啡", "coffee")
    cfg = tree / "config" / "topics" / u"咖啡.json"
    data = json.loads(io.open(str(cfg), encoding="utf-8").read())
    data.pop("slug")
    cfg.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    _landing(tree, hrefs=("coffee/coffee.html",))
    with pytest.raises(P.NoSlug):
        _pack(tree)
    assert not os.path.isdir(str(tree / "dist" / GROUP)), \
        u"缺 slug 却已经打出成品包——半成品会被下一次 prepare_site 误用"


# ---------------------------------------------------------------- W-153 主页

def _published(tree, topic, slug, url, group=GROUP):
    _topic(tree, topic, slug)
    dp = tree / "output" / topic / "data.json"
    data = json.loads(dp.read_text(encoding="utf-8"))
    stem = url.rstrip("/").rsplit("/", 2)[-2]
    data["site"] = {"url": url, "project_id": "01a0d72c-8734-704e-9710-e0b07be48b20",
                    "group": group, "path": u"/%s/%s.html" % (stem, stem),
                    "content_sha": "abc", "published_date": "2026-09-25",
                    "access": "public"}
    dp.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")


def _home(tree, hrefs):
    d = tree / "dist" / "home"
    d.mkdir(parents=True, exist_ok=True)
    cards = u"".join(u'<a class="card" href="%s">x</a>' % h for h in hrefs)
    (d / "index.html").write_text(u"<html><body>%s</body></html>" % cards, encoding="utf-8")


def test_check_home_names_a_card_that_points_at_the_wrong_place(tree):
    """主页恰恰是人唯一会点进去的那个链接。`dist/home/` 是 gitignore 的中间产物，
    `record` 不重建它、G-14 也不读它——于是"文章都重发了、主页还链着旧地址"
    这件事没有任何一处会报警。"""
    _published(tree, u"咖啡", "coffee", DEEP)
    P.write_ledger(root=str(tree))
    _home(tree, ["https://coffee-OLDHOST.example.com/"])
    msgs = P.check_home(root=str(tree))
    assert any(u"咖啡" in m or "coffee" in m for m in msgs), \
        u"链错地址没被报出来：%s" % (msgs,)


def test_check_home_is_quiet_when_the_build_matches_the_ledger(tree):
    _published(tree, u"咖啡", "coffee", DEEP)
    P.write_ledger(root=str(tree))
    _home(tree, [DEEP])
    assert P.check_home(root=str(tree)) == []


def test_a_missing_hosted_build_is_a_note_not_drift(tree):
    """`dist/home/index.html` 本来就要到发布前才构建。
    把它算进 `check()` 的 drift 会让 rc=1，于是"还没构建"变成"账对不上"——
    那是逼人去关闸门。"""
    _published(tree, u"咖啡", "coffee", DEEP)
    P.write_ledger(root=str(tree))
    msgs = P.check_home(root=str(tree))
    assert msgs, u"没构建也该说一句，不然没人知道自己缺这一步"
    assert P.check(root=str(tree)) == [], u"缺构建被算成了 drift（会让 rc=1）"
