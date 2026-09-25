# -*- coding: utf-8 -*-
"""W-146 发布半边：出包、账本、核对。

这批测试要钉住的是**"包就是验证过的那份产物"**这件事：
出包过程一旦允许改内容（改名、压图、重写 src），发出去的东西和闸门判过的东西
就不是同一个东西了，而"闸门全绿"这句话从此只对本地那份成立。
"""
import hashlib
import io
import json
import os

import pytest

import publish as P

GOOD_URL = u"https://coffee" + P.HOST_SUFFIX + u"/"

PROJECT = u"01a0d6cd-4074-721d-b827-e9ee83c8de56"   # 任意一个真实形状的 projectId，测试里只要求它被记下来


def _topic(root, topic, slug, images=("01_a.jpg", "02_b.jpg"), extra=()):
    """在 tmp_path 下摆出和真实仓库一样的三层：output/<领域>/、config/topics/。"""
    out = root / "output"
    d = out / topic
    (d / "images").mkdir(parents=True)
    refs = []
    for name in images:
        (d / "images" / name).write_bytes(b"\xff\xd8\xff\xe0" + name.encode() + b"0" * 3000)
        refs.append(u'<img src="images/%s" alt="x"/>' % name)
    for name in extra:                       # 不被任何页引用的文件
        (d / "images" / name).write_bytes(b"\xff\xd8\xff\xe0" + b"0" * 500)
    page = u"<html><head><!--template-fingerprint:%s--></head><body>%s</body></html>" % (
        json.dumps({"rev": "1", "blocks": ["prose"]}), u"".join(refs))
    (d / ("%s.html" % topic)).write_text(page, encoding="utf-8")
    (d / "data.json").write_text(json.dumps({
        "topic": topic, "category": u"测试", "tags": [topic],
        "generated_date": "2026-09-25", "created_date": "2026-09-20",
        "theme": {"token": "coffee-roast"}, "sections": [], "sources": [],
    }, ensure_ascii=False), encoding="utf-8")
    cfg = d.parent.parent / "config" / "topics" / (topic + ".json")
    cfg.parent.mkdir(parents=True, exist_ok=True)
    cfg.write_text(json.dumps({"topic": topic, "slug": slug}, ensure_ascii=False),
                   encoding="utf-8")
    return d


@pytest.fixture
def tree(tmp_path):
    return tmp_path          # 仓库根：下面有 output/、config/topics/、web_list.md、dist/


def test_pack_copies_the_page_byte_for_byte(tree):
    """包里那份 HTML 必须和 `output/` 里那份**逐字节相同**。

    改名、压图、重写 src 任何一个都算破约：闸门判的是本地那份，
    发出去的是"另一个版本"，那"闸门全绿"这句话就只对本地成立。
    """
    d = _topic(tree, u"咖啡", "coffee")
    src = io.open(str(d / u"咖啡.html"), "rb").read()
    p = P.pack(u"咖啡", root=str(tree))
    assert io.open(os.path.join(p["dir"], "index.html"), "rb").read() == src


def test_pack_carries_only_the_images_the_page_references(tree):
    _topic(tree, u"咖啡", "coffee", images=("01_a.jpg",),
           extra=("02_never_used.jpg",))
    p = P.pack(u"咖啡", root=str(tree))
    names = sorted(os.listdir(os.path.join(p["dir"], "images")))
    assert names == ["01_a.jpg"], u"把没人引用的图也发出去了：%s" % names


def test_pack_excludes_the_collectors_own_ledgers(tree):
    """`manifest.json` / `search-stats.json` 是采集器的内部账本（检索词、召回统计），
    页面不引用它们，发出去只是把实现细节公开。"""
    d = _topic(tree, u"咖啡", "coffee", extra=("manifest.json", "search-stats.json"))
    (d / "images.prev").mkdir()
    (d / "images.prev" / "old.jpg").write_bytes(b"\xff\xd8\xff\xe0" + b"0" * 300)
    p = P.pack(u"咖啡", root=str(tree))
    all_files = [os.path.relpath(os.path.join(r, f), p["dir"])
                 for r, _, fs in os.walk(p["dir"]) for f in fs]
    assert not [f for f in all_files if "manifest" in f or "search-stats" in f
                or "images.prev" in f], all_files


def test_pack_refuses_when_over_the_limit_and_does_not_compress(tree):
    """超上限就报错退出。绝不"顺手压一下图"——那等于发一份比验证过的更差的产物，
    而且没人会知道图被压过。"""
    d = _topic(tree, u"咖啡", "coffee")
    big = d / "images" / "01_a.jpg"
    big.write_bytes(b"\xff\xd8\xff\xe0" + b"0" * (2 * 1024 * 1024))
    with pytest.raises(P.TooLarge) as e:
        P.pack(u"咖啡", root=str(tree), max_mib=1)
    assert u"1 MiB" in str(e.value), \
        u"报的是写死的 50 MiB 而不是这次生效的上限，调小限制时人会看不懂为什么被拒"
    assert not os.path.isdir(os.path.join(str(tree), "dist", "coffee")), \
        u"超限了还把包留在盘上——半成品会被下一次 prepare_site 误用"


def test_pack_reports_non_ascii_names_without_rewriting_them(tree):
    """文件名不是 ASCII 时**只报不改**。

    为什么不改：`sites_artifact_unsafe` 那次我同时改了体积和名字，没归因；
    在归因之前先造一套改名方案，等于把一个还没证实的假设焊进产物结构。
    """
    d = _topic(tree, u"咖啡", "coffee", images=(u"03_椭圆曲线.jpg",))
    p = P.pack(u"咖啡", root=str(tree))
    assert p["non_ascii"] == [u"03_椭圆曲线.jpg"], p["non_ascii"]
    assert os.path.isfile(os.path.join(p["dir"], "images", u"03_椭圆曲线.jpg")), \
        u"报告归报告，却悄悄把名字改了"


def test_pending_lists_a_topic_once_and_not_again_after_record(tree):
    """`pending` 是 agent 的工作清单：内容没变就不该再出现。

    这条防的是 AGENTS 第 5 步——改一次模板要 19 篇全部 `--offline` 重渲染，
    朴素挂钩的后果是 19 次发布。所以判据必须是内容指纹，不是"跑过没有"。
    """
    _topic(tree, u"咖啡", "coffee")
    assert [x["topic"] for x in P.pending(root=str(tree))] == [u"咖啡"]
    p = P.pack(u"咖啡", root=str(tree))
    P.record(u"咖啡", GOOD_URL, sha=p["sha"], root=str(tree),
             project_id=PROJECT, published_date=u"2026-09-25")
    assert P.pending(root=str(tree)) == [], u"记录过、内容也没变，还在待发布清单上"


def test_record_writes_the_site_block_and_regenerates_the_ledger(tree):
    """`web_list.md` 是**派生物**：它只能由 `data.json` 重算出来。

    一份东西活在几处迟早不一致——这条教训已经付过两次学费
    （示意图的三处、封面声明）。所以这里连"手改一行"都要能被发现。"""
    _topic(tree, u"咖啡", "coffee")
    p = P.pack(u"咖啡", root=str(tree))
    P.record(u"咖啡", GOOD_URL, sha=p["sha"], root=str(tree),
             access=u"public", project_id=PROJECT, published_date=u"2026-09-25")
    data = json.loads(io.open(str(tree / "output" / u"咖啡" / "data.json"),
                              encoding="utf-8").read())
    assert data["site"]["url"] == GOOD_URL
    assert data["site"]["published_date"]
    ledger = io.open(str(tree / "web_list.md"), encoding="utf-8").read()
    assert GOOD_URL.split(u"/")[2] in ledger and u"咖啡" in ledger
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
    p = P.pack(u"咖啡", root=str(tree))
    P.record(u"咖啡", GOOD_URL, sha=p["sha"], root=str(tree),
             project_id=PROJECT, published_date=u"2026-09-25")
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
    """`https://coffee-anything.evil.tld/` 从前是收的——检查写成了前缀匹配。

    这条检查存在的理由是我拼错过地址，而前缀匹配对"发到了别人的站"零防御。
    """
    _topic(tmp_path, u"咖啡", "coffee")
    with pytest.raises(P.PublishError):
        P.record(u"咖啡", u"https://coffee-anything.evil.tld/", sha=u"x" * 16,
                 root=str(tmp_path), project_id=PROJECT,
                 published_date=u"2026-09-25")


def test_record_refuses_to_invent_a_publish_date(tmp_path):
    """发布日不能拿渲染日顶：`--offline` 重跑一次 generated_date 就变一次，
    公开账本里那一列会变成会自己改口的数字。"""
    _topic(tmp_path, u"咖啡", "coffee")
    with pytest.raises(P.PublishError):
        P.record(u"咖啡", GOOD_URL, sha=u"x" * 16, root=str(tmp_path),
                 project_id=PROJECT)


def test_check_notices_a_hand_edited_ledger(tree):
    _topic(tree, u"咖啡", "coffee")
    p = P.pack(u"咖啡", root=str(tree))
    P.record(u"咖啡", GOOD_URL, sha=p["sha"], root=str(tree),
             project_id=PROJECT, published_date=u"2026-09-25")
    path = str(tree / "web_list.md")
    s = io.open(path, encoding="utf-8").read()
    io.open(path, "w", encoding="utf-8").write(s + u"\n| 手工加的 | 假链接 | https://x.example |\n")
    drift = P.check(root=str(tree))
    assert drift, u"手改了账本却没人发现——那它就不是派生物，是第二份真相"


def test_site_record_carries_the_project_it_belonged_to(tree):
    """账上光有 URL 不够，必须记下**这是哪个站**（projectId）。

    真实事故：我报告"已把站点设为 public"，那次 `update_access_policy` 打的是
    早先建的另一个草稿站（`llm-crypto-notes`），不是刚发布的那个。多站并存时，
    只写 URL 等于下一次更新靠记忆认站——而记忆会认错。
    """
    _topic(tree, u"咖啡", "coffee")
    p = P.pack(u"咖啡", root=str(tree))
    P.record(u"咖啡", GOOD_URL, sha=p["sha"],
             root=str(tree), project_id=PROJECT, published_date=u"2026-09-25")
    data = json.loads(io.open(str(tree / "output" / u"咖啡" / "data.json"),
                              encoding="utf-8").read())
    assert data["site"]["project_id"] == u"01a0d6cd-4074-721d-b827-e9ee83c8de56"


def test_pending_tells_the_agent_which_project_to_update(tree):
    """`pending` 是 agent 的工作清单：已发布过的篇要把 project_id 一起给它，
    它才知道该往哪个站更新；从没发过的篇 project_id 为空，走建新站那条路。"""
    _topic(tree, u"咖啡", "coffee")
    _topic(tree, u"香奈儿", "chanel")
    p = P.pack(u"咖啡", root=str(tree))
    P.record(u"咖啡", GOOD_URL, sha=p["sha"], root=str(tree),
             project_id=PROJECT, published_date=u"2026-09-25")
    page = tree / "output" / u"咖啡" / u"咖啡.html"
    page.write_text(page.read_text(encoding="utf-8") + u"<!--又改了一版-->",
                    encoding="utf-8")     # 刚记过的篇不在清单上，改了内容才回来
    items = {x["topic"]: x for x in P.pending(root=str(tree))}
    assert items[u"咖啡"]["project_id"] == PROJECT, \
        u"清单上没带 projectId，agent 只能凭记忆认站——错站事故的来源"
    assert items[u"咖啡"]["url"], u"已发布过的篇要标出旧地址，才看得出是更新不是新建"
    assert items[u"香奈儿"]["project_id"] == u""


def test_record_refuses_a_site_without_a_project_id(tree):
    """不给 projectId 就拒绝记账。宁可一条都不记，也不要一条"知道 URL、不知道
    是哪个站"的记录——那种记录会让下一次更新凭记忆认站。"""
    _topic(tree, u"咖啡", "coffee")
    with pytest.raises(P.PublishError):
        P.record(u"咖啡", GOOD_URL, sha="deadbeef",
                 root=str(tree), published_date=u"2026-09-25")


def test_record_rejects_a_url_that_is_not_that_slugs_address(tree):
    """地址必须由 slug 认得出而来。

    真实事故（2026-09-25）：我把 18 条 URL 拼成 `https://<slug>/<suffix>`
    （多一个斜杠、少一个连字符），`check` 照样报"账实一致"——因为账本和
    data.json 是同一个错处生成的，两处自洽不等于正确。
    """
    _topic(tree, u"咖啡", "coffee")
    with pytest.raises(P.PublishError):
        P.record(u"咖啡", u"https://coffee/gtqdc11h6po.qoder.website", sha="x",
                 root=str(tree), project_id=PROJECT, published_date=u"2026-09-25")
    P.record(u"咖啡", u"https://coffee-gtqdc11h6po.qoder.website/", sha="x",
             root=str(tree), project_id=PROJECT, published_date=u"2026-09-25")


def test_slug_is_declared_not_inferred(tree):
    """slug 决定公开地址，必须是人写下来的东西。

    从中文领域名自动转写（拼音/哈希）会让地址长得没人能念、也没人能预期，
    而一旦发布出去就改不掉（改名等于换 URL）。缺 slug 就报错，不猜。
    """
    d = _topic(tree, u"咖啡", "coffee")
    cfg = tree / "config" / "topics" / u"咖啡.json"
    data = json.loads(io.open(str(cfg), encoding="utf-8").read())
    data.pop("slug")
    cfg.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(P.NoSlug):
        P.pack(u"咖啡", root=str(tree))
    assert not os.path.isdir(str(tree / "dist" / "coffee")), \
        u"缺 slug 却已经建出包目录——半成品会被下一次 prepare_site 误用"
