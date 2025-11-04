"use strict";



const chatMessages = document.querySelector(".chat-messages");
const chatInput = document.getElementById("chat-form-input");
const modal = document.querySelector(".chat-activity-modal");
const modalTimer = document.getElementById("chat-activity-modal-timer");
const clavier = document.querySelector(".keyboard");
const chatForme = document.getElementById("chatForm");
const feedbackButtons = document.querySelectorAll(".feedback-button");
const chatSendButtons = document.querySelectorAll(".chat-send");
const feedback_id = document.getElementById("feedback");
const wordSuggestions = document.getElementById("wordSuggestions");
const suggestionsContainer = document.getElementById("wordSuggestions");

const suggestions = [
  "ballon", "je cherche un ballon", "tennis", "basket", "amateur", "entraînement",
  "compétition", "jeu spécifique", "intérieur", "extérieur", "football",
  "basketball", "volleyball", "route", "sentier", "tapis de course"
];

let timer;
let countdown;
const inactivityDuration = 30;
const inactivityDurationPopUp = 90;

let isTyping = false;
let voiceEnabled = true;

// Forcer le chargement des voix dès que possible
let voicesLoaded = false;
let voices = [];

let negativeFeedbackCount = 0;
let recommendationTimerStart = null;
let recommendationTimerInterval = null;
let firstRecommendationSent = false;



function loadVoices() {
  voices = speechSynthesis.getVoices();
  if (voices.length !== 0) {
    voicesLoaded = true;
  }
}

window.speechSynthesis.onvoiceschanged = () => {
  loadVoices();
};

document.addEventListener("DOMContentLoaded", () => {
  const toggleVoiceButton = document.getElementById("toggle-voice");

  function updateVoiceButton() {
    toggleVoiceButton.innerHTML = voiceEnabled
      ? '<i class="bi bi-volume-up-fill"></i>'
      : '<i class="bi bi-volume-mute-fill"></i>';
    toggleVoiceButton.classList.toggle("muted", !voiceEnabled);
  }

  if (toggleVoiceButton) {
    updateVoiceButton();
    toggleVoiceButton.addEventListener("click", () => {
      voiceEnabled = !voiceEnabled;
      if (!voiceEnabled) speechSynthesis.cancel();
      updateVoiceButton();
    });
  }
});

function speakText(text) {
  if (!voiceEnabled || !window.speechSynthesis) return;

  const trySpeak = () => {
    voices = speechSynthesis.getVoices();
    if (!voices.length) {
      setTimeout(() => speakText(text), 300);
      return;
    }

    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = document.getElementById("language-selector")?.value || "fr-FR";
    utterance.rate = 1.2;
    utterance.pitch = 1;
    utterance.volume = 1;

    const frMaleVoices = voices.filter(v =>
      v.lang.startsWith("fr") && /homme|male|paul|yves|thomas|google.*masculin/i.test(v.name)
    );

    if (frMaleVoices.length > 0) {
      utterance.voice = frMaleVoices[0];
    } else {
      const frVoice = voices.find(v => v.lang.startsWith("fr"));
      if (frVoice) {
        utterance.voice = frVoice;
      }
    }

    speechSynthesis.cancel();
    speechSynthesis.speak(utterance);
  };

  trySpeak();
}



// Création d’un message dans le chat
function createMessage(sender, message, extractedProductDetails) {
  message = message.replace(/\*/g, "");

  const chatMessage = document.createElement("div");
  chatMessage.className = "chat-message";
  chatMessage.classList.add(sender.trim());

  const chatMessageAvatar = document.createElement("img");
  chatMessageAvatar.className = "chat-message-avatar";

  if (sender.includes("bot")) {
    chatMessageAvatar.src = "../static/images/bot.png";
    chatMessageAvatar.alt = "Conseiller virtuel";
    chatMessage.appendChild(chatMessageAvatar);
  }

  const chatMessageContainer = document.createElement("div");
  chatMessage.appendChild(chatMessageContainer);

  const isMultipleProducts = Array.isArray(extractedProductDetails) && extractedProductDetails.length > 1;
  const isSingleProduct = extractedProductDetails && typeof extractedProductDetails === "object" && !Array.isArray(extractedProductDetails);

  if (isMultipleProducts) {
    chatMessageContainer.className = "chat-message-container carousel-container";
    const carouselWrapper = document.createElement("div");
    carouselWrapper.className = "carousel-wrapper";

    extractedProductDetails.forEach(product => {
      const carouselCard = document.createElement("div");
      carouselCard.className = "carousel-card";

      carouselCard.setAttribute("data-target", product.id || "produit-inconnu");
      if (product.category) {
  carouselCard.setAttribute("data-categorie", product.category);
}


      const content = document.createElement("div");
      content.className = "carousel-card-content";

      if (product.description) {
        const intro = document.createElement("p");
        intro.className = "carousel-product-intro";
        intro.textContent = product.description.replace(/\*\*/g, "").trim();
        content.appendChild(intro);
      }

      const cardMain = document.createElement("div");
      cardMain.className = "carousel-card-main";

      const image = document.createElement("img");
      image.className = "product-image";
      image.src = product.imageUrl || "../static/images/decathlon-default.png";
      image.alt = product.product || "Produit";

      const details = document.createElement("div");
      details.className = "product-details";

      const name = document.createElement("h3");
      name.className = "product-name";
      name.textContent = product.product || "Sans nom";
      details.appendChild(name);

      const brand = document.createElement("span");
      brand.className = "product-brand";
      brand.textContent = product.brand || "Marque inconnue";
      details.appendChild(brand);

      if (product.price) {
        const price = document.createElement("span");
        price.className = "product-price";
        price.textContent = product.price;
        details.appendChild(price);
      }

      if (Array.isArray(product.features)) {
        const ul = document.createElement("ul");
        ul.className = "product-features";
        product.features.forEach(f => {
          const li = document.createElement("li");
          li.className = "product-features-item";
          li.textContent = f;
          ul.appendChild(li);
        });
        details.appendChild(ul);
      }


      cardMain.appendChild(image);
      cardMain.appendChild(details);
      content.appendChild(cardMain);
      content.appendChild(locationButton);
      carouselCard.appendChild(content);
      carouselWrapper.appendChild(carouselCard);
    });

    chatMessageContainer.appendChild(carouselWrapper);
    chatMessages.appendChild(chatMessage);
    return { container: chatMessage };
  }

  if (isSingleProduct) {
    chatMessageContainer.className = "chat-message-container carousel-container";
    const singleCard = document.createElement("div");
    singleCard.className = "single-product-card";

    const content = document.createElement("div");
    content.className = "carousel-card-content";

    if (extractedProductDetails.description) {
      const intro = document.createElement("p");
      intro.className = "carousel-product-intro";
      intro.textContent = extractedProductDetails.description.replace(/\*\*/g, "").trim();
      content.appendChild(intro);
    }

    const cardMain = document.createElement("div");
    cardMain.className = "carousel-card-main";

    const image = document.createElement("img");
    image.className = "product-image";
    image.src = extractedProductDetails.imageUrl || "../static/images/decathlon-default.png";
    image.alt = extractedProductDetails.product || "Produit";

    const details = document.createElement("div");
    details.className = "product-details";

    const name = document.createElement("h3");
    name.className = "product-name";
    name.textContent = extractedProductDetails.product || "Sans nom";
    details.appendChild(name);

    const brand = document.createElement("span");
    brand.className = "product-brand";
    brand.textContent = extractedProductDetails.brand || "Marque inconnue";
    details.appendChild(brand);

    if (extractedProductDetails.price) {
      const price = document.createElement("span");
      price.className = "product-price";
      price.textContent = extractedProductDetails.price;
      details.appendChild(price);
    }

    if (Array.isArray(extractedProductDetails.features)) {
      const ul = document.createElement("ul");
      ul.className = "product-features";
      extractedProductDetails.features.forEach(f => {
        const li = document.createElement("li");
        li.className = "product-features-item";
        li.textContent = f;
        ul.appendChild(li);
      });
      details.appendChild(ul);
    }


    cardMain.appendChild(image);
    cardMain.appendChild(details);
    content.appendChild(cardMain);
    content.appendChild(locationButton);
    singleCard.appendChild(content);
    chatMessageContainer.appendChild(singleCard);
    chatMessages.appendChild(chatMessage);
    return { container: chatMessage };
  }

  // Message texte classique
  chatMessageContainer.className = "chat-message-container";
  const chatMessageText = document.createElement("p");
  chatMessageText.className = "chat-message-text";
  chatMessageText.textContent = message;
  chatMessageContainer.appendChild(chatMessageText);
  chatMessages.appendChild(chatMessage);

  if (sender.includes("bot")) {
    speakText(message); // lecture vocale
  }

  return { container: chatMessage, text: chatMessageText };
}


function typewriterEffect(element, text, speed = 50) {
  let index = 0;
  element.innerHTML = "";
  isTyping = true;

  function type() {
    if (index < text.length) {
      const char = text.charAt(index);
      element.innerHTML += char === "\n" ? "<br>" : char;
      index++;
      scrollToBottom();
      setTimeout(type, speed);
      resetTimer();
    } else {
      isTyping = false;
    }
  }

  type();
}

function normalizeText(str) {
  return str
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/œ/g, "oe")
    .replace(/æ/g, "ae")
    .replace(/[^\w\s]/g, "")
    .toLowerCase()
    .trim();
}


function extractProductDetails(message) {
  const cleanedMessage = message.replace(/-\s/g, "").trim();
  const lines = cleanedMessage.split("\n");

  const productDetails = {
    product: null,
    brand: null,
    price: null,
    color: null,
    category: null,
    availability: null,
    utilisation: null,
    taille: null,
    materiau: null,
    features: [],
    description: null,
    imageUrl: null,
  };

  let descriptionLines = [];
  let capturingFeatures = false;

  lines.forEach((line) => {
    line = line.trim();
    if (line === "") return;

    if (!productDetails.imageUrl && line.includes("http")) {
      const urlMatch = line.match(/\((https?:\/\/[^\s)]+)\)/);
      if (urlMatch) {
        productDetails.imageUrl = urlMatch[1].trim();
        return;
      }
      const fallbackUrl = line.match(/https?:\/\/[^\s)]+/);
      if (fallbackUrl) {
        productDetails.imageUrl = fallbackUrl[0].replace(/[)\.]+$/, "").trim();
        return;
      }
    }

    //Clé: valeur
    const parts = line.split(":");
    if (parts.length >= 2) {
      const rawKey = parts[0].replace(/\*/g, "").trim();
      const key = normalizeText(rawKey);
      const value = parts.slice(1).join(":").replace(/\*/g, "").trim();

      switch (key) {
        case "produit":
        case "nom":
        case "titre":
        case "nom du produit":
          if (!productDetails.product) productDetails.product = value;
          break;
        case "marque":
          productDetails.brand = value;
          break;
        case "prix":
          productDetails.price = value;
          break;
        case "caractéristiques":
        case "caracteristiques":
          capturingFeatures = true;
          if (value) productDetails.features.push(value);
          break;
        case "couleur":
        case "color":
          productDetails.color = value;
          break;
        case "categorie":
        case "catégorie":
          productDetails.category = value;
          break;
        case "disponibilite":
        case "disponibilité":
          productDetails.availability = value;
          break;
        case "utilisation":
          productDetails.utilisation = value;
          break;
        case "taille":
          productDetails.taille = value;
          break;
        case "materiau":
        case "matière":
          productDetails.materiau = value;
          break;
        case "description":
          if (!productDetails.description) productDetails.description = value;
          break;
        default:
          if (!line.startsWith("http")) descriptionLines.push(line);
      }
    } else if (capturingFeatures && line.startsWith("-")) {
      productDetails.features.push(line.substring(1).trim());
    } else {
      descriptionLines.push(line.replace(/\*/g, "").trim());
    }
  });

  if (!productDetails.description && descriptionLines.length > 0) {
    productDetails.description = descriptionLines.join(" ").trim();
  }

  //Fallback titre entre guillemets
  if (!productDetails.product) {
    const quoted = message.match(/[«"](.*?)[»"]/);
    if (quoted && quoted[1]) {
      productDetails.product = quoted[1].trim();
    }
  }

  //Fallback titre en Markdown **...**
  if (!productDetails.product) {
    const boldMatch = message.match(/\*\*(.+?)\*\*/);
    if (boldMatch && boldMatch[1]) {
      productDetails.product = boldMatch[1].trim();
    }
  }

  return productDetails;
}



function scrollToBottom() {
  if (chatMessages) {
    chatMessages.scrollTop = chatMessages.scrollHeight;
  }
}

async function sendFeedback(event, feedback, messageId) {
  event.stopPropagation();

  const feedbackMessagebot = createMessage("bot", "");
  const bouncingDots = document.createElement("div");
  bouncingDots.className = "bouncing-dots";
  bouncingDots.innerHTML = "<span></span><span></span><span></span>";
  feedbackMessagebot.text.appendChild(bouncingDots);
  scrollToBottom();

  const feedbackButtons = document.querySelectorAll(".feedback-button");
  feedbackButtons.forEach((button) => {
    button.disabled = true;
  });

  await fetch("/send_feedback/", {
    method: "POST",
    body: JSON.stringify({
      message_id: messageId,
      satisfaction: feedback === "yes"
    }),
    headers: {
      "Content-Type": "application/json"
    }
  });

  if (feedback === "no") {
    negativeFeedbackCount++;
  } else {
    negativeFeedbackCount = 0;
  }

  if (negativeFeedbackCount >= 2) {
    feedbackMessagebot.container.remove();
    showEscaladePopup();
    return;
  }

  await fetch("/start_chat/", {
    method: "POST",
    body: JSON.stringify({
      message:
        feedback === "yes"
          ? "Merci, cette recommandation convient à mes attentes."
          : "Merci pour votre recommandation, cependant elle ne correspond pas à mes attentes. Veuillez me reposer des questions pour affiner votre recherche, ou recommandez-moi un nouveau produit qui correspondra à mes attentes."
    }),
    headers: {
      "Content-Type": "application/json"
    }
  })
    .then((response) => response.json())
    .then((data) => {
      feedbackMessagebot.container.remove();

      if (data.status === "success") {
        const feedbackMessage = data.message;
        const msg = createMessage("bot", "");

        if (msg.text) {
          typewriterEffect(msg.text, feedbackMessage);
          speakText(feedbackMessage);
        }

        scrollToBottom();

        if (feedback === "no") {
          chatInput.disabled = false;
          chatForme.style.display = '';
          chatSendButtons.forEach((button) => (button.disabled = false));
          chatInput.focus();
        } else {
          setTimeout(() => {
            showNewSearchPopup();
          }, 15000);
        }
      } else {
        scrollToBottom();
      }
    })
    .catch(() => {
      scrollToBottom();
    });

  resetTimer();
}


function showEscaladePopup() {
  const existingPopup = document.querySelector(".escalade-popup");
  if (existingPopup) existingPopup.remove();

  const popup = document.createElement("div");
  popup.className = "escalade-popup";
  popup.innerHTML = `
    <div class="escalade-popup-container">
      <img src="../static/images/icons/warning.svg" alt="Alerte" class="escalade-popup-icon" />
      <p class="escalade-popup-description">
        <strong>Nous n'avons pas réussi à répondre à votre besoin.</strong><br>
       Nous vous recommandons de consulter un conseiller humain.
      </p>
      <div class="escalade-popup-buttons">
        <button class="button button-secondary" id="escalade-home">Retour à l'accueil</button>
        <button class="button button-primary" id="escalade-continue">Continuer la conversation</button>
      </div>
    </div>
  `;
  document.body.appendChild(popup);

  document.getElementById("escalade-home").addEventListener("click", () => {
    window.location.href = "/";
  });

  document.getElementById("escalade-continue").addEventListener("click", () => {
    popup.remove();

    // Réinitialisation des champs de saisie pour poursuivre
    chatInput.disabled = false;
    chatForme.style.display = '';
    chatSendButtons.forEach((button) => (button.disabled = false));
    chatInput.focus();

    const msg = createMessage("bot", "");
    const text = "Très bien, poursuivons ensemble. N'hésitez pas à me préciser votre besoin.";
    typewriterEffect(msg.text, text);
    speakText(text);
    scrollToBottom();
  });
}

function showNewSearchPopup() {
  const existingPopup = document.querySelector(".new-search-popup");
  if (existingPopup) existingPopup.remove();

  const popup = document.createElement("div");
  popup.className = "escalade-popup new-search-popup";
  popup.innerHTML = `
    <div class="escalade-popup-container">
      <img src="../static/images/icons/question.svg" alt="Nouvelle recherche" class="escalade-popup-icon" />
      <p class="escalade-popup-description">
        Souhaitez-vous faire une nouvelle recherche ?
      </p>
      <div class="escalade-popup-buttons">
        <button class="button button-primary" id="new-search-yes">Oui</button>
        <button class="button button-secondary" id="new-search-no">Non</button>
      </div>
    </div>
  `;
  document.body.appendChild(popup);

  document.getElementById("new-search-no").addEventListener("click", () => {
    window.location.href = "/";
  });

  document.getElementById("new-search-yes").addEventListener("click", () => {
    popup.remove();

    if (typeof resetChat === "function") {
      resetChat();
    }
  });
}






function showFeedbackBlock() {
  const feedback = document.createElement("div");
  feedback.className = "feedback";

  const feedbackText = document.createElement("p");
  feedbackText.className = "feedback-text";
  feedbackText.textContent = "Ce produit correspond-il à vos attentes ?";
  feedback.appendChild(feedbackText);

  const feedbackButtonsDiv = document.createElement("div");
  feedbackButtonsDiv.className = "feedback-buttons";

  const feedbackButtonYes = document.createElement("button");
  feedbackButtonYes.className = "feedback-button primary";
  const feedbackButtonYesIcon = document.createElement("img");
  feedbackButtonYesIcon.src = "../static/images/icons/like.svg";
  feedbackButtonYesIcon.alt = "Oui";
  feedbackButtonYes.appendChild(feedbackButtonYesIcon);
  feedbackButtonYes.appendChild(document.createTextNode(" Oui"));
  feedbackButtonYes.addEventListener("click", (event) => sendFeedback(event, "yes"));

  const feedbackButtonNo = document.createElement("button");
  feedbackButtonNo.className = "feedback-button secondary";
  const feedbackButtonNoIcon = document.createElement("img");
  feedbackButtonNoIcon.src = "../static/images/icons/dislike.svg";
  feedbackButtonNoIcon.alt = "Non";
  feedbackButtonNo.appendChild(feedbackButtonNoIcon);
  feedbackButtonNo.appendChild(document.createTextNode(" Non"));
  feedbackButtonNo.addEventListener("click", (event) => sendFeedback(event, "no"));

  feedbackButtonsDiv.appendChild(feedbackButtonYes);
  feedbackButtonsDiv.appendChild(feedbackButtonNo);

  feedback.appendChild(feedbackButtonsDiv);

  chatMessages.appendChild(feedback);

  chatInput.blur();

  chatInput.disabled = true;
  chatForme.style.display = "none";
  chatSendButtons.forEach(button => button.disabled = true);

  scrollToBottom();
}


async function sendMessage() {
  if (isTyping) return;

  const chatSendButtons = document.querySelectorAll(".chat-send");
  const message = chatInput.value.trim();

  chatInput.disabled = true;
  chatSendButtons.forEach(button => button.disabled = true);

  if (!message) {
    chatInput.disabled = false;
    chatSendButtons.forEach(button => button.disabled = false);
    return;
  }

  createMessage("user", message);
  chatInput.value = "";

  const botMessage = createMessage("bot", "");
  const bouncingDots = document.createElement("div");
  bouncingDots.className = "bouncing-dots";
  bouncingDots.innerHTML = "<span></span><span></span><span></span>";
  botMessage.text.appendChild(bouncingDots);
  scrollToBottom();

  try {
    const response = await fetch("/start_chat/", {
      method: "POST",
      body: JSON.stringify({ message }),
      headers: { "Content-Type": "application/json" },
    });

    const data = await response.json();
    if (botMessage.container) botMessage.container.remove();

    if (data.status === "success") {
      let rawMessage = data.message
        .replace(/#/g, "")
        .replace(/\【.*?\】/g, "")
        .trim();

      let delay = 0;
      let introText = "";
      let conclusionText = "";
      let products = [];

      const productBlocks = [...rawMessage.matchAll(/\d+\.\s+(.*?)(?=\n\d+\.\s+|\n?$)/gs)];
      const multipleHint = /la première|la deuxième|je vous recommande\s+(deux|plusieurs)/i.test(rawMessage);

      if (productBlocks.length > 0 || multipleHint) {
        const match = rawMessage.match(/^(.*?)(\n\d+\.\s+.*)$/s);
        introText = match ? match[1].trim() : "";
        const restMessage = match ? match[2] : rawMessage;

        if (introText) {
  setTimeout(() => {
    const msg = createMessage("bot", introText);
    if (msg.text) {
      typewriterEffect(msg.text, introText);
    }
    scrollToBottom();
  }, delay);
  delay += 1000;
}


        if (productBlocks.length > 0) {
          products = productBlocks.map((block) => {
            const split = block[1].split(/- \*\*Produit\s*:\*\*/);
            const intro = split[0].replace(/\*\*/g, "").trim();
            const fiche = split[1] ? "- **Produit :** " + split[1].trim() : "";

            let details = extractProductDetails(fiche);
            details.description = intro;
            return details;
          });

          const last = productBlocks[productBlocks.length - 1];
          const endIndex = last.index + last[0].length;
          conclusionText = restMessage.substring(endIndex).trim();
        } else if (multipleHint) {
          const blocks = rawMessage.split(/\n(?=- \*\*Produit\s*:\*\*)/g);
          products = blocks.map(bloc => {
            const intro = bloc.split(/- \*\*Produit\s*:\*\*/)[0]?.trim();
            let details = extractProductDetails(bloc);
            details.description = intro;
            return details;
          });
        }

        if (products.length > 0) {
  if (!firstRecommendationSent && recommendationTimerStart) {
    const elapsedSeconds = Math.floor((new Date() - recommendationTimerStart) / 1000);
    clearInterval(recommendationTimerInterval);

    fetch("/log_first_recommendation_delay/", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ delay_seconds: elapsedSeconds })
    });

    firstRecommendationSent = true;
  }

  setTimeout(() => {
    if (products.length === 1) {
      createMessage("bot", "", products[0]);
    } else {
      createProductCarousel(products);
    }
    scrollToBottom();
  }, delay);
  delay += 1000;

  if (conclusionText) {
    setTimeout(() => {
      createMessage("bot", conclusionText);
      scrollToBottom();
    }, delay);
    delay += 1000;
  }

  setTimeout(() => {
    showFeedbackBlock();
    scrollToBottom();
  }, delay);
  return;
}

      }

      // Cas 2 : Produit unique
      const hasImage = rawMessage.includes("http") || rawMessage.includes("![");
      if (hasImage) {
        const introMatch = rawMessage.split(/^- \*\*/m);
        const introText = introMatch[0]?.trim() || "";
        const ficheMarkdown = rawMessage.slice(introText.length).trim();

        const extractedProductDetails = extractProductDetails(ficheMarkdown);

        if (extractedProductDetails && extractedProductDetails.product) {
  if (!firstRecommendationSent && recommendationTimerStart) {
    const elapsedSeconds = Math.floor((new Date() - recommendationTimerStart) / 1000);
    clearInterval(recommendationTimerInterval);

    fetch("/log_first_recommendation_delay/", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ delay_seconds: elapsedSeconds })
    });

    firstRecommendationSent = true;
  }

  if (introText) {
    extractedProductDetails.description = introText + "\n\n" + (extractedProductDetails.description || "");
  }

  createMessage("bot", "", extractedProductDetails);
  scrollToBottom();
  showFeedbackBlock();
  return;
}

      }

      // Cas 3 : Produit implicite
      const implicitMatch = rawMessage.match(/["«](.+?)["»]\s+(de|par)\s+([A-ZÉÈÀÂÔÎ][a-zA-ZÀ-ÿ'’ -]+)/);
      const imageMatch = rawMessage.match(/https?:\/\/[^\s)]+/);
      if (implicitMatch && imageMatch) {
        const titre = implicitMatch[1].trim();
        const auteur = implicitMatch[3].trim();
        const imageUrl = imageMatch[0].trim();
        const description = rawMessage.split(imageUrl)[0].trim();

        const details = {
          product: titre,
          auteur: auteur,
          imageUrl: imageUrl,
          resume: description,
          description: description,
          synopsis: description,
        };

        createMessage("bot", "", details);
        scrollToBottom();
        showFeedbackBlock();
        return;
      }

     // Cas 4 : Message texte classique
const botTextMessage = createMessage("bot", rawMessage);
if (botTextMessage.text) {
  typewriterEffect(botTextMessage.text, rawMessage);

  // Lecture vocale du message texte brut (sans produit)
  if (voiceEnabled && typeof speakText === "function") {
    speakText(rawMessage);
  }
}

    } else {
      if (botMessage.text) {
        botMessage.textContent = "Erreur lors de la récupération de la réponse.";
      }
    }
  } catch (error) {
    console.error("Erreur lors de la requête :", error);
    if (botMessage.text) {
      botMessage.textContent = "Erreur lors de la récupération de la réponse.";
    }
  } finally {
    chatInput.disabled = false;
    chatSendButtons.forEach(button => button.disabled = false);
    resetTimer();
  }
}






function cleanUp() {
  clearHistory();
  clearTimeout(timer);
  clearInterval(countdown);
  modal.classList.remove("active");
  chatMessages.innerHTML = "";
  chatInput.value = "";
  chatInput.disabled = false;
}

function resetTimer() {
  if (!modal) return; // évite les erreurs si modal n'existe pas
  if (modal.classList.contains("active")) return;

  clearTimeout(timer);
  clearInterval(countdown);
  startTimer();
}


function startTimer() {
  let currentTimerValue = inactivityDuration;
  modalTimer.textContent = currentTimerValue;

  timer = setTimeout(function () {
    modal.classList.add("active");
    chatInput.disabled = true;

    countdown = setInterval(function () {
      if (currentTimerValue > 0) {
        currentTimerValue--;
        modalTimer.textContent = currentTimerValue;
      } else {
        cleanUp();
        window.location.href = "/";
      }
    }, 1000);
  }, inactivityDurationPopUp * 1000);
}

function resetActivity() {
  modal.classList.remove("active");
  chatInput.disabled = false;

  scrollToBottom();
  resetTimer();
  resetChat();
  clearHistory();
}

function continueActivity() {
  modal.classList.remove("active");
  chatInput.disabled = false;
  resetTimer();
}

function checkChatActivity() {
  const modalResetButton = document.getElementById("chat-activity-modal-reset");
  const modalContinueButton = document.getElementById(
    "chat-activity-modal-continue"
  );

  modal.addEventListener("click", (event) => event.stopPropagation());
  modalResetButton.addEventListener("click", resetChat);
  modalContinueButton.addEventListener("click", continueActivity);

  //chatInput.addEventListener("input", resetTimer);

  /////////////////////////////////////suggestion word
  chatInput.addEventListener("input", (event) =>  {
    resetTimer;
    //updateSuggestions(userInput.value);
    const inputText = chatInput.value.toLowerCase();

    //wordSuggestions.innerHTML = '';


});
  scrollToBottom();
  startTimer();
}


async function clearHistory() {
  try {
    const response = await fetch("/clear_history/", {
      method: "POST",
    });
    const data = await response.json();

    console.log("Server response:", data); // Log ajouté
    return data;
  } catch (error) {
    console.error("Error clearing history:", error); // Log ajouté
  }
}

async function resetChat() {
  const chatReset = document.getElementById("chat-reset");
  chatReset.disabled = true;

  await clearHistory();

  // Ferme une éventuelle modale active
  if (modal) {
    modal.classList.remove("active");
  }

  // Réinitialise l'interface du chat
  chatMessages.innerHTML = "";
  chatInput.value = "";
  chatInput.disabled = false;
  chatForme.style.display = '';
  chatInput.focus();

  chatSendButtons.forEach((button) => (button.disabled = false));
  chatReset.disabled = false;

  negativeFeedbackCount = 0;

  // Message d’accueil
  const welcomeMessage = "Bonjour, je suis votre conseiller virtuel. En quoi puis-je vous aider aujourd’hui ?";
  const welcome = createMessage("bot", welcomeMessage);
  if (welcome.text) {
    typewriterEffect(welcome.text, welcomeMessage);
    speakText(welcomeMessage);
  }

  scrollToBottom();

  // Réinitialise le timer d’inactivité
  resetTimer();

  // Réinitialise le minuteur de recommandation
  if (recommendationTimerInterval) {
    clearInterval(recommendationTimerInterval);
  }
  firstRecommendationSent = false;
  recommendationTimerStart = new Date();
  recommendationTimerInterval = setInterval(() => {
    const now = new Date();
    const elapsed = Math.floor((now - recommendationTimerStart) / 1000);
    console.log("⏱ Temps écoulé depuis message de bienvenue :", elapsed, "secondes");
  }, 1000);
}




async function initChat() {
  const chatForm = document.getElementById("chatForm");
  const chatReset = document.getElementById("chat-reset");

  const welcome = createMessage(
  "bot",
  "Bonjour je suis votre conseiller virtuel, en quoi puis-je vous aider aujourd’hui ?"
);
if (welcome.text) {
  typewriterEffect(welcome.text, "Bonjour je suis votre conseiller virtuel, en quoi puis-je vous aider aujourd’hui ?");
}
recommendationTimerStart = new Date();
recommendationTimerInterval = setInterval(() => {
  const now = new Date();
  const elapsed = Math.floor((now - recommendationTimerStart) / 1000);
  console.log("⏱ Temps écoulé depuis message de bienvenue :", elapsed, "secondes");
}, 1000);


  chatForm.addEventListener("click", (event) => {
    event.stopPropagation();
  });
  chatForm.addEventListener("submit", (event) => {
    event.preventDefault();

    sendMessage();
  });
  chatInput.addEventListener("keydown", (event) => {
    resetTimer();
    if (event.key === "Enter") {
      sendMessage();

    }
  });
  chatReset.addEventListener("click", resetChat);
}

document.addEventListener("keyboardCreated", async () => {
  const chatSendButtons = await document.querySelectorAll(".chat-send");

});
document.addEventListener("keyboardTyping", () => {
  if (chatInput.disabled) return;
  resetTimer();
});
document.addEventListener("mousemove", () => {
  resetTimer();
});

document.addEventListener("DOMContentLoaded", () => {
  clearHistory();
  initChat();
  checkChatActivity();
  window.addEventListener("resize", scrollToBottom);
  //init();
});

chatMessages.addEventListener("scroll",()=> {
  //console.log("sala ko! scroll");
  resetTimer();
});

function generateSuggestions(input) {
  if (!input) {
      return [
          "Je cherche un ballon",
          "Je cherche des chaussures",
          "Je cherche un vetement",
          "Je cherche un maillot",



      ];
  }

  const suggestions = new Set();
 // Add some general suggestions if we don't have enough
 if (suggestions.size < 3) {
  suggestions.add("Je cherche un ballon");
  suggestions.add("Je cherche des chaussures");
  suggestions.add("Je cherche un maillot");
}
  return Array.from(suggestions).slice(0, 5);
}

// Update the suggestions display
function updateSuggestions(input) {
  const suggestions = generateSuggestions(input);
  suggestionsContainer.innerHTML = '';

  suggestions.forEach(suggestion => {
      const suggestionDiv = document.createElement('div');
      suggestionDiv.classList.add('suggestion');
      suggestionDiv.textContent = suggestion;
      suggestionDiv.addEventListener('click', function() {
        chatInput.value = suggestion;
        //wordSuggestions.style.display = 'none';
        chatInput.focus();
        sendMessage()
      });
      suggestionsContainer.appendChild(suggestionDiv);
  });
}
function blockbutton(){
  feedbackButtons.forEach((button) => {
    button.disabled = true;
  });
}
function createProductCarousel(products) {
  const chatMessage = document.createElement("div");
  chatMessage.className = "chat-message bot";

  const avatar = document.createElement("img");
  avatar.className = "chat-message-avatar";
  avatar.src = "../static/images/bot.png";
  avatar.alt = "Conseiller virtuel";
  chatMessage.appendChild(avatar);

  const container = document.createElement("div");
  container.className = "chat-message-container carousel-container";
  chatMessage.appendChild(container);

  const wrapper = document.createElement("div");
  wrapper.className = "carousel-wrapper";
  container.appendChild(wrapper);

  const leftArrow = document.createElement("button");
  leftArrow.className = "carousel-arrow left";
  leftArrow.innerHTML = "❮";
  wrapper.appendChild(leftArrow);

  const rightArrow = document.createElement("button");
  rightArrow.className = "carousel-arrow right";
  rightArrow.innerHTML = "❯";
  wrapper.appendChild(rightArrow);

  const carousel = document.createElement("div");
  carousel.className = "carousel-product";
  wrapper.appendChild(carousel);

  products.forEach((product, index) => {
    const card = document.createElement("div");
    card.className = "carousel-card";
    card.setAttribute("data-target", product.id || `produit-${index}`);
    if (product.category) {
      card.setAttribute("data-categorie", product.category);
    }

    const content = document.createElement("div");
    content.className = "carousel-card-content";

    if (product.description) {
      const intro = document.createElement("p");
      intro.className = "carousel-product-intro";
      intro.textContent = product.description.replace(/\*\*/g, "").trim();
      content.appendChild(intro);
    }

    const cardMain = document.createElement("div");
    cardMain.className = "carousel-card-main";

    const image = document.createElement("img");
    image.className = "product-image";
    image.src = product.imageUrl || "../static/images/decathlon-default.png";
    image.alt = product.product || "Produit";

    const details = document.createElement("div");
    details.className = "product-details";

    const name = document.createElement("h3");
    name.className = "product-name";
    name.textContent = product.product || "Sans nom";
    details.appendChild(name);

    const brand = document.createElement("span");
    brand.className = "product-brand";
    brand.textContent = product.brand || "Marque inconnue";
    details.appendChild(brand);

    const price = document.createElement("span");
    price.className = "product-price";
    price.textContent = product.price || "Prix non disponible";
    details.appendChild(price);

    if (Array.isArray(product.features)) {
      const ul = document.createElement("ul");
      ul.className = "product-features";
      product.features.forEach(f => {
        const li = document.createElement("li");
        li.textContent = f;
        ul.appendChild(li);
      });
      details.appendChild(ul);
    }

    cardMain.appendChild(image);
    cardMain.appendChild(details);
    content.appendChild(cardMain);

    // --- Localisation ---
    const locationButton = document.createElement("button");
    locationButton.className = "btn-location";
    locationButton.innerHTML = `<i class="bi bi-search"></i> Localiser le produit`;
    locationButton.setAttribute("data-target", product.id || `produit-${index}`);

    locationButton.addEventListener("click", () => {
  const modal = document.getElementById("svgModal");
  const object = document.getElementById("svgMap"); // <object>

  const pathId = getPathIdFromCategory(product.category);
  console.log("Catégorie brute :", product.category);
  console.log(" Recherche de pathId pour :", product.category);
  console.log("Résultat pathId :", pathId);

  if (!pathId) {
    console.warn("Aucune zone trouvée pour cette catégorie.");
    return;
  }

  if (!modal || !object) {
    console.warn(" Modale ou balise <object> introuvable.");
    return;
  }

  modal.style.display = "flex";

  function tryHighlight() {
  const svgDoc = object.contentDocument;
  if (!svgDoc) return;

  const target = svgDoc.getElementById(pathId);
  if (target) {
    applyHighlight(svgDoc, pathId);
  } else {
    setTimeout(tryHighlight, 300);
  }
}


  // Si déjà chargé
  if (object.contentDocument && object.contentDocument.readyState === "complete") {
    tryHighlight();
  } else {
    // Sinon, attendre le chargement
    object.addEventListener("load", tryHighlight, { once: true });
  }
});


    content.appendChild(locationButton);
    card.appendChild(content);
    carousel.appendChild(card);
  });

  chatMessages.appendChild(chatMessage);
  scrollToBottom();

  // Navigation flèche
  let currentIndex = 0;
  const cards = carousel.querySelectorAll(".carousel-card");
  cards.forEach((card, i) => {
    card.style.display = i === 0 ? "flex" : "none";
  });

  leftArrow.addEventListener("click", () => {
    cards[currentIndex].style.display = "none";
    currentIndex = (currentIndex - 1 + cards.length) % cards.length;
    cards[currentIndex].style.display = "flex";
  });

  rightArrow.addEventListener("click", () => {
    cards[currentIndex].style.display = "none";
    currentIndex = (currentIndex + 1) % cards.length;
    cards[currentIndex].style.display = "flex";
  });
}

// Appliquer le surlignage sur la zone SVG
function applyHighlight(svgDoc, pathId) {
  // Injecter le style une seule fois
  if (!svgDoc.getElementById("highlight-style")) {
    const style = svgDoc.createElementNS("http://www.w3.org/2000/svg", "style");
    style.id = "highlight-style";
    style.textContent = `
      .selected {
        fill: #FFD700 !important;
        opacity: 1 !important;
      }

      .ping {
        fill: #FFD700;
        opacity: 0.5;
        animation: ping 1.5s ease-out infinite;
      }

      @keyframes ping {
        0% {
          r: 0;
          opacity: 0.7;
        }
        100% {
          r: 30;
          opacity: 0;
        }
      }
    `;
    svgDoc.documentElement.appendChild(style);
  }

  svgDoc.querySelectorAll(".selected").forEach(el => el.classList.remove("selected"));
  svgDoc.querySelectorAll(".ping").forEach(el => el.remove());

  const targetPath = svgDoc.getElementById(pathId);
  if (targetPath) {
    targetPath.classList.add("selected");

    // un halo (ping) centré sur la zone
    const bbox = targetPath.getBBox();
    const cx = bbox.x + bbox.width / 2;
    const cy = bbox.y + bbox.height / 2;

    const ping = svgDoc.createElementNS("http://www.w3.org/2000/svg", "circle");
    ping.setAttribute("class", "ping");
    ping.setAttribute("cx", cx);
    ping.setAttribute("cy", cy);
    ping.setAttribute("r", "0");
    svgDoc.documentElement.appendChild(ping);
  } else {
    console.warn("Zone non trouvée :", pathId);
  }
}

// Initialize
function init() {
  updateSuggestions("");
}