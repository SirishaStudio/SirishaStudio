/* theme.js — light/dark mode toggle, persisted in localStorage */
(function () {
  const DARK_KEY = "ss_dark";

  function applyTheme(dark) {
    document.body.classList.toggle("dark", dark);
    const btn = document.getElementById("theme_btn");
    if (btn) btn.textContent = dark ? "☀ Light" : "🌙 Dark";
  }

  // Apply immediately (before paint) to avoid flash
  const savedDark = localStorage.getItem(DARK_KEY) === "1";
  // Run as soon as <body> exists — we inject class on DOMContentLoaded if needed
  document.addEventListener("DOMContentLoaded", function () {
    applyTheme(savedDark);
  });

  window.toggleTheme = function () {
    const nowDark = !document.body.classList.contains("dark");
    localStorage.setItem(DARK_KEY, nowDark ? "1" : "0");
    applyTheme(nowDark);
  };
})();
