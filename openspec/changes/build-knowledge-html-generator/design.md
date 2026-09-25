# Design

## Context

架构层取舍见 `docs/superpowers/specs/2026-09-19-knowledge-html-generator-design.md`（尤其是 D-01 React 与纯静态的 A/B/C 方案比较）与 `memo.md` 决策记录。本文只记录**实现层**决策。行为要求见本 change 的 `specs/`。

当前状态：仓库无任何代码，只有治理文档与配置脚手架；`output/` 不存在；依赖镜像已配好并实测有效。

实现必须绕开三个已实测的环境硬事实：
- 联网图源只有 `cn.bing.com/images/async` 可用，Wikimedia/DuckDuckGo/Baidu 均不可用。
- `qodercli` 无头模式必须带 `--permission-mode bypass_permissions` 才会真的查证；且 `--output-format json` 的 token/搜索计数恒为 0，不可用于判断。
- 单次联网调用 2–5 分钟，因此"一次调用生成整页"在 10 个领域的批量下不可接受。

## Goals / Non-Goals

**Goals:**
- 模板真身唯一：React 组件树既服务工作台也服务静态化。
- 生成与验收解耦：产物是数据 + 模板的纯函数结果，任何人可用 `--offline` 复现同一页面。
- 闸门规则集中：一条闸门 = 一个函数 = 一个 `G-NN` 编号，被 spec 场景与测试双向引用。
- 新增领域的边际成本 ≈ 写一个大纲 JSON + 一套主题 token。

**Non-Goals:**
- 不做服务端、不做数据库、不做在线部署（纯本地静态产物）。
- 不做 PDF/EPUB 导出。
- 不做多语言版本（先只做 zh-CN）。
- 不追求模型输出一次到位；靠分节重试 + 闸门兜底。

## Decisions

### D-A `llm.py` 适配器契约：prompt 走 stdin，成功判据看内容而非计数

`generate(prompt, *, schema_hint, expect_json, online, timeout, retries)` 内部：
- 命令行固定为 `qodercli -p --permission-mode bypass_permissions --output-format json`，**prompt 用 stdin 传入**。原因：`--allowed-tools` 这类可变参数旗标会把尾部位置参数吞掉（实测踩坑），stdin 无此歧义。
- 判定"是否真的联网查证过"用**返回内容里是否出现 http(s) URL**，不看 `usage.server_tool_use.web_search_requests`（实测恒 0）。
- JSON 解析走"剥代码围栏 → 取首个平衡 `{}` → schema 校验 → 失败则带错误信息重试一次"三级容错，因为模型常在 JSON 外裹一句解释。
- 兜底顺序 `qodercli → copilot`，两者都失败则该章节标记 failed 并让流水线非 0 退出（不静默降级成无来源内容）。

**备选**：把 prompt 当位置参数传给 `qodercli` —— 否决，实测会吞参数。

### D-B 分节生成而非整页生成

一次调用只做一个章节（900–1400 字 + 该节区块），失败只重试该节。
- 为什么：单页 12 节 ≈ 15,000 字若一次生成，超时与截断风险高，且一处失败要整页重来，成本不可接受。
- 代价：章节间语气可能不统一 → 由"页面级 summary/lead 单独一次调用"补齐串联，并在验收里查章节标题重复度。

### D-C SSR 静态化：`renderToStaticMarkup` + CSS 手工内联，不走 Vite build

`scripts/render.mjs` 直接以 Node 导入 TSX 编译产物渲染，并把 `web/src/tokens/*.css` 读成字符串注入 `<style>`。
- 为什么不用 `vite build`：产物要**单文件自包含**，走 build 会产出 hash 命名的 JS/CSS 资源与 chunk 拆分，反而要做二次内联；而知识页无交互逻辑，运行时 JS 为零，`renderToStaticMarkup` 已足够。
- Vite 只用于 `web/` 工作台（人眼验收排版）。
- **备选**：`react-dom/server` + esbuild 打包组件 —— 采用其思路（用 esbuild 把 TSX 转 JS 供 Node 端导入），但不产出浏览器 bundle。

### D-D 区块类型是封闭枚举

`block.type` 只能是 10 类之一；模板用穷尽 switch 渲染，遇到未知类型**抛错**而非忽略。
- 为什么：静默丢内容是这个管线最危险的失败模式（页面看起来完整、其实少一块）。
- schema 与模板两处各自持有枚举常量，由 `tests/test_contract.py` 断言两者一致，防漂移。

### D-E 图片候选评分而非"取第一条"

`images.py` 对候选打分：尺寸达标 +3、体积 ≥80KB +2、来源页域名可信 +2、标题含章节关键词 +2、重复 -5，低于阈值则不采用。
- 实测依据：中文短查询会混进无关图（"咖啡 咖啡机" 结果里出现手抄包图），取第一条必然翻车。
- `manifest.json` 落盘 `murl/turl/purl/title/宽高/体积/落盘名/所属章节`，人工复核只看这一个文件。

### D-F 校验规则以 ID 暴露，供 spec 与测试双向引用

`validate.py` 每条闸门是一个 `Gate(id="G-05", ...)` 记录，CLI 支持 `--gate G-05` 单跑。
- 为什么：`specs/quality-gates/spec.md` 的场景与 `tests/` 的用例需要稳定锚点，否则改名即断链。
- 闸门编号→spec 场景的映射表写在 `tests/test_gate_matrix.py`，用它断言"每条闸门至少有一个测试"，防止闸门只写在文档里。

### D-G 主题 token 与"不雷同"断言

每个领域一份 `web/src/tokens/<领域>.ts`（主色/强调/背景/字形族/motif 标识）。`validate.py` 计算两两页面主色板色差，低于阈值判 fail。
- 为什么写成断言：不写就会被悄悄复用同一套 token，10 页趋同正是 `frontend-design` 点名的破绽。

### D-H 测试替身：录制的 LLM fixture

`tests/fixtures/llm/<领域>/<section>.json` 存真实返回，集成测试用 `--llm-replay` 跑。
- 为什么：让 1→5 全流程在无网络、无模型额度下可重放，开发者才肯频繁跑（快速反馈是防 regression 的前提）。
- 首次真实生成咖啡时顺手录制这套 fixture（M3 副产品）。

## Migration Plan

无存量数据，纯新增。落地顺序即 `tasks.md` 顺序：M0 骨架 → M1 模板（有快照测试保护）→ M2 流水线（有假 LLM 回放保护）→ M3 咖啡打样（产出真实基线）→ M4 批产 → M5 扩展性验证。

回滚：每里程碑一次提交；未 `git init` 前无法回滚，因此**M0 第一件事建议先 `git init`**（见 Open Questions）。产物目录 `output/` 可整目录删除重建，无状态。

## Open Questions

- 是否 `git init`（当前非仓库，影响回滚与 pre-commit 闸门；需开发者决定，不阻塞 M0/M1 编码）。
- `rule.md` 7 条候选红线是否生效（不阻塞：闸门默认按"无生效红线"运行）。
- 正文 4,500–6,500 字是否真等于你心里的"10 分钟"（可只改 `config/quality_bar.json`）。
