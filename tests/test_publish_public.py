# -*- coding: utf-8 -*-
"""公开快照的排除清单与自查（scripts/publish_public.py）。

`.qoder.site` 是托管平台在 `prepare_site` 时写回仓库根的站点描述符，
里面**内嵌整份 index.html 的 base64**——一个文件等于一份页面副本。
它既不是产物也不该进仓库，而 09-26 那批重发一次就生成 22 个。
"""
import io
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import publish_public as PP  # noqa: E402

DESCRIPTOR = u".浪琴 · 知识专题.qoder.site"


def _exclude_patterns():
    with io.open(os.path.join(ROOT, "config", "public_exclude.txt"), encoding="utf-8") as f:
        return [l.strip() for l in f if l.strip() and not l.startswith("#")]


def test_the_site_descriptor_never_enters_the_public_snapshot():
    """排除清单要真的能匹配上它——`output/` 那一类规则盖不住仓库根的文件。"""
    pats = _exclude_patterns()
    hit = [p for p in pats if re.search(p, DESCRIPTOR)]
    assert hit, u"`.qoder.site` 描述符没被任何一条排除规则盖住：%s" % pats


def test_the_self_check_names_a_descriptor_left_behind():
    """就算有人删了排除规则，推之前的自查也得点名它。

    这条测试防的是"排除清单和自查清单各写一半"：09-25 那次 review 抓到过同类问题
    （pack 的排除与快照的排除不同源）。
    """
    assert PP.is_scratch(DESCRIPTOR), u"自查认不出这是现场文件"
    assert PP.is_scratch(u"output/咖啡/咖啡.html.pending")
    assert not PP.is_scratch(u"output/咖啡/咖啡.html"), u"正常产物被判成现场文件"
