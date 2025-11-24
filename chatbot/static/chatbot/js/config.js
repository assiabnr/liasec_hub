"use strict";

export const DOM_SELECTORS = {
  chatMessages: document.getElementById("messages"),
  chatInput: document.getElementById("chat-form-input"),
  sendBtn: document.querySelector(".chat-send"),
  micBtn: document.querySelector(".chat-mic"),
  resetBtn: document.querySelector(".chat-reset"),
  soundBtn: document.querySelector(".chat-sound"),
  feedbackDock: document.getElementById("feedback-container"),
};

export const API_URLS = {
  chat: window.CHAT_API_URL || "/chatbot/api/ask/",
  reset: window.RESET_URL || "/chatbot/api/reset/",
  feedback: window.FEEDBACK_URL || "/chatbot/api/feedback/",
};

export const INACTIVITY_CONFIG = {
  popupAfterSec: 90,
  countdownSec: 30,
};

export const STATE = {
  lastInteractionId: null,
  voiceEnabled: true,
  isSending: false,
  recognizing: false,
  recognition: null,
  inactivityTimer: null,
  inactivityCountdownTimer: null,
  inactivityPopup: null,
  micLabelEl: null,
};