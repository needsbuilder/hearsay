// Hearsay web demo: a character counter and a busy state while a check runs.
// The page works without this script.
(function () {
  "use strict";
  var form = document.getElementById("check-form");
  if (!form) return;
  var text = document.getElementById("text");
  var count = document.getElementById("text-count");
  var button = document.getElementById("submit");
  var status = document.getElementById("status");
  var max = parseInt(form.getAttribute("data-max"), 10) || 0;

  function length() {
    // Count the way the server does: line endings as one character, outer whitespace ignored.
    return text.value.replace(/\r\n?/g, "\n").trim().length;
  }

  function update() {
    var n = length();
    count.textContent = n.toLocaleString("en-US") + " / " + max.toLocaleString("en-US") + " characters";
    count.classList.toggle("over", max > 0 && n > max);
  }

  text.addEventListener("input", update);
  update();

  form.addEventListener("submit", function (event) {
    if (max > 0 && length() > max) {
      event.preventDefault();
      status.textContent = "The text is longer than " + max.toLocaleString("en-US") + " characters. Shorten it first.";
      text.focus();
      return;
    }
    button.disabled = true;
    button.textContent = "Checking...";
    status.textContent =
      "Checking. Registry and advisory claims take seconds; documentation claims go to the jury and can take a minute or more.";
  });

  // Coming back to the page with the back button must not leave the button disabled.
  window.addEventListener("pageshow", function () {
    button.disabled = false;
    button.textContent = "Check claims";
  });
})();
