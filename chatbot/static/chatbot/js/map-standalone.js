"use strict";

// ==========================================
// CONFIGURATION : Détection du contexte
// ==========================================

function detectContext() {
  // Si une modale existe, on est dans le contexte chatbot
  const modal = document.getElementById("svgModal");
  const isModalContext = !!modal;

  return {
    isModalContext,
    svgObject: document.getElementById("svgMap"),
    modal: modal,
    closeBtn: document.getElementById("closeMapBtn"),
    modalContent: document.querySelector(".map-modal-content")
  };
}

// ==========================================
// GESTION DE LA MODALE (Contexte Chatbot)
// ==========================================

function initMapModal() {
  const { isModalContext, modal, closeBtn, modalContent } = detectContext();

  if (!isModalContext) {
    console.log("[MAP] Pas de modale détectée - Mode localisation direct");
    return;
  }

  if (!closeBtn) {
    console.warn("[MAP] Bouton de fermeture introuvable");
    return;
  }

  // Fermeture via le bouton X
  closeBtn.addEventListener("click", (e) => {
    e.stopPropagation();
    modal.classList.remove("show");
  });

  // Fermeture en cliquant en dehors du contenu
  modal.addEventListener("click", (e) => {
    if (!modalContent) {
      modal.classList.remove("show");
      return;
    }
    if (!modalContent.contains(e.target)) {
      modal.classList.remove("show");
    }
  });

  console.log("[MAP] Modale initialisée");
}

// ==========================================
// HIGHLIGHT DE LA CARTE (Les deux contextes)
// ==========================================

function initMapHighlight() {
  const { svgObject, isModalContext, modal } = detectContext();

  if (!svgObject) {
    console.error("[MAP] Element <object id='svgMap'> introuvable");
    return;
  }

  let svgLoaded = false;

  const checkSvg = () => {
    if (svgObject.contentDocument) {
      svgLoaded = true;
      console.log("[MAP] SVG chargé et prêt");
      return true;
    }
    return false;
  };

  // Vérification progressive du chargement du SVG
  setTimeout(() => {
    if (checkSvg()) {
      console.log("[MAP] SVG déjà disponible après 500ms");
    }
  }, 500);

  setTimeout(() => {
    if (!svgLoaded && checkSvg()) {
      console.log("[MAP] SVG disponible après 1000ms");
    }
  }, 1000);

  svgObject.addEventListener("load", () => {
    svgLoaded = true;
    console.log("[MAP] SVG chargé via événement load");
  });

  // ==========================================
  // ÉCOUTE DE L'ÉVÉNEMENT DE LOCALISATION
  // ==========================================

  document.addEventListener("localize-product", (e) => {
    console.log("[MAP] ━━━ Événement localize-product reçu ━━━");
    console.log("[MAP] Détail complet:", e.detail);

    const { product, category, sport } = e.detail || {};

    if (!product) {
      console.warn("[MAP] Événement localize-product sans produit");
      return;
    }

    const categoryLabel = category || product.category || "";
    const sportLabel = sport || product.sport || "";
    const productName = product.name || product.product || "";

    console.log("[MAP] Produit :", productName);
    console.log("[MAP] Catégorie extraite:", categoryLabel);
    console.log("[MAP] Sport extrait:", sportLabel);

    if (!categoryLabel && !sportLabel) {
      console.warn("[MAP] Aucune catégorie ni sport pour localiser le produit");
      return;
    }

    // Vérifier que sport.js est chargé
    if (typeof window.getPathIdFromCategory !== "function") {
      console.error("[MAP] getPathIdFromCategory n'est pas disponible");
      console.error("[MAP] Vérifiez que sport.js est chargé AVANT map.js");
      return;
    }

    const pathId = window.getPathIdFromCategory(categoryLabel, sportLabel, productName);

    console.log("[MAP] Sport :", sportLabel);
    console.log("[MAP] Catégorie :", categoryLabel);
    console.log("[MAP] Recherche de pathId pour :", categoryLabel, "dans sport:", sportLabel);
    console.log("[MAP] PathId retourné:", pathId);

    if (!pathId || (Array.isArray(pathId) && pathId.length === 0)) {
      console.warn("[MAP] Aucune zone trouvée pour cette catégorie:", categoryLabel);

      // IMPORTANT : Ouvrir la modale même sans zone (si contexte chatbot)
      if (isModalContext && modal) {
        modal.classList.add("show");
      }

      return;
    }

    const svgDoc = svgObject.contentDocument;

    // Si le SVG n'est pas encore chargé, attendre et réessayer
    if (!svgDoc && !svgLoaded) {
      console.warn("[MAP] SVG pas encore chargé, attente...");
      svgObject.addEventListener("load", () => {
        console.log("[MAP] SVG maintenant chargé, retry du highlight");
        const evt = new CustomEvent("localize-product", { detail: e.detail });
        document.dispatchEvent(evt);
      }, { once: true });
      return;
    }

    if (!svgDoc) {
      console.warn("[MAP] SVG contentDocument indisponible");

      // Ouvrir la modale quand même (si contexte chatbot)
      if (isModalContext && modal) {
        modal.classList.add("show");
      }

      return;
    }

    console.log("[MAP] SVG Document disponible");

    // Ouvrir la modale AVANT le highlight (si contexte chatbot)
    if (isModalContext && modal) {
      modal.classList.add("show");
      console.log("[MAP] Modale ouverte");
    }

    // ==========================================
    // FONCTION D'APPLICATION DU HIGHLIGHT
    // ==========================================

    function applyHighlight(svgDoc, pathId) {
      if (!svgDoc) {
        console.error("[MAP] svgDoc est null dans applyHighlight");
        return null;
      }

      // Ajouter les styles d'animation si pas déjà présents
      if (!svgDoc.getElementById("highlight-style")) {
        const style = svgDoc.createElementNS("http://www.w3.org/2000/svg", "style");
        style.id = "highlight-style";
        style.textContent = `
          .selected {
            stroke: #ff7a00 !important;
            stroke-width: 6 !important;
            stroke-linejoin: round;
            stroke-linecap: round;
            animation: highlightStrokeBlink 1s ease-in-out infinite;
          }

          .selected-overlay {
            fill: #ffffff !important;
            fill-opacity: 0.18 !important;
            stroke: none !important;
            pointer-events: none;
            animation: highlightFillBlink 1s ease-in-out infinite;
          }

          @keyframes highlightStrokeBlink {
            0%, 100% { stroke-opacity: 1; }
            50%      { stroke-opacity: 0.25; }
          }

          @keyframes highlightFillBlink {
            0%, 100% { fill-opacity: 0.18; }
            50%      { fill-opacity: 0.03; }
          }
        `;
        svgDoc.documentElement.appendChild(style);
        console.log("[MAP] Styles d'animation ajoutés au SVG");
      }

      // Retirer les anciens highlights
      svgDoc.querySelectorAll(".selected").forEach((el) =>
        el.classList.remove("selected")
      );
      svgDoc.querySelectorAll(".selected-overlay").forEach((el) => el.remove());

      // Trouver l'élément à highlighter
      const targetPath = svgDoc.getElementById(pathId);
      if (!targetPath) {
        console.warn("[MAP] Path non trouvé dans le SVG:", pathId);
        return null;
      }

      console.log("[MAP] Path trouvé, application du highlight sur:", pathId);

      // Appliquer le highlight
      targetPath.classList.add("selected");

      // Créer un overlay pour l'effet de remplissage
      const overlay = targetPath.cloneNode(true);
      overlay.removeAttribute("id");
      overlay.classList.remove("selected");
      overlay.classList.add("selected-overlay");

      if (targetPath.parentNode) {
        targetPath.parentNode.insertBefore(overlay, targetPath.nextSibling);
      }

      // Récupérer le nom de la zone depuis le SVG si disponible
      let zoneName = pathId;
      const textElement = targetPath.querySelector("text");
      if (textElement) {
        zoneName = textElement.textContent.trim();
      }

      return { pathId, zoneName };
    }

    // ==========================================
    // APPLICATION DU HIGHLIGHT
    // ==========================================

    console.log("[MAP] Début du highlight");

    let zones = [];

    if (Array.isArray(pathId)) {
      // Multiple zones
      console.log("[MAP] Zones multiples à highlighter:", pathId);
      pathId.forEach((id) => {
        if (id) {
          const result = applyHighlight(svgDoc, id);
          if (result) zones.push(result);
        }
      });
    } else {
      // Single zone
      console.log("[MAP] Zone unique à highlighter:", pathId);
      const result = applyHighlight(svgDoc, pathId);
      if (result) zones.push(result);
    }

    // ==========================================
    // DISPATCHER L'ÉVÉNEMENT DE LOCALISATION RÉUSSIE
    // ==========================================

    if (zones.length > 0) {
      console.log("[MAP] Highlight appliqué sur", zones.length, "zone(s)");

      const localizationEvent = new CustomEvent("product-localized", {
        detail: {
          productId: product.id,
          productName: product.name,
          zone: zones[0].pathId,
          zoneName: zones[0].zoneName,
          category: categoryLabel,
          sport: sport || product.sport || "",
          allZones: zones,
        },
      });

      document.dispatchEvent(localizationEvent);
      console.log("[MAP] Événement product-localized dispatché");
      console.log("[MAP] Détails:", localizationEvent.detail);
    } else {
      console.warn("[MAP] Aucune zone n'a pu être highlightée");
    }
  });

  console.log("[MAP] Système de highlight initialisé (contexte:", isModalContext ? "chatbot" : "localisation", ")");
}

// ==========================================
// GESTION DES CLICS DIRECTS SUR LA CARTE
// (Mode localisation uniquement)
// ==========================================

function initMapClicks() {
  const { svgObject, isModalContext } = detectContext();

  // Clics directs seulement en mode localisation (pas dans le chatbot)
  if (isModalContext) {
    console.log("[MAP] Contexte chatbot: clics directs désactivés");
    return;
  }

  if (!svgObject) {
    console.error("[MAP] Pas d'objet SVG pour les clics");
    return;
  }

  // Attendre que le SVG soit chargé
  const setupClickHandlers = () => {
    const svgDoc = svgObject.contentDocument;
    if (!svgDoc) {
      console.warn("[MAP] SVG pas encore chargé pour les clics");
      return;
    }

    console.log("[MAP] Configuration des clics directs sur les zones");

    // Récupérer toutes les zones cliquables (paths avec un id)
    const clickableZones = svgDoc.querySelectorAll("path[id], g[id]");

    clickableZones.forEach((zone) => {
      zone.style.cursor = "pointer";

      zone.addEventListener("click", async (e) => {
        e.preventDefault();
        e.stopPropagation();

        const zoneId = zone.id;
        let zoneName = zoneId;

        // Essayer de récupérer le nom de la zone depuis un élément text
        const textElement = zone.querySelector("text");
        if (textElement) {
          zoneName = textElement.textContent.trim();
        }

        console.log("[MAP] Clic direct sur zone:", zoneId, zoneName);

        // Trouver un produit de cette zone (si possible)
        // Pour l'instant, on track juste la zone sans produit spécifique
        try {
          // Appeler l'API pour tracker le clic sur la zone
          const response = await fetch("/chatbot/localisation/api/track-zone-click/", {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
              "X-CSRFToken": getCookie("csrftoken"),
            },
            body: JSON.stringify({
              zone_id: zoneId,
              zone_name: zoneName,
              source: "carte",
            }),
          });

          if (response.ok) {
            console.log("[MAP] Clic sur zone tracké:", zoneName);

            // Émettre un événement pour signaler le clic sur une zone de la carte
            const mapZoneEvent = new CustomEvent("map-zone-clicked", {
              detail: {
                zoneId: zoneId,
                zoneName: zoneName,
                timestamp: Date.now()
              }
            });
            document.dispatchEvent(mapZoneEvent);
            console.log("[MAP] Événement map-zone-clicked émis");

            // Highlight visuel de la zone cliquée
            applyTemporaryHighlight(svgDoc, zoneId);

            // Afficher l'image de la zone dans la modale
            showZoneImage(zoneId, zoneName);
          }
        } catch (error) {
          console.error("[MAP] Erreur tracking zone:", error);
        }
      });
    });

    console.log("[MAP] Clics directs configurés sur", clickableZones.length, "zones");
  };

  // Helper pour highlight temporaire
  function applyTemporaryHighlight(svgDoc, pathId) {
    const path = svgDoc.getElementById(pathId);
    if (!path) return;

    const originalStroke = path.getAttribute("stroke") || "";
    const originalStrokeWidth = path.getAttribute("stroke-width") || "";

    path.setAttribute("stroke", "#ff7a00");
    path.setAttribute("stroke-width", "4");

    setTimeout(() => {
      path.setAttribute("stroke", originalStroke);
      path.setAttribute("stroke-width", originalStrokeWidth);
    }, 800);
  }

  // Helper pour getCookie
  function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== "") {
      const cookies = document.cookie.split(";");
      for (let i = 0; i < cookies.length; i++) {
        const cookie = cookies[i].trim();
        if (cookie.substring(0, name.length + 1) === name + "=") {
          cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
          break;
        }
      }
    }
    return cookieValue;
  }

  // Initialiser quand le SVG est prêt
  if (svgObject.contentDocument) {
    setupClickHandlers();
  } else {
    svgObject.addEventListener("load", setupClickHandlers);
  }
}

// ==========================================
// AFFICHAGE IMAGE ZONE (Mode localisation uniquement)
// ==========================================

function showZoneImage(zoneId, zoneName) {
  const { isModalContext } = detectContext();

  // Seulement en mode localisation (pas dans le chatbot)
  if (isModalContext) {
    console.log("[MAP] Contexte chatbot: affichage image désactivé");
    return;
  }

  const modal = document.getElementById("zoneImageModal");
  const modalImage = document.getElementById("zoneModalImage");
  const modalTitle = document.getElementById("zoneModalTitle");
  const closeBtn = document.getElementById("closeZoneModal");

  if (!modal || !modalImage) {
    console.error("[MAP] Éléments de la modale image non trouvés");
    return;
  }

  // Extraire le numéro de la zone (ex: "area12" -> "12")
  const zoneNumber = zoneId.replace(/\D/g, "");

  // Construire le chemin de l'image
  // Les images sont nommées Area.jpg, Area1.jpg, Area2.jpg, etc.
  let imagePath;
  if (zoneNumber === "") {
    imagePath = "/static/localisation_produits/images/Area.jpg";
  } else {
    imagePath = `/static/localisation_produits/images/Area${zoneNumber}.jpg`;
  }

  console.log("[MAP] Affichage image zone:", zoneId, "->", imagePath);

  // Mettre à jour le titre de la zone avec le nom exact depuis ZONE_NAMES
  if (modalTitle) {
    let displayName = zoneName;

    // Utiliser ZONE_NAMES depuis Python (zone_mapping.py)
    if (window.ZONE_NAMES && window.ZONE_NAMES[zoneId]) {
      displayName = window.ZONE_NAMES[zoneId];
    }
    // Fallback: essayer de récupérer le nom du sport depuis mergedData
    else if (typeof window.getSportFromPathId === "function") {
      const sportName = window.getSportFromPathId(zoneId);
      if (sportName) {
        displayName = sportName;
      }
    }
    // Fallback final si aucun nom trouvé
    else if (!displayName) {
      displayName = `Zone ${zoneNumber || "principale"}`;
    }

    modalTitle.textContent = displayName;
  }

  // Mettre à jour le contenu de la modale
  modalImage.src = imagePath;
  modalImage.alt = `Image de la zone ${zoneName || zoneId}`;

  // Afficher la modale avec animation
  modal.classList.add("show");

  // Forcer le reflow pour l'animation
  setTimeout(() => {
    modal.style.opacity = "1";
  }, 10);

  // Gérer la fermeture
  const closeModal = () => {
    modal.style.opacity = "0";
    setTimeout(() => {
      modal.classList.remove("show");
      // Reset du zoom si présent
      if (modalImage) {
        modalImage.style.transform = "scale(1)";
      }
    }, 300);
  };

  if (closeBtn) {
    closeBtn.onclick = closeModal;
  }

  // Fermer en cliquant en dehors
  modal.onclick = (e) => {
    if (e.target === modal) {
      closeModal();
    }
  };

  // Gestion du swipe vers le bas pour fermer (tactile)
  let touchStartY = 0;
  let touchEndY = 0;

  modal.addEventListener("touchstart", (e) => {
    touchStartY = e.changedTouches[0].screenY;
  }, { passive: true });

  modal.addEventListener("touchend", (e) => {
    touchEndY = e.changedTouches[0].screenY;
    handleSwipe();
  }, { passive: true });

  function handleSwipe() {
    const swipeDistance = touchEndY - touchStartY;
    // Si swipe vers le bas de plus de 100px, fermer la modale
    if (swipeDistance > 100) {
      closeModal();
    }
  }

  // Gestion du pinch-to-zoom basique
  let initialDistance = 0;
  let currentScale = 1;

  modal.addEventListener("touchstart", (e) => {
    if (e.touches.length === 2) {
      initialDistance = getDistance(e.touches[0], e.touches[1]);
    }
  }, { passive: true });

  modal.addEventListener("touchmove", (e) => {
    if (e.touches.length === 2) {
      const currentDistance = getDistance(e.touches[0], e.touches[1]);
      const scale = currentDistance / initialDistance;
      currentScale = Math.min(Math.max(1, scale), 3); // Limiter entre 1x et 3x
      if (modalImage) {
        modalImage.style.transform = `scale(${currentScale})`;
      }
    }
  }, { passive: true });

  function getDistance(touch1, touch2) {
    const dx = touch1.clientX - touch2.clientX;
    const dy = touch1.clientY - touch2.clientY;
    return Math.sqrt(dx * dx + dy * dy);
  }

  console.log("[MAP] Modale image affichée pour zone:", zoneName);
}

// ==========================================
// AUTO-INITIALISATION
// ==========================================

document.addEventListener("DOMContentLoaded", () => {
  console.log("[MAP] ━━━━━━━━━━━━━━━━━━━━━━━━━━━━");
  console.log("[MAP] Auto-initialisation du système de carte");
  console.log("[MAP] ━━━━━━━━━━━━━━━━━━━━━━━━━━━━");
  initMapModal();
  initMapHighlight();
  initMapClicks();
  console.log("[MAP] Initialisation terminée");
});

// Exposer les fonctions globalement si nécessaire
window.initMapModal = initMapModal;
window.initMapHighlight = initMapHighlight;
window.initMapClicks = initMapClicks;
window.showZoneImage = showZoneImage;