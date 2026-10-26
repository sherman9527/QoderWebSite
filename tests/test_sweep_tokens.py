# -*- coding: utf-8 -*-
"""`sweep_tokens.py` 怎么读 measure-layout 的下场。

这台扫描每套主题都要开一次真浏览器，是全站里对 measure-layout 压力最大的调用方之一，
而它以前**没有测试**——因为它只是个手动跑的脚本。W-199 要的是"工具死了要留下现场"，
而这里死法是 IndexError 崩掉整轮扫描：报出来的是一行 traceback，
读的人不会知道"这一档根本没量成"，更不会知道它是第几档。
"""
from __future__ import unicode_literals

import io
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import sweep_tokens as SW  # noqa: E402


def test_a_silent_tool_is_named_as_not_measured_not_a_crash():
    """rc 非 0 且一行都没吐：这是"没查过"，必须成为一条看得见的失败档。

    旧写法是 `out[-1]`，stdout 为空时 `out` 是 `[]`，整轮扫描在这里炸掉，
    而崩之前那句 print 都没有——一次死亡连"哪一档"都没留下。
    """
    bad, line, fails = SW._measure_verdict(1, "")
    assert bad, u"工具死了却不算翻车，等于让跳过冒充通过"
    assert line and u"没吐出结果" in line, u"要说清是「没量到」而不是别的东西：%s" % line
    assert fails == []


def test_a_deaths_line_records_the_rc_so_two_samples_can_be_compared():
    """死法要带上 rc：10-10 那次是「抓到 0 条」，10-12 是 rc=-1、stdout 0 字节，
    两条签名不同却被当成同一个 bug 找了两轮（判据见 HANDOVER W-199）。"""
    bad, line, _ = SW._measure_verdict(-1073741819, "")
    assert bad
    assert u"-1073741819" in line, u"没把 rc 带上，攒样本时对不上号：%s" % line


def test_a_tool_that_ran_still_reports_its_last_line():
    """正常路径不许被我改坏：跑成了就照原样给最后一行，查出问题就给出 FAIL 行。"""
    bad, line, fails = SW._measure_verdict(0, "OK 一切正常\nPASS 12 档量到")
    assert not bad and line == u"PASS 12 档量到" and fails == []
    bad2, line2, fails2 = SW._measure_verdict(1, "FAIL 侧栏溢出 40px\nFAIL 封面太高")
    assert bad2 and len(fails2) == 2, u"翻车行没交出去：%s" % fails2
