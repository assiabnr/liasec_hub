"use strict";

// Configuration pour la page de localisation
const locSearchInput = document.getElementById("locSearchInput");
const locSearchForm = document.getElementById("loc-search-form");

const keys = [
  ["a", "z", "e", "r", "t", "y", "u", "i", "o", "p"],
  ["q", "s", "d", "f", "g", "h", "j", "k", "l", "m"],
  ["capslock", "w", "x", "c", "v", "b", "n", "'", "backspace"],
  ["numeric", "space", "send"],
];
const numericKeys = [
  ["1", "2", "3", "4", "5", "6", "7", "8", "9", "0"],
  ["-", "/", ":", ";", "(", ")", "€", "&", "@", '"'],
  ["specialchars", ".", ",", "?", "!", "'", "backspace"],
  ["numeric", "space", "send"],
];
const specialCharsKeys = [
  ["[", "]", "{", "}", "#", "%", "^", "*", "+", "="],
  ["_", "\\", "|", "~", "<", ">", "$", "£", "¥", "•"],
  ["numeric", ".", ",", "?", "!", "'", "backspace"],
  ["normal", "space", "send"],
];
const specialKeys = {
  numeric: {
    class: "numeric",
  },
  capslock: {
    class: "capslock",
    icon: "/static/chatbot/images/icons/keyboard/capslock.svg",
  },
  backspace: {
    class: "backspace",
    icon: "/static/chatbot/images/icons/keyboard/backspace.svg",
  },
  send: {
    class: "send",
    icon: "/static/chatbot/images/icons/keyboard/send.svg"
  },
};

let isNumeric = false;
let isCapslock = false;
let isSpecialChars = false;

function createKeyIcon(keyElement, iconPath) {
  const keyIconElement = document.createElement("img");
  keyIconElement.className = "key-icon";
  keyIconElement.src = iconPath;
  keyElement.appendChild(keyIconElement);
}

function handleKeyPress(event, key) {
  event.preventDefault();

  const keyboardElement = document.querySelector(".keyboard");
  const keyboardTyping = new CustomEvent("keyboardTyping");
  document.dispatchEvent(keyboardTyping);

  switch (key) {
    case "backspace":
      locSearchInput.value = locSearchInput.value.slice(0, -1);
      break;
    case "space":
      locSearchInput.value += " ";
      break;
    case "capslock":
      isCapslock = !isCapslock;
      const keys = document.querySelectorAll(".key");
      for (let index = 0; index < keys.length; index++) {
        const element = keys[index];
        const specialClasses = [
          "capslock",
          "backspace",
          "numeric",
          "space",
          "send",
        ];
        if (
          specialClasses.some((specialClass) =>
            element.classList.contains(specialClass)
          )
        ) {
          continue;
        }
        element.textContent = isCapslock
          ? element.textContent.toUpperCase()
          : element.textContent.toLowerCase();
      }
      break;
    case "numeric":
      isNumeric = !isNumeric;
      if (keyboardElement.classList.contains("specialchars")) {
        keyboardElement.classList.remove("specialchars");
        isSpecialChars = false;
      }
      keyboardElement.classList.toggle("numeric");
      createKeys(keyboardElement);
      break;
    case "specialchars":
      isSpecialChars = !isSpecialChars;
      if (keyboardElement.classList.contains("numeric")) {
        keyboardElement.classList.remove("numeric");
        isNumeric = false;
      }
      keyboardElement.classList.toggle("specialchars");
      createKeys(keyboardElement);
      break;
    case "normal":
      if (keyboardElement.classList.contains("numeric")) {
        keyboardElement.classList.remove("numeric");
        isNumeric = false;
      }
      if (keyboardElement.classList.contains("specialchars")) {
        keyboardElement.classList.remove("specialchars");
        isSpecialChars = false;
      }
      createKeys(keyboardElement);
      break;
    case "send":
      // Déclencher le submit du formulaire
      keyboardElement.classList.remove("active");
      if (locSearchForm) {
        locSearchForm.dispatchEvent(new Event('submit'));
      }
      break;
    default:
      if (!specialKeys[key]) {
        locSearchInput.value += isCapslock ? key.toUpperCase() : key;
      }
      break;
  }
  locSearchInput.focus();
}

function resetKeyboard(keyboardElement) {
  keyboardElement.innerHTML = "";
}

function createKeys(keyboardElement) {
  resetKeyboard(keyboardElement);

  const keysToUse = isSpecialChars
    ? specialCharsKeys
    : isNumeric
    ? numericKeys
    : keys;

  keysToUse.forEach((row) => {
    const keyRow = document.createElement("div");
    keyRow.className = "key-row";

    row.forEach((key) => {
      const keyElement = document.createElement("button");
      keyElement.type = "button";
      keyElement.className = "key";

      switch (key) {
        case "normal":
          keyElement.textContent = "ABC";
          keyElement.classList.add(key);
          break;
        case "space":
          keyElement.textContent = " ";
          keyElement.classList.add(key);
          break;
        case "numeric":
          keyElement.textContent = "123";
          keyElement.classList.add(key);
          break;
        case "specialchars":
          keyElement.textContent = "#+=";
          keyElement.classList.add(key);
          break;
        default:
          if (specialKeys[key]) {
            keyElement.classList.add(specialKeys[key].class);
            if (specialKeys[key].icon) {
              createKeyIcon(keyElement, specialKeys[key].icon);
            } else if (specialKeys[key].text) {
              keyElement.textContent = specialKeys[key].text;
            } else {
              keyElement.textContent = key.replace("numeric", "123");
            }
          } else {
            keyElement.textContent = isCapslock ? key.toUpperCase() : key;
          }
          break;
      }

      keyElement.addEventListener("click", (event) =>
        handleKeyPress(event, key)
      );
      keyRow.appendChild(keyElement);
    });

    keyboardElement.appendChild(keyRow);
  });

  const keyboardCreateEvent = new CustomEvent("keyboardCreated");
  document.dispatchEvent(keyboardCreateEvent);
}

function openKeyboard(keyboardElement) {
  createKeys(keyboardElement);
  keyboardElement.classList.add("active");

  // Le clavier est maintenant en position fixed, pas besoin d'ajuster le padding
  locSearchInput.focus();
}

function closeKeyboard(event, keyboardElement) {
  if (
    !keyboardElement.contains(event.target) &&
    event.target !== locSearchInput
  ) {
    isCapslock = false;
    isNumeric = false;
    isSpecialChars = false;
    const classesToKeep = ["keyboard"];
    const classesToRemove = Array.from(keyboardElement.classList).filter(
      (className) => !classesToKeep.includes(className)
    );
    keyboardElement.classList.remove(...classesToRemove);
    resetKeyboard(keyboardElement);
  }
}

// Initialisation du clavier pour la page de localisation
document.addEventListener("DOMContentLoaded", function () {
  if (!locSearchInput) {
    console.warn("[KEYBOARD-LOC] Input de recherche non trouvé");
    return;
  }

  const keyboardElement = document.querySelector(".keyboard");
  if (!keyboardElement) {
    console.warn("[KEYBOARD-LOC] Élément clavier non trouvé");
    return;
  }

  keyboardElement.addEventListener("click", (event) => event.stopPropagation());

  locSearchInput.addEventListener("click", () => {
    openKeyboard(keyboardElement);
  });

  document.addEventListener("click", (event) =>
    closeKeyboard(event, keyboardElement)
  );

  console.log("[KEYBOARD-LOC] Clavier virtuel initialisé pour la page de localisation");
});
