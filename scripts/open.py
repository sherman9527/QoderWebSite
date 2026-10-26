# -*- coding: utf-8 -*-
"""用**系统默认浏览器**打开产物（开发者的默认浏览器是 Edge）。

为什么不写死 msedge：`os.startfile` 走的是 Windows 的文件关联，
用户哪天改默认浏览器，这条命令跟着变，不需要改代码。
度量类脚本（G-13 / shot.mjs）不一样，它们要指定内核，见 scripts/browser.mjs。
"""
import os
import subprocess
import sys

# Windows 上 stdout 默认按 ANSI 码页（这台机器是 GBK）编码，而本仓库的输出里全是
# 中文与 ⇒/≠/· 这类非 GBK 字符。少这道守卫不是显示难看，是**直接崩**：
# 10-26 就是 validate.py 打印一条 G-15 告警里的 ⇒ 时抛 UnicodeEncodeError，
# 把 9 篇渲染打成 rc=1 —— 看着像质量闸门拦的，其实是编码。守卫本身由
# tests/test_contract.py 那条"会 print 的脚本必须钉住输出编码"守住。
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def open_in_default_browser(path):
    p = os.path.abspath(path)
    if not os.path.isfile(p):
        raise SystemExit(u"文件不存在：%s" % p)
    if sys.platform.startswith("win"):
        os.startfile(p)  # noqa: S606 - 走系统关联，正是"默认浏览器"的语义
    elif sys.platform == "darwin":
        subprocess.run(["open", p], check=True)
    else:
        subprocess.run(["xdg-open", p], check=True)
    return p


def main(argv=None):
    args = argv if argv is not None else sys.argv[1:]
    if not args:
        print(__doc__)
        return 2
    for a in args:
        print(u"已用默认浏览器打开 %s" % open_in_default_browser(a))
    return 0


if __name__ == "__main__":
    sys.exit(main())
