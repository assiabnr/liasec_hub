"use strict";

import { STATE, INACTIVITY_CONFIG, API_URLS } from "./config.js";
import { getCookie } from "./utils.js";
import { hardResetChat } from "./chat.js";

const INDEX_URL = window.INDEX_URL || "/";
const IS_LOCALISATION_PAGE = window.IS_LOCALISATION_PAGE === true;
const RESET_LABEL = IS_LOCALISATION_PAGE ? "Retour à l'accueil" : "Réinitialiser";

/**
 * Reset de la session côté backend (appel API_URLS.reset).
 * Ne touche pas à l'UI : utilisable partout (chatbot + localisation).
 */
async function resetBackendSession() {
  try {
    await fetch(API_URLS.reset, {
      method: "POST",
      headers: { "X-CSRFToken": getCookie("csrftoken") || "" },
    });
  } catch (err) {
    console.error("Erreur reset (backend):", err);
  }
}

/**
 * Best-effort reset lors d'un refresh / fermeture d'onglet.
 * Utilise sendBeacon si possible (plus fiable dans beforeunload).
 */
function sendResetBeacon() {
  if (!("sendBeacon" in navigator) || !API_URLS?.reset) {
    return false;
  }
  try {
    const data = new FormData();
    const token = getCookie("csrftoken");
    if (token) {
      // Django peut lire ce token comme dans un formulaire classique
      data.append("csrfmiddlewaretoken", token);
    }
    data.append("reason", "unload");
    navigator.sendBeacon(API_URLS.reset, data);
    return true;
  } catch (err) {
    console.error("Erreur sendBeacon reset:", err);
    return false;
  }
}

/**
 * Ajoute un handler global pour terminer la session quand la page est rechargée
 * (F5 / Ctrl+R) ou fermée.
 */
function setupUnloadReset() {
  window.addEventListener("beforeunload", () => {
    const ok = sendResetBeacon();
    if (!ok) {
      // Fallback best-effort (la requête peut être interrompue par le navigateur)
      resetBackendSession();
    }
  });
}

function ensureInactivityPopup() {
  if (STATE.inactivityPopup) return STATE.inactivityPopup;

  const overlay = document.createElement("div");
  overlay.className = "reset-popup";
  overlay.style.display = "none";
  overlay.innerHTML = `
    <div class="reset-content">
      <h3>Vous êtes toujours là ?</h3>
      <p>La session sera réinitialisée dans <strong id="ia-countdown">${INACTIVITY_CONFIG.countdownSec}</strong> s.</p>
      <div class="popup-buttons">
        <button class="button button-secondary" id="ia-continue">Continuer</button>
        <button class="button button-primary" id="ia-reset">${RESET_LABEL}</button>
      </div>
    </div>`;
  document.body.appendChild(overlay);

  overlay
    .querySelector("#ia-continue")
    .addEventListener("click", () => {
      hideInactivityPopup();
      resetInactivity();
    });

  overlay.querySelector("#ia-reset").addEventListener("click", async () => {
    // Arrêter toute synthèse vocale en cours
    if (window.speechSynthesis) {
      window.speechSynthesis.cancel();
    }

    // Reset backend uniquement (pas besoin de reset UI si on redirige)
    await resetBackendSession();

    hideInactivityPopup();
    window.location.href = INDEX_URL; // retour à l'accueil dans tous les cas
  });

  STATE.inactivityPopup = overlay;
  return overlay;
}

function showInactivityPopup() {
  const o = ensureInactivityPopup();
  o.style.display = "flex";
  const label = o.querySelector("#ia-countdown");
  let left = INACTIVITY_CONFIG.countdownSec;
  label.textContent = left;

  clearInterval(STATE.inactivityCountdownTimer);
  STATE.inactivityCountdownTimer = setInterval(async () => {
    left -= 1;
    label.textContent = left;
    if (left <= 0) {
      clearInterval(STATE.inactivityCountdownTimer);

      // Arrêter toute synthèse vocale en cours
      if (window.speechSynthesis) {
        window.speechSynthesis.cancel();
      }

      // Reset backend uniquement (pas besoin de reset UI si on redirige)
      await resetBackendSession();

      hideInactivityPopup();
      window.location.href = INDEX_URL;
    }
  }, 1000);
}

function hideInactivityPopup() {
  const o = ensureInactivityPopup();
  o.style.display = "none";
  clearInterval(STATE.inactivityCountdownTimer);
}

export function resetInactivity() {
  clearTimeout(STATE.inactivityTimer);
  STATE.inactivityTimer = setTimeout(
    showInactivityPopup,
    INACTIVITY_CONFIG.popupAfterSec * 1000
  );
}

export function initInactivityListener() {
  ["click", "keydown", "mousemove", "scroll", "touchstart"].forEach((evt) =>
    document.addEventListener(evt, resetInactivity, { passive: true })
  );

  // Ajout : reset de la session sur refresh / fermeture
  setupUnloadReset();
}
