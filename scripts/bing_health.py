# -*- coding: utf-8 -*-
"""检索引擎体检：几条控制词，看 Bing CN 现在是不是在答不相干的结果集。

为什么要这一步（09-22 实测）：同一分钟里 `劳力士 专柜 等待 名单` 召回 34 条、
34 条全部点名劳力士；而 `积家 机芯` 召回 34 条，全是汉语字典里「积」字的笔顺动画页，
`腕表 校表 精度测试` 回的是 M.C. Escher 木刻，`Oyster 防水表壳 1926 历史` 回的是老叟钓鱼图。
这不是"某个品牌供给稀薄"，是**按查询**答非所问，而且会突然发生。

代价：09-22 晚上我在这样的引擎上跑了 50 分钟配图，347 条候选全死掉，只活下 8 张。
一条控制词只要一次 HTTP GET，十几秒就能给出结论——判活不该靠猜（同 W-90）。

退出码：0 = 健康；1 = 部分查询在答非所问；2 = 全部控制词都没点名（别跑配图）；
3 = 传了 --topic 且这个领域此刻零点名而参照组活着（分钟级波动，下一窗可能就好）。
它不拦任何流水线，只是给"现在要不要开始跑图"提供一个数。
"""
import argparse
import io
import json
import os
import sys
import time

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import images as I
import outline as O

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# 控制词要跨领域、跨语言形态：只用中文品牌词，就会把"中文查询全灭"误判成引擎健康
CONTROLS = [(u"劳力士", u"劳力士 手表"), (u"积家", u"积家 机芯"),
            (u"咖啡", u"咖啡 手冲"), (u"LV", u"Louis Vuitton 手袋"),
            (u"宾利", u"宾利 汽车")]


def verdict(rows):
    """rows = [(topic, query, offered, named, usable)] → (状态, 说明)。

    判据只用一个数：**点名率过半的控制词有几条**，而且只看 `named` 不看 `usable`——
    这个线量的是"引擎现在能不能用"，把人的排除表算进来会因为人挑得认真而误判引擎坏。
    排除表抽干可用候选是另一件事，由 `starved_by_exclusions` 单独喊。
    每条词的原始 offered/named/usable 都照样打出来，看数的人不必信我这个标签。
    """
    if not rows:
        return "dead", u"一条都没搜到"
    good = [r for r in rows if r[3] * 2 >= max(1, r[2]) and r[3] > 0]
    junk = [r for r in rows if r[2] and not r[3]]
    if len(good) == len(rows):
        return "healthy", u"全部控制词点名过半"
    if not good:
        return "dead", u"所有控制词都答非所问（召回 %d 条，点名 0 条）" % sum(r[2] for r in rows)
    return "partial", u"%d/%d 条控制词点名过半，%d 条完全没点名" % (
        len(good), len(rows), len(junk))


def compare(global_rows, topic_rows):
    """把「零点名」分成两种处置相反的病：坏窗口 vs 品牌饿死。

    单看 topic_rows 分不出来——两者的原始形状一模一样（召回几十条、点名 0 条）。
    区别只在与参照组的比较上：
      别的品牌也全灭 → 引擎此刻在答非所问，换时间重试有用（D-14）。
      别的品牌都活、只有它全灭 → 这个词条在 Bing CN 就是搜不到图，
        等下去等不来（娇兰实测：4.3 小时 / 1958 次丢弃 / 活下 2 张）。
    """
    gstate = verdict(global_rows)[0]
    ostate = verdict(topic_rows)[0]
    if ostate == "dead" and gstate in ("healthy", "partial"):
        return "starved", u"参照组 %s，而这个领域零点名（召回 %d 条）" % (
            gstate, sum(r[2] for r in topic_rows))
    if ostate == "dead":
        return "window", u"参照组一起全灭，是引擎此刻的问题"
    return "ok", u"领域自己的检索词点得到名（%s）" % ostate


def topic_controls(topic, root=ROOT, limit=3):
    """给「这个领域现在能不能跑图」造控制词：**各章取第一条点名领域的检索词**。

    为什么不拿领域名当探针：`Muse产业逻辑` 是个短语，图搜里没有这种东西，
    拿它探必然零点名，于是 gate 会说「这篇不能跑」——那是探针的错不是引擎的错。
    为什么不能全取第一章：那一章恰好词形不好就误判整篇不能跑，
    恰好好就其余十章的坑一个没探到。
    凑不满 limit 条时才补一条品牌词（取最短的那个主语词，短语领域名不用）。
    """
    try:
        cfg = O.load_for_topic(topic, root=root)
    except Exception:
        cfg = None
    tokens = list(I.subject_tokens(cfg)) if cfg else [topic.lower()]
    if not tokens:
        tokens = [topic.lower()]
    pairs = []
    seen = set()
    for sec in getattr(cfg, "sections", []) or []:
        if len(pairs) >= limit:
            break
        for q in (sec.image_queries or []):
            q = str(q or "").strip()
            if not q or q in seen:
                continue
            if any(t in q.lower() for t in tokens):
                pairs.append((topic, q))
                seen.add(q)
                break
    if len(pairs) < limit:
        short = sorted(tokens, key=len)[0]
        if len(short) <= 4 and short not in seen:
            pairs.append((topic, short))
    return pairs[:limit]

def probe(controls=CONTROLS, root=ROOT, count=30):
    """每条控制词回五个数：(领域, 检索词, 召回, 点名, 排除后可用)。

    两个口径必须与采集器一致，否则裁判会撒两种相反的谎：
    ① **判点名要看 title+purl+murl**（`reject_reason` 就是这么看的），只看 title
       会把"标题没提领域、来源页提了"的可用图算成不可用；
    ② **人眼排除表另开一个数，不并进点名**。给 MLCC 加 7 条排除那一轮，探针照报
       "召回健康"，而 `collect()` 那边可用候选已经是 0——`specs` 最终空章、被 G-03
       拦下。但把排除算成"引擎坏"同样是错的：那会因为人挑得认真而把整篇判成不能跑。
       所以引擎健康度看 `named`，可用告急看 `usable`，两条分开喊。
    """
    rows = []
    for topic, q in controls:
        try:
            cfg = O.load_for_topic(topic, root=root)
            subj = I.subject_tokens(cfg)
            exclude = getattr(cfg, "image_exclude_pages", None) or []
        except Exception:
            subj, exclude = {topic.lower()}, []
        try:
            cands = I.search(q, count=count) or []
        except Exception as e:
            rows.append((topic, q, 0, 0, 0))
            continue
        named = usable = 0
        for c in cands:
            text = u"%s %s %s" % (c.title or u"", getattr(c, "purl", u"") or u"",
                                  getattr(c, "murl", u"") or u"")
            if not I.names_subject(text.lower(), subj):
                continue
            named += 1
            if not I.page_excluded((getattr(c, "purl", u"") or u"").split("#")[0], exclude):
                usable += 1
        rows.append((topic, q, len(cands), named, usable))
    return rows


def starved_by_exclusions(rows):
    """点名>0 而排除后可用=0 的词形：引擎没坏，是这篇的可用候选被人的判断清空了。
    这一条不改变引擎健康度的标签，但它必须喊出来——MLCC 那次空章就是这么来的。"""
    return [(r[0], r[1]) for r in rows if len(r) > 4 and r[3] > 0 and not r[4]]



def wait_until_healthy(probe=None, interval=300, max_wait=7200, sleep=time.sleep,
                       log=None, topic_probe=None, topic=None):
    """轮询到引擎可用为止，或到 max_wait 放弃。返回 True/False。

    为什么要有这一步：09-23 上午实测，同一条检索词**重复四次拿回同一页垃圾**
    （`咖啡 手冲` 四次都是 0 点名），所以"重试同一条词"在坏窗口里毫无意义，
    只会像娇兰那轮一样烧掉 1958 次丢弃、只活下 2 张图。
    能翻盘的只有两件事：换问法（W-110）或换时间（D-14）。这条就是"换时间"的机制化。
    到点必须返回 False——不能让调用方挂在一个永远不来的好窗口上。

    传了 topic_probe 就换一条判据：**放行只看这个领域自己的检索词点不点得到名**。
    参照组是别的品牌的病——13:06 实测参照组 积家/咖啡/LV 三条全灭（整体 partial），
    同一时刻 娇兰 自己的词 33/35 点名，那一轮空章从 8 降到 2。
    等一个"所有品牌都好"的时间片，等于把别人的故障算在它头上。
    零点名也不收工：13:00 探到 娇兰 0 点名，13:06 就跑通了——
    分钟级波动，唯一已验证有效的杠杆还是换时间，所以只能等到 max_wait 再放弃。
    """
    log = log or (lambda m: None)
    probe = probe or globals()["probe"]
    waited = 0
    while True:
        rows = probe()
        state, why = verdict(rows)
        if topic_probe is None:
            if state == "healthy":
                log(u"  引擎健康，可以开跑（等了 %d 分钟）" % (waited // 60))
                return True
            reason = why
        else:
            own = topic_probe()
            ostate, owhy = verdict(own)
            if ostate in ("healthy", "partial"):
                log(u"  %s 自己的检索词点得到名（%s），可以开跑（等了 %d 分钟；"
                    u"参照组此刻 %s，与本篇无关）" % (
                        topic or u"本领域", owhy, waited // 60, state))
                return True
            kind, kwhy = compare(rows, own)
            reason = u"%s零点名（%s）" % (u"品牌饿死：" if kind == "starved" else u"", kwhy)
        if waited >= max_wait:
            log(u"  等到 %d 分钟仍不能开跑（%s），放弃等待" % (max_wait // 60, reason))
            return False
        log(u"  还不能开跑（%s），%d 分钟后再探一次" % (reason, interval // 60))
        sleep(interval)
        waited += interval


def main(argv=None):
    ap = argparse.ArgumentParser(description=u"图搜引擎体检")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--topic", help=u"以这个领域自己的检索词为准判能不能开跑（参照组只当参照）")
    ap.add_argument("--wait-healthy", action="store_true",
                    help=u"轮询到健康才返回 0；到 --max-wait 仍不健康返回 1")
    ap.add_argument("--interval", type=int, default=300, help=u"轮询间隔（秒）")
    ap.add_argument("--max-wait", type=int, default=7200, help=u"最多等多久（秒）")
    args = ap.parse_args(argv)
    topic_ctl = topic_controls(args.topic, root=ROOT) if args.topic else None
    topic_probe = (lambda: probe(controls=topic_ctl)) if topic_ctl else None
    if args.wait_healthy:
        ok = wait_until_healthy(interval=args.interval, max_wait=args.max_wait,
                                log=lambda m: sys.stdout.write(m + "\n"),
                                topic_probe=topic_probe, topic=args.topic)
        return 0 if ok else 1
    rows = probe()
    state, why = verdict(rows)
    own = topic_probe() if topic_probe else None
    kind, kwhy = compare(rows, own) if own is not None else (None, None)
    # 调用方要的是"能不能给这篇开跑"，所以传了 --topic 就以本篇自己的词为准
    run_state, run_why = verdict(own) if own is not None else (state, why)
    if args.json:
        print(json.dumps({"state": state, "rows": rows, "topic": args.topic,
                          "topic_state": run_state, "can_run": run_state != "dead",
                          "brand_starved": kind == "starved",
                          "topic_rows": own}, ensure_ascii=False))
    else:
        for topic, q, offered, named, usable in rows:
            print(u"  %-6s %-24s 召回 %2d / 点名 %2d / 排除后可用 %2d"
                  % (topic, q, offered, named, usable))
        if own is not None:
            for _t, q, offered, named, usable in own:
                print(u"  %-6s %-24s 召回 %2d / 点名 %2d / 排除后可用 %2d   ← 本领域" % (
                    args.topic, q, offered, named, usable))
        label = {u"healthy": u"✓ 健康", u"partial": u"! 部分查询答非所问",
                 u"dead": u"✗ 引擎在答非所问"}
        if own is None:
            print(u"%s：%s" % (label[state], why))
        else:
            print(u"参照组 %s：%s" % (label[state], why))
            print(u"%s %s：%s" % (label[run_state], args.topic, run_why))
        if kind == "starved":
            print(u"! 此刻 %s 零点名而参照组活着（%s）。"
                  u"这不是判它死刑：13:00 探到零点名、13:06 同一批词跑通了 6 章。"
                  u"要等就 --wait-healthy --topic %s。" % (args.topic, kwhy, args.topic))
        # 引擎没坏、可用却被人的排除表清空——MLCC 的 specs 空章就是这个形状。
        # 不改健康度标签（那是引擎的问题），但必须单独喊一句。
        empty = starved_by_exclusions(own if own is not None else rows)
        if empty:
            print(u"! %d 条词形点名>0 但排除表之后可用=0：%s"
                  u" —— 引擎是好的，跑下去这些章会空、被 G-03 拦下；"
                  u"要么补词形，要么确认排除表是不是划得太宽。"
                  % (len(empty), u"、".join(q for _t, q in empty[:4])))
            return 3
    return {"healthy": 0, "partial": 1, "dead": 2}[run_state]


if __name__ == "__main__":
    sys.exit(main())
