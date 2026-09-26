import type { ThemeTokens } from "../tokens";
import { LAYOUT_CSS, LAYOUT_MOBILE_CSS } from "../tokens/layout";

/**
 * 由 token 生成整页 CSS。这段 CSS 会被内联进产物的 <style>，
 * 因此产物不依赖任何外部样式文件——见 specs/golden-template「产物离线自包含」。
 *
 * 2026-09-19 按开发者反馈重构为「图片优先 feed」语言（Instagram / 小红书 一脉）：
 *  - 越大越细：display 用 400 字重 + 微正字距，小字反而加重（guizang style-system 的核心规则）
 *  - 图是证据：章首大图、稳定宽高比容器、object-fit cover，而不是文末装饰
 *  - 圆角与投影按层级分档（卡片 14 / 图 12 / pill 999），不搞"全站一个圆角"
 *  - 表头去掉大色块，改细线 + 小字重，让位给内容
 */
export function cssFor(t: ThemeTokens): string {
  const dark = isDark(t);
  const shade = dark ? "rgba(255,255,255,.05)" : "rgba(17,17,20,.045)";
  // 文字用色必须过 AA；装饰用色（边框、圆点、色带）继续用原强调色，不然品牌感就没了
  const accentInk = inkFor(t.accent, t.bg);
  const primaryInk = inkFor(t.primary, t.soft);
  // 小标题可能落在 --surface（普通卡）或 --soft（提示块）上，两边都要过线
  const mutedInk = inkFor(inkFor(t.muted, t.surface), t.soft);
  return `${LAYOUT_CSS}
:root{
  --bg:${t.bg};--surface:${t.surface};--ink:${t.ink};--muted:${t.muted};--rule:${t.rule};
  --primary:${t.primary};--accent:${t.accent};--soft:${t.soft};
  --accent-ink:${accentInk};--primary-ink:${primaryInk};--muted-ink:${mutedInk};
  --display:${t.displayFamily};--body:${t.bodyFamily};--num:${t.numFamily};
  --r-card:14px;--r-img:12px;--r-pill:999px;--r-chip:8px;
  --sh-1:0 1px 2px ${shade};
  --sh-2:0 1px 2px ${shade},0 10px 28px -14px ${dark ? "rgba(0,0,0,.6)" : "rgba(17,17,20,.18)"};
}
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--bg);color:var(--ink);font-family:var(--body);
  font-size:clamp(16px, .95rem + .3vw, 22px);line-height:1.78;letter-spacing:.01em;
  text-rendering:optimizeLegibility;-webkit-font-smoothing:antialiased}
a{color:inherit;text-underline-offset:.18em;text-decoration-thickness:1px}
a:hover{color:var(--accent)}
:focus-visible{outline:2px solid var(--accent);outline-offset:3px;border-radius:4px}
p{margin:.75rem 0}

/* ---------- 封面型 hero：图占主导，标题压在图上或紧随其后 ---------- */
.cover{position:relative;width:var(--shell);margin:clamp(1rem,2vw,2.2rem) auto 0;padding:0}
/* 封面必须封顶高度。只给 aspect-ratio 的话，容器多宽图就多高：
   3737px 视口下容器 2688px → 封面 1512px 高，整屏被一张（还是从小图放大来的）
   糊图占满，标题被推到屏幕外。横幅化：高度锁在视口一半以内，多余部分裁掉。 */
.cover-media{position:relative;border-radius:var(--r-card);overflow:hidden;background:var(--soft);
  box-shadow:var(--sh-2);width:100%;height:clamp(220px,26vw,420px);
  max-width:var(--cover-w,100%);margin-inline:auto}
.cover-media img{width:100%;height:100%;object-fit:cover;object-position:center 40%;display:block}
/* 标题不压图：封面图来自检索、亮度完全不可控，白字压浅图必然糊。
   小红书详情页本身就是"图在上、标题在下"，照做顺带消掉对比度风险。 */
/* 没有合格封面时由领域记忆点撑场。记忆点必须铺满整块封面——
   之前是一条 8px 色带浮在 240px 空色块里，开发者评价"像坏版"。 */
.cover-noimg .cover-media{height:clamp(180px,20vw,320px);padding:0;aspect-ratio:auto}
.cover-noimg .motif{position:absolute;inset:0;margin:0}
.cover-noimg .motif-roast,.cover-noimg .motif-bar,.cover-noimg .motif-dots,.cover-noimg .motif-comb,.cover-noimg .motif-attn,.cover-noimg .motif-choice{height:100%;border-radius:0}
.cover-noimg .motif-tiles{height:100%;gap:0;border:0}
.cover-noimg .motif-tiles i{height:100%;border-radius:0;border-left:1px solid var(--rule)}
.cover-noimg .motif-tiles i:first-child{border-left:0}
/* 通用条状记忆点铺满后会变成一块纯色油漆样块——加斜向光泽与细刻度线，
   让它读起来像"领域图形"而不是一屏底色。 */
.cover-noimg .motif-bar{height:100%;border-radius:0;
  background:
    repeating-linear-gradient(90deg,rgba(255,255,255,.07) 0 1px,transparent 1px 44px),
    linear-gradient(115deg,var(--primary),var(--accent) 52%,var(--primary))}
.cover-noimg .motif-label{position:absolute;left:0;right:0;bottom:0;margin:0;
  padding:2.2rem 1.4rem .95rem;color:#fff;font-size:.74rem;
  background:linear-gradient(transparent,rgba(0,0,0,.55))}
.cover-noimg .motif-label span{color:#fff}
.cover-body{margin:1.15rem 0 0}
.cover-body h1{font-family:var(--display);font-size:clamp(1.55rem,4vw,2.35rem);line-height:1.3;
  margin:0;font-weight:500;letter-spacing:.01em;max-width:26ch;color:var(--ink)}
.cover-kicker{font-family:var(--num);font-size:.72rem;font-weight:600;letter-spacing:.1em;
  color:var(--accent-ink);margin-bottom:.45rem}

.wrap{width:var(--shell);margin:0 auto;padding:0 0 clamp(3rem,6vw,6rem)}

/* ---------- 宽屏用"结构"填，而不是用"行长"填 ----------
   目录进左侧常驻栏，正文锁在可读行长（44rem ≈ 32 个汉字/行）。
   之前把整页铺到 2688px 的结果是：一行 120 字 + 一张 828px 的原图被放大到
   2688px 的糊图。宽度给图和目录，句子不给。 */
.layout{display:block}
.body{margin:0}
@media (min-width:60rem){
  /* 正文列不再预留"图表余量"：一条列只有一个宽度，图与表想宽只能整栏出血（目前没有）。
     注意：grid 子项上写 margin-inline:auto 会关掉 stretch，
     列宽会塌成内容宽（实测 1272 的列被压成 704 并居中），别这么干。 */
  .layout{display:grid;align-items:start;gap:2.5rem;
    grid-template-columns:var(--rail) minmax(0,var(--measure))}
  /* 标题跟正文左边缘对齐，不然封面标题会往左戳出去一个目录栏的宽度 */
  .cover-body{padding-left:calc(var(--rail) + 2.5rem)}
}
/* 一条列一个右边界（W-81）：正文、图、表、卡片全部收到 --measure 上。
   以前是 44rem / 50rem / 撑满"正文+24rem"三条边，差到 384px，看着参差。
   文字叶子仍单独锁 --measure，是为了窄屏时盒子贴边、文字不贴边。 */
p,li,blockquote,.note p,.blk h3,.chap-head h2,.cover-body h1,.foot>div{
  max-width:var(--measure)}
.lede,.note{max-width:var(--measure)}
.figs,.steps,.timeline{max-width:none}
.figs.c2,.tablewrap,.cards,.facts,.chart,.cmp{max-width:none}

/* ---------- 笔记式 meta 行 + tag pill ---------- */
.meta{display:flex;flex-wrap:wrap;align-items:center;gap:.55rem;margin:1.1rem 0 .2rem;
  font-size:.78rem;color:var(--muted)}
.meta .who{font-weight:600;color:var(--ink)}
.meta .dot{width:3px;height:3px;border-radius:50%;background:var(--rule)}
.tags{display:flex;flex-wrap:wrap;gap:.4rem;margin:.7rem 0 0}
.tag{font-size:.74rem;padding:.2rem .68rem;border-radius:var(--r-pill);
  background:var(--soft);color:var(--primary-ink);border:1px solid transparent;text-decoration:none}
a.tag:hover{border-color:var(--accent);color:var(--accent)}

.lede{margin:1.5rem 0 0;padding:1.1rem 1.25rem;background:var(--surface);
  border:1px solid var(--rule);border-radius:var(--r-card);box-shadow:var(--sh-1)}
.lede p{margin:0;font-size:1.02em}

/* ---------- 目录：宽屏是左侧常驻栏，窄屏退回两列卡片 ---------- */
nav.toc{margin:2.2rem 0 0;padding:1.15rem 1.25rem;background:var(--surface);
  border:1px solid var(--rule);border-radius:var(--r-card);box-shadow:var(--sh-1)}
@media (min-width:60rem){
  nav.toc{position:sticky;top:1.5rem;margin:0;padding:.4rem 0;background:transparent;
    border:0;box-shadow:none}
  nav.toc ol{grid-template-columns:1fr}
}
nav.toc h2{font-size:.72rem;font-weight:600;letter-spacing:.12em;margin:0 0 .8rem;color:var(--muted)}
nav.toc ol{list-style:none;margin:0;padding:0;display:grid;
  grid-template-columns:repeat(auto-fill,minmax(min(15rem,100%),1fr));gap:.3rem .9rem}
nav.toc li a{display:flex;gap:.6rem;align-items:baseline;font-size:.87rem;max-width:none;
  text-decoration:none;padding:.34rem .4rem;border-radius:var(--r-chip)}
nav.toc li a:hover{background:var(--soft);color:var(--primary)}
nav.toc .anch{flex:none;font-family:var(--display);font-size:.8rem;color:var(--primary);
  font-weight:600;min-width:1.4em}

/* ---------- 章节：图先于文 ---------- */
section.chap{margin:2.8rem 0 0;padding:0}
.chap-head{display:flex;align-items:baseline;gap:.7rem;margin-bottom:.15rem}
.chap-head .num{font-family:var(--num);font-size:.74rem;font-weight:600;color:var(--accent-ink);
  min-width:2.2em;letter-spacing:.06em}
.chap-head h2{font-family:var(--display);font-size:1.5rem;line-height:1.32;margin:0;
  font-weight:400;letter-spacing:.012em}
.chap > .intro{color:var(--muted);font-size:.95em;margin:.35rem 0 0 0}

figure{margin:1.2rem 0 0}
figcaption{font-size:.75rem;color:var(--muted);margin-top:.5rem;line-height:1.6;
  overflow-wrap:anywhere}
figcaption a{color:var(--muted)}
/* 自画示意图的角标（kind=illustration 才渲染）。压在图左上角，
   不依赖图片本身有没有留白，也不参与 G-13 的正文对比度检查（它是白字深底）。 */
figure .ratio{position:relative}
.fig-kind{position:absolute;left:.55rem;top:.55rem;font-size:.66rem;font-weight:600;
  letter-spacing:.02em;padding:.16rem .5rem;border-radius:999px;
  background:rgba(20,18,16,.74);color:#FFFDFB}
.figs{display:grid;gap:.9rem;margin:1.2rem 0 0}
.figs.c2{grid-template-columns:repeat(auto-fit,minmax(min(14rem,100%),1fr))}
/* 文章内配图不能用 feed 的 4:5 竖幅：915px 宽 × 4/5 = 1144px 高的空色块，
   图没加载出来时就是开发者截图里那一大片"白色遮挡"。横图 + 高度封顶。 */
.figs .ratio{aspect-ratio:16/10;overflow:hidden;
  border-radius:var(--r-img);background:var(--soft)}
.figs .ratio img{margin:0;width:100%;height:100%;object-fit:cover;border-radius:0;box-shadow:none}
.figs.c2 .ratio{aspect-ratio:4/3}

/* 网格/弹性子项一律允许收缩到 0，并让长 URL、型号串在叶子节点内断行。
   缺了这两条，一个不可断 token 就能把整页顶出横向滚动条。 */
.cards>*,.facts>*,.cmp>*,.cmp .col,.figs>*,.figs .ratio,.figs figure,
nav.toc ol>*,nav.toc li,nav.toc li a,.motif-tiles>*,.mets span,
.chart,.chart .row,.chart .row>*{min-width:0}
.facts .v,.facts .l,.card p,.card .mets span,.cmp li,.cmp .verdict,.steps .spec,
.timeline li>span,.note p,.lede p,.blk p,td,th,.tag,.chart .lab,.chart .val,.chart .axis,
h1,h2,h3,h4{overflow-wrap:anywhere}

/* ---------- 区块卡片 ---------- */
.blk{margin:1.4rem 0 0}
.blk h3{font-family:var(--display);font-size:1.02rem;margin:0 0 .1rem;
  font-weight:600;letter-spacing:.01em}
.blk p:last-child{margin-bottom:0}

table{width:100%;border-collapse:collapse;font-size:.9rem}
.tablewrap{margin:1.2rem 0 0;border:1px solid var(--rule);border-radius:var(--r-card);
  overflow-x:auto;overflow-y:hidden;background:var(--surface);box-shadow:var(--sh-1);
  overscroll-behavior-x:contain;-webkit-overflow-scrolling:touch}
.tablewrap table{min-width:32rem}
th,td{padding:.7rem .85rem;text-align:left;vertical-align:top;border-bottom:1px solid var(--rule)}
thead th{background:transparent;color:var(--muted);font-size:.7rem;font-weight:600;
  letter-spacing:.1em;border-bottom:1px solid var(--rule);white-space:normal}
tbody tr:last-child td{border-bottom:0}
td.k{font-weight:600}
.num,td.num{font-family:var(--num);font-variant-numeric:tabular-nums;font-size:.86em}
caption{caption-side:bottom;text-align:left;font-size:.74rem;color:var(--muted);padding:.55rem .85rem}

.timeline{list-style:none;margin:.5rem 0 0;padding:0 0 0 .35rem}
.timeline li{position:relative;padding:0 0 1.05rem 1.3rem;border-left:1px solid var(--rule)}
.timeline li:last-child{border-left-color:transparent;padding-bottom:0}
.timeline li::before{content:"";position:absolute;left:-.36rem;top:.55rem;width:.68rem;height:.68rem;
  background:var(--accent);border-radius:50%;box-shadow:0 0 0 3px var(--surface)}
.timeline .yr{font-family:var(--num);font-size:.76rem;font-weight:600;color:var(--accent-ink);display:block}
.timeline .tl-title{font-weight:600;display:block;margin-top:.12rem}

.cards{display:grid;gap:.8rem;margin:.8rem 0 0;
  grid-template-columns:repeat(auto-fit,minmax(min(14rem,100%),20rem));justify-content:start}
.card{background:var(--surface);border:1px solid var(--rule);border-radius:var(--r-card);
  padding:1rem 1.05rem;box-shadow:var(--sh-1)}
.card:hover{box-shadow:var(--sh-2)}
.card .kick{font-size:.7rem;color:var(--muted);font-weight:600;letter-spacing:.06em}
.card h4{font-family:var(--display);font-size:1rem;margin:.2rem 0 .35rem;font-weight:600}
.card p{font-size:.87rem;margin:.25rem 0}
.card .mets{display:flex;flex-wrap:wrap;gap:.4rem;margin-top:.6rem;font-size:.72rem}
.card .mets span{background:var(--soft);padding:.16rem .55rem;border-radius:var(--r-pill)}

.steps{counter-reset:st;list-style:none;margin:.6rem 0 0;padding:0}
.steps li{counter-increment:st;position:relative;padding:.6rem 0 .6rem 2.5rem;
  border-bottom:1px solid var(--rule)}
.steps li:last-child{border-bottom:0}
.steps li::before{content:counter(st);position:absolute;left:0;top:.62rem;
  font-family:var(--num);font-size:.74rem;font-weight:600;color:var(--primary);
  background:var(--soft);width:1.7rem;height:1.7rem;display:grid;place-items:center;
  border-radius:var(--r-pill)}
.steps .sp-title{font-weight:600;display:block}
.steps .spec{font-family:var(--num);font-size:.76rem;color:var(--accent-ink)}

blockquote{margin:1.3rem 0 0;padding:1rem 1.15rem;background:var(--surface);
  border:1px solid var(--rule);border-left:3px solid var(--accent);
  border-radius:var(--r-card);font-family:var(--display);font-size:1.04rem;line-height:1.62}
blockquote footer{font-family:var(--body);font-size:.78rem;color:var(--muted);margin-top:.4rem}

.facts{display:grid;gap:.9rem;justify-content:start;
  grid-template-columns:repeat(auto-fit,minmax(min(8.5rem,100%),15rem));
  margin:1.2rem 0 0;padding:1.05rem 1.1rem;background:var(--surface);
  border:1px solid var(--rule);border-radius:var(--r-card);box-shadow:var(--sh-1)}
.facts .f .v{font-family:var(--num);font-size:1.55rem;font-weight:400;color:var(--primary);line-height:1.15}
.facts .f .l{font-size:.75rem;color:var(--muted);margin-top:.18rem}

/* 评分图：柱子是画出来的数字，不是榜单截图，所以每个数都能挂自己的来源。
   数值单独占一列而不是贴在柱头——那样每行的右边界才落在同一条线上，
   能被 G-13 的"同一列右边界一致"量到（W-81 的教训：量不到的地方就会跑偏）。 */
.chart{display:grid;gap:.6rem;margin:1.2rem 0 0;padding:1.05rem 1.1rem;
  background:var(--surface);border:1px solid var(--rule);
  border-radius:var(--r-card);box-shadow:var(--sh-1)}
.chart .row{display:grid;gap:.35rem .8rem;align-items:center;
  grid-template-columns:minmax(0,11rem) minmax(0,1fr) auto}
.chart .lab{font-size:.82rem;font-weight:500;color:var(--ink)}
.chart .track{height:.6rem;border-radius:var(--r-pill);background:var(--soft);overflow:hidden}
.chart .bar{height:100%;border-radius:var(--r-pill);background:var(--primary)}
.chart .val{font-family:var(--num);font-size:.95rem;color:var(--primary)}
.chart .val .unit{font-size:.7rem;color:var(--muted);margin-left:.16rem}
.chart .axis{font-size:.7rem;color:var(--muted);margin-top:.1rem}
@media(max-width:640px){
  .chart .row{grid-template-columns:minmax(0,1fr) auto;
    grid-template-areas:"lab val" "track track"}
  .chart .lab{grid-area:lab}.chart .val{grid-area:val}.chart .track{grid-area:track}
}

/* 对照块天生两列；auto-fit 会因为 verdict 的 1/-1 跨列而保住 5 个 229px 窄条 */
.cmp{display:grid;gap:.8rem;grid-template-columns:repeat(2,minmax(0,1fr));margin:.8rem 0 0}
.cmp .col{border:1px solid var(--rule);padding:.9rem 1rem;background:var(--surface);
  border-radius:var(--r-card)}
.cmp .col.pro{border-top:3px solid var(--accent)}
.cmp .col.con{border-top:3px solid var(--muted)}
.cmp h4{font-family:var(--display);margin:0 0 .45rem;font-size:.96rem;font-weight:600}
.cmp ul{margin:.2rem 0 0;padding-left:1.1rem;font-size:.87rem}
.cmp .verdict{grid-column:1/-1;font-size:.88rem;background:var(--soft);
  padding:.8rem .95rem;border-radius:var(--r-card);color:var(--primary-ink)}

.note{margin:1.2rem 0 0;padding:.9rem 1rem;border-radius:var(--r-card);
  background:var(--surface);border:1px solid var(--rule);font-size:.88rem}
.note.warn{border-color:var(--accent);background:var(--soft);color:var(--ink)}
.note.myth{border-color:var(--primary);background:var(--soft);color:var(--ink)}
.note.tip{border-color:var(--rule);color:var(--ink)}
.note h4{margin:0 0 .3rem;font-size:.8rem;font-weight:600;letter-spacing:.04em;color:var(--muted-ink)}
.note p{margin:.2rem 0}

.srcs{margin-top:2.8rem;padding-top:1.2rem;border-top:1px solid var(--rule)}
.srcs h2{font-size:.72rem;font-weight:600;letter-spacing:.12em;color:var(--muted);margin:0 0 .6rem}
.srcs ol{margin:0;padding-left:1.5rem;font-size:.76rem;color:var(--muted)}
.srcs li{margin:.3rem 0;overflow-wrap:anywhere}
.foot{margin-top:1.8rem;padding-top:1.1rem;font-size:.74rem;color:var(--muted);line-height:1.75}
.warnbox{margin:1.4rem 0 0;padding:.9rem 1.05rem;border:1px solid var(--accent);background:var(--soft);
  font-size:.85rem;border-radius:var(--r-card)}

.refs{font-family:var(--num);font-size:.66em;font-weight:600}
.refs .ref{color:var(--accent-ink);margin-left:.18em;text-decoration:none}
.refs .ref:hover{text-decoration:underline}

.motif{margin:1.3rem 0 0;position:relative}
.motif-roast{display:flex;height:.5rem;border-radius:var(--r-pill);overflow:hidden}
.motif-roast i{flex:1}
.motif-label{font-size:.7rem;color:var(--muted);display:flex;justify-content:space-between;margin-top:.35rem}
.motif-dots{height:3.4rem;border-radius:var(--r-card);overflow:hidden;background:var(--soft);position:relative}
.motif-dots i{position:absolute;width:.2rem;height:.2rem;border-radius:50%;background:var(--accent)}
.motif-tiles{display:grid;grid-template-columns:repeat(12,1fr);gap:.22rem}
.motif-tiles i{height:1.2rem;border-radius:4px;background:var(--soft);border:1px solid var(--rule)}
.motif-bar{height:.3rem;border-radius:var(--r-pill);background:var(--primary)}
.motif-bar i{display:none}
/* 娇兰：蜂巢。三件事缺一不可——铺满（换行 + 自动填充）、偶数列下沉半格（才像巢）、
   空格用主色 12% 透明（在 soft 底色上原来那版几乎看不见，只剩两颗金格像 bug）。 */
.motif-comb{display:flex;flex-wrap:wrap;gap:.34rem;align-items:center;height:2.4rem}
.motif-comb i{width:1.5rem;height:1.72rem;background:var(--primary);opacity:.12;
  clip-path:polygon(50% 0,100% 25%,100% 75%,50% 100%,0 75%,0 25%)}
.motif-comb i:nth-child(even){transform:translateY(.32rem)}
.motif-comb i.gold{background:var(--accent);opacity:.95}
/* 无封面的大色块里：垂直居中铺几行，而不是贴顶堆一层 */
.cover-noimg .motif-comb{align-content:center;padding:1.2rem}

/* 注意力方阵：12×7 的格子，亮格沿对角线扫过去 */
.motif-attn{display:grid;grid-template-columns:repeat(12,minmax(0,1fr));
  grid-auto-rows:minmax(0,1fr);gap:.3rem;height:2.4rem}
.motif-attn i{border-radius:2px;background:var(--primary);opacity:.1;min-height:.28rem}
.motif-attn i.near{opacity:.3}
.motif-attn i.hot{background:var(--accent);opacity:.95}
.motif-choice{display:flex;flex-direction:column;gap:.34rem;justify-content:center;height:100%;padding:.2rem 0}
.motif-choice i{display:block;height:.42rem;border-radius:99px;background:var(--primary);opacity:.26}
.motif-choice i.hot{background:var(--accent);opacity:.95;height:.62rem}
.cover-noimg .motif-attn{height:100%;padding:1.2rem}
/* 光波导：一排耦出栅，越靠出瞳越亮 */
.motif-guide{display:flex;align-items:stretch;gap:.22rem;height:2.4rem}
.motif-guide i{flex:1 1 0;min-width:0;background:var(--primary);border-radius:1px}
.motif-guide i.hot{opacity:.95}
.motif-guide i.alt{background:var(--accent)}

/* 多数门槛线：25 格席位，第 13 格左边那道粗线就是"过半"的位置 */
.motif-seats{display:flex;align-items:stretch;gap:.14rem;height:2.4rem}
.motif-seats i{flex:1 1 0;min-width:0;border-radius:2px}
.motif-seats i.a{background:var(--primary);opacity:.85}
.motif-seats i.b{background:var(--accent);opacity:.85}
.motif-seats i.line{border-left:3px solid var(--ink);margin-left:-.07rem}
.cover-noimg .motif-seats{height:100%;align-items:center;padding:1.2rem;gap:.3rem}
.cover-noimg .motif-seats i{height:55%}

/* 思考预算：左三格「立刻答」，右二十一格「先想清楚再答」 */
.motif-budget{display:flex;align-items:stretch;gap:.16rem;height:2.4rem}
.motif-budget i{flex:1 1 0;min-width:0;border-radius:2px;background:var(--accent);
  border:1px solid var(--rule)}
.motif-budget i.quick{background:var(--primary);border-color:var(--primary)}
.cover-noimg .motif-budget{height:100%;align-items:center;padding:1.2rem;gap:.3rem}
.cover-noimg .motif-budget i{height:55%}

/* 货架 vs 盲盒：左半三排货架（每格一样），右半一格一格盲盒（三格亮着），共用一条基线 */
.motif-duel{display:flex;align-items:flex-end;gap:1rem;height:2.4rem;
  border-bottom:2px solid var(--primary)}
.motif-duel-shelf{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:.3rem;flex:1 1 0}
.motif-duel-shelf i{height:.5rem;border-radius:2px;background:var(--primary);opacity:.82}
.motif-duel-boxes{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:.3rem;flex:1 1 0}
.motif-duel-boxes i{aspect-ratio:1;border-radius:4px;background:var(--soft);
  border:1px solid var(--rule)}
.motif-duel-boxes i.lit{background:var(--accent);border-color:var(--accent)}
.cover-noimg .motif-duel{height:100%;align-items:center;padding:1.2rem;border-bottom-width:3px}
.cover-noimg .motif-duel-shelf i{height:.8rem}
.cover-noimg .motif-guide{height:100%;padding:1.2rem;gap:.4rem}

/* 沙箱矩阵：一格一台实例，绝大多数已经销毁、只有几格还在跑。
   格子尺寸用 minmax 而不是固定列数：固定 12 列在 375px 会把每格压到 24px 以下，
   记忆点就糊了。反过来，1440 的封面是 1000×288，格数不够就变成三行方块漂在
   一大片空白里（第一版实测就是这样，桌面截图才发现）——所以要够密，
   并且超出封面的部分直接裁掉：它是装饰，不是内容。 */
.motif-rack{display:grid;grid-template-columns:repeat(auto-fill,minmax(24px,1fr));
  gap:.3rem;align-content:center;height:2.4rem;overflow:hidden}
.motif-rack i{aspect-ratio:1/1;min-width:0;background:var(--primary);
  opacity:.13;border-radius:2px}
.motif-rack i.on{opacity:.9}
.motif-rack i.alt{background:var(--accent);opacity:.95}
.cover-noimg .motif-rack{height:100%;padding:1.2rem;gap:.34rem;align-content:start}

/* 架构分层堆栈：五条从窄到宽的横条，越往下越厚=越像生意。
   高度用 fr 而不是固定值，封面从 288px（桌面）压到 180px（手机）时
   五层都还在——固定 px 高在窄封面上会把最下面两层挤出去。 */
.motif-stack{display:flex;flex-direction:column;justify-content:center;
  gap:.3rem;height:2.4rem}
.motif-stack i{height:.34rem;min-height:0;background:var(--primary);
  opacity:.42;border-radius:99px}
.motif-stack i.hot{opacity:.95;background:var(--accent)}
.cover-noimg .motif-stack{height:100%;padding:1.4rem 1.2rem;gap:.55rem;justify-content:center}
.cover-noimg .motif-stack i{height:.62rem}

/* MLCC 的交错内电极：竖条一半挂顶、一半挂底，交错才成电容。
   高度用百分比、条宽用 flex:1，封面从桌面压到手机窄盒时条数与交错关系都还在。 */
.motif-interleave{display:flex;align-items:stretch;gap:.14rem;height:2.4rem}
.motif-interleave i{flex:1 1 0;min-width:0;height:64%;background:var(--primary);
  opacity:.38;border-radius:2px}
.motif-interleave i.up{align-self:flex-start}
.motif-interleave i.down{align-self:flex-end}
.motif-interleave i.hot{opacity:.95;background:var(--accent)}
.cover-noimg .motif-interleave{height:100%;padding:1.4rem 1.2rem;gap:.26rem}
.cover-noimg .motif-interleave i{height:70%}

/* 大模型与加密货币篇：无限层联立。一层压一层、越往下越窄、收到一个点，
   最后两层用强调色——那是 AI 补上的唯一一步。层数与耗时都不标。 */
.motif-cascade{display:flex;flex-direction:column;align-items:center;
  justify-content:center;gap:.2rem;height:2.4rem}
.motif-cascade i{height:.26rem;min-height:0;border-radius:99px;
  background:var(--primary);opacity:.34}
.motif-cascade i.hot{opacity:.95;background:var(--accent)}
.cover-noimg .motif-cascade{height:100%;padding:1.6rem 1.4rem;gap:.44rem}
.cover-noimg .motif-cascade i{height:.5rem}

/* AI制药篇的漏斗：五条逐段收窄的横条，最后一条是强调色——
   只有它进了实验室。宽度按对数收，线性收到最后两格会看不见。 */
.motif-funnel{display:flex;flex-direction:column;justify-content:center;
  gap:.22rem;height:2.4rem}
.motif-funnel i{height:.34rem;min-height:0;border-radius:99px;
  background:var(--primary);opacity:.42}
.motif-funnel i.hot{opacity:.95;background:var(--accent)}
.cover-noimg .motif-funnel{height:100%;padding:1.6rem 1.4rem;gap:.5rem}
.cover-noimg .motif-funnel i{height:.7rem}

/* 骁龙篇的等能效线：点阵里那条斜穿的亮线。数值一个都不标，
   标了它就成了一张没有来源的图表。 */
.motif-ppw{display:grid;grid-template-columns:repeat(6,1fr);gap:.22rem;
  align-content:center;height:2.4rem}
.motif-ppw i{height:.3rem;min-height:0;border-radius:99px;background:var(--primary);opacity:.16}
.motif-ppw i.near{opacity:.34}
.motif-ppw i.hot{opacity:.95;background:var(--accent)}
.cover-noimg .motif-ppw{height:100%;padding:1.2rem;gap:.55rem}
.cover-noimg .motif-ppw i{height:.7rem}

${LAYOUT_MOBILE_CSS}
@media (max-width:640px){
  body{font-size:15.5px;line-height:1.74}
  /* 手机上封面改横幅比例：不给 height:auto 的话桌面那条 clamp() 高度还在，
     aspect-ratio 会被忽略；给 max-height 又会被 aspect-ratio 反推宽度。 */
  .cover-media{height:auto;aspect-ratio:4/3}
  .cover-body{margin-top:.9rem}
  .facts,.cards{grid-template-columns:repeat(2,minmax(0,1fr))}
  nav.toc ol{grid-template-columns:1fr}
}
@media (prefers-reduced-motion:no-preference){
  @keyframes ke-rise{from{opacity:0;transform:translateY(.6rem)}to{opacity:1;transform:none}}
  .cover{animation:ke-rise .55s cubic-bezier(.2,.7,.3,1) both}
  .card{transition:box-shadow .18s ease}
}
`;
}

/** 深色主题判定：决定阴影该往哪个方向抬。 */
function isDark(t: ThemeTokens): boolean {
  const v = hexToRgb(t.bg);
  return 0.299 * v.r + 0.587 * v.g + 0.114 * v.b < 140;
}

function hexToRgb(hex: string): { r: number; g: number; b: number } {
  const h = hex.replace("#", "");
  const v = h.length === 3 ? h.split("").map((c) => c + c).join("") : h;
  return {
    r: parseInt(v.slice(0, 2), 16) || 0,
    g: parseInt(v.slice(2, 4), 16) || 0,
    b: parseInt(v.slice(4, 6), 16) || 0,
  };
}

function relLum(c: { r: number; g: number; b: number }): number {
  const f = (v: number) => {
    const s = v / 255;
    return s <= 0.03928 ? s / 12.92 : Math.pow((s + 0.055) / 1.055, 2.4);
  };
  return 0.2126 * f(c.r) + 0.7152 * f(c.g) + 0.0722 * f(c.b);
}

function contrast(a: string, b: string): number {
  const x = relLum(hexToRgb(a));
  const y = relLum(hexToRgb(b));
  return (Math.max(x, y) + 0.05) / (Math.min(x, y) + 0.05);
}

function toHex(c: { r: number; g: number; b: number }): string {
  const p = (v: number) => Math.max(0, Math.min(255, Math.round(v))).toString(16).padStart(2, "0");
  return `#${p(c.r)}${p(c.g)}${p(c.b)}`;
}

/**
 * 把强调色推到"能当正文小字用"的最低对比度（WCAG AA 4.5:1）。
 *
 * 为什么要算而不是手调 10 套 token：G-13 实测 7/10 套主题的 kicker/编号/tag
 * 落在 2.0–3.8:1，深色那 3 套反而没问题——手调会漏，而且下次加主题又漏一次。
 * 往黑（浅底）或白（深底）方向按 4% 混，直到达标；色相基本不变。
 */
function inkFor(color: string, bg: string, need = 4.5): string {
  if (contrast(color, bg) >= need) return color;
  const target = relLum(hexToRgb(bg)) > 0.5 ? "#000000" : "#ffffff";
  const from = hexToRgb(color);
  const to = hexToRgb(target);
  for (let i = 1; i <= 30; i++) {
    const k = i * 0.04;
    const mixed = {
      r: from.r + (to.r - from.r) * k,
      g: from.g + (to.g - from.g) * k,
      b: from.b + (to.b - from.b) * k,
    };
    const hex = toHex(mixed);
    if (contrast(hex, bg) >= need) return hex;
  }
  return target;
}
