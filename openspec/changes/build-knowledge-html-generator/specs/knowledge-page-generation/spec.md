# Spec Delta

## Purpose

定义"一条命令生成一个领域知识专题页"的对外行为：输入参数、产物形态与命名、部分重跑语义、失败与退出码，使生成结果可预期、可脚本化批量调用。

## ADDED Requirements

### Requirement: 单命令生成一个领域

系统 SHALL 提供形如 `generate.py <领域>` 的命令，接受一个领域名作为唯一必需参数，并在一次调用内完成大纲解析、内容生成、图片获取、页面渲染与质量验收五个阶段，产出该领域的知识专题页。

#### Scenario: 生成已配置的领域

- **WHEN** 运行 `generate.py 咖啡`，且 `config/topics/咖啡.json` 存在
- **THEN** 命令以退出码 0 结束
- **AND** `output/咖啡/` 下存在一个 `<领域>_YYYY-MM-DD.html` 文件与该页引用的 `images/` 目录
- **AND** 质量验收阶段的全部闸门通过

#### Scenario: 领域未配置

- **WHEN** 运行 `generate.py 不存在的领域`，且 `config/topics/不存在的领域.json` 不存在
- **THEN** 命令 MUST NOT 静默产出空页面
- **AND** 系统给出可执行的下一步提示（要么创建该大纲文件，要么显式请求由模型起草一份大纲供人工确认）
- **AND** 退出码非 0

#### Scenario: 重复生成同一天

- **WHEN** 同一领域在同一天内被再次生成
- **THEN** 系统复用同一日期文件名并覆盖旧产物
- **AND** 覆盖前把被替换的产物路径告知调用方

### Requirement: 产物命名与位置

生成页的文件名 SHALL 为 `<领域>_YYYY-MM-DD.html`（日期为生成当日，`YYYY-MM-DD`），并存放于 `output/<领域>/` 下；该页引用的全部图片 SHALL 位于同一 `output/<领域>/images/` 目录内。

#### Scenario: 文件名符合约定

- **WHEN** 2026-09-19 生成"香奈儿"专题页
- **THEN** 产物路径为 `output/香奈儿/香奈儿_2026-09-19.html`

#### Scenario: 图片随页隔离

- **WHEN** 依次生成"咖啡"与"香奈儿"两个领域
- **THEN** 两者的图片分别位于 `output/咖啡/images/` 与 `output/香奈儿/images/`
- **AND** 任一页面 MUST NOT 引用另一领域目录下的图片

### Requirement: 离线与局部重跑

系统 SHALL 支持不重复消耗模型额度即可重做渲染与验收，以及只重做单个章节。

#### Scenario: 离线重渲染

- **WHEN** 运行 `generate.py 咖啡 --offline`，且该领域已有 `data.json` 与 `images/`
- **THEN** 系统跳过内容生成与图片获取阶段
- **AND** 仍执行渲染与质量验收，并按验收结果决定退出码

#### Scenario: 单章节重做

- **WHEN** 运行 `generate.py 咖啡 --only roasting`
- **THEN** 系统只重新生成 `roasting` 章节内容
- **AND** 其余章节内容保持不变
- **AND** 页面整体重新渲染并通过验收

### Requirement: 失败可定位且可恢复

任一阶段失败时，系统 SHALL 明确指出失败的阶段、领域、（若适用）章节，并保留已完成的中间产物以便续跑，MUST NOT 留下半成品页面却报告成功。

#### Scenario: 章节生成失败

- **WHEN** 某章节内容生成重试后仍不合格
- **THEN** 命令以非 0 退出码结束
- **AND** 输出指明失败章节标识与失败原因
- **AND** 已通过的其他章节内容保留在 `data.json` 中供 `--only` 续跑

#### Scenario: 验收未过不产页

- **WHEN** 渲染完成但质量验收存在 fail 级问题
- **THEN** 命令以非 0 退出码结束
- **AND** 输出逐条列出未通过的闸门与定位信息
