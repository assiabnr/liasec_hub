"use strict";

import { STATE, DOM_SELECTORS } from "./config.js";

export function setupSTT() {
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SR) return;

  STATE.recognition = new SR();
  STATE.recognition.lang = "fr-FR";
  STATE.recognition.interimResults = true;
  STATE.recognition.maxAlternatives = 3;
  STATE.recognition.continuous = true;

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

  STATE.recognition.onerror = (e) => {
    STATE.recognizing = false;
    DOM_SELECTORS.micBtn?.classList.remove("recording");
    showMicLabel(false);

    // Afficher un message d'erreur convivial
    if (e.error === 'no-speech') {
      showErrorFeedback("Aucune parole détectée. Réessayez.");
    } else if (e.error === 'audio-capture') {
      showErrorFeedback("Microphone non détecté.");
    } else if (e.error === 'not-allowed') {
      showErrorFeedback("Accès au microphone refusé.");
    } else {
      console.warn("Erreur de reconnaissance:", e.error);
    }
  };

  STATE.recognition.onresult = (e) => {
    let interimTranscript = '';
    let finalTranscript = '';

    for (let i = e.resultIndex; i < e.results.length; i++) {
      const result = e.results[i];
      const transcript = result[0].transcript;
      const confidence = result[0].confidence;

      if (result.isFinal) {
        // Filtrer les résultats avec une confiance trop basse
        if (confidence > 0.5) {
          finalTranscript += transcript;
        } else {
          console.log(`Résultat ignoré (confiance: ${confidence}): "${transcript}"`);
        }
      } else {
        interimTranscript += transcript;
      }
    }

    // Afficher les résultats intermédiaires dans l'input
    if (interimTranscript) {
      DOM_SELECTORS.chatInput.value = interimTranscript;
      updateMicLabel(interimTranscript, false);
    }

    // Quand le résultat est final
    if (finalTranscript) {
      DOM_SELECTORS.chatInput.value = finalTranscript;
      updateMicLabel(finalTranscript, true);
    }
  };
}

function showMicLabel(show) {
  if (show) {
    if (!STATE.micLabelEl) {
      STATE.micLabelEl = document.createElement("div");
      STATE.micLabelEl.className = "mic-listening-label";
      STATE.micLabelEl.innerHTML = `
        <div class="mic-label-content">
          <i class="bi bi-mic-fill"></i>
          <span class="mic-label-text">Écoute en cours…</span>
        </div>
      `;
      document.body.appendChild(STATE.micLabelEl);
    }
  } else if (STATE.micLabelEl) {
    STATE.micLabelEl.remove();
    STATE.micLabelEl = null;
  }
}

function updateMicLabel(text, isFinal) {
  if (STATE.micLabelEl) {
    const labelText = STATE.micLabelEl.querySelector('.mic-label-text');
    if (labelText) {
      if (isFinal) {
        labelText.innerHTML = `<i class="bi bi-check-circle-fill me-2"></i>"${text}"`;
        STATE.micLabelEl.classList.add('success');
      } else {
        labelText.textContent = `"${text}"`;
      }
    }
  }
}

function showErrorFeedback(message) {
  const errorEl = document.createElement("div");
  errorEl.className = "mic-error-feedback";
  errorEl.innerHTML = `
    <i class="bi bi-exclamation-triangle-fill"></i>
    <span>${message}</span>
  `;
  document.body.appendChild(errorEl);

  setTimeout(() => {
    errorEl.classList.add('show');
  }, 10);

  setTimeout(() => {
    errorEl.classList.remove('show');
    setTimeout(() => errorEl.remove(), 300);
  }, 3000);
}

export function startRecognition() {
  if (!STATE.recognition) {
    console.warn("Reconnaissance vocale non disponible");
    return;
  }
  if (STATE.recognizing) {
    return;
  }

  try {
    STATE.recognition.start();
  } catch (e) {
    console.error("Erreur au démarrage de la reconnaissance:", e);
    showErrorFeedback("Impossible de démarrer la reconnaissance vocale.");
  }
}

export function stopRecognition() {
  if (!STATE.recognition) {
    return;
  }
  if (STATE.recognizing) {
    STATE.recognition.stop();
  }
}

export function setupLongPressRecognition() {
  if (!DOM_SELECTORS.micBtn) {
    console.warn("Bouton micro non trouvé");
    return;
  }

  // Gestion souris
  DOM_SELECTORS.micBtn.addEventListener("mousedown", (e) => {
    e.preventDefault();
    startRecognition();
  });

  DOM_SELECTORS.micBtn.addEventListener("mouseup", (e) => {
    e.preventDefault();
    stopRecognition();
  });

  DOM_SELECTORS.micBtn.addEventListener("mouseleave", (e) => {
    if (STATE.recognizing) {
      stopRecognition();
    }
  });

  // Gestion tactile
  DOM_SELECTORS.micBtn.addEventListener("touchstart", (e) => {
    e.preventDefault();
    startRecognition();
  });

  DOM_SELECTORS.micBtn.addEventListener("touchend", (e) => {
    e.preventDefault();
    stopRecognition();
  });

  DOM_SELECTORS.micBtn.addEventListener("touchcancel", (e) => {
    if (STATE.recognizing) {
      stopRecognition();
    }
  });
}