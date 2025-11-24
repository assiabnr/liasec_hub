"use strict";

import { STATE, API_URLS } from "./config.js";
import { scrollBottom, sanitize, getCookie } from "./utils.js";

export function createProductCarousel(products) {
  if (!products || !products.length) return null;

  const productIds = products.map((p) => p.id || p.reference).join(",");
  const existingCards = document.querySelector(
    `[data-products="${productIds}"]`
  );
  if (existingCards) {
    console.log("Ces produits sont déjà affichés");
    return null;
  }

  const wrap = document.createElement("div");
  wrap.className = "message bot";
  wrap.setAttribute("data-products", productIds);

  const bubbleDiv = document.createElement("div");
  bubbleDiv.className = "bubble";

  const carouselWrapper = document.createElement("div");
  carouselWrapper.className = "carousel-wrapper";

  const leftArrow = document.createElement("button");
  leftArrow.className = "carousel-arrow left";
  leftArrow.innerHTML = "&#8249;";
  leftArrow.setAttribute("aria-label", "Produit précédent");

  const carouselContainer = document.createElement("div");
  carouselContainer.className = "carousel-container";

  const rightArrow = document.createElement("button");
  rightArrow.className = "carousel-arrow right";
  rightArrow.innerHTML = "&#8250;";
  rightArrow.setAttribute("aria-label", "Produit suivant");

  products.forEach((p, index) => {
    const card = createProductCard(p);
    if (index === 0) card.classList.add("active");
    carouselContainer.appendChild(card);
  });

  carouselWrapper.appendChild(leftArrow);
  carouselWrapper.appendChild(carouselContainer);
  carouselWrapper.appendChild(rightArrow);
  bubbleDiv.appendChild(carouselWrapper);
  wrap.appendChild(bubbleDiv);

  let currentIndex = 0;
  const updateCarousel = () => {
    const cards = carouselContainer.querySelectorAll(".carousel-card");
    cards.forEach((card, i) => {
      card.classList.toggle("active", i === currentIndex);
    });
    leftArrow.disabled = currentIndex === 0;
    rightArrow.disabled =
      currentIndex === carouselContainer.querySelectorAll(".carousel-card").length - 1;
  };

  leftArrow.addEventListener("click", () => {
    if (currentIndex > 0) {
      currentIndex--;
      updateCarousel();
    }
  });

  rightArrow.addEventListener("click", () => {
    const cards = carouselContainer.querySelectorAll(".carousel-card");
    if (currentIndex < cards.length - 1) {
      currentIndex++;
      updateCarousel();
    }
  });

  updateCarousel();
  return wrap;
}

function cleanFeatures(text) {
  if (!text) return [];
  let cleaned = text
    .replace(/Couleur\s*:[^.!?\n]*[.!?\n]?/gi, "")
    .replace(/Couleurs?\s*:[^.!?\n]*/gi, "")
    .replace(/\*\*Référence\s*:\*?\*?\s*\d+/gi, "")
    .replace(/Référence\s*:\*?\*?\s*\d+/gi, "")
    .replace(/Réf\.?\s*:?\s*\d+/gi, "")
    .replace(/\*\*/g, "")
    .replace(/\s+/g, " ")
    .trim();

  let sentences = cleaned
    .split(/[.!?]/)
    .map((s) => s.trim())
    .filter((s) => s.length > 0);

  const features = sentences
    .filter((s) => {
      if (s.length < 20) return false;
      if (s.length > 250) return false;
      if (/couleur|référence|réf\./i.test(s)) return false;
      if (/^[\d\s,.()\[\]cm\-]+$/.test(s)) return false;
      return true;
    })
    .slice(0, 3);

  return features;
}

function extractReference(text) {
  if (!text) return null;
  const refMatch = text.match(/\*?\*?Réf(?:érence)?\.?\s*:\*?\*?\s*(\d+)/i);
  if (refMatch) {
    return refMatch[1];
  }
  return null;
}

function createProductCard(p) {
  const featuresText = Array.isArray(p.features)
    ? p.features.join(" ")
    : p.features || "";
  let reference = p.reference || extractReference(featuresText);

  const feats = Array.isArray(p.features)
    ? p.features
    : cleanFeatures(p.features || "");

  const card = document.createElement("div");
  card.className = "carousel-card";

  const images = [];
  const mainFromProduct =
    p.imageUrl || p.image_url || p.image || "/static/chatbot/images/placeholder.png";
  if (mainFromProduct) images.push(mainFromProduct);
  if (p.imageUrlAlt) images.push(p.imageUrlAlt);
  if (p.image_1) images.push(p.image_1);
  if (p.image_2) images.push(p.image_2);

  const uniqueImages = [...new Set(images)];
  const mainImage = uniqueImages[0] || "/static/chatbot/images/placeholder.png";

  const productName = p.product || p.name || "Produit";
  const brandName = p.brand || "";
  const priceText = p.price || "";
  const categoryText = p.category || p.sport || "";
  const description = p.description || p.productDescription || "";

  card.innerHTML = `
    ${
      description
        ? `<p class="carousel-intro">${sanitize(description)}</p>`
        : ""
    }
    <div class="carousel-card-main">
      <div class="product-media">
        <img
          class="product-image main-image"
          src="${sanitize(mainImage)}"
          alt="${sanitize(productName)}"
          onerror="this.src='/static/chatbot/images/placeholder.png'"
        />
        ${
          uniqueImages.length > 1
            ? `
          <div class="product-thumbs">
            ${uniqueImages
              .map(
                (img, idx) => `
              <button
                type="button"
                class="product-thumb ${idx === 0 ? "active" : ""}"
                data-src="${sanitize(img)}"
              >
                <img
                  src="${sanitize(img)}"
                  alt="${sanitize(productName)} - vue ${idx + 1}"
                  onerror="this.src='/static/chatbot/images/placeholder.png'"
                />
              </button>
            `
              )
              .join("")}
          </div>`
            : ""
        }
      </div>

      <div class="product-details">
        <h4 class="product-name">${sanitize(productName)}</h4>
        ${
          brandName
            ? `<p class="product-brand">${sanitize(brandName)}</p>`
            : ""
        }
        ${
  priceText
    ? `<p class="product-price">
         ${sanitize(priceText)}
         <span class="product-price-note">
           Tarif à titre indicatif. Seuls les prix en rayon sont valables.
         </span>
       </p>`
    : ""
}
        ${
          reference
            ? `<p class="product-reference">Réf. ${sanitize(reference)}</p>`
            : ""
        }
        ${
          feats && feats.length
            ? `<ul class="product-features">
                ${feats
                  .map(
                    (f) =>
                      `<li class="product-features-item">${sanitize(
                        String(f)
                      )}</li>`
                  )
                  .join("")}
               </ul>`
            : ""
        }

        <button
          type="button"
          class="btn-location"
          ${
            reference
              ? `data-reference="${sanitize(reference)}"`
              : ""
          }
        >
          <img
            src="/static/chatbot/images/icons/location.svg"
            alt=""
            class="btn-location-icon"
          />
          <span>Localiser le produit</span>
        </button>
      </div>
    </div>
  `;

  const mainImgEl = card.querySelector(".main-image");
  const thumbButtons = card.querySelectorAll(".product-thumb");
  thumbButtons.forEach((btn) => {
    btn.addEventListener("click", () => {
      const src = btn.getAttribute("data-src");
      if (src && mainImgEl) {
        mainImgEl.src = src;
      }
      thumbButtons.forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
    });
  });

  const locBtn = card.querySelector(".btn-location");
  if (locBtn) {
    locBtn.addEventListener("click", async () => {
      const interactionId = p.conversationId || STATE.lastInteractionId;
      if (interactionId) {
        try {
          // Enregistrer le clic sur la recommandation
          await fetch(API_URLS.trackClick, {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
              "X-CSRFToken": getCookie("csrftoken") || "",
            },
            body: JSON.stringify({
              product_id: p.id,
              interaction_id: interactionId,
            }),
          });
          console.log(
            "Clic enregistré sur la recommandation",
            p.id,
            interactionId
          );

          // Marquer la satisfaction
          await fetch(API_URLS.feedback, {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
              "X-CSRFToken": getCookie("csrftoken") || "",
            },
            body: JSON.stringify({
              interaction_id: interactionId,
              satisfaction: true,
            }),
          });
          console.log(
            "Satisfaction marquée suite au clic sur Localiser le produit",
            interactionId
          );
        } catch (err) {
          console.error(
            "Erreur lors du tracking du clic ou de la satisfaction :",
            err
          );
        }
      }

      const evt = new CustomEvent("localize-product", {
        detail: {
          product: p,
          reference,
          category: p.category,
          sport: p.sport,
        },
      });
      document.dispatchEvent(evt);
    });
  }

  return card;
}