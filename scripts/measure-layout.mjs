#!/usr/bin/env node
/**
 * G-13 布局几何闸门：真开浏览器量产物，而不是只看 DOM 里有没有这个元素。
 *
 * 为什么需要它：本项目的 pytest 一度 129 全绿，而页面上同时存在三个几何缺陷
 * （标题被 overflow:hidden 裁掉、配图被 max-height 反推成 614px 孤岛、
 *  长 token 把整页顶出横向滚动条）。它们没有一个是"元素不存在"，
 * 所以任何 DOM 断言都抓不到。尺寸只能用浏览器量。
 *
 * 用法：node scripts/measure-layout.mjs --file <html 绝对路径> [--json]
 * 退出码 0=通过，1=有 fail。
 */
import { createRequire } from "node:module";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(__dirname, "..");
const requireFromWeb = createRequire(path.join(ROOT, "web", "package.json"));
const { launch } = await import("./browser.mjs");

/** 要测的视口：手机、小平板、笔记本、常见桌面、2K/4K/超宽。 */
const WIDTHS = [375, 768, 1024, 1440, 1920, 2560, 3737];

/** 版心一致性只量"同一列里的块"：正文列的直接子元素必须左右对齐。
 *  外壳（.cover/.wrap/.layout）单独一组——它们比正文宽，是设计意图不是跑偏。 */
/* 第二组以前只量 `.body > *`，而每个区块都被包在 `.blk` 里 → 量到的全同宽，
   真正参差的是下一层（`.blk` 里的 `p` 44rem vs `.tablewrap` 撑满 68rem vs `.figs` 50rem），
   所以 W-81 那个"三条右边界"从这条规则底下滑过去了。现在把会各自设 max-width 的
   结构盒都拉进同一组比：谁再单独加一个宽度，这里就红。
   `.cmp` 的内层列、两图并排的单张图**不在组内**——它们本来就该比栏窄。 */
const COL_GROUPS = [[".cover", ".wrap", ".layout"],
  [".body > *", ".tablewrap", ".figs", ".note", ".cards", ".facts", ".chart", ".steps", ".timeline"]];

/** 正文行长上限。超过它，一行汉字就超过 40 个，宽屏上变成"一小戳字配一大片空白"。 */
const PROSE_MAX_PX = 820;
const PROSE_SELECTORS = ["p", "li", "blockquote", ".lede", ".note", ".chap-head h2", ".intro"];

/** 要查对比度的文字元素：正文、小字标签、表格、页脚——深色主题下最容易糊的就是这几类。 */
const CONTRAST_SELECTORS = [
  "p", "li", "h1", "h2", "h3", "h4", "td", "th", "figcaption",
  ".tag", ".meta", ".lede", ".note", ".foot", ".facts .l", ".facts .v",
  ".card .kick", ".card .mets span", ".chap-head .num", ".cover-kicker", ".srcs li",
  ".ph-word", ".chart .lab", ".chart .val", ".chart .axis",
];

function arg(name) {
  const i = process.argv.indexOf("--" + name);
  return i < 0 ? null : process.argv[i + 1];
}

/**
 * 产物里的配图是 loading="lazy"：没滚到就 naturalWidth=0，
 * 于是"图片放大"检查会**静默跳过整页下半部分**——这正是 G-13 要防的那类假绿。
 * 所以量之前先滚到底把所有图真正加载出来。
 */
async function forceLoadImages(page) {
  await page.evaluate(async () => {
    const h = document.documentElement.scrollHeight;
    for (let y = 0; y < h; y += Math.max(300, innerHeight - 100)) {
      window.scrollTo(0, y);
      await new Promise((r) => setTimeout(r, 40));
    }
    window.scrollTo(0, 0);
    await Promise.all([...document.images].map((i) => (i.complete
      ? 1
      : new Promise((res) => { i.onload = i.onerror = res; i.loading = "eager"; }))));
  });
  await page.waitForFunction(
    () => [...document.images].every((i) => i.complete),
    null, { timeout: 15000 },
  ).catch(() => {});
}

async function measurePage(file) {
  // 用开发者实际看页面的那颗内核（默认浏览器是 Edge），不是恰好装了哪颗
  const browser = await launch();
  const problems = [];
  try {
    const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
    await page.goto("file:///" + file.replace(/\\/g, "/"), { waitUntil: "load" });

    for (const w of WIDTHS) {
      await page.setViewportSize({ width: w, height: 900 });
      await page.evaluate(() => document.fonts && document.fonts.ready);
      await forceLoadImages(page);
      const tag = `@${w}px`;

      const r = await page.evaluate(
        ({ COL_GROUPS, PROSE_SELECTORS, PROSE_MAX_PX, CONTRAST_SELECTORS }) => {
          const de = document.documentElement;
          const out = {
            docScrollW: de.scrollWidth,
            docClientW: de.clientWidth,
            cols: [],
            prose: [],
            upscaled: [],
            tallFigs: [],
            lowContrast: [],
            scrollers: [],
            tracks: [],
            cover: null,
          };
          // 1) 版心一致性：同一组内的块必须左右对齐，否则说明有的块自己造宽度
          const groups = [];
          for (const sels of COL_GROUPS) {
            const cols = [];
            for (const sel of sels) {
              for (const el of document.querySelectorAll(sel)) {
                const b = el.getBoundingClientRect();
                if (b.width <= 0) continue;
                cols.push({ sel, left: b.left, right: b.right, width: b.width });
              }
            }
            if (cols.length > 1) groups.push(cols);
          }
          out.cols = groups;
          // 1a) 正文行长：宽屏上文字必须留在可读列里，图可以铺得更开
          for (const sel of PROSE_SELECTORS) {
            for (const el of document.querySelectorAll(sel)) {
              const b = el.getBoundingClientRect();
              if (b.width > PROSE_MAX_PX) {
                out.prose.push({ sel, w: b.width, text: (el.textContent || "").trim().slice(0, 18) });
              }
            }
          }
          // 1b) 图片不得放大到超过原图 1.35 倍——放大即糊，是"图不好看"的头号根因
          for (const im of document.images) {
            if (!im.complete || !im.naturalWidth) continue;
            const b = im.getBoundingClientRect();
            if (b.width > im.naturalWidth * 1.35) {
              out.upscaled.push({ nat: im.naturalWidth, shown: Math.round(b.width), src: (im.currentSrc || im.src).split("/").pop().slice(0, 40) });
            }
          }
          // 1c) 单张配图不得吃掉整屏
          for (const el of document.querySelectorAll(".ratio")) {
            const b = el.getBoundingClientRect();
            if (b.height > innerHeight * 0.8 && b.width > 200) {
              out.tallFigs.push({ w: Math.round(b.width), h: Math.round(b.height), vh: innerHeight });
            }
          }
          // 1d) 对比度：深色主题最容易悄悄糊掉（本项目真的出过 .note.warn 1.1:1 的事故）。
          //     几何检查看不见对比度，颜色检查看不见布局，所以两条都要有。
          const parseRGB = (s) => {
            const m = /rgba?\(([^)]+)\)/.exec(s || "");
            if (!m) return null;
            const p = m[1].split(",").map(parseFloat);
            return { r: p[0], g: p[1], b: p[2], a: p.length > 3 ? p[3] : 1 };
          };
          const lum = ({ r, g, b }) => {
            const f = (v) => (v /= 255) <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4);
            return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b);
          };
          const bgOf = (el) => {
            for (let n = el; n; n = n.parentElement) {
              const c = parseRGB(getComputedStyle(n).backgroundColor);
              if (c && c.a > 0.02) return c;
            }
            return { r: 255, g: 255, b: 255, a: 1 };
          };
          for (const sel of CONTRAST_SELECTORS) {
            for (const el of document.querySelectorAll(sel)) {
              const cs = getComputedStyle(el);
              const fg = parseRGB(cs.color);
              if (!fg || fg.a < 0.5) continue;
              if (!el.textContent || !el.textContent.trim()) continue;
              const b = el.getBoundingClientRect();
              if (b.width < 2 || b.height < 2) continue;
              const bg = bgOf(el);
              const [l1, l2] = [lum(fg), lum(bg)].sort((x, y) => y - x);
              const ratio = (l1 + 0.05) / (l2 + 0.05);
              const px = parseFloat(cs.fontSize);
              const large = px >= 24 || (px >= 18.66 && parseInt(cs.fontWeight || "400", 10) >= 700);
              const need = large ? 3.0 : 4.5;   // WCAG AA
              if (ratio < need) {
                out.lowContrast.push({
                  sel, ratio: +ratio.toFixed(2), need, px: Math.round(px),
                  fg: cs.color, bg: `rgb(${bg.r},${bg.g},${bg.b})`,
                  text: (el.textContent || "").trim().slice(0, 14),
                });
              }
            }
          }
          // 2) 滚动容器：内容超出但 overflow-x 不是 auto/scroll = 内容被删掉
          document.querySelectorAll("*").forEach((n) => {
            const cs = getComputedStyle(n);
            const ox = cs.overflowX;
            if (n.scrollWidth > n.clientWidth + 1 && ox !== "auto" && ox !== "scroll") {
              const b = n.getBoundingClientRect();
              if (b.width > 0 && b.height > 0) {
                out.scrollers.push({
                  sel: n.tagName + "." + (n.className || ""),
                  scrollW: n.scrollWidth, clientW: n.clientWidth, ox,
                });
              }
            }
          });
          // 3) 网格轨道等宽：同一行卡片宽度不等就是 min-width:auto 被顶开
          document.querySelectorAll(".cards,.facts,.cmp,.figs.c2,nav.toc ol").forEach((g) => {
            const cs = getComputedStyle(g);
            if (cs.display !== "grid") return;
            const tracks = cs.gridTemplateColumns.split(" ").map(parseFloat).filter((v) => v > 0);
            if (tracks.length > 1) {
              const mx = Math.max(...tracks), mn = Math.min(...tracks);
              out.tracks.push({ sel: g.className, tracks, spread: mx - mn });
            }
          });
          // 3a) 多列网格不得塌成单列。非法声明（例如嵌套 minmax）会被整条丢弃，
          //     计算值退化成 none → 卡片铺满整屏，而其它检查全都"看起来正常"。
          document.querySelectorAll(".cards,.facts,.cmp,.figs.c2,.feed").forEach((g) => {
            const cs = getComputedStyle(g);
            const kids = [...g.children].filter((k) => k.getBoundingClientRect().width > 0);
            if (cs.display !== "grid") {
              out.tracks.push({ sel: "grid-decl:" + g.className, tracks: [0], spread: 999 });
              return;
            }
            const tr = cs.gridTemplateColumns.split(" ").map(parseFloat).filter((v) => v > 0);
            if (tr.length === 0) {
              out.tracks.push({ sel: "collapsed:" + g.className, tracks: [0], spread: 999 });
            } else if (kids.length > 1 && tr.length < 2 && innerWidth >= 1024) {
              out.tracks.push({ sel: "single-track:" + g.className, tracks: tr, spread: 999 });
            }
          });
          // 3b) 单图配图必须铺满版心：max-height 会通过 aspect-ratio 反推宽度，
          //     让图变成版心里的一块孤岛（实测 614px 图 + 2528px 列宽）
          document.querySelectorAll(".figs").forEach((f) => {
            if (f.classList.contains("c2")) return;
            // 量 .ratio 本身：外层 <figure> 是块级，永远占满列宽，缩的是里面的比例盒
            const kids = [...f.querySelectorAll(".ratio")].filter((k) => k.getBoundingClientRect().width > 0);
            if (kids.length !== 1) return;
            const fw = f.getBoundingClientRect().width;
            const kw = kids[0].getBoundingClientRect().width;
            if (fw > 200 && kw < fw * 0.98) {
              out.tracks.push({ sel: "figs-single", tracks: [kw, fw], spread: fw - kw });
            }
          });
          // 4) 封面形状：不得随视口宽度变成一条缝，也不得吃掉整屏
          const cm = document.querySelector(".cover-media");
          if (cm) {
            const b = cm.getBoundingClientRect();
            out.cover = { w: b.width, h: b.height, ratio: b.width / b.height };
          }
          // 5) 关键文字必须真的看得见（尺寸非 0、未被父级裁掉）
          const h1 = document.querySelector("h1");
          if (h1) {
            const b = h1.getBoundingClientRect();
            let clippedBy = null;
            for (let p = h1.parentElement; p; p = p.parentElement) {
              const cs = getComputedStyle(p);
              if (cs.overflow === "hidden" || cs.overflowY === "hidden") {
                const pb = p.getBoundingClientRect();
                if (b.bottom > pb.bottom + 1 || b.right > pb.right + 1) { clippedBy = p.className; break; }
              }
            }
            out.h1 = { w: b.width, h: b.height, clippedBy };
          }
          return out;
        },
        { COL_GROUPS, PROSE_SELECTORS, PROSE_MAX_PX, CONTRAST_SELECTORS },
      );

      // ── 断言
      if (r.docScrollW > r.docClientW + 1) {
        problems.push({ gate: "overflow-x", tag, detail: `文档 ${r.docScrollW} > 视口 ${r.docClientW}` });
      }
      if (r.h1 && (r.h1.w < 2 || r.h1.h < 2)) {
        problems.push({ gate: "h1-invisible", tag, detail: JSON.stringify(r.h1) });
      }
      if (r.h1 && r.h1.clippedBy) {
        problems.push({ gate: "h1-clipped", tag, detail: `被 .${r.h1.clippedBy} 裁掉` });
      }
      for (const cols of r.cols) {
        const spread =
          Math.max(...cols.map((c) => c.left)) - Math.min(...cols.map((c) => c.left));
        const rspread =
          Math.max(...cols.map((c) => c.right)) - Math.min(...cols.map((c) => c.right));
        if (spread > 2 || rspread > 2) {
          problems.push({
            gate: "measure-inconsistent", tag,
            detail: `版心左右边不齐（左差 ${spread.toFixed(1)}，右差 ${rspread.toFixed(1)}）：`
              + cols.map((c) => `${c.sel}=${c.width.toFixed(0)}`).join(" "),
          });
        }
      }
      for (const s of r.scrollers.slice(0, 3)) {
        problems.push({ gate: "clipped-scroller", tag, detail: `${s.sel} 内容 ${s.scrollW} > 容器 ${s.clientW} 但 overflow-x=${s.ox}` });
      }
      for (const p of r.prose.slice(0, 3)) {
        problems.push({
          gate: "prose-measure", tag,
          detail: `${p.sel} 宽 ${p.w.toFixed(0)}px > 可读行长上限 ${PROSE_MAX_PX}px（"${p.text}…"）`,
        });
      }
      for (const u of r.upscaled.slice(0, 3)) {
        problems.push({ gate: "img-upscale", tag, detail: `${u.src} 原图 ${u.nat}px 被放大到 ${u.shown}px（糊）` });
      }
      const seenRatio = new Set();
      for (const c of r.lowContrast) {
        const key = c.sel + c.ratio;
        if (seenRatio.has(key)) continue;
        seenRatio.add(key);
        if (seenRatio.size > 4) break;
        problems.push({
          gate: "contrast", tag,
          detail: `${c.sel} 对比度 ${c.ratio}:1 < ${c.need}:1（${c.fg} on ${c.bg}，"${c.text}…"）`,
        });
      }
      for (const t of r.tallFigs.slice(0, 3)) {
        problems.push({ gate: "fig-wall", tag, detail: `配图 ${t.w}×${t.h}px 高于视口 ${t.vh}px 的 80%，吃掉整屏` });
      }
      for (const t of r.tracks) {
        if (t.spread > 2) {
          problems.push({ gate: "uneven-tracks", tag, detail: `.${t.sel} 同行轨道宽度不等：${t.tracks.map((v) => v.toFixed(0)).join("/")}px` });
        }
      }
      if (r.cover) {
        const { ratio, h } = r.cover;
        if (ratio > 7.5) problems.push({ gate: "cover-sliver", tag, detail: `封面被压成 ${ratio.toFixed(1)}:1 的一条缝` });
        if (h > 620) problems.push({ gate: "cover-wall", tag, detail: `封面高 ${h.toFixed(0)}px，吃掉整屏` });
      }
    }
  } finally {
    await browser.close();
  }
  return problems;
}

async function main() {
  const file = arg("file");
  if (!file) { console.error("用法: node scripts/measure-layout.mjs --file <html>"); process.exit(2); }
  let problems;
  try {
    problems = await measurePage(path.resolve(file));
  } catch (e) {
    // 浏览器不可用时不能算通过——否则 G-13 会静默失效，正是它要防的那类问题
    console.log(JSON.stringify({ ok: false, browserUnavailable: true, error: String(e && e.message || e) }));
    process.exit(3);
  }
  const ok = problems.length === 0;
  if (process.argv.includes("--json")) {
    console.log(JSON.stringify({ ok, widths: WIDTHS, problems }, null, 1));
  } else {
    for (const p of problems) console.log(`FAIL [G-13/${p.gate}] ${p.tag} ${p.detail}`);
    console.log(ok ? "布局几何检查通过" : `${problems.length} 个布局问题`);
  }
  process.exit(ok ? 0 : 1);
}
main();
