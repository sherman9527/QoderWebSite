# -*- coding: utf-8 -*-
"""W-42b：研究中间文件的清理策略。

钉住两件事：可追溯性不依赖这些副本（URL 已记在 manifest/data.json），
以及**默认不删**——删文件不可逆，必须显式 --apply。
"""
import io
import os
import time

import prune_scratch as P


def _mk(path, age_days):
    io.open(path, "w", encoding="utf-8").write("x")
    t = time.time() - age_days * 86400
    os.utime(path, (t, t))


def test_only_files_older_than_the_window_are_selected(tmp_path, monkeypatch):
    scratch = str(tmp_path)
    _mk(os.path.join(scratch, "old.html"), 30)
    _mk(os.path.join(scratch, "recent.html"), 1)
    os.makedirs(os.path.join(scratch, "rejects"))
    _mk(os.path.join(scratch, "rejects", "old2.txt"), 90)
    got = {os.path.basename(p) for p in P.stale_files(scratch, 7)}
    assert got == {"old.html", "old2.txt"}, got


def test_dry_run_is_the_default(tmp_path, monkeypatch, capsys):
    scratch = str(tmp_path)
    _mk(os.path.join(scratch, "old.html"), 30)
    monkeypatch.setattr(P, "SCRATCH", scratch)
    assert P.main([]) == 0
    assert os.path.isfile(os.path.join(scratch, "old.html")), "没加 --apply 就删了文件"
    assert "未删除" in capsys.readouterr().out


def test_apply_deletes_only_stale(tmp_path, monkeypatch):
    scratch = str(tmp_path)
    _mk(os.path.join(scratch, "old.html"), 30)
    _mk(os.path.join(scratch, "recent.html"), 1)
    monkeypatch.setattr(P, "SCRATCH", scratch)
    assert P.main(["--apply"]) == 0
    assert not os.path.exists(os.path.join(scratch, "old.html"))
    assert os.path.isfile(os.path.join(scratch, "recent.html"))
