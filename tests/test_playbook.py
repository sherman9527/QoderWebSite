# -*- coding: utf-8 -*-
"""`publish.py playbook`：把"还差哪些发布动作"打成一份 agent 能照着敲的清单。

发布这条链路的后半段只有 agent 能走（托管工具是 MCP，脚本调不到），所以脚本能做的
最有用的事不是"假装发布"，而是**把每一步的具体参数算好**——包括该往哪个 projectId
更新。参数留在人脑或聊天记录里，下一次会话就得重新猜一遍，而猜错的后果是
把 A 篇发到 B 篇的站上（这件事已经真做过一次，见 memo 09-25）。

10-04 合站之后**四条全部改写**（memo D-34）：清单的单位从"篇"变成"组"，
`slug` 键换成 `group`，`webDirectory` 从 `dist/<篇slug>` 变成 `dist/<组>`。
留一条新的：主页重建必须排在删旧站**之前**——那是迁移期最容易做反的一步。
"""
import io
import json

import pytest

import publish as P

PROJECT = u"01a0d72c-11eb-74d5-9178-d732514e54fa"
GROUP = "watches"
GROUP_URL = u"https://watches" + P.HOST_SUFFIX + u"/"


def _topic(root, topic, slug, group=GROUP):
    out = root / "output" / topic
    (out / "images").mkdir(parents=True)
    (out / "images" / "01_a.jpg").write_bytes(b"\xff\xd8\xff\xe0" + b"0" * 4000)
    (out / ("%s.html" % topic)).write_text(
        u'<html><head><title>t</title></head>'
        u'<body><img src="images/01_a.jpg"/></body></html>', encoding="utf-8")
    data = {u"topic": topic, u"category": u"测试", u"tags": [topic],
            u"generated_date": "2026-09-25", u"created_date": "2026-09-20",
            u"theme": {"token": "coffee-roast"}, u"sections": [], u"sources": []}
    (out / "data.json").write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    cfg = root / "config" / "topics" / (topic + ".json")
    cfg.parent.mkdir(parents=True, exist_ok=True)
    cfg.write_text(json.dumps({u"topic": topic, u"slug": slug}, ensure_ascii=False),
                   encoding="utf-8")
    _member(root, topic, group)
    return out


def _member(root, topic, group=GROUP):
    p = root / "config" / "site_groups.json"
    doc = json.loads(p.read_text(encoding="utf-8")) if p.is_file() else {"groups": {}}
    g = doc["groups"].setdefault(group, {
        "display_name": group, "members": [], "project_id": None, "site_id": None,
        "url": None, "access": "private", "published_date": None, "group_sha": None})
    if topic not in g["members"]:
        g["members"].append(topic)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    return g


def _landing(root, group=GROUP, hrefs=()):
    dest = root / "dist" / group
    dest.mkdir(parents=True, exist_ok=True)
    cards = u"".join(u'<a class="card" href="%s">x</a>' % h for h in hrefs)
    (dest / "index.html").write_text(u"<html><body>%s</body></html>" % cards,
                                     encoding="utf-8")


def test_playbook_gives_the_exact_prepare_arguments_for_a_new_group(tmp_path):
    _topic(tmp_path, u"咖啡", "coffee")
    _landing(tmp_path, hrefs=("coffee/coffee.html",))
    steps = P.playbook(root=str(tmp_path))
    assert len(steps) == 2, u"一个组 + 一条主页"
    s = steps[0]
    assert s["action"] == u"new-site", u"没有 projectId 的组应该是建新站"
    assert s["webDirectory"] == u"dist/watches"
    assert s["group"] == GROUP
    assert s["members"] == [u"咖啡"], u"清单不列成员，agent 不知道该逐篇 curl 哪些深链"
    assert s["project_id"] == u""
    prep = [x for x in s["steps"] if u"prepare_site" in x]
    assert prep, u"清单里必须给出带参数的调用"
    assert u", projectId=" not in prep[0], u"新站的 prepare_site 不该带 projectId"
    assert u"没有 projectId" in prep[0], u"没说清这一步是在建新站"



def test_playbook_routes_an_update_to_its_own_project(tmp_path):
    """已发布过的组必须带着 projectId 出场——这是防串台的全部依赖。"""
    _topic(tmp_path, u"咖啡", "coffee")
    _landing(tmp_path, hrefs=("coffee/coffee.html",))
    P.record_group(GROUP, GROUP_URL, root=str(tmp_path), project_id=PROJECT,
                   published_date=u"2026-09-24")
    # 记完之后内容又变了，才会重新出现在清单上
    page = tmp_path / "output" / u"咖啡" / u"咖啡.html"
    page.write_text(page.read_text(encoding="utf-8") + u"<!--又改了一版-->",
                    encoding="utf-8")
    _landing(tmp_path, hrefs=("coffee/coffee.html",))
    s = P.playbook(root=str(tmp_path))[0]
    assert s["action"] == u"update-site"
    assert s["project_id"] == PROJECT
    assert s["url"] == GROUP_URL


def test_playbook_omits_groups_whose_published_copy_is_current(tmp_path):
    """内容没变就不该催发布——否则改一次模板会催出几十次没有内容的重发。"""
    _topic(tmp_path, u"咖啡", "coffee")
    _landing(tmp_path, hrefs=("coffee/coffee.html",))
    P.pack_group(GROUP, root=str(tmp_path), render=False)
    P.record_group(GROUP, GROUP_URL, root=str(tmp_path), project_id=PROJECT,
                   published_date=u"2026-09-25")
    assert P.playbook(root=str(tmp_path)) == [], \
        u"内容没变还催着发布，等于让模板改动触发几十次发布"


def test_playbook_names_the_home_site_as_a_separate_step(tmp_path):
    """主页站是第 N+1 个站：它链的是各篇的线上深链，所以任何一组重发之后它都要跟着重发。
    清单里必须**排在最后**，否则 agent 先推主页，卡片上就少了这一轮刚发的地址。"""
    _topic(tmp_path, u"咖啡", "coffee")
    _topic(tmp_path, u"香奈儿", "chanel")
    _landing(tmp_path, hrefs=("coffee/coffee.html", "chanel/chanel.html"))
    s = P.playbook(root=str(tmp_path))
    assert len(s) == 2, u"两组同属一个组 → 一个组 + 主页，清单应该是两条"
    assert s[-1]["group"] == u"home", u"主页站必须排在最后一条"
    assert s[-1]["webDirectory"] == u"dist/home"
    assert s[0]["group"] != u"home"


def test_the_cli_prints_the_group_list(capsys, tmp_path, monkeypatch):
    """`main()` 里那行格式化以前少传了一个参数（`%d` 收到组名），
    而所有测试都直接调 `playbook()`，没人跑过 CLI——一跑就 traceback。
    清单是给人和 agent 照着敲的，打印这条路本身也得有测试。"""
    _topic(tmp_path, u"咖啡", "coffee")
    _landing(tmp_path, hrefs=("coffee/coffee.html",))
    monkeypatch.setattr(P, "ROOT", str(tmp_path))
    rc = P.main(["playbook"])
    out = capsys.readouterr().out
    assert rc == 0, u"playbook 的文本输出这条路没被跑过"
    assert out.startswith(u"1. watches"), out[:80]
    assert u"2. home" in out, u"主页站没有作为最后一条打印出来"


def test_playbook_never_invents_an_address_for_an_unpublished_group(tmp_path):
    """没发过的组**没有地址可报**。
    拼一个 `<组>-<后缀>` 的假地址再去 curl 它、record 它，正是主机名校验要防的那类错
    ——而我把它搬进过防错工具本身（memo 09-25）。真实地址只能来自 get_site。"""
    _topic(tmp_path, u"咖啡", "coffee")
    _landing(tmp_path, hrefs=("coffee/coffee.html",))
    s = P.playbook(root=str(tmp_path))[0]
    assert s["url"] == u"", u"清单替我编了一个地址：%s" % s["url"]
    assert not any(GROUP_URL in x for x in s["steps"]), \
        u"步骤里出现了没发生过的地址，agent 会拿它去 curl 并当成 200 的证据"
    assert any(u"get_site" in x for x in s["steps"]), u"没说清真实地址从哪儿来"


def test_playbook_orders_record_then_rebuild_then_delete(tmp_path):
    """迁移期最容易做反的两步，顺序有两个理由：

    · **record-group 必须在重建 hosted 主页之前**——主页卡片读的是各篇 data.json 的
      `site.url`。先重建再记账，主页上这一组的卡片还是旧的，而清单看着每一步都做了。
    · **删旧站必须排在最后**——先删的话，每删一个，线上主页就多一张 404 卡片，
      一直到迁移结束才有人发现。
    """
    _topic(tmp_path, u"咖啡", "coffee")
    _landing(tmp_path, hrefs=("coffee/coffee.html",))
    steps = P.playbook(root=str(tmp_path))[0]["steps"]
    text = u"\n".join(steps)

    def at(*needles):
        hits = [i for i, x in enumerate(steps) if all(n in x for n in needles)]
        assert hits, u"清单里找不到含 %r 的一步：\n%s" % (needles, text)
        return hits[0]

    recorded = at(u"record-group")
    rebuilt = at(u"重建 hosted 主页")
    deleted = at(u"才删掉被这一组吸收的旧单篇站")
    assert recorded < rebuilt, u"先重建主页再记账，主页读到的还是旧地址"
    assert rebuilt < deleted, u"删旧站排在重建主页之前，中间每一秒都有 404 卡片"
