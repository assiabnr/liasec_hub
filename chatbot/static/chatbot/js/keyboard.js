"use strict";

const keyboardChatForm = document.getElementById("chatForm");
const keyboardChatInput = document.getElementById("chat-form-input");
//const feedback = document.getElementById("feedback");
const chatSendButtonsIA = document.querySelectorAll(".chat-send");
const wordS = document.getElementById('wordSuggestions');
const Elementword = document.getElementById('element-word');
const chatMessagesK = document.querySelector(".chat-messages");
const suggest = ['ballon', 'je cherche un ballon', 'tennis', 'basket', 'amateur','entraînement','compétition',
                'jeu spécifique','intérieur', 'extérieur','football', 'basketball', 'volleyball'];

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
  send: { class: "send", icon: "/static/chatbot/images/icons/keyboard/send.svg" },
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
      keyboardChatInput.value = keyboardChatInput.value.slice(0, -1);
      //wordSuggestions.style.display = 'none';
      break;
    case "space":
      keyboardChatInput.value += " ";
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

      keyboardElement.classList.remove("active");
      //wordSuggestions.style.display = 'none';
      sendMessage();
      break;
    default:
      if (!specialKeys[key]) {
        keyboardChatInput.value += isCapslock ? key.toUpperCase() : key;

        //console.log(keyboardChatInput.value)
        const inputText = keyboardChatInput.value;


        }
      break;
  }
  keyboardChatInput.focus();
}

function generateKeyboard() {
  const keyboardElement = document.createElement("div");
  keyboardElement.className = "keyboard";
  keyboardElement.addEventListener("click", (event) =>
  event.stopPropagation());
  keyboardChatForm.appendChild(keyboardElement);

  keyboardChatInput.addEventListener("input", (event) => {

    const value = event.target.value;
    const lastChar = value.slice(-1);
    event.target.value = value.slice(0, -1);
    event.target.value += isCapslock
      ? lastChar.toUpperCase()
      : lastChar.toLowerCase();
  });
  return keyboardElement;
}

function openKeyboard(keyboardElement) {
  createKeys(keyboardElement);
  keyboardElement.classList.add("active");
}

function closeKeyboard(event, keyboardElement) {
  if (
    !keyboardElement.contains(event.target) &&
    !event.target.closest(".feedback") &&
    event.target !== keyboardChatInput
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
      keyElement.type = key === "send" ? "submit" : "button";
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
            } else {
              keyElement.textContent = key.replace("numeric", "123");
            }
            if (key === "send") {
              keyElement.classList.add("chat-send");


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

const chatForm = document.getElementById("chatForm");
document.addEventListener("DOMContentLoaded", function () {
  window.scrollTo({
    top: document.body.scrollHeight,
    behavior: "smooth"  // smooth scrolling effect
  });
  const keyboardElement = generateKeyboard();

  keyboardChatInput.addEventListener("click", () =>{
    openKeyboard(keyboardElement);
    scrollToBottom();
  });

  document.addEventListener("click", (event) =>
    closeKeyboard(event, keyboardElement)

  );

  chatSendButtonsIA.forEach((button) => {
    button.addEventListener("click", (event) => {
      console.log("bon")
      event.preventDefault();
      keyboardChatInput.disabled = false;
      closeKeyboard(event, keyboardElement)
      sendMessage();
      scrollToBottom();
    });
  });

});