"use strict";

import { STATE, DOM_SELECTORS, API_URLS } from "./config.js";
import { getCookie, scrollBottom } from "./utils.js";

// Nouvelle fonction qui retourne un élément feedback (pas dans une bubble)
export function createFeedbackElement() {
  if (DOM_SELECTORS.feedbackDock) {
    DOM_SELECTORS.feedbackDock.innerHTML = "";
    DOM_SELECTORS.feedbackDock.classList.add("hidden");
  }

  const feedbackDiv = document.createElement("div");
  feedbackDiv.className = "feedback";
  feedbackDiv.style.marginTop = "16px";
  feedbackDiv.innerHTML = `
    <p class="feedback-text">Ce produit correspond-il à vos attentes ?</p>
    <div class="feedback-buttons">
      <button class="feedback-button primary">
        <img src="/static/chatbot/images/icons/like.svg" alt="Oui" /> Oui
      </button>
      <button class="feedback-button secondary">
        <img src="/static/chatbot/images/icons/dislike.svg" alt="Non" /> Non
      </button>
    </div>
  `;

  const [btnYes, btnNo] = feedbackDiv.querySelectorAll(".feedback-button");
  const lock = () => {
    btnYes.disabled = true;
    btnNo.disabled = true;
  };

  btnYes.addEventListener("click", async (e) => {
    e.stopPropagation();
    lock();
    await sendFeedback(true);
    btnYes.style.opacity = "1";
    btnNo.style.opacity = "0.4";
  });

  btnNo.addEventListener("click", async (e) => {
    e.stopPropagation();
    lock();
    await sendFeedback(false);
    btnNo.style.opacity = "1";
    btnYes.style.opacity = "0.4";
  });

  return feedbackDiv;
}

// Ancienne fonction maintenue pour compatibilité si nécessaire
export function showFeedbackBlock(chatMessages) {
  if (DOM_SELECTORS.feedbackDock) {
    DOM_SELECTORS.feedbackDock.innerHTML = "";
    DOM_SELECTORS.feedbackDock.classList.add("hidden");
  }

  const wrap = document.createElement("div");
  wrap.className = "message bot";
  wrap.innerHTML = `
    <div class="bubble">
      <div class="feedback">
        <p class="feedback-text">Ce produit correspond-il à vos attentes ?</p>
        <div class="feedback-buttons">
          <button class="feedback-button primary">
            <img src="/static/chatbot/images/icons/like.svg" alt="Oui" /> Oui
          </button>
          <button class="feedback-button secondary">
            <img src="/static/chatbot/images/icons/dislike.svg" alt="Non" /> Non
          </button>
        </div>
      </div>
    </div>`;
  chatMessages.appendChild(wrap);
  scrollBottom(chatMessages);

  const [btnYes, btnNo] = wrap.querySelectorAll(".feedback-button");
  const lock = () => {
    btnYes.disabled = true;
    btnNo.disabled = true;
  };

  btnYes.addEventListener("click", async (e) => {
    e.stopPropagation();
    lock();
    await sendFeedback(true);
    btnYes.style.opacity = "1";
    btnNo.style.opacity = "0.4";
  });

  btnNo.addEventListener("click", async (e) => {
    e.stopPropagation();
    lock();
    await sendFeedback(false);
    btnNo.style.opacity = "1";
    btnYes.style.opacity = "0.4";
  });
}

async function sendFeedback(positive) {
  if (!STATE.lastInteractionId) return;
  try {
    await fetch(API_URLS.feedback, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": getCookie("csrftoken") || "",
      },
      body: JSON.stringify({
        interaction_id: STATE.lastInteractionId,
        feedback: positive ? "positive" : "negative",
      }),
    });
  } catch (err) {
    console.error("Erreur feedback:", err);
  }
}