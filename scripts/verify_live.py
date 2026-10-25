# -*- coding: utf-8 -*-
"""发完一个组之后的**上线验收**：深链、图、以及"线上就是本地产物"。

为什么要有这个而不是手 curl：迁移有 13 组，手抄的判据会一组比一组松。
三件事必须每次都问：
  1 落地页与每个成员深链是否 200；
  2 每个页面里引用的每张图是否 200（中文文件名要 percent-encode，
    相对路径要按**页面所在目录**解析——按页面本身解析会全 404，我踩过）；
  3 剥掉平台注入的 watermark 脚本之后，线上字节是否等于本地打包件。

第 3 条是"包就是验证过的那份产物"这句话在**线上**的唯一证据。
不判它，前面两条只能证明"有个页面在那儿"，不能证明是哪一个版本。
"""
import argparse
import hashlib
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
INJECT = re.compile(r"<script[^>]*data-qoder-watermark.*?</script>", re.S)


def get(url):
    try:
        r = urllib.request.urlopen(url)
        return r.getcode(), r.read()
    except Exception as e:
        return (getattr(e, "code", None) or type(e).__name__), b""


def check_group(group, root=ROOT):
    """返回 (是否全通过, 逐条结果)。

    **不要求账上已有 url**：这一步是"该不该记账"的证据，顺序不能倒过来。
    深链由组名算出来（`group_host` 是确定函数），所以没记录也照样能验。
    """
    dest = os.path.join(root, "dist", group)
    rows = []
    ok = True

    if not os.path.isdir(dest):
        return False, [(u"包", u"缺目录", u"dist/%s 不在，先 pack" % group, u"")]

    landing = P.landing_page(group, root)
    url = u"https://%s/index.html" % P.group_host(group)
    code, body = get(url)
    same = _eq(body, os.path.join(dest, "index.html"))
    ok = ok and code == 200 and same
    rows.append((u"落地页", code, u"逐字节一致" if same else u"内容不一致", url))

    html = body.decode("utf-8", "replace")
    cards = re.findall(r'<a class="card"[^>]*href="([^"]+)"', html)
    for topic in P.members_of(group, root):
        stem = P.topic_stem(topic, os.path.join(root, "config", "topics"))
        want = u"%s/%s.html" % (stem, stem)
        if want not in cards:
            ok = False
            rows.append((topic, u"缺卡", want, u""))
        deep = P.deep_link(group, topic, root)
        code, page = get(deep)
        same = _eq(page, os.path.join(dest, stem, u"%s.html" % stem))
        local = os.path.join(dest, stem)
        refs = [m for m in re.findall(r'<img[^>]*src="([^"]+)"',
                                      page.decode("utf-8", "replace"))
                if not m.startswith(("data:", "http"))]
        bad = []
        for r in refs:
            u2 = urllib.parse.urljoin(deep.rsplit("/", 1)[0] + u"/", urllib.parse.quote(r))
            c2, _ = get(u2)
            if c2 != 200:
                bad.append(u"%s→%s" % (r, c2))
        good = code == 200 and same and not bad
        ok = ok and good
        rows.append((topic, code,
                     (u"逐字节一致" if same else u"内容不一致")
                     + (u"；图 %d 张全 200" % len(refs) if not bad
                        else u"；图坏 %d 张：%s" % (len(bad), u" ".join(bad[:3]))),
                     deep))
    return ok, rows


def _eq(live_bytes, disk_path):
    if not live_bytes or not os.path.isfile(disk_path):
        return False
    stripped = INJECT.sub("", live_bytes.decode("utf-8", "replace")).encode("utf-8")
    return hashlib.sha256(stripped).hexdigest() == \
        hashlib.sha256(io.open(disk_path, "rb").read()).hexdigest()


def main():
    ap = argparse.ArgumentParser(description=u"组站上线验收")
    ap.add_argument("groups", nargs="+")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    all_ok = True
    report = {}
    for g in a.groups:
        ok, rows = check_group(g)
        all_ok = all_ok and ok
        report[g] = {"ok": ok, "rows": [list(r) for r in rows]}
        if not a.json:
            sys.stdout.write(u"%s %s\n" % (u"✓" if ok else u"✗", g))
            for name, code, detail, url in rows:
                sys.stdout.write(u"    %-24s %-6s %s\n" % (name, code, detail))
    if a.json:
        sys.stdout.write(json.dumps(report, ensure_ascii=False, indent=1) + u"\n")
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
