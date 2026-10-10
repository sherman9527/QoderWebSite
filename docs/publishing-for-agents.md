# 给 Agent 的发布手册：把一个**组**发成一个公开站点

读者是**下一个接手的 agent**（或按手册操作的人）。这篇文章讲"怎么把
`output/<领域>/` 里验证过的产物发成公网地址并记进账本"，不讲怎么生成文章。

**发布单位是组，不是篇**（`memo.md` D-34 授权、D-36 落地）。29 篇文章按类别装进
13 个组站，成员与站点身份的唯一权威是 `config/site_groups.json`；一篇文章在公网上的
地址是它所在组站的**深链** `https://<组>-…qoder.website/<slug>/<slug>.html`。

前提：`python scripts/validate.py --all` 是 `0 fail`。**闸门没过就不要发布**——
发布链路对内容质量零判断，它只会把本地那份原样搬上去。

---

## 0. 一句话的形状

```
生成 → 闸门 → pack <组>（脚本）→ prepare_site → 验证 ready → 【读回 host】
     → publish_site → 设 public → verify_live → record-group（脚本）
     → 重建并重发主页站 → absorbed <组> → 删旧站
        ↑ 脚本能做        ↑ 只有 agent 能做（MCP 工具）        ↑ 顺序不能换
```

**脚本发不了布。** 托管工具（`prepare_site` / `publish_site` / `update_access_policy`
/ `delete_project`）是 MCP 工具，只有 agent 会话能调；`qodercli` 没有 `sites` 子命令，
也没有受支持的 CI/REST 路径。所以这条链路是**半自动**的：脚本算出一切确定性部分，
agent 执行要授权的那几步。

**主页重建与重发必须在删旧站之前。** 主页卡片链的是各篇 `data.json` 的 `site.url`；
先删后建，线上主页就会挂着指向已删站的 404 卡片，而每一步看起来都执行了。

## 1. 先向脚本要清单，不要凭记忆拼参数

```bash
python scripts/publish.py playbook          # 人读
python scripts/publish.py playbook --json   # agent 读
python scripts/publish.py groups            # 全组总览：成员数、有没有地址
```

它给的是**带具体参数的步骤**：`projectRoot`、`webDirectory=dist/<组>`、`group`、
`members`，以及最关键的 `projectId`。为什么必须来自脚本而不是你的记忆或上一轮对话：

- `projectId` 决定更新落到**哪个站**。猜错的后果是把 A 组发到 B 组的站上，
  而两边看起来都"发布成功"。（本项目 2026-09-25 真发生过：访问策略改到了另一个
  草稿站，`published: true` 之后 curl 仍 401。）
- 组身份住在 `config/site_groups.json`（不是 `data.json.category`——category 是内容的
  属性，会随编辑判断改，而组名进了 URL）。主页站自己的 `projectId` 在
  `config/home_site.json`：它不是一篇文章，没有 `data.json` 可住。

`playbook` 只列**指纹变了**的组。判据是两级指纹：`own_sha(篇)` 只覆盖这一篇自己的
字节，组怎么重组它都不动；`group_sha(组)` 覆盖落地页 + Σ(成员 own_sha) + 组身份。
所以改一次模板会惊动每一组的落地页，而只改一篇只惊动它那一个组。清单为空就是
`✓ 没有待发布的组`。

## 2. 出包

```bash
python scripts/publish.py pack <组>
```

产出 `dist/<组>/`：`index.html`（该组成员的落地页）+ 每个成员一个 `<slug>/` 目录
（`<slug>.html` 与被它引用的图）+ 落地页要用的封面图。五条规矩：

- **包就是验证过的那份产物**：不改名、不压图、不重写 `src`。图片压缩发生在**入库时**
  （`scripts/images.py` 的 `fit_bytes`），不在这里——出包时压会造出第二份字节，
  上面那句话当场作废。
- **文章页一个字节都不改**。它们「返回主页」写的是相对路径 `../index.html`：
  在包内正好指向该组落地页。曾经有一套"改写返回链接 + 要求标记恰好出现一次"的
  字符串契约，一篇一站时代它存在的唯一理由（那个相对路径会指回自己）随合站消失了。
- **包目录里的文件集合必须恰好等于包清单**。`prepare_site` 拿的是**整个目录**，
  所以包里多出来的任何东西都会上公网。`_prune_to_package` 递归清掉它们——
  包括渲染顺带写出的 `<页面>.html.srchash`，也包括打包器自己的 marker
  （它因此搬到 `dist/.packed/<组>.sha`，不在被清理的那棵树里）。
  **这里刻意不写"排除名单"**：名单是一条会漏的规矩，加两个名字，下一个内部文件照样漏。
- 落地页每个相对链接都必须能在包内找到文件；**任何一次失败的 `pack` 都不留包目录**
  （超限、缺 slug、链接对不上，一律清场）。包是构建产物，真相在 `output/`——
  留在盘上的半成品会被下一次 `prepare_site` 照原样传上去。
- 超过 **40 MiB**（工作上限；文档给的硬顶是 50）直接报错，并报"这个组该分裂了"。
  实测 2026-10-04 通过的最大包：`ai-industry` 30.90 MB、160 个文件、含 92 个中文文件名。

## 3. 发布（agent 执行）

对清单里每一条：

1. `prepare_site(projectRoot, webDirectory, slug, displayName[, projectId])`
   —— 带 `projectId` 是更新，不带是建新站。**同一个 `actionId` 重试，不要新建 action**——
   但这句话只对"同一份上传"成立：本地重新出包之后 `actionId` 必须换一个新的，
   旧 actionId 撞见上一份未发布的草稿会报 `sites_duplicate_draft`，
   而那份草稿的 artifact 是**旧字节**，复用它等于把刚修的缺陷再发一遍。
2. `get_publish_status(actionId)` 轮询到 `canPublish: true`。
   `queued` / `running` / 验证 Operation 存在，都**不是** ready。
3. **读回 `site.host`，和 `python scripts/publish.py groups` 里那个组名拼出来的地址逐字比。**
   这一步不是仪式感，见第 6 节第一条：组名短于 3 个字符时 `prepare_site` 不报错，
   而是**静默**换一个十六进制前缀给你。
4. `publish_site(actionId)`。
5. 再 `get_publish_status`，直到 `published: true` **且** `site.active_release_id` 非空
   **且** Operation `committed: true`。只有 `published: true` 才算发出去了。
6. `update_access_policy(siteId, mode=public, confirmPublic=true, expectedRevision=<当前>)`
   —— **发布 ≠ 可见**。新站默认 private，`published: true` 之后 curl 仍会 401。
   改可见性需要用户明确授权；`expectedRevision` 是**字符串**。
7. 验收：`python .probe/verify_live.py <组>`。它判三件事——落地页与每条深链是否 200、
   每页每张 `<img>` 是否 200（中文要百分号编码、相对路径要按**页面所在目录**解析），
   以及剥掉平台注入的水印脚本之后**线上字节是否等于包内那份**。
   第三条才是"包就是验证过的那份产物"在线上的唯一证据；手 curl 只会证明"有个页面在那儿"。

## 4. 记账（脚本执行）

```bash
python scripts/publish.py record-group <组> <组地址> --project-id <projectId> \
       --access public --published-date YYYY-MM-DD
python scripts/publish.py check      # 账实核对
```

`record-group` 会把组身份写进 `site_groups.json`，并把**每个成员**的
`data.json.site` 改成 `{group, path, url=深链, project_id, content_sha(=own_sha), …}`。
它会拒绝两类输入，别绕过：

- **不给 `--project-id`**：只记 URL 的账，下一次更新就得凭记忆认站。
- **主机名不等于该组名派生的地址，或路径不等于 `/<slug>/<slug>.html`**。两段都查、
  且**整名相等**——退化成 `startswith` 就等于把 `watches-anything.evil.tld` 也收下。
  这条被真实事故逼出来过两次：我拼错过 18 条 URL，而 `check` 照样报"账实一致"
  （账本和 `data.json` 由同一次错误生成时，同源互校发现不了一致的错）。

`web_list.md` 是**派生物**，由记账整体重生成，永远不要手改。`validate.py` 的 G-14
判的就是它、`data.json`、`site_groups.json` 三处是否同源。

## 5. 收尾两刀：主页，然后才是旧站

```bash
python scripts/build_index.py --variant hosted     # → dist/home/index.html（29 张卡）
python .probe/verify_home.py                       # 线上主页：卡数 + 每张卡 200
python scripts/publish.py absorbed <组>            # 这组吸收掉哪些旧单篇站
python .probe/absorbed_ids.py <组>                 # 附上 projectId，账本与规则两边对上才列
```

主页站按第 3 步再走一遍（`projectId` 从 `config/home_site.json` 读）。

**只有内容变了才需要重发主页**：卡片封面内联的是 `dist/.thumbs/` 里按内容哈希缓存的
缩略图（上限 `quality_bar.index.card_cover_px`），所以任何一次 `--variant hosted`
都会把主页字节重排一遍——`ls -la dist/home/index.html` 只用来看，别拿它当"变了"的判据。
反过来，**组站的指纹里不含主页**，重发主页不会让 13 个组变成待发布。

**注意 `--json` 是"只打印条目、不渲染"**：`build_index.py --json --variant hosted`
会 rc=0 却不产出任何文件。要出文件必须不带 `--json`。

`absorbed` 之后删站：先 `get_project(projectId)` 读 `display_name` 与 `revision`，
再 `delete_project(... confirmDisplayName, expectedRevision, confirm=true)`，
然后 `get_operation` 轮询到 `succeeded`，最后 `get_project` 确认 `status: deleted`。
**`accepted` 不等于 deleted。** 只有 `verify_live` 全绿的组才可以删它的成员旧站。

## 6. 会踩到的坑（都是实测，不是推测）

| 症状 | 真相 | 怎么办 |
|---|---|---|
| 站建出来了，host 是一串十六进制而不是组名 | 平台的前缀下限是 **3 个字符**，`prepare_site` 遇到非法前缀**不报错**，按它文档里 "with server fallback" 静默换地址。后果是账上写 `ai-…`、线上住 `5d8a…`，每条卡片从第一天起就 404 | 组名由 `publish._require_addressable()` 在**读组表时**判死（3–51）。别信本地拼的地址，发完读回 `get_site` 的 host |
| 准备删一个旧站，`display_name` 和文章名对不上 | 那个站被复用过（真实例子：`llm-and-crypto` 被改名成「归因探针 · 中文文件名小包」当实验载体）。账上的 `project_id` 仍然有效，但**它承载的不一定是你以为的内容** | 停下来查历史结论是否已经落在 `memo.md`，确认没信息要救之后再删 |
| `publish_site` 返回 `task_deadline_exceeded`，`published: false` | 服务端发布 worker 超时，**可重试**，与包内容无关 | 重新 `prepare_site` 让验证再次 `succeeded`，然后 `publish_site` 会拿到**新的 Operation id** 并成功。在同一个失败 Operation 上重复调用只会拿回同一个失败 |
| `published: true` 但 curl 401 | 新站默认 private | 走 `update_access_policy`，并核对 siteId |
| curl 返回 `000` | 连接层抖动，不是站点坏了 | 先单独重试几次再下结论 |
| 并行几个 `get_publish_status` → `sites_unavailable` | 状态读请求更容易撞限 | 批量看状态用**一次 `list_sites`**；写操作并行 4 个没问题。但 `list_sites` 每条都带一张签名封面图 URL，读起来很贵——能用 `get_project`/`get_operation` 定点查就别整表拉 |
| 改了 `data.json` 的一个新字段，`validate --all` 立刻整篇判死 | `topic_data.schema.json` 是 `additionalProperties: false`，契约没同步；而 G-10 判死会让索引**静默跳过**该篇 | 写产物的代码和约束产物的契约必须同一次改 |
| 线上页面里有 1 个 `<script>` | 托管平台**有时**注入水印脚本，不是我们的产物 | "零运行时 JS"只能在**本地文件**上判；线上判字节要先剥掉注入（`verify_live.py` 做了）。**但注入不是每次都发生**：10-04 主页重发后 `live sha == local sha` 且响应里没有 `data-qoder-watermark`——所以"剥掉之后再比"是常规，"必须剥掉才相等"不是判据，报数时按实测说 |
| 中文图片名会不会出问题 | 不会。两次独立证据：2.27 MB + 中文名的包（09-25）、30.90 MB + 92 个中文名的组包（10-04）都上传、发布、逐图 200 | 什么都不用做；`pack` 只**报告**非 ASCII 文件名，**不改名** |
| `data.json` 干净、闸门全绿，线上却印着点不开的来源编号 | 09-26 实测：21 篇共 587 处 `[S033]`，全部由模板里一处没走 `<Refs>` 的引用位拼出来。**只读 data 的闸门永远看不见模板的错** | 现在 G-06 会读渲染产物；重发包之前先 `node scripts/measure-layout.mjs --file …` 并肉眼过一张元素级截图 |
| 单包上限 | 工作上限 40 MiB（实测 30.90 MB 通过；文档给的硬顶 50 MiB 没实测过） | 超了就分裂这个组（`<slug>-2` 接**新**文章，已发布的不搬），不要压图 |
| 站点总数配额 | **10-03 实测天花板：`sites_total` = 30**，含"建了没发布"的站。**更新已有站不受影响**——带 `projectId` 的 prepare 不新建 | 撞了就停下把 `used/limit` 报出来。**删站当场释放**（10-04 实测），所以滚动迁移的写法是"建一组、验一组、删一组"，不是一次腾够 13 个坑。拿本地包冒充线上不在这条的处置里 |

## 7. 完成判据（缺一不可）

```bash
python -m pytest                       # 别接管道；rc 与"N passed"都要看真的
python scripts/validate.py --all       # 29 篇 0 fail（组落地页也在闸门里）
python scripts/publish.py check        # ✓ 账实一致
python .probe/verify_live.py <组>      # ✓ 深链、每张图、字节等于包
python .probe/verify_home.py           # ✓ 线上 29 张卡全 200
python scripts/publish.py playbook     # ✓ 没有待发布的组
```

`playbook` 清空 + `check` 一致 + `verify_live` 全绿三件事同时成立，才叫"这一组已经在
公网上了"。少任何一条都只证明我做了一半。
