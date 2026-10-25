# -*- coding: utf-8 -*-
"""线上主页的验收：抓 live 那张卡表，逐条链接确认 200。

为什么不复用 `publish.py check`：它比的是**本地** `dist/home` 和账本，
证的是"我构建的这份和账上记的一致"。而用户点的是线上那一份——
它是不是刚发出去的那版、每条卡片指不指得通，`check` 一个字都没说。

主页是 29 张卡的**入口**，也是最容易被旧版冻住的地方（D-33 那次就是它）。
所以这里只问两件事，且每次都问：卡数对不对、每一条是不是 200。
"""
import io
import json
import os
import re
import sys
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import publish as P  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # scripts/ 比仓库根深一层
HOME = json.loads(io.open(os.path.join(ROOT, "config", "home_site.json"),
                          encoding="utf-8").read())


def get(url):
    try:
        r = urllib.request.urlopen(url)
        return r.getcode(), r.read()
    except Exception as e:
        return getattr(e, "code", None) or type(e).__name__, b""


def main():
    want = sum(len(P.members_of(g, ROOT)) for g in P.all_groups(ROOT))
    code, body = get(HOME["url"])
    cards = [h for h in re.findall(r'<a class="card"[^>]*href="([^"]+)"',
                                   body.decode("utf-8", "replace"))
             if h.startswith("http")]
    sys.stdout.write(u"%s %s\n    HTTP %s，卡 %d / 账上应 %d\n" % (
        u"✓" if code == 200 and len(cards) == want else u"✗",
        HOME["url"], code, len(cards), want))
    bad = []
    for h in cards:
        c, _ = get(h if "%" in h else urllib.parse.quote(h, safe=":/?&="))
        if c != 200:
            bad.append((c, h))
    for c, h in bad:
        sys.stdout.write(u"    %s  %s\n" % (c, h))
    sys.stdout.write(u"    卡片全部 200\n" if not bad
                     else u"    坏 %d 条\n" % len(bad))
    return 0 if (code == 200 and len(cards) == want and not bad) else 1


if __name__ == "__main__":
    sys.exit(main())
