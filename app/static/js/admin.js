/**
 * admin.js — Panel de administración: usuarios y configuración Ollama.
 */
(function () {
  "use strict";

  // ── Init ─────────────────────────────────────────────────────────────────────
  document.addEventListener("DOMContentLoaded", () => {
    loadUsers();
    setupCreateUser();
    setupOllamaConfig();
    setupCheckUpdate();
  });

  // ── Usuarios ──────────────────────────────────────────────────────────────────
  async function loadUsers() {
    const tbody = document.getElementById("users-tbody");
    if (!tbody) return;

    try {
      const res   = await fetch("/admin/api/users");
      const users = await res.json();
      tbody.innerHTML = "";

      if (users.length === 0) {
        tbody.innerHTML = '<tr><td colspan="5" style="text-align:center;color:var(--text-secondary)">Sin usuarios</td></tr>';
        return;
      }

      users.forEach((u) => {
        const tr = document.createElement("tr");
        tr.innerHTML = `
          <td>${esc(u.username)}</td>
          <td><span class="badge badge-${u.role}">${u.role}</span></td>
          <td>${u.must_change_password ? "⚠ Pendiente" : "✓ OK"}</td>
          <td>${formatDate(u.created_at)}</td>
          <td>
            <div class="table-actions">
              <button class="btn-sm" data-action="reset" data-id="${u.id}" data-name="${esc(u.username)}">Reset pwd</button>
              <button class="btn-sm danger" data-action="delete" data-id="${u.id}" data-name="${esc(u.username)}">Eliminar</button>
            </div>
          </td>`;

        tr.querySelector("[data-action='reset']").addEventListener("click", (e) => {
          resetPassword(Number(e.target.dataset.id), e.target.dataset.name);
        });
        tr.querySelector("[data-action='delete']").addEventListener("click", (e) => {
          confirmDeleteUser(Number(e.target.dataset.id), e.target.dataset.name);
        });

        tbody.appendChild(tr);
      });
    } catch {
      tbody.innerHTML = '<tr><td colspan="5" style="color:#c62828">Error cargando usuarios.</td></tr>';
    }
  }

  function setupCreateUser() {
    const form = document.getElementById("create-user-form");
    if (!form) return;
    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      const errEl = document.getElementById("create-user-error");
      if (errEl) errEl.textContent = "";

      const data = {
        username: form.username.value.trim(),
        password: form.password.value,
        role:     form.role.value,
      };

      try {
        const res  = await fetch("/admin/api/users", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(data),
        });
        const json = await res.json();
        if (!res.ok) {
          if (errEl) errEl.textContent = json.error || "Error al crear usuario.";
          return;
        }
        form.reset();
        await loadUsers();
        showToast("Usuario creado correctamente.");
      } catch {
        if (errEl) errEl.textContent = "Error de red.";
      }
    });
  }

  async function resetPassword(id, name) {
    if (!confirm(`¿Resetear contraseña de "${name}"?`)) return;
    try {
      const res  = await fetch(`/admin/api/users/${id}/reset-password`, { method: "PUT" });
      const json = await res.json();
      if (json.ok) {
        showToast(`Contraseña temporal: ${json.temp_password}`, 8000);
      } else {
        alert(json.error || "Error al resetear.");
      }
    } catch {
      alert("Error de red.");
    }
  }

  function confirmDeleteUser(id, name) {
    const overlay = document.createElement("div");
    overlay.className = "modal-overlay";
    overlay.innerHTML = `
      <div class="modal">
        <h3>Eliminar usuario</h3>
        <p>¿Eliminar al usuario <strong>${esc(name)}</strong>? Se borrarán todas sus conversaciones.</p>
        <div class="modal-actions">
          <button class="btn-sm" id="mc">Cancelar</button>
          <button class="btn-sm danger" id="md">Eliminar</button>
        </div>
      </div>`;
    document.body.appendChild(overlay);
    overlay.querySelector("#mc").addEventListener("click", () => overlay.remove());
    overlay.querySelector("#md").addEventListener("click", async () => {
      overlay.remove();
      try {
        const res  = await fetch(`/admin/api/users/${id}`, { method: "DELETE" });
        const json = await res.json();
        if (json.ok) { await loadUsers(); showToast("Usuario eliminado."); }
        else alert(json.error || "Error al eliminar.");
      } catch { alert("Error de red."); }
    });
  }

  // ── Configuración Ollama ──────────────────────────────────────────────────────
  function setupOllamaConfig() {
    const testBtn = document.getElementById("test-ollama-btn");
    const saveBtn = document.getElementById("save-ollama-btn");
    const hostInput = document.getElementById("ollama-host-input");
    const statusEl = document.getElementById("ollama-test-status");
    const modelListEl = document.getElementById("ollama-model-list");

    if (!testBtn || !hostInput) return;

    testBtn.addEventListener("click", async () => {
      statusEl.textContent = "Probando…";
      statusEl.className = "ollama-status-badge";
      modelListEl.innerHTML = "";
      try {
        // Test directo al endpoint
        const res  = await fetch("/api/ollama/status");
        const data = await res.json();
        statusEl.className = "ollama-status-badge " + (data.ok ? "ok" : "err");
        statusEl.textContent = data.ok
          ? `✓ Conectado · ${data.models_count} modelo(s)`
          : "✗ Sin conexión";

        if (data.ok) {
          const modRes  = await fetch("/api/models");
          const modData = await modRes.json();
          modelListEl.innerHTML = (modData.models || []).map((m) => `<li>${esc(m)}</li>`).join("");
        }
      } catch {
        statusEl.className = "ollama-status-badge err";
        statusEl.textContent = "✗ Error de red";
      }
    });

    if (saveBtn) {
      saveBtn.addEventListener("click", async () => {
        const host = hostInput.value.trim();
        if (!host) return;
        try {
          const res  = await fetch("/api/settings/ollama", {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ host }),
          });
          const json = await res.json();
          if (json.ok) showToast("Host de Ollama guardado.");
          else alert(json.error || "Error al guardar.");
        } catch { alert("Error de red."); }
      });
    }
  }

  // ── Check update ──────────────────────────────────────────────────────────────
  function setupCheckUpdate() {
    const btn = document.getElementById("check-update-btn");
    const res = document.getElementById("update-result");
    if (!btn || !res) return;

    btn.addEventListener("click", async () => {
      res.textContent = "Consultando GitHub…";
      try {
        const r    = await fetch("/admin/api/check-update");
        const data = await r.json();
        if (data.error) { res.textContent = "Error: " + data.error; return; }
        res.textContent = data.update_available
          ? `🆕 Nueva versión: ${data.latest} (actual: ${data.current})`
          : `✓ Al día · versión ${data.current}`;
      } catch { res.textContent = "Error de red."; }
    });
  }

  // ── Helpers ───────────────────────────────────────────────────────────────────
  function esc(str) {
    return String(str)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;")
      .replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#39;");
  }

  function formatDate(iso) {
    if (!iso) return "–";
    return new Date(iso).toLocaleDateString("es-ES", { day: "2-digit", month: "short", year: "numeric" });
  }

  let toastTimeout;
  function showToast(msg, duration = 3500) {
    let toast = document.getElementById("admin-toast");
    if (!toast) {
      toast = document.createElement("div");
      toast.id = "admin-toast";
      toast.style.cssText = `
        position:fixed;bottom:24px;right:24px;background:var(--text-primary);color:var(--bg-primary);
        padding:12px 20px;border-radius:8px;font-size:.85rem;font-weight:600;z-index:9999;
        box-shadow:0 4px 16px rgba(0,0,0,.2);animation:fadeIn .2s ease;font-family:var(--font-sans);
        max-width:360px;word-break:break-word;`;
      document.body.appendChild(toast);
    }
    toast.textContent = msg;
    toast.style.display = "block";
    clearTimeout(toastTimeout);
    toastTimeout = setTimeout(() => { toast.style.display = "none"; }, duration);
  }
})();
