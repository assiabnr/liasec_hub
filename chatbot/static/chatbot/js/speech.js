"use strict";

import { STATE } from "./config.js";

export function speak(text) {
  if (!STATE.voiceEnabled) return;
  if (!("speechSynthesis" in window)) return;
  window.speechSynthesis.cancel();
  const u = new SpeechSynthesisUtterance(text);
  u.lang = "fr-FR";
  window.speechSynthesis.speak(u);
}

export function toggleVoice() {
  STATE.voiceEnabled = !STATE.voiceEnabled;
  if (!STATE.voiceEnabled && "speechSynthesis" in window) {
    window.speechSynthesis.cancel();
  }
  return STATE.voiceEnabled;
}