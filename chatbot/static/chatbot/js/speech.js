"use strict";

import { STATE } from "./config.js";

export function speak(text) {
  if (!STATE.voiceEnabled) return;
  if (!("speechSynthesis" in window)) return;
  window.speechSynthesis.cancel();

  const u = new SpeechSynthesisUtterance(text);
  u.lang = "fr-FR";

  // Appliquer les paramètres de voix
  u.volume = STATE.voiceSettings.volume; // 0 à 1
  u.rate = STATE.voiceSettings.rate; // 0.1 à 10
  u.pitch = STATE.voiceSettings.pitch; // 0 à 2

  // Utiliser la voix sélectionnée si disponible
  if (STATE.voiceSettings.voice) {
    u.voice = STATE.voiceSettings.voice;
  }

  window.speechSynthesis.speak(u);
}

export function toggleVoice() {
  STATE.voiceEnabled = !STATE.voiceEnabled;
  if (!STATE.voiceEnabled && "speechSynthesis" in window) {
    window.speechSynthesis.cancel();
  }
  return STATE.voiceEnabled;
}

// Récupérer les voix disponibles
export function getAvailableVoices() {
  if (!("speechSynthesis" in window)) return [];
  return window.speechSynthesis.getVoices();
}

// Définir le volume (0 à 1)
export function setVolume(volume) {
  STATE.voiceSettings.volume = Math.max(0, Math.min(1, volume));
}

// Définir la vitesse (0.1 à 10, normal = 1)
export function setRate(rate) {
  STATE.voiceSettings.rate = Math.max(0.1, Math.min(10, rate));
}

// Définir la tonalité (0 à 2, normal = 1)
export function setPitch(pitch) {
  STATE.voiceSettings.pitch = Math.max(0, Math.min(2, pitch));
}

// Définir la voix
export function setVoice(voice) {
  STATE.voiceSettings.voice = voice;
}

// Initialiser la voix masculine par défaut (Gerard ou autre)
export function initializeDefaultVoice() {
  return new Promise((resolve) => {
    const feminineNames = ['hortense', 'julie', 'denise', 'marie', 'celine', 'amelie', 'lea', 'pauline'];

    function setDefaultMasculineVoice() {
      const voices = window.speechSynthesis.getVoices();
      if (voices.length === 0) {
        // Les voix ne sont pas encore chargées, réessayer
        return false;
      }

      const frenchVoices = voices.filter(v => v.lang.startsWith('fr'));

      // 1. Chercher Gerard d'abord
      let selectedVoice = frenchVoices.find(v =>
        v.name.toLowerCase().includes('gerard')
      );

      // 2. Si Gerard n'est pas disponible, chercher une autre voix masculine
      if (!selectedVoice) {
        // Filtrer les voix masculines (exclure les voix féminines)
        const masculineVoices = frenchVoices.filter(v => {
          const nameLower = v.name.toLowerCase();
          return !feminineNames.some(fname => nameLower.includes(fname));
        });

        // Prioriser les voix Online parmi les voix masculines
        selectedVoice = masculineVoices.find(v =>
          v.name.toLowerCase().includes('online')
        );

        // Si pas de voix Online masculine, prendre la première voix masculine
        if (!selectedVoice && masculineVoices.length > 0) {
          selectedVoice = masculineVoices[0];
        }
      }

      // 3. Définir la voix sélectionnée
      if (selectedVoice) {
        STATE.voiceSettings.voice = selectedVoice;
        console.log('Voix masculine initialisée par défaut:', selectedVoice.name);
        return true;
      } else {
        console.warn('Aucune voix masculine française trouvée, utilisation de la voix par défaut du navigateur');
        return true; // On considère quand même l'initialisation comme réussie
      }
    }

    // Essayer immédiatement
    if (setDefaultMasculineVoice()) {
      resolve();
      return;
    }

    // Si les voix ne sont pas encore chargées, attendre l'événement voiceschanged
    const onVoicesChanged = () => {
      if (setDefaultMasculineVoice()) {
        resolve();
      }
    };

    window.speechSynthesis.addEventListener('voiceschanged', onVoicesChanged, { once: true });

    // Timeout de sécurité après 2 secondes
    setTimeout(() => {
      resolve();
    }, 2000);
  });
}