import { renderToStaticMarkup } from "react-dom/server";
import { createElement } from "react";
import { TopicPage } from "./template/TopicPage";
import { IndexPage, css as indexCss } from "./template/IndexPage";
import { cssFor } from "./template/styles";
import { themeOf } from "./tokens";
import { BLOCK_TYPES } from "./template/blocks";
import type { IndexEntry, TopicData } from "./types";

export { BLOCK_TYPES };

/** 模板指纹：产物必须能证明自己是这份模板渲染的（validate.py G-08 用它比对）。 */
export const TEMPLATE_FINGERPRINT = JSON.stringify({
  blocks: BLOCK_TYPES,
  rev: "ke-template-1",
});

export function renderDocument(data: TopicData): string {
  const body = renderToStaticMarkup(createElement(TopicPage, { data, hideStyle: true }));
  // <style> 必须在 <head>：React SSR 会把组件树里的 style 当 body 子节点渲染出来，
  // 产物既不合规、又让"往 </head> 插样式"的写法被静默覆盖（本轮注错用例就踩过）。
  const style = "<style>" + cssFor(themeOf(data.theme.token)) + "</style>";
  return `<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>${escapeHtml(data.topic)} · ${escapeHtml(data.subtitle || "知识专题")}</title>
<meta name="description" content="${escapeHtml(data.subtitle || "")}">
<!--template-fingerprint:${TEMPLATE_FINGERPRINT}-->
${style}
</head>
<body>
${body}
</body>
</html>`;
}

/** 索引主页：一份自包含静态 HTML，卡片按 category 归类并下钻到各专题页。 */
export function renderIndexDocument(entries: IndexEntry[], generatedDate: string): string {
  const body = renderToStaticMarkup(
    createElement(IndexPage, { entries, generatedDate, hideStyle: true }),
  );
  const style = "<style>" + indexCss() + "</style>";
  return `<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>知识专题索引</title>
<meta name="description" content="按类别归档的科普长文索引，每篇约十分钟读完。">
<!--template-fingerprint:${TEMPLATE_FINGERPRINT}-->
<!--index-document-->
${style}
</head>
<body>
${body}
</body>
</html>`;
}

function escapeHtml(s: string): string {
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}
