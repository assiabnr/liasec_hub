"use strict";

import { DOM_SELECTORS } from "./config.js";
import { typingBubble } from "./ui.js";
import { toggleVoice, speak, initializeDefaultVoice } from "./speech.js";
import { setupSTT, toggleRecognition } from "./recognition.js";
import { resetInactivity, initInactivityListener } from "./inactivity.js";
import { sendMessage, hardResetChat } from "./chat.js";
import { initMapModal, initMapHighlight } from "./map.js";

function initEventListeners() {
  DOM_SELECTORS.sendBtn?.addEventListener("click", sendMessage);

  DOM_SELECTORS.chatInput?.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  });

  DOM_SELECTORS.resetBtn?.addEventListener("click", hardResetChat);

  DOM_SELECTORS.soundBtn?.addEventListener("click", () => {
    const enabled = toggleVoice();
    DOM_SELECTORS.soundBtn.classList.toggle("muted", !enabled);
  });

  DOM_SELECTORS.micBtn?.addEventListener("click", toggleRecognition);

  document.addEventListener("triggerSendMessage", sendMessage);
}

async function init() {
  console.log("Init chatbot");

  setupSTT();
  initEventListeners();
  initInactivityListener();

  if (DOM_SELECTORS.feedbackDock) {
    DOM_SELECTORS.feedbackDock.innerHTML = "";
    DOM_SELECTORS.feedbackDock.classList.add("hidden");
  }

  // Attendre que la voix masculine par défaut soit initialisée
  await initializeDefaultVoice();

  // Utiliser l'effet de frappe pour le message de bienvenue avec synthèse vocale
  typingBubble(
    DOM_SELECTORS.chatMessages,
    "Bonjour, je suis votre conseiller virtuel. Comment puis-je vous aider ?",
    () => speak("Bonjour, je suis votre conseiller virtuel. Comment puis-je vous aider ?")
  );
  resetInactivity();

  console.log("Chatbot prêt");
}

document.addEventListener("DOMContentLoaded", () => {
  init();
  initMapModal();
  initMapHighlight();
});