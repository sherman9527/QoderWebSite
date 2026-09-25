# -*- coding: utf-8 -*-
"""CLI 适配层（specs/knowledge-page-generation + memo 环境事实）。

不打真实模型：全部用注入的 runner。真模型的联调在 generate.py 的 smoke 上单独跑。
"""
import io
import json
import os

import pytest

import llm as L


def cli_json(result, search_requests=0):
    return json.dumps({
        "type": "result", "result": result, "stop_reason": "end_turn",
        "usage": {"server_tool_use": {"web_search_requests": search_requests,
                                      "web_fetch_requests": 0},
                  "input_tokens": 0, "output_tokens": 0},
        "permission_denials": [],
    }).encode("utf-8")


# ------------------------------------------------------------------ 命令行

def test_prompt_never_appears_in_argv():
    """提示词必须走 stdin：--allowed-tools 这类可变参数旗标会吞掉位置参数。"""
    argv = L.build_argv("qodercli", online=True)
    assert all("联网" not in a for a in argv)
    assert argv[0] == L.QODER and "-p" in argv


def test_online_call_grants_permission():
    """实测：不加 bypass_permissions，模型会自己放弃查证并反问要不要联网。"""
    assert "bypass_permissions" in " ".join(L.build_argv("qodercli", online=True))
    assert "bypass_permissions" not in " ".join(L.build_argv("qodercli", online=False))


def test_unknown_backend_rejected():
    with pytest.raises(L.LlmUnavailable):
        L.build_argv("chatgpt-cli", True)


# ------------------------------------------------------------------ 输出解析

def test_parse_result_from_cli_json():
    text, meta = L.parse_cli_output(cli_json(u"正文内容"))
    assert text == u"正文内容"
    assert meta["usage"]["server_tool_use"]["web_search_requests"] == 0


def test_parse_falls_back_to_plain_output():
    text, meta = L.parse_cli_output(b"just some plain text")
    assert text == "just some plain text" and meta is None


def test_parse_rejects_empty():
    with pytest.raises(L.LlmError):
        L.parse_cli_output(b"")


def test_decode_survives_gbk_console():
    """qodercli 在 Windows 上可能按代码页输出，UTF-8 失败要能退 GBK。"""
    raw = u"中文正文".encode("gbk")
    text, _ = L.parse_cli_output(raw)
    assert u"中文" in text


# ------------------------------------------------------------------ JSON 三级容错

def test_extract_plain_json():
    assert L.extract_json('{"a": 1}') == {"a": 1}


def test_extract_from_code_fence():
    assert L.extract_json('好的，这是结果：\n```json\n{"a": 1}\n```\n希望有帮助') == {"a": 1}


def test_extract_balanced_object_with_prose_around():
    s = u'前置说明 {"a": {"b": [1,2,3]}, "c": "有 } 花括号在字符串里"} 后置说明'
    assert L.extract_json(s) == {"a": {"b": [1, 2, 3]}, "c": u"有 } 花括号在字符串里"}


def test_extract_raises_when_nothing_parseable():
    with pytest.raises(L.LlmError):
        L.extract_json(u"对不起，我无法完成这个任务")
    with pytest.raises(L.LlmError):
        L.extract_json('{坏掉的 json')


# ------------------------------------------------------------------ 联网判据

def test_grounded_detection_ignores_cli_counter():
    """web_search_requests 恒为 0 不可信：判联网只看内容里有没有 URL。"""
    assert L.looks_grounded(u"公价约 13.55 万元，见 https://k.sina.com.cn/article_1.html")
    assert not L.looks_grounded(u"我没有联网查证，凭印象大约是十几万")
    assert not L.looks_grounded("")


# ------------------------------------------------------------------ call 行为

def test_call_uses_runner_and_returns_text():
    seen = {}

    def runner(argv, prompt, timeout):
        seen["argv"] = argv
        seen["prompt"] = prompt
        return cli_json(u"内容")

    out = L.call(u"写点什么", runner=runner, backends=["qodercli"])
    assert out == u"内容"
    assert seen["prompt"] == u"写点什么"


def test_call_retries_then_falls_back_to_second_backend():
    calls = []

    def runner(argv, prompt, timeout):
        calls.append(argv[1] if len(argv) > 1 else "")
        if "qodercli" in argv[0] or L.QODER in argv[0]:
            raise RuntimeError("boom")
        return cli_json(u"来自兜底后端")

    out = L.call(u"x", runner=runner, backends=["qodercli", "copilot"], retries=1)
    assert out == u"来自兜底后端"


def test_call_fails_loudly_when_all_backends_fail():
    def runner(argv, prompt, timeout):
        raise RuntimeError("nope")
    with pytest.raises(L.LlmUnavailable):
        L.call(u"x", runner=runner, backends=["qodercli", "copilot"], retries=0)


def test_validate_hook_rejects_soft_failure():
    """模型返回 200 但内容缺字段，也要算失败并参与重试。"""
    tries = {"n": 0}

    def runner(argv, prompt, timeout):
        tries["n"] += 1
        return cli_json(u'{"sections": []}' if tries["n"] == 1 else u'{"sections": [1]}')

    def validate(text):
        d = L.extract_json(text)
        return None if d.get("sections") else "sections 为空"

    out = L.call(u"x", runner=runner, backends=["qodercli"], retries=2, validate=validate)
    assert tries["n"] == 2 and "sections" in out


def test_parallel_returns_results_in_input_order():
    res = L.parallel([1, 2, 3, 4], lambda i: i * 10, workers=2)
    assert [r[1] for r in res] == [10, 20, 30, 40]


def test_parallel_captures_errors_per_item():
    def work(i):
        if i == 2:
            raise ValueError("bad item")
        return i
    res = L.parallel([1, 2, 3], work, workers=2)
    assert res[0][0] == "ok" and res[1][0] == "err" and res[2][0] == "ok"
    assert isinstance(res[1][1], ValueError)


def test_cli_runs_in_scratch_dir_not_project_root(monkeypatch, tmp_path):
    """qodercli 联网研究会把它抓到的网页写进 cwd。cwd 必须是 .research-scratch/，
    否则一轮批量生成就把项目根变成垃圾场（红线 H：不得向工作目录落盘无关文件）。"""
    import os
    seen = {}

    class Out(object):
        returncode = 0
        stdout = b'{"type":"result","result":"ok"}'
        stderr = b""

    def fake_run(argv, **kw):
        seen.update(kw)
        return Out()

    monkeypatch.setattr(L.subprocess, "run", fake_run)
    scratch = str(tmp_path / "scratch")
    monkeypatch.setattr(L, "SCRATCH", scratch)
    L._run(["x"], "prompt", 5)
    assert seen.get("cwd") == scratch, "CLI 仍在调用方 cwd 下运行：%s" % seen.get("cwd")
    assert os.path.isdir(scratch), "scratch 目录没有提前建好"


def test_a_research_file_dropped_in_the_repo_root_is_pulled_into_scratch(monkeypatch, tmp_path, capsys):
    """cwd 已经设成 scratch 了，但 CLI 找的是它自己眼里的「项目根」——
    从 cwd 往上走到有 .git 的那一层，于是抓到的网页还是落在仓库根。
    09-23 实测：AI 眼镜篇研究期间根目录多出一个 39KB 的 cdt.html（雷鸟 AR 眼镜文章），
    红线 R-08 正是这么漏掉的。跑完之后把新增的根目录文件搬进 scratch，
    并说搬了几个——不搬就是留着让下一次 git status 才发现。"""
    import os
    root = str(tmp_path / "repo")
    scratch = os.path.join(root, ".research-scratch")
    os.makedirs(scratch)
    os.makedirs(os.path.join(root, "scripts"))
    open(os.path.join(root, "AGENTS.md"), "w").write("x")   # 本来就有的文件不许动

    monkeypatch.setattr(L, "ROOT", root)
    monkeypatch.setattr(L, "SCRATCH", scratch)

    class Out(object):
        returncode = 0
        stdout = b'{"type":"result","result":"ok"}'
        stderr = b""

    def fake_run(argv, **kw):
        # 模拟 CLI 的真实行为：它不看我们给的 cwd，而看它自己找到的「项目根」，
        # 也就是 scratch 的上一层。
        open(os.path.join(root, "cdt.html"), "w").write("<html>雷鸟推出2款AR眼镜</html>")
        return Out()

    monkeypatch.setattr(L.subprocess, "run", fake_run)
    L._run(["x"], u"提示", 5)

    assert not os.path.exists(os.path.join(root, "cdt.html")), "研究文件还留在项目根"
    assert os.path.isfile(os.path.join(scratch, "escaped", "cdt.html"))
    assert os.path.isfile(os.path.join(root, "AGENTS.md")), "把原有文件也搬走了"
    assert u"cdt.html" in capsys.readouterr().out, "搬了却没说，等于悄悄改现场"


def test_run_surfaces_stderr_when_stdout_has_no_payload(monkeypatch, tmp_path):
    """两个后端都是 `--output-format json` 调起来的，所以 stdout 里连 `{` 都没有
        就是"根本没回答"，不是"回答得不好"。
    今天 copilot 三次只回一行横幅 `Color output disabled.`，退出码 0，
    上层于是报"响应里找不到合法 JSON：Color output disabled."——
    真因（stderr 里那句话）被整个丢掉，日志看着像模型的锅，其实是后端的锅。"""
    class Out(object):
        returncode = 0
        stdout = b"Color output disabled.\n"
        stderr = b"quota exceeded for this model"

    monkeypatch.setattr(L.subprocess, "run", lambda *a, **k: Out())
    monkeypatch.setattr(L, "SCRATCH", str(tmp_path / "scratch"))
    with pytest.raises(L.LlmError) as got:
        L._run(["copilot", "-p"], u"提示", 5)
    msg = str(got.value)
    assert "quota exceeded" in msg, u"没把 stderr 带进报错：%s" % msg
    assert "Color output disabled." in msg, u"没留下 stdout 的线索：%s" % msg


def test_run_still_raises_on_nonzero_exit_even_with_junk_stdout(monkeypatch, tmp_path):
    """退出码非 0 就是失败，不能因为 stdout 里"有点东西"就当响应。"""
    class Out(object):
        returncode = 3
        stdout = b"Color output disabled.\n"
        stderr = b"auth expired"

    monkeypatch.setattr(L.subprocess, "run", lambda *a, **k: Out())
    monkeypatch.setattr(L, "SCRATCH", str(tmp_path / "scratch"))
    with pytest.raises(L.LlmError) as got:
        L._run(["copilot", "-p"], u"提示", 5)
    assert "auth expired" in str(got.value)


def test_copilot_argv_is_machine_readable():
    """copilot 默认会把"Checking my documentation"之类的过程播报写进 stdout，
    兜底后端于是永远解析不到 JSON——等于没有兜底。"""
    argv = L.build_argv("copilot", True)
    assert "--silent" in argv, "copilot 未加 --silent，过程播报会混进结果：%s" % argv
    i = argv.index("--output-format")
    assert argv[i + 1] == "json", "copilot 未走 JSONL 输出：%s" % argv


def test_copilot_jsonl_result_is_parsed():
    line = '{"type":"result","result":"{\\"blocks\\":[{\\"type\\":\\"prose\\"}]}","stop_reason":"end_turn"}'
    noise = "● Checking my documentation\nColor output disabled for this response.\n"
    assert L.parse_cli_output((noise + line + "\n").encode("utf-8"))[0] == \
        '{"blocks":[{"type":"prose"}]}'


def test_rejected_response_is_dumped_for_postmortem(tmp_path, monkeypatch):
    """失败只留一行"blocks 为空"就没法查——模型到底返回了什么。
    最终失败时必须把原始响应落盘（红线 R-08：落在 scratch，不落在项目根）。"""
    monkeypatch.setenv("KE_REJECT_DIR", str(tmp_path))
    def runner(argv, prompt, timeout):
        return b'{"type":"result","result":"{\\"blocks\\":[]}"}'
    with pytest.raises(L.LlmError):
        L.call("p", online=False, timeout=5, retries=0, runner=runner,
               backends=["qodercli"], validate=lambda s: "blocks 为空")
    dumps = list((tmp_path).glob("*.txt"))
    assert dumps, "没有留下任何被拒响应的原始文本"
    body = dumps[0].read_text(encoding="utf-8")
    assert "blocks" in body and "blocks 为空" in body


def test_copilot_offline_flag_actually_exists():
    """--no-tools 不是 copilot 的旗标（它建议 --no-color），
    离线兜底调用直接以退出码 1 结束——等于兜底后端在离线路径上从来没通过。"""
    argv = L.build_argv("copilot", False)
    assert "--no-tools" not in argv
    assert "--available-tools" in argv, argv


def test_parse_picks_the_result_line_not_a_decoy():
    """copilot 的 JSONL 里每行都是独立事件，过程事件也可能含 "result" 字样。
    取"最后一条像 JSON 的行"会拿到状态事件，正文于是变成一坨元数据。"""
    lines = "\n".join([
        '{"type":"result","exitCode":0,"result":"{\\"ok\\":true}"}',
        '{"type":"session.mcp_server_status_changed","data":{"status":"pending",'
        '"note":"result 之后还会发这条"}}',
    ])
    assert L.parse_cli_output(lines.encode("utf-8"))[0] == '{"ok":true}'


COPILOT_FIXTURE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures", "copilot_real.jsonl")


def test_copilot_answer_is_taken_from_assistant_message():
    """copilot 的 {"type":"result"} 行只有 exitCode/usage，**没有正文**；
    真正的答案在 assistant.message 的 data.content 里。
    照 qodercli 的写法解析 copilot，会一路掉到"把整坨 JSONL 当正文返回"。"""
    raw = ('{"type":"session.start","data":{}}\n'
           '{"type":"assistant.message","data":{"content":"{\\"ok\\":true}"}}\n'
           '{"type":"result","exitCode":0,"usage":{"premiumRequests":1}}\n')
    text, meta = L.parse_cli_output(raw.encode("utf-8"))
    assert text == '{"ok":true}'
    assert meta.get("type") == "assistant.message"


@pytest.mark.skipif(not os.path.isfile(COPILOT_FIXTURE), reason="缺真实录制的 copilot JSONL")
def test_copilot_real_output_is_not_returned_as_raw_blob():
    """真实录制件：绝不能再把整段 JSONL 当正文返回（那会让 extract_json 抓到状态事件）。"""
    raw = io.open(COPILOT_FIXTURE, "rb").read()
    text, meta = L.parse_cli_output(raw)
    assert meta is not None and meta.get("type") == "assistant.message"
    assert not text.startswith('{"type":"session'), "返回的还是整坨 JSONL"
