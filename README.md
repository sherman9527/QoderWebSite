# KnowEverything —— 一条命令生成一个知识专题页

`python scripts/generate.py 咖啡` → 一个**自包含的纯静态 HTML**（图文并茂、约 10 分钟读完、`file://` 双击可开、断网能看），外加一张汇总全部专题的索引主页。每个领域一套视觉，不是同一模板换字。

> 面向 agent 的冷启动顺序在 [`AGENTS.md`](AGENTS.md)；这份 README 面向**人**：怎么跑起来、产物长什么样、为什么这么设计。
> 原始需求见 [`requirement.txt`](requirement.txt)（只读，9 条场景 + 8 条工程要求）。

---

## 1. 现在有什么

20 篇已上架，全站质量闸门 `0 fail`（G-05 正文偏长的 warn 按 D-11/D-18 容忍）：

| 类别 | 篇 |
|---|---|
| 人工智能 | 大模型、Muse、Muse产业逻辑、AI眼镜、骁龙笔电、AI制药、大模型与加密货币 |
| 腕表 | 劳力士、百达翡丽、积家、浪琴 |
| 箱包时装 | 香奈儿、爱马仕、LV |
| 汽车 | 宾利、劳斯莱斯 |
| 电子元件 | MLCC |
| 香水美妆 | 娇兰 |
| 饮食风物 | 咖啡 |
| 消费零售 | 名创优品与泡泡玛特 |

怎么把页面分享出去（本地文件 / 局域网 / 托管成公开 URL）：见 [`docs/sharing.md`](docs/sharing.md)。**当前状态：20 篇各自一个站、全部已发布且公开可达**，还有一个把它们连起来的主页站 <https://knoweverything-gtqdc11h6po.qoder.website/>，逐篇地址在 [`web_list.md`](web_list.md)。那个文件是派生物——权威源是各篇 `output/<领域>/data.json` 的 `site` 字段，别手改，改完 `python scripts/publish.py ledger` 重生成。实测上限是**单包 50 MiB**（最大的一篇 LV 29.78 MB 通过）；中文图片名不是问题（曾疑过，实验证伪）。

**要发布或接手发布：[`docs/publishing-for-agents.md`](docs/publishing-for-agents.md) 是给 agent 的完整手册**——先 `python scripts/publish.py playbook` 向脚本要带参数的清单（含每篇该往哪个 projectId 更新），不要凭记忆拼参数。脚本负责出包与记账，托管那几步只有 agent 能调。

### 这个仓库怎么公开出去

`scripts/publish_public.py` 生成**一条干净的单提交快照**再推：

```bash
python scripts/publish_public.py                 # 只构造 + 自查，不推
PUBLIC_GIT_NAME=... PUBLIC_GIT_EMAIL=... \
  python scripts/publish_public.py --push https://github.com/<owner>/<repo>.git
```

它**不碰本地历史**（用临时 index 造 tree），并且推之前自己验三件事：
没有 `output/` 下的第三方图片、没有 `.pending` / `manifest.json` 这类现场文件、
没有本机用户名与绝对路径。**排除清单在 `config/public_exclude.txt`**，是要给人审的，
不是藏在代码里的正则。

两条刻意的取舍：① 远端只有一条提交，本地 124 条历史不外传（作者身份与旧版
`memo.md` 里的本机路径都在历史里）；② `output/*/images/` 那 344 张抓来的图不进公开仓库
（版权与体积），克隆后跑 `generate.py` 自行取图；`tests/golden/**` 的 13 张是测试夹具，留着，
否则 clone 之后 `pytest` 跑不起来。

看效果：

```bash
python scripts/open.py output/index.html      # 走系统默认浏览器，不写死可执行文件
```

---

## 2. 快速开始

### 前置

| 依赖 | 版本 | 说明 |
|---|---|---|
| Python | 3.10+ | 流水线与闸门 |
| Node.js | 26（18+ 应可） | 跑 SSR 渲染与截图 |
| `qodercli` | v1.13.1 | **正文与 HTML 的生成器**，需已 login；`copilot` v1.0.84 是兜底 |
| Edge 或 Chrome | 任意近期版本 | G-13 要真开浏览器量几何 |

### 装依赖（国内镜像优先，这是红线 R-07）

```bash
pip install -r requirements.txt          # 清华源为主、阿里为备，已写进文件
cd web && npm install && cd ..           # .npmrc 已指向 registry.npmmirror.com
```

### 生成一个领域

```bash
python scripts/generate.py 咖啡                          # 全流程（联网 + 抓图，单次约 40–60 分钟）
python scripts/generate.py 咖啡 --offline                # 只重跑渲染+校验，不花模型额度
python scripts/generate.py 咖啡 --fast                   # 4 分钟档 + 每章最多 2 条来源
python scripts/generate.py 咖啡 --minutes 20 --sources-per-section 8
python scripts/generate.py 咖啡 --only timeline          # 只重做某一章
python scripts/generate.py 咖啡 --redo-images            # 只重做配图（正文不动）
```

### 校验与体检

```bash
python scripts/validate.py --all         # 14 条质量闸门，唯一裁判
python scripts/audit_images.py           # 配图语义体检（跑题只有这道看得见）
python scripts/contact_sheet.py 咖啡     # 一篇的配图拼成带标签联络表，给人眼看的
pytest -q                                # 回归套件（332 项，fixtures 打桩，不碰真模型）
```

---

## 3. 流水线五个阶段

```
config/topics/<领域>.json
        │
   1 outline   读大纲；缺失则让模型起草并**停下等人工确认**（不自动往下跑）
   2 research  逐节两趟：research pass 联网取料（产 fact + source）→ write pass 凭料成文
               并发默认 4；单节失败只重试该节
   3 images    逐节 image_queries → 三档检索 → 校验落盘 → images/ + manifest.json
   4 render    scripts/render.mjs 用 React SSR 把 data.json 灌进黄金模板 → <领域>_<日期>.html
               同时 build_index.py 重建 output/index.html
   5 verify    validate.py 闸门。不过就 exit 1，且**不更新索引**——坏页面不会悄悄挂上入口
```

产物：`output/<领域>/<领域>.html`（一篇只有一页，名字不带日期）+ `output/<领域>/images/` + `data.json`（中间数据，也是重渲染的输入）。

**非破坏式不变量**：任何被已发布页面引用的文件都不许删、不许覆盖、不许挪。W-145 之后它不再靠"旧日期页还留在盘上"实现，而是靠**暂存 + 原子换名**：渲染写到 `<领域>.html.pending`（扩展名故意不是 `.html`，所以索引、候选表、孤儿判定全看不见它）→ 对 pending 跑闸门 → 把当前那份复制成 `.html.prev` 再 `os.replace` 换名 → 重建索引 → 索引成功才删 `.prev` 与 `images.prev/`。换名之前任何一步失败，线上那份和它那套图原封不动。配图重做另有一层：`--redo-images` 之前先把旧图备份进 `images.prev/`，逐章比较哪章变少就退回那章的旧图。

---

## 4. 黄金模板长什么样

### React 是唯一实现，产物是静态的

需求 7 要 React、场景 1 要纯静态，看似冲突。解法：**组件树既跑在 dev 工作台（人眼验收），又被 `render.mjs` 用 `renderToStaticMarkup()` 打成一份自包含 HTML**——CSS 内联进 `<head>`、图片走相对路径、零外部请求、零运行时 JS。

这样"工作台看到的"和"产物"是同一份代码，视觉回归只有一个被测对象。反面方案（Python/Jinja 手写模板 + React 做预览台）会让排版维护在两处，必然漂移。

### 正文是**带类型的区块**，不是一坨 markdown

`web/src/template/blocks.ts` 的 11 类区块，与 `config/topic_data.schema.json` 的枚举**必须完全一致**（契约测试钉住，改一处忘改另一处立刻红）：

```
prose | keyvalue_table | timeline | price_table | card_grid | steps
quote | fact_strip | bar_chart | compare | note
```

模板渲染的是**结构**，闸门才能按类型查一致性——比如 `price_table` 每一行必须有 `source`、`timeline` 条目不许只有一个字。

### 一页一套主题 token，共享骨架不共享配色

`web/src/tokens/index.ts` 现有 15 套，每套给 `primary / accent / soft / display 字体 / hero motif`：

| token | 主色 | 强调色 | 记忆点 |
|---|---|---|---|
| coffee-roast | `#4A2C17` 烘焙棕 | `#1E6B52` | roast_axis 烘焙度色带 |
| chanel-noir | `#0B0B0C` 黑白 | `#B8A15A` 米金 | chain_and_camellia |
| hermes-orange | `#E1610F` 爱马仕橙 | `#7C4A23` 鞍皮棕 | saddle_stitch |
| patek-calatrava | `#C6A15B` 金 | `#6FA88C` 深绿 | calatrava_cross |
| jaeger-reverso | `#1F3A5F` 钢蓝 | `#4B7FA6` | reverso_flip 翻转矩形 |
| rolex-oyster | `#0F6B3D` 皇冠绿 | `#A9B0B6` 钢灰 | crown_and_bezel |
| lv-monogram | `#6E5A38` | `#C08A4E` | monogram_tile |
| longines-winged | `#4A5A6A` | `#C8102E` 沙漏红 | winged_hourglass |
| bentley-racing | `#0B3B24` 赛翠 | `#7E1F2C` 皮革酒红 | matrix_grille |
| rolls-argenteal | `#C7CDD6` 银灰 | `#7C8CB0` | starlight_headliner |
| guerlain-abeille | `#4B2A5B` 蜂紫 | `#C9A227` 蜜金 | bee_comb_axis 蜂巢 |
| llm-attention | `#B5177E` 品红 | `#2A9D8F` | attention_matrix |
| muse-sandbox | `#0A6E6E` | `#FF8A00` | sandbox_rack 机架灯阵 |
| muse-industry | `#502B3A` 酒红 | `#A8D60C` 电光黄绿 | stack_layers 五层横条 |
| glasses-waveguide | `#1466C8` | `#6B2CF5` | waveguide_rainbow |

配色不是审美自由：**G-11 断言任意两领域的主色与强调色在 CIE76 下都不得同时 ΔE<25**（孪生色板），否则 15 页会悄悄长成一张脸。这条闸门自己也被注入过错值自证有效。

### 每页只有一处"记得住的东西"

hero motif（见上表最后一列）在页头出现一次，其余保持安静。视觉语言走"反 AI 默认"清单：**不用**奶油底 + 衬线大字 + 陶土橙、近黑底 + 单一荧光色、报纸细线密排、千篇一律圆角卡片同层阴影、每标题上方 ALL-CAPS 小标签、`A · B · C` 元信息串、链接尾追加 `→`。

### 封面：声明优先，其次才是"最宽的一张"

`data.json` 可以写 `cover`；模板 `coverOf()` 与索引 `build_index.cover_of()` 用同一套规则（不一致会导致点进去换一张图）。**默认那条"取最宽"天然偏爱排行榜截图与宣传横幅**——它们像素宽度最大，索引卡片上被 `object-fit:cover` 裁掉半截字；LV 甚至挑中过一张 16 MB 的秀场照，慢解码时整张卡片是白的。所以每个领域上架前都要人看一眼封面并声明。

### 索引主页

一条连续 feed（不是按类别切成多个小网格——切了之后单篇类别会预留 6 条轨道，2560px 下用掉 356px 空 1869px，看着就是"不自适应"）。类别改成卡片上的 chip + 顶部锚点。

卡片带**创建时间**角标，顶部可**按创建时间排序（最新在前 / 最早在前）**。两点实现值得知道：

- 创建时间 = 该领域**最早那篇日期页**的日期，不是 `generated_date`——后者每次 `--offline` 重渲染都变成今天，用它排序等于"谁最近被重做过谁排最前"。文件名里的日期不会漂移，也不需要新字段。
- 排序是**纯 CSS**（DOM 按创建时间升序，卡片带 `--asc/--desc` 两个序号，`:has(#sort-old:checked)` 换 `order`）。产物零运行时 JS 是一条性质，有测试钉着；浏览器不支持 `:has()` 时退化成"最新在前"，只是切换失效。

### 自包含

CSS 内联、不引 CDN、不引外部字体（本地栈 `PingFang SC / Microsoft YaHei / Noto Serif SC`）、图片相对路径。断网双击可开。这是 R-01，由 G-04 逐条扫 `<script src>` / `<link href>` / `@import` / `url()`。

---

## 5. 内容从哪来，为什么不编

- 正文与事实由本地 CLI 生成（`qodercli` 优先、`copilot` 兜底），**无头模式必须 `--permission-mode bypass_permissions` 才拿得到联网工具**。
- 两趟取料：research pass 联网产 `fact + source`，write pass 凭料成文不联网。分开是因为让模型"边写边查"会写成散文再倒推来源。
- **反幻觉契约**：所有数字型断言（价格/年份/产量/排名）必须挂在带 `source{label,url}` 的字段上；价格必须带 `as_of` 时点。无来源的数字 → G-06 直接失败，按 R-02 干脆不写。
- 档位可参数化：`--minutes N` 同时改每章字数预算与 G-05 判据（走同一个环境变量，不可能一半新一半旧）；`--sources-per-section K` 是单次耗时的主开关（实测每章抓约 12 个网页）。

---

## 6. 配图是怎么来的（这里踩坑最多）

图片源只有 `cn.bing.com/images/async` 可达（Wikimedia / DuckDuckGo / Baidu 图搜在本网络不可用），解析内嵌 JSON 拿 `murl` 原图、`turl` 缩略图兜底。**不能只看 HTTP 状态码判成败**——Bing 缩略图会返回 404 而字节是合法 JPEG，所以必须校验 magic bytes + 尺寸 + 体积。

### 三档阶梯，顺序不可换

```
1 章节检索词 + 必须点名领域
2 品牌词 / 章内两词短语 + 必须点名领域
3 放弃点名要求（仍有关键词命中下限）
```

理由：**空着比脏好，但品牌图比脏图好**。第 3 档历史上捞回过"中国行政区划""圆糯米""重型工作台""中华万年历 app 下载"——闸门全绿的页面上挂着这些，因为"这张图配不配这一章"在结构上量不出来。

### 主语闸门

候选图片的标题/图注/来源页必须**点名领域本身**。推导规则：领域名 → 大纲声明的 `aliases` → 在 ≥3 章检索词里露过面的拉丁词。短 ASCII 缩写（`lv`）按整词匹配，否则 `involve/resolve` 全算点名；而完全不认 `lv` 又会把"LV Monogram 手袋"这种真图全判跑题——LV 篇 22 张因此重做成 1 张、10 章空掉。

### 词形比品牌重要（实测三次）

Bing CN 会把短/歧义中文品牌名切词切进词典与地理内容：`积家 手表` → 0 点名，`积家手表` → 35/35；`娇兰 香水` → 0，`Guerlain Shalimar` → 33/35；`沪电股份` → "浦江"、`澜起科技` → "王者荣耀"。所以大纲里的检索词是**量出来的形态**，不是随手写的中文词。

### 品牌词档挑哪个词，由大纲自己回答

`primary_subject` 原本只看形状挑"第一个够长的词"，于是必然挑中领域名。两篇 Muse 的 22 条检索词**一条都没写过裸 `muse`**——而 `muse` 在中文图搜里是英国摇滚乐队和一家同名手术机器人，它们的标题确实带着 muse，点名闸门放行。现在：**领域名在本篇检索词里零覆盖时**，换成覆盖率最高的那个词（人写检索词就是在赌"这个物体在图里会出现"，这是免费的信号）。15 篇里只有 2 篇因此改变，13 篇行为不变。同一档内部还先问**这一章自己的两词短语**——实测裸词档的跑题率是章节原词的 3 倍。

### 人眼结论要能落成数据

联络表抓到的错图（同名公司会议照、品牌字标面板、优惠入口广告卡）没有机器判据——按词否决实测要赔 27 张好图。所以大纲有 `image_exclude_pages`：**按来源页 URL 前缀排除**，排在配额与下载之前，逐章退回那条路径也拦。没有这个声明位的话，`--redo-images` 会把人手工摘掉的图原样抓回来（真发生过）。

### 召回会突然跳水

同一句检索词，实测两次分别返回 5 条和 35 条；并发（生成 + 探针）会让召回塌到 1–2 条并抛 `ConnectionResetError 10054`。所以：

- `python scripts/bing_health.py --topic <领域> --wait-healthy` —— **用这篇自己的检索词**判"现在能不能跑图"，参照组只作诊断，不参与放行。
- `--redo-images` 之前先备份到 `images.prev/`，结束时逐章比较，**哪一章变少了就退回那一章的旧图**。判据只有"变少了没有"，没有"召回健康线"——别给噪声定指标。

### 第四种图：自己画的示意图

有些章实拍根本答不上来——MLCC 的工艺链、叠层剖面、板级供电位置，`mlcc 产线`、`贴片电容 工厂` 全部 0 点名。这类章以前只有两个结局：堆一张无关厂房照骗读者，或者空章被 G-03 拦下不上架。

现在多了第三条：`kind: illustration`。契约上它与引用图**互斥**——schema 用 `if/then` 规定示意图必须带 `based_on`（追责到正文哪几条事实）且**禁止带 `source_page`**，所以它不可能冒充"有出处的图"；反过来照片必须带 `source_page`。渲染时页面打「示意图 · 非实拍」角标，索引页与封面自动规则跳过它（否则"取最宽的一张"会选中一张线条图）。

入口只有一个：`python scripts/add_illustration.py <领域> <章节> --from <png> --alt … --based-on …`，它同时写文件、`data.json`、`manifest.json` 三处——少写一处就分别以破链、被重当没抓过、孤儿图三种方式坏掉。图上**刻意不写任何数字**：层数、电压、容值、良率都是可核查的量化断言，必须走带来源的结构化区块，烧进图片就绕过了 R-02。

`--redo-images` 不会抹掉示意图（采集器只会找回照片，清引用等于把手画图交给孤儿清理）。

### 上架前的最后一道是人

`validate --all` 全绿 **不是**能上架的充分条件。配图有变动的领域必须跑 `contact_sheet.py` 出一张带标签联络表**用眼睛过一遍**。这条不是仪式感：闸门全绿的页面上出现过常柴柴油机、木工坊、永乐大钟、西铁城机芯、Meta 字标、1688 钢板网广告。

---

## 7. 质量闸门：14 条，一个裁判

`scripts/validate.py` 是唯一裁判（D-05）——CI、pre-commit、本地手动都调它，避免规则两处漂移。

| | 判什么 | 为什么存在 |
|---|---|---|
| G-01 | 产物命名与位置 | `output/<领域>/<领域>.html`，且**同目录不许出现第二页**——"只留最新版"靠闸门守，不靠约定 |
| G-02 | 章节覆盖率 | 大纲声明的每节都必须存在且非空 |
| G-03 | 图片 | 引用存在、有 alt、无孤儿、每章至少一张、数量达标 |
| G-04 | 自包含 | 零外部网络资源（R-01） |
| G-05 | 篇幅 | 正文汉字数落在目标区间（R-05，软上限 warn） |
| G-06 | 来源 | 数字必须有 `source.url`，价格必须有 `as_of`（R-02） |
| G-07 | 占位符 | 不许残留 `TODO`/`{{`/`待补充`/`Lorem` |
| G-08 | 模板指纹 | 产物必须由**当前**模板渲染，防手改产物 HTML |
| G-09 | 红线 | `rule.md` 每条生效红线还得挂着有效检测器 |
| G-10 | schema | `data.json` 与大纲各自过 JSON Schema |
| G-11 | 跨领域配色 | 任意两领域主/强调色不得同时 ΔE<25（global） |
| G-12 | 索引主页 | 封面真实存在、链接可达、类别非空（global） |
| G-13 | 布局几何 | **真开浏览器**量七档视口：溢出、破版、对比度 AA（R-09） |
| G-14 | 发布账实相符 | `web_list.md` 必须等于由各篇 `data.json.site` 重算出来的那份；还没有任何发布时保持沉默 |

G-13 存在的原因：pytest 全绿过两次，开发者一眼看出"自适应不对"——量几何这件事在字符串层面看不见。它必须指定内核，`scripts/browser.mjs` 探到 Edge 就用 `msedge`。

---

## 8. 红线与流程

9 条生效红线在 [`rule.md`](rule.md)。**红线只能由开发者移除或放宽**，agent 不得删。

开发流程固定八步（详见 `AGENTS.md` §2）：取 TODO → 移 IN PROGRESS → **先写失败测试并亲眼看到它红** → 最小实现转绿 → `pytest -q` → 改过模板就全站重渲染 → `validate --all` → 把命令与真实输出写进 `memo.md` → 工作项进 COMPLETE 带**可点开的证据指针**（"done" 不算证据）。

四份治理文档各管一件事：

| 文件 | 管什么 |
|---|---|
| `rule.md` | 不许做什么 |
| `HANDOVER.md` | 还剩什么要做（TODO / IN PROGRESS / COMPLETE，一条只在一处） |
| `memo.md` | 环境事实、决策记录、踩坑、测试日志——重新发现一次要几十分钟的东西 |
| `AGENTS.md` | 新会话 5 分钟冷启动 |

---

## 9. 已知边界与代价

- **Bing CN 的召回不稳**是外部事实，不是能修的 bug。对策是等窗口 + 逐章回滚，不是给噪声定阈值。
- **闸门绿 ≠ 能上架**：配图相关性只到人眼为止（§6 末）。
- **产物体积**：W-145 之后每篇盘上只剩一页（稳定名 `<领域>.html`），36 个历史日期页已 `git rm`——版本历史交给 git，不交给文件名。当前 `output/` 是 19 页 + 索引 + 353 张图 ≈ 167 MB，全部进 git。真要瘦身是 git 历史重写，破坏性且需单独授权（D-19 决定不动）。
- **正文普遍偏长**：目标 4500–6500 字，实际 6500–7300 字，走 warn 不 fail（D-11 开发者定调"容忍超长、保持高质量默认"）。
- **价格与政策会过期**：每篇页尾声明时效，`data_as_of` 标到月。
- **单次生成成本**：一个 11 章的领域，正文约 50 分钟、配图 15–40 分钟（取决于窗口）。

---

## 10. 目录

```
config/topics/<领域>.json     领域大纲（人可改；新增领域 = 加一个 JSON，不改代码）
config/*.schema.json          两份契约：大纲、内容
web/                          React 工作台 = 黄金模板真身
  src/template/               TopicPage / IndexPage / blocks / renderers / styles
  src/tokens/                 每领域一套主题 + 布局常量（清单以本文件为准，文档不抄数字）
  src/workbench/              本地预览台（vite dev）
scripts/
  generate.py                 主入口（五阶段）
  outline.py  llm.py  images.py  render.mjs  build_index.py  validate.py
  audit_images.py  contact_sheet.py  bing_health.py  recover_images.py
  shot.mjs  measure-layout.mjs  browser.mjs  open.py  sweep_tokens.py  prune_scratch.py
tests/                        pytest 回归（fixtures 打桩，不碰真模型）
output/<领域>/                产物：唯一一页 <领域>.html + images/ + data.json
openspec/                     规格驱动的 change 计划
docs/superpowers/specs/       架构设计与取舍
rule.md  HANDOVER.md  memo.md  AGENTS.md   红线 / 台账 / 记忆 / 冷启动
```
