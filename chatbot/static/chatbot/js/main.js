"use strict";

import { DOM_SELECTORS } from "./config.js";
import { bubble } from "./ui.js";
import { toggleVoice } from "./speech.js";
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

function init() {
  console.log("Init chatbot");

  setupSTT();
  initEventListeners();
  initInactivityListener();

  if (DOM_SELECTORS.feedbackDock) {
    DOM_SELECTORS.feedbackDock.innerHTML = "";
    DOM_SELECTORS.feedbackDock.classList.add("hidden");
  }

  bubble(DOM_SELECTORS.chatMessages, "bot", "Bonjour, je suis votre conseiller. Posez votre question.");
  resetInactivity();

  console.log("Chatbot prêt");
}

document.addEventListener("DOMContentLoaded", () => {
  init();
  initMapModal();
  initMapHighlight();
});