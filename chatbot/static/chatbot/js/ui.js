"use strict";

import { scrollBottom } from "./utils.js";
import { STATE } from "./config.js";

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

// Nouvelle fonction pour créer une bulle avec effet de frappe
export function typingBubble(chatMessages, html, speakText, callback) {
  const wrap = document.createElement("div");
  wrap.className = "message bot";
  const bubbleDiv = document.createElement("div");
  bubbleDiv.className = "bubble typing"; // Ajouter la classe typing pour le curseur
  wrap.appendChild(bubbleDiv);
  chatMessages.appendChild(wrap);
  scrollBottom(chatMessages);

  // Marquer que le bot est en train d'écrire
  STATE.isTyping = true;

  // Extraire le texte brut du HTML
  const tempDiv = document.createElement("div");
  tempDiv.innerHTML = html;
  const text = tempDiv.textContent || tempDiv.innerText || "";

  // Démarrer la synthèse vocale EN MÊME TEMPS que le typing
  if (speakText && typeof speakText === 'function') {
    speakText();
  }

  let index = 0;
  const speed = 80; // Millisecondes par caractère - ralenti pour synchronisation avec la voix

  function typeChar() {
    if (index < text.length) {
      // Ajouter caractère par caractère
      bubbleDiv.textContent = text.substring(0, index + 1);
      index++;
      scrollBottom(chatMessages);
      setTimeout(typeChar, speed);
    } else {
      // Fin de l'animation - remplacer par le HTML complet et retirer la classe typing
      bubbleDiv.classList.remove("typing");
      bubbleDiv.innerHTML = html;
      STATE.isTyping = false;
      scrollBottom(chatMessages);
      if (callback) callback();
    }
  }

  typeChar();
  return wrap;
}