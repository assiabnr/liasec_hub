"use strict";

import { STATE, DOM_SELECTORS } from "./config.js";

export function setupSTT() {
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SR) return;

  STATE.recognition = new SR();
  STATE.recognition.lang = "fr-FR";
  STATE.recognition.interimResults = false;
  STATE.recognition.maxAlternatives = 1;

  STATE.recognition.onstart = () => {
    STATE.recognizing = true;
    DOM_SELECTORS.micBtn?.classList.add("recording");
    showMicLabel(true);
  };

  STATE.recognition.onend = () => {
    STATE.recognizing = false;
    DOM_SELECTORS.micBtn?.classList.remove("recording");
    showMicLabel(false);
  };

  STATE.recognition.onerror = () => {
    STATE.recognizing = false;
    DOM_SELECTORS.micBtn?.classList.remove("recording");
    showMicLabel(false);
  };

  STATE.recognition.onresult = (e) => {
    const t = e.results[0][0].transcript;
    DOM_SELECTORS.chatInput.value = t;

    // Déclencher l'envoi via un événement personnalisé pour éviter la dépendance circulaire
    const sendEvent = new Event('triggerSendMessage');
    document.dispatchEvent(sendEvent);
  };
}

function showMicLabel(show) {
  if (show) {
    if (!STATE.micLabelEl) {
      STATE.micLabelEl = document.createElement("div");
      STATE.micLabelEl.className = "mic-listening-label";
      STATE.micLabelEl.textContent = "Écoute en cours…";
      document.body.appendChild(STATE.micLabelEl);
    }
  } else if (STATE.micLabelEl) {
    STATE.micLabelEl.remove();
    STATE.micLabelEl = null;
  }
}

export function toggleRecognition() {
  if (!STATE.recognition) {
    console.warn("Reconnaissance vocale non disponible");
    return;
  }
  if (STATE.recognizing) {
    STATE.recognition.stop();
    return;
  }
  STATE.recognition.start();
}