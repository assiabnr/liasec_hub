"use strict";

import { STATE, DOM_SELECTORS, API_URLS } from "./config.js";
import { getCookie, sanitize, renderMarkdownLite, extractIntroOnly, scrollBottom } from "./utils.js";
import { bubble, loaderBubble, typingBubble } from "./ui.js";
import { speak, initializeDefaultVoice } from "./speech.js";
import { createProductCarousel } from "./carousel.js";
import { createFeedbackElement } from "./feedback.js";

export async function sendMessage() {
  const text = DOM_SELECTORS.chatInput.value.trim();
  // Empêcher l'envoi si déjà en cours d'envoi OU si le bot est en train d'écrire
  if (!text || STATE.isSending || STATE.isTyping) return;

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
        // Utiliser l'effet de frappe pour le bot avec synthèse vocale en parallèle
        typingBubble(
          DOM_SELECTORS.chatMessages,
          renderMarkdownLite(introOnly),
          () => speak(introOnly), // Parler EN MÊME TEMPS que le typing
          () => {
            // Afficher le carousel après le typing
            const carousel = createProductCarousel(apiRecs);
            if (carousel) {
              DOM_SELECTORS.chatMessages.appendChild(carousel);
              scrollBottom(DOM_SELECTORS.chatMessages);

              // Ajouter le feedback comme élément séparé après le carousel
              if (data.interaction_id && (data.ask_feedback || apiRecs.length)) {
                const feedbackWrapper = document.createElement("div");
                feedbackWrapper.className = "feedback-wrapper";
                feedbackWrapper.style.padding = "20px 60px";
                const feedbackElement = createFeedbackElement();
                feedbackWrapper.appendChild(feedbackElement);
                DOM_SELECTORS.chatMessages.appendChild(feedbackWrapper);
                scrollBottom(DOM_SELECTORS.chatMessages);
              }
            }
            // Masquer le clavier quand les produits sont affichés
            hideKeyboard();
          }
        );
      } else {
        // Afficher directement le carousel si pas d'intro
        const carousel = createProductCarousel(apiRecs);
        if (carousel) {
          DOM_SELECTORS.chatMessages.appendChild(carousel);
          scrollBottom(DOM_SELECTORS.chatMessages);

          // Ajouter le feedback comme élément séparé après le carousel
          if (data.interaction_id && (data.ask_feedback || apiRecs.length)) {
            const feedbackWrapper = document.createElement("div");
            feedbackWrapper.className = "feedback-wrapper";
            feedbackWrapper.style.padding = "20px 60px";
            const feedbackElement = createFeedbackElement();
            feedbackWrapper.appendChild(feedbackElement);
            DOM_SELECTORS.chatMessages.appendChild(feedbackWrapper);
            scrollBottom(DOM_SELECTORS.chatMessages);
          }
        }
        // Masquer le clavier quand les produits sont affichés
        hideKeyboard();
      }
    } else {
      // Utiliser l'effet de frappe pour toutes les réponses du bot avec synthèse vocale en parallèle
      typingBubble(
        DOM_SELECTORS.chatMessages,
        renderMarkdownLite(answer),
        () => speak(answer) // Parler EN MÊME TEMPS que le typing
      );
    }

    if (data.interaction_id) {
      STATE.lastInteractionId = data.interaction_id;
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

  // Attendre que la voix masculine par défaut soit initialisée
  await initializeDefaultVoice();

  // Utiliser l'effet de frappe pour le message de reset avec synthèse vocale
  typingBubble(
    DOM_SELECTORS.chatMessages,
    "Bonjour, je suis votre conseiller virtuel. Comment puis-je vous aider ?",
    () => speak("Bonjour, je suis votre conseiller virtuel. Comment puis-je vous aider ?")
  );
}

// Fonction pour masquer le clavier virtuel
function hideKeyboard() {
  const keyboardElement = document.querySelector(".keyboard");
  if (keyboardElement) {
    keyboardElement.classList.remove("active");
  }
}