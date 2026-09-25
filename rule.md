# 红线 rule.md

> 本文件是**开发过程中的硬性禁止项**。需求原文：「建立红线 rule.md，这是开发过程中，如果开发者要求添加红线，后续所有的开发必须遵循红线，**默认没有红线**。做所有的 change 之前都应该检查是否违反红线。」
>
> 因此：**当前生效红线为空。** 下面「候选红线」只是建议，未被开发者确认前**不具约束力**。

## 一、当前生效红线

> 2026-09-19 开发者指令：「3、4 你自己决定我只看效果」——候选红线由 Agent 裁决生效。
> 决策记录见 `memo.md` D-08。红线只能由开发者移除或放宽。

- **[R-01]** 产物 HTML 禁止任何外部网络资源（CDN、外链字体、远程图片），必须 `file://` 双击可开 —— 检测：G-04
- **[R-02]** 禁止编造数字：价格/年份/产量/排名等硬事实必须绑定可点开来源，无来源即生成失败 —— 检测：G-06、G-07
- **[R-03]** 每张**引用图**必须记录来源页 `source_page`，无源图片不得进产物；本项目自画的示意图必须标 `kind=illustration` + `based_on`（画的是正文里哪几条已溯源事实），**禁止**带 `source_page` 冒充引用图，且页面上必须有「示意图 · 非实拍」角标 —— 检测：G-10（schema 的 if/then 双向约束：photo 缺 source_page 死、illustration 带 source_page 死、缺 based_on 死）+ `tests/test_redlines.py::test_R03_data_schema_rejects_image_without_source_page`、`tests/test_redlines.py::test_R03_self_drawn_illustration_is_allowed_but_cannot_fake_a_source`、`tests/test_render.py::test_a_self_drawn_illustration_is_labeled_and_has_no_source_link`。2026-09-24 开发者授权此改写，见 `memo.md` D-22：允许生图的前提是**标得出种类**，不是放松可核查性。
- **[R-04]** 禁止用品牌 logo、桌面壁纸、广告大片、海报作为正文配图 —— 检测：`scripts/images.py` DECOR_HINTS + `tests/test_redlines.py::test_R04_rejects_logo_wallpaper_and_ad_creatives`
- **[R-05]** 每篇正文目标 4,500–6,500 汉字；**超出 2,000 字以内（≤8,500）可接受**，再多才判死 —— 检测：G-05（软上限 warn / 硬上限 fail，容忍值 `quality_bar.words.overrun_tolerance_chars`）。2026-09-19 开发者原话「超出 2000 字以内可接受」，同时判定「默认还是高质量吧」→ 不砍章节、不限制每章来源数
- **[R-06]** 未跑 `python scripts/validate.py --all` 全绿，不得在 `HANDOVER.md` 里把任何领域标为已完成 —— 检测：流程（COMPLETE 条目必须带可点开的证据指针）
- **[R-07]** 依赖安装必须国内镜像优先、官方源其次、源码编译最后，且镜像配置必须写进仓库 —— 检测：`tests/test_redlines.py::test_R07_npm_registry_pinned_in_repo`、`test_R07_pip_index_pinned_in_requirements`
- **[R-08]** 生成过程不得向项目工作目录落盘无关文件；联网研究的中间文件只允许进 `output/<领域>/` 或 `.research-scratch/` —— 检测：`tests/test_llm.py::test_cli_runs_in_scratch_dir_not_project_root`
- **[R-09]** 样式层改动必须附真浏览器几何断言或截图验收，不得只凭 pytest 全绿 —— 检测：G-13 + `tests/test_gates.py::test_G13_detects_wide_screen_defects`（闸门自身要被注错自证）

<!--
添加格式（由开发者明确指令后填写）：
- **[R-01]** 一句话规则 —— 违反后果 / 检测方式（尽量给出可执行断言或 validate.py 规则名）
  注意：`validate.active_red_lines()` 按 `- **[R-NN]**` 开头的行解析，格式改了要同步改解析。
-->

## 二、如何添加红线

1. 开发者提出「加一条红线：X」；
2. 在本文件「一、当前生效红线」按 `[R-NN]` 编号追加，写清**规则**与**检测方式**；
3. 若该红线可机检，同步在 `scripts/validate.py` 加一条断言，并在 `tests/` 补一个会因违反红线而失败的用例（TDD：先红后绿）；
4. 在 `HANDOVER.md` 的 TODO 增加对应工作项，在 `memo.md` 决策记录里写为什么加；
5. 红线**只能由开发者移除或放宽**，Agent 不得自行删除。

## 三、每次改动前的检查动作（强制流程）

做任何 change 之前，按顺序确认：

- [ ] 读本节「一、当前生效红线」，逐条比对本次改动是否违反；
- [ ] 若存在可机检红线，跑 `python scripts/validate.py --all`，确认仍全绿；
- [ ] 若本次改动**会**违反红线：停止，向开发者说明并请求处置（改方案 or 明确放宽），不得先斩后奏。

## 四、候选红线（**未生效**，等待开发者裁决）

以下是我在研究需求与网络环境后认为值得上升为红线的内容，**在你确认之前我不会把它们当规则执行**：

| 编号建议 | 候选规则 | 为什么值得 |
|---|---|---|
| 候选-A | 产物 HTML 禁止任何外部网络资源（CDN/外链字体/远程图片），必须离线可开 | 需求要"纯静态 html"；本网络 Wikimedia/DuckDuckGo 不可达，外链必然挂图 |
| 候选-B | 禁止编造数字：价格/年份/产量/排名等硬事实必须带可点开来源 URL，无来源即生成失败 | 这是科普页的信任底线；参考项目 oreilly 也把它写成筛选标准第 3 条 |
| 候选-C | 图片必须记录来源页 `purl` 并在图注展示，禁止无源图片进产物 | 奢侈品/腕表图多来自网络，无源即版权风险 |
| 候选-D | 禁止使用品牌官方 logo、受版权保护的广告大片作为页面装饰元素 | 与候选-C 同源的法律风险，且装饰性 logo 无信息价值 |
| 候选-E | 每篇正文必须落在 4,500–6,500 汉字区间（对应"10 分钟读完"），不得为凑字数灌水 | 需求 7 是唯一篇幅口径，超出即视为质量退化 |
| 候选-F | 禁止在未跑 `validate.py` 全绿的情况下宣称某个领域"已完成" | 防止"生成了就算完"，与需求 4 的防 regression 目标一致 |
| 候选-G | 依赖安装顺序必须国内镜像优先、官方源其次、源码编译最后 | 需求 7/8 明文要求；本环境实测官方源可达性差 |
| 候选-H | 生成过程不得向项目工作目录落盘无关文件；联网研究产物只允许进 `output/<领域>/` 或 `.research-scratch/` | 实测 `qodercli` 联网研究会往 cwd 写出 15 个网页/PDF，污染仓库根目录 |
| 候选-I | 样式层改动必须附"可见性/尺寸"断言或真浏览器截图验收，不得只凭 pytest 全绿 | 本 session 连续两个 bug（标题被 overflow 裁掉、配图撑出 1144px 空块）都是在测试全绿的情况下被肉眼发现的 |

## 五、变更历史

| 日期 | 动作 | 提出方 |
|---|---|---|
| 2026-09-19 | R-05 放宽：超目标 2,000 字以内只 warn；耗时口径保持高质量默认 | 开发者（「超出 2000 字以内可接受」「默认还是高质量吧」）|
| 2026-09-19 | 建立本文件，生效红线为空，附 7 条候选 | Agent（依据 requirement.txt 第 6 条） |
