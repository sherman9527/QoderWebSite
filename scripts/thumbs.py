# -*- coding: utf-8 -*-
"""主页卡片封面的缩略图。W-185。

为什么需要它：`.probe/measure_cards.mjs` 在 375 / 1440 / 2560 三档量过，
卡片框只有 **316–343 CSS px** 宽（它不随视口长大，是固定列数的卡片网格），
而 hosted 主页内联的是原文那张 **1472–2400 px** 的图 —— 29 张卡里 26 张超出
2 倍屏预算，主页因此 9.9 MB。这不是"能打开就行"的问题：主页是读者点进来的第一屏。

三条设计决定：

1. **缓存键是源文件的内容哈希，不是路径。** 按路径缓存的话，换封面之后主页会
   继续显示旧图——而旧图看起来完全正常，没有任何一处会报错。
   这一条写在 `tests/test_thumbs.py` 里钉死。
2. **只往下缩，绝不放大。** 源图比目标窄就原样返回：放大不省一个字节，
   只会让卡片上的图发虚。
3. **Pillow 缺位不是错误，是降级**——返回 None 让调用方退到原图，
   但调用方**必须喊一声**。静默退回 9.9 MB 和没做这件事没区别。

为什么不把缩略图写进 `output/<篇>/images/`：那里是文章包的内容，多一个文件
`own_sha` 就变，13 个站会全部变成"待重发"。缩略图是**主页这一份产物的派生物**，
所以住在 `dist/.thumbs/`——`prepare_site` 拿的是 `dist/<组>/`，永远不会带上它。
"""
import hashlib
import io
import os

DEFAULT_CACHE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                             "dist", ".thumbs")
QUALITY = 82


def _sha16(path):
    h = hashlib.sha256()
    with io.open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()[:16]


def thumb_for(src, width, cache=None):
    """返回一张宽度 ≤ `width` 的本地文件路径；做不出来（没装 Pillow、图打不开）返回 None。

    源图本来就比 `width` 窄时**原样返回那个路径**，不生成文件。
    """
    cache = cache or DEFAULT_CACHE
    try:
        from PIL import Image
    except Exception:
        return None
    try:
        im = Image.open(src)
        im.load()
    except Exception:
        return None
    if im.width <= width:
        return src
    has_alpha = (im.mode in ("RGBA", "LA") or
                 (im.mode == "P" and "transparency" in im.info))
    ext = "png" if has_alpha else "jpg"
    key = u"%s_w%d.%s" % (_sha16(src), width, ext)
    out = os.path.join(cache, key[:2], key)      # 分片：一个目录几万个文件会拖慢
    if os.path.isfile(out) and os.path.getsize(out) > 0:
        return out
    ratio = float(width) / float(im.width)
    size = (width, max(1, int(round(im.height * ratio))))
    resized = im.resize(size, Image.LANCZOS)
    if not has_alpha:
        resized = resized.convert("RGB")
    try:
        os.makedirs(os.path.dirname(out), exist_ok=True)
        tmp = out + ".part"
        resized.save(tmp, "PNG" if has_alpha else "JPEG", quality=QUALITY,
                     optimize=True)
        os.replace(tmp, out)                     # 原子：半成品会被下一次当成真的读走
    except Exception:
        return None
    return out
