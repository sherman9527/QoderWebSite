# Tasks

## 1. Setup（M0 地基）

- [x] 1.1 创建目录骨架（`config/`、`web/src/{template,tokens,workbench}`、`scripts/`、`tests/{fixtures,golden}`、`output/`）并验证 `ls` 可见全部约定路径与 `AGENTS.md` §5 一致
- [x] 1.2 写 `requirements.txt`（pytest + jsonschema）并用清华源安装，验证 `python -m pytest --version` 成功退出
- [x] 1.3 建 `pytest.ini`（`testpaths=tests`、UTF-8 输出）并验证空套件 `python -m pytest -q` 以 "no tests ran" 退出而非报错
- [x] 1.4 写 `tests/test_smoke.py` 断言治理四件套（`AGENTS.md`/`rule.md`/`memo.md`/`HANDOVER.md`）存在且非空，验证 `python -m pytest tests/test_smoke.py -q` 通过
- [x] 1.5 初始化 `web/`（Vite + React + TS，npmmirror 源）并验证 `npm run build` 在 `web/` 下成功产出 dist

## 2. 数据契约（M2 前置）

- [x] 2.1 写 `config/topic_outline.schema.json`（含 `topic`/`theme`/`reading_target_minutes`/`sections[]`，每节必填 `id`/`title`/`angle`/`block_types`/`image_queries`）并验证 schema 自身是合法 JSON Schema
- [x] 2.2 写 `config/topic_data.schema.json`（`blocks[].type` 为 10 类封闭枚举）并验证一份手工样例数据通过校验
- [x] 2.3 写 `scripts/outline.py`（加载 + 校验 + 章节 id 去重检查）并验证 `tests/test_outline.py` 覆盖"缺字段""重复 id""未知领域"三种失败路径各自报错定位到文件与位置
- [x] 2.4 写 `tests/test_contract.py` 断言 `block_types` 枚举在 schema 与模板常量两处完全一致，验证该测试当前可失败（人为改一处常量即红）

## 3. 黄金模板（M1）

- [x] 3.1 建 `web/src/tokens/` 主题 token 结构与咖啡一套 token，验证 TypeScript 类型检查通过且 token 字段齐全（主色/强调/背景/字形族/motif）
- [x] 3.2 实现 10 类区块组件，未知 `block.type` 抛错而非忽略，验证单测 `test_blocks.py::test_unknown_block_type_raises` 通过
- [x] 3.3 实现 `TopicPage` 骨架（开场 motif、章节目录、章节流、页尾来源与时效声明）并验证快照测试 `test_topicpage_snapshot` 生成且首次通过
- [x] 3.4 实现 `web/src/workbench/` 预览页喂 `data.json` 渲染，验证 `npm run dev` 后浏览器可见完整页面且无控制台报错
- [x] 3.5 用 `frontend-design` 的反默认清单自查咖啡视觉方案（避开奶油底+衬线+陶土橙、近黑底+荧光、SaaS 卡片套件、ALL-CAPS 标签、`A · B · C` 串、链接尾 `→`），验证结论与调整写进 `memo.md` 决策记录
- [ ] 3.6 建响应式与可访问性地板（375px 不破版、键盘焦点可见、`prefers-reduced-motion`、正文行长 <80 字），验证 Playwright 在桌面/移动两档视口截图无横向溢出

## 4. 静态化渲染（M2）

- [x] 4.1 写 `scripts/render.mjs`：esbuild 转译 TSX + `renderToStaticMarkup` + 读 token CSS 注入 `<style>`，验证对 fixture 数据产出 HTML 且 `<script src>`/外链字体/`@import` 均为 0 处
- [x] 4.2 产物文件名与位置实现 `<领域>_YYYY-MM-DD.html` 落在 `output/<领域>/`，验证 `tests/test_render.py` 断言路径正则匹配
- [x] 4.3 模板指纹段写入产物 HTML，验证改动产物样式段后 `validate.py --gate G-08` 判 fail
- [ ] 4.4 集成测试：以 fixture 数据渲染两领域，断言二者主色板差异超阈值，验证 `test_tokens_distinct` 通过

## 5. 图片管线（M2）

- [x] 5.1 写 `scripts/images.py` 的 Bing 解析（`cn.bing.com/images/async` + 解码 `m="..."` 内嵌 JSON 取 `murl/turl/purl/title`），验证用录制 HTML fixture 解析出 ≥10 条候选
- [x] 5.2 实现下载与字节校验（magic bytes 判格式、宽 ≥640、体积 ≥40KB、不以 HTTP 状态码论成败），验证 `test_image_validate.py` 覆盖"404 但字节合法""200 但是 HTML""尺寸过小"三种判定
- [x] 5.3 实现 `murl` 优先 `turl` 兜底 + sha256 去重 + 落盘 `NN_slug.ext`，验证同一查询重复运行不产生重复文件
- [x] 5.4 实现候选评分（尺寸/体积/域名可信/标题相关性/重复惩罚）与黑名单域名过滤，验证 `test_scoring.py` 中无关图（如"咖啡 咖啡机"混入的手抄包图）被剔除
- [x] 5.5 生成 `manifest.json`（落盘名/章节/检索词/murl/turl/purl/宽高/体积）并在图注展示来源，验证每条记录含可点开的 `purl`
- [x] 5.6 断言 `images/` 无孤儿文件、每主要章节 ≥1 图、每 `<img>` 有 `alt`，验证 `validate.py --gate G-03` 对故意删掉一张被引用图后判 fail

## 6. LLM 适配与生成（M2）

- [x] 6.1 写 `scripts/llm.py`：`qodercli -p --permission-mode bypass_permissions --output-format json`，prompt 走 stdin，验证一次最小调用返回 UTF-8 正常中文（文件字节为判据，不看终端）
- [x] 6.2 实现"剥代码围栏 → 取首个平衡 `{}` → schema 校验 → 带错误信息重试一次"三级 JSON 容错，验证 `test_llm_parse.py` 用裹解释文字/多 JSON 块/纯垃圾三种样本均按预期处理
- [x] 6.3 实现联网判据（看内容是否含 http(s) URL，不看恒为 0 的 `web_search_requests`），验证对含 URL 与不含 URL 两种样本判为"已查证/未查证"
- [x] 6.4 实现 `copilot` 兜底与两者皆失败时章节标记 failed + 非 0 退出，验证 `--llm-fail-mock` 下流水线不产出无来源内容
- [ ] 6.5 实现 research pass（联网取料 → 事实条目 + 来源）与 write pass（凭料成文，不联网），验证每节正文硬事实均可追溯到取料条目
- [x] 6.6 实现分节生成（每节 900–1400 字）+ 单节失败只重试该节，验证 `--only <section>` 只改该节、其余字节级不变
- [ ] 6.7 录制 `tests/fixtures/llm/咖啡/*.json` 回放替身，实现 `--llm-replay`，验证断网下完整流水线跑通且零真实模型调用

## 7. 质量闸门（M2 核心，需求 4）

- [x] 7.1 写 `scripts/validate.py` 骨架：`Gate(id, spec_ref, check)` 注册表 + `--all`/`--gate`/`--domain` + 可定位输出 + 退出码，验证 `--gate 不存在` 报可用清单而非静默
- [x] 7.2 实现 G-01 命名与位置、G-02 章节覆盖率、G-09 红线断言（生效红线为空时该组为空集不报错），验证各自正反例测试通过
- [x] 7.3 实现 G-03 图片引用/alt/孤儿、G-04 自包含（无 `<script src>`/外链 `<link>`/`@import`/`url()` 外链），验证故意注入外链后判 fail
- [x] 7.4 实现 G-05 正文 4,500–6,500 汉字（读 `config/quality_bar.json`，越界 fail 非 warn）、G-06 数字断言必须有 `source.url` 且域名不在黑名单、G-07 占位符残留，验证三条正反例
- [x] 7.5 实现 G-08 模板指纹一致性与 G-10 数据/大纲 schema 合法性，验证绕过模板手改产物后判 fail
- [x] 7.6 实现"每数字型断言带时点"检查（价格类须标"截至 YYYY-MM"），验证无时点公价被判 fail
- [x] 7.7 写 `tests/test_gate_matrix.py` 断言每条闸门 ≥1 测试且每条 spec 场景有对应闸门，验证人为注释掉一条闸门后该测试变红
- [ ] 7.8 把 `validate.py --all` 接成流水线第 5 阶段（不过即非 0，不产出"看似成功"的半成品页），验证集成测试断言未过闸门时产物不被当作完成

## 8. 主流程（M2 收口）

- [x] 8.1 写 `scripts/generate.py` 五阶段编排（outline → research → images → render → verify）+ `--offline`/`--only`/`--llm-replay`，验证 `--help` 列出全部开关且非法领域在开始前即失败
- [x] 8.2 实现"未完成领域不静默产出"路径：大纲缺失时提示创建或显式请求起草，验证退出码非 0 且不产生空页面
- [x] 8.3 实现同日重复生成覆盖并告知被替换路径，验证第二次运行输出含旧产物提示
- [x] 8.4 端到端集成测试（假 LLM + 假图片源）跑完整 1→5，验证产物存在且 `validate.py --all` 全绿

## 9. 咖啡打样（M3）

- [x] 9.1 写 `config/topics/咖啡.json`，覆盖历史/精品品牌/种植地/大赛/特调做法/价格/烘焙方法/咖啡机，验证通过 `topic_outline.schema.json`
- [ ] 9.2 真实运行 `generate.py 咖啡`（联网），记录命令与输出摘要进 `memo.md` 测试日志，验证 10 章非空且全部闸门绿
- [ ] 9.3 真浏览器验收咖啡页（桌面 + 375px），验证截图无破版、图片无破图、来源链接可点开，并把结论写进 `memo.md`
- [ ] 9.4 把咖啡产物与 fixture 入 `tests/golden/` 作基线，验证模板改动会触发快照差异测试

## 10. 批产（M4）

- [ ] 10.1 香奈儿（历史/限量款包袋/配货政策/全球最划算购物地/价格）大纲 + token + 生成 + 验收全绿
- [ ] 10.2 爱马仕（含配货与工坊、铂金/凯莉）大纲 + token + 生成 + 验收全绿
- [ ] 10.3 百达翡丽（历史/经典型号/复杂功能/拍卖价/保养）大纲 + token + 生成 + 验收全绿
- [ ] 10.4 积家（历史/翻转系列/机芯自产/价格）大纲 + token + 生成 + 验收全绿
- [ ] 10.5 劳力士（历史/型号演变/二级市场溢价/认证体系）大纲 + token + 生成 + 验收全绿
- [ ] 10.6 LV（历史/Monogram 与限量/配货与涨价/产地代工/价格）大纲 + token + 生成 + 验收全绿
- [ ] 10.7 浪琴（历史/名匠与运动系列/价格带/机芯）大纲 + token + 生成 + 验收全绿
- [ ] 10.8 宾利（历史/车型/定制 Mulliner/价格）大纲 + token + 生成 + 验收全绿
- [ ] 10.9 劳斯莱斯（历史/幻影与库里南/Bespoke 定制/价格）大纲 + token + 生成 + 验收全绿
- [ ] 10.10 跑 `validate.py --all` 扫全部 10 个领域并验证两两主色板差异均超阈值、0 fail

## 11. 可扩展性验证（M5）

- [ ] 11.1 新增一个未列入首批的领域（只加 `config/topics/*.json` + token，不改 `scripts/`）并成功生成，验证 `scripts/` 下文件修改时间/内容均未变更（若已 `git init` 则用 `git status` 佐证）
- [ ] 11.2 更新 `AGENTS.md` 与 `memo.md` 记录"如何加新领域"的实际步骤与耗时，验证新人按文档可独立跑通
