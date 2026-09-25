# -*- coding: utf-8 -*-
"""红线（rule.md 第一节）的可执行断言。

红线不是宣言：每条生效红线都必须在这里有一个"违反它就失败"的用例，
否则它会在下一次赶工的时候静默失守。
"""
import copy
import io
import json
import os

import pytest

import images as IM
import validate as V
from conftest import make_passing_data
from test_gates import by_id

ROOT = V.ROOT


# ── 红线 R-03 / R-04：图片必须有来源页；不得拿 logo / 壁纸 / 广告大片当装饰 ──

def test_R03_self_drawn_illustration_is_allowed_but_cannot_fake_a_source(quality_bar):
    """D-22 改后的 R-03：引用图必须有 source_page；自制示意图必须有 `based_on`，
    而且**禁止**带 source_page。放行示意图的前提是它不能冒充引用图，
    所以三个方向都要钉住：合法示意图过、带来源页的示意图死、没依据的示意图死。"""
    def check(img):
        data = make_passing_data()
        data["sections"][0]["images"][0] = img
        ctx = V.Ctx(u"红线", ".", "x.html", "<html></body>", data, quality_bar)
        return [str(f) for f in (by_id("G-10").check(ctx) or []) if f.level == "fail"]

    good = {"file": "images/01_交错内电极剖面.png", "kind": "illustration",
            "alt": u"示意图·非实拍：陶瓷介质层与镍内电极交替叠层",
            "caption": u"按正文已溯源的结构参数绘制",
            "based_on": [u"sec-01#层数与介质厚度"], "width": 1200, "height": 800}
    assert not check(dict(good)), u"合法自制示意图被 schema 判死了"

    faking = dict(good, source_page="https://example.com/whatever")
    assert check(faking), u"示意图带上了 source_page 却没被拦——它就能冒充引用图"

    baseless = {k: v for k, v in good.items() if k != "based_on"}
    assert check(baseless), u"没有 based_on 的示意图被放过了：画错了没人能追责"

    # 默认仍是引用图：没写 kind 的图缺 source_page 照样死（上面那条 R-03 原测试守着）


def test_R03_data_schema_rejects_image_without_source_page(quality_bar):
    data = make_passing_data()
    del data["sections"][0]["images"][0]["source_page"]
    ctx = V.Ctx(u"红线", ".", "x.html", "<html></body>", data, quality_bar)
    fails = [f for f in (by_id("G-10").check(ctx) or []) if f.level == "fail"]
    assert any("source_page" in str(f) for f in fails), \
        "无源图片通过了 schema 校验，红线 R-03 等于没写：%s" % [str(f) for f in fails]


@pytest.mark.parametrize("title,slug", [
    (u"Chanel 官方 logo 矢量图 PNG 下载", "chanel"),
    (u"劳力士 壁纸 高清桌面 4K", "rolex"),
    (u"Hermès 广告大片 key visual 2024", "hermes"),
    (u"百达翡丽 poster 海报 裱框装饰画", "patek"),
])
def test_R04_rejects_logo_wallpaper_and_ad_creatives(title, slug):
    """关键词命中、分辨率很高、体积很大——单看这些全是好图。
    但 logo / 壁纸 / 广告大片 / 海报没有信息价值，还有版权风险（红线 R-04）。"""
    cand = IM.Candidate(title=title, murl="https://img.example/%s.jpg" % slug,
                        turl="", purl="https://example.com/%s/page" % slug)
    got = IM.score(cand, 2000, 1200, 300 * 1024, [slug])
    assert got < 0, "无信息量的装饰图被收下了（score=%s）" % got


# ── 红线 R-07：依赖安装必须国内镜像优先（写进仓库，不靠机器全局配置） ──

def test_R07_npm_registry_pinned_in_repo():
    p = os.path.join(ROOT, "web", ".npmrc")
    assert os.path.isfile(p), "web/.npmrc 不存在——镜像配置只在这台机器的全局 npm 里，换机即失守"
    txt = io.open(p, encoding="utf-8").read()
    assert "registry.npmmirror.com" in txt, txt


def test_R07_pip_index_pinned_in_requirements():
    txt = io.open(os.path.join(ROOT, "requirements.txt"), encoding="utf-8").read()
    assert "--index-url" in txt, "requirements.txt 没有固定主源，pip 会退回官方源"
    assert "tuna" in txt or "aliyun" in txt, txt


# ── 红线本身要能被读到：解析失败 = 全部红线静默失效 ──

def test_R_active_lines_are_parsed_by_validate():
    """G-09 靠 active_red_lines() 读 rule.md。格式一改（比如加了 ** 强调）
    解析就会返回空列表，红线看着在、其实一条都没生效。"""
    lines = V.active_red_lines()
    ids = [rid for rid, _ in lines]
    assert ids == ["R-%02d" % i for i in range(1, len(ids) + 1)], \
        "rule.md 生效红线解析结果异常（只解析到 %s）" % ids
    assert len(ids) >= 8, "生效红线只有 %d 条，rule.md 第一节大概没被解析" % len(ids)


def test_R_every_active_line_declares_a_detector():
    for rid, rule in V.active_red_lines():
        assert V.red_line_has_detector(rule), \
            "%s 没写检测方式，等于无法执行：%s" % (rid, rule[:60])


def test_R09_gate_warns_only_for_undetected_lines(monkeypatch, quality_bar):
    monkeypatch.setattr(V, "active_red_lines",
                        lambda: [("R-99", u"一条没有检测器的红线")])
    ctx = V.Ctx(u"红线", ".", "x.html", "<html></body>", make_passing_data(), quality_bar)
    got = [f for f in (by_id("G-09").check(ctx) or [])]
    assert any(f.level == "warn" and "R-99" in str(f) for f in got), \
        "没有检测器的红线必须显式告警，不能静默通过"


def test_R08_scratch_dir_is_gitignored():
    txt = io.open(os.path.join(ROOT, ".gitignore"), encoding="utf-8").read()
    assert ".research-scratch/" in txt


# ── 红线 R-09：样式改动必须有真浏览器几何断言（G-13 自证用例在 test_gates.py） ──

def test_R09_layout_gate_is_self_proven():
    """闸门本身要被证明有效：注错必须被抓到，否则它只是个摆设。"""
    src = io.open(os.path.join(ROOT, "scripts", "measure-layout.mjs"), encoding="utf-8").read()
    for gate in ("prose-measure", "img-upscale", "fig-wall", "h1-clipped"):
        assert gate in src, "G-13 少了 %s 检查" % gate
    tests = io.open(os.path.join(ROOT, "tests", "test_gates.py"), encoding="utf-8").read()
    for gate in ("prose-measure", "img-upscale", "fig-wall"):
        assert gate in tests, "%s 没有对应的注错用例" % gate
