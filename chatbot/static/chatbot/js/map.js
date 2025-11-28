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

export function initMapModal() {
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

export function initMapHighlight() {
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
    console.log("[MAP] Événement localize-product reçu", e.detail);

    const { product, category, sport } = e.detail || {};

    if (!product) {
      console.warn("[MAP] Événement localize-product sans produit");
      return;
    }

    const categoryLabel = category || product.category || "";
    const sportLabel = sport || product.sport || "";

    if (!categoryLabel && !sportLabel) {
      console.warn("[MAP] Aucune catégorie ni sport pour localiser le produit");
      return;
    }

    // Vérifier que sport.js est chargé
    if (typeof window.getPathIdFromCategory !== "function") {
      console.error("[MAP] getPathIdFromCategory n'est pas disponible (sport.js non chargé ?)");
      return;
    }

    const pathId = window.getPathIdFromCategory(categoryLabel, sportLabel);

    console.log("[MAP] Sport :", sportLabel);
    console.log("[MAP] Catégorie :", categoryLabel);
    console.log("[MAP] Recherche de pathId pour :", categoryLabel, "dans sport:", sportLabel);
    console.log("[MAP] Résultat pathId :", pathId);

    if (!pathId || (Array.isArray(pathId) && pathId.length === 0)) {
      console.warn("[MAP] Aucune zone trouvée pour cette catégorie");

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
        console.warn("[MAP] Path non trouvé dans le SVG :", pathId);
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
      pathId.forEach((id) => {
        if (id) {
          const result = applyHighlight(svgDoc, id);
          if (result) zones.push(result);
        }
      });
    } else {
      // Single zone
      const result = applyHighlight(svgDoc, pathId);
      if (result) zones.push(result);
    }

    // ==========================================
    // DISPATCHER L'ÉVÉNEMENT DE LOCALISATION RÉUSSIE
    // ==========================================

    if (zones.length > 0) {
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
      console.log("[MAP] Événement product-localized dispatché", localizationEvent.detail);
    } else {
      console.warn("[MAP] Aucune zone n'a pu être highlightée");
    }
  });

  console.log("[MAP] Système de highlight initialisé (contexte:", isModalContext ? "chatbot" : "localisation", ")");
}

// ==========================================
// AUTO-INITIALISATION
// ==========================================

// Si le script est chargé comme module, ne rien faire automatiquement
// Si le script est chargé normalement, initialiser automatiquement
if (typeof module === 'undefined' || !module.exports) {
  document.addEventListener("DOMContentLoaded", () => {
    console.log("[MAP] Auto-initialisation du système de carte");
    initMapModal();
    initMapHighlight();
  });
}