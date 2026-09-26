#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""知识专题页生成器：python scripts/generate.py <领域>

五阶段：outline → research → images → render → verify。

设计要点（都对应到 openspec 里的某个 spec 条款）：
  · 逐节生成，单次失败只重做该节，不整页重来（联网一次要 2–5 分钟）。
  · 硬事实必须带可点开来源，闸门 G-06 会拒掉无来源的数字。
  · 产物必须自包含静态 HTML，由 React 模板 SSR 出来，不在这里拼字符串。
"""
import argparse
import collections
import concurrent.futures
import datetime as dt
import io
import json
import os
import re
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import images as images_mod      # noqa: E402
import llm                       # noqa: E402
import outline as outline_mod    # noqa: E402

import validate as V             # noqa: E402

try:
    from jsonschema import Draft202012Validator
except ImportError:  # pragma: no cover
    Draft202012Validator = None

ROOT = os.path.dirname(HERE)
CONFIG = os.path.join(ROOT, "config")
OUTPUT = os.path.join(ROOT, "output")

VALID_BLOCK_TYPES = set(outline_mod.BLOCK_TYPES)


def log(msg):
    sys.stderr.write(msg.rstrip() + "\n")
    sys.stderr.flush()


# ---------------------------------------------------------------- 阶段 1：大纲

def draft_outline(topic, backend_online=True):
    """让模型起草一份大纲，写盘后**停住**等人工确认——大纲决定整页覆盖面，不能自动往下跑。"""
    prompt = (
        u"我要为『%s』做一个约 10 分钟读完的中文知识科普专题页。"
        u"请设计 8–12 个章节，做到“古往今来”都覆盖：历史脉络、核心产品/系列、行业版图与代表品牌、"
        u"产地或源头、赛事或评鉴体系、工艺或技术、价格与钱怎么花、器具/配件或延伸品类、常见误区与争议。"
        u"再为该领域选一个视觉主题 token 名（kebab-case，例如 coffee-roast）和一个开场记忆点 hero_motif。\n"
        u"只输出 JSON，形如 "
        u'{"topic":"...","subtitle":"...","reader":"...",'
        u'"theme":{"token":"...","hero_motif":"...","hero_note":"..."},'
        u'"reading_target_minutes":10,'
        u'"sections":[{"id":"kebab-case","title":"...","anchor":"单个汉字",'
        u'"angle":"这章讲什么、砍掉什么","block_types":["prose"],'
        u'"image_queries":["图搜关键词"],"fact_prompts":["要联网查证的具体问题"]}]}'
        u"\n\n要求：id 用英文 kebab-case 且互不重复；block_types 只能取这些值："
        + ", ".join(sorted(VALID_BLOCK_TYPES))
        + u"；angle 不能是 title 的换词复述；fact_prompts 每条都要能查出具体数字或年份。"
    ) % topic
    text = llm.call(prompt, online=False, timeout=300, retries=1, log=log)
    data = llm.extract_json(text)
    data["topic"] = topic
    path = os.path.join(CONFIG, "topics", topic + ".json")
    with io.open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)
    try:
        outline_mod.load(path)
    except outline_mod.OutlineError as e:
        log(u"⚠ 起草的大纲不合 schema（已写盘供你修）：\n%s" % e)
        return 2
    log(u"已起草大纲：%s（%d 章）。请人工检查覆盖面与 angle，确认后去掉 --draft-outline 再生成。"
        % (path, len(data["sections"])))
    return 0


# ---------------------------------------------------------------- 阶段 2：内容

SECTION_TMPL = u"""你在为中文知识科普专题页《{topic}》撰写其中一章。

本章标题：{title}
本章角度：{angle}
目标读者：{reader}
全书其他章节：{siblings}

硬性要求：
1. 正文合计 {lo}–{hi} 个汉字。信息密度优先，不要为了凑字数重复同一句话。
2. 需要查证的问题（请联网检索后回答，逐条给出来源）：
{prompts}
3. 每个数字型断言（价格、年份、数量、尺寸、排名、评分）都必须挂 source_ids，
   source 里必须是你**真的检索到的**可点开 URL。查不到就不要写那个数字，
   或者改成明确的区间/不确定表述。绝不许编造来源。
   **引用只写在块级 `source_ids` 里，正文文字里不要出现 `[S1]` 这种标号**——
   它会被原样印到页面上，而读者点不开；章节内你自己编的 S1/S2 在合并时会被重编号，
   只有 `source_ids` 字段会被改，写在文字里的不会。
4. 只使用这些区块类型：{blocks}
5. 语言：简体中文，客观科普口吻，第二人称适度使用；不要营销腔，不要"令人惊叹"式形容。
6. 这一章要写"具体"的东西：型号名、地名、年份、做法参数、价格数字，而不是一般性道理。

只输出 JSON，不要任何解释文字：
{{"sources":[{{"id":"S1","url":"https://...","label":"这段文字说明它是什么来源","publisher":"可选"}}],
 "blocks":[
   {{"type":"prose","heading":"小节标题","text":"正文\\n\\n另一段"}},
   {{"type":"price_table","as_of":"{ym}","columns":["型号","公价"],
     "rows":[{{"cells":["X","3.2 万元"],"source_ids":["S1"]}}]}}
 ]}}

block 结构约定（严格按此写，否则会被拒）：
- prose: {{type,heading?,text,source_ids}}  text 用 \\n\\n 分段；
  这一章引用了哪几条来源，就写在 prose 的 source_ids 里（契约支持，别写进文字）
- keyvalue_table: {{type,caption?,rows:[{{k,v,source_ids?}}]}}
- timeline: {{type,items:[{{year:"1931",title?,text,source_ids}}]}}
- price_table: {{type,as_of:"YYYY-MM",columns:[...],rows:[{{cells:[...],source_ids:[...] }}]}}  每个价格行必须有来源
- card_grid: {{type,heading?,cards:[{{kicker?,title,body,metrics?:[{{label,value,source_ids?}}]}}]}}
- steps: {{type,title?,items:[{{n,title?,text,spec?}}]}}
- quote: {{type,text,who?,when?,source_ids?}}
- fact_strip: {{type,facts:[{{value,label,hint?,source_ids}}]}}  每条都必须有来源
- bar_chart: {{type,heading?,unit?,max?,as_of:"YYYY-MM"?,bars:[{{label,value,note?,source_ids}}]}}
  用来横向比同一量纲的数字（评测得分、价格、参数）。**每根柱子都必须有 source_ids**；
  至少两根；`max` 只在量表本身有上限时写（如 100 分制），不要为了放大差距截断坐标轴；
  分数类一定要给 `as_of`，榜单每月都在变，没有时点的分数等于没有分数。
- compare: {{type,left:{{title,tone:"pro|con|neutral",points:[...]}},right:{{...}},verdict?}}
- note: {{type,tone:"tip|warn|myth|glossary",title?,text}}
"""


def sources_per_section():
    """每章允许查证几条事实。未设/0 = 不限制（高质量默认）。"""
    try:
        n = int(os.environ.get("KE_SOURCES_PER_SECTION", "0"))
    except ValueError:
        return 0
    return n if n > 0 else 0


def section_budget(bar, n_sections, total=None):
    """每章字数由"整页预算 ÷ 章数"算出来，不另配一套常量。

    之前 config 里 section_min/max_chars 与全页 min/max_chars 各写各的：
    12 章 × 上限 1600 = 19200，而 G-05 只收 6500。模型照提示词认真写必挂，
    咖啡第一轮就是死在这里（实测产出 18107 字）。
    """
    n = max(1, int(n_sections))
    w = bar["words"]
    lo_total, hi_total = total or (int(w["min_chars"]), int(w["max_chars"]))
    lo = max(200, int(lo_total) // n)
    hi = max(lo + 50, int(hi_total) // n)
    return lo, hi


def section_payload(cfg, sec, reader, siblings, bar):
    # total 用大纲的 words_range：G-05 判的是它，提示词必须算同一个数
    dlo, dhi = section_budget(bar, len(cfg.sections), total=cfg.words_range)
    lo = sec.min_words or dlo
    hi = sec.max_words or dhi
    asks = sec.fact_prompts
    cap = sources_per_section()
    if cap:
        asks = asks[:cap]
    prompts = "\n".join(u"   - %s" % q for q in asks)
    return SECTION_TMPL.format(
        topic=cfg.topic, title=sec.title, angle=sec.angle, reader=reader or u"普通读者",
        siblings=siblings, lo=lo, hi=hi, prompts=prompts,
        blocks=", ".join(sec.block_types), ym=dt.date.today().strftime("%Y-%m"),
    )


def _validate_section_json(text):
    try:
        d = llm.extract_json(text)
    except llm.LlmError as e:
        return str(e)
    if not isinstance(d, dict):
        return "顶层不是对象"
    if not d.get("blocks"):
        return "blocks 为空"
    bad = [b.get("type") for b in d["blocks"] if b.get("type") not in VALID_BLOCK_TYPES]
    if bad:
        return "非法区块类型：%s" % bad
    for b in d["blocks"]:
        if b.get("type") == "price_table" and not re.match(r"^\d{4}-\d{2}$", str(b.get("as_of") or "")):
            return "price_table 缺 as_of（应为 YYYY-MM）"
    if d.get("sources"):
        for s in d["sources"]:
            if not str(s.get("url", "")).startswith("http"):
                return "来源缺 url"
    return None


def _strip_inline_marks(text, mapping=None):
    """删掉正文里的 `[Sxx]` 标号，返回 (新文本, 能映射到真实 id 的列表, 删掉的个数)。

    为什么不直接改号留在文字里：章节自己编的 S1/S2 会被印到页面上，而读者点不开——
    引用必须活在 `source_ids` 字段里，那才是模板会渲染成可点开芯片的地方。
    所以能映射的**并进所在块的 source_ids**（保住引用），映射不出的一律丢掉
    （没有东西保证它指谁，写进去就是凭空造引用）。
    混着别的字的方括号（`[约65%]`、`[注3]`）一个都不许动。
    """
    mapping = mapping or {}
    resolved = []
    n = [0]

    def repl(m):
        inner = m.group(1)
        sids = V._SID_IN_BRACKET.findall(inner)
        if not sids:
            return m.group(0)
        n[0] += len(sids)
        for s in sids:
            if mapping.get(s):
                resolved.append(mapping[s])
        rest = V._SID_IN_BRACKET.sub(u"", inner)
        rest = re.sub(u"[,，、/；;\\s]+", u" ", rest).strip()
        return (u"[%s]" % rest) if rest else u""

    out = re.sub(u"\\[([^\\]\\[]{1,80})\\]", repl, text)
    out = re.sub(u"\\s+([。，、；：）])", u"\\1", out)
    return re.sub(u" {2,}", u" ", out), resolved, n[0]


def _clean_markers(node, mapping):
    """递归清掉一个子树里的标号，返回 (处理数, 没能挂出去的 id)。

    字符串既可能是 dict 的值，也可能直接躺在 list 里（`compare.left.points`
    就是一串句子）。只走 dict 会整类漏掉后者，而且漏得安静——计数照样往上报。
    子节点挂不出去的 id 往上一层汇，最后由所在的块兜住，保证"删掉的引用"不凭空消失。
    """
    resolved = []
    moved = 0
    if isinstance(node, dict):
        for k, v in list(node.items()):
            if isinstance(v, (dict, list)):
                m2, loose = _clean_markers(v, mapping)
                moved += m2
                resolved += loose
            elif isinstance(v, type(u"")):
                new, got, n = _strip_inline_marks(v, mapping)
                if n:
                    node[k] = new
                    moved += n
                    resolved += got
    elif isinstance(node, list):
        for i, v in enumerate(node):
            if isinstance(v, (dict, list)):
                m2, loose = _clean_markers(v, mapping)
                moved += m2
                resolved += loose
            elif isinstance(v, type(u"")):
                new, got, n = _strip_inline_marks(v, mapping)
                if n:
                    node[i] = new
                    moved += n
                    resolved += got
    if not resolved:
        return moved, []
    refs = node.get("source_ids") if isinstance(node, dict) else None
    if isinstance(refs, list):
        for sid in dict.fromkeys(resolved):
            if sid not in refs:
                refs.append(sid)
        return moved, []
    if isinstance(node, dict) and "type" in node:      # 这是一个块，契约允许挂来源
        node["source_ids"] = list(dict.fromkeys(resolved))
        return moved, []
    return moved, list(dict.fromkeys(resolved))


def _strip_block_markers(blocks, mapping):
    """清掉所有块里的标号，返回处理数。块级挂不上的引用由块自己兜住。"""
    moved = 0
    for b in blocks or []:
        n, loose = _clean_markers(b, mapping)
        moved += n
        if loose and isinstance(b, dict):
            refs = b.get("source_ids")
            if not isinstance(refs, list):
                refs = []
                b["source_ids"] = refs
            for sid in dict.fromkeys(loose):
                if sid not in refs:
                    refs.append(sid)
    return moved


def _remap_sources(sec_result, global_sources, prefix):
    """章节内 S1/S2 会撞车，统一改成 S<前缀><序号> 并回写 source_ids。

    返回 (blocks, 删掉的内嵌标号个数)。第二个返回值必须往上传：删掉一个引用声明
    而不说，等于悄悄把内容变得没有出处——那是另一种撒谎。
    """
    blocks = sec_result.get("blocks") or []
    mapping = {}
    for i, s in enumerate(sec_result.get("sources") or [], 1):
        sid = "S%s%d" % (prefix, i)
        # 键两种写法都收：模型有时给 "S1"，有时省略 id 由序号补出来。
        # 只登记一个键，正文里按另一种写法的标号就会映射失败被丢掉。
        for key in (s.get("id"), u"S%d" % i):
            if key and key not in mapping:
                mapping[key] = sid
        if not any(g["id"] == sid for g in global_sources):
            # 可选字段缺省时整个键不写：写成 None 会被 schema 判成类型错，
            # 而模型有一半概率不提供 publisher。
            entry = {"id": sid, "url": s.get("url"),
                     "label": s.get("label") or s.get("url"),
                     "retrieved": dt.date.today().isoformat()}
            if s.get("publisher"):
                entry["publisher"] = s["publisher"]
            global_sources.append(entry)

    def walk(o):
        if isinstance(o, dict):
            refs = o.get("source_ids")
            if isinstance(refs, list):
                o["source_ids"] = [mapping.get(r, r) for r in refs]
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)

    walk(blocks)
    dropped = _strip_block_markers(blocks, mapping)
    return blocks, dropped


def research(cfg, existing, only=None, workers=3, replay=None, online=True):
    """逐节生成。返回 (sections, sources, failed_ids)。"""
    bar = V._bar()
    siblings = u"、".join(s.title for s in cfg.sections)
    global_sources = list(existing.get("sources", []))
    done = {s["id"]: s for s in existing.get("sections", [])}
    # --only 的语义是"重做这一节"（帮助文本与 AGENTS.md 都这么写），所以它必须能盖掉
    # done 里已有的那一节；否则这个旗标只能补缺，永远重做不了任何章节。
    # done 本身不动：万一本节重做失败，out 还能回退到旧内容，而不是整章消失。
    todo = [s for s in cfg.sections
            if (only is None or s.id == only) and (s.id not in done or s.id == only)]

    def one(job):
        sec, prefix = job
        prompt = section_payload(cfg, sec, cfg.reader, siblings, bar)
        if replay:
            text = replay(sec)
        else:
            # 同一后端多给一次：模型偶尔会返回 blocks 为空的软失败，换 copilot 只会更差
            # （它的 result 行没有正文，且结构化提示经常答成"Color output disabled."）。
            text = llm.call(prompt, online=online, timeout=bar_llm_timeout(), retries=2, log=log,
                             validate=_validate_section_json)
        payload = llm.extract_json(text)
        grounded = llm.looks_grounded(text)
        return sec, payload, grounded

    jobs = [(s, "%02d" % (cfg.sections.index(s) + 1)) for s in todo]
    results, failed = [], []
    if jobs:
        with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, workers)) as ex:
            futs = {ex.submit(one, j): j[0] for j in jobs}
            for fut in concurrent.futures.as_completed(futs):
                sec = futs[fut]
                try:
                    _sec, payload, grounded = fut.result()
                    blocks, dropped = _remap_sources(payload, global_sources, _prefix_for(cfg, sec))
                    results.append((sec.id, {
                        "id": sec.id, "title": sec.title, "anchor": sec.anchor,
                        "blocks": blocks, "images": [],
                    }))
                    log(u"  ✓ %s%s%s" % (sec.title, u"" if grounded else u"（未取到来源）",
                                         u"" if not dropped else
                                         u"（删掉 %d 处正文内嵌标号，引用改由块级 source_ids 承担）" % dropped))
                except Exception as e:
                    failed.append(sec.id)
                    log(u"  ✗ %s：%s" % (sec.title, e))
    out = [done.get(s.id) for s in cfg.sections]
    by_id = dict(results)
    out = [by_id.get(s.id) or done.get(s.id) for s in cfg.sections]
    return [s for s in out if s], global_sources, failed


def bar_llm_timeout():
    """单次联网取料的超时。本机实测一次真联网 5–20 分钟，600s 会把大部分章节判死，
    整批生成看起来在跑、其实全在重试。要更快结束请用 KE_LLM_TIMEOUT 调小。"""
    return int(os.environ.get("KE_LLM_TIMEOUT", "1500"))


def _prefix_for(cfg, sec):
    return "%02d" % (cfg.sections.index(sec) + 1)


def replay_from(topic, sec):
    p = os.path.join(ROOT, "tests", "fixtures", "llm", topic, sec.id + ".json")
    if not os.path.isfile(p):
        raise llm.LlmError("replay 缺 fixture：%s" % p)
    return io.open(p, encoding="utf-8").read()


# ---------------------------------------------------------------- 阶段 3：图片

def _drop_orphan_images(out_dir, data, log):
    """删掉 images/ 里没有任何一页引用的文件。

    判据与 G-03 完全同源（V._page_image_refs），这是重点不是细节：只按当前
    data.json 判孤儿，就会在「上一版页面还被索引着、这一版没发布成功」的时刻
    把上一版要用的图删掉——闸门随后一挂，入口页指着的那张页当场断图
    （09-21 百达翡丽那 18 个破链就是这个形状）。两边同一个口径，闸门才能既绿又不拆台。

    W-145 之后一篇只留一页，这个函数在**一次发布里被调用两次**（闸门之前、
    回滚页 `.prev` 删掉之后），各挡一头：前者防"孤儿挡住闸门→清理永远轮不到"的死锁，
    后者防"回滚页替一批图挡了一道，回滚页一删那批图就漏在盘上"。
    """
    img_dir = os.path.join(out_dir, "images")
    if not os.path.isdir(img_dir):
        return 0
    keep = set(os.path.basename(im["file"]) for s in (data.get("sections") or [])
               for im in (s.get("images") or []))
    keep |= V._page_image_refs(out_dir)
    n = 0
    for f in sorted(os.listdir(img_dir)):
        if not f.lower().endswith((".jpg", ".jpeg", ".png", ".webp", ".gif")) or f in keep:
            continue
        try:
            os.remove(os.path.join(img_dir, f))
            n += 1
        except OSError:
            log(u"  孤儿图删除失败：%s" % f)
    return n


def _clear_image_refs(data, log):
    """把章节配图引用清空（只动内存，**不动磁盘**），让 do_images 真的去重找。

    为什么不删文件：`--redo-images` 的老写法是"先删再抓"，而退路挂在 finally 上——
    硬杀（taskkill、断电、机器休眠）根本不走 finally。09-21 实测就是这个形状：
    百达翡丽 data.json 引用 0 张、images/ 里 19 张、images.prev/ 里 17 张、
    已发布页面 18 个破链，恢复要人手工从 manifest 拼记录。
    引用不清就等于什么都没重做（do_images 看到"这章已经够图"会跳过），
    所以清的是内存里的引用，文件一份不删；旧文件的清理挪到新页面渲染出来之后
    （见 main() 里的 `_drop_orphan_images`）。

    例外：`kind: illustration` 是自画的，不在"重找"的范围内——采集器只会找回照片，
    把它的引用一起清掉就是让孤儿清理把手画的剖面图删了（W-132）。
    """
    cleared = 0
    for s in data.get("sections") or []:
        ims = s.get("images") or []
        drawn = [im for im in ims if im.get("kind") == "illustration"]
        cleared += len(ims) - len(drawn)
        s["images"] = drawn
    return cleared


SNAP_DIR = "images.prev"
# 待发布的包放这儿。像 OUTPUT 一样做成模块常量，是为了测试能把它指到 tmp 里——
# 否则每跑一次集成测试就会往真实仓库的 dist/ 里写一份包。
PUBLISH_DIST = os.path.join(ROOT, "dist")


def _prev_files(out_dir, records):
    """一组配图记录对应的文件现在躺在哪个目录，每张最多产出一个路径。
    优先快照位：文件名是按章节顺序编号的，重做会造出**同名**的新图，
    而我们要退回去的那条记录指的是旧文件。"""
    img_dir = os.path.join(out_dir, "images")
    prev_dir = os.path.join(out_dir, SNAP_DIR)
    for im in records:
        base = os.path.basename(str(im.get("file") or ""))
        if not base:
            continue
        for d in (prev_dir, img_dir):
            src = os.path.join(d, base)
            if os.path.isfile(src):
                yield src
                break


def _snapshot_images(out_dir, ids, data, log):
    """把 `ids` 这几章当前的配图记录连文件一起备份到 `images.prev/`。

    为什么清空之前要先留一份：Bing CN 的召回在同一条检索词上就能从 35 条掉到 5 条
    （2026-09-20 实测两次），积家篇那一轮更是整段 getaddrinfo failed。
    先删后抓碰上这种抖动，等于把一篇 22 张图、闸门全绿的页面押上去赌一次网络——
    LV 篇真就这么掉到 1 张、10 章空掉。

    为什么是复制而不是把整个目录改名：`--only` 只清一章，
    其它章节的引用必须一直有效，改名会先把它们弄坏。
    """
    prev_dir = os.path.join(out_dir, SNAP_DIR)
    shutil.rmtree(prev_dir, ignore_errors=True)
    snap = {}
    for sec in (data or {}).get("sections") or []:
        sid = sec.get("id")
        ims = [im for im in (sec.get("images") or []) if im.get("file")]
        if sid not in ids or not ims:
            continue
        srcs = list(_prev_files(out_dir, ims))
        if len(srcs) != len(ims):
            log(u"  ! %s 有 %d 张引用图已经不在磁盘上，只能保住剩下 %d 张" % (
                sid, len(ims) - len(srcs), len(srcs)))
        if not srcs:
            continue
        snap[sid] = json.loads(json.dumps(ims))
        os.makedirs(prev_dir, exist_ok=True)
        for src in srcs:
            dst = os.path.join(prev_dir, os.path.basename(src))
            # `_prev_files` 先查快照位，所以两章共用一张图时，第二条记录找到的
            # 就是刚被第一条复制进来的那个路径——src 与 dst 是同一个文件，
            # copy2 会抛 SameFileError 把整轮重做打死（09-22 百达翡丽实测）。
            if os.path.abspath(src) == os.path.abspath(dst):
                continue
            shutil.copy2(src, dst)
    if snap:
        # 记录也要落盘：只有文件的话，硬杀之后得靠人手工从 manifest 拼回引用。
        # 带 query 是必须的——从这份记录恢复回来的图，体检器还要靠它分诊
        # "检索词没点名" vs "点名了还给脏图"（丢了来路就变成"不可分诊"）。
        records = [dict(im, section=sid)
                   for sid, ims in sorted(snap.items()) for im in ims]
        with io.open(os.path.join(prev_dir, "records.json"), "w", encoding="utf-8") as fh:
            json.dump(records, fh, ensure_ascii=False, indent=1)
        log(u"      先备份旧配图 %d 张（重做召回变差就退回这份）"
            % sum(len(v) for v in snap.values()))
    return snap


def _query_wordset(queries):
    """一条检索词列表的全部词形（小写）。拆词重试与颠倒词序都是它的子集。"""
    toks = set()
    for q in queries or ():
        toks |= {t.lower() for t in re.split(images_mod.TOKEN_SPLIT, str(q or u"")) if t}
    return toks


def _found_by_this_chapter(rec_query, cur_tokens, subject):
    """这张图当初是不是**这一章现在会发出的词**找出来的。

    采集器会自己派生三种形态，都算这一章的词：拆词重试（子集）、颠倒词序（同集）、
    `ensure_subject` 补主语（只多一个主语词）。除此之外它不该出现在这一章的备份里。
    没有 `query` 的旧记录判不了——按"不知道"放行，不把"没证据"当成"证据是假的"
    （同 W-95：报"无来路"和报"可救"是两件事）。
    """
    if not cur_tokens:
        return True
    q = str(rec_query or u"").strip().lower()
    toks = {t for t in re.split(images_mod.TOKEN_SPLIT, q) if t}
    if not toks or toks <= cur_tokens:
        return True
    prim = (images_mod.primary_subject(subject) or u"").lower()
    return bool(prim) and (toks - {prim}) <= cur_tokens


def _rollback_images(out_dir, data, snap, log, subject=(), exclude_pages=(), queries=None):
    """重做没收获就退回备份：哪一章变少了，就把那一章的图和引用还回去。

    判据是"变少了没有"**且退回来的东西还值得看**——不设"召回要够 N 条"那种健康线，
    但数量不是唯一一句话：09-23 实测百达翡丽页上还挂着柴油机、Calatrava 建筑、万年历 APP，
    就是因为新一轮引擎答非所问、这一章拿到 0 张，于是旧那批"根本没点名领域"的图
    被当成"没变差"整章退了回来。空章会被 G-03 拦住（页面就不上架），
    脏图却能上架骗读者——所以不点名领域的不退。
    `queries` 是各章**现在**的检索词：改了词之后"变少"是预期结果，不是召回崩了，
    只按数量判就会把改词之前的跑章图退回来（W-141）。
    同一条检索词两次返回 5 条和 35 条，任何单点阈值都是在给噪声定指标。
    跑在 `_drop_orphan_images` **之前**（那是渲染出新页面之后的事）：
    退回来的图是被引用的，孤儿清理不会碰它们；本轮抓到却没派上用场的新图
    才归它删。旧图本身从头到尾没被删过（见 `_clear_image_refs`），
    所以这里多数时候只是把引用接回去，不是一次真正的恢复。
    """
    prev_dir = os.path.join(out_dir, SNAP_DIR)
    secs = {s.get("id"): s for s in (data or {}).get("sections") or []}
    worse = {}
    for sid, old in (snap or {}).items():
        sec = secs.get(sid)
        if sec is None:
            continue        # 章节没了就不是"变少"，是别的问题，交给 schema 去判
        cur = sec.get("images") or []
        if len(cur) < len(old):
            worse[sid] = (cur, old)
    if not worse:
        # 不在这里删快照：调用方还在 finally 里，而渲染与闸门都在后面。
        # 快照是"这一篇还能回到重做之前"的唯一凭据，
        # 只有真的一路走到索引重建才配删掉它（见 main() 末尾）。
        return False
    img_dir = os.path.join(out_dir, "images")
    os.makedirs(img_dir, exist_ok=True)
    # 退回来的图不能和别的章节撞：G-03 判"同一张图被 2 个章节共用"。
    # 重做时别的章节可能正好抓到了这一章的旧图，此时再原样退回就是重复
    # （09-22 百达翡丽实测红了 3 条）。冲突时让给已经拿到图的那一章——
    # 它这一轮有收获，退回逻辑本来就只该补"变少"的缺口，不该抢走别人的图。
    used = {im.get("file") for sid, s in secs.items()
            if sid not in worse for im in (s.get("images") or [])}
    for sid, (cur, old) in worse.items():
        files = set(im.get("file") for im in cur)
        cur_tokens = _query_wordset((queries or {}).get(sid))

        # 不点名领域的旧记录不参与退回（W-99 那批脏图正是这个形态：
        # 跑在主语闸门上线之前，alt/caption 里没有这个领域的名字）
        keep, junk, stale = [], [], []
        for it in old:
            # 人工排除的来源页连退回都不参与：退回不经过采集，
            # 不在这里拦一道，摘掉的错图会在下一次「变少就退回」时复活（W-120）。
            if exclude_pages and images_mod.page_excluded(
                    it.get("source_page") or u"", exclude_pages):
                junk.append(it)
                continue
            text = u"%s %s %s" % (it.get("caption") or u"", it.get("alt") or u"",
                                  it.get("source_page") or u"")
            if subject and not images_mod.names_subject(text.lower(), subject):
                junk.append(it)
                continue
            # 还得是**这一章现在的检索词找出来的**那张图。少了这一道，改词等于白改：
            # 09-25 实测把「稳定币」章的检索词从我写错的 `OpenAI`（领域里最热的实体，
            # 不是这一章讲的东西）换成 稳定币/储备/清算，本轮 0 张合格，回滚按"变少了"
            # 把 `OpenAI放开ChatGPT限制` 退了回来，跑章图原地复活。
            # 为什么不用"撞上几个词"当判据：撞 1 个太松（`学习软件编程` 里那个"软件"
            # 让一张椭圆曲线科普图回到 Lean 章），抬到 2 又比采集器本身还严
            # （点名档只要求 1 个命中），会把"召回崩了要兜底"那条路一起堵死。
            if not _found_by_this_chapter(it.get(u"query"), cur_tokens, subject):
                stale.append(it)
                continue
            keep.append(it)
        old = keep
        back = list(cur) + [im for im in old
                            if im.get("file") not in files and im.get("file") not in used]
        blocked = [im for im in old
                   if im.get("file") not in files and im.get("file") in used]
        used |= {im.get("file") for im in back}
        added = len(back) - len(cur)
        # 原来这里无条件打「已退回旧图」，于是一行说"不退"、下一行说"已退回"，
        # 看日志的人会以为退成功了——实际一张都没退回来。报真实数字。
        log(u"  ! %s 重做后配图变少（%d 张 < 原来的 %d 张）：退回 %d 张%s" % (
            sid, len(cur), len(old), added,
            u"，另有 %d 张这轮被别的章节用走、退回来就是两章共用一张，没退" % len(blocked)
            if blocked else u""))
        if junk:
            log(u"  ! %s 旧图里 %d 张没点名领域，不退——空章会被 G-03 拦住，脏图却会上架骗读者" % (sid, len(junk)))
        if stale:
            log(u"  ! %s 旧图里 %d 张不是这一章现在的检索词找出来的，不退——"
                u"那是改词之前的图，属于别的章" % (sid, len(stale)))
        secs[sid]["images"] = back
        for src in _prev_files(out_dir, back):
            dst = os.path.join(img_dir, os.path.basename(src))
            if not os.path.isfile(dst):
                shutil.copy2(src, dst)
        gone = [im.get("file") for im in back
                if not os.path.isfile(os.path.join(
                    img_dir, os.path.basename(str(im.get("file") or ""))))]
        if gone:
            log(u"  ! 这几张旧图连备份里都没有，闸门会判 G-03：%s"
                % u"、".join(map(str, gone)))
    # 快照留给 main() 在索引重建成功之后删——见 _rollback_images 开头那条注释。
    return True


def image_ref(row):
    """把一行 `collect` 记录投影成 data.json 允许的图片对象。

    契约里图片对象是 `additionalProperties:false`，只认这七个键：collect 的整行还带着
    source_image / title / bytes / format，多写一个键就是一条 G-10 fail。
    投影只写这一处——配图阶段与恢复命令（`recover_images.py`）必须产出同一个形状，
    否则修了一边漏一边，而报错的是闸门。
    """
    ref = {}
    for k in ("file", "alt", "caption", "source_page", "width", "height", "query"):
        v = row.get(k)
        if v is None or v == u"":
            continue
        ref[k] = v
    return ref


def _read_search_stats(out_dir):
    p = os.path.join(out_dir, "images", "search-stats.json")
    if not os.path.isfile(p):
        return {}
    try:
        return json.load(io.open(p, encoding="utf-8"))
    except ValueError:
        return {}


def _write_search_stats(out_dir, stats):
    """把每条检索词的召回统计落盘：{"offered": 召回几条, "named": 其中点名领域几条}。

    只有一份数据能回答「这一章空着，是引擎答非所问，还是这个品牌真的没图」——
    09-22 实测 `积家 腕表 专柜` 召回 34 条全是「积」字的字典笔顺页，
    而同一时刻 `劳力士 手表` 完好。判成"供给稀薄"就会去砍花过额度的章节（W-98 的岔口），
    判成"引擎答非所问"则只是换个时间重试（D-14）。
    跨轮**按词覆盖**而不是取历史最大：这份数据说的是"上一轮跑成什么样"，
    取最大会把后来的一次引擎退化藏起来。
    """
    if not stats:
        return
    d = os.path.join(out_dir, "images")
    if not os.path.isdir(d):
        os.makedirs(d)
    merged = _read_search_stats(out_dir)
    merged.update(stats)
    with io.open(os.path.join(d, "search-stats.json"), "w", encoding="utf-8") as fh:
        json.dump(merged, fh, ensure_ascii=False, indent=1, sort_keys=True)


def _answered_off_subject(queries, stats):
    """这一章的检索词是不是**全都**被引擎答成了不相干的页面。

    判据是 collect 记下的召回统计：`offered>0 且 named==0`——引擎确实回了整整一页，
    只是没有一条点名领域（09-22 实测：`积家 机芯` 回的是汉语字典里「积」字的笔顺页，
    同一分钟 `劳力士 专柜 等待 名单` 却是 34/34 点名）。
    这种时刻放宽主语要求不是"退一步"，而是**保证跑题**：
    候选里没有一张点名的图可挑，填进来的必然是别人的东西
    ——百达翡丽那两张（常柴柴油机、重型工作台）就是这个机制进来的。
    只要有一条词曾经点名过，就仍按原判断走：放宽档救的是"点名页全被尺寸/评分刷掉"。
    """
    rows = [stats.get(q) for q in queries if stats.get(q)]
    if not rows:
        return False
    return all(r.get("offered") and not r.get("named") for r in rows)


def do_images(cfg, data, out_dir, skip=False, reserve=None):
    if skip:
        return
    ibar = V._bar()["images"]
    sbar = V._bar()["structure"]
    # 封面会复用一张章节图 → HTML 里的 <img> 比章节图数多 1。
    # 不预留这一格，24 张的页永远会渲染出 25 个 img 并撞 G-03 上限。
    room = max(1, sbar["max_images"] - 1)
    per_section = max(1, min(2, room // max(1, len(data["sections"]))))
    total = sum(len(s.get("images") or []) for s in data["sections"])
    claimed = {im["file"] for s in data["sections"] for im in (s.get("images") or [])}
    # 重做时的"预留"：还没轮到的章节，它们原有的图不许被前面的章节认走。
    # 不预留就会出这种事——A 章先跑，Bing 还给它的正是 B 章原来那张，
    # 等 B 章自己什么都没抓到想退回旧图时，那张已经在 A 章名下了，
    # 只能判"不退"，B 章直接空掉（09-22 百达翡丽 history 一章实测）。
    pending = {k: set(v or ()) for k, v in (reserve or {}).items()}
    subject = images_mod.subject_tokens(cfg)
    search_stats = {}
    # 同一来源页最多给两章用（见 images.collect 的说明）：一轮配图里跨章共享这个计数
    used_pages = {}
    log(u"      主语词：%s" % u"、".join(subject))
    for sec in data["sections"]:
        pending.pop(sec["id"], None)
        claimed_now = claimed | {f for fs in pending.values() for f in fs}
        cfg_sec = next((s for s in cfg.sections if s.id == sec["id"]), None)
        if not cfg_sec:
            continue
        if total >= sbar["max_images"]:
            break
        have = len(sec.get("images") or [])
        need = min(per_section - have, room - total)
        if need <= 0:
            continue
        # 用尽这一章的全部检索词，而不是只取前 need 条：
        # 上一版只查 2 条，碰上 Bing 返回无关页（实测返回过侏罗纪海报）就整章没图。
        kw = [cfg.topic, sec["title"]] + cfg_sec.image_queries[:1]
        # 检索词要先点名领域。大纲里大多写的是"天文台认证 COSC 证书"这种通用词，
        # 照原样搜回来的是别人的证书/别人的建筑，主语那一档必然全灭、
        # 只能退回放宽档——劳力士篇就是这么配上"圆糯米"的。
        # "哪些词能用、长词怎么救"归 images.gated_queries 一处管，别在这里再写一遍。
        qs = images_mod.gated_queries(cfg_sec.image_queries, subject)
        def _try(queries, gated):
            return images_mod.collect(queries, out_dir, ibar, keywords=kw,
                                      max_per_query=1, log=log, claimed=claimed_now,
                                      min_hits=1 if gated else images_mod.RELAXED_MIN_HITS,
                                      stats=search_stats,
                                      max_per_source_page=2, used_pages=used_pages,
                                      exclude_pages=getattr(cfg, "image_exclude_pages", None),
                                      **({"subject": subject} if gated else {}))

        def _ok(rows):
            return [g for g in rows if g["source_page"]]

        # 三档，顺序不能换：章节检索词+要求点名 > 品牌单词+要求点名 > 放弃点名要求。
        # 中间那档是实测加进来的：积家篇 9 条检索词全灭时，"宾利"这个单词
        # 召回 10 张里 8 张点名品牌的可用图；而直接跳到第三档就会捞回
        # "中国行政区划""圆糯米"那种东西——空着比脏好，但品牌图比脏图好。
        got = _try(qs, True)
        dropped = []
        if not _ok(got):
            # 先重问这一章自己的两词短语，再退到全领域共用的品牌单词。
            # 顺序是实测出来的：本篇摘掉的 9 张错图里 5 张来自裸词档（字标、优惠入口、
            # 钢板网广告），而章节原词带回来的只摘掉 3 张——裸词跑题率是章节词的 3 倍。
            # 一个与这一章无关的品牌单词，比把这一章的词问短更容易配上别人的东西。
            cands = [c for c in (images_mod.brand_phrase(cfg_sec.image_queries, subject,
                                                        already=qs),
                                 images_mod.primary_subject(subject)) if c]
            if cands:
                log(u"  该章检索词召不到点名主语的图，改搜「%s」" % u"」「".join(cands))
                dropped += list(got)
                got = _try(cands, True)
        if not _ok(got):
            # 最后才放弃主语要求。空着过不了 G-03（每章必须有图），
            # 但拿一张只蹭到产区名/地名（巴拿马、也门）的图顶上，读者看到的就是跑题。
            if _answered_off_subject(qs, search_stats):
                log(u"  引擎答非所问：这一章的检索词召回 %s，没有一条点名领域。"
                    u"放宽主语要求只会把别人的图配上来，这一章这轮空着，换时间重试"
                    % u"、".join(u"%s(%d/%d)" % (q[:12], search_stats[q]["named"],
                                                 search_stats[q]["offered"])
                                for q in qs if q in search_stats))
            else:
                log(u"  品牌单词也召不到，放宽主语要求重试")
                dropped += list(got)
                got = _try(qs, False)
        for g in got:
            g["alt"] = g.get("title") or (u"%s：%s" % (sec["title"], cfg_sec.image_queries[0]))
            g["caption"] = u"%s" % (g.get("title") or sec["title"])
        sec.setdefault("images", [])
        usable = [g for g in got if g["source_page"]][:need]
        for g in usable:
            claimed.add(g["file"])
        sec["images"].extend(image_ref(g) for g in usable)
        # 下载了却没派上用场的图必须删掉：留着就是 G-03 的"孤儿图片"，
        # 而且它是我们自己这一轮生成的，删它不涉及任何用户数据。
        # 两条判据都按**文件**说，不按行说：
        #  1) 同一个文件可能在一次 do_images 里出现两行——第一档写盘但那条候选没来源页
        #     所以被丢，第二档按内容哈希认回同一份字节、这次有来源页于是被采用。
        #     按行判断（`g in usable`）会因为两个字典的 fresh 不同而判不相等，
        #     结果把正在被采用的那张删掉（09-22 code review 实测复现）。
        #  2) 只删本轮真的写过盘的行。缺 fresh 键按"不是本轮写的"处理——
        #     宁可留一张孤儿图让闸门响，也不要删掉别人还指着的文件。
        kept = {g["file"] for g in usable}
        for g in list(got) + dropped:
            if g["file"] in kept:
                continue
            if g.get("fresh") is not True:
                continue
            path = os.path.join(out_dir, g["file"].replace("/", os.sep))
            try:
                os.remove(path)
            except OSError:
                log(u"  孤儿图删除失败：%s" % g["file"])
        total += len(usable)
    if total < sbar["min_images"]:
        log(u"  ! 全站仅 %d 张配图，低于下限 %d（G-03 会判死）" % (total, sbar["min_images"]))
    images_mod.write_manifest(out_dir, _manifest_of(out_dir, data))
    _write_search_stats(out_dir, search_stats)


def _manifest_of(out_dir, data):
    entries = []
    for sec in data["sections"]:
        for im in sec.get("images", []):
            entries.append(dict(im, section=sec["id"]))
    return entries


# ---------------------------------------------------------------- 阶段 4/5

def render(data_path, page_path):
    p = subprocess.run(
        [os.environ.get("NODE", "node"), os.path.join("scripts", "render.mjs"),
         "--data", data_path, "--out", page_path],
        cwd=ROOT, capture_output=True, timeout=600)
    out = (p.stdout + p.stderr).decode("utf-8", "ignore")
    if p.returncode != 0:
        raise RuntimeError("渲染失败：" + out[-800:])
    return out.strip()


def verify(topic, page=None):
    """跑这个领域的闸门。`page` 用于换名协议：新页先落在 `<领域>.html.pending`，
    要在它**还没成为已发布页**的时候判它——判错了磁盘上那一份才是真相。"""
    argv = ["--domain", topic]
    if page:
        argv += ["--page", page]
    return V.main(argv)


# ---------------------------------------------------------------- 主流程

def main(argv=None):
    ap = argparse.ArgumentParser(description=u"生成一个领域的知识专题页")
    ap.add_argument("topic", help=u"领域名，对应 config/topics/<领域>.json")
    ap.add_argument("--offline", action="store_true", help=u"只重跑 render+verify，不再花模型额度")
    ap.add_argument("--only", metavar="SECTION_ID", help=u"只重做某一节")
    ap.add_argument("--draft-outline", action="store_true", help=u"让模型起草大纲后停住，等人工确认")
    ap.add_argument("--workers", type=int, default=int(os.environ.get("KE_WORKERS", "4")))
    ap.add_argument("--llm-replay", action="store_true", help=u"用 tests/fixtures/llm 回放，零真实调用")
    ap.add_argument("--skip-images", action="store_true")
    ap.add_argument("--redo-images", action="store_true",
                    help=u"清空旧配图后重新检索（改了配图规则时用；正文不重跑，不花模型额度）")
    # 档位：默认高质量（不限制来源、按大纲的 reading_target_minutes 算字数）。
    # 要快必须显式说，快出来的代价是引用变少（红线 R-02 会让查不到的数字直接不写）。
    ap.add_argument("--minutes", type=int, metavar="N",
                    help=u"覆盖目标阅读时长（分钟），同时改变每章字数预算与 G-05 判据")
    ap.add_argument("--sources-per-section", type=int, metavar="K",
                    help=u"每章最多查证 K 条事实（默认不限制）。这是单次耗时的主开关")
    ap.add_argument("--fast", action="store_true",
                    help=u"快档预设：--minutes 4 --sources-per-section 2，用于快速出报告")
    ap.add_argument("--date", help=u"覆盖产物日期（默认今天）")
    args = ap.parse_args(argv)

    # 档位必须在读大纲之前落到环境变量：大纲的 words_range 与提示词的每章预算
    # 都从那里取，晚设就会一半新一半旧。
    if args.fast:
        os.environ.setdefault("KE_READING_MINUTES", "4")
        os.environ.setdefault("KE_SOURCES_PER_SECTION", "2")
    if args.minutes:
        os.environ["KE_READING_MINUTES"] = str(args.minutes)
    if args.sources_per_section:
        os.environ["KE_SOURCES_PER_SECTION"] = str(args.sources_per_section)
    tier = []
    if os.environ.get("KE_READING_MINUTES"):
        tier.append(u"目标 %s 分钟" % os.environ["KE_READING_MINUTES"])
    if sources_per_section():
        tier.append(u"每章最多 %d 条来源" % sources_per_section())
    log(u"档位：%s" % (u"、".join(tier) if tier else u"高质量默认（不限制来源）"))

    today = args.date or dt.date.today().isoformat()

    if args.draft_outline:
        return draft_outline(args.topic)

    try:
        cfg = outline_mod.load_for_topic(args.topic, root=ROOT)
    except outline_mod.OutlineError as e:
        log(u"✗ %s" % e)
        return 2

    out_dir = os.path.join(OUTPUT, cfg.topic)
    if not os.path.isdir(out_dir):
        os.makedirs(out_dir)
    data_path = os.path.join(out_dir, "data.json")
    data = json.load(io.open(data_path, encoding="utf-8")) if os.path.isfile(data_path) else {
        "topic": cfg.topic, "sections": [], "sources": [],
    }
    data.setdefault("topic", cfg.topic)
    data["category"] = cfg.category or data.get("category", "")
    data["tags"] = cfg.tags or data.get("tags", [])
    data["subtitle"] = cfg.subtitle or data.get("subtitle", "")
    data["reader"] = cfg.reader or data.get("reader", "")
    data["theme"] = {"token": cfg.token, "hero_motif": cfg.hero_motif, "hero_note": cfg.hero_note}
    data["generated_date"] = today
    # 创建时间与重渲染日期是两件事（W-128 的性质）。W-145 之后一篇只留一页、
    # 文件名不带日期，索引再也无法从"最早那篇日期页"反推它哪天第一次上架，
    # 所以这里显式落一次盘：setdefault 而不是赋值——`--offline` 重跑不许改写它。
    data.setdefault("created_date", today)
    data["data_as_of"] = today[:7]

    # --only 打错一个字母不会报错，只会什么都不做：research() 过滤后 todo 为空，
    # 于是日志照跑、配图照抓、退出码只反映后面的闸门——你以为重做了那一章，其实一个字没动。
    # （今天真踩了一次 `--only sections-3`，真实 id 是 complications。）
    if args.only and args.only not in set(s.id for s in cfg.sections):
        log(u"✗ --only %s 不是「%s」的章节 id。可用：%s" % (
            args.only, cfg.topic, u"、".join(s.id for s in cfg.sections)))
        return 2

    # 重做配图之前先备份：召回变差时宁可退回旧图，也不能把一篇闸门全绿的页面清空。
    # 范围 = 本轮会被清掉引用的那些章节：--redo-images 清全部，--only 清那一章
    # （新章节对象带着 "images": [] 回来，旧引用就是这么没的）。
    redo_all = args.redo_images and not (args.offline or args.skip_images)
    redo_one = args.only and not (args.offline or args.skip_images)
    redo_scope = (set(s.get("id") for s in data.get("sections") or [])
                  if redo_all else ({args.only} if redo_one else None))
    snap = _snapshot_images(out_dir, redo_scope, data, log) if redo_scope else None
    try:
        if not args.offline:
            log(u"[2/5] 逐节生成内容（%d 章，并发 %d）" % (len(cfg.sections), args.workers))
            replay = (lambda s: replay_from(cfg.topic, s)) if args.llm_replay else None
            sections, sources, failed = research(
                cfg, data, only=args.only, workers=args.workers, replay=replay,
                online=not args.llm_replay)
            data["sections"] = sections
            data["sources"] = sources
            data["research_mode"] = "replay" if args.llm_replay else "online"
            if failed:
                log(u"✗ 以下章节生成失败，未产出页面：%s" % u"、".join(failed))
                _save(data_path, data)
                return 1
            _save(data_path, data)
            if args.only:
                _merge_images_for(cfg, data, out_dir)
        else:
            log(u"[2/5] --offline：沿用已有 data.json")

        if not args.offline and not args.skip_images:
            if redo_all:
                n = _clear_image_refs(data, log)
                # 故意不落盘：磁盘上那份 data.json 还指着旧图，而旧图一张没删——
                # 这才是"任何时候被硬杀都完好"的状态。旧图的清理排到新页面落盘之后。
                log(u"[3/5] 配图检索（--redo-images：换掉旧配图 %d 张，旧文件先留着）" % n)
            else:
                log(u"[3/5] 配图检索")
            do_images(cfg, data, out_dir, skip=args.skip_images,
                      reserve={k: [im.get("file") for im in v if im.get("file")]
                               for k, v in (snap or {}).items()})
            _save(data_path, data)
        elif args.skip_images:
            log(u"[3/5] 跳过配图")
        else:
            log(u"[3/5] --offline：沿用已有图片")
    finally:
        # 放在 finally：中途抛异常正是"引用已清、新图没抓到"的时刻，
        # 这时候最需要的就是退路。闸门会在最后一步拦住退不回来的页面。
        if snap is not None and _rollback_images(
                out_dir, data, snap, log, subject=images_mod.subject_tokens(cfg),
                              exclude_pages=getattr(cfg, "image_exclude_pages", None),
                              queries={s.id: list(s.image_queries or [])
                                       for s in cfg.sections}):
            _save(data_path, data)

    # 分钟数含"每张图 0.15 分钟"，必须在配图之后算，否则页眉会少算
    data["reading_minutes"] = V.reading_minutes(data, V._bar())
    _save(data_path, data)

    errs = _schema_errors(data)
    if errs:
        log(u"✗ data.json 不合 topic_data.schema.json：")
        for e in errs[:10]:
            log(u"   - %s" % e)
        return 1

    # ---- W-145 换名协议：一篇只留一页，非破坏式不变量改由「暂存 + 原子换名」承担 ----
    # 以前这条不变量靠"旧日期页一直留在盘上"兜底（W-103）。只留最新版之后没有旧页可留，
    # 所以改成：渲染到 `.pending` → 判它 → 通过才把现役复制成 `.prev` 并原子换名 →
    # 索引重建成功才删 `.prev`。任何一步挂掉，磁盘上那份已发布页和它的图都是完整的。
    # 扩展名故意不叫 `.html`：`published_pages()` / `_page_image_refs()` / 索引的
    # `_candidates()` 都按 `.html` 收，未过闸门的候选必须对它们全部不可见。
    page = os.path.join(out_dir, cfg.page_name())
    pending = page + ".pending"
    prev = page + ".prev"
    log(u"[4/5] SSR 渲染 → %s（待发布，闸门过了才换名）"
        % os.path.relpath(pending, ROOT).replace("\\", "/"))
    try:
        log(u"      " + render(data_path, pending))
    except Exception as e:
        log(u"✗ 渲染失败：%s（已发布页 %s 未改动）"
            % (e, os.path.relpath(page, ROOT).replace("\\", "/")))
        return 1

    # 孤儿清理要跑**两次**，各挡一头，判据都是同一个 _drop_orphan_images：
    # ① 闸门之前——LV 篇实测：旧日期页删掉之后盘上留着两张没人引用的图，
    #    G-03 判孤儿 → 闸门不过 → 清理不跑 → 下次还是不过，死锁。
    #    放在闸门之前不会误删新图：G-03 的引用集合含"候选页自己的 srcs"，
    #    而 data.json 与候选页出自同一次渲染，keep 集合等价。
    # ② 删掉 `.prev` 之后——回滚页活着的时候它的图被 `_page_image_refs` 保护着，
    #    回滚页一删那批图就漏在盘上（09-25 被 test_redoing_a_section_leaves_no_orphan_images 抓到）。
    cleaned = _drop_orphan_images(out_dir, data, log)

    log(u"[5/5] 质量闸门")
    rc = verify(cfg.topic, page=pending)
    if rc != 0:
        # 不在这里删 pending：它是"这次为什么没过"的唯一现场。
        log(u"✗ 闸门未过，未换名、未更新索引：%s（已发布页原封不动）" % cfg.topic)
        return rc

    if os.path.isfile(page):
        shutil.copyfile(page, prev)
    os.replace(pending, page)

    # 索引只在闸门全绿后重建：坏页面不该出现在入口页上。
    # try 只包住索引重建这一件事。原先它把"删退路"也包在里面，于是删 `.prev` 时
    # 抛的 OSError 会被报成"索引重建失败、.prev 留着可回滚"——**cause 是错的，
    # 而它声称还留着的那份文件正是它刚删掉的**。
    try:
        import build_index
        idx = build_index.build(today, OUTPUT)
    except Exception as e:
        log(u"✓ 已换名：%s，但索引重建失败：%s（%s 留着，可回滚）"
            % (page, e, os.path.basename(prev)))
        return 1

    # 走到这里才算「这一篇真的发布出去了」，两份退路才配删。它们原先在 finally 里
    # 就没了，于是「闸门挂了」与「闸门过了但索引没更新」这两种情况下，唯一能回到
    # 发布之前状态的凭据也一起没了——恢复只能人手工从 manifest 拼。
    shutil.rmtree(os.path.join(out_dir, SNAP_DIR), ignore_errors=True)
    if os.path.isfile(prev):
        os.remove(prev)
    # 孤儿清理排在 `.prev` 删掉**之后**。判据与 G-03 同源（V._page_image_refs 会把
    # `.prev` 的引用也算成"还在用"），所以放在删除前跑，等于让回滚页替一批图挡一道：
    # 回滚页随后被删，那批图就永久漏在盘上——09-25 被 test_redoing_a_section_leaves_
    # no_orphan_images 抓到了。放最后，引用集合恰好等于"此刻真的发布着的那一页"。
    orphans = _drop_orphan_images(out_dir, data, log)
    if orphans:
        log(u"      回滚页删掉后又清掉 %d 张没人引用的图" % orphans)
    cleaned += orphans
    _pack_for_site(cfg.topic, log)
    log(u"✓ 完成：%s（索引 %s）" % (page, idx or u"未更新"))
    return rc


def _pack_for_site(topic, log):
    """闸门全绿、索引也更新之后，把这一篇打成待发布的包。

    这是"新增文章自动带上 URL"里脚本能做的全部：**发布本身要 agent 调托管工具**
    （`qodercli` 没有 sites 子命令、插件文档也没有 CI/REST，不做逆向的 PAT 直连）。
    整段非致命——一篇验证过的页面不该因为打不出包就算失败；
    但失败必须写进日志，不能静默，否则 `pending` 清单会永远说不清为什么空。
    """
    if not PUBLISH_DIST:
        return
    try:
        import publish as PUB
        info = PUB.pack(topic, root=ROOT, dist=PUBLISH_DIST)
        if info.get("skipped"):
            log(u"      内容未变，沿用已有的待发布包 %s" % os.path.basename(info["dir"]))
        else:
            log(u"      待发布的包：%s（%d 个文件 %.1f MB，sha %s）"
                % (info["dir"], info["files"], info["bytes"] / 1048576.0, info["sha"]))
        if info["non_ascii"]:
            log(u"      ! 包内有 %d 个非 ASCII 文件名（只报告，未改名）：%s"
                % (len(info["non_ascii"]), u"、".join(info["non_ascii"][:5])))
        # 账本是派生物：内容指纹一变，"本地 vs 线上"那一栏就得跟着变。
        # 不在这里重算的话，改一次模板重渲染 20 篇之后 `validate --all` 会因
        # "web_list.md 与 data.json 不一致"整站判死——而 AGENTS 第 5、6 步是要求连着跑的
        # （09-25 的 review 抓到：那时 check 要等人手动跑 `publish.py ledger` 才恢复）。
        PUB.write_ledger(root=ROOT)
    except Exception as e:
        log(u"      ! 出包失败（页面本身已发布成功）：%s" % e)


def _merge_images_for(cfg, data, out_dir):
    for sec in data["sections"]:
        sec.setdefault("images", [])


def _save(path, data):
    """原子写：先落同目录临时文件，再 os.replace 顶掉旧的。
    data.json 是断点续跑的唯一凭据；直接 "w" 截断会让一次中断（Ctrl+C、
    taskkill、序列化中途抛错）把十几章研究成果变成半截 JSON。"""
    tmp = path + ".tmp"
    try:
        with io.open(tmp, "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=1)
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise


def _err_brief(value, limit=70):
    """约束值要能读，但不能把整棵子树印出来。"""
    try:
        s = value if isinstance(value, type(u"")) else json.dumps(value, ensure_ascii=False)
    except (TypeError, ValueError):
        s = unicode_(value)
    return s if len(s) <= limit else s[:limit] + u"…"


def _err_line(path, e):
    return u"%s → %s %s（%s）" % (
        u"/".join(str(p) for p in path) or u"(根)",
        str(e.validator),
        _err_brief(e.validator_value),
        str(e.message).replace(u"\n", u" ")[:110])


def _closest_branch(e):
    """oneOf 的 context 里塞着**每个分支**的错误，其中绝大多数只是"type 不对"。
    挑出判别键（type）匹配的那个分支——那才是作者本来想写的区块类型，也只有它
    会给出真理由（超长、多余键）。挑不出来就退回全部，至少不撒谎说没有线索。"""
    by_branch = {}
    for sub in e.context or ():
        idx = sub.schema_path[0] if len(sub.schema_path) > 0 else "?"
        by_branch.setdefault(idx, []).append(sub)
    if not by_branch:
        return list(e.context or ())
    def is_discriminator_miss(x):
        return (x.validator in (u"type", u"enum", u"const")
                and len(x.schema_path) >= 2 and x.schema_path[1] == u"type")
    meant = {i: errs for i, errs in by_branch.items()
             if not any(is_discriminator_miss(x) for x in errs)}
    pool = meant or by_branch
    return min(pool.values(), key=len)


def _flatten_error(e):
    """一条（可能嵌套 oneOf 的）错误 → 若干行只讲病灶的描述。"""
    if e.validator in (u"oneOf", u"anyOf") and e.context:
        base = list(e.path)
        return [ln for sub in _closest_branch(e) for ln in _flatten_error(
            _repath(sub, base))]
    return [_err_line(e.path, e)]


def _repath(e, prefix):
    """分支内部的错误路径是相对那个块的，补上块自己的路径才能定位。"""
    e.path = collections.deque(prefix + list(e.path))
    return e


def _schema_errors(data):
    if Draft202012Validator is None:
        return []
    schema = json.load(io.open(os.path.join(CONFIG, "topic_data.schema.json"), encoding="utf-8"))
    v = Draft202012Validator(schema)
    out = []
    for e in sorted(v.iter_errors(data), key=lambda e: list(e.path))[:12]:
        out += _flatten_error(e)
    return out


if __name__ == "__main__":
    sys.exit(main())
