/**
 * projects.js — Gestión de proyectos y habilidades.
 */
(function () {
  "use strict";

  let allSkills = [];

  // ── Init ──────────────────────────────────────────────────────────────────
  document.addEventListener("DOMContentLoaded", () => {
    setupTabs();
    loadProjects();
    loadSkills();
    setupCreateProject();
    setupCreateSkill();
    setupProjectModal();
    setupSkillModal();
  });

  // ── Tabs ──────────────────────────────────────────────────────────────────
  function setupTabs() {
    document.querySelectorAll(".tab-btn").forEach(btn => {
      btn.addEventListener("click", () => {
        document.querySelectorAll(".tab-btn").forEach(b => b.classList.remove("active"));
        btn.classList.add("active");
        const tab = btn.dataset.tab;
        document.getElementById("tab-projects").style.display = tab === "projects" ? "" : "none";
        document.getElementById("tab-skills").style.display = tab === "skills" ? "" : "none";
      });
    });
  }

  // ── Proyectos ─────────────────────────────────────────────────────────────
  async function loadProjects() {
    const list = document.getElementById("projects-list");
    try {
      const res = await fetch("/projects/api/projects");
      const projects = await res.json();
      list.innerHTML = "";
      if (projects.length === 0) {
        list.innerHTML = '<p style="color:var(--text-secondary);font-size:.87rem;">Sin proyectos aún. Crea uno abajo.</p>';
        return;
      }
      projects.forEach(p => list.appendChild(buildProjectCard(p)));
    } catch {
      list.innerHTML = '<p style="color:#c62828">Error cargando proyectos.</p>';
    }
  }

  function buildProjectCard(p) {
    const card = document.createElement("div");
    card.style.cssText = `background:var(--bg-primary);border:1px solid var(--border);border-radius:var(--radius);padding:16px;cursor:pointer;transition:box-shadow var(--transition);`;
    card.innerHTML = `
      <div style="display:flex;align-items:flex-start;gap:8px;">
        <span style="font-size:1.2rem;">📁</span>
        <div style="flex:1;min-width:0;">
          <div style="font-weight:700;font-size:.95rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">${esc(p.name)}</div>
          <div style="font-size:.78rem;color:var(--text-secondary);margin-top:2px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">${esc(p.description || "Sin descripción")}</div>
        </div>
        <button class="conv-btn" title="Editar" data-edit="${p.id}">✎</button>
      </div>
      <div style="margin-top:12px;display:flex;gap:8px;">
        <a href="/?project_id=${p.id}" class="btn-sm" style="text-decoration:none;text-align:center;flex:1;">💬 Chatear</a>
      </div>`;
    card.querySelector("[data-edit]").addEventListener("click", e => {
      e.stopPropagation();
      openProjectModal(p.id);
    });
    card.addEventListener("mouseenter", () => card.style.boxShadow = "var(--shadow-md)");
    card.addEventListener("mouseleave", () => card.style.boxShadow = "");
    return card;
  }

  function setupCreateProject() {
    document.getElementById("btn-create-project").addEventListener("click", async () => {
      const name = document.getElementById("new-project-name").value.trim();
      const desc = document.getElementById("new-project-desc").value.trim();
      const errEl = document.getElementById("project-error");
      errEl.style.display = "none";
      if (!name) { errEl.textContent = "El nombre es obligatorio."; errEl.style.display = "block"; return; }
      try {
        const res = await fetch("/projects/api/projects", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ name, description: desc }),
        });
        const json = await res.json();
        if (!res.ok) { errEl.textContent = json.error; errEl.style.display = "block"; return; }
        document.getElementById("new-project-name").value = "";
        document.getElementById("new-project-desc").value = "";
        await loadProjects();
        showToast("Proyecto creado.");
      } catch { errEl.textContent = "Error de red."; errEl.style.display = "block"; }
    });
  }

  // ── Modal Proyecto ────────────────────────────────────────────────────────
  function setupProjectModal() {
    document.getElementById("modal-project-cancel").addEventListener("click", () => closeModal("modal-project"));
    document.getElementById("modal-project-save").addEventListener("click", saveProject);
    document.getElementById("modal-project-delete").addEventListener("click", deleteProject);
  }

  async function openProjectModal(id) {
    const res = await fetch(`/projects/api/projects/${id}`);
    const data = await res.json();
    const { project, skills, all_skills } = data;
    allSkills = all_skills;

    document.getElementById("edit-project-id").value = project.id;
    document.getElementById("edit-project-name").value = project.name;
    document.getElementById("edit-project-desc").value = project.description;

    const assignedIds = new Set(skills.map(s => s.id));
    const container = document.getElementById("edit-project-skills");
    container.innerHTML = "";

    if (all_skills.length === 0) {
      container.innerHTML = '<span style="font-size:.78rem;color:var(--text-secondary);">Sin habilidades disponibles. Crea alguna en la pestaña Habilidades.</span>';
    } else {
      all_skills.forEach(s => {
        const chip = document.createElement("div");
        const active = assignedIds.has(s.id);
        chip.className = "skill-chip" + (active ? " active" : "");
        chip.dataset.id = s.id;
        chip.style.cssText = `padding:4px 10px;border-radius:20px;font-size:.78rem;font-weight:600;cursor:pointer;border:1px solid ${active ? "var(--accent)" : "var(--border)"};background:${active ? "var(--accent-light)" : "transparent"};color:${active ? "var(--accent)" : "var(--text-secondary)"};transition:all var(--transition);display:inline-flex;align-items:center;gap:4px;`;
        chip.innerHTML = (active ? "✓ " : "+ ") + esc(s.name);
        chip.title = active ? "Clic para desasignar" : "Clic para asignar";
        chip.addEventListener("click", () => toggleChip(chip));
        container.appendChild(chip);
      });
    }

    document.getElementById("modal-project").style.display = "flex";
  }

  function toggleChip(chip) {
    const active = chip.classList.toggle("active");
    chip.style.borderColor = active ? "var(--accent)" : "var(--border)";
    chip.style.background = active ? "var(--accent-light)" : "transparent";
    chip.style.color = active ? "var(--accent)" : "var(--text-secondary)";
    chip.title = active ? "Clic para desasignar" : "Clic para asignar";
    // Actualizar icono prefijo
    const name = chip.innerHTML.replace(/^[✓+] /, "");
    chip.innerHTML = (active ? "✓ " : "+ ") + name;
  }

  async function saveProject() {
    const id = document.getElementById("edit-project-id").value;
    const name = document.getElementById("edit-project-name").value.trim();
    const desc = document.getElementById("edit-project-desc").value.trim();
    const skillIds = [...document.querySelectorAll(".skill-chip.active")].map(c => Number(c.dataset.id));

    await fetch(`/projects/api/projects/${id}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name, description: desc }),
    });
    await fetch(`/projects/api/projects/${id}/skills`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ skill_ids: skillIds }),
    });
    closeModal("modal-project");
    await loadProjects();
    showToast("Proyecto actualizado.");
  }

  async function deleteProject() {
    const id = document.getElementById("edit-project-id").value;
    if (!confirm("¿Eliminar este proyecto y todas sus conversaciones?")) return;
    await fetch(`/projects/api/projects/${id}`, { method: "DELETE" });
    closeModal("modal-project");
    await loadProjects();
    showToast("Proyecto eliminado.");
  }

  // ── Habilidades ───────────────────────────────────────────────────────────
  async function loadSkills() {
    const list = document.getElementById("skills-list");
    try {
      const res = await fetch("/projects/api/skills");
      const skills = await res.json();
      allSkills = skills;
      list.innerHTML = "";
      if (skills.length === 0) {
        list.innerHTML = '<p style="color:var(--text-secondary);font-size:.87rem;">Sin habilidades aún. Crea una abajo.</p>';
        return;
      }
      const table = document.createElement("table");
      table.className = "users-table";
      table.innerHTML = `<thead><tr><th>Nombre</th><th>Descripción</th><th>Acciones</th></tr></thead>`;
      const tbody = document.createElement("tbody");
      skills.forEach(s => {
        const tr = document.createElement("tr");
        tr.innerHTML = `
          <td><strong>${esc(s.name)}</strong></td>
          <td style="color:var(--text-secondary)">${esc(s.description || "–")}</td>
          <td><button class="btn-sm" data-edit-skill="${s.id}">Editar</button></td>`;
        tr.querySelector("[data-edit-skill]").addEventListener("click", () => openSkillModal(s));
        tbody.appendChild(tr);
      });
      table.appendChild(tbody);
      list.appendChild(table);
    } catch {
      list.innerHTML = '<p style="color:#c62828">Error cargando habilidades.</p>';
    }
  }

  function setupCreateSkill() {
    document.getElementById("btn-create-skill").addEventListener("click", async () => {
      const name = document.getElementById("new-skill-name").value.trim();
      const desc = document.getElementById("new-skill-desc").value.trim();
      const content = document.getElementById("new-skill-content").value.trim();
      const errEl = document.getElementById("skill-error");
      errEl.style.display = "none";
      if (!name || !content) { errEl.textContent = "Nombre y contenido son obligatorios."; errEl.style.display = "block"; return; }
      try {
        const res = await fetch("/projects/api/skills", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ name, description: desc, content }),
        });
        const json = await res.json();
        if (!res.ok) { errEl.textContent = json.error; errEl.style.display = "block"; return; }
        document.getElementById("new-skill-name").value = "";
        document.getElementById("new-skill-desc").value = "";
        document.getElementById("new-skill-content").value = "";
        await loadSkills();
        showToast("Habilidad creada.");
      } catch { errEl.textContent = "Error de red."; errEl.style.display = "block"; }
    });
  }

  // ── Modal Habilidad ───────────────────────────────────────────────────────
  function setupSkillModal() {
    document.getElementById("modal-skill-cancel").addEventListener("click", () => closeModal("modal-skill"));
    document.getElementById("modal-skill-save").addEventListener("click", saveSkill);
    document.getElementById("modal-skill-delete").addEventListener("click", deleteSkill);
  }

  function openSkillModal(s) {
    document.getElementById("edit-skill-id").value = s.id;
    document.getElementById("edit-skill-name").value = s.name;
    document.getElementById("edit-skill-desc").value = s.description;
    document.getElementById("edit-skill-content").value = s.content;
    document.getElementById("modal-skill").style.display = "flex";
  }

  async function saveSkill() {
    const id = document.getElementById("edit-skill-id").value;
    const name = document.getElementById("edit-skill-name").value.trim();
    const desc = document.getElementById("edit-skill-desc").value.trim();
    const content = document.getElementById("edit-skill-content").value.trim();
    await fetch(`/projects/api/skills/${id}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name, description: desc, content }),
    });
    closeModal("modal-skill");
    await loadSkills();
    showToast("Habilidad actualizada.");
  }

  async function deleteSkill() {
    const id = document.getElementById("edit-skill-id").value;
    if (!confirm("¿Eliminar esta habilidad?")) return;
    await fetch(`/projects/api/skills/${id}`, { method: "DELETE" });
    closeModal("modal-skill");
    await loadSkills();
    showToast("Habilidad eliminada.");
  }

  // ── Helpers ───────────────────────────────────────────────────────────────
  function closeModal(id) { document.getElementById(id).style.display = "none"; }

  function esc(str) {
    return String(str).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;").replace(/'/g,"&#39;");
  }

  let toastT;
  function showToast(msg) {
    let t = document.getElementById("toast");
    if (!t) {
      t = document.createElement("div");
      t.id = "toast";
      t.style.cssText = "position:fixed;bottom:24px;right:24px;background:var(--text-primary);color:var(--bg-primary);padding:12px 20px;border-radius:8px;font-size:.85rem;font-weight:600;z-index:9999;box-shadow:0 4px 16px rgba(0,0,0,.2);font-family:var(--font-sans);";
      document.body.appendChild(t);
    }
    t.textContent = msg;
    t.style.display = "block";
    clearTimeout(toastT);
    toastT = setTimeout(() => t.style.display = "none", 3000);
  }
})();
