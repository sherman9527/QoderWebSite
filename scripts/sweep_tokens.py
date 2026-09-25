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

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "demo_site", "output", u"咖啡")
WORK = os.path.join(ROOT, ".probe", "tokens")
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
        m = subprocess.run(["node", os.path.join("scripts", "measure-layout.mjs"),
                            "--file", page],
                           cwd=ROOT, capture_output=True, timeout=300)
        out = m.stdout.decode("utf-8", "ignore").strip().splitlines()
        if m.returncode == 0:
            print("%-24s %s" % (tag, out[-1]))
        else:
            bad.append(tag)
            print("%-24s %s" % (tag, out[-1]))
            for line in out[:6]:
                if line.startswith("FAIL"):
                    print("    %s" % line[:150])
    print("\n翻车主题：%s" % (u"、".join(bad) if bad else u"无"))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
