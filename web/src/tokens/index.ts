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
