# -*- coding: utf-8 -*-
"""10 套主题的文字用色必须过 WCAG AA（W-50）。

浏览器版全量扫描在 `scripts/sweep_tokens.py`（慢，约 2 分钟，手动/夜间跑）；
这里只验"产物里算出来的墨色达标"，不开浏览器，跑得起才进得了 pre-commit。
"""
import io
import json
import os
import re
import subprocess

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_DATA = os.path.join(ROOT, "demo_site", "output", u"咖啡", "data.json")
TOKENS = ["coffee-roast", "chanel-noir", "hermes-orange", "patek-calatrava",
          "jaeger-reverso", "rolex-oyster", "lv-monogram", "longines-winged",
          "bentley-racing", "rolls-argenteal"]


def _rgb(hexs):
    h = hexs.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def _lum(c):
    f = lambda v: (v / 255)
    r, g, b = [(s / 12.92 if s <= 0.03928 else ((s + 0.055) / 1.055) ** 2.4)
               for s in map(f, c)]
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def ratio(a, b):
    x, y = _lum(_rgb(a)), _lum(_rgb(b))
    return (max(x, y) + 0.05) / (min(x, y) + 0.05)


@pytest.fixture(scope="module")
def pages(tmp_path_factory):
    """一次渲染 10 套主题，返回 {token: 产物 CSS 里的变量表}。"""
    base = json.load(io.open(SRC_DATA, encoding="utf-8"))
    out = {}
    for tok in TOKENS:
        d = tmp_path_factory.mktemp(tok)
        payload = json.loads(json.dumps(base))
        payload["theme"]["token"] = tok
        dp = d / "data.json"
        dp.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        page = d / ("%s.html" % tok)
        r = subprocess.run(["node", os.path.join("scripts", "render.mjs"),
                            "--data", str(dp), "--out", str(page)],
                           cwd=ROOT, capture_output=True, timeout=300)
        assert r.returncode == 0, r.stderr.decode("utf-8", "ignore")[-300:]
        css = io.open(str(page), encoding="utf-8").read()
        out[tok] = dict(re.findall(r"--([a-z-]+):(#[0-9a-fA-F]{3,6})", css))
    return out


def test_every_text_color_clears_aa_on_its_own_background(pages):
    """墨色是算出来的（styles.ts inkFor），这里复核算的确实对：
    强调色小字压页面底色、primary 压 soft、muted 压 surface 与 soft，都要 ≥4.5。"""
    bad = []
    for tok, v in pages.items():
        checks = [("accent-ink", "bg"), ("primary-ink", "soft"),
                  ("muted-ink", "surface"), ("muted-ink", "soft"),
                  ("ink", "bg"), ("ink", "surface")]
        for fg, bg in checks:
            got = ratio(v[fg], v[bg])
            if got < 4.5:
                bad.append(u"%s %s on %s = %.2f" % (tok, fg, bg, got))
    assert not bad, u"以下主题文字对比度不达标：" + u"；".join(bad)


def test_brand_color_is_not_flattened_to_black(pages):
    """修对比度不能把品牌色洗成黑白——那是把"每个领域不一样"改没了（D-03）。
    浅底主题允许压暗，但不许压到纯黑/纯白。"""
    for tok, v in pages.items():
        ink = _rgb(v["accent-ink"])
        assert ink not in ((0, 0, 0), (255, 255, 255)), \
            u"%s 的强调墨色被洗成了纯黑/纯白" % tok
