/**
 * 主题 token：每个领域一套。
 *
 * 设计约束（见 memo.md D-03 与 frontend-design 的反默认清单）：
 *  - 10 页共享版式骨架与信息装置，但**不**共享配色与字形；
 *  - 主动避开"奶油底 #F4F1EA + 高对比衬线 + 陶土橙点缀"与"近黑底 + 单一荧光强调色"这两族 AI 默认皮；
 *  - validate.py 会比较任意两页的 [bg, primary, accent] 色板签名，差异不足即判 fail。
 *
 * 加新领域＝在这里加一条，并在 config/topics/<领域>.json 的 theme.token 指过来。
 */
export interface ThemeTokens {
  id: string;
  label: string;
  bg: string;
  surface: string;
  ink: string;
  muted: string;
  rule: string;
  primary: string;
  accent: string;
  soft: string;
  /** 标题字族：领域性格主要靠这一项区分 */
  displayFamily: string;
  /** 正文字族 */
  bodyFamily: string;
  /** 数字/表格字族 */
  numFamily: string;
  heroMotif: string;
  /** 章节标题是否使用序号（只有真序列领域才开） */
  numberedSections: boolean;
}

const SANS =
  "'PingFang SC','Hiragino Sans GB','Microsoft YaHei','Source Han Sans SC','Noto Sans SC',system-ui,sans-serif";
const SERIF =
  "'Songti SC','Noto Serif SC','Source Han Serif SC','SimSun',Georgia,'Times New Roman',serif";
const MONO = "'SFMono-Regular','Cascadia Mono',Consolas,'Courier New',monospace";

export const THEMES: Record<string, ThemeTokens> = {
  "coffee-roast": {
    id: "coffee-roast",
    label: "咖啡 · 烘焙色带",
    bg: "#FFFFFF",
    surface: "#F7F6F4",
    ink: "#1B1715",
    muted: "#6E6560",
    rule: "#E3DED9",
    primary: "#4A2C17",
    accent: "#1E6B52",
    soft: "#F2E4D0",
    displayFamily: SANS,
    bodyFamily: SANS,
    numFamily: MONO,
    heroMotif: "roast_axis",
    numberedSections: false,
  },
  "chanel-noir": {
    id: "chanel-noir",
    label: "香奈儿 · 黑白与金扣",
    bg: "#FAFAF9",
    surface: "#FFFFFF",
    ink: "#0B0B0C",
    muted: "#75726E",
    rule: "#D8D5D0",
    primary: "#0B0B0C",
    accent: "#B8A15A",
    soft: "#EFEEEA",
    displayFamily: SERIF,
    bodyFamily: SANS,
    numFamily: MONO,
    heroMotif: "chain_and_camellia",
    numberedSections: false,
  },
  "hermes-orange": {
    id: "hermes-orange",
    label: "爱马仕 · 橙盒与马鞍针",
    bg: "#FFFDFB",
    surface: "#F6EFE6",
    ink: "#2A1A10",
    muted: "#7A6857",
    rule: "#E6D8C6",
    primary: "#E1610F",
    accent: "#7C4A23",
    soft: "#FBE7D2",
    displayFamily: SANS,
    bodyFamily: SANS,
    numFamily: MONO,
    heroMotif: "saddle_stitch",
    numberedSections: false,
  },
  "patek-calatrava": {
    id: "patek-calatrava",
    label: "百达翡丽 · 墨绿与旧金",
    bg: "#0E1F19",
    surface: "#162922",
    ink: "#EDEAE3",
    muted: "#9DAAA2",
    rule: "#2A4038",
    primary: "#C6A15B",
    accent: "#6FA88C",
    soft: "#1D352C",
    displayFamily: SERIF,
    bodyFamily: SANS,
    numFamily: MONO,
    heroMotif: "calatrava_cross",
    numberedSections: false,
  },
  "jaeger-reverso": {
    id: "jaeger-reverso",
    label: "积家 · 钢蓝与矩形",
    bg: "#EDF1F5",
    surface: "#FFFFFF",
    ink: "#16222E",
    muted: "#5D6E7E",
    rule: "#CFD9E2",
    primary: "#1F3A5F",
    accent: "#4B7FA6",
    soft: "#DCE7F0",
    displayFamily: SANS,
    bodyFamily: SANS,
    numFamily: MONO,
    heroMotif: "reverso_flip",
    numberedSections: false,
  },
  "rolex-oyster": {
    id: "rolex-oyster",
    label: "劳力士 · 冠绿与钢",
    bg: "#F5F7F6",
    surface: "#FFFFFF",
    ink: "#10201A",
    muted: "#5E6E66",
    rule: "#D2DCD6",
    primary: "#0F6B3D",
    accent: "#A9B0B6",
    soft: "#DFF0E5",
    displayFamily: SANS,
    bodyFamily: SANS,
    numFamily: MONO,
    heroMotif: "crown_and_bezel",
    numberedSections: true,
  },
  "lv-monogram": {
    id: "lv-monogram",
    label: "LV · 焦糖花纹与橄榄帆布",
    bg: "#FCFBF9",
    surface: "#F1EAE0",
    ink: "#231A12",
    muted: "#6E6055",
    rule: "#DCD2C4",
    primary: "#6E5A38",
    accent: "#C08A4E",
    soft: "#F5E9D8",
    displayFamily: SANS,
    bodyFamily: SANS,
    numFamily: MONO,
    heroMotif: "monogram_tile",
    numberedSections: false,
  },
  "longines-winged": {
    id: "longines-winged",
    label: "浪琴 · 银灰与飞翼红",
    bg: "#F4F5F7",
    surface: "#FFFFFF",
    ink: "#1E2429",
    muted: "#646E77",
    rule: "#D5DAE0",
    primary: "#4A5A6A",
    accent: "#C8102E",
    soft: "#E4E9EF",
    displayFamily: SANS,
    bodyFamily: SANS,
    numFamily: MONO,
    heroMotif: "winged_hourglass",
    numberedSections: false,
  },
  "bentley-racing": {
    id: "bentley-racing",
    label: "宾利 · 赛车绿与酒红",
    bg: "#F1F3F1",
    surface: "#FFFFFF",
    ink: "#131C17",
    muted: "#5A6760",
    rule: "#CED7D0",
    primary: "#0B3B24",
    accent: "#7E1F2C",
    soft: "#DDE8E0",
    displayFamily: SERIF,
    bodyFamily: SANS,
    numFamily: MONO,
    heroMotif: "matrix_grille",
    numberedSections: true,
  },
  "rolls-argenteal": {
    id: "rolls-argenteal",
    label: "劳斯莱斯 · 星银与午夜蓝",
    bg: "#12172B",
    surface: "#1A2038",
    ink: "#E8ECF3",
    muted: "#98A2BC",
    rule: "#2C3552",
    primary: "#C7CDD6",
    accent: "#7C8CB0",
    soft: "#212A48",
    displayFamily: SERIF,
    bodyFamily: SANS,
    numFamily: MONO,
    heroMotif: "starlight_headliner",
    numberedSections: false,
  },
  "guerlain-abeille": {
    id: "guerlain-abeille",
    label: "娇兰 · 蜂后紫与釉金",
    bg: "#FCFBFD",
    surface: "#F5F1F7",
    ink: "#221A28",
    muted: "#6E6172",
    rule: "#E6DEEA",
    primary: "#4B2A5B",
    accent: "#C9A227",
    soft: "#F0E7F3",
    displayFamily: SERIF,
    bodyFamily: SANS,
    numFamily: MONO,
    heroMotif: "bee_comb_axis",
    numberedSections: false,
  },
  "llm-attention": {
    id: "llm-attention",
    label: "大模型 · 品红与孔雀绿",
    bg: "#FBFAF9",
    surface: "#F3F1EF",
    ink: "#1C1A1E",
    muted: "#6B6670",
    rule: "#E2DEE4",
    primary: "#B5177E",
    accent: "#2A9D8F",
    soft: "#F6E7F1",
    displayFamily: SERIF,
    bodyFamily: SANS,
    numFamily: MONO,
    heroMotif: "attention_matrix",
    numberedSections: false,
  },
  "muse-industry": {
    /* Muse 的产业逻辑篇：酒红是资本与报表的颜色，电光黄绿是数据与信号。
       主色离娇兰 22.1（14 套里已经很难再找到更开的暗色位），
       但强调色离最近的一套 44.4、离所有主色 57.5——G-11 判双胞胎要两道同时 <25。 */
    id: "muse-industry",
    label: "Muse 产业逻辑 · 酒红与电光黄绿",
    bg: "#FAF8F8",
    surface: "#F2EDED",
    ink: "#2A1620",
    muted: "#7A6470",
    rule: "#E3D8DD",
    primary: "#502B3A",
    accent: "#A8D60C",
    soft: "#EFE8C4",
    displayFamily: SERIF,
    bodyFamily: SANS,
    numFamily: MONO,
    heroMotif: "stack_layers",
    numberedSections: false,
  },
  "muse-sandbox": {
    /* Meta Muse / 云电脑：深青是机房与终端的颜色，亮橙是"这一格正在跑"的指示灯。
       与浪琴（#4A5A6A/#C8102E）最近，primary ΔE 23.9、accent ΔE 36.8——
       两道都过 25 才敢用，只过一道就是双胞胎（G-11）。 */
    id: "muse-sandbox",
    label: "Muse · 深青与信号橙",
    bg: "#F6F9F9",
    surface: "#EDF3F4",
    ink: "#14262B",
    muted: "#5C7278",
    rule: "#D2E0E2",
    primary: "#0A6E6E",
    accent: "#FF8A00",
    soft: "#DCEEF0",
    displayFamily: MONO,
    bodyFamily: SANS,
    numFamily: MONO,
    heroMotif: "sandbox_rack",
    numberedSections: false,
  },
  "glasses-waveguide": {
    id: "glasses-waveguide",
    label: "AI 眼镜 · 激光蓝与电光紫",
    bg: "#FAFBFC",
    surface: "#EEF1F6",
    ink: "#12161F",
    muted: "#5E6672",
    rule: "#DDE3EC",
    primary: "#1466C8",
    accent: "#6B2CF5",
    soft: "#E6EEFB",
    displayFamily: SANS,
    bodyFamily: SANS,
    numFamily: MONO,
    heroMotif: "waveguide_rainbow",
    numberedSections: false,
  },
  "mlcc-ceramic": {
    /* MLCC 篇：砖红是烧结后的陶瓷介质体，钢蓝灰是里面的镍内电极与外面的锡端头。
       身份色离最近的一套 34.6（coffee-roast），两道都拉开了。
       四个文字色在瓷白底上全部 ≥4.5:1（ink 15.1 / muted 5.6 / primary 6.3 / accent 5.4）。 */
    id: "mlcc-ceramic",
    label: "MLCC · 烧结砖红与镍电极钢蓝",
    bg: "#FBF9F7",
    surface: "#F2EAE4",
    ink: "#2B201A",
    muted: "#6E625B",
    rule: "#E6D9D1",
    primary: "#9C3F27",
    accent: "#4E6B7A",
    soft: "#E7DFD4",
    displayFamily: SERIF,
    bodyFamily: SANS,
    numFamily: MONO,
    heroMotif: "interleaved_electrodes",
    numberedSections: false,
  },
  "indigo-coral": {
    /* AI制药篇：靛蓝是实验服与试剂瓶里的深蓝，珊瑚橙是活体染色与警示。
       色板已经饱和——17 套之后任何深色主色离现有主色都很近，所以这套靠**强调色**拉开：
       实测主色离最近的一套 18.4、强调色离最近的 28.8。G-11 要两道同时 <25 才判双胞胎，
       这里强调色那道远在线上，通过。真正的差异化交给记忆点：漏斗＝本篇的论点本身。 */
    id: "indigo-coral",
    label: "AI制药 · 靛蓝与珊瑚橙",
    bg: "#F7F6F3",
    surface: "#E8EAF1",
    ink: "#1A1C22",
    muted: "#5E626E",
    rule: "#D8DBE4",
    primary: "#3D4E8C",
    accent: "#C24E1E",
    soft: "#DFE3EF",
    displayFamily: SERIF,
    bodyFamily: SANS,
    numFamily: MONO,
    heroMotif: "hypothesis_funnel",
    numberedSections: false,
  },
  "graphite-ultramarine": {
    /* 大模型与加密货币篇：石墨黑是账本与矿机的金属灰，群青蓝是密码学的传统色
       （也是"蓝队"的蓝）。色板到 18 套已经饱和——主色离最近的一套只有 12.2，
       靠主色拉开是不可能的，所以这套把力气全放在强调色上：群青 #1F3193
       离所有现有强调色 53.0（最远的候选，用网格搜出来的，不是挑的）。
       G-11 判双胞胎要两道同时 <25，这里强调色那道远在天上，通过。
       四个文字色在纸上底色上全部 >=4.5:1（ink 16.6 / muted 5.6 / primary 14.1 / accent 10.0）。
       真正的差异化交给记忆点：无限层联立——那才是两个团队共同站在上面的东西。 */
    id: "graphite-ultramarine",
    label: "大模型与加密货币 · 石墨与群青",
    bg: "#F6F5F2",
    surface: "#E9E8E3",
    ink: "#141619",
    muted: "#5E626E",
    rule: "#DCDAD3",
    primary: "#22252B",
    accent: "#1F3193",
    soft: "#DDE2F0",
    displayFamily: SERIF,
    bodyFamily: SANS,
    numFamily: MONO,
    heroMotif: "layer_cascade",
    numberedSections: false,
  },
  "snapdragon-obsidian": {
    /* 骁龙笔电篇：曜石靛是芯片封装与深夜屏幕的颜色，电光品红是 NPU/信号。
       色彩已经饱和了——量过 16 套之后，任何深色主色离积家的钢蓝都只有 13~18，
       所以这套靠**强调色**拉开：品红离所有现有强调色 57.7（最近的宾利酒红）。
       G-11 判双胞胎要两道同时 <25，这里主色那道近、强调色那道很远，通过。
       真正的差异化交给字形与记忆点，不硬撑"整组颜色都前无古人"。 */
    id: "snapdragon-obsidian",
    label: "骁龙笔电 · 曜石靛与电光品红",
    bg: "#FAFAFC",
    surface: "#ECEEF4",
    ink: "#141619",
    muted: "#646B78",
    rule: "#DFE3EA",
    primary: "#101A33",
    accent: "#BD0598",
    soft: "#DDE4F0",
    displayFamily: SANS,
    bodyFamily: SANS,
    numFamily: MONO,
    heroMotif: "perf_per_watt",
    numberedSections: false,
  },
  "shelf-vermilion": {
    /* 名创 × 泡泡玛特篇：深货架绿是便利店冷白灯下的一排排货架，
       盲盒黄是那一片格子里被点亮的一格——两家的差别就在这两个字上：
       一边是每一格都长一样（护城河=可复制），一边是哪一格亮不可预知（定价权=稀缺）。
       量过 19 套之后的真实位置：最近的一套是 Muse 沙盘（primary ΔE 24.0、accent ΔE 30.4），
       两道里有一道拉开了，G-11 因此通过——但别把这套读成"颜色和 Muse 有别"，
       真正的区分在字形与记忆点（货架 + 盲盒格），颜色只是不撞。 */
    id: "shelf-vermilion",
    label: "名创 × 泡泡玛特 · 货架绿与盲盒黄",
    bg: "#FAF8F2",
    surface: "#EFEAE0",
    ink: "#161C19",
    muted: "#5F6A63",
    rule: "#DBD5C6",
    primary: "#123B2E",
    accent: "#F2B705",
    soft: "#E4EBE4",
    displayFamily: SANS,
    bodyFamily: SANS,
    numFamily: MONO,
    heroMotif: "shelf_vs_blindbox",
    numberedSections: false,
  },
  "petrol-amber": {
    /* Claude Opus 5.5 篇：深 petrol 是机房夜里的那点蓝绿，琥珀是负载表上发亮的格子。
       选色时踩到一个更硬的事实：现有 20 套里**找不到两条腿都离得远的组合**——
       量过之后最好的这套也只做到 min ΔE 13.7（最近的是浪琴的钢蓝主色）。
       G-11 只拦"两条腿都 <25"，所以它放得过"主色几乎一样、只换强调色"的撞脸；
       我不拿这个当许可：真正的区分交给记忆点（思考预算那条横杠）与字形。
       与名创篇的货架绿：主色 ΔE 23.1（同一色系，G-11 不拦这种），
       但强调色琥珀与盲盒黄差到 32.2，加上记忆点完全不同，两页不会被认成同一个牌子。 */
    id: "petrol-amber",
    label: "Claude Opus 5.5 · 机房蓝绿与琥珀",
    bg: "#F5F8F9",
    surface: "#E7EEF1",
    ink: "#131A1E",
    muted: "#5C6B72",
    rule: "#D6E1E6",
    primary: "#124559",
    accent: "#F2A65A",
    soft: "#DCE9EE",
    displayFamily: SANS,
    bodyFamily: SANS,
    numFamily: MONO,
    heroMotif: "thinking_budget",
    numberedSections: false,
  },
  "ballot-navy": {
    /* 美国中期选举篇：选战深蓝与票绿。两色**不指定哪边是哪个党**——
       记忆点画的是"多数门槛线"，不是阵营归属（红线 R-09：不写哪一党更好）。
       配色是量出来的：21 套现有主题里，这套的 G-11 裕度 47.2（最近的是香奈儿的墨黑），
       最紧的一条腿是 indigo-coral 的主色（ΔE 12.7，同为深蓝）——
       但它的强调色是橙，两页不会读成同一个牌子。 */
    id: "ballot-navy",
    label: "中期选举 · 选战深蓝与票绿",
    bg: "#F7F8FB",
    surface: "#EBEEF6",
    ink: "#12161F",
    muted: "#5A6274",
    rule: "#DCE0EA",
    primary: "#16326B",
    accent: "#3FA34D",
    soft: "#E1EBE2",
    displayFamily: SERIF,
    bodyFamily: SANS,
    numFamily: MONO,
    heroMotif: "majority_line",
    numberedSections: false,
  },
  "jev-choice": {
    /* Jev 篇：橄榄绿与紫。这一对是量出来的，不是挑出来的——
       22 套既有主题把黄绿（娇兰金、muse 的青柠）与紫（glasses、snapdragon 的洋红）
       各自占了一条腿，但**没有一套同时占住"暗橄榄 + 中紫"**这一格。
       实测：与每一套既有主题比，primary 与 accent 不会两条腿同时靠近
       （单腿最小 ΔE 24.4，出现在 primary 腿；那一套的 accent 腿相距 >25，
       G-11 要两条腿都近才判雷同）。
       为什么是橄榄而不是草绿：这篇讲的是"封闭选项里点亮一条"，
       底色要沉、点亮色要能当唯一的高亮，紫比红更不像警告色。 */
    id: "jev-choice",
    label: "Jev · 橄榄与紫",
    bg: "#F7F8F3",
    surface: "#ECEFE3",
    ink: "#1A1E14",
    muted: "#5C6353",
    rule: "#DCE0D1",
    primary: "#526F20",
    accent: "#872BB6",
    soft: "#E6EBD8",
    displayFamily: SERIF,
    bodyFamily: SANS,
    numFamily: MONO,
    heroMotif: "choice_bars",
    numberedSections: false,
  },
  "morgan-split": {
    /* 摩根篇：克拉特红与湖蓝。这对颜色是量出来的，而且**第一版是错的**——
       我先按"墨绿+酒红"选了一组，只报了每条腿的最近距离（primary 11.6、accent 8.4），
       看着很开。但 G-11 的判据是**每一对主题取两条腿里较远的那条**
       （max(pr,ac) < 25 才 fail），按真实判据重算，那组和 bentley-racing 只有 20.1，
       会把宾利那篇判成雷同。现在这组：与 23 套里最近的一对是 mlcc-ceramic，max ΔE 36.5。
       为什么是红配蓝：这篇讲的是"同一条家族干断成两条腿"。干（血亲时代）和
       小摩（继承了章程与名字的那条）共用克拉特红；大摩是 1935 年带新资本
       另起的一条腿，只有它是蓝。红色不是"摩根的招牌色"——两家今天的标志都是蓝——
       红是**家族**的颜色，蓝是**分家之后**的颜色，记忆点上正好一红一蓝。 */
    id: "morgan-split",
    label: "摩根 · 克拉特与湖蓝",
    bg: "#F7F7F5",
    surface: "#EDEEEA",
    ink: "#1C1F22",
    muted: "#5F6469",
    rule: "#DCE0DE",
    primary: "#4A0E1B",
    accent: "#0F8FB8",
    soft: "#E9DFDD",
    displayFamily: SERIF,
    bodyFamily: SANS,
    numFamily: MONO,
    heroMotif: "morgan_split",
    /* 三代人 + 1933/1935 两道口子，是这一篇唯一的真序列，序号给它。 */
    numberedSections: true,
  },
  "agent-terminal": {
    /* W-171 教学篇《从零做一个 Agent 对话聊天框》。
       这对颜色同样是量出来的，用的判据是 G-11 的真实判据——每一对主题取
       两条腿里**较远**的那条（max(pr,ac) < 25 才判雷同），不是单腿最近距离（T-115）。
       24 套里与它最近的一对是 graphite-ultramarine，max ΔE = 41.0，
       第二近 44.5（rolex-oyster）。
       为什么是终端绿配钢蓝：绿是**说话的那一方**（模型吐字、光标在闪），
       蓝是**被调用的那一方**（tool、数据库、后端 service）。
       这篇通篇就在讲这两件事的分界，所以记忆点也照这个分：上条绿、下条蓝。 */
    id: "agent-terminal",
    label: "Agent 开发 · 终端绿与钢蓝",
    bg: "#F5F7F3",
    surface: "#EAEFE8",
    ink: "#181D19",
    muted: "#5B6660",
    rule: "#D7DED6",
    primary: "#0F5D3C",
    accent: "#33507A",
    soft: "#DDE8DF",
    displayFamily: SANS,
    bodyFamily: SANS,
    numFamily: MONO,
    heroMotif: "turn_caret",
    numberedSections: true,
  },
  "ust-yieldcurve": {
    /* W-172 美债 7% 情景篇。配色按 G-11 的真实判据（max(pr,ac) >= 25）在 25 套里量：
       最近的一对是 longines-winged，max ΔE = 35.7；第二近 bentley-racing 36.2。
       为什么不选更"像国债"的深蓝配铜黄：那两组与 petrol-amber / indigo-coral
       分别只剩 18.9 / 21.2，会被判雷同。
       铁蓝是**债**，酒红是**倒挂**：这篇的异常不在利率高低，而在曲线形状变，
       所以两条线一蓝一红，红色只出现在短端高于长端的那一段。 */
    id: "ust-yieldcurve",
    label: "美债 · 铁蓝与倒挂红",
    bg: "#F4F6F8",
    surface: "#E9EEF3",
    ink: "#1A2027",
    muted: "#5A6672",
    rule: "#D5DDE5",
    primary: "#26415C",
    accent: "#8E2C42",
    soft: "#E1E7EE",
    displayFamily: SERIF,
    bodyFamily: SANS,
    numFamily: MONO,
    heroMotif: "curve_invert",
    /* 六类资产的传导没有先后，序号不开。 */
    numberedSections: false,
  },
  "cerebras-wafer": {
    /* W-173 Cerebras 篇。配色按 G-11 的真实判据（max(pr,ac) >= 25）在 26 套里量：
       最近的一对是 graphite-ultramarine，max ΔE = 40.7，第二近 jev-choice 42.7。
       为什么是硅青配锆紫：抛光的硅片在氧化层薄膜干涉下就是这个颜色——
       青里泛紫，是**晶圆本身的颜色**，不是哪家公司的品牌色。
       青是"未切割的那一片"，紫是"切割线"：这一篇的技术与商业分野
       全在那道线落没落下，所以记忆点也照这个分色。 */
    id: "cerebras-wafer",
    label: "Cerebras · 硅青与锆紫",
    bg: "#F6F7F5",
    surface: "#EAEFEC",
    ink: "#171C1B",
    muted: "#5A6663",
    rule: "#D6DEDA",
    primary: "#17756E",
    accent: "#6B2E8E",
    soft: "#DFE7E4",
    displayFamily: SANS,
    bodyFamily: SANS,
    numFamily: MONO,
    heroMotif: "wafer_grid",
    /* 这篇是"从技术到报表到估值"的递进，但各章之间不是硬序列，序号不开。 */
    numberedSections: false,
  },
  "open-weight-collision": {
    /* W-173 拆出来的下半篇（开发者裁决：R-05 的 8500 不动，长内容拆两篇）。
       配色按 G-11 的真实判据（max(pr,ac) >= 25）在 28 套里量：最近的一对是
       indigo-coral，max ΔE = 30.8，第二近 ust-yieldcurve。
       为什么不是先想的那组"群青+锶黄"：#C9A227 与 guerlain-abeille 的强调色
       **是同一个十六进制值**（ΔE=0.0）。按判据它照样能过（primary 够远），
       但两篇在入口页上会挂着同一块金子——判据漏的是"跨腿相同色"这一类，
       所以这里自己加一条：不许复用另一套已经在用的十六进制值。
       群青是开源权重那一层（公共、不要钱），焦褐是资本开支那一层（金属、机房、
       折旧）：这一篇问的就是前者撞后者能撞出什么价。 */
    id: "open-weight-collision",
    label: "开源权重与算力估值 · 群青与焦褐",
    bg: "#F5F6F9",
    surface: "#E9ECF3",
    ink: "#161A22",
    muted: "#5C6472",
    rule: "#D7DCE6",
    primary: "#1B3A8C",
    accent: "#9A5B3F",
    soft: "#E0E5EF",
    displayFamily: SANS,
    bodyFamily: SANS,
    numFamily: MONO,
    heroMotif: "rent_shift",
    numberedSections: false,
  },
  "rate-spillover": {
    /* 拆出来的下半篇（开发者裁决：R-05 的 8500 不动，长内容拆两篇）。
       配色按 G-11 的真实判据在 27 套里量：最近的一对是 patek-calatrava，max ΔE = 36.7，
       第二近 rolex-oyster 44.5。
       为什么先试的三组都被否：砖橙、赤铜、陶土配深青，全部与 mlcc-ceramic 只剩
       12.6~15.6——那套本来就是"烧结砖红配镍电极蓝"，暖棕配冷青这条路已经被它占了。
       深芥是**预警色**（利率撞到东西的那一下），湖蓝是**流动性本身**：
       这一篇讲的就是一条线分叉去撞四个地方。 */
    id: "rate-spillover",
    label: "利率外溢 · 深芥与湖蓝",
    bg: "#F7F6F1",
    surface: "#EDEBE1",
    ink: "#1D1D17",
    muted: "#615F52",
    rule: "#DDD9C9",
    primary: "#8A8421",
    accent: "#155E6B",
    soft: "#E9E6D2",
    displayFamily: SERIF,
    bodyFamily: SANS,
    numFamily: MONO,
    heroMotif: "spillover_fan",
    /* 四条传导路径没有先后，序号不开。 */
    numberedSections: false,
  },
  "silicon-copper": {
    /* 本地大模型芯片篇。这套是按 G-11 的真实判据在 29 套里搜出来的：
       判据要 primary 与 accent **两个都近**才算雷同，所以安全边际取的是
       「对每个既有主题，两个身份色里较远那一个」的最小值。
       实测最深的那对是 Δ=41.4（vs lv-monogram 的 #6E5A38/#C08A4E 那一族暖棕），
       全站 29 套里违规对数 0；比它远的「深林绿/磷光绿」有 66.4，但磷光绿配纸白
       读起来是终端而不是评测页，宁可让边际小一点也要留住"器件"的味道。
       深硅绿是 PCB 与晶圆的那层绿，铜橙是封装、导线与散热鳍——这一篇讲的是
       内存带宽与功耗，颜色该来自器件本身，不该来自厂商 PPT。
       字形按原样给（这一篇的数字密度高于任何一篇：tokens/s、GB/s、W、¥ 四列并排）。 */
    id: "silicon-copper",
    label: "本地大模型芯片 · 硅绿与铜橙",
    bg: "#F2F4F1",
    surface: "#E6EAE6",
    ink: "#171A17",
    muted: "#5E6660",
    rule: "#D5DBD6",
    primary: "#125912",
    accent: "#C87137",
    soft: "#DFE9DC",
    displayFamily: SANS,
    bodyFamily: SANS,
    numFamily: MONO,
    heroMotif: "bandwidth_neck",
    /* 三家没有先后，序号不开。 */
    numberedSections: false,
  },
};

export function themeOf(token: string | undefined): ThemeTokens {
  const t = token && THEMES[token];
  if (!t) {
    throw new Error(
      `未知主题 token "${token}"。可用：${Object.keys(THEMES).join(", ")}。` +
        `新领域请在 web/src/tokens/index.ts 增加一套 token。`,
    );
  }
  return t;
}
