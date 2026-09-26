# AGENTS.md — 冷启动指引

给**新会话的 Agent** 或**新接手的人**：按下面顺序读，5 分钟内可以续跑，不需要问。

## 0. 这个项目是什么

一条命令 `python scripts/generate.py <领域>` 产出**一个纯静态 HTML 知识专题页**（图文并茂、约 10 分钟读完、每个领域视觉不同）。首批 10 个领域：咖啡、香奈儿、爱马仕、百达翡丽、积家、劳力士、LV、浪琴、宾利、劳斯莱斯；09-20 起陆续加了娇兰、大模型、AI 眼镜、Muse，09-24 加了 Muse产业逻辑、MLCC 与 骁龙笔电，09-25 加了 AI制药、名创优品与泡泡玛特 与 大模型与加密货币，09-26 加了 ClaudeOpus55 与 美国中期选举与全球资产，**现在 22 篇全部上架**（每篇一个独立站点，地址记在 `web_list.md`，主页 <https://knoweverything-gtqdc11h6po.qoder.website/>）。原始需求见 `requirement.txt`。

## 1. 阅读顺序（有依赖，别跳）

| 顺序 | 文件 | 为什么先读它 |
|---|---|---|
| 0 | `README.md` | 面向**人**的全景：怎么跑起来、黄金模板长什么样、配图三档、14 条闸门各判什么。想知道"为什么这么设计"先看它 |
| 1 | `rule.md` | **做任何 change 之前必须先看**。9 条红线已生效（R-01…R-09，开发者 09-19 授权裁决，见 `memo.md` D-08）；红线只能由开发者移除或放宽，agent 不得删 |
| 2 | `HANDOVER.md` | 唯一的工作项台账：TODO / IN PROGRESS / COMPLETE |
| 3 | `memo.md` | 环境事实与踩坑（网络可达性、CLI 权限怪癖、遥测字段骗人）——这些重新发现一次要几十分钟 |
| 4 | `docs/superpowers/specs/2026-09-19-knowledge-html-generator-design.md` | 架构设计与方案取舍（为什么 React 出静态页）。**写于 09-19，部分数字已旧**（10 领域 / 10 条闸门），以 `README.md` 与代码为准 |
| 5 | `openspec/changes/` | 规格驱动的开发计划与 tasks |

## 2. 干活流程（不可颠倒）

1. `HANDOVER.md` 取一条 TODO → 移到 IN PROGRESS（这是并行互斥标记）。
2. **先写失败测试**，并**亲眼看到它红**。
3. 写最小实现让它绿。
4. `pytest -q` 全绿（确认没打破别的）。
5. **改过模板（区块枚举 / token / 样式）就必须重渲染全部产物**：
   `for t in $(ls config/topics | sed 's/.json//'); do python scripts/generate.py "$t" --offline; done`。
   模板指纹一变，G-08 就把所有旧产物判陈；而索引现在会跳过闸门未过的领域，
   于是**只改模板不重渲染，入口页会从 9 篇掉到 2 篇**（2026-09-22 实测踩过）。
   `--offline` 不重跑研究、不花模型额度，只 render + verify。
  W-145 之后重渲染**不再产生新的日期页**：渲染到 `<领域>.html.pending`，
  闸门全绿才原子换名，所以失败的重渲染动不了已发布那一份（版本历史交给 git）。
6. `python scripts/validate.py --all` 全绿（质量闸门，唯一裁判）。
   **但闸门绿不是"能上架"的充分条件**：配图有变动的领域还要跑
   `python scripts/contact_sheet.py <领域>` 出一张带标签联络表**用眼睛过一遍**。
   这条不是仪式感——闸门全绿的页面上出现过常柴柴油机、陈志远木工坊、永乐大钟、
   西铁城机芯（D-17 / W-99 / W-115 各一次），而"这张图配不配得上这一章"
   在结构上无法用关键词或尺寸量出来。封面同理：默认规则"取最宽的一张"
   会选中排行榜截图与宣传横幅（W-119），要声明 `data.cover`。
7. 把命令 + 真实输出摘要写进 `memo.md` 测试日志。不许写"应该没问题"。
8. 工作项从 TODO 删除、追加进 COMPLETE，带**可点开的证据指针**（文件路径 / 测试名 / 命令），"done" 不算证据。
9. 冒出新需求 → TODO 加一条；砍掉功能 → 删该项并在 `memo.md` 决策记录写为什么砍。
10. **要把文章发成公开站点**：照 [`docs/publishing-for-agents.md`](docs/publishing-for-agents.md) 走。第一步永远是 `python scripts/publish.py playbook`——它算出每篇的 `projectId` 与逐步参数。发布是**半自动**的：`pack` / `record` / `check` 是脚本，`prepare_site` → `publish_site` → `update_access_policy` 只有 agent 能调。三条不能省的判断：`published: true` 且 `active_release_id` 非空才算发出去；**发布 ≠ 可见**（新站默认 private）；最后必须 `curl` 到 200。

`.qoder/skills/handover/` 把第 1、8、9 步变成可触发的流程。

## 3. 已定架构（一句话版）

React 是黄金模板的**唯一实现**；`scripts/render.mjs` 用 SSR 把它打成**自包含静态 HTML**（CSS 内联、图片相对路径、零外链、`file://` 双击可开）。需求 7 要 React、场景 1 要纯静态，靠这个决策同时满足。

流水线五阶段：`outline → research → images → render → verify`。

## 4. 环境硬约束（本机实测，别再试错）

- **npm 用 npmmirror，pip 用清华源**（需求 7/8）。已配好，见 `memo.md`。
- **GitHub 直连卡死** → 用 `https://gh-proxy.com/https://github.com/...` 浅克隆。
- **Wikimedia / DuckDuckGo / Baidu 图搜在本网络不可用**。图片走 `cn.bing.com/images/async`（`murl` 原图优先，`turl` 缩略图兜底）。
- **不能只看 HTTP 状态码判断下载成功** —— Bing 缩略图会返回 404 但字节是合法 JPEG。必须校验 magic bytes + 尺寸 + 体积。
- **Bing CN 的召回会突然跳水**：同一句检索词，实测两次分别返回 5 条和 35 条。
  所以 `--redo-images` / `--only` 在清空之前先把本轮要掉的章节备份到 `output/<领域>/images.prev/`
  （已 gitignore，是中间态不是产物），配图阶段结束时**逐章比较，哪一章变少了就退回那一章的旧图**。
  判据只有"变少了没有"，没有"召回健康线"——别去加那种阈值，那是给噪声定指标。
- **生成 HTML 用本地 CLI**：`qodercli`（优先，v1.13.1）→ `copilot`（兜底，v1.0.84）。提示词走 stdin，别当位置参数传（`--allowed-tools` 会吞掉它）。
- **`qodercli` 无头联网必须加 `--permission-mode bypass_permissions`**，否则模型直接放弃查证。
- **`--output-format json` 的 `web_search_requests` / token 计数恒为 0，不可信**：判断有没有真联网，看答案里是否出现具体 URL 与数字。
- 终端打中文乱码是 Git Bash 控制台编码问题，**不代表文件坏了**。写文件统一 `encoding="utf-8"`。
- **`pytest.ini` 的 `addopts` 已经带了 `-q`，再敲 `pytest -q` 等于 `-qq`，会把"N passed"那行整个吞掉**——
  只剩点号，量不到测试数。要报数就 `python -m pytest`（不加 `-q`）。今天因为读不到这行而编过一个测试数。
- **同理，任何判绿都不要接管道**：`pytest -q | tail -8` 的退出码是 `tail` 的，
  真实 rc 会被洗成 0。统一 `> 文件 2>&1` 再 `echo rc=$?`。

## 5. 目录约定

```
README.md                     面向人的全景：怎么跑、黄金模板、配图三档、14 条闸门各判什么
config/topics/<领域>.json     领域大纲（人可改；新增领域=加一个 JSON，不改代码）
web/                          React 工作台 = 黄金模板真身
  src/template/               区块组件（11 类 block）
  src/tokens/                 设计 token，每领域一套
scripts/generate.py           主入口
scripts/validate.py           质量闸门（唯一裁判）
tests/                        pytest 回归（fixtures 打桩，不碰真模型）
output/<领域>/<领域>.html + output/<领域>/images/   # 一篇只有一页，名字不带日期（W-145）
openspec/                     规格与 change 计划
docs/superpowers/specs/       架构设计文档
rule.md / HANDOVER.md / memo.md   红线 / 台账 / 记忆
```

## 6. 常用命令

```bash
python scripts/generate.py 咖啡                  # 全流程生成一个领域
python scripts/generate.py 咖啡 --offline        # 只重跑 render+verify（省模型额度）
python scripts/generate.py 咖啡 --fast            # 快档：目标 4 分钟 + 每章最多 2 条来源
python scripts/generate.py 咖啡 --minutes 20 --sources-per-section 8   # 自定义档位
python scripts/generate.py 咖啡 --only timeline  # 只重做某一节
python scripts/validate.py --all                 # 全站质量闸门（14 条，唯一裁判）
python scripts/publish.py playbook            # 待发布清单（含每篇的 projectId 与逐步参数）
python scripts/publish.py pack 咖啡            # 出包到 dist/<slug>/，超 50 MiB 直接拒
python scripts/publish.py record 咖啡 <url> --project-id <pid> --access public
python scripts/publish.py check                # 账实核对（G-14 用的就是这个）
python scripts/audit_images.py                   # 配图语义体检（闸门量形式，跑题只有这道看得见）
python scripts/audit_images.py --fix             # 只重做体检不合格的领域，跑完自动复查
python scripts/contact_sheet.py 咖啡             # 一篇的配图拼成带标签联络表（.probe/sheet_*.png）
python scripts/open.py output/咖啡/咖啡.html       # 用系统默认浏览器（Edge）打开产物
node scripts/shot.mjs <产物.html> --widths 375,1440,3762   # 五档截图 + 实测几何，自查用
python scripts/sweep_tokens.py                # 每套主题 × 有/无封面全部过 G-13（主题清单从 tokens/index.ts 读，不在脚本里抄死）
python scripts/prune_scratch.py               # 研究报告中间文件；默认 dry-run，删要 --apply
pytest -q                                        # 回归套件
/opsx:propose "<要改什么>"                        # OpenSpec 提变更计划
```

**给人看页面一律走 `scripts/open.py`**（系统文件关联，不写死浏览器可执行文件）。
**量几何的脚本（G-13 / shot.mjs）必须指定内核**，且优先开发者那颗：
`scripts/browser.mjs` 会探测到 Edge 就用 `msedge`，没有才退 `chrome`。

### 档位（2026-09-19 起可参数化）
默认 = **高质量**：不限制每章来源数，字数按大纲的 `reading_target_minutes` 换算。
`--minutes N` 同时改变每章字数预算与 G-05 判据（走同一个环境变量，不可能一半新一半旧）；
`--sources-per-section K` 是单次耗时的主开关（实测每章抓 ~12 个网页，K 直接砍这个）；
`--fast` = `--minutes 4 --sources-per-section 2`。快档代价：引用变少，
按红线 R-02 查不到来源的数字会直接不写。

## 7. 待开发者决定 / 已定

- 2026-09-19 已定：候选红线 A–I → **9 条全部生效**（`rule.md` 第一节）；**`git init` 已做**，
  pre-commit 跑 pytest（正本 `scripts/git-hooks/pre-commit`，换机要 `cp` 进 `.git/hooks/`）；
  批量生成**接受后台跑数小时**。
- 仍待确认：正文 4,500–6,500 汉字的"10 分钟"换算是否符合你的阅读预期（见 `memo.md` D-02）。
