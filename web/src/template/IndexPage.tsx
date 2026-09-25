import type { ReactNode } from "react";
import { THEMES, themeOf } from "../tokens";
import { LAYOUT_CSS, LAYOUT_MOBILE_CSS } from "../tokens/layout";
import type { IndexEntry } from "../types";

/**
 * 索引主页：小红书/Instagram 式的图片优先 feed。
 *
 * 为什么是**一条连续 feed**而不是按类别切成多个小网格：
 * 切了之后每个类别只有 1 篇时，auto-fill 仍会预留 6 条轨道 ——
 * 实测 2560px 视口下用掉 356px、空 1869px，看起来就是"不自适应"。
 * 类别改为卡片上的 chip + 顶部锚点，顺序与密度都由一条网格负责。
 */
const HOUSE = {
  bg: "#FFFFFF",
  ink: "#1F1F23",
  muted: "#73737B",  // 白底 4.7:1；再浅就过不了 G-13 的 AA 检查
  rule: "#EFEFF1",
  hairline: "#F5F5F6",
  brand: "#FF2442",
};

/** 封面比例轮换：连续 feed 里的错落节奏来自这里。 */
const RATIOS = ["3/4", "1/1", "4/5", "3/4", "5/4", "1/1", "3/4", "4/5"];

export function css(): string {
  return `${LAYOUT_CSS}
*{box-sizing:border-box}
body{margin:0;background:${HOUSE.bg};color:${HOUSE.ink};
  font-family:'PingFang SC','Hiragino Sans GB','Microsoft YaHei','Noto Sans SC',system-ui,sans-serif;
  font-size:15px;line-height:1.6;-webkit-font-smoothing:antialiased}
a{color:inherit;text-decoration:none}
:focus-visible{outline:2px solid ${HOUSE.brand};outline-offset:2px;border-radius:6px}

.bar{position:sticky;top:0;z-index:20;background:rgba(255,255,255,.92);
  backdrop-filter:saturate(1.4) blur(10px);border-bottom:1px solid ${HOUSE.rule}}
.bar-in{width:var(--col);margin:0 auto;padding:.7rem 0;display:flex;align-items:center;gap:1rem}
.brand{display:flex;align-items:center;gap:.45rem;font-size:1.02rem;font-weight:600;flex:none}
.brand i{width:1.35rem;height:1.35rem;border-radius:5px;background:${HOUSE.brand};color:#fff;
  display:grid;place-items:center;font-style:normal;font-size:.72rem;font-weight:700}
.tabs{display:flex;gap:.35rem;overflow-x:auto;scrollbar-width:none;flex:1;min-width:0}
.tabs::-webkit-scrollbar{display:none}
.tab{flex:none;font-size:.85rem;padding:.3rem .8rem;border-radius:999px;color:${HOUSE.muted};
  white-space:nowrap;font-weight:500;overflow-wrap:anywhere}
.tab:hover{color:${HOUSE.ink};background:${HOUSE.hairline}}
.tab i{font-style:normal;font-size:.7rem;opacity:.6;margin-left:.25rem}
.tally{flex:none;font-size:.74rem;color:${HOUSE.muted};font-family:ui-monospace,Consolas,monospace}

.head{width:var(--col);margin:0 auto;padding:clamp(1.2rem,2.5vw,2.2rem) 0 .2rem}
.head h1{font-size:clamp(1.5rem,2.2vw,2.4rem);font-weight:600;letter-spacing:-.015em;margin:0}
.head p{margin:.3rem 0 0;color:${HOUSE.muted};font-size:.86rem;max-width:56ch}

.sortbar{width:var(--col);margin:0 auto;padding:.7rem 0 0;display:flex;align-items:center;
  gap:.4rem;font-size:.76rem;color:${HOUSE.muted};flex-wrap:wrap}
.sortbar input{position:absolute;width:1px;height:1px;opacity:0}
.sortbar label{font-size:.75rem;padding:.22rem .62rem;border-radius:999px;
  border:1px solid ${HOUSE.rule};color:${HOUSE.muted};cursor:pointer;white-space:nowrap}
.sortbar label:hover{color:${HOUSE.ink};background:${HOUSE.hairline}}
.sortbar input:checked+label{background:${HOUSE.ink};border-color:${HOUSE.ink};color:#fff}
.sortbar input:focus-visible+label{outline:2px solid ${HOUSE.brand};outline-offset:2px}

.grp{width:var(--col);margin:0 auto;padding:clamp(1.2rem,2.2vw,2rem) 0 0}
.feed{display:grid;gap:clamp(.7rem,1.2vw,1.1rem);
  grid-template-columns:repeat(auto-fill,minmax(min(19rem,100%),1fr))}

.card{display:flex;flex-direction:column;min-width:0;position:relative;order:var(--desc,0);
  border:1px solid ${HOUSE.rule};border-radius:12px;overflow:hidden;background:#fff;
  transition:transform .16s ease,box-shadow .16s ease}
/* 排序是纯 CSS：DOM 已经是创建时间升序，默认 --desc 显示"最新在前"，
   勾"最早在前"就把 order 换成 --asc。不支持 :has() 的浏览器退化成"最新在前"，
   只是切换失效——不为了一个排序按钮给自包含产物引运行时 JS。
   祖先必须写 body 而不是 .feed：radio 在 .sortbar 里，不是 .feed 的后代，
   「.feed:has(#sort-old:checked)」永远匹配不上（真浏览器里验过一次，顺序纹丝不动）。 */
body:has(#sort-old:checked) .card{order:var(--asc,0)}
.card:hover{transform:translateY(-2px);box-shadow:0 12px 28px -14px rgba(20,20,25,.28)}
a[id^="cat-"]{scroll-margin-top:4.2rem}
.ph{position:relative;background:var(--soft,#F2F2F4);overflow:hidden}
.ph img{width:100%;height:100%;object-fit:cover;display:block}
/* 无封面时的排版层：字压在渐变的浅色带（soft 停在 60%）上，
   所以用主题自己的 primary 就够读，不需要额外描边。 */
.ph-word{position:absolute;left:.6rem;right:.6rem;top:58%;transform:translateY(-50%);
  text-align:center;font-size:clamp(1.45rem,3.2vw,2.5rem);font-weight:700;line-height:1.15;
  letter-spacing:.01em;color:var(--brand,#1F1F23);overflow-wrap:anywhere;pointer-events:none}
.badge{position:absolute;left:.5rem;bottom:.5rem;font-size:.68rem;font-weight:600;
  padding:.16rem .5rem;border-radius:999px;background:rgba(255,255,255,.9);color:var(--brand,#1F1F23);
  box-shadow:0 1px 3px rgba(0,0,0,.12)}
.cat-chip{position:absolute;right:.5rem;top:.5rem;font-size:.66rem;font-weight:600;
  padding:.16rem .5rem;border-radius:999px;background:rgba(0,0,0,.55);color:#fff}
/* 排序键必须看得见，否则读者只会觉得卡片顺序莫名其妙。 */
.cdate{position:absolute;left:.5rem;top:.5rem;font-size:.64rem;font-weight:600;
  padding:.16rem .45rem;border-radius:999px;background:rgba(0,0,0,.55);color:#fff;
  font-family:ui-monospace,Consolas,monospace}
.bd{padding:.6rem .7rem .72rem;flex:1;display:flex;flex-direction:column}
.t{margin:0;font-size:clamp(.92rem,1vw,1.08rem);font-weight:600;line-height:1.4;
  display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;
  overflow-wrap:anywhere}
.m{display:flex;align-items:center;gap:.3rem;margin-top:.42rem;font-size:.72rem;color:${HOUSE.muted}}
.m i{font-style:normal}
.m .sep{width:2px;height:2px;border-radius:50%;background:#D5D5D9}
.tg{display:flex;flex-wrap:wrap;gap:.25rem;margin-top:.45rem;min-width:0}
.tg span{font-size:.68rem;padding:.1rem .45rem;border-radius:999px;background:${HOUSE.hairline};
  color:#5A5A63;overflow-wrap:anywhere}
.empty{width:var(--col);margin:2.5rem auto;padding:0;color:${HOUSE.muted};font-size:.9rem}

footer.ft{width:var(--col);margin:3rem auto 0;padding:1.2rem 0;
  border-top:1px solid ${HOUSE.rule};color:${HOUSE.muted};font-size:.74rem;line-height:1.8}
footer.ft code{font-family:ui-monospace,Consolas,monospace;font-size:.95em}
${LAYOUT_MOBILE_CSS}
@media (max-width:640px){
  .bar-in{padding:.6rem 0;gap:.6rem}
  .tally{display:none}
  .feed{grid-template-columns:repeat(auto-fill,minmax(min(15rem,100%),1fr))}
}
@media (prefers-reduced-motion:no-preference){
  @keyframes rise{from{opacity:0;transform:translateY(.5rem)}to{opacity:1;transform:none}}
  .head{animation:rise .4s cubic-bezier(.2,.7,.3,1) both}
}
`;
}

function CoverArt({ token, topic }: { token: string; topic: string }) {
  const t = themeOf(token);
  return (
    <>
      <div
        style={{
          position: "absolute",
          inset: 0,
          background: `linear-gradient(150deg, ${t.primary} 0%, ${t.soft} 60%, ${t.accent} 100%)`,
        }}
        aria-hidden="true"
      />
      {/* 没有配图时要明确是"一张排版封面"，不是一个坏掉的图框：
          只有一块渐变，读者只会理解成图裂了（主页上真被这么报过一次）。 */}
      <div className="ph-word">{topic}</div>
    </>
  );
}

export interface IndexPageProps {
  entries: IndexEntry[];
  generatedDate: string;
  /** SSR 产物把 <style> 放进 <head>（见 ssr-entry）；工作台预览仍让组件自带。 */
  hideStyle?: boolean;
}

export function IndexPage({ entries, generatedDate, hideStyle }: IndexPageProps): ReactNode {
  const cats: [string, number][] = [];
  for (const e of entries) {
    const hit = cats.find((c) => c[0] === e.category);
    if (hit) hit[1] += 1;
    else cats.push([e.category, 1]);
  }
  const tagCount = new Set(entries.flatMap((e) => e.tags)).size;
  const firstOfCat = new Set<string>();
  for (const e of entries) if (!firstOfCat.has(e.category)) firstOfCat.add(e.category);
  const seen = new Set<string>();

  return (
    <>
      {!hideStyle && <style dangerouslySetInnerHTML={{ __html: css() }} />}
      <div className="bar">
        <div className="bar-in">
          <span className="brand">
            <i>知</i>知识专题
          </span>
          <nav className="tabs" aria-label="类别">
            {cats.map(([cat, n]) => (
              <a className="tab" key={cat} href={"#cat-" + cat}>
                {cat}
                <i>{n}</i>
              </a>
            ))}
          </nav>
          <span className="tally">
            {entries.length} 篇 · {tagCount} 标签
          </span>
        </div>
      </div>

      <div className="head">
        <h1>十分钟读完一个领域</h1>
        <p>按类别归档的科普长文。每篇都带来源与价格时点，点开卡片看完整专题页。</p>
      </div>

      <div className="sortbar" role="group" aria-label="按创建时间排序">
        <span>按创建时间</span>
        <input type="radio" name="sort" id="sort-new" defaultChecked />
        <label htmlFor="sort-new">最新在前</label>
        <input type="radio" name="sort" id="sort-old" />
        <label htmlFor="sort-old">最早在前</label>
      </div>

      {entries.length === 0 ? (
        <div className="empty">
          还没有任何专题页。运行 <code>python scripts/generate.py 咖啡</code> 生成第一篇。
        </div>
      ) : (
        <section className="grp">
          <div className="feed">
            {entries.map((e, i) => {
              const t = THEMES[e.token];
              const anchor = !seen.has(e.category) ? "cat-" + e.category : undefined;
              seen.add(e.category);
              return (
                <a
                  className="card"
                  href={e.href}
                  key={e.topic}
                  id={anchor}
                  style={
                    {
                      "--brand": t ? t.primary : HOUSE.ink,
                      "--soft": t ? t.soft : "#F2F2F4",
                      "--asc": String(i),
                      "--desc": String(entries.length - 1 - i),
                    } as React.CSSProperties
                  }
                >
                  <div className="ph" style={{ aspectRatio: RATIOS[i % RATIOS.length] }}>
                    {e.cover ? (
                      <img src={e.cover.file} alt={e.cover.alt} loading="lazy" />
                    ) : (
                      <CoverArt token={e.token} topic={e.topic} />
                    )}
                    <span className="badge">{e.topic}</span>
                    <span className="cat-chip">{e.category}</span>
                    {e.created && (
                      <time className="cdate" dateTime={e.created}>
                        {e.created.slice(5)}
                      </time>
                    )}
                  </div>
                  <div className="bd">
                    <h3 className="t">{e.subtitle || e.topic}</h3>
                    <div className="m">
                      <i>{e.minutes} 分钟</i>
                      <span className="sep" />
                      <i>{e.sections} 章</i>
                      {e.dataAsOf && (
                        <>
                          <span className="sep" />
                          <i>{e.dataAsOf}</i>
                        </>
                      )}
                    </div>
                    <div className="tg">
                      {e.tags.slice(0, 4).map((tag) => (
                        <span key={tag}>#{tag}</span>
                      ))}
                    </div>
                  </div>
                </a>
              );
            })}
          </div>
        </section>
      )}

      <footer className="ft">
        <div>
          共 <b>{entries.length}</b> 篇专题（{cats.length} 个类别），由 <code>scripts/generate.py</code>{" "}
          生成、<code>scripts/build_index.py</code> 汇总；每篇均通过 <code>scripts/validate.py</code>{" "}
          质量闸门。更新于 {generatedDate}
        </div>
        <div>内容为科普整理，不构成购买建议；价格与政策随时间变化，请以官方与来源链接为准。</div>
      </footer>
    </>
  );
}
