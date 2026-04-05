/**
 * theme.js — Gestión de tema con tres opciones: light / dark / system
 */
(function () {
  const STORAGE_KEY = "fo-theme";
  const THEMES = ["light", "dark", "system"];

  function getPreferred() {
    return localStorage.getItem(STORAGE_KEY) || "system";
  }

  function resolveEffective(pref) {
    if (pref === "system") {
      return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
    }
    return pref;
  }

  function applyTheme(pref) {
    const effective = resolveEffective(pref);
    document.documentElement.setAttribute("data-theme", effective);
    document.querySelectorAll(".theme-btn[data-theme-value]").forEach((btn) => {
      btn.classList.toggle("active", btn.dataset.themeValue === pref);
    });
  }

  function setTheme(pref) {
    if (!THEMES.includes(pref)) pref = "system";
    localStorage.setItem(STORAGE_KEY, pref);
    applyTheme(pref);
  }

  applyTheme(getPreferred());

  window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", () => {
    if (getPreferred() === "system") applyTheme("system");
  });

  window.ThemeManager = { setTheme, getPreferred };

  document.addEventListener("DOMContentLoaded", () => {
    document.querySelectorAll(".theme-btn[data-theme-value]").forEach((btn) => {
      btn.addEventListener("click", () => setTheme(btn.dataset.themeValue));
    });
    applyTheme(getPreferred());
  });
})();
