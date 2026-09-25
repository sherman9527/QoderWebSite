#!/usr/bin/env node
// 真浏览器截图 + 实测几何。用法：
//   node scripts/shot.mjs <html路径> [--widths 375,1440,2171] [--out .probe/shots] [--full]
// 输出：每张 <topic>_<w>.png，并在 stdout 打印该宽度下的实测几何（JSON 一行一档）。
// 与 measure-layout.mjs 的区别：那个只判定对错，这个给人（和模型）用眼睛看。
import { mkdirSync } from "node:fs";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { createRequire } from "node:module";

const require = createRequire(path.join(import.meta.dirname, "..", "web", "package.json"));
const { launch } = await import("./browser.mjs");

const argv = process.argv.slice(2);
const target = argv.find((a) => !a.startsWith("--"));
const opt = (name, dflt) => {
  const i = argv.indexOf(`--${name}`);
  return i >= 0 ? argv[i + 1] : dflt;
};
if (!target) {
  console.error("用法: node scripts/shot.mjs <html路径> [--widths a,b] [--out dir] [--full]");
  process.exit(2);
}
const widths = opt("widths", "375,768,1024,1440,2171,3762")
  .split(",")
  .map(Number)
  .filter(Boolean);
const outDir = opt("out", ".probe/shots");
const jsonOut = opt("json-out", null);   // 给基线比对用：把实测几何写成 JSON
const records = [];
let pending = 0;   // 跨视口累计：有任何一张没加载完，这一轮测量就不配当结论
const SETTLE_PASSES = Number(opt("settle-passes", 3));
const wantFull = argv.includes("--full");
mkdirSync(outDir, { recursive: true });

const file = pathToFileURL(path.resolve(target)).href;
const base = path.basename(target).replace(/\.html?$/i, "");

const browser = await launch();

for (const w of widths) {
  const page = await browser.newPage({ viewport: { width: w, height: Math.round(w * 0.62) } });
  await page.goto(file, { waitUntil: "load" });
  // 配图是 loading="lazy"：不滚一遍的话 naturalWidth 全是 0，
  // "破图"和"放大"两项量到的都只是首屏。
  await page.evaluate(async () => {
    const h = document.documentElement.scrollHeight;
    for (let y = 0; y < h; y += Math.max(300, innerHeight - 100)) {
      window.scrollTo(0, y);
      await new Promise((r) => setTimeout(r, 40));
    }
    window.scrollTo(0, 0);
  });
  // 粗滚一遍在大视口下会漏：Chromium 的懒加载按"离视口多远"决定要不要开始取，
  // 而这里步长是 innerHeight-100（@3762 等于 2232px 一跳）。09-24 实测同一份
  // 冻结快照 @3762 滚完还有 3 张 complete=false，逐张 scrollIntoView 之后才是 0。
  // 旧写法把这一步的失败咽掉了（`waitForFunction(...).catch(() => {})`），
  // 于是「还没加载完」被算进 brokenImgs，两次跑出 4 与 6 两个数字——
  // 一道随机器快慢变的闸门等于没有闸门：既会误伤，也会在最该响的时候沉默。
  for (let pass = 0; pass < SETTLE_PASSES; pass++) {
    const left = await page.evaluate(async () => {
      const stuck = [...document.images].filter((i) => !i.complete);
      for (const el of stuck) {
        el.scrollIntoView({ block: "center" });
        await new Promise((r) => setTimeout(r, 200));
      }
      window.scrollTo(0, 0);
      return [...document.images].filter((i) => !i.complete).length;
    });
    if (!left) break;
  }
  const unsettled = await page.evaluate(
    () => [...document.images].filter((i) => !i.complete).length);
  if (unsettled) {
    console.error(`@${w} 有 ${unsettled} 张图没加载完（滚到眼前仍未开始，`
      + `多半是 display:none 或解码超过 ${SETTLE_PASSES} 轮）——这一档的 brokenImgs 不可信`);
  }
  pending += unsettled;
  const m = await page.evaluate(() => {
    const cs = getComputedStyle(document.documentElement);
    const rect = (sel) => {
      const el = document.querySelector(sel);
      if (!el) return null;
      const r = el.getBoundingClientRect();
      return { x: Math.round(r.x), w: Math.round(r.width), h: Math.round(r.height) };
    };
    const imgs = [...document.images].map((i) => ({
      complete: i.complete,
      nw: i.naturalWidth,
      sel: Math.round(i.getBoundingClientRect().width),
      sh: Math.round(i.getBoundingClientRect().height),
      src: (i.currentSrc || i.src).split("/").slice(-2).join("/"),
    }));
    return {
      cssViewport: innerWidth,
      dpr: devicePixelRatio,
      docScrollW: document.documentElement.scrollWidth,
      bodyScrollH: document.documentElement.scrollHeight,
      pad: cs.getPropertyValue("--pad").trim(),
      col: cs.getPropertyValue("--col").trim(),
      rootFont: parseFloat(cs.fontSize),
      cover: rect(".cover-media"),
      wrap: rect(".wrap"),
      h1: rect(".cover-body h1"),
      firstFig: rect(".figs .ratio"),
      brokenImgs: imgs.filter((i) => i.complete && i.nw === 0).length,
      pendingImgs: imgs.filter((i) => !i.complete).length,
      zeroBoxImgs: imgs.filter((i) => i.complete && i.nw > 0 && (i.sel < 40 || i.sh < 20)).length,
      thinImgs: imgs
        .filter((i) => i.nw > 0 && i.sel > i.nw * 2.5)
        .slice(0, 3)
        .map((i) => `${i.nw}px 原图被放大到 ${i.sel}px: ${i.src}`),
      totalImgs: imgs.length,
    };
  });
  const shot = path.join(outDir, `${base}_${w}.png`);
  const BAND = 12000;
  const banded = wantFull && m.bodyScrollH > BAND;
  const shots = [];
  if (banded) {
    // Chromium 单张纹理上限是 16384px。超过之后 fullPage 会分块拼接，
    // 而拼接结果会从 16384 起把整页重复一遍——09-23 实测大模型篇（30514px）
    // 自相关 0.999 落在偏移 16384，肉眼看上去就是"文章出现了两次"。
    // 与其交给肉眼一张假的全页图，不如按带截取：每带都走 clip，不碰那个上限。
    const n = Math.ceil(m.bodyScrollH / BAND);
    for (let b = 0; b < n; b++) {
      const top = b * BAND;
      const height = Math.min(BAND, m.bodyScrollH - top);
      const bp = path.join(outDir, `${base}_${w}_band${b + 1}.png`);
      await page.screenshot({ path: bp, clip: { x: 0, y: top, width: w, height },
        fullPage: true });
      shots.push(bp);
    }
  } else {
    await page.screenshot({ path: shot, fullPage: !!wantFull });
    shots.push(shot);
  }
  records.push({ width: w, ...m });
  console.log(JSON.stringify({ width: w, shot, shots, fullBands: banded ? shots.length : 1, ...m }));
  await page.close();
}
await browser.close();
if (jsonOut) {
  // 基线只留"会因样式改动而变"的量，不留时间戳/路径，否则 diff 全是噪音
  const slim = records.map((r) => ({
    width: r.width,
    docScrollW: r.docScrollW,
    cover: r.cover, wrap: r.wrap, h1: r.h1, firstFig: r.firstFig,
    totalImgs: r.totalImgs, brokenImgs: r.brokenImgs,
  }));
  const fs = await import("node:fs");
  fs.mkdirSync(path.dirname(path.resolve(jsonOut)), { recursive: true });
  fs.writeFileSync(path.resolve(jsonOut), JSON.stringify(slim, null, 1), "utf8");
  console.error("几何基线已写出：" + jsonOut);
}
if (pending) {
  // 图和截图照样写（人要看得见页面长什么样），但退出码必须非 0：
  // 调用方（G-13 / 视觉基线）拿到"这一轮没测准"的信号，才不会把没加载完
  // 当成 0 破图通过，或反过来把没加载完当成破图判死。
  console.error(`✗ 共 ${pending} 张图没加载完，本轮几何不可信`);
  process.exitCode = 1;
}
