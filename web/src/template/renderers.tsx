import { Fragment, type ReactNode } from "react";
import type { Block, Source } from "../types";

/**
 * 10 类区块渲染器。
 *
 * 穷尽分发：遇到未知 type 直接抛错，而不是返回 null——
 * 静默丢内容会让页面"看起来完整其实少一块"，是最危险的失败模式。
 * 见 openspec specs/golden-template「未知区块类型」。
 */
export function renderBlock(b: Block, src: SrcIndex): ReactNode {
  switch (b.type) {
    case "prose":
      return <Prose block={b} src={src} />;
    case "keyvalue_table":
      return <KvTable block={b} src={src} />;
    case "timeline":
      return <Timeline block={b} src={src} />;
    case "price_table":
      return <PriceTable block={b} src={src} />;
    case "card_grid":
      return <CardGrid block={b} src={src} />;
    case "steps":
      return <Steps block={b} />;
    case "quote":
      return <QuoteBlock block={b} src={src} />;
    case "fact_strip":
      return <FactStrip block={b} src={src} />;
    case "bar_chart":
      return <BarChart block={b} src={src} />;
    case "compare":
      return <Compare block={b} />;
    case "note":
      return <Note block={b} />;
    default:
      throw new Error(
        `模板不支持的区块类型 ${JSON.stringify((b as { type?: unknown }).type)}；` +
          `可用类型见 web/src/template/blocks.ts`,
      );
  }
}

export type SrcIndex = Map<string, Source>;

function Refs({ ids, src }: { ids?: string[]; src: SrcIndex }) {
  if (!ids || !ids.length) return null;
  return (
    <span className="refs">
      {ids.map((id) => {
        const s = src.get(id);
        if (!s) {
          throw new Error(`正文引用了不存在的来源 id ${id}（sources 里没有这条）`);
        }
        return (
          // <wbr/> 不是装饰：一串 "S0717S0720…" 之间没有任何空白，排版上就是**一个不可断的词**，
          // 引用一多就把标题撑到 358px > 版心 345px，G-13 判 clipped-scroller。
          // 之前试过给 .refs 加 overflow-wrap，那会从中间劈开编号（"S071|7"）；
          // 正确的做法是**造一个换行机会**而不是允许乱劈。
          <Fragment key={id}>
            <wbr />
            <a href={"#src-" + id} className="ref" title={s.label}>
              {id}
            </a>
          </Fragment>
        );
      })}
    </span>
  );
}

function asArr(v: unknown): any[] {
  return Array.isArray(v) ? v : [];
}
function asStr(v: unknown, fallback = ""): string {
  return typeof v === "string" ? v : fallback;
}


function headingOf(b: Block): ReactNode {
  const h = asStr(b.heading);
  return h ? <h3>{h}</h3> : null;
}
function titleOf(b: Block): ReactNode {
  const h = asStr(b.heading) || asStr(b.title);
  return h ? <h3>{h}</h3> : null;
}
function captionOf(b: Block): ReactNode {
  const c = asStr(b.caption);
  return c ? <caption>{c}</caption> : null;
}
function verdictOf(b: Block): ReactNode {
  const v = asStr(b.verdict);
  return v ? <div className="verdict">{v}</div> : null;
}

function Prose({ block, src }: { block: Block; src: SrcIndex }) {
  const paras = asStr(block.text)
    .split(/\n{2,}|\r\n{2,}/)
    .map((p) => p.trim())
    .filter(Boolean);
  return (
    <div className="blk">
      {headingOf(block)}
      {paras.map((p, i) => (
        <p key={i}>{p}</p>
      ))}
      <Refs ids={block.source_ids as string[] | undefined} src={src} />
    </div>
  );
}

function KvTable({ block, src }: { block: Block; src: SrcIndex }) {
  const rows = asArr(block.rows);
  return (
    <div className="blk">
      {headingOf(block)}
      <div className="tablewrap">
        <table>
          {captionOf(block)}
          <tbody>
            {rows.map((r: any, i: number) => (
              <tr key={i}>
                <td className="k">{r.k}</td>
                <td>
                  {r.v} <Refs ids={r.source_ids} src={src} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function Timeline({ block, src }: { block: Block; src: SrcIndex }) {
  return (
    <div className="blk">
      {headingOf(block)}
      <ol className="timeline">
        {asArr(block.items).map((it: any, i: number) => (
          <li key={i}>
            <span className="yr">{it.year}</span>
            {asStr(it.title) && <span className="tl-title">{it.title}</span>}
            <span>
              {it.text} <Refs ids={it.source_ids} src={src} />
            </span>
          </li>
        ))}
      </ol>
    </div>
  );
}

function PriceTable({ block, src }: { block: Block; src: SrcIndex }) {
  const cols = asArr(block.columns).map((c) => asStr(c));
  const rows = asArr(block.rows);
  return (
    <div className="blk">
      {headingOf(block)}
      <div className="tablewrap">
        <table>
          <caption>{`价格时点：${asStr(block.as_of)}（此后可能已调整）`}</caption>
          <thead>
            <tr>
              {cols.map((c, i) => (
                <th key={i}>{c}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((r: any, i: number) => (
              <tr key={i}>
                {asArr(r.cells).map((cell: unknown, j: number) => (
                  <td key={j} className={/\d/.test(String(cell)) ? "num" : undefined}>
                    {String(cell)}
                    {j === asArr(r.cells).length - 1 && (
                      <>
                        {" "}
                        <Refs ids={r.source_ids} src={src} />
                        {asStr(r.note) && <em>（{r.note}）</em>}
                      </>
                    )}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function CardGrid({ block, src }: { block: Block; src: SrcIndex }) {
  return (
    <div className="blk">
      {headingOf(block)}
      <div className="cards">
        {asArr(block.cards).map((c: any, i: number) => (
          <div className="card" key={i}>
            {asStr(c.kicker) && <div className="kick">{c.kicker}</div>}
            <h4>{c.title}</h4>
            <p>{c.body}</p>
            {asArr(c.metrics).length > 0 && (
              <div className="mets">
                {asArr(c.metrics).map((m: any, j: number) => (
                  <span key={j}>
                    {m.label} {m.value}
                    <Refs ids={m.source_ids} src={src} />
                  </span>
                ))}
              </div>
            )}
            <Refs ids={c.source_ids} src={src} />
          </div>
        ))}
      </div>
    </div>
  );
}

function Steps({ block }: { block: Block }) {
  return (
    <div className="blk">
      {titleOf(block)}
      <ol className="steps">
        {asArr(block.items).map((it: any, i: number) => (
          <li key={i}>
            <span className="sp-title">{it.title || `步骤 ${it.n ?? i + 1}`}</span>
            <span>{it.text}</span>
            {asStr(it.spec) && <span className="spec"> {it.spec}</span>}
          </li>
        ))}
      </ol>
    </div>
  );
}

function QuoteBlock({ block, src }: { block: Block; src: SrcIndex }) {
  const who = asStr(block.who);
  const when = asStr(block.when);
  return (
    <div className="blk">
      {headingOf(block)}
      <blockquote>
        {asStr(block.text)}
        {(who || when) && (
          <footer>
            {who}
            {who && when ? "，" : ""}
            {when} <Refs ids={block.source_ids as string[]} src={src} />
          </footer>
        )}
      </blockquote>
    </div>
  );
}

function FactStrip({ block, src }: { block: Block; src: SrcIndex }) {
  return (
    <div className="blk">
      {headingOf(block)}
      <div className="facts">
        {asArr(block.facts).map((f: any, i: number) => (
          <div className="f" key={i}>
            <div className="v">
              {f.value} <Refs ids={f.source_ids} src={src} />
            </div>
            <div className="l">{f.label}</div>
            {asStr(f.hint) && <div className="l">{f.hint}</div>}
          </div>
        ))}
      </div>
    </div>
  );
}

/**
 * 条形图。存在的理由：评分/价格/参数这类"要横向比"的数字，用表格读不出高低，
 * 而抓一张榜单截图进页面等于把数字交给读者自己去核（红线 R-02 不允许）。
 * 所以每根柱子自己带 source_ids，数字是画出来的、不是拍下来的。
 */
function BarChart({ block, src }: { block: Block; src: SrcIndex }) {
  const bars = asArr(block.bars) as any[];
  const declared = Number(block.max);
  const top = declared > 0 ? declared : Math.max(1, ...bars.map((b) => Number(b.value) || 0));
  const unit = asStr(block.unit);
  return (
    <div className="blk">
      {headingOf(block)}
      <div className="chart">
        {bars.map((b: any, i: number) => {
          const v = Number(b.value) || 0;
          // 截断坐标轴会把差距放大成视觉谎言，所以长度只按 top 算、不做"看起来更清楚"的调整
          const w = Math.max(0, Math.min(100, (v / top) * 100));
          return (
            <div className="row" key={i}>
              <div className="lab">{b.label}</div>
              <div className="track">
                <div className="bar" style={{ width: `${w.toFixed(2)}%` }} />
              </div>
              <div className="val">
                {v}
                {unit && <span className="unit">{unit}</span>} <Refs ids={b.source_ids} src={src} />
              </div>
            </div>
          );
        })}
        <div className="axis">
          {asStr(block.as_of) ? `榜单时点 ${block.as_of}` : ""}
          {asStr(block.as_of) && unit ? " · " : ""}
          {unit ? `刻度 ${unit}，最大值 ${top}` : `最大值 ${top}`}
        </div>
      </div>
    </div>
  );
}

function Compare({ block }: { block: Block }) {
  const side = (key: "left" | "right") => {
    const s: any = (block as any)[key] || { title: "", points: [] };
    return (
      <div className={"col " + (s.tone === "pro" ? "pro" : s.tone === "con" ? "con" : "")}>
        <h4>{s.title}</h4>
        <ul>
          {asArr(s.points).map((p: unknown, i: number) => (
            <li key={i}>{String(p)}</li>
          ))}
        </ul>
      </div>
    );
  };
  return (
    <div className="blk">
      {headingOf(block)}
      <div className="cmp">
        {side("left")}
        {side("right")}
        {verdictOf(block)}
      </div>
    </div>
  );
}

const NOTE_TITLES: Record<string, string> = {
  tip: "实操建议",
  warn: "注意",
  myth: "常见误解",
  glossary: "名词解释",
};

function Note({ block }: { block: Block }) {
  const tone = asStr(block.tone, "tip");
  return (
    <div className="blk">
      <div className={"note " + tone}>
        <h4>{asStr(block.heading) || asStr(block.title) || NOTE_TITLES[tone] || "提示"}</h4>
        <p>{asStr(block.text)}</p>
      </div>
    </div>
  );
}
