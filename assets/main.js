/* Theme toggle: remember the choice, keep the button honest about it. */
(function () {
  var root = document.documentElement;
  var button = document.getElementById("theme-toggle");
  var meta = document.querySelector('meta[name="theme-color"]');

  function paint(theme) {
    root.setAttribute("data-theme", theme);
    var dark = theme === "dark";
    if (button) {
      button.setAttribute("aria-pressed", dark ? "true" : "false");
      var label = dark ? "Switch to light theme" : "Switch to dark theme";
      button.setAttribute("aria-label", label);
      button.setAttribute("title", label);
    }
    if (meta) meta.setAttribute("content", dark ? "#0A0722" : "#F7F3E9");
  }

  paint(root.getAttribute("data-theme") === "dark" ? "dark" : "light");

  if (button) {
    button.addEventListener("click", function () {
      var next = root.getAttribute("data-theme") === "dark" ? "light" : "dark";
      paint(next);
      try { localStorage.setItem("td-theme", next); } catch (e) { /* private mode */ }
    });
  }

  var year = document.getElementById("year");
  if (year) year.textContent = String(new Date().getFullYear());
})();
