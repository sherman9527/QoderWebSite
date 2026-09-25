/**
 * 浏览器选择：量几何要用**开发者实际看页面的那颗内核**。
 * 开发者默认浏览器是 Edge，所以 msedge 优先；装了才用，没装退回 chrome，
 * 再没有就用 playwright 自带的 chromium。KE_CHROME_CHANNEL 可强制指定。
 */
import { createRequire } from "node:module";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(__dirname, "..");
const requireFromWeb = createRequire(path.join(ROOT, "web", "package.json"));
const { chromium } = requireFromWeb("playwright-core");

const CANDIDATES = [
  ["msedge", "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe"],
  ["msedge", "C:/Program Files/Microsoft/Edge/Application/msedge.exe"],
  ["chrome", "C:/Program Files/Google/Chrome/Application/chrome.exe"],
  ["chrome", "C:/Program Files (x86)/Google/Chrome/Application/chrome.exe"],
];

export function resolveChannel() {
  const forced = process.env.KE_CHROME_CHANNEL || process.env.SHOT_CHANNEL;
  if (forced) return forced;
  for (const [channel, exe] of CANDIDATES) {
    if (fs.existsSync(exe)) return channel;
  }
  return "chromium";
}

export function launch() {
  const channel = resolveChannel();
  return chromium.launch({
    channel: channel === "chromium" ? undefined : channel,
    args: ["--allow-file-access-from-files"],
  });
}
