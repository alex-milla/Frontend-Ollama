/**
 * theme.js — Gestión de tema con tres opciones: light / dark / system
 * Persiste la preferencia en localStorage.
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

    // Actualiza botones si existen
    document.querySelectorAll(".theme-btn[data-theme-value]").forEach((btn) => {
      btn.classList.toggle("active", btn.dataset.themeValue === pref);
    });
  }

  function setTheme(pref) {
    if (!THEMES.includes(pref)) pref = "system";
    localStorage.setItem(STORAGE_KEY, pref);
    applyTheme(pref);
  }

  // Aplica al cargar la página (antes de que el DOM esté listo para evitar flash)
  applyTheme(getPreferred());

  // Escucha cambios del sistema operativo
  window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", () => {
    if (getPreferred() === "system") applyTheme("system");
  });

  // Expone API global
  window.ThemeManager = { setTheme, getPreferred };

  // Inicializa botones cuando el DOM esté listo
  document.addEventListener("DOMContentLoaded", () => {
    document.querySelectorAll(".theme-btn[data-theme-value]").forEach((btn) => {
      btn.addEventListener("click", () => setTheme(btn.dataset.themeValue));
    });
    applyTheme(getPreferred()); // re-apply para sincronizar botones
  });
})();
