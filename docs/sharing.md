# 把页面分享出去

三种方式，成本从低到高。**前两种不需要网络**，第三种给的是公开 URL。

---

## 1. 直接给文件（最常用，零依赖）

产物是自包含静态 HTML：CSS 内联、图片相对路径、**零运行时 JS、零 `file://`、零站点根绝对路径**
（2026-09-25 实测：55 个 HTML 里 `file://` 出现 0 次）。所以"发文件"就等于"发网页"。

```bash
python scripts/open.py output/咖啡/咖啡.html              # 自己先看，走系统默认浏览器
```

给别人：**连目录一起给**，只给 HTML 会断图。

```bash
cd output && zip -r 咖啡.zip 咖啡                        # 咖啡/咖啡.html + 咖啡/images/
```

主页同理：`output/index.html` 加上它引用到的各个领域目录。

## 2. 局域网临时给同事看

产物没有服务端依赖，任何静态服务器都行：

```bash
cd output && python -m http.server 8000                 # http://<你的IP>:8000/
```

这只在同一个网络里可达，不是"分享链接"。要给外面的人看，走第 3 种。

## 3. 托管成公开 URL（Qoder Sites）

**CLI 里就能做**——Windows 客户端那个"分享 URL"按钮走的是同一套托管能力，不是客户端独占。
工具顺序（每一步都不是终态，只有 `published: true` 才是）：

```
prepare_site  →  get_publish_status  →  publish_site  →  get_publish_status(终态)
              →  update_access_policy(要公开时)  →  show_publish_confirmation
```

### 实测硬约束

| 约束 | 实测到的数 |
|---|---|
| 单个站点 artifact ≤ **50 MiB**（文档给的顶） | 09-25：19 篇全量 **165.4 MB**，超 3 倍，一次发不出去。本项目因此把工作上限设在 **40 MiB**——留 20% 余量，超了就把那个组分裂，不压图 |
| 真传上去过的最大包 | **30.90 MB / 160 个文件**（10-04 的组 `ai-industry`，9 篇）。图片入库压缩后全库 190.5 MB → **101.7 MB** |
| 站点总数 **`sites_total` ≤ 30**（账号级） | 10-03 撞实：第 30 个站建完之后 `prepare_site` 报 `sites_quota_exceeded`，含"建了没发布"的站。**更新已有站不受影响**。10-04 实测**删站当场释放**，所以迁移能"建一组、验一组、删一组"地滚 |
| 地址前缀 **3–51 个字符** | 组名短于 3（如 `ai`）时 `prepare_site` **不报错**，静默换成十六进制前缀 → 账上地址和线上地址分家，每条卡片从第一天起 404（D-37） |
| 文件名**不需要** ASCII（已归因） | 一个 165 MB、中文目录名的包被 `sites_artifact_unsafe` 拒过。之后两次独立证据都指向**体积**而不是名字：09-25 的 2.3 MB + 中文名包、10-04 的 30.90 MB + 92 个中文名包，均上传、发布、逐图 200。`pack` 因此**只报告非 ASCII 文件名、绝不改名**——改名等于发出"验证过的产物的另一个版本" |
| 新站默认 `access_mode: private` | 要公开必须另走 `update_access_policy`，且需要 `confirmPublic=true` 与用户对公开的明确授权 |
| 发布内容政策 | 上传前要过一遍站点内容。本项目按公开标准写：加密货币篇刻意不含可操作攻击路径，医药与行情段落都带免责声明 |

### 打包规则（发出去的包该装什么）

- 只放**这个站真正需要**的文件：`index.html` + 它 `src` 到的图片。
- **不要**把 `images/manifest.json`、`images/search-stats.json` 放进包里（`pack` 已经写死排除）——那是采集器的内部账本
  （检索词、召回统计），页面不引用，发出去只是泄露实现细节。
- 不要把 `images.prev/`、`.probe/`、`.git/`、`node_modules/` 放进包。
- 历史日期页不要一起发：`output/` 每个领域留着每天的日期页，索引只链最新那份；
  全发会让旧版本被 URL 摸到，读者会拿旧口径当现状。

### 曾经的状态（2026-09-25：20 篇文章站 + 1 个主页站，每篇一个站）

> **这一段已被 10-04 的合站取代**（`memo.md` D-34 / D-36）。留着是因为它记的是**当时量出来的数**
> 和当时踩的坑，那些不会因为改结构而失效；变的只是"一次发一篇、一篇占一个站"这个形状。


每篇一个站，逐篇 `pack` → `prepare_site` → 验证 Operation `succeeded` → `publish_site` →
`update_access_policy(public)`。**判"发出去了"的是 `list_sites` 里每个站点 `active_release_id`
非空**，之后逐站 `curl` 全部 200（最小的 `snapdragon-laptop` 1.79 MB 包 / 207 KB HTML，
最大的 `ai-glasses` 256 KB HTML、23 张图）。全部 19 篇的地址在
[`web_list.md`](../web_list.md)——它是各篇 `data.json.site` 的派生物，不要手改。

配额实测：`list_sites` 报 `total_size: 21`（20 篇文章站 + 1 个主页站 + 1 个早期空草稿），
**没有触发 `sites_total`**；最大单包 **29,781,927 字节**（LV）验证 `succeeded`，
50 MiB 上限之内。也就是说"一篇一站"这条路今天是走通了的，不是推测。

三条实测结论，都是之前踩过或猜过的：

1. **中文文件名不是问题**——包里的图片名是中文，上传、验证、服务全部正常。
   上次 `sites_artifact_unsafe` 的原因就是 165 MB 的体积，不是名字。
2. **`publish_site` 会超时，但超时不是永久失败**：第一次失败在 `task_deadline_exceeded`；
   草稿保留、重新 `prepare_site` 验证通过之后再次 `publish_site`，拿到的是**新的 Operation id**
   并成功。所以失败后要重验草稿再发，而不是拿着那个已失败的 id 反复点
   （同一 action 上重复调用只会返回同一个失败 Operation）。
3. **发布 ≠ 可见**：`published: true` 之后 `curl` 仍然 401 `sites_gateway_login_required`，
   因为新站默认 `access_mode: private`。要别人打得开必须另外走 `update_access_policy`。

一条我自己犯过的错，写下来免得再犯：我一度以为"站点已设为 public"，实际那次改的是
**另一个站**（早先建的 `llm-crypto-notes` 草稿）。**多站并存时，改策略前必须核 siteId，
不能凭"我刚刚改过"的记忆**——`get_site` 一次调用就能证伪。

## 4. 发布形态：一组一个站，主页出本地版与线上版两个变体

限制有两条，一条量出来才知道另一条会咬人。**单包 50 MiB** 决定了"全站装一个站发不出去"
（09-25 实测：单篇 1.9–29.3 MB，全库 165.4 MB），于是先选了**一篇一站**；
跑满 19 篇之后咬人的是第二条——**`sites_total` 账号级 30 个站**，29 篇要 29 个站，加主页正好顶死。
现在的形状是**按类别合站**：图片入库时压到 400 KB（`memo.md` D-35）之后全库 **101.7 MB**，
29 篇装进 **13 个组站**，实测最大组 `ai-industry` **30.90 MB**，13 组 + 主页 = 14 个站，
距 30 的天花板腾出 16 个坑。主页出**两个变体、一份模板**：本地版 `output/index.html`
卡片链相对路径；线上版 `dist/home/index.html` 卡片链各篇的**深链**、封面内联成 base64
（主页站因此自包含，不依赖那 13 个组站在不在）。不做"一个页面 + CSS 开关"：
模式改变的不只是 href，而未发布的主题根本没有 URL，开关的另一半会是空链。

两件必须先钉住的事：

1. **文件名稳定了，会漂的是内容——所以要记"线上是哪一版"，不能只存一个 host。**
   W-145 之后产物叫 `<领域>.html`、不带日期，链接本身不再变化；
   会变的是内容：本地重渲染出新版本，线上还是上次发布的那一份。
   卡片上写着"在线看 ↗"，点进去是旧版且看不出是旧版。
   所以记 `{url, published_date, content_sha}`，卡片显示"在线看（09-24 版）"，
   本地比它新时这个差**必须可见**。
   合站之后这件事变成**两级**：`own_sha(篇)` 只覆盖这一篇自己的字节（组怎么重组它都不动），
   `group_sha(组)` 覆盖落地页 + Σ(成员 own_sha) + 组身份。只留一级就会出现
   "线上那组是旧的、每一篇都说自己新"的第三种状态，谁都不报警。
2. **一篇一站迟早撞站点总数配额**（`sites_total`）。这条 09-25 写下时还是预测，
   **10-03 撞实了**：第 29 篇建不出站（30/30），连带 hosted 主页因为"有一篇没地址"
   拒绝出片，主页冻在 24 卡（`memo.md` D-33）。退成"按类别合站"就是当时预留的那条路，
   代价是先解决 50 MiB 预算——靠图片入库压缩把全库从 190.5 MB 压到 101.7 MB（D-35）。

实现拆成"脚本能做的确定性部分"和"只有托管工具能做的那一步"：

- `scripts/publish.py pack <组>`：产出 `dist/<组>/` = 该组落地页 `index.html` + 每个成员一个
  `<slug>/` 目录（页面 + 页面真引用到的图 + 落地页要用的封面）。**逐字节搬，不改名、
  不压图、不重写 `src`**；超过工作上限 40 MiB 直接报错并说"这个组该分裂了"，绝不悄悄压图。
- Agent 对每个 `dist/<组>` 走第 3 节的工具顺序，拿回 `host`——**并且读回它**。
- `scripts/publish.py record-group <组> <组地址> --project-id <pid>`：把组身份写进
  `config/site_groups.json`，并把每个成员的 `data.json.site` 改成
  `{group, path, url=深链, project_id, content_sha, published_date, access}`，重生成 `web_list.md`。

URL 回写进产物而不是只记在脚本里，是为了让本地 `file://` 打开主页时卡片也能跳到线上版——记在 `data.json` 才跟着产物走。代价是索引卡片加一个可选字段＝改模板，按 `AGENTS.md` 第 5 步要全站重渲染。台账里是 **W-144**。

## 5. 现在实际怎么用（W-146 已落地）

发布是**半自动**，而且这是硬约束不是偷懒：托管工具只有 agent 能调
（`qodercli` 没有 sites 子命令，插件文档也没有 CI/REST 路径；
唯一能让纯脚本发布的路子是拿 PAT 逆向起那个 stdio MCP 服务——不做）。
所以链路切成"脚本能测的半边"和"要联网要授权的那半边"：

```bash
python scripts/publish.py playbook          # agent 的工作清单：按组给 projectId / webDirectory / 逐步参数
python scripts/publish.py pack watches      # 出组包 → dist/watches/（逐字节搬，不改名不压图）
python scripts/publish.py record-group watches https://watches-xxx.qoder.website/ \
       --project-id <pid> --access public --published-date 2026-10-04
python scripts/publish.py check             # 账实核对（G-14 用的就是这个）
python .probe/verify_live.py watches        # 上线验收：深链、每张图、字节等于包
```

- **`pack` 不改一个字节**：包里那份 HTML 和 `output/<领域>/<领域>.html` 逐字节相同。
  一旦允许改名/压图/重写 `src`，发出去的和闸门判过的就不是同一个东西。
- **超工作上限 40 MiB 直接报错退出，不悄悄压图**。要压得先让人看见"线上那份比验证过的差"。
  图片压缩只在**入库时**发生（`scripts/images.py` 的 `fit_bytes`），那里只有一份真相。
- **`web_list.md` 是派生物**，权威源是各篇 `data.json` 的 `site` 字段 + `config/site_groups.json`；
  它只能被 `record-group`/`ledger` 整体重生成，手改会被 **G-14** 判 fail。
- **`slug` 写在 `config/topics/<领域>.json` 里**，人写、不从中文名自动转写：
  地址一旦发布就改不掉（改名等于换 URL，读者手里的链接全废）。**组名同理，而且更硬**——
  它就是公开地址的前缀，平台限定 3–51 字符，短于此 `prepare_site` 会**静默**换成十六进制
  （`memo.md` D-37：`ai` 就这么变成过 `5d8a0008…`，而每条卡片链接从第一天起都是 404）。
- **`generate.py` 闸门全绿之后自动重算该篇所属组的包**，但只在内容指纹变化时——
  否则 AGENTS 第 5 步"改一次模板 29 篇全部 `--offline` 重渲染"会变成 29 次打包。
- 两级指纹都**不含 `generated_date`**（它每次重渲染都变，拿它当指纹等于让全部篇
  永远挂在待发布清单上）。

### 主页两个变体（W-147）

```bash
python scripts/build_index.py                       # 本地版 → output/index.html（链相对路径）
python scripts/build_index.py --variant hosted      # 线上版 → dist/home/index.html
python scripts/build_index.py --json --variant hosted
```

**`--json` 是「只打印条目、不渲染」**——计划书里我写的验证命令是
`--json --variant hosted`，照跑会得到 rc=0 却没有 `dist/home/index.html`，
看起来像已经出了线上版。要出文件必须不带 `--json`。19 篇全部记上地址之后实跑：
线上版 **12.93 MB**、19 张卡片全是 `https://`、19 张封面全是 `data:`、`<script>` 0 个、
相对链 0 条；本地版 20 KB，反向（19 张全相对链、0 条 https）。两版都零运行时 JS。

- 两个变体**同一份模板**：模板里卡片是 `href={e.href}`、封面是 `<img src={e.cover.file}>`，
  data URI 直接就能用，所以 Python 侧换 `href` 和 `cover.file` 就够了，**没有改模板**、
  也就不触发 AGENTS 第 5 步的全站重渲染。
- 线上版封面**内联成 base64**：主页站自己是一个站，卡片图若去引各篇文章站的 URL，
  任何一篇没发上去或挂了，主页就碎图。
  内联的是**卡片尺寸的缩略图**（`scripts/thumbs.py`，宽度上限 `quality_bar.index.card_cover_px`
  = 700，锚自真浏览器量到的 316–343 CSS px 框 × 2 倍屏）——不是原文那张 1472–2400 px。
  主页因此从 **9.9 MB 降到 2.7 MB**（W-185）。缩略图缓存住在 `dist/.thumbs/`，
  **按源图内容哈希命名**：按路径缓存会在换封面之后继续显示旧图，而旧图看起来完全正常。
  Pillow 缺位时退到原图并**在 stderr 喊一声**——静默退回 9.9 MB 等于没做这件事。
- 有一篇**声明在某个组里却没有自己的记录**，线上版直接报错退出（`NotPublished`），
  不悄悄把这张卡删掉——删掉的结果是一个看起来正常、少了几篇文章的主页。
  但**"还没分到组"不再冻住整张主页**（10-04 重新定范围，见 `memo.md` D-33 / D-34）：
  那种篇目跳过并大声报告，因为合站之后"某篇暂时没组"是迁移中的正常中间态，
  而一条防呆判据在第二种失败成因下会变成阻塞器。

### 一处我主动缩掉的范围（别当成已完成）

计划里写了"G-12 要加一条 hosted 分支去校验线上版主页"。**没做**，理由是：
`validate.py` 的全站段只看 `output/index.html`，要让 G-12 去判 `dist/home/index.html`
得先给闸门加一条"校验哪个文件"的通路，而今天线上版根本产不出来（没有任何已发布地址），
写那条分支等于给一个还没跑通过的产物加校验、还要为此改动闸门的调用约定。
线上版需要的三条不变性（每张卡都有 https 地址、封面是 data URI、零运行时 JS）
现在由 `tests/test_index.py` 的四条测试守——**测试守，不是闸门守**，这个区别要说清。
等第一篇真的发布出去、线上版有了真实数据，再决定要不要升格成闸门判据。

## 6. 还差什么

- **主页站已上线**：<https://knoweverything-gtqdc11h6po.qoder.website/>（20 张卡片全链各篇已发布站、封面内联 base64、13.4 MB 服务体积、零运行时 JS）。
  它上次失败在 `publish_site` 的 `task_deadline_exceeded`，重验草稿后拿到新 Operation 就成功了——
  **超时是可重试的，不是永久失败**。以后每次改模板或加篇，这个站要跟着重发一次。
- **G-12 的线上版分支没建**：`validate.py` 全站段只看 `output/index.html`。线上版主页的
  三条不变性（卡片全链已发布站点、封面是 `data:`、仍然零运行时 JS）现在**由测试守，
  不由闸门守**——这个区别要记住，改模板的人不会被闸门提醒。
- **可达性没有进闸门**：上面 21 个站的 200 是人手 `curl` 量的，不是 `validate --all` 判的。

一条已经落进代码的教训（值得单独记，因为它阴）：`publish.py record` 往 `data.json` 写
`site` 时，`topic_data.schema.json` 是 `additionalProperties: false`，**没同步加字段就被
G-10 判死整篇**——而 G-10 判死会让索引静默跳过它，看起来像"发布把页面弄坏了"。
写产物的代码和约束产物的契约必须同一次改。同一类问题还有第二个：账本 `web_list.md` 与
`data.json` 由同一次错误生成时，`check` 会 happily 报"账实一致"——同源互校只能发现漂移，
发现不了一致的错，所以要有一条"这个值本身合不合结构"的检查（`record` 现在校验主机名
必须由该篇 slug 派生）。
