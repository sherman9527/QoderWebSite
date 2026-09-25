# -*- coding: utf-8 -*-
"""用**系统默认浏览器**打开产物（开发者的默认浏览器是 Edge）。

为什么不写死 msedge：`os.startfile` 走的是 Windows 的文件关联，
用户哪天改默认浏览器，这条命令跟着变，不需要改代码。
度量类脚本（G-13 / shot.mjs）不一样，它们要指定内核，见 scripts/browser.mjs。
"""
import os
import subprocess
import sys

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
