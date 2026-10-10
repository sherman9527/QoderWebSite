#!/usr/bin/env node
/**
 * 把 data.json 渲染成自包含静态 HTML。
 *
 * 做法：esbuild 把 TSX 打成一个 Node 可用的 ESM bundle → renderToStaticMarkup
 * → 一份纯静态 HTML。CSS 由模板生成后内联在 <style> 里，因此产物零外链、断网可看。
 * 见 openspec specs/golden-template 与 memo.md D-01 / D-C。
 *
 * 用法：node scripts/render.mjs --data output/咖啡/data.json --out output/咖啡/咖啡_2026-09-19.html
 *       node scripts/render.mjs --print-fingerprint    区块枚举 + rev + 模板源哈希
 *       node scripts/render.mjs --print-sources-hash   只打印模板源哈希（validate.py 取同一个值）
 */
import { mkdtempSync, readdirSync, readFileSync, writeFileSync, mkdirSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import { createRequire } from "node:module";
import { fileURLToPath, pathToFileURL } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(__dirname, "..");
const WEB = path.join(ROOT, "web");
const SSR_ENTRY = path.join(WEB, "src", "ssr-entry.tsx");

// 依赖装在 web/ 下，而本脚本在 scripts/ 下：Node 从脚本所在目录向上找 node_modules
// 是找不到的，所以显式以 web/ 为解析根。
const requireFromWeb = createRequire(path.join(WEB, "package.json"));
const { build } = requireFromWeb("esbuild");

function arg(name) {
  const i = process.argv.indexOf("--" + name);
  if (i < 0) return null;
  return process.argv[i + 1] || null;
}

/**
 * 模板源哈希：W-163。区块枚举 + rev 看不见改 CSS、改措辞、改组件内部——
 * 实测 `web/src` 30 次提交里只有 1 次动过 TEMPLATE_FINGERPRINT，剩下 29 次
 * G-08 一声不吭，产物可以永远不重渲染。
 * 哈希只在这里算（Python 侧调 `--print-sources-hash` 取同一个值），
 * 两边各写一遍迟早打架。
 */
function sourcesHash() {
  const crypto = requireFromWeb("node:crypto");
  const files = [];
  const walk = (dir) => {
    for (const e of readdirSync(dir, { withFileTypes: true })) {
      const p = path.join(dir, e.name);
      if (e.isDirectory()) walk(p);
      else if (/\.(ts|tsx|css)$/.test(e.name)) files.push(p);
    }
  };
  walk(path.join(WEB, "src"));
  files.sort();
  const h = crypto.createHash("sha256");
  for (const f of files) {
    h.update(path.relative(ROOT, f).split(path.sep).join("/"));
    h.update(readFileSync(f));
  }
  return h.digest("hex").slice(0, 12);
}

async function loadRenderer() {
  const outfile = path.join(mkdtempSync(path.join(tmpdir(), "ke-render-")), "ssr.mjs");
  await build({
    entryPoints: [SSR_ENTRY],
    bundle: true,
    format: "esm",
    platform: "node",
    target: "node18",
    outfile,
    jsx: "automatic",
    loader: { ".tsx": "tsx", ".ts": "ts" },
    // react-dom/server 的 CJS 分支里有动态 require('stream') 之类调用，
    // 打进 ESM 包后 Node 不认裸 require，补一个 createRequire 垫片。
    banner: {
      js: 'import{createRequire as __keCR}from"node:module";const require=__keCR(import.meta.url);',
    },
    logLevel: "silent",
  });
  return import(pathToFileURL(outfile).href);
}

async function main() {
  const dataPath = arg("data");
  const indexPath = arg("index");
  const outPath = arg("out");
  if (process.argv.includes("--print-sources-hash")) {
    process.stdout.write(sourcesHash());
    return;
  }

  const printOnly = process.argv.includes("--print-fingerprint");
  if (!dataPath && !indexPath && !printOnly) {
    console.error("用法: node scripts/render.mjs (--data <data.json> | --index <entries.json>) --out <out.html>");
    process.exit(2);
  }
  const mod = await loadRenderer();

  if (indexPath) {
    const payload = JSON.parse(readFileSync(path.resolve(indexPath), "utf8"));
    const html = mod.renderIndexDocument(payload.entries, payload.generated_date, {
      title: payload.title, homeUrl: payload.home_url,
    });
    mkdirSync(path.dirname(path.resolve(outPath)), { recursive: true });
    writeFileSync(path.resolve(outPath), html, "utf8");
    writeFileSync(path.resolve(outPath) + ".srchash", sourcesHash() + String.fromCharCode(10));
    console.error(
      `已渲染 ${outPath}（${payload.entries.length} 篇，${Buffer.byteLength(html, "utf8") / 1024 | 0} KB）`,
    );
    return;
  }

  if (printOnly) {
    process.stdout.write(mod.TEMPLATE_FINGERPRINT);
    return;
  }

  const data = JSON.parse(readFileSync(path.resolve(dataPath), "utf8"));
  const html = mod.renderDocument(data);

  // 自包含闸门在 Python 侧（validate.py G-04）做，这里先挡一道明显的漏网：
  const externalHit = /<(script|link)\b[^>]*\b(?:src|href)\s*=\s*["']https?:\/\//i.exec(html);
  if (externalHit) {
    console.error("渲染产物含外链资源，违反自包含要求：" + externalHit[0].slice(0, 120));
    process.exit(1);
  }

  mkdirSync(path.dirname(path.resolve(outPath)), { recursive: true });
  writeFileSync(path.resolve(outPath), html, "utf8");
  // 侧车按**页面文件**配对（`咖啡.html.srchash`），不按目录：闸门判的是 `.pending`，
  // 换名之后才写侧车会让 pending 阶段永远找不到它。W-163。
  writeFileSync(path.resolve(outPath) + ".srchash", sourcesHash() + String.fromCharCode(10));
  const kb = (Buffer.byteLength(html, "utf8") / 1024).toFixed(1);
  console.error(`已渲染 ${outPath}（${kb} KB，${data.sections.length} 章）`);
}

main().catch((e) => {
  console.error("渲染失败：" + (e && e.message ? e.message : e));
  process.exit(1);
});
