"use strict";

export function getCookie(name) {
  let v = null;
  if (!document.cookie) return v;
  document.cookie.split(";").forEach((c) => {
    const [k, ...rest] = c.trim().split("=");
    if (k === name) v = decodeURIComponent(rest.join("="));
  });
  return v;
}

export function scrollBottom(element) {
  element.scrollTop = element.scrollHeight;
}

export function sanitize(s) {
  if (!s) return "";
  const collapsed = s.replace(/(.{1,4})\1{10,}/g, "$1");
  return collapsed.replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

export function renderMarkdownLite(text) {
  let html = sanitize(text);

  html = html.replace(/!\[([^\]]*)\]\(([^)]+)\)/g, (_m, alt, url) => {
    return `<img src="${sanitize(url)}" alt="${sanitize(
      alt
    )}" style="max-width:100%;border-radius:8px;margin:6px 0;">`;
  });

  html = html.replace(/\[([^\]]+)\]\((https?:\/\/[^)]+)\)/g, (_m, lbl, url) => {
    return `<a href="${sanitize(url)}" target="_blank">${sanitize(lbl)}</a>`;
  });

  html = html.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
  html = html.replace(/\*([^*]+)\*/g, "<em>$1</em>");
  html = html.replace(/\n/g, "<br>");

  return html;
}

export function extractIntroOnly(answer) {
  const idx = answer.indexOf("\n1.");
  if (idx > 0) return answer.slice(0, idx).trim();
  const lines = answer.split("\n");
  return lines[0].trim();
}