"use strict";

import { STATE, DOM_SELECTORS, API_URLS } from "./config.js";
import { getCookie, scrollBottom } from "./utils.js";
import { bubble, loaderBubble } from "./ui.js";
import { speak } from "./speech.js";
import { hardResetChat } from "./chat.js";

// Fonction pour afficher la popup d'escalade après 2 feedbacks négatifs
function showEscaladePopup() {
  console.log("[POPUP] Affichage popup d'escalade");
  const existingPopup = document.querySelector(".escalade-popup");
  if (existingPopup) {
    console.log("[POPUP] Suppression de la popup existante");
    existingPopup.remove();
  }

  const popup = document.createElement("div");
  popup.className = "escalade-popup";
  popup.style.cssText = `
    position: fixed;
    left: 0;
    right: 0;
    top: 0;
    bottom: 0;
    background-color: rgba(0, 0, 0, 0.5);
    backdrop-filter: blur(4px);
    display: flex;
    justify-content: center;
    align-items: center;
    z-index: 9999;
    font-family: "Poppins", sans-serif;
  `;
  popup.innerHTML = `
    <div class="escalade-popup-container" style="
      background-color: #ffffff;
      border-radius: 36px;
      padding: 50px;
      max-width: 750px;
      width: 90%;
      text-align: center;
      box-shadow: 0 8px 30px rgba(0, 0, 0, 0.2);
    ">
      <img src="/static/chatbot/images/icons/warning.svg" alt="Alerte" style="
        width: 100px;
        height: 100px;
        margin: 0 auto 30px auto;
        display: block;
      " />
      <p style="
        font-weight: 400;
        font-size: 1.25rem;
        color: #111827;
        margin: 0;
        line-height: 1.8;
      ">
        <strong>Nous n'avons pas réussi à répondre à votre besoin.</strong><br>
        Nous vous recommandons de consulter un conseiller humain.
      </p>
      <div style="
        display: flex;
        flex-direction: row;
        justify-content: center;
        gap: 30px;
        margin-top: 60px;
        flex-wrap: wrap;
      ">
        <button class="button button-secondary" id="escalade-home" style="min-width: 250px; width: auto;">Retour à l'accueil</button>
        <button class="button button-primary" id="escalade-continue" style="min-width: 250px; width: auto;">Continuer la conversation</button>
      </div>
    </div>
  `;
  document.body.appendChild(popup);
  console.log("[POPUP] Popup d'escalade ajoutée au DOM");

  document.getElementById("escalade-home").addEventListener("click", () => {
    window.location.href = "/";
  });

  document.getElementById("escalade-continue").addEventListener("click", () => {
    popup.remove();

    // Réinitialisation des champs de saisie pour poursuivre
    if (DOM_SELECTORS.chatInput) {
      DOM_SELECTORS.chatInput.disabled = false;
      DOM_SELECTORS.chatInput.focus();
    }
    if (DOM_SELECTORS.sendBtn) DOM_SELECTORS.sendBtn.disabled = false;

    const text = "Très bien, poursuivons ensemble. N'hésitez pas à me préciser votre besoin.";
    bubble(DOM_SELECTORS.chatMessages, "bot", text);
    speak(text);
    scrollBottom(DOM_SELECTORS.chatMessages);
  });
}

// Fonction pour afficher la popup de nouvelle recherche
function showNewSearchPopup() {
  console.log("[POPUP] Affichage popup nouvelle recherche");
  const existingPopup = document.querySelector(".new-search-popup");
  if (existingPopup) {
    console.log("[POPUP] Suppression de la popup existante");
    existingPopup.remove();
  }

  const popup = document.createElement("div");
  popup.className = "escalade-popup new-search-popup";
  popup.style.cssText = `
    position: fixed;
    left: 0;
    right: 0;
    top: 0;
    bottom: 0;
    background-color: rgba(0, 0, 0, 0.5);
    backdrop-filter: blur(4px);
    display: flex;
    justify-content: center;
    align-items: center;
    z-index: 9999;
    font-family: "Poppins", sans-serif;
  `;
  popup.innerHTML = `
    <div class="escalade-popup-container" style="
      background-color: #ffffff;
      border-radius: 36px;
      padding: 50px;
      max-width: 750px;
      width: 90%;
      text-align: center;
      box-shadow: 0 8px 30px rgba(0, 0, 0, 0.2);
    ">
      <img src="/static/chatbot/images/icons/question.svg" alt="Nouvelle recherche" style="
        width: 100px;
        height: 100px;
        margin: 0 auto 30px auto;
        display: block;
      " />
      <p style="
        font-weight: 400;
        font-size: 1.25rem;
        color: #111827;
        margin: 0;
        line-height: 1.8;
      ">
        Souhaitez-vous faire une nouvelle recherche ?
      </p>
      <div style="
        display: flex;
        flex-direction: row;
        justify-content: center;
        gap: 30px;
        margin-top: 60px;
        flex-wrap: wrap;
      ">
        <button class="button button-primary" id="new-search-yes" style="min-width: 250px; width: auto;">Oui</button>
        <button class="button button-secondary" id="new-search-no" style="min-width: 250px; width: auto;">Non</button>
      </div>
    </div>
  `;
  document.body.appendChild(popup);
  console.log("[POPUP] Popup nouvelle recherche ajoutée au DOM");

  document.getElementById("new-search-no").addEventListener("click", () => {
    window.location.href = "/";
  });

  document.getElementById("new-search-yes").addEventListener("click", async () => {
    popup.remove();

    // Réinitialiser la conversation
    try {
      await hardResetChat();
    } catch (err) {
      console.error("Erreur lors du reset:", err);
      // Fallback si hardResetChat échoue
      window.location.reload();
    }
  });
}

// Nouvelle fonction qui retourne un élément feedback (pas dans une bubble)
export function createFeedbackElement() {
  if (DOM_SELECTORS.feedbackDock) {
    DOM_SELECTORS.feedbackDock.innerHTML = "";
    DOM_SELECTORS.feedbackDock.classList.add("hidden");
  }

  const feedbackDiv = document.createElement("div");
  feedbackDiv.className = "feedback";
  feedbackDiv.style.cssText = "margin-top: 16px; max-width: 600px; margin-left: auto; margin-right: auto;";
  feedbackDiv.innerHTML = `
    <p class="feedback-text" style="text-align: center; margin-bottom: 16px;">Ce produit correspond-il à vos attentes ?</p>
    <div class="feedback-buttons" style="display: flex; justify-content: center; gap: 20px; flex-wrap: wrap;">
      <button class="feedback-button primary" style="flex: 0 1 auto; min-width: 200px; max-width: 300px;">
        <img src="/static/chatbot/images/icons/like.svg" alt="Oui" /> Oui
      </button>
      <button class="feedback-button secondary" style="flex: 0 1 auto; min-width: 200px; max-width: 300px;">
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
    await sendFeedback(true, feedbackDiv);
    btnYes.style.opacity = "1";
    btnNo.style.opacity = "0.4";
  });

  btnNo.addEventListener("click", async (e) => {
    e.stopPropagation();
    lock();
    await sendFeedback(false, feedbackDiv);
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
        <div class="feedback-buttons" style="display: flex; justify-content: center; gap: 20px; flex-wrap: wrap;">
          <button class="feedback-button primary" style="flex: 0 1 auto; min-width: 200px; max-width: 300px;">
            <img src="/static/chatbot/images/icons/like.svg" alt="Oui" /> Oui
          </button>
          <button class="feedback-button secondary" style="flex: 0 1 auto; min-width: 200px; max-width: 300px;">
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
    await sendFeedback(true, wrap);
    btnYes.style.opacity = "1";
    btnNo.style.opacity = "0.4";
  });

  btnNo.addEventListener("click", async (e) => {
    e.stopPropagation();
    lock();
    await sendFeedback(false, wrap);
    btnNo.style.opacity = "1";
    btnYes.style.opacity = "0.4";
  });
}

async function sendFeedback(positive, feedbackElement) {
  if (!STATE.lastInteractionId) {
    console.warn("Pas d'interaction_id, abandon du feedback");
    return;
  }

  console.log(`[FEEDBACK] Envoi feedback: ${positive ? 'positif' : 'négatif'}`);

  // Créer un message de chargement
  const loading = loaderBubble(DOM_SELECTORS.chatMessages);
  scrollBottom(DOM_SELECTORS.chatMessages);

  // Désactiver tous les boutons de feedback
  const allFeedbackButtons = document.querySelectorAll(".feedback-button");
  allFeedbackButtons.forEach((button) => {
    button.disabled = true;
  });

  try {
    // Envoyer le feedback au backend
    await fetch(API_URLS.feedback, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": getCookie("csrftoken") || "",
      },
      body: JSON.stringify({
        interaction_id: STATE.lastInteractionId,
        satisfaction: positive,
      }),
    });

    // Gérer le compteur de feedbacks négatifs
    if (!positive) {
      STATE.negativeFeedbackCount++;
      console.log(`[FEEDBACK] Compteur négatif: ${STATE.negativeFeedbackCount}`);
    } else {
      STATE.negativeFeedbackCount = 0;
      console.log(`[FEEDBACK] Feedback positif - compteur réinitialisé`);
    }

    // Si 2 feedbacks négatifs consécutifs, afficher popup d'escalade
    if (STATE.negativeFeedbackCount >= 2) {
      console.log("[FEEDBACK] 2 feedbacks négatifs → Affichage popup d'escalade");
      loading.remove();
      showEscaladePopup();
      return;
    }

    // Envoyer un message automatique au bot selon le feedback
    const autoMessage = positive
      ? "Merci, cette recommandation convient à mes attentes."
      : "Merci pour votre recommandation, cependant elle ne correspond pas à mes attentes. Veuillez me reposer des questions pour affiner votre recherche, ou recommandez-moi un nouveau produit qui correspondra à mes attentes.";

    const response = await fetch(API_URLS.chat, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": getCookie("csrftoken") || "",
      },
      body: JSON.stringify({ message: autoMessage }),
    });

    const data = await response.json();
    loading.remove();

    if (data.response) {
      const botMessage = data.response;
      bubble(DOM_SELECTORS.chatMessages, "bot", botMessage);
      speak(botMessage);
      scrollBottom(DOM_SELECTORS.chatMessages);
    }

    // Gérer l'interface selon le type de feedback
    if (!positive) {
      // Si feedback négatif, réactiver le champ de saisie
      console.log("[FEEDBACK] Réactivation du champ de saisie");
      if (DOM_SELECTORS.chatInput) {
        DOM_SELECTORS.chatInput.disabled = false;
        DOM_SELECTORS.chatInput.focus();
      }
      if (DOM_SELECTORS.sendBtn) DOM_SELECTORS.sendBtn.disabled = false;
    } else {
      // Si feedback positif, afficher popup de nouvelle recherche après 15 secondes
      console.log("[FEEDBACK] Feedback positif → Timer de 15s pour popup nouvelle recherche");
      setTimeout(() => {
        console.log("[FEEDBACK] 15 secondes écoulées → Affichage popup nouvelle recherche");
        showNewSearchPopup();
      }, 15000);
    }
  } catch (err) {
    console.error("[FEEDBACK] Erreur:", err);
    loading.remove();
  }
}