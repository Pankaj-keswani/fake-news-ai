// Applies the saved (or system) colour theme before the page paints, so there's no flash.
(function () {
  var theme = null;
  try { theme = localStorage.getItem("fnd_theme"); } catch (e) { /* storage blocked */ }
  if (theme !== "light" && theme !== "dark") {
    theme = window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  }
  document.documentElement.setAttribute("data-theme", theme);
})();
