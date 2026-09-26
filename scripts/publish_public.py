# -*- coding: utf-8 -*-
"""把当前产物打成一个**干净的单提交**，推到公开仓库。

为什么是"单提交快照"而不是推本地历史：本地历史里的提交 author 带真实邮箱，
旧版 memo.md 里还有本机绝对路径——推历史等于永久公开它们
（开发者 2026-09-25 拍板：远端只要一条干净提交，本地历史不动）。

为什么图片不进公开仓库：`output/*/images/` 是从图搜渠道抓来的第三方图片
（品牌产品图、新闻图、社区图钉），二次分发到公开仓库是真实的版权风险，
而且它们是克隆体积的绝大部分。线上站点不受影响——图已经在各篇的托管站上了。

三条不可省的规矩：
  * 不碰本地 HEAD、不碰本地 index——只用一个临时 index 文件构造 tree。
  * 排除清单在 `config/public_exclude.txt`（要被人读得到，不藏在代码里）；
    推之前自己验一遍，并且**排除必须真的删掉了东西**——否则就是正则没匹配上。
  * 作者从中性环境变量读，绝不把任何真实邮箱写进这个文件。
"""
import argparse
import io
import json
import os
import re
import subprocess
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXCLUDE_FILE = os.path.join(ROOT, "config", "public_exclude.txt")
SNAPSHOT_STATE = os.path.join(ROOT, "config", "public_snapshot.json")
SCRATCH = os.path.join(ROOT, ".probe")
TMP_INDEX = os.path.join(SCRATCH, "public.index")
DROPFILE = os.path.join(SCRATCH, "public_dropped.z")

# 身份痕迹 = 本机用户名，或"盘符 + 斜杠 + Users 目录"形态的绝对路径。
# 用户名**从环境取**，不写死：写死的话这个文件自己就带着那个字符串，
# 于是自查会把它自己的源码报成泄漏（09-25 第一次推就是这么被拦下来的——
# 检查是对的，写法是蠢的）。
_LOCAL_USER = os.environ.get("USERNAME") or os.environ.get("USER") or u""
_IDENTITY_PARTS = ([re.escape(_LOCAL_USER)] if _LOCAL_USER else []) + \
                  [u"[A-Za-z]:[\\\\/]+Users[\\\\/]"]
IDENTITY = re.compile(u"|".join(_IDENTITY_PARTS), re.I)
IMG_EXT = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".woff", ".woff2", ".ttf")


def git(*args, **kw):
    env = dict(os.environ)
    env.update(kw.pop("env", {}))
    r = subprocess.run(["git"] + list(args), capture_output=True, env=env, **kw)
    if r.returncode != 0:
        raise SystemExit(u"git %s 失败：%s" % (
            " ".join(args), r.stderr.decode("utf-8", "replace").strip()))
    return r.stdout.decode("utf-8", "replace")


def paths(ref):
    """列路径，**必须关掉 core.quotePath**。

    默认 `git ls-tree` 会把非 ASCII 路径转义成带引号的八进制串，于是所有中文命名的
    文件既躲过排除、也躲过自查。我第一次跑就是被这个骗过去，报了"图片残留 0"，
    实际一张都没删掉。
    """
    return git("-c", "core.quotePath=false", "ls-tree", "-r", "--name-only",
               ref).splitlines()


def read_excludes():
    out = []
    for line in io.open(EXCLUDE_FILE, encoding="utf-8").read().splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            out.append(line)
    return out


def build_tree(ref, excludes):
    """在临时 index 上造 tree；本地 index 与 HEAD 一个字都不动。"""
    if not os.path.isdir(SCRATCH):
        os.makedirs(SCRATCH)
    if os.path.isfile(TMP_INDEX):
        os.remove(TMP_INDEX)
    env = {"GIT_INDEX_FILE": TMP_INDEX}
    git("read-tree", ref, env=env)
    all_paths = paths(ref)
    drop = [p for p in all_paths if any(re.search(g, p) for g in excludes)]
    if drop:
        with io.open(DROPFILE, "w", encoding="utf-8", newline="") as fh:
            fh.write(u"\0".join(drop) + u"\0")
        git("rm", "--cached", "-q", "--pathspec-file-nul",
            "--pathspec-from-file=" + DROPFILE.replace("\\", "/"), env=env)
    # .gitignore 里补一条，免得克隆者下次 `git add -A` 又把图收回去
    gi = git("show", "%s:.gitignore" % ref)
    extra = (u"\n# 公开快照专属：第三方图片不进这个仓库"
             u"（原因见 docs/publishing-for-agents.md）\noutput/*/images/\n")
    blob = subprocess.run(["git", "hash-object", "-w", "--stdin"],
                          input=(gi + extra).encode("utf-8"), capture_output=True)
    git("update-index", "--add", "--cacheinfo",
        "100644,%s,.gitignore" % blob.stdout.decode().strip(), env=env)
    return git("write-tree", env=env).strip(), len(all_paths)


def is_img(name):
    return name.split("/")[-1].lower().endswith(IMG_EXT)


def is_scraped_img(name):
    """只判 `output/` 下的图——那是抓来的第三方内容，版权风险与体积都在它身上。

    `tests/golden/**` 与 `tests/fixtures/**` 的 13 张（4.2 MB）是**测试夹具**：
    没有它们，clone 之后 `pytest` 直接跑不起来。这是刻意留的例外，
    不是检查漏了——所以写在这里，而不是把整条检查放宽。
    """
    return is_img(name) and name.startswith("output/")


def is_scratch(name):
    """现场文件：生成/换名/托管过程中掉在仓库里的中间物，一个都不是产物。

    `.qoder.site` 是 `prepare_site` 写回仓库根的站点描述符，里面**内嵌整份
    index.html 的 base64**——收进快照等于白白多带一份页面副本，
    而它一次重发就能生成 22 个（09-26 实测）。
    """
    return (name.endswith((".html.pending", ".html.prev", ".qoder.site"))
            or (name.startswith("output/")
                and name.endswith(("manifest.json", "search-stats.json"))))


def audit(ref, excludes):
    tree, total = build_tree(ref, excludes)
    names = paths(tree)
    bad_img = [n for n in names if is_scraped_img(n)]
    scratch = [n for n in names if is_scratch(n)]
    leaks = []
    for n in names:
        if is_img(n):
            continue
        body = git("show", "%s:%s" % (tree, n))
        if IDENTITY.search(body):
            leaks.append(n)
    return tree, total, names, bad_img, scratch, leaks


def last_snapshot_parent():
    """上一次推出去的快照提交，可以当新快照的父。

    为什么不 force-push 一条新的根提交：远端已经有历史了，force 会抹掉它。
    记录的 sha 是我们自己 commit-tree 造出来的，对象就在本地库里，
    所以接父不需要先 fetch 远端。对象丢了（换机器、gc 掉）就退回"无父"，
    那种情况下要推得先 fetch 一次，脚本宁可明说不做。
    """
    if not os.path.isfile(SNAPSHOT_STATE):
        return u""
    try:
        sha = (json.load(io.open(SNAPSHOT_STATE, encoding="utf-8")).get("last_commit") or u"").strip()
    except ValueError:
        return u""
    if not sha:
        return u""
    r = subprocess.run(["git", "cat-file", "-e", sha], capture_output=True)
    if r.returncode != 0:
        sys.stderr.write(u"! 记录的上一次快照 %s 不在本地对象库里，"
                         u"这次会试图再推一条根提交（远端已有历史，会被拒）\n" % sha[:10])
        return u""
    return sha


def main(argv=None):
    ap = argparse.ArgumentParser(description=u"生成并（可选）推送公开快照")
    ap.add_argument("ref", nargs="?", default="HEAD")
    ap.add_argument("--push", help=u"远端 URL；不传就只构造并自查")
    ap.add_argument("--branch", default="main")
    ap.add_argument("--author-name", default=os.environ.get("PUBLIC_GIT_NAME", ""))
    ap.add_argument("--author-email", default=os.environ.get("PUBLIC_GIT_EMAIL", ""))
    args = ap.parse_args(argv)

    ref = git("rev-parse", args.ref).strip()
    excludes = read_excludes()
    tree, total, names, bad_img, scratch, leaks = audit(ref, excludes)
    print(u"公开树 %s：%d 个文件（排除前 %d，删掉 %d）"
          % (tree[:10], len(names), total, total - len(names)))
    print(u"  图片残留 %d｜中间文件残留 %d｜身份痕迹 %d"
          % (len(bad_img), len(scratch), len(leaks)))
    for n in leaks[:8]:
        print(u"  ! 身份痕迹：%s" % n)
    for n in scratch[:8]:
        print(u"  ! 中间文件：%s" % n)
    if total == len(names):
        print(u"✗ 一条都没排除掉——排除正则八成没匹配上（中文路径转义就是这么骗过检查的）。")
        return 1
    if bad_img or scratch or leaks:
        print(u"✗ 自查没过，不推。")
        return 1
    if not args.push:
        print(u"✓ 自查通过。（dry-run：加 --push 才真推）")
        return 0
    if not args.author_name or not args.author_email:
        print(u"✗ 需要 PUBLIC_GIT_NAME / PUBLIC_GIT_EMAIL（中性作者），不推。")
        return 1
    msg = (u"KnowEverything · 静态知识专题页生成器\n\n"
           u"一条命令产出图文并茂、自包含、file:// 双击可开的 HTML 专题页。\n"
           u"本仓库是干净快照（不含第三方图片与本机身份痕迹），"
           u"由 scripts/publish_public.py 生成。\n")
    env = {"GIT_AUTHOR_NAME": args.author_name, "GIT_AUTHOR_EMAIL": args.author_email,
           "GIT_COMMITTER_NAME": args.author_name, "GIT_COMMITTER_EMAIL": args.author_email}
    parent = last_snapshot_parent()
    cmd = ["commit-tree", tree] + ([u"-p", parent] if parent else []) + [u"-m", msg]
    commit = git(*cmd, env=env).strip()
    print(u"提交 %s%s" % (commit[:10],
                          u"（接在 %s 之后）" % parent[:10] if parent else u"（根提交）"))
    r = subprocess.run(["git", "push", args.push, "%s:refs/heads/%s" % (commit, args.branch)],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    sys.stdout.write(r.stdout or u"")
    sys.stderr.write(r.stderr or u"")
    if r.returncode == 0:
        with io.open(SNAPSHOT_STATE, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(json.dumps({
                "last_commit": commit, "last_tree": tree,
                "branch": args.branch, "files": len(names),
                "pushed_at": subprocess.run(
                    ["git", "show", "-s", "--format=%cI", commit],
                    capture_output=True, text=True).stdout.strip(),
                "note": u"上一次推给公开仓库的快照。publish_public.py 用它当新快照的父，"
                        u"这样更新是快进而不用 force-push。删掉这个文件就等于重新起一条历史。"},
                ensure_ascii=False, indent=1) + u"\n")
        print(u"已记录快照状态 → config/public_snapshot.json")
    return r.returncode


if __name__ == "__main__":
    sys.exit(main())
