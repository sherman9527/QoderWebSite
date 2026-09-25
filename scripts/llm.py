# -*- coding: utf-8 -*-
"""本地 CLI 生成器适配层：qodercli 优先，copilot 兜底（需求 5）。

两个实测踩出来的硬约束，别再改回去：
  1. 提示词走 stdin。`--allowed-tools` 这类可变参数旗标会把尾部位置参数吞掉。
  2. 判断"有没有真的联网查证"要看返回内容里是否出现 URL。
     --output-format json 的 usage.web_search_requests / token 计数在本机恒为 0，不可信。
"""
import io
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time

QODER = os.environ.get("QODERCLI", "qodercli")
COPILOT = os.environ.get("COPILOT_CLI", "copilot")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 无头 CLI 联网时把它抓到的网页写进自己的 cwd。给它一个专用沙箱目录，
# 否则一轮批量生成会往项目根扔几百个 html/pdf。
SCRATCH = os.environ.get("KE_SCRATCH") or os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".research-scratch")

URL_RE = re.compile(r"https?://[^\s\)\]\"'，。；]+")


class LlmError(Exception):
    pass


class LlmUnavailable(LlmError):
    pass


def _which(cmd):
    return shutil.which(cmd if isinstance(cmd, str) else cmd[0])


def available_backends():
    out = []
    if _which(QODER):
        out.append("qodercli")
    if _which(COPILOT):
        out.append("copilot")
    return out


def build_argv(backend, online):
    """组装命令行。注意不塞 prompt —— prompt 走 stdin。"""
    if backend == "qodercli":
        argv = [QODER, "-p", "--output-format", "json", "--no-session-persistence"]
        # 无头模式默认拿不到联网工具，模型会自己放弃查证；必须显式放权限。
        if online:
            argv += ["--permission-mode", "bypass_permissions", "--tools", "default"]
        else:
            argv += ["--tools", ""]
        return argv
    if backend == "copilot":
        # 默认 text 模式会把"● Checking my documentation"这类过程播报写进 stdout，
        # 兜底后端于是永远解析不到 JSON —— 等于没有兜底。
        argv = [COPILOT, "-p", "--no-color", "--silent", "--output-format", "json"]
        if not online:
            # 没有 --no-tools 这个旗标；清空可用工具才是它的等价写法。
            argv += ["--available-tools", ""]
        return argv
    raise LlmUnavailable("未知后端 %r" % backend)


_JSON_LINE = re.compile(r'^\{"type":.*"result".*\}\s*$', re.M)


def _decode(b):
    """qodercli 在 Windows 下按控制台代码页输出，优先按 UTF-8 试，失败再退 GBK。"""
    for enc in ("utf-8", "gbk", "cp936"):
        try:
            return b.decode(enc)
        except UnicodeDecodeError:
            continue
    return b.decode("utf-8", "ignore")


def parse_cli_output(raw):
    """从 CLI 输出里取正文。两个后端的形状完全不同，别混为一谈：

      - qodercli --output-format json：一行大 JSON，正文在 `result` 字段。
      - copilot --output-format json：JSONL 事件流。它的 `{"type":"result"}` 行
        只有 exitCode/usage，**没有正文**；正文在 `assistant.message` 的
        `data.content`。之前按 qodercli 的写法解 copilot，会一路掉到
        "把整坨 JSONL 当正文返回"，于是兜底后端等于没有。
    """
    text = _decode(raw) if isinstance(raw, bytes) else raw
    body = None
    meta = None
    for m in _JSON_LINE.finditer(text or ""):
        try:
            obj = json.loads(m.group(0))
        except ValueError:
            continue
        got = obj.get("result")
        if isinstance(got, str) and got.strip():
            body, meta = got, obj
    if body is not None:
        return body, meta
    for line in (text or "").splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            obj = json.loads(line)
        except ValueError:
            continue
        if obj.get("type") != "assistant.message":
            continue
        got = (obj.get("data") or {}).get("content")
        if isinstance(got, str) and got.strip():
            body, meta = got, obj
    if body is not None:
        return body, meta
    stripped = (text or "").strip()
    if stripped:
        return stripped, None
    raise LlmError("CLI 无输出")


_FENCE = re.compile(r"```(?:json)?\s*(.*?)```", re.S | re.I)


def extract_json(text):
    """三级容错：整段 → 代码围栏 → 首个平衡的 {...}/[...]。

    模型很爱在 JSON 前后裹一句解释，直接 json.loads 会白挂一半调用。
    """
    if text is None:
        raise LlmError("空响应")
    s = text.strip()
    try:
        return json.loads(s)
    except ValueError:
        pass
    for m in _FENCE.finditer(s):
        body = m.group(1).strip()
        try:
            return json.loads(body)
        except ValueError:
            continue
    for open_ch, close_ch in (("{", "}"), ("[", "]")):
        start = s.find(open_ch)
        while start >= 0:
            end = _match_balance(s, start, open_ch, close_ch)
            if end is not None:
                try:
                    return json.loads(s[start:end + 1])
                except ValueError:
                    pass
            start = s.find(open_ch, start + 1)
    raise LlmError("响应里找不到合法 JSON：%s" % s[:160])


def _match_balance(s, start, o, c):
    depth, in_str, esc = 0, False, False
    for i in range(start, len(s)):
        ch = s[i]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == o:
            depth += 1
        elif ch == c:
            depth -= 1
            if depth == 0:
                return i
    return None


def looks_grounded(text):
    """是否出现过 URL —— 真查证的证据。不看 CLI 的 self-reported 计数。"""
    return bool(URL_RE.search(text or ""))


def _dump_reject(backend, attempt, text, err):
    """被拒响应必须留下原文。只报一句"blocks 为空"根本没法查——
    是模型偷懒、还是提示词让它把 blocks 写在别的字段里，看得见的原文才知道。
    落在 scratch（红线 R-08），不落项目根。"""
    d = os.environ.get("KE_REJECT_DIR") or os.path.join(SCRATCH, "rejects")
    try:
        if not os.path.isdir(d):
            os.makedirs(d)
        p = os.path.join(d, "%s-%s-%d.txt" % (time.strftime("%H%M%S"), backend, attempt))
        with io.open(p, "w", encoding="utf-8") as fh:
            fh.write(u"# 后端 %s 第 %d 次\n# 拒因 %s\n\n%s\n" % (
                backend, attempt, err, text if text is not None else u"（无输出）"))
        return p
    except OSError:
        return None


def call(prompt, online=True, timeout=420, retries=1, backends=None, log=None,
         runner=None, validate=None):
    """调用本地 CLI 取回文本。retries 只补同一后端的偶发失败，然后才换后端。

    validate(text) 返回错误串则视为不合格、参与重试（用来挡"JSON 里少字段"这类软失败）。
    """
    log = log or (lambda *a: None)
    order = backends or available_backends() or ["qodercli"]
    last = None
    for backend in order:
        if not runner and not _which(build_argv(backend, online)[0]):
            log("  后端不可用，跳过：%s" % backend)
            continue
        for attempt in range(1, retries + 2):
            text = None
            try:
                raw = (runner or _run)(build_argv(backend, online), prompt, timeout)
                text, meta = parse_cli_output(raw)
                if validate:
                    err = validate(text)
                    if err:
                        raise LlmError("响应不合格：%s" % err)
                return text
            except Exception as e:
                last = e
                path = _dump_reject(backend, attempt, text, e)
                log("  %s 第 %d 次失败：%s%s" % (
                    backend, attempt, e,
                    u"（原文 %s）" % os.path.basename(path) if path else u""))
    raise LlmUnavailable("所有后端都失败（%s）：%s" % ("、".join(order), last))


def _root_files():
    try:
        return set(n for n in os.listdir(ROOT) if os.path.isfile(os.path.join(ROOT, n)))
    except OSError:
        return set()


def _sweep_root_extras(before):
    """把 CLI 落到仓库根的研究文件搬回 scratch——**cwd 设了也没用**。

    我们给 CLI 的 cwd 是 .research-scratch/，但它自己找的是「项目根」：
    从 cwd 往上走到有 .git 的那一层，也就是仓库根。于是红线 R-08 还是漏
    （09-23 实测：AI 眼镜篇研究期间根目录多出一个 39KB 的 cdt.html）。
    只搬**这次新增的文件**：目录、既有文件、别人的文件一律不碰。
    搬不动就跳过——并发下另一个 worker 可能已经搬走了，那正是我们想要的结果。
    """
    moved = []
    for name in sorted(_root_files() - before):
        try:
            dst_dir = os.path.join(SCRATCH, "escaped")
            if not os.path.isdir(dst_dir):
                os.makedirs(dst_dir)
            shutil.move(os.path.join(ROOT, name), os.path.join(dst_dir, name))
            moved.append(name)
        except OSError:
            continue
    if moved:
        print(u"  ! 研究文件落到项目根：%s（已搬进 .research-scratch/escaped/）"
              % u"、".join(moved[:4]))


def _run(argv, prompt, timeout):
    env = dict(os.environ)
    env.setdefault("PYTHONIOENCODING", "utf-8")
    if not os.path.isdir(SCRATCH):
        os.makedirs(SCRATCH)
    before = _root_files()
    try:
        p = subprocess.run(argv, input=prompt.encode("utf-8"), capture_output=True,
                           timeout=timeout, env=env, cwd=SCRATCH)
    finally:
        _sweep_root_extras(before)
    out = p.stdout or b""
    if p.returncode != 0:
        raise LlmError("%s 退出码 %d：%s" % (argv[0], p.returncode,
                                            _decode(p.stderr)[:200]))
    if b"{" not in out:
        # 两个后端都是 --output-format json 调起来的：stdout 连 { 都没有，
        # 就是"根本没回答"。以前这里会把一行横幅当响应返回，上层于是报
        # "响应里找不到合法 JSON：Color output disabled."，把 stderr 里的真因整个丢掉。
        raise LlmError("%s 没返回 JSON（stdout %d 字节：%s）stderr：%s" % (
            argv[0], len(out),
            _decode(out)[:60].replace("\n", " ").strip() or u"空",
            _decode(p.stderr)[:200].replace("\n", " ").strip() or u"空"))
    return out


class Budget(object):
    """限制并发模型调用数——单次联网要 2–5 分钟，不控台数会一次挂几十个进程。"""

    def __init__(self, n):
        self._sem = threading.Semaphore(max(1, int(n)))

    def __enter__(self):
        self._sem.acquire()
        return self

    def __exit__(self, *a):
        self._sem.release()


def parallel(items, work, workers=3, log=None):
    """对 items 并发执行 work(item)，返回与输入等长的结果列表（异常就地捕获）。"""
    log = log or (lambda *a: None)
    results = [None] * len(items)
    budget = Budget(workers)

    def run(i, it):
        with budget:
            try:
                results[i] = ("ok", work(it))
            except Exception as e:
                results[i] = ("err", e)
                log("  任务 %d 失败：%s" % (i + 1, e))

    threads = [threading.Thread(target=run, args=(i, it)) for i, it in enumerate(items)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    return results
