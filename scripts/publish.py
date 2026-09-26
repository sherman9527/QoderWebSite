# -*- coding: utf-8 -*-
"""发布这条链路的**确定性半边**：出包、记 URL、核对账本。

为什么只有半边：托管工具（`prepare_site` / `publish_site`）只有 agent 能调——
`qodercli` 没有 sites 子命令，插件文档里也没有 CI/REST 路径，唯一能让纯脚本发布的
路子是拿 PAT 去逆向起那个 stdio MCP 服务，不做。所以这个脚本负责"能测的那一半"
（包、指纹、账本），把"要联网要授权的那一半"留成一份机器可读的清单给 agent。

一条贯穿全部函数的约定：**包就是验证过的那份产物**。不改名、不压图、不重写 src——
一旦允许改内容，发出去的东西和闸门判过的就不是同一个东西，"闸门全绿"这句话
从此只对本地那份成立。非 ASCII 文件名只**报告**不修改，因为
`sites_artifact_unsafe` 那次我同时改了体积和名字、没有归因；在归因之前
先造一套改名方案，等于把一个没证实的假设焊进产物结构。
"""
import argparse
import hashlib
import io
import json
import os
import re
import shutil
import sys
from urllib import parse as urlparse

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT = os.path.join(ROOT, "output")
CONFIG = os.path.join(ROOT, "config", "topics")
DIST = os.path.join(ROOT, "dist")
LEDGER = os.path.join(ROOT, "web_list.md")

# 托管侧实测到的上限（2026-09-25）：Worker artifact ≤ 50 MiB。
LIMIT_MIB = 50
# 采集器的内部账本：页面不引用它们，发出去只是把实现细节公开。
SKIP = ("manifest.json", "search-stats.json")
IMG_EXT = (".jpg", ".jpeg", ".png", ".webp", ".gif", ".svg")

# 公开地址的实测形态是 `<slug>-<账号后缀>.qoder.website`。后缀由托管侧按账号分配，
# 换账号要改这里或设 KE_HOST_SUFFIX。playbook 只用它拼**建议**地址；
# 真实地址永远以 prepare_site / get_site 返回的 host 为准——这里拼错了不影响发布，
# 但 record 的主机名校验会拒绝把错地址写进账本。
HOST_SUFFIX = os.environ.get("KE_HOST_SUFFIX", u"-gtqdc11h6po.qoder.website")


class PublishError(Exception):
    pass


class NoSlug(PublishError):
    pass


class TooLarge(PublishError):
    pass


def _read(path):
    return io.open(path, encoding="utf-8").read().strip()


def _read_json(path):
    return json.load(io.open(path, encoding="utf-8"))


def _write_json(path, obj):
    """`data.json` 只有一个作者：`generate._save`（原子写、indent=1）。

    另起一套 `json.dump` 的代价是真实的——2026-09-25 第一次 `record` 把一份
    1700 多行的文件整份重排，git diff 里全是被缩进改掉、内容一字未动的旧行。
    延迟导入是为了绕开 generate ↔ publish 的循环引用。
    """
    from generate import _save
    _save(path, obj)


def page_path(topic, output=OUTPUT):
    return os.path.join(output, topic, "%s.html" % topic)


def slug_of(topic, config=CONFIG):
    """公开地址里那一段。必须是人写进大纲的，不从中文领域名猜。

    自动转写（拼音/哈希）会让地址没人能念、也没人能预期，而一旦发出去就改不掉
    ——改名等于换 URL，读者手里的链接、别人收藏的页面全废。
    """
    p = os.path.join(config, topic + ".json")
    if not os.path.isfile(p):
        raise NoSlug(u"没有大纲 %s，无从确定 slug" % p)
    slug = (_read_json(p).get("slug") or u"").strip()
    if not slug:
        raise NoSlug(u"%s 没有声明 slug。发布地址要人写下来，不要从领域名自动转写" % topic)
    return slug


def _img_refs(html):
    return [m for m in re.findall(r'<img[^>]*\bsrc="([^"]+)"', html)
            if not m.startswith(("http", "data:"))]


def package_files(topic, output=OUTPUT):
    """这个主题**要发出去的文件清单**：那一页 HTML + 它真引用到的图。

    清单由页面自己说了算（读 `<img src>`），不由目录遍历说了算——
    否则 `images/` 里任何历史残留都会跟着上公网。
    """
    out_dir = os.path.join(output, topic)
    page = os.path.join(out_dir, "%s.html" % topic)
    if not os.path.isfile(page):
        raise PublishError(u"%s 没有产物页面 %s" % (topic, page))
    html = io.open(page, encoding="utf-8").read()
    got = [("%s.html" % topic, page)]
    for ref in _img_refs(html):
        if not ref.startswith("images/"):
            # 原先是 continue：这种引用既不进包、也不计体积、也不进指纹，
            # 于是"包 = 验证过的那份产物"这句话悄悄不成立了，而且没人报警。
            raise PublishError(u"%s 的页面引用了 images/ 之外的 %s——"
                              u"要么它是漏出去的产物，要么页面被手改过" % (topic, ref))
        base = os.path.basename(ref)
        if base in SKIP:
            continue
        src = os.path.join(out_dir, ref.replace("/", os.sep))
        if os.path.isfile(src):
            got.append(("images/" + base, src))
    seen, uniq = set(), []
    for rel, src in got:
        if rel not in seen:
            seen.add(rel)
            uniq.append((rel, src))
    return uniq


def fingerprint(topic, output=OUTPUT):
    """这一篇"该发出去的内容"的指纹：对**包内每个文件的字节**求哈希再汇总。

    用包字节而不是 `data.json` 或 HTML 单独一份，是因为要回答的问题是
    "线上那份和本份是不是同一个东西"——那正好是包的内容。
    `generated_date` 不参与：它每次重渲染都变，拿它当指纹等于让 19 篇永远待发布。
    """
    h = hashlib.sha256()
    for rel, src in sorted(package_files(topic, output), key=lambda x: x[0]):
        h.update(rel.encode("utf-8"))
        h.update(hashlib.sha256(io.open(src, "rb").read()).hexdigest().encode("ascii"))
    return h.hexdigest()[:16]


def pack(topic, root=ROOT, dist=None, max_mib=LIMIT_MIB, output=None,
         force=False):
    """把一篇打成 ASCII 检查过、体积核对过的包。**不改任何一个字节。**"""
    output = output or os.path.join(root, "output")
    config = os.path.join(root, "config", "topics")
    slug = slug_of(topic, config)
    files = package_files(topic, output)
    total = sum(os.path.getsize(s) for _, s in files)
    if total > max_mib * 1024 * 1024:
        # 不在这里压图：那等于发一份比验证过的更差的产物，而且没人知道图被压过。
        raise TooLarge(
            u"%s 的包 %.1f MB，超过这次生效的上限 %d MiB。"
            u"要么拆成更小的站，要么按类别合站——不许悄悄压图来凑数"
            % (topic, total / 1048576.0, max_mib))
    dest = os.path.join(dist or os.path.join(root, "dist"), slug)
    sha = fingerprint(topic, output)
    marker = os.path.join(dest, ".packed-sha")
    if not force and os.path.isfile(marker) and _read(marker) == sha:
        # 内容一个字节没变，就不重新出包。AGENTS 第 5 步改一次模板要 19 篇全部
        # `--offline` 重渲染，没有这一道，每次都会重新打包 19 次、
        # 并且 `pending` 永远不为空——那时没人会去看它到底说了什么。
        return {"topic": topic, "slug": slug, "dir": dest, "bytes": 0,
                "files": 0, "non_ascii": [], "sha": sha, "skipped": True}
    shutil.rmtree(dest, ignore_errors=True)
    os.makedirs(os.path.join(dest, "images"), exist_ok=True)
    non_ascii = []
    for rel, src in files:
        dst = os.path.join(dest, "index.html") if not rel.startswith("images/") \
            else os.path.join(dest, rel.replace("/", os.sep))
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(src, dst)
        if not os.path.basename(dst).isascii():
            non_ascii.append(os.path.basename(dst))
    io.open(marker, "w", encoding="utf-8").write(sha)
    return {"topic": topic, "slug": slug, "dir": dest, "bytes": total,
            "files": len(files), "non_ascii": non_ascii, "sha": sha,
            "skipped": False}


def _site_of(topic, output):
    dp = os.path.join(output, topic, "data.json")
    if not os.path.isfile(dp):
        return {}
    return (_read_json(dp).get("site") or {})


def pending(root=ROOT, output=None):
    """agent 的工作清单：哪些篇的线上版和本份不是同一个东西。

    判据是指纹而不是"这次跑没跑过"——AGENTS 第 5 步改一次模板要把 19 篇全部
    `--offline` 重渲染，朴素挂钩的代价就是 19 次发布。
    """
    output = output or os.path.join(root, "output")
    if not os.path.isdir(output):
        return []
    out = []
    for topic in sorted(os.listdir(output)):
        if not os.path.isfile(page_path(topic, output)):
            continue
        try:
            sha = fingerprint(topic, output)
            slug = slug_of(topic, os.path.join(root, "config", "topics"))
        except PublishError as e:
            out.append({"topic": topic, "slug": "", "error": str(e),
                        "stale": True, "url": u""})
            continue
        site = _site_of(topic, output)
        if site.get("content_sha") != sha:
            out.append({"topic": topic, "slug": slug, "sha": sha,
                        "url": site.get("url") or u"",
                        "project_id": site.get("project_id") or u"",
                        "stale": bool(site.get("url")), "error": u""})
    return out


def record(topic, url, sha=None, root=ROOT, output=None, access=u"private",
           published_date=None, project_id=None):
    """把一次真实发布的结果写回产物。`sha` 不传就现算——但调用方（agent）
    手里已经有 pack 给的那个，传进来才能钉住"发出去的正是这份"。

    `project_id` 必填：URL 说不出它属于哪个站。我犯过的错是把访问策略改到了
    另一个草稿站上（凭"我刚改过"的记忆，没核 siteId），所以每次发布都必须把
    托管侧返回的 projectId 落进账本，下一次更新才知道往哪儿发。

    `published_date` 同样必填：发布日是事实，不是可推算的量。
    """
    output = output or os.path.join(root, "output")
    if not project_id:
        raise PublishError(u"record 需要 --project-id：只记 URL 的话，下一次更新"
                           u"会凭记忆认站，而我已经把策略改到错的站上去过一次")
    if not published_date:
        # 原先缺省取 generated_date，那是**渲染日**：--offline 重跑一次就变一次，
        # 等于往公开账本的「发布日」列里写一个会自己改口的数字。
        raise PublishError(u"record 需要 --published-date：发布日只能是真实发布那天，"
                          u"不能拿 generated_date 顶")
    dp = os.path.join(output, topic, "data.json")
    if not os.path.isfile(dp):
        raise PublishError(u"没有 %s，先跑 generate.py %s" % (dp, topic))
    data = _read_json(dp)
    slug = data.get("slug") or slug_of(topic, os.path.join(root, "config", "topics"))
    host = urlparse.urlparse(url)[1]
    # **整名相等**，不是前缀。写成 startswith(slug + "-") 的话
    # `https://coffee-anything.evil.tld/` 也收，而这条检查存在的理由就是我真拼错过地址。
    if host != slug + HOST_SUFFIX:
        raise PublishError(u"地址 %s 的主机名不是该篇的那个（应为 %s%s）。"
                          u"我拼出过 https://<slug>/<后缀>；账本与 data.json 同源，"
                          u"这种错 check 自己发现不了。换账号请设 KE_HOST_SUFFIX。"
                          % (url, slug, HOST_SUFFIX))
    data["site"] = {
        "url": url,
        "project_id": project_id,
        "slug": slug,
        "content_sha": sha or fingerprint(topic, output),
        "published_date": published_date,
        "access": access,
    }
    _write_json(dp, data)
    write_ledger(root=root, output=output)
    return data["site"]


def playbook(root=ROOT, output=None):
    """agent 的执行清单：每篇一条，**最后一条是主页站**。

    为什么要有这个而不是让人自己拼参数：发布的后半段只有 agent 能走（托管是 MCP，
    脚本调不到），而 `prepare_site` 要 projectRoot / webDirectory / slug / projectId
    四个值同时正确。projectId 猜错的后果是把 A 篇发到 B 篇的站上——这件事我 09-25
    真做过一次（把访问策略改到了另一个草稿站）。所以清单必须自己算出来，
    而不是靠"上次会话里我记得"。
    """
    output = output or os.path.join(root, "output")
    repo = os.path.dirname(os.path.abspath(root)) if not os.path.isabs(root) else os.path.abspath(root)
    out = []
    for row in pending(root=root, output=output):
        if row.get("error"):
            out.append({"topic": row["topic"], "slug": u"", "action": u"blocked",
                        "project_id": u"", "url": u"", "webDirectory": u"",
                        "steps": [u"先补 slug：%s" % row["error"]]})
            continue
        pid = row.get("project_id") or u""
        # 没发过的站**没有地址可报**。原先这里拼一个 `<slug>-<后缀>` 的假地址，
        # 然后第 7 步去 curl 它、第 8 步把它 record 进账本——那正是加主机名校验要防的
        # 那类错，只是搬到了清单里。真实地址只能来自 prepare_site / get_site 返回的 host。
        url = row.get("url") or u""
        wd = u"dist/" + row["slug"]
        prep = (u"prepare_site(projectRoot=%s, webDirectory=%s, slug=%s, "
                u"displayName=%s%s)"
                % (repo, wd, row["slug"], row["topic"],
                   u", projectId=" + pid if pid else u""))
        steps = [
            u"pack：%s" % row["slug"],
            prep + u"  ← 没有 projectId 就是建新站",
            u"get_publish_status 直到 canPublish: true（这一步不能跳，"
            u"queued/running 都不是 ready）",
            u"publish_site",
            u"get_publish_status 直到 published: true 且 active_release_id 非空",
            u"update_access_policy(siteId, mode=public, confirmPublic=true)"
            u"  ← 发布 ≠ 可见：新站默认 private，public 要单独授权",
            (u"curl -s -o /dev/null -w '%%{http_code}' %s  必须是 200" % url) if url else
            u"从 get_site 返回的 host 取真实地址，再 curl 到 200（脚本不替你猜新站地址）",
            u"python scripts/publish.py record \"%s\" %s --project-id <projectId> "
            u"--access public --published-date <真实发布那天>"
            % (row["topic"], url or u"<上一步拿到的地址>"),
        ]
        out.append({"topic": row["topic"], "slug": row["slug"],
                    "action": u"update-site" if pid else u"new-site",
                    "project_id": pid, "url": url, "webDirectory": wd, "steps": steps})

    if not out:
        # 没有一篇要重发，主页也就没有跟着发的理由——否则改一次模板的清单会永远挂着一条
        return out
    home_pid = u""
    hp = os.path.join(root, "config", "home_site.json")
    if os.path.isfile(hp):
        home_pid = (_read_json(hp).get("project_id") or u"").strip()
    # 没建过站就没有地址可报；拼一个 `<slug>-<后缀>` 的假地址会被当成真的去 record
    home_url = u""
    out.append({
        "topic": u"主页站（把各篇连起来的那个站）", "slug": u"home",
        "action": u"update-site" if home_pid else u"new-site",
        "project_id": home_pid,
        "url": (_read_json(hp).get("url") or home_url) if home_pid else home_url,
        "webDirectory": u"dist/home",
        "steps": [
            u"python scripts/build_index.py --variant hosted"
            u"  ← 不带 --json：--json 只打印条目、不渲染",
            u"prepare_site(projectRoot=%s, webDirectory=dist/home, slug=knoweverything%s)"
            % (repo, u", projectId=" + home_pid if home_pid else u""),
            u"get_publish_status 直到 canPublish: true",
            u"publish_site",
            u"get_publish_status 直到 published: true",
            u"update_access_policy(siteId, mode=public, confirmPublic=true)",
            u"curl 主页必须 200，且卡片数等于已发布篇数",
            u"把 projectId 写回 config/home_site.json（它没有 data.json 可住）",
        ]})
    return out


def ledger_rows(root=ROOT, output=None):
    output = output or os.path.join(root, "output")
    rows = []
    if not os.path.isdir(output):
        return rows
    for topic in sorted(os.listdir(output)):
        dp = os.path.join(output, topic, "data.json")
        if not os.path.isfile(dp) or not os.path.isfile(page_path(topic, output)):
            continue
        data = _read_json(dp)
        site = data.get("site") or {}
        if not site.get("url"):
            continue
        try:
            now = fingerprint(topic, output)
        except PublishError:
            now = u"?"
        rows.append({"topic": topic, "url": site["url"],
                     "published_date": site.get("published_date") or u"?",
                     "access": site.get("access") or u"private",
                     "drift": u"已更新未发布" if now != site.get("content_sha") else u"一致"})
    return rows


def ledger_text(root=ROOT, output=None):
    rows = ledger_rows(root, output)
    lines = [u"# 线上地址清单",
             u"",
             u"**这个文件是派生物，不要手改。**权威源是各篇 `output/<领域>/data.json` 的",
             u"`site` 字段；本文件由 `python scripts/publish.py record ...` 整体重生成，",
             u"`validate.py` 的 G-14 判的就是「这个文件与 data.json 是否一致」。",
             u"",
             u"| 领域 | 线上地址 | 发布日 | 访问 | 本地 vs 线上 |",
             u"|---|---|---|---|---|"]
    if not rows:
        lines.append(u"| （还没有任何一篇发布成功） | | | | |")
    for r in rows:
        lines.append(u"| %s | <%s> | %s | %s | %s |"
                     % (r["topic"], r["url"], r["published_date"], r["access"], r["drift"]))
    return u"\n".join(lines) + u"\n"


def write_ledger(root=ROOT, output=None):
    io.open(os.path.join(root, "web_list.md"), "w", encoding="utf-8").write(
        ledger_text(root, output))


def check(root=ROOT, output=None):
    """账实核对。返回不一致的清单（空 = 一致）。G-14 用的就是这个。"""
    output = output or os.path.join(root, "output")
    path = os.path.join(root, "web_list.md")
    want = ledger_text(root, output)
    rows = ledger_rows(root, output)
    if not rows:
        return [] if not os.path.isfile(path) else [u"web_list.md 存在但没有任何已发布记录"]
    if not os.path.isfile(path):
        return [u"有已发布记录却没有 web_list.md（缺派生物）"]
    have = io.open(path, encoding="utf-8").read()
    if have != want:
        return [u"web_list.md 与 data.json 的 site 字段不一致——它是派生物，"
                u"手改无效，请跑 `python scripts/publish.py ledger`"]
    return []


def check_home(root=ROOT, output=None):
    """线上版主页的卡片链接与账本对得上吗。返回提示清单（**不是** drift）。

    为什么单独一条函数而不是塞进 `check()`：`dist/home/index.html` 是 gitignore 的
    中间产物，`record` 不重建它、G-14 也不读它——于是"文章都重发了、主页还链着旧指纹"
    这件事没有任何一处会报警，而主页恰恰是人唯一会点进去的那个链接。
    但它**没构建**是正常状态（发布前才构建），算进 drift 会让 rc=1，
    把"还没做那一步"变成"账对不上"——那是逼人去关闸门。
    """
    output = output or os.path.join(root, "output")
    rows = ledger_rows(root, output)
    if not rows:
        return []
    home = os.path.join(root, "dist", "home", "index.html")
    if not os.path.isfile(home):
        return [u"还没有线上版主页（跑 `python scripts/build_index.py --variant hosted`）"]
    html = io.open(home, encoding="utf-8").read()
    hrefs = set(url for url in re.findall(r'class="card"\s+href="([^"]+)"', html))
    want = set(r["url"] for r in rows)
    out = []
    for url in sorted(want - hrefs):
        out.append(u"主页上没有链向 %s 的卡片——主页是旧版，重跑 hosted 变体再重发主页站" % url)
    for url in sorted(hrefs - want):
        out.append(u"主页链着 %s，但账本里没有这条——主页指向了一个没有记录站" % url)
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=u"发布半边：出包 / 记 URL / 核对账本")
    sub = ap.add_subparsers(dest="cmd")
    a = sub.add_parser("pack", help=u"把一篇打成待发布的包")
    a.add_argument("topic")
    a.add_argument("--max-mib", type=int, default=LIMIT_MIB)
    s = sub.add_parser("slug", help=u"只打印某篇的 slug")
    s.add_argument("topic")
    p = sub.add_parser("pending", help=u"哪些篇的线上版和本份不是同一个东西")
    p.add_argument("--json", action="store_true")
    r = sub.add_parser("record", help=u"写回一次真实发布的结果")
    r.add_argument("topic")
    r.add_argument("url")
    r.add_argument("--sha")
    r.add_argument("--access", default=u"private", choices=[u"private", u"public"])
    r.add_argument("--published-date", required=True,
                   help=u"真实发布那天；不能拿渲染日顶")
    r.add_argument("--project-id", dest="project_id",
                   help=u"托管侧返回的 projectId，必填：URL 说不出它属于哪个站")
    l = sub.add_parser("ledger", help=u"整体重生成 web_list.md")
    b = sub.add_parser("playbook", help=u"agent 的发布执行清单（含每步具体参数）")
    b.add_argument("--json", action="store_true")
    c = sub.add_parser("check", help=u"账实核对（G-14 用的就是这个）")
    args = ap.parse_args(argv)
    if not args.cmd:
        sys.stderr.write(u"要做什么？pack / slug / pending / record / ledger / check\n")
        return 2

    try:
        if args.cmd == "pack":
            info = pack(args.topic, root=ROOT, max_mib=args.max_mib)
            sys.stdout.write(u"✓ %s → %s（%d 个文件，%.1f MB，sha %s）\n"
                             % (info["topic"], info["dir"], info["files"],
                                info["bytes"] / 1048576.0, info["sha"]))
            if info["non_ascii"]:
                sys.stdout.write(u"  ! 包内有 %d 个非 ASCII 文件名（只报告，未改名）：%s\n"
                                 % (len(info["non_ascii"]),
                                    u"、".join(info["non_ascii"][:5])))
            return 0
        if args.cmd == "slug":
            sys.stdout.write(slug_of(args.topic) + u"\n")
            return 0
        if args.cmd == "pending":
            rows = pending()
            if args.json:
                sys.stdout.write(json.dumps(rows, ensure_ascii=False, indent=1) + u"\n")
            else:
                for x in rows:
                    sys.stdout.write(u"%-14s %-24s %s %s\n" % (
                        x["topic"], x.get("slug") or u"?", x.get("sha") or u"-",
                        u"待发布" if not x.get("stale") else u"线上是旧版"))
                if not rows:
                    sys.stdout.write(u"没有待发布的篇目。\n")
            return 0
        if args.cmd == "record":
            site = record(args.topic, args.url, sha=args.sha, access=args.access,
                          published_date=args.published_date,
                          project_id=args.project_id)
            sys.stdout.write(u"✓ 已记录 %s → %s（%s）\n"
                             % (args.topic, site["url"], site["content_sha"]))
            return 0
        if args.cmd == "ledger":
            write_ledger()
            sys.stdout.write(u"✓ web_list.md 已按 data.json 重生成\n")
            return 0
        if args.cmd == "playbook":
            steps = playbook()
            if args.json:
                sys.stdout.write(json.dumps(steps, ensure_ascii=False, indent=1) + u"\n")
                return 0
            if not steps:
                sys.stdout.write(u"✓ 没有待发布的篇（线上就是最新那份）\n")
                return 0
            for i, s_ in enumerate(steps, 1):
                sys.stdout.write(u"%d. %s  [%s%s]\n" % (
                    i, s_["topic"], s_["action"],
                    u" projectId=" + s_["project_id"] if s_["project_id"] else u""))
                for st in s_["steps"]:
                    sys.stdout.write(u"     - %s\n" % st)
            return 0
        if args.cmd == "check":
            drift = check()
            for d in drift:
                sys.stdout.write(u"✗ %s\n" % d)
            for note in check_home():
                sys.stdout.write(u"! %s\n" % note)
            if not drift:
                sys.stdout.write(u"✓ 账实一致\n")
            return 1 if drift else 0
    except PublishError as e:
        sys.stderr.write(u"✗ %s\n" % e)
        return 2
    return 2


if __name__ == "__main__":
    sys.exit(main())
