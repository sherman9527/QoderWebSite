# 知识科普 HTML 生成器 · 架构设计

日期：2026-09-19 ｜ 状态：**已实现并跑通 15 篇**（原为"待评审"） ｜ 来源需求：`requirement.txt`

> **这是一份有日期的设计文档，不是现状说明书。** 里面的取舍（为什么 React 出静态页、为什么 validate 是唯一裁判、为什么两趟取料）至今成立，也仍然是排查"当初为什么这么定"的第一手材料。
> 但**数字与闸门清单已经旧了**，现状以 [`README.md`](../../../README.md) 与代码为准。差异列在下面，正文不回改——把设计文档改成"永远正确"，它就失去了作为时间戳的价值。

## 0. 与 2026-09-24 现状的差异

| 本文说的 | 现在 | 记在哪 |
|---|---|---|
| 首批 10 个领域 | **15 篇**：加了娇兰、大模型、AI 眼镜、Muse、Muse产业逻辑 | `HANDOVER.md` COMPLETE |
| 10 类区块 | **11 类**（漏了 `bar_chart`） | `web/src/template/blocks.ts` |
| 闸门 10 条 | **13 条 G-01…G-13**：新增 G-11 跨领域配色不得雷同、G-12 索引主页、G-13 真开浏览器量几何 | `scripts/validate.py`；G-13 的存在理由见 `memo.md`（pytest 全绿而开发者一眼看出自适应不对，两次） |
| R4 风险"10 页视觉雷同"→ 断言主色板差异 | 落成了 G-11，且判据是 CIE76 ΔE、**主色与强调色同时** <25 才算孪生 | `memo.md` D-03、W-88（这条闸门一度写成永远全灭，修它的过程比写它更值得读） |
| R6 风险"`git` 未初始化" | 已初始化，pre-commit 跑 pytest | `memo.md` D-10 |
| §7 只说"一页一主题 token" | 加了：**封面必须人声明**（默认"取最宽的一张"会挑中排行榜截图、宣传横幅与 16 MB 巨图）；索引页可按创建时间排序，纯 CSS 无运行时 JS | `memo.md` D-20、W-119、W-128 |
| §6 流水线五阶段 | 骨架没变，但配图阶段长出了一整套机制：**三档阶梯 + 主语闸门 + 词形实测 + 来源页排除表 + 品牌词按覆盖率自动选 + 召回健康闸门 + 逐章回滚快照** | `README.md` §6、`memo.md` D-14/D-17/D-19/D-21 |
| §8 "validate 全绿即完成" | **被证伪过一次**：闸门全绿的页面上挂着常柴柴油机、木工坊、永乐大钟、西铁城机芯、Meta 字标、1688 钢板网广告。现在多一步人眼验收：配图有变动的领域必须看 `contact_sheet.py` 的联络表 | `AGENTS.md` §2 第 6 步、`memo.md` D-19/W-116 |
| §5 反幻觉契约 | 生效，并扩成红线 R-02/R-03；另加"查不到来源的数字干脆不写" | `rule.md` |

## 1. 目标

一条命令 `python scripts/generate.py <领域>` 产出**一个可离线打开的纯静态 HTML 知识专题页**，图文并茂、约 10 分钟读完、排版优雅且每个领域视觉各不相同。首批 10 个领域：咖啡、香奈儿、爱马仕、百达翡丽、积家、劳力士、LV、浪琴、宾利、劳斯莱斯。

## 2. Spike 已验证事实（不靠猜）

| 结论 | 证据 |
|---|---|
| `qodercli` 可无头生成 | `qodercli -p --tools "" "1+1=?"` → `1+1=2`，v1.13.1 已登录可用 |
| 无头模式**默认拿不到联网工具** | 同一条腕表公价问题，模型回答"你可以允许我使用 WebSearch/WebFetch"，没有去查证 |
| 联网可用 `--permission-mode bypass_permissions` 解锁 | 该模式下问 Daytona 126500 国内公价，返回 `约 13.55 万元` + 一条真实可点开的 `k.sina.com.cn` 文章链接——是查证得来的而非记忆里的泛泛之谈 |
| ⚠️ 但 `usage.server_tool_use.web_search_requests` 恒报 0 | 该遥测字段在此模型通道下不可信：**判断有没有真联网，要看答案里是否出现具体 URL/数字，不能看这个计数器** |
| 图片源只有国内可达的 Bing | `cn.bing.com/images/async?q=…` 200，解析 `m="…"` 内嵌 JSON 得 `murl/turl/purl`；实测下载 12–35 条结果，`murl` 原图成功、部分 404 由 `turl` 兜底 |
| Wikimedia / DuckDuckGo 本网络不可达 | `commons.wikimedia.org` 连接超时、`duckduckgo.com` 21s 超时 |
| 依赖镜像可用 | npm 切 `registry.npmmirror.com` 后 `@fission-ai/openspec` 6s 装完；pip 已配清华源 + 阿里备用 |
| Baidu 图搜反爬 | `image.baidu.com/search/acjson` → `{"antiFlag":1,"message":"Forbid spider access"}` |

## 3. 核心张力与决策：React 还是纯静态？

需求 7 要"前端使用 react"，场景 1 要"纯静态 html"。三个方案：

- **A. 手写 HTML 黄金模板 + Python 占位符渲染，React 只做个预览台** —— 最省事，但模板真身住在 Python/Jinja 里，React 是装饰品；同一份排版要维护两处，改样式必然漂移。
- **B. React 是模板的唯一实现，产物用 SSR 静态化** —— `web/` 里的组件树既跑在 dev 工作台（人眼验收），又被 `render.mjs` 用 `renderToStaticMarkup()` 打成一份自包含 HTML：CSS 内联、图片相对路径、零外部请求，双击 `file://` 即开。
- **C. 每页一个 React SPA** —— 直接违反"纯静态"，排除。

**选 B。** 只有它同时诚实地满足两条需求，并且让视觉回归有单一被测对象：工作台截图 = 产物渲染结果。代价是流水线里多一个 Node 构建步骤，可接受。

## 4. 目录结构

```
KnowEverything/
├── requirement.txt          原始需求（只读）
├── AGENTS.md                新会话/新人入手指引：先读什么、按什么顺序动手
├── memo.md                  记忆机制：开发 + 测试结果持续追加
├── rule.md                  红线：默认无红线；任何改动前必须检查
├── HANDOVER.md              交接台账：TODO 工作项 / COMPLETE 工作项
├── openspec/                规格驱动：changes/* 是开发计划，specs/* 是已生效规格
├── docs/superpowers/specs/  本设计文档
├── config/
│   ├── topics/<领域>.json    领域大纲：章节 + 检索词 + 图片查询 + 主题 token
│   ├── topic_outline.schema.json
│   └── topic_data.schema.json
├── web/                     React 工作台（Vite + TS）＝黄金模板真身
│   └── src/
│       ├── template/        TopicPage 及其区块组件
│       ├── tokens/          设计 token：每个领域一套
│       └── workbench/       预览台（数据驱动的本地 dev app）
├── scripts/
│   ├── generate.py          主入口：outline → research → images → render → verify
│   ├── llm.py               qodercli 优先、copilot 兜底，统一重试/超时/JSON 解析
│   ├── images.py            Bing 图搜 + 校验 + 落盘 + manifest
│   ├── render.mjs           Node SSR：组件树 → 自包含静态 HTML
│   └── validate.py          质量闸门（唯一裁判，CI 与本地同一份）
├── tests/                   pytest 回归套件
│   ├── fixtures/            假数据 + 假 LLM 响应（不打真实模型，保证快且可重放）
│   └── golden/              模板快照
└── output/<领域>/<领域>_YYYY-MM-DD.html ＋ output/<领域>/images/*
```

## 5. 数据契约

**`config/topics/<领域>.json`（大纲，人可改）**：`topic`、`theme`（palette/type/motif token）、`reading_target_minutes`、`sections[]`，每节含 `id/title/angle/block_types/image_queries[]/fact_prompts[]`。新增领域＝加一个 JSON，不改代码。

**`output/<领域>/data.json`（内容，机器生成）**：符合 `topic_data.schema.json`。每个 section 的正文是**带类型的 block 列表**，不是 markdown 大块：

```
prose | keyvalue_table | timeline | price_table | card_grid | steps | quote | fact_strip | compare | note
```

区块类型让模板渲染"结构"而非"一坨文字"，也让 validate 能按类型查一致性（如 `price_table` 每行必须有 `source`）。

**反幻觉契约**：所有数字型断言（价格/年份/产量/尺寸/排名）必须挂在带 `source{label,url}` 的字段上。无来源的数字 → validator 直接失败。这是把 oreilly 参考页里"不编数字、标注来源与样本量"的纪律固化成机器闸门。

## 6. 生成流水线

```
generate.py <领域>
 1 outline   读 config/topics/<领域>.json；缺失则让 LLM 起草一份并要求人工确认（不自动往下跑）
 2 research  逐节调用 LLM（8–12 次）→ data.json 的分节内容
             两趟：research pass（联网取料，产 fact + source）→ write pass（凭料成文，不联网）
             每节 900–1400 字；单节失败只重试该节
 3 images    逐节 image_queries → images.py → output/<领域>/images/NN_slug.jpg + manifest.json
             校验：magic bytes 真图 / 宽≥640 / 体积≥40KB / 去重 / 记源页 purl
 4 render    render.mjs 用 SSR 把 data.json 灌进 React 模板 → <领域>_<日期>.html（自包含）
 5 verify    validate.py 质量闸门（见 §8），不过就 exit 1，绝不"生成了就算完"
```

`--offline` 复用已有 data.json 与图片只重跑 4–5，改样式时不必再花模型额度；`--only <section>` 局部重做。

## 7. 黄金模板设计语言

参考 oreilly 页的**信息装置**（编号锚点、评分条、结论框、适合/不适合对照、页脚来源链），但按 `frontend-design` 的"反 AI 默认"清单重做视觉，因为整站 10 页雷同就是模板化破绽：

- **一页一主题 token**：咖啡走烘焙棕 + 萃取金；香奈儿走黑白 + 米色山茶；百达翡丽走深绿 + 金；劳力士走皇冠绿 + 钢灰；宾利/劳斯莱斯走皮革酒红 / 银灰。10 页共享**版式骨架**与**信息装置**，不共享**配色与字形**。
- **主动避开**：奶油底 `#F4F1EA` + 衬线大字 + 陶土橙点缀（AI 味最重的一族）；近黑底 + 单一荧光色；报纸细线密排；千篇一律圆角卡片 + 同一层阴影；每标题上方 ALL-CAPS 小标签；`A · B · C` 元信息串；小字号一律等宽体；链接尾追加 `→`。
- **每页只有一处"记得住的东西"**（hero motif），其余保持安静克制：例如咖啡用一条烘焙度×年份的萃取色带开场，钟表用机芯擒纵结构线稿开场，箱包用配货比例图开场。
- **结构编号只在真是序列时使用**（历史时间线、冲煮步骤），非序列内容不套 `01/02/03`。
- **动效**：只在页面加载做一次编排式揭示，不做逐卡片淡入上移；尊重 `prefers-reduced-motion`。
- **质量地板**：移动端不破版、键盘焦点可见、正文行长 <80 字（衬线略放宽 + 更大行高）、对比度达标、`<img>` 全有 `alt` 且注明图源。
- 自包含：CSS 内联进 `<head>`，不引 CDN、不引外部字体（用 `PingFang SC / Microsoft YaHei / Noto Serif SC` 本地栈），断网可看。

## 8. 防 Regression 机制与 TDD 流程（需求 4）

**测试金字塔**

| 层 | 内容 | 是否打真实模型 |
|---|---|---|
| 单元 | schema 校验、大纲解析、区块渲染快照、LLM JSON 解析容错、Bing 响应解析（录制的 fixture） | 否 |
| 集成 | 假 LLM（fixture 回放）跑完整 1→5，断言产物落盘且 validate 通过 | 否 |
| 契约 | 真跑 1 个领域（咖啡）打通端到端，产物入 `tests/golden/` 作基线 | 是 |
| 视觉 | Playwright 打开工作台与产物截图对比；断言"无外部网络请求" | 否 |
| 全站闸门 | `validate.py` 扫 `output/**` 全部页面 | 否 |

**`validate.py` 是唯一的裁判**，CI 与 pre-commit 与本地手动都调它，避免规则两处漂移。闸门清单：

1. 文件名 = `<领域>_YYYY-MM-DD.html`，且落在 `output/<领域>/` 下
2. 章节覆盖 = 大纲声明的 `sections` 全部存在且非空（咖啡必须含历史/品牌/产地/大赛/特调/价格/烘焙/机器）
3. 全部 `<img src>` 指向本目录 `images/` 真实存在的文件；`images/` 里无未被引用的孤儿文件；每个 `<img>` 有 `alt`
4. HTML 自包含：无 `http(s)://` 形式的 `<script src>` / `<link href>` / `@import` / `url()` 外链资源
5. 字数落在 10 分钟目标带内（4,500–6,500 正文汉字，假设 500 字/分钟 + 图表约 2 分钟；越界即 fail 而非 warn）
6. 每个数字型断言有 `source.url`；来源域名不得是内容农场黑名单
7. 无占位符残留（`TODO`、`{{`、`…`、`待补充`、`Lorem`）
8. 模板指纹一致：产物的 token 段必须来自 `web/src/tokens/`（防止有人绕过模板手改产物 HTML）
9. `rule.md` 生效红线逐条转成可执行断言（默认无红线时该组为空，加红线即加断言）
10. 大纲 JSON 通过 `topic_outline.schema.json`；`data.json` 通过 `topic_data.schema.json`

**TDD 开始流程（每个工作项固定八步）**

1. `HANDOVER.md` 取一条 TODO → 移到 IN PROGRESS（防止并行重复劳动）
2. 先写失败测试：validator 新断言 / 组件快照 / 解析器 fixture。**先跑一遍确认它真的红了**
3. 写最小实现让该测试转绿
4. 跑 `pytest -q` 全量，确认没有别的测试被打破
5. 跑 `python scripts/validate.py --all`，确认全站闸门仍绿
6. 只有 5 绿了，才把结果写进 `memo.md`（命令 + 实际输出摘要 + 结论），不许写"应该没问题"
7. `openspec` 对应 change 的 tasks 勾掉；工作项从 IN PROGRESS 移进 `HANDOVER.md` 的 COMPLETE，并从 TODO 删除
8. 若过程中冒出新需求 → 在 TODO 新增一条；若砍掉功能 → 删除对应工作项并在 `memo.md` 记为什么砍

红→绿→全站闸门→记账，顺序不许颠倒。改动前先看 `rule.md`。

## 9. 记忆机制（需求 3）

`memo.md` 追加式，不回改历史。四节：**当前状态快照**（可续跑的最小上下文）、**决策记录**（决定 + 为什么 + 否决的备选，防止下次有人重走弯路）、**踩坑与已验证事实**（网络可达性、CLI 权限怪癖这类环境知识最贵）、**测试日志**（命令 + 输出摘要）。新会话冷启动顺序：`AGENTS.md → rule.md → HANDOVER.md → memo.md`。

## 10. 交接机制（需求 5）

`HANDOVER.md` 三段：`TODO`、`IN PROGRESS`、`COMPLETE`。规则：一条工作项只在一处存在——完成即从 TODO **删除**并追加到 COMPLETE（带日期与证据指针）；新需求进 TODO；砍功能则删项并留一句原因。项目内 `.qoder/skills/handover/` 提供同名 skill，把这套台账维护动作变成可被触发的流程，而不是靠人自觉。

## 11. 风险与未决

| ID | 风险 | 应对 |
|---|---|---|
| R1 | ~~qodercli 无头联网能否解锁~~ **已解**：`--permission-mode bypass_permissions` 可联网 | 采用两趟取料（research pass 联网 → write pass 成文）；联网失败/超时则退化为区间表述并在页尾声明"未经联网查证" |
| R2 | 奢侈品/腕表价格随年份漂移 | 每个价格标"截至 YYYY-MM 公价"并绑来源；页尾统一声明时效 |
| R3 | Bing 图搜结果版权与相关性不稳 | 每图记录 `purl` 源页并显示在图注；建立黑名单域名过滤；优先商品/场景实拍而非插画；失败图不进产物 |
| R4 | 10 页视觉雷同 | 主题 token 是硬要求：validator 断言相邻两页主色板差异 > 阈值 |
| R5 | 单次生成成本 | 分节生成 + `--offline` 复跑 + `--only` 局部重做 |
| R6 | `git` 未初始化（当前目录非仓库） | 建议 `git init` 才能获得快照/回滚与 pre-commit 闸门；是否初始化由使用者决定 |

## 12. 里程碑

- **M0 地基**：治理文档 + 镜像源 + skill 装配 + pytest 骨架（本设计通过后第一件事）
- **M1 模板**：React 黄金模板 + 咖啡主题 token + 工作台预览 + 快照测试
- **M2 流水线**：`generate.py` 五阶段 + `llm.py`（qodercli→copilot 兜底）+ `images.py` + validator 全闸门
- **M3 咖啡打样**：首个领域端到端跑通 + 真浏览器验收 + 基线入 `tests/golden/`
- **M4 批产**：其余 9 个领域 + 每领域主题 token + 全站 validate 绿灯
- **M5 可扩展**：新领域＝加一个 `config/topics/*.json`，验证需求 6"后续用脚本继续生成新的知识点"
