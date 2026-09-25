# -*- coding: utf-8 -*-
"""领域大纲：加载、校验、把阅读时长换算成篇幅闸门。

大纲是唯一决定"一个领域该讲什么"的地方。新增领域＝加一个 config/topics/<领域>.json，
不该需要改这个文件；如果你发现自己在往这里加领域专有分支，那说明它该进配置。
"""
import json
import os
import re

try:
    from jsonschema import Draft202012Validator
except ImportError:  # pragma: no cover
    Draft202012Validator = None

_HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(_HERE)
CONFIG_DIR = os.path.join(ROOT, "config")
TOPICS_DIR = os.path.join(CONFIG_DIR, "topics")

BLOCK_TYPES = (
    "prose",
    "keyvalue_table",
    "timeline",
    "price_table",
    "card_grid",
    "steps",
    "quote",
    "fact_strip",
    "bar_chart",
    "compare",
    "note",
)


class OutlineError(Exception):
    """大纲不合法：定位信息写在消息里，供 CLI 直接展示。"""


class OutlineNotFound(OutlineError):
    """该领域没有大纲配置。消息必须是可执行的下一步，而不是一句"不存在"。"""


class Section(object):
    def __init__(self, raw, index):
        self.index = index
        self.id = raw["id"]
        self.title = raw["title"]
        self.anchor = raw.get("anchor") or raw["title"][:1]
        self.angle = raw.get("angle", "")
        self.block_types = list(raw["block_types"])
        self.image_queries = list(raw.get("image_queries", []))
        self.fact_prompts = list(raw.get("fact_prompts", []))
        self.min_words = raw.get("min_words")
        self.max_words = raw.get("max_words")

    def word_bounds(self, default_lo, default_hi):
        return (self.min_words or default_lo, self.max_words or default_hi)


class Outline(object):
    def __init__(self, raw, path):
        self._raw = raw
        self.path = path
        self.topic = raw["topic"]
        self.category = raw.get("category", "")
        self.tags = list(raw.get("tags", []))
        self.aliases = [str(a).strip() for a in raw.get("aliases", []) if str(a or "").strip()]
        self.subtitle = raw.get("subtitle", "")
        self.reader = raw.get("reader", "")
        self.theme = raw.get("theme", {}) or {}
        self.token = self.theme.get("token", "")
        self.hero_motif = self.theme.get("hero_motif", "")
        self.hero_note = self.theme.get("hero_note", "")
        # 人眼结论要能落成数据：这些来源页的图**永远不进产物**，
        # 也不参与逐章退回。见 images.page_excluded 与 W-120。
        self.image_exclude_pages = [str(u).strip() for u in raw.get("image_exclude_pages", [])
                                    if str(u or "").strip()]
        # 第二档「品牌单词」与补检索词用哪个名字。不声明就退到领域名拆出来的第一个词。
        self.image_primary_subject = str(raw.get("image_primary_subject", "") or "").strip()
        self.minutes = int(raw.get("reading_target_minutes", 10))
        self.sections = [Section(s, i) for i, s in enumerate(raw["sections"])]
        self._bar = _load_quality_bar()
        self.words_range = self._compute_words_range()

    # 领域产物目录：output/<领域>
    @property
    def output_dir(self):
        return os.path.join("output", self.topic)

    @property
    def outline_dir_name(self):
        return self.output_dir

    def page_name(self, date_str=None):
        """W-145：一页一名，名字里不带日期。

        参数留着（很多地方按 `page_name(today)` 调，也还要 `--date` 喂 `generated_date`），
        但**不再参与文件名**：日期名会让每篇的深层链接每天变一次，线上 URL 跟着失效。
        版本历史交给 git，不交给文件名。
        """
        return "%s.html" % self.topic

    def page_path(self, date_str=None):
        return os.path.join(self.output_dir, self.page_name(date_str))

    def section(self, sid):
        for s in self.sections:
            if s.id == sid:
                return s
        raise OutlineError(
            "%s：没有 id 为 %r 的章节；现有 %s"
            % (self.path, sid, ", ".join(s.id for s in self.sections))
        )

    def _compute_words_range(self):
        r = self._bar["reading"]
        per_min = r["assumed_chinese_chars_per_minute"]
        figs = r["figure_minutes_allowance"]
        base = _load_quality_bar()["words"]
        # 正文按 (目标分钟 - 图表耗时) 换算；上下限按比例缩放默认带宽，
        # 这样 20 分钟页不会只是把 10 分钟的字区间抄一遍。
        # --minutes / --fast 通过同一个环境变量进来，保证提示词与 G-05 用的是
        # 同一个换算口——两处各算一次就是本轮已经翻过车的那类矛盾。
        minutes = int(os.environ.get("KE_READING_MINUTES") or self.minutes)
        eff = max(1, minutes - figs)
        default_eff = max(1, r["target_minutes_default"] - figs)
        scale = float(eff) / default_eff
        return (int(base["min_chars"] * scale), int(base["max_chars"] * scale))

    def image_bounds(self):
        return self._bar["structure"]["min_images"], self._bar["structure"]["max_images"]


def _load_quality_bar():
    return json.load(open(os.path.join(CONFIG_DIR, "quality_bar.json"), encoding="utf-8"))


def _validate_against_schema(raw, path):
    schema = json.load(open(os.path.join(CONFIG_DIR, "topic_outline.schema.json"), encoding="utf-8"))
    if Draft202012Validator is None:  # pragma: no cover
        return
    v = Draft202012Validator(schema)
    errs = sorted(v.iter_errors(raw), key=lambda e: list(e.path))
    if not errs:
        return
    lines = []
    for e in errs[:8]:
        where = "/".join(str(p) for p in e.path) or "(根)"
        # 数组路径形如 sections/2/id，把它翻成"第 2 节"这类人话定位
        m = re.match(r"sections/(\d+)(?:/(.*))?", where)
        human = ("第 %s 节 %s" % (m.group(1), m.group(2) or "")) if m else where
        lines.append("  - %s：%s" % (human.strip(), e.message[:180]))
    raise OutlineError("%s 不符合 topic_outline.schema.json：\n%s" % (path, "\n".join(lines)))


def load(path):
    """从文件加载并校验一份大纲。"""
    if not os.path.isfile(path):
        raise OutlineNotFound(path)
    try:
        raw = json.load(open(path, encoding="utf-8"))
    except ValueError as e:
        raise OutlineError("%s 不是合法 JSON：%s" % (path, e))
    _validate_against_schema(raw, path)
    cfg = Outline(raw, path)
    _check_ids_unique(cfg, path)
    _check_block_types(cfg, path)
    return cfg


def load_for_topic(topic, root=None):
    base = root or ROOT
    path = os.path.join(base, "config", "topics", topic + ".json")
    if not os.path.isfile(path):
        raise OutlineNotFound(
            "没有领域 %r 的大纲。下一步二选一：\n"
            "  1) 新建 config/topics/%s.json（照抄一个现有大纲改章节即可）；\n"
            "  2) 运行 generate.py %s --draft-outline 让模型起草一份，"
            "然后人工确认再重新生成。\n"
            "已可用领域：%s"
            % (
                topic,
                topic,
                topic,
                ", ".join(available_topics(base)) or "（无）",
            )
        )
    return load(path)


def available_topics(root=None):
    base = root or ROOT
    d = os.path.join(base, "config", "topics")
    if not os.path.isdir(d):
        return []
    return sorted(os.path.splitext(f)[0] for f in os.listdir(d) if f.endswith(".json"))


def _check_ids_unique(cfg, path):
    seen = {}
    for s in cfg.sections:
        if s.id in seen:
            raise OutlineError(
                "%s：章节 id %r 重复（第 %d 节与第 %d 节）；id 必须唯一，"
                "否则 --only 与验收定位都会指错地方"
                % (path, s.id, seen[s.id], s.index)
            )
        seen[s.id] = s.index


def _check_block_types(cfg, path):
    for s in cfg.sections:
        for bt in s.block_types:
            if bt not in BLOCK_TYPES:
                raise OutlineError(
                    "%s：第 %d 节（%s）声明了未知区块类型 %r；可用类型：%s"
                    % (path, s.index, s.id, bt, ", ".join(BLOCK_TYPES))
                )
