# -*- coding: utf-8 -*-
"""W-170 的守卫：审计链必须在版本库里，且台账指到的路径要能解析。

为什么值得占一个测试位：handover 规则要求 COMPLETE 每条带"能点开的证据指针"，
而 10-02 之前那些指针全写在 `.probe/`——被 .gitignore 忽略，
`git ls-files .probe` 是空的。也就是说这条纪律**只在开发机上成立**，
换台机器就退化成"Done 不算证据"那句话本身。测试是唯一能把它钉住的形状。
"""
import io
import os
import re
import subprocess

import pytest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def _git(*args):
    return subprocess.run(["git"] + list(args), cwd=ROOT, capture_output=True)


def test_audit_tools_are_tracked():
    out = _git("ls-files", "audit/tools").stdout.decode("utf-8", "ignore")
    tracked = [l for l in out.splitlines() if l.strip()]
    assert "audit/tools/w157_hand.py" in tracked, u"裁决工具没进版本库，审计链又回到 gitignore 里了"
    assert "audit/tools/w162_scan.py" in tracked, u"判据（派生规则）没进版本库"


def test_audit_records_are_tracked():
    out = _git("ls-files", "audit/records").stdout.decode("utf-8", "ignore")
    n = len([l for l in out.splitlines() if l.strip()])
    assert n >= 20, u"audit/records 只有 %d 份记录，裁决 JSON 没搬全" % n


@pytest.mark.parametrize("name", [
    "w157_hand.py", "w157_scan.py", "w162_scan.py", "w162_measure.py", "w164_measure.py",
    "w164_evidence.py", "w164_sweep.py", "w164_windows.py",
    "w193_read.py", "w193_triage.py", "w193_rollup.py", "w193_ledger.py", "w193_alist.py",
    "livecmp.py", "fill_sections.py",
    # W-199 那批探针从 .probe/ 搬进来了：台账留着它们，是因为"两条候选假设都被量掉了"
    # 这个结论只有可重跑才算证据。搬过来第一件事就是 ROOT 层数——见下面那条测试的说明。
    "w199_probe.py", "w199_leak.py", "w199_real.py", "w199_conc.py",
])
def test_moved_tool_resolves_the_repo_root(name):
    """搬家最容易坏的不是 import 而是 ROOT 层数：`.probe/` 深一层，`audit/tools/` 深两层。
    层数错了工具会去错误的路径读写欠账清单——不报错，只是把账记到别处。
    这正是 10-02 第一次搬完时发生的事。"""
    rel = os.path.join("audit", "tools", name)
    src = io.open(os.path.join(ROOT, rel), encoding="utf-8").read()
    lines = [l for l in src.splitlines() if l.strip().startswith("ROOT =")]
    if not lines:
        pytest.skip(u"%s 不定义 ROOT，不需要验层数" % name)
    g = {"__file__": os.path.join(ROOT, rel), "os": os}
    exec(lines[0].strip(), g)
    assert os.path.normcase(g["ROOT"]) == os.path.normcase(ROOT), \
        u"%s 里的 `%s` 解析成 %s，不是仓库根 %s" % (name, lines[0].strip(), g["ROOT"], ROOT)


# `.txt` 必须在选择支里：10-05 把 W-191 的三份测量证据搬进 `audit/records/*.txt` 之后，
# 这条守卫对它们**一条都没判过**——正则只认 jsonl/json/md/py，`.txt` 指针写得再准也没人验。
# 顺带解释了一个更早的疑点：为什么有指针指向不存在的文件却一直是绿的。
AUDIT_POINTER = re.compile(r"audit/[A-Za-z0-9_./-]*\.(?:jsonl|json|md|py|txt)")


def test_a_txt_pointer_is_checked_at_all():
    """钉住这次的修法本身：证据文件最常见的形状就是 .txt（跑出来的报表），
    而它曾经完全落在正则之外。"""
    m = AUDIT_POINTER.search(u"实测见 audit/records/w168_naming.txt 与 audit/tools/x.py")
    assert m.group(0) == u"audit/records/w168_naming.txt", m.group(0)
    assert os.path.isfile(os.path.join(ROOT, m.group(0).replace("/", os.sep))), \
        u"台账指着一个不存在的 .txt，而这条守卫曾经看不见它"


def test_a_jsonl_pointer_is_matched_whole_not_truncated():
    """.jsonl 的指针必须整段匹配到 .jsonl。

    为什么单独立一条：选择支 `json|jsonl` 里 json 先命中，`.jsonl` 会被截成
    `.json`，于是"这条指针指向不存在的文件"永远为真——**任何指向 jsonl 的
    证据都没法写进台账**。10-04 W-164 报的就是 `audit/records/w157_decisions.json`
    缺失，而那个 .jsonl 就在它旁边。
    """
    m = AUDIT_POINTER.search(u"理由逐条在 audit/records/w157_decisions.jsonl 里")
    assert m is not None
    assert m.group(0) == u"audit/records/w157_decisions.jsonl", \
        u"截断成了 %s" % m.group(0)


def test_every_audit_pointer_in_the_ledger_resolves():
    """台账里 `audit/...` 形式的证据指针必须真的存在。"""
    t = io.open(os.path.join(ROOT, "HANDOVER.md"), encoding="utf-8").read()
    bad = []
    for m in AUDIT_POINTER.finditer(t):
        p = m.group(0).rstrip(u"，。；")
        if not os.path.isfile(os.path.join(ROOT, p.replace("/", os.sep))):
            bad.append(p)
    assert not bad, u"台账指向不存在的审计文件：%s" % bad[:6]


def test_the_probe_to_audit_move_is_documented():
    """历史条目里仍写着 `.probe/...`（那些路径当时是真的），必须有一处说明去哪找。"""
    t = io.open(os.path.join(ROOT, "HANDOVER.md"), encoding="utf-8").read()
    assert u"audit/tools" in t and (u"搬家" in t or u".probe" in t), \
        u"台账里还留着 .probe 指针，却没有一处说明它们搬到了 audit/"


TODO_ID = re.compile(r"^- \[ \] (W-\d+)", re.M)
COMPLETE_ID = re.compile(r"^\| \d{4}-\d{2}-\d{2} \| (W-\d+) \|", re.M)


def _sections():
    t = io.open(os.path.join(ROOT, "HANDOVER.md"), encoding="utf-8").read()
    todo = t.split(u"## TODO")[1].split(u"## COMPLETE")[0]
    done = t.split(u"## COMPLETE")[1]
    return todo, done


def test_no_work_item_is_listed_twice_in_todo():
    """同一编号在 TODO 里出现两次——10-06 真发生过：
    更正脚本把 `lines[a:b]` 写成 `lines[b:b]`，那是**插入**不是替换，
    旧的那块（还带着已作废的数）留在台账里，而当时没有任何测试看得见这件事。"""
    todo, _done = _sections()
    ids = TODO_ID.findall(todo)
    dup = sorted(set(i for i in ids if ids.count(i) > 1))
    assert not dup, u"TODO 里重复的工作项：%s" % dup


def test_a_finished_item_lives_in_exactly_one_place():
    """handover 的第一条规矩：做完 = 从 TODO 删掉、追加进 COMPLETE。
    两边都留着，下一个人就不知道哪份是真的。"""
    todo, done = _sections()
    both = sorted(set(TODO_ID.findall(todo)) & set(COMPLETE_ID.findall(done)))
    assert not both, u"既在 TODO 又在 COMPLETE：%s" % both


def test_importing_a_tool_must_not_truncate_its_own_report():
    """10-06 我自己撞的：为了单测 `expected_claims()` 顺手 import 了一次 `w164_sweep`，
    而它在模块顶层写着 `OUT = io.open(OUT_PATH, "w")` —— import 这个动作本身
    就把全站合计表清空了。文件没坏在任何报错里，只是**变空**，
    下一次读它的人会以为"没跑过"。

    判据要的就是这个形状：import 前后产物必须一字不变。
    """
    import importlib
    import sys
    rel = os.path.join("audit", "records", "w164_sweep_full.txt")
    p = os.path.join(ROOT, rel)
    if not os.path.isfile(p):
        pytest.skip(u"这台机器还没跑过全站扫描，没有产物可保护")
    before = io.open(p, encoding="utf-8").read()
    assert before.strip(), u"合计表已经是空的——先重跑 `python audit/tools/w164_sweep.py`"
    sys.path.insert(0, os.path.join(ROOT, "audit", "tools"))
    try:
        importlib.import_module("w164_sweep")
    finally:
        sys.path.remove(os.path.join(ROOT, "audit", "tools"))
    after = io.open(p, encoding="utf-8").read()
    assert after == before, u"import 一个工具把它的报告改写了（长度 %d → %d）" % (
        len(before), len(after))


def test_the_evidence_tool_still_runs_as_a_cli(tmp_path):
    """判据文件的函数**定义顺序**也是会被改坏的：10-08 我把 W-197 那几个函数接到文件末尾，
    正好落在 `if __name__ == "__main__"` 之后——import 得到（pytest 全绿），
    但 sweep 以子进程跑它时先执行 main()，`number_cells` 还没定义 ⇒ 29 篇全炸，
    而 `audit/records/w164_sweep_full.txt` 已经被写坏一半。
    所以这条不测判据算得对不对，只测**那条命令行还跑不跑得通**。
    """
    import subprocess
    import sys
    topic = sorted(os.path.splitext(f)[0] for f in os.listdir(os.path.join(ROOT, "config", "topics"))
                   if f.endswith(".json"))[0]
    r = subprocess.run([sys.executable, os.path.join(ROOT, "audit", "tools", "w164_evidence.py"), topic],
                       capture_output=True, cwd=ROOT)
    assert r.returncode == 0, u"%s 跑不动：%s" % (topic, r.stderr.decode("utf-8", "replace")[-500:])
