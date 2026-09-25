#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""汇总 output/ 下所有专题页，生成自包含静态索引主页 output/index.html。

按 category 归类、卡片式下钻、每篇带 tags。索引与专题页共用同一套 React 模板组件，
所以不会出现"主页一套样式、点进去另一套样式"。

用法：python scripts/build_index.py [--date YYYY-MM-DD]
"""
import argparse
import datetime as dt
import io
import json
import os
import re
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import outline as outline_mod  # noqa: E402
import validate as V           # noqa: E402

ROOT = os.path.dirname(HERE)
OUTPUT = os.environ.get("KE_OUTPUT") or os.path.join(ROOT, "output")
CJK_RE = re.compile(u"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]")


def cjk(v):
    """与 validate.cjk_count 同一口径；索引显示的"分钟数"必须和 G-05 算的是同一件事。"""
    if isinstance(v, str):
        return len(CJK_RE.findall(v))
    if isinstance(v, list):
        return sum(cjk(x) for x in v)
    if isinstance(v, dict):
        return sum(cjk(x) for x in v.values())
    return 0


def minutes_of(data, bar):
    """委托给 validate.reading_minutes——页眉与索引卡片必须显示同一个数。"""
    return V.reading_minutes(data, bar)


def cover_of(data):
    """封面取最宽的一张，与模板 coverOf 同一套规则——不设尺寸门槛，
    否则整面照片墙会退成渐变（开发者 2026-09-19 反馈）。
    两处规则必须一致，否则索引卡片点进去会换一张图。"""
    declared = data.get("cover")
    if declared:
        return declared
    best = None
    for s in data.get("sections", []):
        for im in s.get("images") or []:
            # 自画示意图不参与自动封面：索引卡片上没有「示意图 · 非实拍」那行字，
            # 拿它当门面等于让读者以为那是真实照片。人显式声明是另一回事。
            if im.get("kind") == "illustration":
                continue
            if best is None or (im.get("width") or 0) > (best.get("width") or 0):
                best = im
    return best


def _candidates(root):
    """output/ 下"有 data.json 且有产物页面"的领域——即索引的候选集。"""
    if not os.path.isdir(root):
        return []
    out = []
    for topic in sorted(os.listdir(root)):
        d = os.path.join(root, topic)
        if not os.path.isdir(d) or not os.path.isfile(os.path.join(d, "data.json")):
            continue
        # 发现逻辑只此一份（W-145）：这里原先自己写了一遍 `<领域>_*.html`，
        # 改稳定名之后它和 collect() 各判各的，结果是"有产物但全被闸门挡下"
        # 被误判成"还没有产物"——索引静默变空而退出码是 0。
        # 是既有的 test_build_refuses_to_silently_empty_the_index 把它抓出来的。
        if V.published_pages(d, topic):
            out.append(topic)
    return out


def _publishable(topic, root):
    """
    闸门说了算（D-05：判据只有 validate 一处）。
    索引以前只在「某领域自己 verify 通过」时重建，于是**门槛收紧之后**老页面一直挂在
    入口页上——09-22 实测积家 4 章没图、G-03 判死，索引照列它。

    这里问的是「这一篇能不能单独上架」，所以只有 domain 级闸门参与：
    * G-11（跨领域配色雷同）与 G-12（索引本身）是 global 级，
      `V.run(domains=[topic])` 结构上就不会跑它们。这不是漏洞：两套配色撞了，
      该改的是其中一套，把**两边都**踢下索引不解决任何问题。
      它们由 `validate.py --all` 与 generate 的 verify 阶段拦。
    * G-13 显式 skip：它要开真浏览器量七档视口，每个领域再等一遍不值，
      几何同样由 verify 阶段拦。
    * 剩下的是归因过滤：只算 `where` 落在本领域目录里的 fail。不过滤的话，一条
      站点级 fail 会被算到每个被问的领域头上，索引清空，而 build() 把「空」当成
      「还没有产物」返回 None，generate.py 再以 0 退出码打「✓ 完成（索引未更新）」
      ——入口页没了，没人知道。
    """
    findings, _, _ = V.run(domains=[topic], skip=("G-13",), output_dir=root)
    mine = "output/%s" % topic
    return [str(f) for f in findings
            if f.level == "fail" and mine in str(f.where or "")]


def created_of(topic, data, fallback=""):
    """这篇第一次上架是哪天 = `data.json.created_date`（W-128 的性质，W-145 的载体）。

    原来读的是"最早那篇日期页"的文件名——那前提是旧日期页一直留着。
    一篇只留一页之后没有"最早那篇"可读，所以创建时间必须显式落盘：
    写一次、`--offline` 重渲染永不改写。
    也不能退到 `generated_date` 就算完：它每次都变，拿它排序等于"谁最近被重做过谁排最前"，
    正是 W-128 要躲开的东西。所以缺字段时**退回去并且喊一声**，让顺序可疑这件事能被追溯。
    """
    created = (data or {}).get("created_date") or ""
    if created:
        return created
    fb = fallback or (data or {}).get("generated_date") or ""
    if fb:
        sys.stderr.write(u"  ! %s 的 data.json 没有 created_date，"
                         u"排序暂用 generated_date=%s（重渲染过就会漂移，请回填）\n"
                         % (topic, fb))
    return fb


class NotPublished(Exception):
    """线上版主页要每一篇都已发布。缺一篇就报错，不悄悄退回相对路径——
    退回的结果是一个看起来正常、点进去两篇行为不一致的主页：
    一篇跳公网、一篇跳本地文件，而在公网托管的站上后者必然 404。"""


def _data_uri(abs_path):
    """封面内联成 base64。线上版必须自带封面：主页站自己是站，
    如果卡片图去引各篇文章站的 URL，任何一篇没发上去或挂了，主页就碎图。"""
    import base64
    ext = os.path.splitext(abs_path)[1].lower().lstrip(".")
    mime = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png",
            "gif": "image/gif", "webp": "image/webp", "svg": "image/svg+xml"}.get(
                ext, "application/octet-stream")
    return u"data:%s;base64,%s" % (mime, base64.b64encode(io.open(abs_path, "rb").read()).decode("ascii"))


def collect(date=None, output_dir=None, variant="local"):
    bar = V._bar()
    entries = []
    root = output_dir or OUTPUT
    if not os.path.isdir(root):
        return entries
    for topic in sorted(os.listdir(root)):
        d = os.path.join(root, topic)
        dp = os.path.join(d, "data.json")
        if not os.path.isdir(d) or not os.path.isfile(dp):
            continue
        data = json.load(io.open(dp, encoding="utf-8"))
        # 一篇只有一页，名字稳定（W-145）。真出现多页时不在这里判——G-01 会判死，
        # 上面那个 _publishable 就会把这个领域跳过，两处判据不必各写一遍。
        pages = V.published_pages(d, topic)
        if not pages:
            continue
        fails = _publishable(topic, root)
        if fails:
            sys.stderr.write(u"  索引跳过 %s：闸门 %d 条未过（%s）\n"
                             % (topic, len(fails), fails[0][:90]))
            continue
        outline_path = os.path.join(ROOT, "config", "topics", topic + ".json")
        tags = data.get("tags") or []
        category = data.get("category") or ""
        if os.path.isfile(outline_path):
            raw = json.load(io.open(outline_path, encoding="utf-8"))
            tags = tags or raw.get("tags", [])
            category = category or raw.get("category", "")
        cover = cover_of(data)
        if cover and cover.get("file", "").startswith("images/"):
            # 索引在 output/ 下，封面路径要相对它重算；直接抄 data.json 的相对路径会 404
            cover = dict(cover, file="%s/%s" % (topic, cover["file"]))
        site = data.get("site") or {}
        href_local = "%s/%s" % (topic, pages[-1])
        if variant == "hosted":
            if not site.get("url"):
                raise NotPublished(u"%s 还没有已发布地址，线上版主页不能出" % topic)
            href = site["url"]
            if cover and cover.get("file"):
                cover = dict(cover, file=_data_uri(os.path.join(root, cover["file"])))
        else:
            href = href_local
        entries.append({
            "topic": topic,
            "category": category or u"未归类",
            "subtitle": data.get("subtitle", ""),
            "tags": tags,
            "href": href,
            "cover": cover,
            "sections": len(data.get("sections", [])),
            "minutes": minutes_of(data, bar),
            "generatedDate": data.get("generated_date", date or ""),
            "created": created_of(topic, data),
            "dataAsOf": data.get("data_as_of"),
            "token": (data.get("theme") or {}).get("token", ""),
        })
    # DOM 顺序 = 创建时间升序；默认显示是"最新在前"（CSS order 翻过来），
    # 所以 --asc/--desc 两组序号由这里发。
    entries.sort(key=lambda e: (e["created"], e["topic"]))
    return entries


def build(date=None, output_dir=None, variant="local"):
    """`output_dir` 让调用方（generate.py）把它自己那套产物目录传进来。
    不传就用模块默认——命令行 `python scripts/build_index.py` 的行为不变。
    为什么必须由调用方传：测试 patch 的是 `generate.OUTPUT`，
    索引自己算路径就会绕过那个 patch，跑一次测试改一次入库产物。"""
    root = output_dir or OUTPUT
    entries = collect(date, root, variant)
    if not entries:
        candidates = _candidates(root)
        if not candidates:
            sys.stderr.write(u"output/ 下还没有任何专题页，索引跳过\n")
            return None
        # 有产物、却被闸门全挡——这不是"还没生成"，是出事了。
        # 静默返回 None 的话，调用方会把它当成"无需更新"并以 0 退出，
        # 于是整站入口消失而每一次运行都报告成功。
        raise RuntimeError(
            u"索引拒绝生成：%d 个已有产物被闸门全部挡下（%s）。"
            u"要么闸门判据变了，要么这些产物真的坏了——不能当成「还没有产物」。"
            % (len(candidates), u"、".join(candidates[:5])))
    today = date or dt.date.today().isoformat()
    payload = {"entries": entries, "generated_date": today}
    tmp = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8")
    json.dump(payload, tmp, ensure_ascii=False)
    tmp.close()
    # 本地版就是 output/index.html（今天的行为）。线上版落在仓库的 dist/home/，
    # 位置从 output_dir 的上一层推——这样测试把它指到 tmp 时不会写进真实仓库，
    # 也不用再多一个"要记得 patch 的常量"。
    if variant == "hosted":
        out = os.path.join(os.path.dirname(os.path.abspath(root)), "dist", "home", "index.html")
        os.makedirs(os.path.dirname(out), exist_ok=True)
    else:
        out = os.path.join(root, "index.html")
    p = subprocess.run(
        [os.environ.get("NODE", "node"), os.path.join("scripts", "render.mjs"),
         "--index", tmp.name, "--out", out],
        cwd=ROOT, capture_output=True, timeout=600)
    os.unlink(tmp.name)
    msg = (p.stdout + p.stderr).decode("utf-8", "ignore")
    if p.returncode != 0:
        raise RuntimeError("索引渲染失败：" + msg[-800:])
    sys.stderr.write(msg.strip() + "\n")
    cats = {}
    for e in entries:
        cats[e["category"]] = cats.get(e["category"], 0) + 1
    sys.stderr.write(u"  类别：%s\n" % u"、".join(
        "%s(%d)" % (k, v) for k, v in sorted(cats.items())))
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=u"生成索引主页 output/index.html")
    ap.add_argument("--date", help=u"覆盖索引显示的生成日期")
    ap.add_argument("--json", action="store_true", help=u"只打印条目清单，不渲染")
    ap.add_argument("--variant", choices=["local", "hosted"], default="local",
                    help=u"local=链相对路径（output/index.html，今天的行为）；"
                         u"hosted=链各篇已发布站点、封面内联 base64（dist/home/index.html）")
    args = ap.parse_args(argv)
    if args.json:
        print(json.dumps(collect(args.date, variant=args.variant), ensure_ascii=False, indent=1))
        return 0
    try:
        path = build(args.date, variant=args.variant)
    except Exception as e:
        sys.stderr.write(u"✗ %s\n" % e)
        return 1
    return 0 if path else 1


if __name__ == "__main__":
    sys.exit(main())
