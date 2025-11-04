"use strict";

/* =========================================================
   CONFIGURATION GLOBALE
========================================================= */
const messages = document.getElementById("messages");
const input = document.getElementById("chat-form-input");
const sendBtn = document.querySelector(".chat-send");
const micBtn = document.querySelector(".chat-mic");
const resetBtn = document.querySelector(".chat-reset");
const soundBtn = document.querySelector(".chat-sound");
const feedbackContainer = document.getElementById("feedback-container");

let lastInteractionId = null;
let isTyping = false;
let voiceEnabled = true;
let recognition;
let recognizing = false;
let micPressed = false;

// URL du chatbot
window.CHAT_API_URL = window.CHAT_API_URL || "/chatbot/api/ask/";
const CHATBOT_HOME_URL = "/chatbot/";

/* =========================================================
   CSRF UTILITY
========================================================= */
function getCookie(name) {
  let cookieValue = null;
  if (document.cookie && document.cookie !== "") {
    const cookies = document.cookie.split(";");
    for (let cookie of cookies) {
      cookie = cookie.trim();
      if (cookie.startsWith(name + "=")) {
        cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
        break;
      }
    }
  }
  return cookieValue;
}

/* =========================================================
   SYNTHÈSE VOCALE
========================================================= */
function speakText(text) {
  if (!voiceEnabled || !("speechSynthesis" in window)) return;
  const utterance = new SpeechSynthesisUtterance(text);
  utterance.lang = "fr-FR";
  utterance.rate = 1.1;
  utterance.pitch = 1;
  speechSynthesis.cancel();
  speechSynthesis.speak(utterance);
}

/* =========================================================
   AFFICHAGE DES MESSAGES
========================================================= */
function appendMessage(sender, text) {
  const msgDiv = document.createElement("div");
  msgDiv.classList.add("message", sender);

  const bubble = document.createElement("div");
  bubble.classList.add("bubble");
  bubble.innerHTML = text.replace(/\n/g, "<br>");

  if (sender === "bot") {
    const avatar = document.createElement("div");
    avatar.classList.add("avatar");
    avatar.innerHTML = `<img src="/static/chatbot/images/bot.png" alt="Bot">`;
    msgDiv.appendChild(avatar);
  }

  msgDiv.appendChild(bubble);
  messages.appendChild(msgDiv);
  scrollToBottom();
}

function scrollToBottom() {
  messages.scrollTop = messages.scrollHeight;
}

/* =========================================================
   ENVOI DU MESSAGE
========================================================= */
async function sendMessage() {
  const text = input.value.trim();
  if (!text || isTyping) return;

  appendMessage("user", text);
  input.value = "";
  input.disabled = true;
  sendBtn.disabled = true;
  isTyping = true;

  const loadingBubble = document.createElement("div");
  loadingBubble.classList.add("message", "bot");
  loadingBubble.innerHTML = `
    <div class="bubble loading">
      <div class="bouncing-dots"><span></span><span></span><span></span></div>
    </div>`;
  messages.appendChild(loadingBubble);
  scrollToBottom();

  try {
    const response = await fetch(CHAT_API_URL, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": getCookie("csrftoken"),
      },
      body: JSON.stringify({ message: text }),
    });

    const data = await response.json();
    loadingBubble.remove();

    let answer = data.response || "Je n’ai pas compris, pouvez-vous reformuler ?";
    appendMessage("bot", answer);
    speakText(answer);

    if (data.interaction_id) {
      lastInteractionId = data.interaction_id;
      showEnhancedFeedback(); // ✅ remplace l'ancien système par le nouveau
    }

  } catch (error) {
    console.error(error);
    loadingBubble.remove();
    appendMessage("bot", "Erreur réseau, veuillez réessayer.");
  } finally {
    input.disabled = false;
    sendBtn.disabled = false;
    isTyping = false;
    input.focus();
  }
}
/* =========================================================
   🎨 FEEDBACK MODERNE (boutons rectangulaires + icônes)
========================================================= */
function showEnhancedFeedback() {
  if (!lastInteractionId) return;

  const composer = document.querySelector(".composer");
  if (composer) {
    composer.style.visibility = "hidden";
    composer.style.pointerEvents = "none";
    composer.style.opacity = "0";
  }

  const feedbackDiv = document.createElement("div");
  feedbackDiv.classList.add("message", "bot", "feedback-bubble");
  feedbackDiv.innerHTML = `
    <div class="bubble feedback-box">
      <p>Cette réponse vous a-t-elle aidé ?</p>
      <div class="toast-buttons">
        <button class="button button-rect button-secondary btn-yes">
          <i class="bi bi-emoji-smile-fill"></i>
          <span>Oui</span>
        </button>
        <button class="button button-rect button-primary btn-no">
          <i class="bi bi-emoji-frown-fill"></i>
          <span>Non</span>
        </button>
      </div>
    </div>
  `;
  messages.appendChild(feedbackDiv);
  scrollToBottom();

  const yesBtn = feedbackDiv.querySelector(".btn-yes");
  const noBtn = feedbackDiv.querySelector(".btn-no");

  yesBtn.addEventListener("click", () => sendEnhancedFeedback(lastInteractionId, 5, feedbackDiv));
  noBtn.addEventListener("click", () => sendEnhancedFeedback(lastInteractionId, 1, feedbackDiv));
}

/* =========================================================
   🎨 FEEDBACK MODERNE (style popup rectangulaire)
========================================================= */
function showEnhancedFeedback() {
  if (!lastInteractionId) return;

  const composer = document.querySelector(".composer");
  if (composer) {
    composer.style.visibility = "hidden";
    composer.style.pointerEvents = "none";
    composer.style.opacity = "0";
  }

  const feedbackDiv = document.createElement("div");
  feedbackDiv.classList.add("message", "bot", "feedback-bubble");
  feedbackDiv.innerHTML = `
    <div class="bubble feedback-box">
      <p>Cette réponse vous a-t-elle aidé ?</p>
      <div class="toast-buttons">
        <button class="button button-secondary btn-yes">
          <i class="bi bi-emoji-smile-fill"></i>
          <span>Oui</span>
        </button>
        <button class="button button-primary btn-no">
          <i class="bi bi-emoji-frown-fill"></i>
          <span>Non</span>
        </button>
      </div>
    </div>
  `;

  messages.appendChild(feedbackDiv);
  scrollToBottom();

  const yesBtn = feedbackDiv.querySelector(".btn-yes");
  const noBtn = feedbackDiv.querySelector(".btn-no");

  // ✅ Envoie vrai ou faux selon le clic
  yesBtn.addEventListener("click", () => sendEnhancedFeedback(lastInteractionId, true, feedbackDiv));
  noBtn.addEventListener("click", () => sendEnhancedFeedback(lastInteractionId, false, feedbackDiv));
}

async function sendEnhancedFeedback(interactionId, satisfactionValue, feedbackDiv) {
  try {
    const response = await fetch("/chatbot/api/feedback/", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        interaction_id: interactionId,
        satisfaction: satisfactionValue, // ✅ true ou false selon le clic
      }),
    });

    if (!response.ok) throw new Error(`HTTP ${response.status}`);

    const data = await response.json();
    console.log("✅ Feedback enregistré :", data);

    const bubble = feedbackDiv.querySelector(".feedback-box");
bubble.innerHTML = `
  <p class="feedback-thanks visible">
    <i class="bi bi-check-circle-fill" style="color:#3B82F6; margin-right:6px;"></i>
    <span style="color:#0b132b; font-weight:600;">Merci pour votre avis&nbsp;!</span>
  </p>`;

    // Animation de disparition douce
    setTimeout(() => {
      bubble.classList.add("fade-out");
      setTimeout(() => feedbackDiv.remove(), 800);
    }, 2500);

  } catch (err) {
    console.error("Erreur feedback :", err);
    const bubble = feedbackDiv.querySelector(".feedback-box");
    bubble.innerHTML = `
      <p class="feedback-thanks visible text-danger">
         Erreur d’envoi, merci quand même
      </p>`;

    setTimeout(() => {
      bubble.classList.add("fade-out");
      setTimeout(() => feedbackDiv.remove(), 800);
    }, 2500);

  } finally {
    setTimeout(() => {
      const composer = document.querySelector(".composer");
      if (composer) {
        composer.style.visibility = "visible";
        composer.style.pointerEvents = "auto";
        composer.style.opacity = "1";
      }
      input.disabled = false;
      sendBtn.disabled = false;
      input.focus();
      scrollToBottom();
    }, 2500);
  }
}


/* =========================================================
   🧩 STYLE FEEDBACK — cohérent avec popups
========================================================= */
const style = document.createElement("style");
style.innerHTML = `
  .feedback-bubble .bubble {
    background: var(--white);
    border: 2px solid #d8d8d8;
    border-radius: 16px;
    padding: 1.2rem;
    box-shadow: var(--shadow);
    max-width: 420px;
    animation: fadeSlideIn 0.4s ease forwards;
  }

  .feedback-bubble p {
    margin: 0 0 1rem;
    font-weight: 600;
    color: var(--text);
    text-align: center;
    font-size: 1.05rem;
  }

  .toast-buttons {
    display: flex;
    justify-content: center;
    gap: 16px;
    flex-wrap: wrap;
  }

  .button {
    border: none;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 10px;
    padding: 12px 26px;
    border-radius: 12px;
    font-size: 1rem;
    font-weight: 600;
    font-family: "Poppins", sans-serif;
    color: #fff;
    box-shadow: var(--shadow);
    cursor: pointer;
    transition: all 0.25s ease;
  }

  .button i {
    font-size: 1.3rem;
    margin-right: 6px;
  }

  .button-primary {
    background: linear-gradient(135deg, #f86f0b 0%, #ffb700 100%);
    border: 2px solid #e67c0a;
    box-shadow: 0 4px 10px rgba(248, 111, 11, 0.35);
  }
  .button-primary:hover {
    background: linear-gradient(135deg, #fc8020 0%, #ffc836 100%);
    box-shadow: 0 8px 18px rgba(248, 111, 11, 0.5);
    transform: translateY(-2px);
  }

  .button-secondary {
    background: linear-gradient(135deg, #445be8 0%, #4f90f0 100%);
    border: 2px solid #3040df;
    box-shadow: 0 4px 10px rgba(68, 91, 232, 0.35);
  }
  .button-secondary:hover {
    background: linear-gradient(135deg, #5563ff 0%, #3143f0 100%);
    box-shadow: 0 8px 18px rgba(68, 91, 232, 0.5);
    transform: translateY(-2px);
  }

  .feedback-thanks {
    color: #0b7043;
    font-weight: 600;
    text-align: center;
    font-size: 1.1rem;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 0.4rem;
    opacity: 0;
    transform: scale(0.9);
    transition: opacity 0.4s ease, transform 0.4s ease;
  }

  .feedback-thanks.visible {
    opacity: 1;
    transform: scale(1);
  }

  .feedback-thanks.fade-out {
    opacity: 0;
    transform: scale(0.95);
  }

  .feedback-thanks i {
    color: #ff3366;
    font-size: 1.3rem;
  }

  @keyframes fadeSlideIn {
    from { opacity: 0; transform: translateY(10px); }
    to { opacity: 1; transform: translateY(0); }
  }
`;
document.head.appendChild(style);



/* =========================================================
   🎙️ RECONNAISSANCE VOCALE (Push-to-talk)
========================================================= */
function initVoiceRecognition() {
  if (!("webkitSpeechRecognition" in window || "SpeechRecognition" in window)) {
    console.warn("Reconnaissance vocale non supportée");
    if (micBtn) micBtn.classList.add("disabled");
    return;
  }

  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  recognition = new SpeechRecognition();
  recognition.lang = "fr-FR";
  recognition.continuous = false;
  recognition.interimResults = true;

  let finalTranscript = "";

  recognition.onstart = () => {
    recognizing = true;
    finalTranscript = "";
    micBtn.classList.add("recording");
    showListeningLabel();
  };

  recognition.onresult = (event) => {
    let interimTranscript = "";
    for (let i = event.resultIndex; i < event.results.length; ++i) {
      const transcript = event.results[i][0].transcript;
      if (event.results[i].isFinal) finalTranscript += transcript + " ";
      else interimTranscript += transcript;
    }
    input.value = (finalTranscript + interimTranscript).trim();
  };

  recognition.onerror = (e) => {
    console.warn("Erreur vocale :", e.error);
    stopMicVisual();
  };

  recognition.onend = () => {
    recognizing = false;
    stopMicVisual();
    hideListeningLabel();
    if (input.value.trim()) showReadyToSendLabel();
  };
}

/* =========================================================
   VISUELS MICRO / ÉTATS
========================================================= */
function showListeningLabel() {
  const label = document.createElement("div");
  label.className = "mic-listening-label";
  label.innerHTML = `<i class="bi bi-mic-fill" style="margin-right:8px;"></i> Parlez maintenant...`;
  document.body.appendChild(label);
}

function hideListeningLabel() {
  const label = document.querySelector(".mic-listening-label");
  if (label) label.remove();
}

function showReadyToSendLabel() {
  const label = document.createElement("div");
  label.className = "mic-ready-label";
  label.textContent = "Message vocal prêt à envoyer";
  document.body.appendChild(label);
  setTimeout(() => label.remove(), 2500);
}

function stopMicVisual() {
  micBtn.classList.remove("recording");
}

/* =========================================================
   Événements microphone
========================================================= */
if (micBtn) {
  micBtn.addEventListener("mousedown", () => {
    if (recognition && !recognizing) {
      micPressed = true;
      recognition.start();
    }
  });
  micBtn.addEventListener("mouseup", () => {
    if (recognition && recognizing) {
      micPressed = false;
      recognition.stop();
    }
  });
  micBtn.addEventListener("touchstart", (e) => {
    e.preventDefault();
    if (recognition && !recognizing) {
      micPressed = true;
      recognition.start();
    }
  });
  micBtn.addEventListener("touchend", (e) => {
    e.preventDefault();
    if (recognition && recognizing) {
      micPressed = false;
      recognition.stop();
    }
  });
}


/* =========================================================
   🔊 CONTRÔLE DU SON (Activation + Panneau volume)
========================================================= */
let voiceVolume = 1; // Volume par défaut

function toggleSound() {
  voiceEnabled = !voiceEnabled;
  const iconBtn = document.getElementById("soundToggle");
  const slider = document.querySelector("#volume-slider");

  if (voiceEnabled) {
    iconBtn.classList.remove("muted");
    if (slider) {
      slider.disabled = false;
      slider.classList.remove("disabled");
    }
  } else {
    speechSynthesis.cancel();
    iconBtn.classList.add("muted");
    if (slider) {
      slider.disabled = true;
      slider.classList.add("disabled");
    }
  }
}

// Crée et affiche le panneau
function createSoundPanel() {
  // éviter doublon
  const existingPanel = document.querySelector(".sound-panel");
  if (existingPanel) return;

  const panel = document.createElement("div");
  panel.className = "sound-panel";
  panel.innerHTML = `
    <div class="sound-header">
      <h4>Contrôle vocal</h4>
      <button class="close-sound-panel">×</button>
    </div>
    <div class="sound-body">
      <label for="volume-slider">Volume : <span id="volume-value">${voiceEnabled ? Math.round(voiceVolume * 100) + "%" : "0%"}</span></label>
      <input type="range" id="volume-slider" min="0" max="1" step="0.05" value="${voiceEnabled ? voiceVolume : 0}" ${voiceEnabled ? "" : "disabled"}>
<button class="mute-toggle">
  ${voiceEnabled 
    ? '<i class="bi bi-volume-up-fill"></i> Désactiver' 
    : '<i class="bi bi-volume-mute-fill"></i> Activer'}
</button>
    </div>
  `;
  document.body.appendChild(panel);

  // Fermeture
  panel.querySelector(".close-sound-panel").addEventListener("click", () => {
    panel.classList.add("hide");
    setTimeout(() => panel.remove(), 250);
  });

  // Volume slider
  const slider = panel.querySelector("#volume-slider");
  const valueText = panel.querySelector("#volume-value");
  slider.addEventListener("input", (e) => {
    voiceVolume = parseFloat(e.target.value);
    valueText.textContent = Math.round(voiceVolume * 100) + "%";
  });

  // Bouton Mute/Unmute
  const muteBtn = panel.querySelector(".mute-toggle");
  muteBtn.addEventListener("click", () => {
  toggleSound();

  // Change l’icône + texte selon l’état
  muteBtn.innerHTML = voiceEnabled
    ? `<i class="bi bi-volume-up-fill"></i> Désactiver`
    : `<i class="bi bi-volume-mute-fill"></i> Activer`;

  valueText.textContent = voiceEnabled ? Math.round(voiceVolume * 100) + "%" : "0%";
  slider.value = voiceEnabled ? voiceVolume : 0;
});

}

// Parole du bot
function speakText(text) {
  if (!voiceEnabled || !("speechSynthesis" in window)) return;
  const utterance = new SpeechSynthesisUtterance(text);
  utterance.lang = "fr-FR";
  utterance.volume = voiceVolume;
  utterance.rate = 1.1;
  utterance.pitch = 1;
  speechSynthesis.cancel();
  speechSynthesis.speak(utterance);
}

// Bouton principal volume
const soundToggle = document.getElementById("soundToggle");
if (soundToggle) {
  soundToggle.addEventListener("click", createSoundPanel);
}

/* =========================================================
   🔁 RESET DU CHAT
========================================================= */
if (resetBtn) {
  resetBtn.addEventListener("click", () => {
    showResetConfirmationPopup();
  });
}

function showResetConfirmationPopup() {
  const existing = document.querySelector(".reset-popup");
  if (existing) existing.remove();

  const popup = document.createElement("div");
  popup.classList.add("reset-popup");
  popup.style.cssText = `
    position: fixed; inset: 0;
    background: rgba(0,0,0,0.55);
    display: flex; align-items: center; justify-content: center;
    z-index: 9999;
  `;

popup.innerHTML = `
  <div class="reset-content">
    <h3>Réinitialiser la conversation ?</h3>
    <p>Cette action effacera l’historique du chat. Êtes-vous sûr ?</p>
    <div class="popup-buttons">
      <button id="confirm-reset" class="button button-primary">Oui, réinitialiser</button>
      <button id="cancel-reset" class="button button-secondary">Annuler</button>
    </div>
  </div>
`;

  document.body.appendChild(popup);

  popup.querySelector("#confirm-reset").addEventListener("click", () => {
    popup.remove();
    cleanUp();
    sendSessionEnd();
    window.location.href = CHATBOT_HOME_URL;
  });

  popup.querySelector("#cancel-reset").addEventListener("click", () => popup.remove());
}

/* =========================================================
   💤 INACTIVITÉ + POPUP
========================================================= */
let inactivityTimer;
let countdownTimer;
const inactivityDelay = 90 * 1000;
const countdownDuration = 15;

function resetInactivityTimer() {
  clearTimeout(inactivityTimer);
  clearInterval(countdownTimer);
  inactivityTimer = setTimeout(showInactivityPopup, inactivityDelay);
}

function showInactivityPopup() {
  const popup = document.createElement("div");
  popup.classList.add("reset-popup");
 popup.innerHTML = `
    <div class="reset-content">
      <h3>Souhaitez-vous continuer la conversation ?</h3>
      <p>Retour automatique dans <span id="countdown">${countdownDuration}</span> secondes...</p>
      <div class="popup-buttons">
        <button id="continue-chat" class="button button-secondary">Continuer</button>
        <button id="reset-chat" class="button button-primary">Retour à l’accueil</button>
      </div>
    </div>
  `;
  document.body.appendChild(popup);

  let remaining = countdownDuration;
  const countdownDisplay = popup.querySelector("#countdown");
  countdownTimer = setInterval(() => {
    remaining--;
    countdownDisplay.textContent = remaining;
    if (remaining <= 0) {
      clearInterval(countdownTimer);
      popup.remove();
      cleanUp();
      sendSessionEnd();
      window.location.href = CHATBOT_HOME_URL;
    }
  }, 1000);

  popup.querySelector("#continue-chat").addEventListener("click", () => {
    clearInterval(countdownTimer);
    popup.remove();
    resetInactivityTimer();
  });

  popup.querySelector("#reset-chat").addEventListener("click", () => {
    clearInterval(countdownTimer);
    popup.remove();
    cleanUp();
    sendSessionEnd();
    window.location.href = CHATBOT_HOME_URL;
  });
}

/* =========================================================
   CLEANUP / FIN SESSION
========================================================= */
function cleanUp() {
  clearInterval(countdownTimer);
  clearTimeout(inactivityTimer);
  messages.innerHTML = "";
  input.value = "";
  input.disabled = false;
  sendBtn.disabled = false;
  speechSynthesis.cancel();
}

function sendSessionEnd() {
  try {
    const csrfToken = getCookie("csrftoken");
    const blob = new Blob([JSON.stringify({})], { type: "application/json" });
    navigator.sendBeacon("/chatbot/api/reset/", blob);
  } catch (err) {
    console.error("Erreur lors de la fermeture de session :", err);
  }
}

/* =========================================================
   INIT
========================================================= */
document.addEventListener("DOMContentLoaded", () => {
  appendMessage("bot", "Bonjour, je suis votre conseiller virtuel. En quoi puis-je vous aider aujourd’hui ?");
  initVoiceRecognition();
  ["click", "mousemove", "keydown", "touchstart"].forEach(evt =>
    document.addEventListener(evt, resetInactivityTimer)
  );
  resetInactivityTimer();
});

window.addEventListener("beforeunload", sendSessionEnd);
