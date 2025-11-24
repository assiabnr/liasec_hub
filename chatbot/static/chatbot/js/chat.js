"use strict";

import { STATE, DOM_SELECTORS, API_URLS } from "./config.js";
import { getCookie, sanitize, renderMarkdownLite, extractIntroOnly, scrollBottom } from "./utils.js";
import { bubble, loaderBubble } from "./ui.js";
import { speak } from "./speech.js";
import { createProductCarousel } from "./carousel.js";
import { showFeedbackBlock } from "./feedback.js";

export async function sendMessage() {
  const text = DOM_SELECTORS.chatInput.value.trim();
  if (!text || STATE.isSending) return;

  STATE.isSending = true;
  bubble(DOM_SELECTORS.chatMessages, "user", sanitize(text));
  DOM_SELECTORS.chatInput.value = "";
  if (DOM_SELECTORS.sendBtn) DOM_SELECTORS.sendBtn.disabled = true;

  const loading = loaderBubble(DOM_SELECTORS.chatMessages);

  try {
    const r = await fetch(API_URLS.chat, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": getCookie("csrftoken") || "",
      },
      body: JSON.stringify({ message: text }),
    });

    if (!r.ok) {
      console.error("Erreur API:", await r.text());
      loading.remove();
      bubble(DOM_SELECTORS.chatMessages, "bot", "Désolé, une erreur est survenue.");
      return;
    }

    const data = await r.json();
    loading.remove();

    const answer = data.response || "Je n'ai pas compris.";
    const apiRecs = Array.isArray(data.recommendations) ? data.recommendations : [];

    if (apiRecs.length > 0) {
      const introOnly = extractIntroOnly(answer);
      if (introOnly && introOnly.length > 0) {
        bubble(DOM_SELECTORS.chatMessages, "bot", renderMarkdownLite(introOnly));
        speak(introOnly);
      }
      const carousel = createProductCarousel(apiRecs);
      if (carousel) {
        DOM_SELECTORS.chatMessages.appendChild(carousel);
        scrollBottom(DOM_SELECTORS.chatMessages);
      }
    } else {
      bubble(DOM_SELECTORS.chatMessages, "bot", renderMarkdownLite(answer));
      speak(answer);
    }

    if (data.interaction_id) {
      STATE.lastInteractionId = data.interaction_id;
      if (data.ask_feedback || apiRecs.length) {
        showFeedbackBlock(DOM_SELECTORS.chatMessages);
      }
    }
  } catch (err) {
    console.error("Erreur:", err);
    loading.remove();
    bubble(DOM_SELECTORS.chatMessages, "bot", "Erreur réseau.");
  } finally {
    if (DOM_SELECTORS.sendBtn) DOM_SELECTORS.sendBtn.disabled = false;
    STATE.isSending = false;
  }
}

export async function hardResetChat() {
  try {
    await fetch(API_URLS.reset, {
      method: "POST",
      headers: { "X-CSRFToken": getCookie("csrftoken") || "" },
    });
  } catch (err) {
    console.error("Erreur reset:", err);
  }
  DOM_SELECTORS.chatMessages.innerHTML = "";
  STATE.lastInteractionId = null;
  bubble(DOM_SELECTORS.chatMessages, "bot", "Bonjour, je suis votre conseiller. Posez votre question.");
}