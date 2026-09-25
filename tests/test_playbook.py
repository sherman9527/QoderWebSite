# -*- coding: utf-8 -*-
"""`publish.py playbook`：把"还差哪些发布动作"打成一份 agent 能照着敲的清单。

发布这条链路的后半段只有 agent 能走（托管工具是 MCP，脚本调不到），所以脚本能做的
最有用的事不是"假装发布"，而是**把每一步的具体参数算好**——包括该往哪个 projectId
更新。参数留在人脑或聊天记录里，下一次会话就得重新猜一遍，而猜错的后果是
把 A 篇发到 B 篇的站上（这件事我已经真做过一次，见 memo 09-25）。
"""
import io
import json

import pytest

import publish as P

PROJECT = u"01a0d72c-11eb-74d5-9178-d732514e54fa"
HOME_URL = u"https://coffee" + P.HOST_SUFFIX + u"/"


def _topic(root, topic, slug, with_site=None):
    out = root / "output" / topic
    (out / "images").mkdir(parents=True)
    (out / "images" / "01_a.jpg").write_bytes(b"\xff\xd8\xff\xe0" + b"0" * 4000)
    (out / ("%s.html" % topic)).write_text(
        u'<html><head><!--template-fingerprint:{"rev":"1"}--></head>'
        u'<body><img src="images/01_a.jpg"/></body></html>', encoding="utf-8")
    data = {u"topic": topic, u"category": u"测试", u"tags": [topic],
            u"generated_date": "2026-09-25", u"created_date": "2026-09-20",
            u"theme": {"token": "coffee-roast"}, u"sections": [], u"sources": []}
    if with_site:
        data[u"site"] = with_site
    (out / "data.json").write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    cfg = root / "config" / "topics" / (topic + ".json")
    cfg.parent.mkdir(parents=True, exist_ok=True)
    cfg.write_text(json.dumps({u"topic": topic, u"slug": slug}, ensure_ascii=False),
                   encoding="utf-8")
    return out


def test_playbook_gives_the_exact_prepare_arguments_for_a_new_topic(tmp_path):
    _topic(tmp_path, u"咖啡", "coffee")
    steps = P.playbook(root=str(tmp_path))
    assert len(steps) == 2, u"一篇 + 一条主页"
    s = steps[0]
    assert s["action"] == u"new-site", u"没有 projectId 的篇应该是建新站"
    assert s["webDirectory"] == u"dist/coffee"
    assert s["slug"] == "coffee"
    assert s["project_id"] == u""
    assert any(u"prepare_site" in x for x in s["steps"]), u"清单里必须给出带参数的调用"


def test_playbook_routes_an_update_to_its_own_project(tmp_path):
    """已发布过的篇必须带着 projectId 出场——这是防串台的全部依赖。"""
    _topic(tmp_path, u"咖啡", "coffee", with_site={
        u"url": HOME_URL, u"project_id": PROJECT,
        u"slug": "coffee", u"content_sha": u"deadbeefdeadbeef",
        u"published_date": u"2026-09-24", u"access": u"public"})
    s = P.playbook(root=str(tmp_path))[0]
    assert s["action"] == u"update-site"
    assert s["project_id"] == PROJECT
    assert s["url"] == HOME_URL


def test_playbook_omits_topics_whose_published_copy_is_current(tmp_path):
    _topic(tmp_path, u"咖啡", "coffee")
    p = P.pack(u"咖啡", root=str(tmp_path))
    P.record(u"咖啡", HOME_URL, sha=p["sha"],
             root=str(tmp_path), project_id=PROJECT, published_date=u"2026-09-25")
    assert P.playbook(root=str(tmp_path)) == [], u"内容没变还催着发布，等于让模板改动触发 19 次发布"


def test_playbook_names_the_home_site_as_a_separate_step(tmp_path):
    """主页站是第 N+1 个站：它链的是各篇的线上地址，所以任何一篇重发之后它都要跟着重发。
    清单里必须**排在最后**，否则 agent 先推主页，卡片上就少了这一轮刚发的地址。"""
    _topic(tmp_path, u"咖啡", "coffee")
    _topic(tmp_path, u"香奈儿", "chanel")
    s = P.playbook(root=str(tmp_path))
    assert len(s) == 3, u"两篇 + 主页，清单应该是三条"
    assert s[-1]["slug"] == u"home", u"主页站必须排在最后一条"
    assert s[-1]["webDirectory"] == u"dist/home"
    assert s[0]["slug"] != u"home" and s[1]["slug"] != u"home"
