// Open the Material search dialog with Ctrl+K (Windows/Linux) or Cmd+K (macOS).
// Material's own shortcut handler ignores key presses that carry Ctrl or Meta,
// so this does not fight the built-in f / s / / shortcuts.
(function () {
  function openSearch() {
    var state = document.getElementById("__search");
    var label = document.querySelector('label[for="__search"]');

    // Only toggle the dialog open; clicking while it is open would close it.
    if (state && !state.checked && label) {
      label.click();
    }

    var input = document.querySelector(".md-search__input");
    if (!input) return;

    // The dialog becomes visible on the next frame, so focus after it does.
    window.requestAnimationFrame(function () {
      input.focus();
      input.select();
    });
  }

  document.addEventListener("keydown", function (event) {
    if (!(event.ctrlKey || event.metaKey)) return;
    if (event.altKey || event.shiftKey) return;
    if (event.key.toLowerCase() !== "k") return;

    event.preventDefault();
    openSearch();
  });
})();
