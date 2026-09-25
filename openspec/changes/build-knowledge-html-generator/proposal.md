# Proposal

## Why

`requirement.txt` 要的是"一条命令产出一个能离线打开、图文并茂、约 10 分钟读完、排版优雅的知识科普 HTML 页"，而且首批就要 10 个领域、后续还要用脚本继续加新领域。手工做 10 页不可扩展，随意让模型写一篇既会编造价格年份、又会 10 页长成一个样。所以要把"生成"和"验收"两头都变成可重复、可机检的管线。

## What Changes

- 新增 `scripts/generate.py <领域>` 五阶段流水线：outline → research → images → render → verify。
- 新增黄金模板：React 组件树是模板**唯一实现**，经 `renderToStaticMarkup()` SSR 产出**自包含静态 HTML**（CSS 内联、零外链、`file://` 双击可开）。同时满足需求 7"前端使用 react"与场景 1"纯静态 html"。
- 新增领域配置契约 `config/topics/<领域>.json`：新增领域＝加一个 JSON，不改代码（需求 6 的持续生成能力）。
- 新增主题 token 体系：10 个领域各一套配色/字形/motif，共享版式骨架但不共享视觉，避免模板化破绽。
- 新增图片管线：`cn.bing.com/images/async` 搜索 + 字节校验 + `murl`→`turl` 兜底 + 每领域独立 `images/` 目录 + manifest 记录源页（需求 场景 2）。
- 新增内容落地契约：research pass 联网取料 → write pass 成文；所有数字型断言必须带可点开来源 URL，无来源即生成失败。
- 新增 `scripts/validate.py` 作为**唯一质量裁判**（十条闸门），CI／本地／pre-commit 共用同一份。
- 新增 `tests/` 回归套件（单元/集成/契约/视觉/全站五层）与固定 TDD 八步流程（需求 4）。
- 新增生成器 CLI 适配层：`qodercli` 优先、`copilot` 兜底（需求 5）。
- 新增治理三件套：`memo.md`（记忆，需求 3）、`rule.md`（红线，默认无红线，需求 6）、`HANDOVER.md` + 项目版 `handover` skill（工作项台账，需求 5）。
- 产出首批 10 个领域专题页：咖啡、香奈儿、爱马仕、百达翡丽、积家、劳力士、LV、浪琴、宾利、劳斯莱斯。

## Capabilities

### New Capabilities

- `knowledge-page-generation`: 单命令五阶段流水线的对外行为——入参（领域名、`--offline`、`--only`）、产物文件名 `<领域>_YYYY-MM-DD.html`、失败与重试语义、退出码。
- `topic-outline-config`: 领域大纲配置的 schema 与解析行为；"新增领域零代码"这一约束由它保证。
- `golden-template`: 模板渲染行为——React 单一真身、SSR 静态化、自包含约束、每领域主题 token、跨主题视觉差异要求、区块类型集合。
- `image-sourcing`: 图片检索/校验/落盘/清单行为，含本网络环境下的源可用性约束与"不得只看 HTTP 状态码"。
- `content-grounding`: 内容生成的取证行为——两趟生成、数字断言必须绑来源、来源缺失的处置方式。
- `quality-gates`: 质量闸门与防 regression 行为——十条可执行断言、字数区间、覆盖率、唯一裁判原则、TDD 流程要求。
- `project-governance`: 跨会话记忆、红线检查、工作项台账三项流程行为（含"改动前必须检查红线"）。

### Modified Capabilities

（无——本仓库尚无既有 spec，全部为新建。）

## Impact

- **新增代码**：`scripts/`（Python + 一个 Node SSR 脚本）、`web/`（Vite + React + TS）、`tests/`、`config/`。
- **新增产物目录**：`output/<领域>/`（HTML + `images/` + `data.json` + manifest）。
- **依赖**：npm 侧 `react`、`react-dom`、`vite`、`typescript`；pip 侧 `pytest`（图片解析走标准库，不引入重依赖）。全部按需求 7/8 走国内镜像优先：npm→`registry.npmmirror.com`（已配并实测 6s 装包成功）、pip→清华源（已配）。
- **外部工具**：`qodercli` v1.13.1（已登录，无头联网需 `--permission-mode bypass_permissions`）、`copilot` v1.0.84（已登录，兜底）。
- **网络前提**：Wikimedia / DuckDuckGo / Baidu 图搜在本环境不可达，方案不得依赖。
- **不影响**：`requirement.txt`（只读原始需求）、参考项目 `<用户目录>\Desktop\ADEMO\oreilly`（只读参考）。
- **风险登记**：见 `docs/superpowers/specs/2026-09-19-knowledge-html-generator-design.md` §11。
