#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""W-50：拿同一份内容把 10 套主题 token 全渲染一遍，逐个跑 G-13 真浏览器几何。

为什么值得单独跑：几何缺陷只在特定配色/字族下出现（深色主题的对比度与
box-shadow 方向、不同 displayFamily 的行高都会改变盒子）。只看咖啡一套
等于没测。产物落在 .probe/tokens/，不进 output/，免得污染质量闸门扫描。
"""
import io
import json
import os
import re
import shutil
import subprocess
import sys
import time

# Windows 上 stdout 默认按 ANSI 码页（这台机器是 GBK）编码，而本仓库的输出里全是
# 中文与 ⇒/≠/· 这类非 GBK 字符。少这道守卫不是显示难看，是**直接崩**：
# 10-26 就是 validate.py 打印一条 G-15 告警里的 ⇒ 时抛 UnicodeEncodeError，
# 把 9 篇渲染打成 rc=1 —— 看着像质量闸门拦的，其实是编码。守卫本身由
# tests/test_contract.py 那条"会 print 的脚本必须钉住输出编码"守住。
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "demo_site", "output", u"咖啡")
WORK = os.path.join(ROOT, ".probe", "tokens")
def _measure_verdict(rc, stdout_text):
    """把 measure-layout 的下场读成 `(是否翻车, 打印哪一行, 哪些 FAIL 行)`。

    **一行都没吐 = 没查过**，不是"查过且没问题"。旧写法是 `out[-1]`，stdout 为空时
    `out` 就是 `[]`，整轮扫描在这里 IndexError——崩在一行 traceback 上，
    连"第几档死的"都没留下，而那正是 W-199 想要的信息。
    """
    out = [l.strip() for l in (stdout_text or u"").splitlines() if l.strip()]
    if not out:
        return True, u"几何没吐出结果（rc=%s，stdout 0 行）——这一档等于没量过" % rc, []
    fails = [l for l in out if l.startswith(u"FAIL")]
    return rc != 0, out[-1], fails


def _note_death(tag, rc, stdout_bytes, stderr_text, elapsed_ms):
    """死讯交给 validate 那台已经在攒现场记录的器（**同一个 jsonl**，跨调用方攒样本）。

    扫描是全仓库对 measure-layout 压力最大的调用方之一，它的死亡本来落在记录之外；
    两处各写一套格式的话，攒到的样本没法放在一起比。记不上就算了，判据不依赖它。
    """
    try:
        sys.path.insert(0, os.path.join(ROOT, "scripts"))
        import validate as V
        V._record_g13_death(tag, rc, stdout_bytes, stderr_text, elapsed_ms=elapsed_ms)
    except Exception:
        pass


def _themes():
    """主题清单从 `web/src/tokens/index.ts` 读，不在这里再抄一份名单。
    以前是写死的 10 个，加第 11 个领域时这里不会报错——只会静默不跑，
    于是"每套主题都过 G-13"这句话悄悄变成了假话。"""
    src = io.open(os.path.join(ROOT, "web", "src", "tokens", "index.ts"),
                  encoding="utf-8").read()
    return re.findall(r'^  "([a-z0-9-]+)": \{', src, re.M)


TOKENS = _themes()


def main():
    data = json.load(io.open(os.path.join(SRC, "data.json"), encoding="utf-8"))
    bad = []
    if os.path.isdir(WORK):
        shutil.rmtree(WORK)
    # 两套都要跑：有封面走 <img>，无封面走领域记忆点（.cover-noimg 那条路径
    # 出过"一条色带浮在空色块里"的观感事故，只有无封面态才看得见）。
    cases = [(t, True) for t in TOKENS] + [(t, False) for t in TOKENS]
    for tok, with_photo in cases:
        tag = tok if with_photo else tok + "-motif"
        d = os.path.join(WORK, tag)
        os.makedirs(os.path.join(d, "images"))
        if with_photo:
            for f in os.listdir(os.path.join(SRC, "images")):
                shutil.copyfile(os.path.join(SRC, "images", f),
                                os.path.join(d, "images", f))
        payload = json.loads(json.dumps(data))
        payload["theme"]["token"] = tok
        # 每套主题都必须被量到**每一种会涂身份色的小字**。咖啡那篇没有 bar_chart，
        # 于是 .chart .val 用 primary 原色涂小字这件事，扫描全绿而线上 27 篇里
        # 有一篇被 G-13 当场拦下（深芥压在 surface 上 3.25:1）。
        # 这块是几何探针，不是内容：数值是编的，扫描不跑 G-06。
        payload["sections"][0]["blocks"].append({
            "type": "bar_chart", "heading": u"扫描探针：条形数值是身份色小字，必须过对比度",
            "unit": u"%", "as_of": u"2026-01",
            "bars": [{"label": u"甲", "value": 42}, {"label": u"乙", "value": 78},
                     {"label": u"丙", "value": 15}]})
        payload["sections"][0]["blocks"].append({
            "type": "steps", "title": u"扫描探针：步骤序号是身份色小字",
            "items": [{"n": i, "title": u"第%d步" % i, "text": u"序号涂在 soft 底上，量的是它。",
                       "spec": u"探针"} for i in (1, 2, 3)]})
        if not with_photo:
            payload.pop("cover", None)
            for s in payload["sections"]:
                s["images"] = []
        dp = os.path.join(d, "data.json")
        io.open(dp, "w", encoding="utf-8").write(json.dumps(payload, ensure_ascii=False))
        page = os.path.join(d, "%s.html" % tag)
        r = subprocess.run(["node", os.path.join("scripts", "render.mjs"),
                            "--data", dp, "--out", page],
                           cwd=ROOT, capture_output=True, timeout=300)
        if r.returncode != 0:
            print("%-24s 渲染失败 %s" % (tag, r.stderr.decode("utf-8", "ignore")[-160:]))
            bad.append(tag)
            continue
        t0 = time.monotonic()
        m = subprocess.run(["node", os.path.join("scripts", "measure-layout.mjs"),
                            "--file", page],
                           cwd=ROOT, capture_output=True, timeout=300)
        mbad, line, fails = _measure_verdict(m.returncode,
                                             m.stdout.decode("utf-8", "ignore"))
        print("%-24s %s" % (tag, line))
        if mbad:
            bad.append(tag)
            if not line.startswith(u"FAIL"):
                _note_death(tag, m.returncode, len(m.stdout or b""),
                            m.stderr.decode("utf-8", "ignore"),
                            int((time.monotonic() - t0) * 1000))
            for l in fails[:6]:
                print("    %s" % l[:150])
    print("\n翻车主题：%s" % (u"、".join(bad) if bad else u"无"))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
