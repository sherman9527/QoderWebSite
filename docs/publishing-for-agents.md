# 给 Agent 的发布手册：把一篇文章发成一个公开站点

读者是**下一个接手的 agent**（或按手册操作的人）。这篇文章讲"怎么把
`output/<领域>/<领域>.html` 变成公网 URL 并记进账本"，不讲怎么生成文章。

前提：仓库已经能跑通 `python scripts/generate.py <领域>`，并且
`python scripts/validate.py --all` 是 `0 fail`。**闸门没过就不要发布**——
发布链路对内容质量零判断，它只会把本地那份原样搬上去。

---

## 0. 一句话的形状

```
生成 → 闸门 → pack（脚本）→ prepare_site → 验证 ready → publish_site
     → 设 public → curl 验 200 → record 写回账本 → 重建主页 → 重发主页站
        ↑ 脚本能做                ↑ 只有 agent 能做（MCP 工具）        ↑ 脚本能做
```

**脚本发不了布。** 托管工具（`prepare_site` / `publish_site` / `update_access_policy`）
是 MCP 工具，只有 agent 会话能调；`qodercli` 没有 `sites` 子命令，也没有受支持的
CI/REST 路径。所以这条链路是**半自动**的：脚本算出一切确定性部分，agent 执行要授权的那几步。

## 1. 先向脚本要清单，不要凭记忆拼参数

```bash
python scripts/publish.py playbook          # 人读
python scripts/publish.py playbook --json   # agent 读
```

它给的是**带具体参数的步骤**：`projectRoot`、`webDirectory=dist/<slug>`、`slug`、
以及最关键的 `projectId`。为什么必须来自脚本而不是来自你的记忆或上一轮对话：

- `projectId` 决定更新落到**哪个站**。猜错的后果是把 A 篇发到 B 篇的站上，
  而且两边看起来都"发布成功"。（本项目 2026-09-25 真发生过：把访问策略改到了另一个
  草稿站，`published: true` 之后 curl 仍 401，因为改的是别人的站。）
- 权威源是各篇 `output/<领域>/data.json` 的 `site` 字段；主页站的 projectId 在
  `config/home_site.json`（它不是一篇文章，没有 `data.json` 可住）。

`playbook` 只列**内容指纹变了**的篇。改一次模板会让 20 篇全部重渲染，但只有真正
需要重发的才进清单——判据是包内字节哈希，不是"这次跑没跑过"。清单为空就是
`✓ 没有待发布的篇`。

## 2. 出包

```bash
python scripts/publish.py pack <领域>
```

产出 `dist/<slug>/`：`index.html` + **页面 `<img src>` 真引用到的图**。三条规矩：

- **包就是验证过的那份产物**：不改名、不压图、不重写 `src`。一旦允许改内容，
  发出去的东西和闸门判过的就不是同一个东西。
- 排除 `manifest.json` / `search-stats.json` / `images.prev/`（采集器的内部账本，
  发出去只是把实现细节公开）。
- 超过 **50 MiB** 直接报错退出，**绝不悄悄压图**。

## 3. 发布（agent 执行）

对清单里每一条：

1. `prepare_site(projectRoot, webDirectory, slug, displayName[, projectId])`
   —— 带 `projectId` 是更新，不带是建新站。**同一个 `actionId` 重试，不要新建 action**——
   但这句话只对"同一份上传"成立：本地重新出包之后 `actionId` 必须换一个新的，
   旧 actionId 撞见上一份未发布的草稿会报 `sites_duplicate_draft`，
   而那份草稿的 artifact 是**旧字节**，复用它等于把刚修的缺陷再发一遍。
2. `get_publish_status(actionId)` 轮询到 `canPublish: true`。
   `queued` / `running` / 验证 Operation 存在，都**不是** ready。
3. `publish_site(actionId)`。
4. 再 `get_publish_status`，直到 `published: true` **且** `site.active_release_id` 非空。
   只有 `published: true` 才算发出去了。
5. `update_access_policy(siteId, mode=public, confirmPublic=true, expectedRevision=<当前>)`
   —— **发布 ≠ 可见**。新站默认 private，`published: true` 之后 curl 仍会 401。
   改可见性需要用户明确授权，且要先 `get_site` 核对 siteId。
6. `curl -s -o /dev/null -w '%{http_code}' <url>` 必须是 200。

## 4. 记账（脚本执行）

```bash
python scripts/publish.py record <领域> <url> --project-id <projectId> \
       --access public --published-date YYYY-MM-DD
python scripts/publish.py check      # 账实核对
```

`record` 会拒绝两类输入，别绕过：

- **不给 `--project-id`**：只记 URL 的账，下一次更新就得凭记忆认站。
- **URL 主机名不是该篇 slug 派生的**（`<slug>-…`）。这条是被真实事故逼出来的：
  我拼错过 18 条 URL（`https://<slug>/<后缀>`），而 `check` 照样报"账实一致"——
  账本和 `data.json` 由同一次错误生成时，同源互校发现不了一致的错。

`web_list.md` 是**派生物**，由 `record` 整体重生成，永远不要手改。
`validate.py` 的 G-14 判的就是它和 `data.json` 是否一致。

## 5. 最后一步：主页站

```bash
python scripts/build_index.py --variant hosted     # → dist/home/index.html
```

然后对 `slug=knoweverything` 走一遍第 3 步（`projectId` 从 `config/home_site.json` 读，
发完把新的 projectId 写回去）。

**注意 `--json` 是"只打印条目、不渲染"**：`build_index.py --json --variant hosted`
会 rc=0 却不产出任何文件。要出文件必须不带 `--json`。

## 6. 会踩到的坑（都是实测，不是推测）

| 症状 | 真相 | 怎么办 |
|---|---|---|
| `publish_site` 返回 `task_deadline_exceeded`，`published: false` | 服务端发布 worker 超时，**可重试**，与包内容无关 | 重新 `prepare_site` 让验证再次 `succeeded`，然后 `publish_site` 会拿到**新的 Operation id** 并成功。在同一个失败 Operation 上重复调用只会拿回同一个失败 |
| `published: true` 但 curl 401 | 新站默认 private | 走 `update_access_policy`，并核对 siteId |
| curl 返回 `000` | 连接层抖动，不是站点坏了 | 先单独重试几次再下结论 |
| 并行 5 个 `get_publish_status` → `sites_unavailable` | 状态读请求更容易撞限 | 批量看状态用**一次 `list_sites`**（含 host / access_mode / active_release_id）；写操作并行 4 个没问题 |
| 改了 `data.json` 的一个新字段，`validate --all` 立刻整篇判死 | `topic_data.schema.json` 是 `additionalProperties: false`，契约没同步；而 G-10 判死会让索引**静默跳过**该篇 | 写产物的代码和约束产物的契约必须同一次改 |
| 线上页面里有 1 个 `<script>` | 托管平台注入的水印脚本，不是我们的产物 | "零运行时 JS"只能在**本地文件**上判；线上要判的是状态码、字节数、关键标记 |
| 中文图片名会不会出问题 | 不会。曾疑过，实测证伪（2.27 MB + 中文名的包上传、验证、服务全正常） | 什么都不用做；`pack` 只报告非 ASCII 文件名，**不改名** |
| `data.json` 干净、闸门全绿，线上却印着点不开的来源编号 | 09-26 实测：21 篇共 587 处 `[S033]`，全部由模板里一处没走 `<Refs>` 的引用位拼出来。**只读 data 的闸门永远看不见模板的错** | 现在 G-06 会读渲染产物；重发包之前先 `node scripts/measure-layout.mjs --file …` 并肉眼过一张元素级截图 |
| 单包上限 | 50 MiB（实测 29.78 MB 通过） | 超了就拆文章，不要压图 |
| 站点总数配额 | 实测 21 个站未触发 `sites_total` | 真撞了再谈合站，届时 slug 形状要重新定 |

## 7. 完成判据（缺一不可）

```bash
python -m pytest                      # 别接管道；rc 与"N passed"都要看真的
python scripts/validate.py --all      # 20 个领域 0 fail
python scripts/publish.py check       # ✓ 账实一致
python scripts/publish.py playbook    # ✓ 没有待发布的篇
curl -s -o /dev/null -w '%{http_code}' https://<slug>-<后缀>.qoder.website/   # 200
```

最后一条不是形式：`playbook` 清空 + `check` 一致 + curl 200 三件事同时成立，
才叫"这篇已经在公网上了"。
