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
# **出包用的是这个，不是上面那个。** 50 MiB 是文档给的数，我们真正上传过的最大包是 29.3 MB，
# 从没实测过天花板。留 20% 余量比贴着跑稳：撞上一次 `artifact_size_exceeded` 的代价
# 是一个发了一半的站，而提前分裂一个组的代价是改一行配置。
WORKING_LIMIT_MIB = 40
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


def home_site_url(root=ROOT):
    """主页站的线上地址。没有 config/home_site.json 就是还没有主页站，返回空。"""
    path = os.path.join(root, "config", "home_site.json")
    if not os.path.isfile(path):
        return u""
    return (_read_json(path).get("url") or u"").strip()


# 这里原来有 `BACK_HOME_MARK` + `hosted_page_bytes`：出包时把文章页的
# 「返回主页」从 `../index.html` 改写成主页站的绝对地址，并要求那个标记**恰好出现一次**。
# 那套契约是整个项目最脆的一处耦合——它是"一篇一个站"的产物：
# 一个站只有一页时，`../index.html` 在托管域名上确实指回自己，只能改写。
# 合站之后 `../index.html` 正好指向**本组的落地页**，而落地页就在同一个包里，
# 一个字节都不用改。属性顺序一变就全线 pack 失败的风险随之消失。


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


def _sha_of(files):
    """对一组 (rel, 源文件) 求指纹。rel 一律用正斜杠，且**按 rel 排序**——
    否则同一份内容在 Windows 和 Linux 上会得出两个哈希，而 pending 会永远不为空。"""
    h = hashlib.sha256()
    for rel, src in sorted(files, key=lambda x: x[0]):
        h.update(rel.replace(os.sep, "/").encode("utf-8"))
        h.update(hashlib.sha256(io.open(src, "rb").read()).hexdigest().encode("ascii"))
    return h.hexdigest()[:16]


def topic_stem(topic, config=CONFIG):
    """这一篇在组包里的目录名 = 它自己的 slug。

    不用中文领域名：那会把公开地址变成一串百分号编码，没人能念、也没人能预期，
    而 `slug_is_declared_not_inferred` 这条规矩就没有落点了。
    缺 slug 在这里就报错——**不猜**。
    """
    return slug_of(topic, config)


def topic_files(topic, output=OUTPUT, config=CONFIG):
    """这一篇在**任何组包里**都长这样：`<slug>/<slug>.html` + `<slug>/images/<图>`。

    前缀用的是自己的 slug 而不是组名，所以组怎么重组，这一篇的 `own_sha` 都不变——
    这是两级指纹成立的前提（D-b：谁变了就只报谁）。
    页面里的引用（`images/...`、`../index.html`）不含自己的文件名，
    所以从 `output/<领域>/<领域>.html` 搬到 `<slug>/<slug>.html` 不改一个字节。
    """
    stem = topic_stem(topic, config)
    page = u"%s.html" % topic
    out = []
    for rel, src in package_files(topic, output):
        if rel == page:
            out.append((u"%s/%s.html" % (stem, stem), src))
        else:
            out.append((u"%s/%s" % (stem, rel), src))
    return out


def cover_files(topic, output=OUTPUT, config=CONFIG):
    """声明过的封面单独并进来。

    落地页引用它，而文章页**不一定**引用：`data.cover` 可以指向一张没进任何章节的图。
    少一项不是少一张卡片，是整组的卡片都破，而 pack 全绿。
    """
    dp = os.path.join(output, topic, "data.json")
    if not os.path.isfile(dp):
        return []
    f = (_read_json(dp).get("cover") or {}).get("file") or u""
    if not f.startswith("images/"):
        return []
    src = os.path.join(output, topic, f.replace("/", os.sep))
    if not os.path.isfile(src):
        raise PublishError(u"%s 声明的封面 %s 不在盘上" % (topic, f))
    return [("%s/%s" % (topic_stem(topic, config), f), src)]


def _config_of(root=None):
    return os.path.join(root or ROOT, "config", "topics")


def own_sha(topic, output=OUTPUT, root=None):
    """这一篇自己的指纹：页面按**原始字节**（不再改写任何链接），
    不含 `generated_date`、不含 `data.json`、不含组名。"""
    return _sha_of(topic_files(topic, output, _config_of(root)))


def landing_page(group, root=ROOT):
    return os.path.join(root, "dist", group, "index.html")


def group_package_files(group, root=ROOT, output=None):
    """组包清单：落地页 + 每个成员页 + 它们各自引用到的图 + 每个成员声明过的封面。"""
    output = output or os.path.join(root, "output")
    page = landing_page(group, root)
    if not os.path.isfile(page):
        raise PublishError(
            u"组 %s 还没有落地页 %s——先跑 "
            u"python scripts/build_index.py --topics %s --out %s"
            % (group, u"、".join(members_of(group, root)), page))
    files = [("index.html", page)]
    for topic in members_of(group, root):
        files.extend(topic_files(topic, output, _config_of(root)))
        files.extend(cover_files(topic, output, _config_of(root)))
    seen, uniq = set(), []
    for rel, src in files:
        if rel not in seen:
            seen.add(rel)
            uniq.append((rel, src))
    return uniq


def group_sha(group, root=ROOT, output=None):
    """落地页字节 + 排序后的 Σ(成员 own_sha) + 组身份。

    为什么需要第二个指纹：只有落地页变了（模板改动、成员增减、主页地址变化）
    时，每个成员的 own_sha 都没动。只判 own_sha 就会出现
    "线上那一组是旧的，而每一篇都说自己新"的第三种状态，谁都不报警。
    """
    output = output or os.path.join(root, "output")
    h = hashlib.sha256()
    h.update(group.encode("utf-8"))
    page = landing_page(group, root)
    if os.path.isfile(page):
        h.update(hashlib.sha256(io.open(page, "rb").read()).hexdigest().encode("ascii"))
    for topic in members_of(group, root):
        h.update(own_sha(topic, output, root).encode("ascii"))
    return h.hexdigest()[:16]


# ---------------------------------------------------------------- 组（合站）

GROUPS_CONFIG = os.path.join(ROOT, "config", "site_groups.json")

# 组名不是内部代号，它就是公开地址的前缀，所以长度归平台定：3–51（实测
# `check_subdomain("ai")` 回 `sites_invalid_subdomain`）。下限 3 的坑不是"地址丑"：
# `prepare_site` 遇到非法前缀**不报错**，静默换成十六进制串，于是账上写 `ai-…`、
# 线上住 `5d8a…`，`deep_link()` 拼出的每一条卡片链接从第一天起就是 404。
SUBDOMAIN_MIN = 3
SUBDOMAIN_MAX = 51


def _require_addressable(group):
    if not SUBDOMAIN_MIN <= len(group) <= SUBDOMAIN_MAX:
        raise PublishError(
            u"组名 %r 不能当公开地址用：平台要求前缀 %d–%d 个字符，"
            u"而 `prepare_site` 不会报错，它会静默换成十六进制地址，"
            u"账上的深链从此每一条都是 404" % (group, SUBDOMAIN_MIN, SUBDOMAIN_MAX))


def load_groups(root=ROOT):
    p = os.path.join(root, "config", "site_groups.json")
    if not os.path.isfile(p):
        return {}
    groups = _read_json(p).get("groups") or {}
    for g in groups:
        _require_addressable(g)
    return groups


def all_groups(root=ROOT):
    return sorted(load_groups(root))


def members_of(group, root=ROOT):
    spec = load_groups(root).get(group)
    if spec is None:
        raise PublishError(u"config/site_groups.json 里没有组 %s" % group)
    return sorted(spec.get("members") or [])


def group_of(topic, root=ROOT):
    """这一篇属于哪个组。唯一权威是 `config/site_groups.json`，
    **不是 `data.json` 的 category**：category 是内容的属性，会随编辑判断改，
    而组名进了 URL——跟着改一次，所有已分享的深链就断一次。"""
    for g in all_groups(root):
        if topic in members_of(g, root):
            return g
    return None


def group_host(group):
    _require_addressable(group)
    return group + HOST_SUFFIX


def group_url(group):
    return u"https://%s/" % group_host(group)


def deep_link(group, topic, root=ROOT):
    """这一篇在组里的公开地址。路径段是它自己的 slug，和包内布局一字不差。"""
    stem = topic_stem(topic, _config_of(root))
    return u"https://%s/%s/%s.html" % (group_host(group), stem, stem)


def _first_url(topic, output):
    """这篇**第一次**发布时的地址；没记过就返回 None（不编）。"""
    dp = os.path.join(output, topic, "data.json")
    if not os.path.isfile(dp):
        return None
    try:
        return (_read_json(dp).get("site") or {}).get("first_url") or None
    except (ValueError, KeyError):
        return None


def absorbed_sites(group, root=ROOT, output=None):
    """这一组**发布之后**，哪些旧的单篇站已经不再承载任何内容、可以删。

    为什么必须由脚本算而不是人记：我差一点就删错了。
    《大模型与加密货币》属于 `ai-industry` 组而不是 `ai-compute`，
    在只发了 ai-compute 的时候删掉 `llm-and-crypto`，等于把一篇线上文章删了。
    而 `record-group` 已经把成员的 `site.url` 覆盖成深链，旧地址在 data.json 里查不到了——
    所以旧地址按**规则**重建：一篇一站时代的 host 就是 `<slug>-<后缀>`。

    但规则只能回答"如果有一篇一站，它该叫什么"，回答不了"到底有没有过"。
    10-12 就是被这一点绊的：`absorbed space-comms` 给两篇**生在组里**的新文章
    各列了一条"旧站可删"，而账号里 15 个站根本没有那两个名字。
    所以现在看 `site.first_url` 定性，三种结果：
    · 等于重建出来的那个单篇 host → `evidence="single-site"`，这才是真有旧站；
    · 是别的地址（组深链，含换过组的）→ 从来没有过一篇一站，**不列**；
    · 没记过（W-202 之前的老账）→ `evidence="unknown"`，列出来但明说判不出来。
    **不许把"判不出来"写成"可删"**，也不许为了清单好看替老记录补一个 first_url——
    那等于替它们下"没有旧站"的结论，而那正是会少删、把线上文章留成孤本的反方向。

    返回每行带 `evidence`；`live` 一律 False，要由调用方拿 HTTP 证据填进来，
    脚本不猜——猜就是把"没验证"当成"验证过"。
    """
    output = output or os.path.join(root, "output")
    spec = load_groups(root).get(group) or {}
    if not spec.get("url"):
        return []                       # 组还没发布，一个都不许删
    if spec.get("absorbed_deleted"):
        return []                       # 吸收已经执行完（W-203），清单该空，不该永远挂着
    out = []
    for topic in sorted(spec.get("members") or []):
        try:
            stem = topic_stem(topic, _config_of(root))
        except PublishError:
            continue
        old_host = stem + HOST_SUFFIX
        if old_host == group_host(group):
            continue                    # 旧站就是组站本身（同名），没有可删的
        first = _first_url(topic, output)
        evidence = "unknown"
        if first:
            first_host = urlparse.urlparse(first).netloc
            if first_host and first_host != old_host:
                continue                # 第一次发布就住在某个组里——没有旧站可删
            evidence = "single-site"
        out.append({"topic": topic, "old_host": old_host,
                    "deep_link": deep_link(group, topic, root),
                    "evidence": evidence, "live": False})
    return out




def _render_landing(group, root, output, dist=None):
    """渲染这一组的落地页到 `dist/<组>/index.html`。

    和全站主页是**同一段代码的两次调用**：`build_index.build(topics=成员, out=...)`。
    落地页里卡片指向 `<篇>/<篇>.html`、封面指向 `<篇>/images/...`，
    都是组包内的相对路径——所以它用 local 变体就够，不需要 hosted、
    也不需要把封面内联成 base64。
    """
    import build_index as B
    dest = os.path.join(dist or os.path.join(root, "dist"), group)
    os.makedirs(dest, exist_ok=True)
    out = os.path.join(dest, "index.html")
    title = load_groups(root).get(group, {}).get("display_name") or group
    B.build(topics=members_of(group, root), out=out, root=root,
            output_dir=output, home_url=home_site_url(root), title=title,
            slug_paths=True)
    return out


def landing_link_problems(files):
    """落地页里每个相对链接都必须能在包内找到那个文件。

    这条是**从一次真事故里长出来的**：落地页曾经照抄 `output/` 的布局
    链到 `咖啡/咖啡.html`，而包里文章住在 `coffee/coffee.html`——
    `pack` 全绿、文件都搬对了，而线上每一张卡都 404。
    搬文件这一步看不见"链接指哪儿"，所以必须专门问一次。

    只看相对链接：`https://` 是主页站（不在本包内），`data:` 是内联封面。
    """
    have = {rel for rel, _ in files}
    page = dict(files).get("index.html")
    if not page or not os.path.isfile(page):
        return [u"包里没有落地页 index.html"]
    html = io.open(page, encoding="utf-8").read()
    bad = []
    refs = [m for m in re.findall(r'<a[^>]*\bhref="([^"]+)"', html)
            if not m.startswith(("http", "data:", "#", "mailto:"))]
    refs += [m for m in re.findall(r'<img[^>]*\bsrc="([^"]+)"', html)
             if not m.startswith(("http", "data:"))]
    for ref in refs:
        rel = os.path.normpath(urlparse.urlparse(ref).path).replace(os.sep, "/")
        rel = rel[2:] if rel.startswith("./") else rel
        if rel not in have:
            bad.append(u"落地页链到 %s，但包里没有这个文件" % ref)
    return sorted(set(bad))


def pack_group(group, root=ROOT, dist=None, max_mib=WORKING_LIMIT_MIB, output=None,
               force=False, render=True):
    """把一个组打成包：`dist/<组>/index.html` + 每篇 `dist/<组>/<篇>/<篇>.html` + 各自的图。

    除落地页之外**不改任何一个字节**：图原样复制，文章页也不再改写「返回主页」——
    合站之后 `../index.html` 正好指向同一个包里的落地页。
    压缩发生在**入库时**（`images.fit_bytes`），不在这里：在这里压会造出第二份字节，
    "包就是验证过的那份产物"当场作废。

    上限用 40 MiB 而不是文档给的 50：我们真正上传过的最大包是 29.3 MB，
    50 是没实测过的天花板数，留 20% 余量比贴着跑稳。超了就拒绝并说明该分裂，
    绝不悄悄压图、绝不丢成员凑数。
    """
    output = output or os.path.join(root, "output")
    dist_root = dist or os.path.join(root, "dist")
    dest = os.path.join(dist_root, group)
    # marker 住在包**之外**（`dist/.packed/<组>.sha`）：它一旦落在 `dist/<组>/` 里，
    # 就既是"跳过重打包"的依据，又是要被 `_prune_to_package` 清掉的东西——
    # 两个身份不能共存，而 T-135 那个"先 rmtree 再判跳过"的 bug 就是这么长出来的。
    # 更实际的一条：`prepare_site` 拿的是整个目录，住在里面的话它会上公网。
    marker = os.path.join(dist_root, ".packed", group + ".sha")
    try:
        if render:
            _render_landing(group, root, output, dist=dist)
        files = group_package_files(group, root, output)
        total = sum(os.path.getsize(s) for _, s in files)
        if total > max_mib * 1024 * 1024:
            raise TooLarge(
                u"组 %s（%s）的包 %.1f MB，超过工作上限 %d MiB。"
                u"这个组该分裂了：另开一个桶接**新**文章，已发布的成员不搬。"
                u"不许靠在这里悄悄压图或丢掉某篇来凑数"
                % (group, load_groups(root).get(group, {}).get("display_name", u""),
                   total / 1048576.0, max_mib))
        sha = _sha_of(files)
        bad = landing_link_problems(files)
        if bad:
            raise PublishError(u"组 %s 的落地页有 %d 处链接在包内找不到：%s"
                               % (group, len(bad), u"；".join(bad[:5])))
        # 清理放在**判跳过之前**。顺序反过来的话，`render=True` 那一步刚写出的
        # `index.html.srchash` 会在"内容没变、直接返回"那条路上活下来——
        # 而它正是要被清掉的那类东西。
        _prune_to_package(dest, files)
        if not force and os.path.isfile(marker) and _read(marker) == sha:
            # 内容一个字节没变就不重新铺文件。**这里曾经先 rmtree 再判跳过**，
            # 于是那道优化永远不会命中——marker 刚被自己删掉，每次重渲染都要重铺一遍，
            # 而 AGENTS 第 5 步一次要重渲染 29 篇。
            # 但**报数要报包里的真实数量**：这里曾经返回 0 个文件 0.0 MB，
            # 于是"跳过重打包"和"出了一个空包"在终端上长得一模一样。
            return {"group": group, "dir": dest, "bytes": total, "files": len(files),
                    "members": members_of(group, root),
                    "non_ascii": [], "sha": sha, "skipped": True}
        non_ascii = []
        for rel, src in files:
            if rel == "index.html":
                continue          # 落地页已由 _render_landing 写到位，原样保留
            dst = os.path.join(dest, rel.replace("/", os.sep))
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copy2(src, dst)
            if not os.path.basename(dst).isascii():
                non_ascii.append(rel)
        os.makedirs(os.path.dirname(marker), exist_ok=True)
        io.open(marker, "w", encoding="utf-8").write(sha)
        return {"group": group, "dir": dest, "bytes": total, "files": len(files),
                "members": members_of(group, root), "non_ascii": non_ascii,
                "sha": sha, "skipped": False}
    except PublishError:
        # **任何一次失败都不留包目录**。原来只有"超限"和"链接对不上"两条出口清场，
        # 于是 `NoSlug` 这种在更早一步抛出的失败会把"新落地页 + 旧文章"留在盘上——
        # 那是一个没有任何 sha 描述得了的混合体，而下一次 `prepare_site` 会照原样传上去。
        # 清掉它是安全的：包是构建产物，真相在 `output/`。
        shutil.rmtree(dest, ignore_errors=True)
        raise


def _prune_to_package(dest, files):
    """把包目录修剪成**恰好等于**包清单——多出来的目录和文件一律删。

    两件事合成一条，因为它们同一个成因：`prepare_site` 拿的是**整个目录**，
    所以包里留下的任何东西都会被传到公网去。
    ① 成员被摘出去（或改了 slug）之后旧目录还在 → 线上多出一页谁都不链接的旧内容，
       而它可能正是某个人收藏着的那个地址；
    ② 打包器自己的文件（渲染时顺带写出的 `<页面>.html.srchash` 那一类）→
       页面不引用它，发出去只是把实现细节公开（W-184）。
    **不列排除名单**：名单是一条会漏的规矩，加两个名字，下一个内部文件照样漏。
    """
    if not os.path.isdir(dest):
        return
    keep = {rel for rel, _ in files}
    # **递归**清，且自底向上。只扫顶层等于没扫：文章页那份 `<slug>/<slug>.html.srchash`
    # 住在成员目录里面（这条是测试写出来才发现的——我第一版只清了顶层）。
    for cur, _dirs, names in os.walk(dest, topdown=False):
        rel_dir = os.path.relpath(cur, dest).replace(os.sep, "/")
        for name in names:
            rel = name if rel_dir == u"." else u"%s/%s" % (rel_dir, name)
            if rel not in keep:
                os.remove(os.path.join(cur, name))
        if rel_dir != u"." and not os.listdir(cur):
            os.rmdir(cur)          # 被摘出去的成员目录清空之后收掉



def _site_of(topic, output):
    dp = os.path.join(output, topic, "data.json")
    if not os.path.isfile(dp):
        return {}
    return (_read_json(dp).get("site") or {})


def pending(root=ROOT, output=None):
    """agent 的工作清单：**这一篇自己的字节变没变**。

    判据是指纹而不是"这次跑没跑过"——AGENTS 第 5 步改一次模板要把全部领域
    `--offline` 重渲染，朴素挂钩的代价就是几十次发布。

    只看 `own_sha`，所以"组重组了 / 落地页变了"不在这里出现——那是
    `pending_groups()` 的活。两级分开报才不会出现"线上那组是旧的而每篇都说自己新"。
    """
    output = output or os.path.join(root, "output")
    if not os.path.isdir(output):
        return []
    out = []
    for topic in sorted(os.listdir(output)):
        if not os.path.isfile(page_path(topic, output)):
            continue
        try:
            sha = own_sha(topic, output, root)
        except PublishError as e:
            out.append({"topic": topic, "group": group_of(topic, root) or u"",
                        "error": str(e), "stale": True, "url": u""})
            continue
        site = _site_of(topic, output)
        if site.get("content_sha") != sha:
            out.append({"topic": topic, "group": group_of(topic, root) or u"",
                        "sha": sha, "url": site.get("url") or u"",
                        "project_id": site.get("project_id") or u"",
                        "stale": bool(site.get("url")), "error": u""})
    return out


def pending_groups(root=ROOT, output=None):
    """组级清单：落地页或成员集合变了，整组要重发。"""
    output = output or os.path.join(root, "output")
    spec = load_groups(root)
    out = []
    for group in sorted(spec):
        try:
            sha = group_sha(group, root, output)
        except PublishError as e:
            out.append({"group": group, "error": str(e), "stale": True})
            continue
        if spec[group].get("group_sha") != sha:
            out.append({"group": group, "sha": sha,
                        "members": members_of(group, root),
                        "url": spec[group].get("url") or u"",
                        "project_id": spec[group].get("project_id") or u"",
                        "stale": bool(spec[group].get("url")), "error": u""})
    return out


def _stamp_site(prev, block):
    """给 `first_url` / `first_published_date` 上一次性戳记。

    为什么要单独一个字段：`published_date` 每轮重发都要改，于是"这篇最早哪天上线、
    上线在哪个地址"就被覆盖没了——30 篇现在全写着最后一次重发的日子。
    而 `absorbed_sites` 判"这篇有没有过一篇一站"靠的正是这件事（W-202：
    它给两篇生在组里的文章各列了一条"旧站可删"，而账号里根本没有那两个站）。

    **老记录不补戳**：prev 存在但没有 first_url 时，它的 url 已经是深链了，
    拿它当 first_url 等于替这篇编一个"从来没有过一篇一站"的结论——
    那是把危险方向（该删的没列出来）反过来犯。宁可让它停在"判不出来"。
    """
    prev = prev or {}
    if prev.get("first_url"):
        block["first_url"] = prev["first_url"]
    elif not prev:
        block["first_url"] = block["url"]
    if prev.get("first_published_date"):
        block["first_published_date"] = prev["first_published_date"]
    elif not prev:
        block["first_published_date"] = block.get("published_date")
    return block


def mark_absorbed(group, date, root=ROOT):
    """记一笔"这一组吸收掉的旧单篇站已经删完"。W-203。

    为什么需要这个字段：`absorbed_sites` 能判"这篇有没有过一篇一站"（看 first_url），
    但判不了"那个旧站删了没有"。10-04 把 28 个站删完之后，那 13 个组的清单就一直挂着，
    每跑一次都像在催一次删不存在的站。缺的是一件**已办事实**，不是又一个推测。

    三条不许，都是为了这件事实不许被写歪：
    · 组还没发布 → 根本没有"吸收"这回事；
    · 日期早于组上线 → 旧站只可能在组上线之后才失去内容，早了就是笔误或回填填错；
    · 改成一个**不同的**已办日期 → write-once，和 first_url 同一套纪律。同值重放允许。
    """
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", str(date or u"")):
        raise PublishError(u"日期 %r 不是 YYYY-MM-DD；比不了先后顺序的日期不能进账"
                           % (date,))
    gp = os.path.join(root, "config", "site_groups.json")
    doc = _read_json(gp)
    groups = doc.get("groups") or {}
    if group not in groups:
        raise PublishError(u"没有组 %s" % group)
    spec = groups[group]
    if not spec.get("url"):
        raise PublishError(u"组 %s 还没有发布记录，谈不上「吸收」——一个旧站都还没被承接"
                           % group)
    pub = spec.get("published_date")
    if not pub:
        raise PublishError(u"组 %s 已发布却没记 published_date，先把上线那天补上"
                           % group)
    if date < pub:
        raise PublishError(u"组 %s 是 %s 上线的，旧站不可能在 %s 之前就删完——"
                           u"这个日期只能来自别的地方" % (group, pub, date))
    had = spec.get("absorbed_deleted")
    if had and had != date:
        raise PublishError(u"组 %s 已经记着吸收完成于 %s，现在要改成 %s。"
                           u"已办事实是 write-once；真记错了就改 site_groups.json 并说明为什么"
                           % (group, had, date))
    if had == date:
        return spec
    spec["absorbed_deleted"] = date
    _write_json(gp, doc)
    return spec


def record_group(group, url, root=ROOT, output=None, access=u"private",
                 published_date=None, project_id=None, group_sha_value=None):
    """记一个组的发布，并把每个成员的深链写回各自的 data.json。

    为什么一次记一组而不是一篇一篇记：它们**本来就是同一个站**。
    一篇一篇记会给出一组自相矛盾的账——成员 A 有地址而成员 B 没有，
    而真实世界里要么整组上线要么整组没上。

    `project_id` / `published_date` 必填的理由和单篇时代一样：
    URL 说不出它属于哪个站，而发布日是事实不是可推算的量。
    """
    output = output or os.path.join(root, "output")
    if not project_id:
        raise PublishError(u"record 需要 --project-id：只记 URL 的话，下一次更新"
                           u"会凭记忆认站，而我已经把策略改到错的站上去过一次")
    if not published_date:
        raise PublishError(u"record 需要 --published-date：发布日只能是真实发布那天，"
                           u"不能拿 generated_date 顶")
    parts = urlparse.urlparse(url)
    # **整名相等**，不是前缀。写成 startswith(group + "-") 的话
    # `https://watches-anything.evil.tld/` 也收，而这条检查存在的理由就是我真拼错过地址。
    if parts.netloc != group_host(group):
        raise PublishError(u"地址 %s 的主机名不是组 %s 的那个（应为 %s）。"
                          u"换账号请设 KE_HOST_SUFFIX。"
                          % (url, group, group_host(group)))
    prev = _read_json(os.path.join(root, "config", "site_groups.json"))["groups"][group]
    # 同一个主机名就是同一个站，所以 project_id 不该跟着重发变。
    # 我 10-10 把 playbook 的 actionId 当成 projectId 记了一遍：它也是合法 UUID，
    # G-10 的格式检查和 `check` 的自洽核对都放行，而账本从此指着一个不存在的站。
    # 真换账号时地址必然跟着换（后缀带主人，D-37），所以这条不误伤迁移。
    old_pid = prev.get("project_id")
    if old_pid and old_pid != project_id and prev.get("url") == url:
        raise PublishError(u"组 %s 已记着 project_id %s，现在要给同一个地址记 %s。"
                          u"同一个主机名就是同一个站——重发只换内容不换站。"
                          u"（确认是记错了就拿正确的 id 重来；真换站请先改地址。）"
                          % (group, old_pid, project_id))
    members = members_of(group, root)
    if not members:
        raise PublishError(u"组 %s 没有成员，没什么可记" % group)
    gp = os.path.join(root, "config", "site_groups.json")
    doc = _read_json(gp)
    sha = group_sha_value or group_sha(group, root, output)
    doc["groups"][group].update({
        "url": url, "site_id": None, "project_id": project_id,
        "access": access, "group_sha": sha,
        "published_date": doc["groups"][group].get("published_date") or published_date,
    })
    _write_json(gp, doc)
    for topic in members:
        dp = os.path.join(output, topic, "data.json")
        if not os.path.isfile(dp):
            raise PublishError(u"成员 %s 没有 %s" % (topic, dp))
        data = _read_json(dp)
        stem = topic_stem(topic, _config_of(root))
        path = u"/%s/%s.html" % (stem, stem)
        data["site"] = _stamp_site(data.get("site"), {
            "url": u"https://%s%s" % (group_host(group), path),
            "group": group,
            "path": path,
            "project_id": project_id,
            "content_sha": own_sha(topic, output, root),
            "published_date": published_date,
            "access": access,
        })
        _write_json(dp, data)
    write_ledger(root=root, output=output)
    return doc["groups"][group]


def record(topic, url, sha=None, root=ROOT, output=None, access=u"private",
           published_date=None, project_id=None):
    """记**一篇**的深链。组已经发布过，这里只补这一篇自己的账。

    校验两件事，缺一不可：主机名整名等于组地址，路径正好是 `/<篇>/<篇>.html`。
    只查主机的话，把成员记到同组的**错**篇章上没人拦得住——
    而深链错了就是线上 404、账上却写着"一致"。
    """
    output = output or os.path.join(root, "output")
    if not project_id:
        raise PublishError(u"record 需要 --project-id：只记 URL 下一次会凭记忆认站")
    if not published_date:
        raise PublishError(u"record 需要 --published-date：发布日不能拿 generated_date 顶")
    group = group_of(topic, root)
    if not group:
        raise PublishError(u"%s 不在 config/site_groups.json 的任何一组里。"
                          u"一篇一站的时代结束了：先决定它进哪一组，再记地址" % topic)
    dp = os.path.join(output, topic, "data.json")
    if not os.path.isfile(dp):
        raise PublishError(u"没有 %s，先跑 generate.py %s" % (dp, topic))
    parts = urlparse.urlparse(url)
    stem = topic_stem(topic, _config_of(root))
    want_path = u"/%s/%s.html" % (stem, stem)
    if parts.netloc != group_host(group):
        raise PublishError(u"地址 %s 的主机名不是 %s 所属组 %s 的那个（应为 %s）"
                           % (url, topic, group, group_host(group)))
    if parts.path != want_path:
        raise PublishError(u"地址 %s 的路径是 %s，但该篇在组里的深链必须是 %s——"
                          u"包里的布局就是 `<篇>/<篇>.html`，路径错了线上 404 而账上写着一致"
                          % (url, parts.path or u"/", want_path))
    data = _read_json(dp)
    data["site"] = _stamp_site(data.get("site"), {
        "url": url,
        "group": group,
        "path": parts.path,
        "project_id": project_id,
        "content_sha": sha or own_sha(topic, output, root),
        "published_date": published_date,
        "access": access,
    })
    _write_json(dp, data)
    write_ledger(root=root, output=output)
    return data["site"]


def playbook(root=ROOT, output=None):
    """agent 的执行清单：**一组一条**，最后一条是主页站。

    为什么要有这个而不是让人自己拼参数：发布的后半段只有 agent 能走（托管是 MCP，
    脚本调不到），而 `prepare_site` 要 projectRoot / webDirectory / slug / projectId
    四个值同时正确。projectId 猜错的后果是把 A 篇发到 B 篇的站上——这件事 09-25
    真做过一次（把访问策略改到了另一个草稿站）。所以清单必须自己算出来，
    而不是靠"上次会话里我记得"。
    """
    output = output or os.path.join(root, "output")
    repo = os.path.dirname(os.path.abspath(root)) if not os.path.isabs(root) else os.path.abspath(root)
    out = []
    for row in pending_groups(root=root, output=output):
        group = row["group"]
        if row.get("error"):
            out.append({"group": group, "action": u"blocked", "url": u"",
                        "webDirectory": u"", "steps": [u"先修这个组：%s" % row["error"]]})
            continue
        pid = row.get("project_id") or u""
        # 没发过的站**没有地址可报**。拼一个 `<组>-<后缀>` 的假地址再去 curl 它、
        # record 它，正是主机名校验要防的那类错搬到清单里。真实地址只能来自 get_site。
        url = row.get("url") or u""
        wd = u"dist/" + group
        prep = (u"prepare_site(projectRoot=%s, webDirectory=%s, slug=%s, "
                u"displayName=%s%s)"
                % (repo, wd, group,
                   load_groups(root).get(group, {}).get("display_name", group),
                   u", projectId=" + pid if pid else u""))
        curl = (u"逐篇 curl 深链 200：" +
                u" ".join(deep_link(group, t).rsplit(u"/", 1)[-1] for t in row["members"]))
        steps = [
            u"pack_group：%s（成员 %d 篇：%s）"
            % (group, len(row["members"]), u"、".join(row["members"])),
            prep + u"  ← 没有 projectId 就是建新站",
            u"get_publish_status 直到 canPublish: true（这一步不能跳，"
            u"queued/running 都不是 ready）",
            u"publish_site",
            u"get_publish_status 直到 published: true 且 active_release_id 非空",
            u"update_access_policy(siteId, mode=public, confirmPublic=true)"
            u"  ← 发布 ≠ 可见：新站默认 private，public 要单独授权",
            (curl + u" 必须全是 200") if url else
            u"从 get_site 返回的 host 取真实地址，再逐篇 curl 深链到 200（脚本不替你猜新站地址）",
            u"python scripts/publish.py record-group %s %s --project-id <projectId> "
            u"--access public --published-date <真实发布那天>"
            % (group, url or u"<上一步拿到的地址>"),
            # 记账必须在重建主页**之前**：hosted 主页的卡片地址是从各篇 data.json 的
            # site.url 读出来的。先重建再记账，主页上这一组的卡片还是空的或旧的，
            # 而清单看起来一步一步都做了。
            u"重建 hosted 主页并重发主页站  ← 必须在 record-group 之后、删旧站之前："
            u"主页卡片读的是各篇 data.json 的 site.url，"
            u"删早了线上主页就会出现 404 卡片",
            u"以上全部通过之后，才删掉被这一组吸收的旧单篇站",
        ]
        out.append({"group": group, "action": u"update-site" if pid else u"new-site",
                    "project_id": pid, "url": url, "webDirectory": wd,
                    "members": row["members"], "steps": steps})

    if not out:
        # 没有一个组要重发，主页也就没有跟着发的理由
        return out
    home_pid = u""
    hp = os.path.join(root, "config", "home_site.json")
    if os.path.isfile(hp):
        home_pid = (_read_json(hp).get("project_id") or u"").strip()
    out.append({
        "group": u"home", "action": u"update-site" if home_pid else u"new-site",
        "project_id": home_pid,
        "url": (_read_json(hp).get("url") or u"") if home_pid else u"",
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


def check_group(group, root=ROOT, output=None):
    """一个**已经打出包**的组：落地页的卡片集合必须正好等于它的成员集合。

    为什么单独一条函数：`pack` 只搬文件，看不见链接指哪儿。
    这一条就是那次事故的回归检查——落地页照抄了 `output/` 的布局，
    卡片链到 `咖啡/咖啡.html`，而包里文章住在 `coffee/coffee.html`：
    13 个组全部"打包成功"，线上每张卡都 404。

    返回问题清单（空 = 一致）。包不存在就返回空——**没打包是正常状态**，
    把它算成问题会让 `validate --all` 在每次发布前都红一片，那是逼人去关闸门。
    """
    output = output or os.path.join(root, "output")
    page = landing_page(group, root)
    if not os.path.isfile(page):
        return []
    problems = list(landing_link_problems(group_package_files(group, root, output)))
    html = io.open(page, encoding="utf-8").read()
    cards = {c for c in re.findall(r'<a class="card" href="([^"]+)"', html)
             if not c.startswith(("http", "data:", "#"))}
    want = {u"%s/%s.html" % (topic_stem(t, _config_of(root)),
                             topic_stem(t, _config_of(root)))
            for t in members_of(group, root)}
    for missing in sorted(want - cards):
        problems.append(u"落地页少一张卡：%s（成员 %s 没有对应的卡片）"
                        % (missing, missing.split("/", 1)[0]))
    for extra in sorted(cards - want):
        problems.append(u"落地页多一张卡：%s（不在 %s 的成员里）" % (extra, group))
    return problems


def all_group_problems(root=ROOT, output=None):
    """所有**已打包**的组的问题，返回 [(组, 问题)]。"""
    out = []
    for group in all_groups(root):
        for p in check_group(group, root, output):
            out.append((group, p))
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
            now = own_sha(topic, output, root)
        except PublishError:
            now = u"?"
        group = site.get("group") or group_of(topic, root) or u"?"
        rows.append({"topic": topic, "group": group, "url": site["url"],
                     "published_date": site.get("published_date") or u"?",
                     "access": site.get("access") or u"private",
                     "drift": u"已更新未发布" if now != site.get("content_sha") else u"一致"})
    return rows


def ledger_text(root=ROOT, output=None):
    rows = ledger_rows(root, output)
    lines = [u"# 线上地址清单",
             u"",
             u"**这个文件是派生物，不要手改。**权威源是各篇 `output/<领域>/data.json` 的",
             u"`site` 字段（组身份在 `config/site_groups.json`）；本文件由",
             u"`python scripts/publish.py record ...` 整体重生成，",
             u"`validate.py` 的 G-14 判的就是「这个文件与 data.json 是否一致」。",
             u"",
             u"合站之后一行仍是一篇，但**「站点」列才是发布单位**：同一组里的行共用一个站，",
             u"重发一次整组都算发过。",
             u"",
             u"| 领域 | 站点 | 线上地址 | 发布日 | 访问 | 本地 vs 线上 |",
             u"|---|---|---|---|---|---|"]
    if not rows:
        lines.append(u"| （还没有任何一篇发布成功） | | | | | |")
    for r in rows:
        lines.append(u"| %s | %s | <%s> | %s | %s | %s |"
                     % (r["topic"], r["group"], r["url"], r["published_date"],
                        r["access"], r["drift"]))
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
    a = sub.add_parser("pack", help=u"把一个组打成待发布的包（合站之后发布单位是组）")
    a.add_argument("group")
    a.add_argument("--max-mib", type=int, default=WORKING_LIMIT_MIB,
                   help=u"工作上限，默认 %d MiB（托管侧文档给的是 %d，没实测过）"
                        % (WORKING_LIMIT_MIB, LIMIT_MIB))
    a.add_argument("--no-render", action="store_true",
                   help=u"不重渲染落地页（测试用；正常出包一定要渲染）")
    g = sub.add_parser("groups", help=u"列出 config/site_groups.json 里的组与成员")
    ab = sub.add_parser("absorbed", help=u"这一组发布后，哪些旧单篇站已不再承载内容（可删）")
    ab.add_argument("group")
    ma = sub.add_parser("mark-absorbed",
                        help=u"记一笔：这一组吸收的旧站**已经删完**（删站之后才跑）")
    ma.add_argument("group")
    ma.add_argument("date", help=u"删完那天 YYYY-MM-DD，不得早于该组上线日")
    s = sub.add_parser("slug", help=u"只打印某篇的 slug")
    s.add_argument("topic")
    p = sub.add_parser("pending", help=u"哪些篇的线上版和本份不是同一个东西")
    p.add_argument("--json", action="store_true")
    pg = sub.add_parser("pending-groups", help=u"哪些组要重发（落地页或成员集合变了）")
    r = sub.add_parser("record", help=u"写回**一篇**的深链（组已由 record-group 记过）")
    r.add_argument("topic")
    r.add_argument("url")
    r.add_argument("--sha")
    r.add_argument("--access", default=u"private", choices=[u"private", u"public"])
    r.add_argument("--published-date", required=True, help=u"真实发布那天；不能拿渲染日顶")
    r.add_argument("--project-id", dest="project_id",
                   help=u"托管侧返回的 projectId，必填：URL 说不出它属于哪个站")
    rg = sub.add_parser("record-group", help=u"写回一个组的发布，并给每个成员记深链")
    rg.add_argument("group")
    rg.add_argument("url")
    rg.add_argument("--access", default=u"private", choices=[u"private", u"public"])
    rg.add_argument("--published-date", required=True)
    rg.add_argument("--project-id", dest="project_id", required=True)
    rg.add_argument("--group-sha", dest="group_sha")
    l = sub.add_parser("ledger", help=u"整体重生成 web_list.md")
    b = sub.add_parser("playbook", help=u"agent 的发布执行清单（一组一条，含每步参数）")
    b.add_argument("--json", action="store_true")
    c = sub.add_parser("check", help=u"账实核对（G-14 用的就是这个）")
    args = ap.parse_args(argv)
    if not args.cmd:
        sys.stderr.write(u"要做什么？pack / groups / pending / pending-groups / "
                         u"record / record-group / ledger / playbook / check\n")
        return 2

    try:
        if args.cmd == "pack":
            info = pack_group(args.group, root=ROOT, max_mib=args.max_mib,
                              render=not args.no_render)
            sys.stdout.write(u"%s %s → %s（%d 个文件、%d 篇，%.1f MB，sha %s）\n"
                             % (u"=" if info.get("skipped") else u"✓",
                                info["group"], info["dir"], info["files"],
                                len(info["members"]), info["bytes"] / 1048576.0,
                                info["sha"]))
            if info.get("skipped"):
                sys.stdout.write(u"  指纹未变，跳过重打包（上面是包里现有的东西）\n")
            if info["non_ascii"]:
                sys.stdout.write(u"  ! 包内有 %d 个非 ASCII 文件名（只报告，未改名）：%s\n"
                                 % (len(info["non_ascii"]),
                                    u"、".join(info["non_ascii"][:5])))
            return 0
        if args.cmd == "groups":
            for grp in all_groups(ROOT):
                sys.stdout.write(u"%-20s %-10s %d 篇  %s\n"
                                 % (grp, load_groups(ROOT).get(grp, {}).get("display_name", u""),
                                    len(members_of(grp, ROOT)),
                                    load_groups().get(grp, {}).get("url") or u"（未发布）"))
            return 0
        if args.cmd == "absorbed":
            spec = load_groups().get(args.group) or {}
            if not spec.get("url"):
                sys.stdout.write(u"组 %s 还没有发布记录，一个旧站都不许删"
                                 u"（删了就少一篇）\n" % args.group)
                return 0
            rows = absorbed_sites(args.group)
            if not rows:
                if spec.get("absorbed_deleted"):
                    sys.stdout.write(u"组 %s 吸收的旧站已于 %s 删完（`absorbed_deleted` 记着），"
                                     u"清单为空。\n" % (args.group, spec["absorbed_deleted"]))
                else:
                    sys.stdout.write(u"组 %s 已发布，没有任何成员曾经有一篇一站——"
                                     u"一个都不许删。\n" % args.group)
                return 0
            sure = [r for r in rows if r["evidence"] == "single-site"]
            unknown = [r for r in rows if r["evidence"] == "unknown"]
            if sure:
                sys.stdout.write(u"组 %s 已发布。以下成员**第一次发布就在单篇主机上**，"
                                 u"旧站内容已由深链承接：\n" % args.group)
                for r in sure:
                    sys.stdout.write(u"  %-22s 旧站 %-42s 深链 %s\n"
                                     % (r["topic"], r["old_host"], r["deep_link"]))
            if unknown:
                sys.stdout.write(u"以下成员没有记过 first_url（那是 W-202 才加的字段），"
                                 u"**判不出来有没有过一篇一站**——不许按本清单删，"
                                 u"要删先用 list_sites 按 host 核到真实存在的站：\n")
                for r in unknown:
                    sys.stdout.write(u"  ?  %-22s 假定的旧站 %-42s 深链 %s\n"
                                     % (r["topic"], r["old_host"], r["deep_link"]))
            sys.stdout.write(u"删除前逐条 curl 深链必须 200；本清单不含 projectId，"
                             u"要用 list_sites 按 host 核对后再删。\n")
            return 0
        if args.cmd == "mark-absorbed":
            spec = mark_absorbed(args.group, args.date)
            sys.stdout.write(u"✓ 组 %s 的旧站记为已于 %s 删完；此后 absorbed 对这组返回空。\n"
                             % (args.group, spec["absorbed_deleted"]))
            return 0
        if args.cmd == "slug":
            sys.stdout.write(slug_of(args.topic) + u"\n")
            return 0
        if args.cmd in ("pending", "pending-groups"):
            rows = (pending_groups(root=ROOT) if args.cmd == "pending-groups"
                    else pending(root=ROOT))
            if getattr(args, "json", False):
                sys.stdout.write(json.dumps(rows, ensure_ascii=False, indent=1) + u"\n")
                return 0
            key = "group" if args.cmd == "pending-groups" else "topic"
            for x in rows:
                sys.stdout.write(u"%-22s %-16s %s %s\n" % (
                    x.get(key) or u"?", x.get("sha") or u"-",
                    u"、".join(x.get("members") or [])[:40],
                    u"待发布" if not x.get("stale") else u"线上是旧版"))
            if not rows:
                sys.stdout.write(u"没有待发布的条目。\n")
            return 0
        if args.cmd == "record":
            site = record(args.topic, args.url, sha=args.sha, access=args.access,
                          published_date=args.published_date,
                          project_id=args.project_id)
            sys.stdout.write(u"✓ 已记录 %s → %s（%s）\n"
                             % (args.topic, site["url"], site["content_sha"]))
            return 0
        if args.cmd == "record-group":
            got = record_group(args.group, args.url, access=args.access,
                               published_date=args.published_date,
                               project_id=args.project_id,
                               group_sha_value=args.group_sha)
            sys.stdout.write(u"✓ 已记录组 %s → %s（%d 篇，group_sha %s）\n"
                             % (args.group, got["url"], len(got["members"]),
                                got["group_sha"]))
            return 0
        if args.cmd == "ledger":
            write_ledger(root=ROOT)
            sys.stdout.write(u"✓ web_list.md 已按 data.json 重生成\n")
            return 0
        if args.cmd == "playbook":
            steps = playbook(root=ROOT)
            if args.json:
                sys.stdout.write(json.dumps(steps, ensure_ascii=False, indent=1) + u"\n")
                return 0
            if not steps:
                sys.stdout.write(u"✓ 没有待发布的组（线上就是最新那份）\n")
                return 0
            for i, s_ in enumerate(steps, 1):
                sys.stdout.write(u"%d. %s  [%s%s]\n" % (
                    i, s_["group"], s_["action"],
                    u" projectId=" + s_["project_id"] if s_["project_id"] else u""))
                for st in s_["steps"]:
                    sys.stdout.write(u"     - %s\n" % st)
            return 0
        if args.cmd == "check":
            drift = check(root=ROOT)
            for d in drift:
                sys.stdout.write(u"✗ %s\n" % d)
            for note in check_home(root=ROOT):
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
