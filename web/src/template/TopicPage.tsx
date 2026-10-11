import type { ReactNode } from "react";
import { themeOf } from "../tokens";
import type { PageImage, TopicData } from "../types";
import { renderBlock, type SrcIndex } from "./renderers";
import { cssFor } from "./styles";

/** 每页唯一的"记忆点"。只在此处集中花视觉预算，其余版面保持安静。 */
function Motif({ token }: { token?: string }) {
  if (token === "roast_axis") {
    const shades = ["#C9A227", "#B07D3A", "#8A5230", "#5C3220", "#2E1A14"];
    return (
      <div className="motif" aria-hidden="true">
        <div className="motif-roast">
          {shades.map((c) => (
            <i key={c} style={{ background: c }} />
          ))}
        </div>
        <div className="motif-label">
          <span>浅焙 · 果酸</span>
          <span>中焙 · 平衡</span>
          <span>深焙 · 焦糖苦</span>
        </div>
      </div>
    );
  }
  if (token === "starlight_headliner" || token === "calatrava_cross" || token === "matrix_grille") {
    return (
      <div className="motif motif-dots" aria-hidden="true">
        {Array.from({ length: 46 }).map((_, i) => (
          <i
            key={i}
            style={{
              left: `${(i * 37) % 100}%`,
              top: `${(i * 53) % 100}%`,
              opacity: 0.25 + ((i * 7) % 60) / 100,
            }}
          />
        ))}
      </div>
    );
  }
  if (token === "reverso_flip" || token === "monogram_tile" || token === "chain_and_camellia") {
    return (
      <div className="motif motif-tiles" aria-hidden="true">
        {Array.from({ length: 12 }).map((_, i) => (
          <i key={i} />
        ))}
      </div>
    );
  }
  if (token === "bee_comb_axis") {
    /* 娇兰：蜂巢六边形 + 几格金，取"皇家蜜蜂瓶"与"格拉斯田间"同一意象。
       格子要够多才能在没有封面的大色块里铺成几行——只有 14 格时它缩在左上角，
       看上去像两个黄点（截图自查发现）。 */
    return (
      <div className="motif motif-comb" aria-hidden="true">
        {Array.from({ length: 44 }).map((_, i) => (
          <i key={i} className={i === 3 || i === 14 || i === 26 || i === 39 ? "gold" : ""} />
        ))}
      </div>
    );
  }
  if (token === "waveguide_rainbow") {
    /* AI 眼镜：光波导。光从左边耦进一块几毫米厚的玻璃，靠全反射往前传，
       每经过一段耦出栅就漏出一丝——所以是一排向右逐渐变亮的竖条，
       最后三格才出射成蓝、紫、青：那才是全彩画面真正离开镜片的瞬间。 */
    return (
      <div className="motif motif-guide" aria-hidden="true">
        {Array.from({ length: 36 }).map((_, i) => (
          <i
            key={i}
            className={i >= 33 ? (i % 2 ? "hot" : "hot alt") : ""}
            style={{ opacity: 0.1 + (i / 35) * 0.55 }}
          />
        ))}
      </div>
    );
  }
  if (token === "stack_layers") {
    /* 产业逻辑篇：一次 agent 调用真正穿过的五层——模型、编排、执行、网络出口、算力与机房。
       越往下越厚、越贵、越像生意；「执行层」用强调色，因为这一篇的全部争论都在这一层。
       宽度不是装饰：它按「这层吃掉多少成本」给，所以读图就是在读价值链。 */
    const layers = [
      { w: 42, hot: false },
      { w: 56, hot: false },
      { w: 74, hot: true },
      { w: 86, hot: false },
      { w: 100, hot: false },
    ];
    return (
      <div className="motif motif-stack" aria-hidden="true">
        {layers.map((l, i) => (
          <i key={i} className={l.hot ? "hot" : ""} style={{ width: l.w + "%" }} />
        ))}
      </div>
    );
  }
  if (token === "majority_line") {
    /* 中期选举篇：25 格席位，中间那道线是多数门槛。
       资产关心的从来不是"谁票多"，而是**哪一院跨过那条线、跨过多格**——
       所以线比颜色重要。两色不指定阵营（红线 R-09：不写哪一党更好），
       格子上也不标任何席位数字：席位是随时点变的量化断言，带来源地活在正文里（R-02）。 */
    return (
      <div className="motif motif-seats" aria-hidden="true">
        {Array.from({ length: 25 }).map((_, i) => (
          <i key={i} className={(i < 12 ? "a" : "b") + (i === 12 ? " line" : "")} />
        ))}
      </div>
    );
  }
  if (token === "thinking_budget") {
    /* Claude Opus 5.5 篇：一条横杠就是同一道题的推理预算。左边三格是「立刻答」，
       右边二十一格是「先想清楚再答」——这一版真正的差别不在模型更大，
       而在预算被允许花在哪，所以能力数字必须先问"这次给了多少思考预算"。
       格子上不标任何数值（R-02）：标了它就是一张没有来源的图表。 */
    return (
      <div className="motif motif-budget" aria-hidden="true">
        {Array.from({ length: 24 }).map((_, i) => (
          <i
            key={i}
            className={i < 3 ? "quick" : "think"}
            style={{ opacity: i < 3 ? 0.3 : 0.5 + (i - 3) * 0.02 }}
          />
        ))}
      </div>
    );
  }
  if (token === "shelf_vs_blindbox") {
    /* 名创 × 泡泡玛特：左边三排货架——每一格都和隔壁那格一样，这是性价比零售的护城河
       （可复制、可预期、赚周转）；右边二十格盲盒，其中三格亮着，哪一格亮事先不知道，
       这是潮玩的定价权（稀缺、抽中、不可预期）。两半共用同一条基线：它们是同一场消费
       的两侧，不是两个行业。格子上不标任何数值——标了就成了没有来源的图表（R-02）。 */
    return (
      <div className="motif motif-duel" aria-hidden="true">
        <div className="motif-duel-shelf">
          {Array.from({ length: 9 }).map((_, i) => (
            <i key={i} />
          ))}
        </div>
        <div className="motif-duel-boxes">
          {Array.from({ length: 20 }).map((_, i) => (
            <i key={i} className={i === 4 || i === 11 || i === 17 ? "lit" : ""} />
          ))}
        </div>
      </div>
    );
  }
  if (token === "perf_per_watt") {
    /* 骁龙篇：横轴性能、纵轴功耗，亮点连起来就是那条等能效线——这条路的争论
       全在"每瓦"上，而不是任何一方的绝对峰值。
       格子上不标任何数值：一标数值它就成了一张没有来源的图表（R-02）。 */
    const cols = 6;
    const rows = 4;
    const cells = [];
    for (let r = 0; r < rows; r++) {
      for (let c = 0; c < cols; c++) {
        const diag = c === cols - 1 - r;
        cells.push(
          <i key={`${r}-${c}`} className={diag ? "hot" : (r + c) % 3 === 0 ? "near" : ""} />,
        );
      }
    }
    return (
      <div className="motif motif-ppw" aria-hidden="true">
        {cells}
      </div>
    );
  }
  if (token === "interleaved_electrodes") {
    /* MLCC 的横截面就是这张图：陶瓷介质层与镍内电极一层层叠起来，
       相邻两层电极分别朝两个端头引出——奇数条接顶、偶数条接底，
       交错才有电容，对齐了就是短路。所以记忆点不是装饰，是器件原理本身。
       强调色落在两条"接得上端头"的电极上，其余是介质层的暗条。 */
    const n = 22;
    return (
      <div className="motif motif-interleave" aria-hidden="true">
        {Array.from({ length: n }).map((_, i) => (
          <i key={i} className={(i % 2 ? "down" : "up") + (i === 7 || i === 14 ? " hot" : "")} />
        ))}
      </div>
    );
  }
  if (token === "layer_cascade") {
    /* 大模型与加密货币篇的记忆点：无限层联立（infinite cascade）。
       两个团队都不是凭空"想到"答案的——他们站在 Córdoba 与 Martínez-Zoroa 的
       解析方法上：造一列无穷多个各自无奇点的"层"，再把它们联立成一个新解，
       新解里才含奇点。所以这张图是**一层压一层、越往下越窄、收到一个点**，
       而不是链条或区块图：这一篇要反驳的恰恰是"算力堆得多就破解了"。
       强调色落在最后收口那一层——那是 AI 补上的唯一一步（让 forcing 也保持光滑）。
       不标层数、不标小时数：那些数字在正文里逐条带来源。 */
    const n = 11;
    return (
      <div className="motif motif-cascade" aria-hidden="true">
        {Array.from({ length: n }).map((_, i) => (
          <i key={i} className={i >= n - 2 ? "hot" : undefined}
             style={{ width: `${100 - i * (72 / n)}%` }} />
        ))}
      </div>
    );
  }
  if (token === "hypothesis_funnel") {
    /* AI制药篇的记忆点就是本篇的论点本身：假设生成那一段被 AI 压得很便宜，
       验证那一段一分没动，所以漏斗的最后一跳不是"算力不够"，是"人只来得及测一个"。
       实测那组数字是 20 万+ → 3,500 → 20 → 1，条宽按对数收（线性收会看不见末两格）。
       最后一格用强调色：它是唯一进了实验室的那个。
       和骁龙篇一样，这里一个数字都不标——标了它就成了一张没有来源的图表。 */
    const widths = [100, 58, 30, 13, 4];
    return (
      <div className="motif motif-funnel" aria-hidden="true">
        {widths.map((w, i) => (
          <i key={i} className={i === widths.length - 1 ? "hot" : undefined}
             style={{ width: w + "%" }} />
        ))}
      </div>
    );
  }
  if (token === "sandbox_rack") {
    /* Meta Muse：一个智能体一台沙箱。矩阵里每一格是一个几分钟拉起、用完即销毁的
       Linux 实例——绝大多数早就暗下去了，只有当下还在跑的几格亮着，
       其中个别是橙色（正在被调度起来的那几台）。
       格子必须够密：稀疏的网格在 1440 宽的封面里会糊成几条线，
       而"上万台"这件事本身就靠密度说话。 */
    return (
      <div className="motif motif-rack" aria-hidden="true">
        {Array.from({ length: 340 }).map((_, i) => {
          // 位混淆哈希，不是 `i % 13` 也不是线性同余：两者都会在固定列数的网格里
          // 排成对角线（1440 实测出一条橙色斜线，像 bug 不像"正在调度"）。
          // 也不能用 Math.random——SSR 每次必须渲染出同一份 HTML。
          let x = (i + 0x9e3779b9) | 0;
          x ^= x << 13;
          x ^= x >>> 17;
          x ^= x << 5;
          const h = Math.abs(x) % 100;
          return <i key={i} className={h < 5 ? "on alt" : h < 13 ? "on" : ""} />;
        })}
      </div>
    );
  }
  if (token === "attention_matrix") {
    /* 大模型：注意力方阵。第 i 个 token 最关心的是离它近的那几个，所以亮格沿一条
       来回扫的对角线排，其余按距离衰减——这是这套架构唯一"看得见"的样子。
       格子必须铺满整块：娇兰那版第一层只有 14 格，缩在角上像两个黄点，
       是截图自查才发现的（G-13 全绿也看不出）。 */
    const COLS = 12;
    const ROWS = 7;
    const cells: ReactNode[] = [];
    for (let r = 0; r < ROWS; r++) {
      // 真正的对角线：第 r 行的亮格落在 round(r·(COLS-1)/(ROWS-1))，
      // 从左上角走到右下角。(r*5)%COLS 那种步长会把亮格打成锯齿，
      // 看着像随机撒的，就不"注意力"了。
      const hot = Math.round((r * (COLS - 1)) / (ROWS - 1));
      for (let c = 0; c < COLS; c++) {
        const d = Math.abs(c - hot);
        cells.push(
          <i key={`${r}-${c}`} className={d === 0 ? "hot" : d === 1 ? "near" : ""} />,
        );
      }
    }
    return (
      <div className="motif motif-attn" aria-hidden="true">
        {cells}
      </div>
    );
  }
  if (token === "choice_bars") {
    /* 封闭选项上的概率条：候选由人给定，模型只点亮一条。
       这是 Jev 与自回归模型最直观的分界，所以拿它当这一篇的记忆点。 */
    const odds = [18, 92, 34, 12, 44, 8];
    return (
      <div className="motif motif-choice" aria-hidden="true">
        {odds.map((w, i) => (
          <i key={i} className={w > 80 ? "hot" : ""} style={{ width: `${w}%` }} />
        ))}
      </div>
    );
  }
  /* 记忆点是一轮对话：上面那条是模型在吐字（主色），下面那条是被它调用的
     tool / 数据库（强调色），右边实心方块是还在等的光标。
     为什么不画整个聊天窗口：hero 记忆点要的是"一眼认出这篇讲什么"，
     窗口边框、输入框这些外壳信息量为零，画了反而像通用模板。
     宽度比不是随手定的：绿条比蓝条长，因为一次回合里模型的话总比一次调用多；
     但**不代表任何比例数据**，图上也不写数字（D-22）。 */
  /* 两条曲线画在同一个坐标系里：上面那条正常（左低右高），下面那条倒挂
     （左端翘起、右端压平）。柱高只表**形状**，图上不写任何数字（D-22）；
     红色只出现在倒挂那条的短端——那正是"短端比长端高"这件事本身。 */
  /* 左边是常规做法：一张晶圆切成一格一格分别封装；右边是晶圆级做法：
     整片不切，格子还在，但切割线没有落下。
     这道"切 / 不切"就是这家公司的全部技术主张，也是它良率与供电风险的来源，
     所以记忆点画的是**边界**而不是芯片本身。
     格数只是装饰密度，不代表任何数量关系，图上也不写数字（D-22）。 */
  /* 一条利率线进来，分叉打到四个地方。
     主干用强调色（流动性本身），四条分叉用主色并依次变淡——
     变淡不是"重要性排序"，只是表示它们是同一条线的不同去向。
     分叉条数与角度都是形状，图上不写任何数字（D-22）。 */
  if (token === "spillover_fan") {
    return (
      <div className="motif motif-fan" aria-hidden="true">
        <i className="trunk" />
        <div className="fan">
          {[0, 1, 2, 3].map((i) => (
            <i key={i} className={"arm a" + i} />
          ))}
        </div>
      </div>
    );
  }
  if (token === "wafer_grid") {
    return (
      <div className="motif motif-wafer" aria-hidden="true">
        <div className="half diced">
          {Array.from({ length: 16 }).map((_, i) => (
            <i key={i} />
          ))}
        </div>
        <div className="scribe" />
        <div className="half whole" />
      </div>
    );
  }
  if (token === "rent_shift") {
    /* 开源权重与算力估值篇：三条横带是价值链的三层，钱从最上面那层搬到了最下面那层。
       最上面只描边——开源权重这一层不收钱；中间那条用强调色，是它现在的住处；
       最下面最宽最实，资本开支真正落在这一层。宽度表达的是"谁拿走现金"，不是装饰。
       与 stack_layers 的区别是刻意的：那套五层全是实的（讲一次调用穿过几层），
       这套要讲的是**有一层是空的**。 */
    return (
      <div className="motif motif-rent" aria-hidden="true">
        <i className="open" style={{ width: "38%" }} />
        <i className="hot" style={{ width: "64%" }} />
        <i className="capex" style={{ width: "94%" }} />
      </div>
    );
  }
  if (token === "curve_invert") {
    const normal = [26, 38, 50, 64, 80, 96];
    const inverted = [92, 74, 58, 46, 40, 36];
    return (
      <div className="motif motif-curve" aria-hidden="true">
        <div className="cline">
          {normal.map((h, i) => (
            <i key={i} style={{ height: `${h}%` }} />
          ))}
        </div>
        <div className="cline inv">
          {inverted.map((h, i) => (
            <i key={i} className={h > 60 ? "hot" : ""} style={{ height: `${h}%` }} />
          ))}
        </div>
      </div>
    );
  }
  if (token === "turn_caret") {
    return (
      <div className="motif motif-turn" aria-hidden="true">
        <i className="turn out" />
        <i className="turn call" />
        <i className="caret" />
      </div>
    );
  }
  if (token === "morgan_split") {
    /* 摩根篇：一条家族干在 1933 那道口子上断成两条腿。
       上横是 J. Pierpont Morgan 一人手里的那家银行，中缝是《格拉斯–斯蒂格尔》
       逼出来的分家，下面两条分别是今天的 JPMorgan Chase 与 Morgan Stanley——
       两条宽度不同，因为这两家的资产规模差着一个数量级。 */
    return (
      <div className="motif motif-morgan" aria-hidden="true">
        <i className="stem" />
        <i className="cut" />
        <i className="leg bank" />
        <i className="leg sec" />
      </div>
    );
  }
  if (token === "bandwidth_neck") {
    /* 本地大模型芯片篇：四路内存并排很宽，中间收成一个脖子，右边那颗芯片大多时候在等。
       强调色给脖子——这一篇的论点就是"卡住你的是搬运，不是计算"。
       不画成横条阶梯：`.motif-choice` 已经是"几条不等长横条 + 一条 hot"，
       两个领域的记忆点撞形状，就等于其中一个白设。 */
    return (
      <div className="motif motif-lane" aria-hidden="true">
        <div className="pool">
          <i />
          <i />
          <i />
          <i />
        </div>
        <i className="neck" />
        <i className="chip" />
      </div>
    );
  }
  if (token) {
    return (
      <div className="motif motif-bar" aria-hidden="true">
        <i />
      </div>
    );
  }
  return null;
}

function Figure({ img }: { img: PageImage }) {
  /* 自画示意图必须一眼看得出是画的：读者对照片和对图的信任方式不同。
     它也不许挂「图源」链接——那是引用图的可核查性凭证，借给画出来的图就是冒充。 */
  const drawn = img.kind === "illustration";
  return (
    <figure className={drawn ? "drawn" : undefined}>
      <div className="ratio">
        <img src={img.file} alt={img.alt} loading="lazy" />
        {drawn && <span className="fig-kind">示意图 · 非实拍</span>}
      </div>
      {(drawn || img.caption || img.source_page) && (
        <figcaption>
          {img.caption || img.alt}
          {img.source_page && (
            <>
              {" · "}
              <a href={img.source_page} rel="noreferrer" target="_blank">
                图源
              </a>
            </>
          )}
        </figcaption>
      )}
    </figure>
  );
}

/** 封面：先看数据里声明的那张，没有才退到"最宽的那张"，且不设尺寸门槛。
 *  不设门槛的理由：低于某个宽度就不显示，结果是整面照片墙退成渐变（开发者 2026-09-19 反馈）；
 *  防放大糊图改由渲染层负责——封面盒被限到图片自身宽度（见 --cover-w）。
 *  为什么要"先看声明"：默认那条规则天然偏爱排行榜截图与宣传横幅（它们像素宽度最大），
 *  索引卡片上会被 object-fit:cover 裁掉半截文字。声明写在 data.json 的 `cover`，
 *  `--offline` 重渲染是从盘上读 data.json 再合并，所以人挑的那张不会被冲掉；
 *  `build_index.cover_of` 必须与这里同规则，否则点进去会换一张图。 */
export function coverOf(data: TopicData): PageImage | undefined {
  /* 声明优先，其次才是"最宽的一张"。默认那条规则天然偏爱排行榜截图与
     宣传横幅（它们的像素宽度最大），索引卡片上会被 object-fit:cover 裁掉
     半截文字。build_index.cover_of 必须与这里同规则，否则点进去会换一张图。 */
  if (data.cover) return data.cover;
  let best: PageImage | undefined;
  for (const s of data.sections) {
    for (const im of s.images || []) {
      // 自画示意图不参与自动封面：首屏与索引卡片都没有「示意图 · 非实拍」那行字的位置，
      // 拿它当门面等于让读者以为那是真实照片。与 build_index.cover_of 同一套规则。
      if (im.kind === "illustration") continue;
      if (!best || (im.width || 0) > (best.width || 0)) best = im;
    }
  }
  return best;
}

/** 读页时长：正文汉字 ÷ 500 字/分钟 + 每张图 0.15 分钟，与质量闸门 G-05 同一口径。 */
export function readingMinutes(data: TopicData): number {
  let cjk = 0;
  const walk = (v: unknown): void => {
    if (typeof v === "string") cjk += (v.match(/[㐀-鿿]/g) || []).length;
    else if (Array.isArray(v)) v.forEach(walk);
    else if (v && typeof v === "object") Object.values(v).forEach(walk);
  };
  walk(data);
  const imgs = data.sections.reduce((n, s) => n + (s.images?.length || 0), 0);
  return Math.max(1, Math.round(cjk / 500 + imgs * 0.15));
}

export interface TopicPageProps {
  data: TopicData;
  /** 给了就把 tag 渲染成可点跳转（索引页用），不给就是纯文本标签 */
  tagHref?: (tag: string) => string;
  /** SSR 产物把 <style> 放进 <head>（见 ssr-entry）；工作台预览仍让组件自带。 */
  hideStyle?: boolean;
}

/** 最后核对于：本页所有来源里**最晚**的那个 `retrieved`。
 *  来源清单本来逐条印「查阅 X」（609 行），但读者要的是这一篇整体多久没被人回头看过了；
 *  「生成于」只是渲染时间，不能假装内容被复查过（W-190）。
 *  与闸门 G-15 读同一个数，所以运维清单和页面上那句话不会各说一套。 */
function lastChecked(data: TopicData): string | undefined {
  const ds = data.sources
    .map((s) => s.retrieved)
    .filter((d): d is string => typeof d === "string" && d.length > 0);
  return ds.length ? ds.sort()[ds.length - 1] : undefined;
}

export function TopicPage({ data, tagHref, hideStyle }: TopicPageProps): ReactNode {
  const t = themeOf(data.theme?.token);
  const src: SrcIndex = new Map(data.sources.map((s) => [s.id, s]));
  const cover = coverOf(data);
  const checked = lastChecked(data);
  const minutes = data.reading_minutes || readingMinutes(data);
  const tags = data.tags || [];

  return (
    <>
      {!hideStyle && <style dangerouslySetInnerHTML={{ __html: cssFor(t) }} />}
      <header className={"cover" + (cover ? "" : " cover-noimg")}>
        <div
          className="cover-media"
          style={
            cover?.width
              ? ({ "--cover-w": `${cover.width}px` } as React.CSSProperties)
              : undefined
          }
        >
          {/* 封面框里没有 figcaption。声明了封面就必有 alt（schema 与 G-03 各钉一条）；
              没声明、退到"最宽的一张"时那张图的 alt 是空的，所以拿本页标题兜底，
              否则这一格对屏读器是完全静音的。 */}
          {cover ? <img src={cover.file} alt={cover.alt || data.subtitle || data.topic} /> : null}
          {/* 自画图当封面时角标必须出现在**页面上**，不能只躲在 alt 里：
              alt 是给读屏器与搜索引擎的，读者什么也看不到（R-03）。
              正文里的图一直有这条，缺的只有封面这一支——第一篇用自画图做封面的
              （Agent 开发）才把它暴露出来。 */}
          {cover?.kind === "illustration" && (
            <span className="fig-kind">示意图 · 非实拍</span>
          )}
          {/* 记忆点不再只在"没有封面"时出现：coverOf 总会退到章节首图，
              于是 10 个领域各自的 motif 实际上一次都没渲染过。 */}
          {!cover && <Motif token={t.heroMotif} />}
        </div>
        {/* 标题必须在 cover-media 之外：那层是固定宽高比 + overflow:hidden，
            放进去会被裁掉——上一版就是这么把 H1 弄丢的。 */}
        <div className="cover-body">
          <div className="cover-kicker">
            {data.category ? `${data.category} · ` : ""}知识专题
          </div>
          <h1>{data.subtitle || data.topic}</h1>
        </div>
      </header>

      <div className="wrap">
        {/* `../index.html` 在合站之后**正好指向本组的落地页**（包内布局就是
            `<组>/<篇>/<篇>.html`，落地页是 `<组>/index.html`），所以出包不再改写这一处，
            也不再有"标记必须恰好出现一次"的契约——那是一篇一站时代的产物，
            当时 `../index.html` 在托管域名上会指回自己。
            文案跟着落地页走：落地页列的是本类别的专题，不是全站。 */}
        <nav className="backhome" aria-label="返回目录">
          <a className="backhome-link" href="../index.html">
            ← {data.category ? `${data.category}全部专题` : "本组全部专题"}
          </a>
          {data.home_url ? (
            <a className="backhome-link backhome-site" href={data.home_url}>
              ← 全部领域 · 总站首页
            </a>
          ) : null}
        </nav>
        <div className="layout">
        <nav className="toc" aria-label="目录">
          <h2>目录</h2>
          <ol>
            {data.sections.map((s) => (
              <li key={s.id}>
                <a href={"#" + s.id}>
                  <span className="anch">{s.anchor || s.title.slice(0, 1)}</span>
                  <span>{s.title}</span>
                </a>
              </li>
            ))}
          </ol>
        </nav>

        <div className="body">
        <div className="meta">
          <span className="who">{data.topic}</span>
          <span className="dot" />
          <span>{minutes} 分钟读完</span>
          <span className="dot" />
          <span>{data.sections.length} 章</span>
          {data.data_as_of && (
            <>
              <span className="dot" />
              <span>数据时点 {data.data_as_of}</span>
            </>
          )}
          {checked && (
            <>
              <span className="dot" />
              <span>核对于 {checked}</span>
            </>
          )}
          <span className="dot" />
          <span>生成于 {data.generated_date}</span>
        </div>

        {tags.length > 0 && (
          <div className="tags">
            {tags.map((tag) =>
              tagHref ? (
                <a className="tag" key={tag} href={tagHref(tag)}>
                  #{tag}
                </a>
              ) : (
                <span className="tag" key={tag}>
                  #{tag}
                </span>
              ),
            )}
          </div>
        )}

        {data.reader && (
          <div className="meta">
            <span>写给：{data.reader}</span>
          </div>
        )}

        {data.research_mode !== "online" && (
          <div className="warnbox">
            本次生成未能联网查证，文中数字为模型已知信息，可能过时或有误，请以下方来源为准自行核对。
          </div>
        )}

        {data.lede && (
          <div className="lede">
            <p>{data.lede}</p>
          </div>
        )}

        {data.sections.map((s, i) => (
          <section className="chap" id={s.id} key={s.id}>
            <div className="chap-head">
              {t.numberedSections && (
                <span className="num">{String(i + 1).padStart(2, "0")}</span>
              )}
              <h2>{s.title}</h2>
            </div>
            {s.intro && <p className="intro">{s.intro}</p>}
            {(s.images || []).length > 0 && (
              <div className={"figs" + ((s.images || []).length > 1 ? " c2" : "")}>
                {(s.images || []).map((im) => (
                  <Figure img={im} key={im.file} />
                ))}
              </div>
            )}
            {s.blocks.map((b, j) => (
              <div key={j}>{renderBlock(b, src)}</div>
            ))}
          </section>
        ))}

        <div className="srcs" id="sources">
          <h2>来源</h2>
          <ol>
            {data.sources.map((s) => (
              <li key={s.id} id={"src-" + s.id}>
                <a href={s.url} rel="noreferrer" target="_blank">
                  {s.label || s.url}
                </a>
                {s.publisher ? `（${s.publisher}）` : ""}
                {s.retrieved ? ` · 查阅 ${s.retrieved}` : ""}
              </li>
            ))}
          </ol>
        </div>

        <footer className="foot">
          <div>
            《{data.topic}》知识专题 · 生成于 {data.generated_date}
            {data.data_as_of ? ` · 价格与状态类信息截至 ${data.data_as_of}` : ""}
          </div>
          <div>
            本文为科普整理，不构成购买建议；价格、产期、政策随时间变化，请以品牌官方与权威来源为准。
          </div>
        </footer>
        </div>
        </div>
      </div>
    </>
  );
}
