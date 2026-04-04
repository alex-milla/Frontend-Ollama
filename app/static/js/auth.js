/**
 * auth.js — Pequeñas mejoras de UX para login y change-password
 */
document.addEventListener("DOMContentLoaded", () => {
  // Mostrar/ocultar password
  document.querySelectorAll("[data-toggle-password]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const target = document.getElementById(btn.dataset.togglePassword);
      if (!target) return;
      const isText = target.type === "text";
      target.type = isText ? "password" : "text";
      btn.textContent = isText ? "👁" : "🙈";
    });
  });

  // Validación cliente para change-password
  const cpForm = document.getElementById("change-password-form");
  if (cpForm) {
    cpForm.addEventListener("submit", (e) => {
      const newPw = cpForm.querySelector('[name="new_password"]').value;
      const confirm = cpForm.querySelector('[name="confirm_password"]').value;
      const errEl = cpForm.querySelector(".client-error");
      if (errEl) errEl.textContent = "";

      if (newPw.length < 8) {
        e.preventDefault();
        if (errEl) errEl.textContent = "La contraseña debe tener al menos 8 caracteres.";
        return;
      }
      if (newPw !== confirm) {
        e.preventDefault();
        if (errEl) errEl.textContent = "Las contraseñas no coinciden.";
      }
    });
  }
});
