"use strict";

import { scrollBottom } from "./utils.js";

export function bubble(chatMessages, role, html) {
  const wrap = document.createElement("div");
  wrap.className = `message ${role === "user" ? "user" : "bot"}`;
  wrap.innerHTML = `<div class="bubble">${html}</div>`;
  chatMessages.appendChild(wrap);
  scrollBottom(chatMessages);
  return wrap;
}

export function loaderBubble(chatMessages) {
  const el = document.createElement("div");
  el.className = "message bot";
  el.innerHTML =
    '<div class="bubble"><span class="bouncing-dots"><span></span><span></span><span></span></span></div>';
  chatMessages.appendChild(el);
  scrollBottom(chatMessages);
  return el;
}