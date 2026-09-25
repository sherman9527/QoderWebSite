#!/usr/bin/env node
/**
 * 把 data.json 渲染成自包含静态 HTML。
 *
 * 做法：esbuild 把 TSX 打成一个 Node 可用的 ESM bundle → renderToStaticMarkup
 * → 一份纯静态 HTML。CSS 由模板生成后内联在 <style> 里，因此产物零外链、断网可看。
 * 见 openspec specs/golden-template 与 memo.md D-01 / D-C。
 *
 * 用法：node scripts/render.mjs --data output/咖啡/data.json --out output/咖啡/咖啡_2026-09-19.html
 */
import { mkdtempSync, readFileSync, writeFileSync, mkdirSync } from "node:fs";
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
  const printOnly = process.argv.includes("--print-fingerprint");
  if (!dataPath && !indexPath && !printOnly) {
    console.error("用法: node scripts/render.mjs (--data <data.json> | --index <entries.json>) --out <out.html>");
    process.exit(2);
  }
  const mod = await loadRenderer();

  if (indexPath) {
    const payload = JSON.parse(readFileSync(path.resolve(indexPath), "utf8"));
    const html = mod.renderIndexDocument(payload.entries, payload.generated_date);
    mkdirSync(path.dirname(path.resolve(outPath)), { recursive: true });
    writeFileSync(path.resolve(outPath), html, "utf8");
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
  const kb = (Buffer.byteLength(html, "utf8") / 1024).toFixed(1);
  console.error(`已渲染 ${outPath}（${kb} KB，${data.sections.length} 章）`);
}

main().catch((e) => {
  console.error("渲染失败：" + (e && e.message ? e.message : e));
  process.exit(1);
});
