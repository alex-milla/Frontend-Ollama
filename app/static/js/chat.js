/**
 * chat.js — Chat con soporte de proyectos, habilidades y adjuntos.
 */
(function () {
  "use strict";

  let currentConvId  = null;
  let isStreaming    = false;
  let currentProject = null;
  let activeSkillIds = [];
  let allProjects    = [];

  const messagesArea    = document.getElementById("messages-area");
  const messagesInner   = document.getElementById("messages-inner");
  const chatTextarea    = document.getElementById("chat-textarea");
  const sendBtn         = document.getElementById("send-btn");
  const modelSelect     = document.getElementById("model-select");
  const statusDot       = document.getElementById("status-dot");
  const statusText      = document.getElementById("status-text");
  const convList        = document.getElementById("conv-list");
  const newChatBtn      = document.getElementById("btn-new-chat");
  const sidebarToggle   = document.getElementById("btn-sidebar-toggle");
  const sidebar         = document.getElementById("sidebar");
  const sidebarOverlay  = document.getElementById("sidebar-overlay");
  const projectSelect   = document.getElementById("project-select");
  const skillsPanel     = document.getElementById("skills-panel");
  const skillsChips     = document.getElementById("skills-chips");
  const projectBadge    = document.getElementById("project-badge");

  // ── API pública para attachments.js ─────────────────────────────────────────

  window.getCurrentConvId    = () => currentConvId;
  window.getCurrentProjectId = () => currentProject ? currentProject.id : null;
  window.setCurrentConvId    = (id) => {
    currentConvId = id;
    setActiveConv(id);
  };

  // ── Init ─────────────────────────────────────────────────────────────────────

  async function init() {
    await loadModels();
    await checkOllamaStatus();
    await loadProjects();
    setupTextarea();
    setupSidebar();

    const params = new URLSearchParams(window.location.search);
    const pid = params.get("project_id");
    if (pid) {
      const opt = projectSelect.querySelector(`option[value="${pid}"]`);
      if (opt) {
        projectSelect.value = pid;
        await onProjectChange();
        return;
      }
    }
    await loadConversations();
  }

  async function loadModels() {
    try {
      const res = await fetch("/api/models");
      const data = await res.json();
      modelSelect.innerHTML = "";
      (data.models || []).forEach(m => {
        const opt = document.createElement("option");
        opt.value = m; opt.textContent = m;
        modelSelect.appendChild(opt);
      });
      if (!data.models || !data.models.length)
        modelSelect.innerHTML = '<option value="">Sin modelos disponibles</option>';
    } catch {
      modelSelect.innerHTML = '<option value="">Error cargando modelos</option>';
    }
  }

  async function checkOllamaStatus() {
    try {
      const res = await fetch("/api/ollama/status");
      const data = await res.json();
      statusDot.className = "status-dot " + (data.ok ? "ok" : "err");
      statusText.textContent = data.ok
        ? `Ollama · ${data.models_count} modelo${data.models_count !== 1 ? "s" : ""}`
        : "Ollama desconectado";
    } catch {
      statusDot.className = "status-dot err";
      statusText.textContent = "Sin conexión";
    }
  }

  async function loadProjects() {
    try {
      const res = await fetch("/projects/api/projects");
      allProjects = await res.json();
      while (projectSelect.options.length > 1) projectSelect.remove(1);
      allProjects.forEach(p => {
        const opt = document.createElement("option");
        opt.value = String(p.id);
        opt.textContent = p.name;
        projectSelect.appendChild(opt);
      });
    } catch { }
    projectSelect.addEventListener("change", onProjectChange);
  }

  async function onProjectChange() {
    const pid = projectSelect.value ? Number(projectSelect.value) : null;
    activeSkillIds = [];

    if (!pid) {
      currentProject = null;
      skillsPanel.style.display = "none";
      projectBadge.style.display = "none";
      updateSaveBtn();
      await loadConversations();
      return;
    }

    try {
      const res = await fetch(`/projects/api/projects/${pid}`);
      const data = await res.json();
      currentProject = data.project;

      projectBadge.textContent = "📁 " + data.project.name;
      projectBadge.style.display = "";

      skillsChips.innerHTML = "";
      if (!data.skills || data.skills.length === 0) {
        skillsPanel.style.display = "none";
      } else {
        skillsPanel.style.display = "";
        data.skills.forEach(s => {
          const chip = document.createElement("div");
          chip.dataset.id = s.id;
          chip.style.cssText = "padding:3px 8px;border-radius:12px;font-size:.72rem;font-weight:600;cursor:pointer;border:1px solid var(--accent);background:var(--accent-light);color:var(--accent);transition:all var(--transition);";
          chip.textContent = s.name;
          chip.title = s.description || s.name;
          activeSkillIds.push(s.id);
          chip.addEventListener("click", () => toggleSkillChip(chip, s.id));
          skillsChips.appendChild(chip);
        });
      }
      updateSaveBtn();
      await loadConversations();
    } catch { }
  }

  function updateSaveBtn() {
    const saveBtn = document.getElementById("export-save-btn");
    if (!saveBtn) return;
    saveBtn.style.display = currentProject ? "" : "none";
  }

  function toggleSkillChip(chip, skillId) {
    const idx = activeSkillIds.indexOf(skillId);
    if (idx === -1) {
      activeSkillIds.push(skillId);
      chip.style.background = "var(--accent-light)";
      chip.style.borderColor = "var(--accent)";
      chip.style.color = "var(--accent)";
      chip.style.opacity = "1";
    } else {
      activeSkillIds.splice(idx, 1);
      chip.style.background = "transparent";
      chip.style.borderColor = "var(--border-sidebar)";
      chip.style.color = "var(--text-sidebar-muted)";
      chip.style.opacity = ".5";
    }
  }

  async function loadConversations() {
    try {
      const pid = currentProject ? currentProject.id : "";
      const url = pid ? `/api/conversations?project_id=${pid}` : "/api/conversations";
      const res = await fetch(url);
      const convs = await res.json();
      renderConvList(convs);
    } catch { }
  }

  function renderConvList(convs) {
    convList.innerHTML = "";
    if (convs.length === 0) {
      convList.innerHTML = '<p style="font-size:.78rem;color:var(--text-sidebar-muted);padding:8px 10px">Sin conversaciones aún</p>';
      return;
    }
    convs.forEach(c => convList.appendChild(buildConvItem(c)));
  }

  function buildConvItem(c) {
    const el = document.createElement("div");
    el.className = "conv-item" + (c.id === currentConvId ? " active" : "");
    el.dataset.id = c.id;
    el.innerHTML = `
      <span class="conv-title" title="${esc(c.title)}">${esc(c.title)}</span>
      <span class="conv-actions">
        <button class="conv-btn" data-action="move" title="Mover a proyecto">📁</button>
        <button class="conv-btn" data-action="export" title="Exportar">⬇</button>
        <button class="conv-btn" data-action="delete" title="Eliminar">✕</button>
      </span>`;
    el.addEventListener("click", e => {
      if (e.target.closest("[data-action]")) return;
      loadConversation(c.id, c.title);
    });
    el.querySelector("[data-action='delete']").addEventListener("click", e => {
      e.stopPropagation(); confirmDelete(c.id, c.title);
    });
    el.querySelector("[data-action='export']").addEventListener("click", e => {
      e.stopPropagation(); window.location.href = `/api/conversations/${c.id}/export`;
    });
    el.querySelector("[data-action='move']").addEventListener("click", e => {
      e.stopPropagation(); openMoveModal(c.id, c.title);
    });
    return el;
  }

  function openMoveModal(convId, convTitle) {
    const existing = document.getElementById("move-modal-overlay");
    if (existing) existing.remove();

    const opts = allProjects.map(p =>
      `<option value="${p.id}">${esc(p.name)}</option>`
    ).join("");

    const overlay = document.createElement("div");
    overlay.className = "modal-overlay";
    overlay.id = "move-modal-overlay";
    overlay.innerHTML = `
      <div class="modal">
        <h3>Mover conversación</h3>
        <p style="margin-bottom:12px;font-size:.85rem;color:var(--text-secondary);">${esc(convTitle)}</p>
        <select id="move-project-select" class="form-input" style="margin-bottom:16px;">
          <option value="">— Sin proyecto —</option>
          ${opts}
        </select>
        <div class="modal-actions">
          <button class="btn-sm" id="move-cancel">Cancelar</button>
          <button class="btn-primary" style="padding:6px 16px;" id="move-confirm">Mover</button>
        </div>
      </div>`;
    document.body.appendChild(overlay);

    if (currentProject) {
      overlay.querySelector("#move-project-select").value = String(currentProject.id);
    }

    overlay.querySelector("#move-cancel").addEventListener("click", () => overlay.remove());
    overlay.querySelector("#move-confirm").addEventListener("click", async () => {
      const newPid = overlay.querySelector("#move-project-select").value;
      overlay.remove();
      await fetch(`/api/conversations/${convId}/move`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ project_id: newPid ? Number(newPid) : null }),
      });
      await loadConversations();
    });
  }

  function setActiveConv(id) {
    document.querySelectorAll(".conv-item").forEach(el =>
      el.classList.toggle("active", Number(el.dataset.id) === id)
    );
  }

  async function loadConversation(id, title) {
    if (isStreaming) return;
    closeSidebar();
    currentConvId = id;
    setActiveConv(id);

    messagesInner.innerHTML = `
      <div class="message assistant">
        <div class="message-avatar">AI</div>
        <div class="message-body" style="flex:1">
          <div class="message-bubble">
            <div class="skeleton-line" style="width:80%"></div>
            <div class="skeleton-line" style="width:60%;margin-top:6px"></div>
          </div>
        </div>
      </div>`;

    try {
      const res = await fetch(`/api/conversations/${id}`);
      const data = await res.json();
      renderMessages(data.messages || []);
      if (data.conversation?.model) {
        const opt = modelSelect.querySelector(`option[value="${CSS.escape(data.conversation.model)}"]`);
        if (opt) modelSelect.value = data.conversation.model;
      }
    } catch {
      messagesInner.innerHTML = '<p style="color:var(--text-secondary);text-align:center;padding:32px">Error cargando conversación.</p>';
    }
  }

  function renderMessages(msgs) {
    if (msgs.length === 0) { showEmptyState(); return; }
    messagesInner.innerHTML = "";
    msgs.forEach(m => appendMessage(m.role, m.content));
    scrollToBottom();
  }

  function showEmptyState() {
    const projectHint = currentProject
      ? `<p>Proyecto: <strong>${esc(currentProject.name)}</strong> · ${activeSkillIds.length} habilidad(es) activa(s)</p>`
      : "<p>Selecciona un modelo y escribe tu primer mensaje.</p>";
    messagesInner.innerHTML = `
      <div class="empty-state">
        <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
          <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
        </svg>
        <h2>¿En qué puedo ayudarte?</h2>
        ${projectHint}
      </div>`;
  }

  function newChat() {
    if (isStreaming) return;
    currentConvId = null;
    document.querySelectorAll(".conv-item").forEach(el => el.classList.remove("active"));
    showEmptyState();
    closeSidebar();
    chatTextarea.focus();
  }

  async function sendMessage() {
    let content = chatTextarea.value.trim();
    const model   = modelSelect.value;
    if (!content || !model || isStreaming) return;

    // Inyectar contexto del adjunto si existe
    const attachCtx = window.getAttachmentContext ? window.getAttachmentContext() : null;
    if (attachCtx) {
      content = content + attachCtx;
    }

    const emptyState = messagesInner.querySelector(".empty-state");
    if (emptyState) emptyState.remove();

    // Solo mostrar al usuario el texto original (sin el contexto del adjunto)
    const displayContent = chatTextarea.value.trim();
    chatTextarea.value = "";
    resizeTextarea();
    setStreaming(true);

    appendMessage("user", displayContent);
    const thinkingEl = appendThinking();
    scrollToBottom();

    const body = { message: content, model, skill_ids: activeSkillIds };
    if (currentConvId) body.conversation_id = currentConvId;
    if (currentProject) body.project_id = currentProject.id;

    const response = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });

    if (!response.ok) {
      thinkingEl.remove();
      appendError("Error al conectar con el servidor.");
      setStreaming(false);
      return;
    }

    // Limpiar adjunto de un solo uso después del envío
    if (window.clearAttachmentAfterSend) window.clearAttachmentAfterSend();

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    let assistantBubble = null;
    let fullText = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop();

      for (const line of lines) {
        if (!line.startsWith("data: ")) continue;
        const raw = line.slice(6).trim();
        if (raw === "[DONE]") {
          setStreaming(false);
          await loadConversations();
          break;
        }
        try {
          const obj = JSON.parse(raw);
          if (obj.conv_id && !currentConvId) {
            currentConvId = obj.conv_id;
            setActiveConv(currentConvId);
          }
          if (obj.token) {
            thinkingEl.remove();
            if (!assistantBubble) assistantBubble = appendMessageStreaming();
            fullText += obj.token;
            assistantBubble.innerHTML = renderMarkdown(fullText);
            scrollToBottom();
          }
          if (obj.error) {
            thinkingEl.remove();
            appendError(obj.error);
            setStreaming(false);
          }
        } catch { }
      }
    }
    setStreaming(false);
  }

  function appendMessage(role, content) {
    const el = document.createElement("div");
    el.className = `message ${role}`;
    el.innerHTML = `
      <div class="message-avatar">${role === "user" ? "Tú" : "AI"}</div>
      <div class="message-body">
        <div class="message-bubble">${role === "assistant" ? renderMarkdown(content) : esc(content)}</div>
      </div>`;
    messagesInner.appendChild(el);
    return el.querySelector(".message-bubble");
  }

  function appendThinking() {
    const el = document.createElement("div");
    el.className = "message assistant";
    el.id = "thinking-msg";
    el.innerHTML = `
      <div class="message-avatar">AI</div>
      <div class="message-body">
        <div class="message-bubble thinking-indicator">
          <span class="thinking-dot"></span><span class="thinking-dot"></span><span class="thinking-dot"></span>
        </div>
      </div>`;
    messagesInner.appendChild(el);
    scrollToBottom();
    return el;
  }

  function appendMessageStreaming() {
    const t = document.getElementById("thinking-msg");
    if (t) t.remove();
    const el = document.createElement("div");
    el.className = "message assistant";
    el.innerHTML = `
      <div class="message-avatar">AI</div>
      <div class="message-body">
        <div class="message-bubble" id="streaming-bubble"></div>
      </div>`;
    messagesInner.appendChild(el);
    return document.getElementById("streaming-bubble");
  }

  function appendError(msg) {
    const el = document.createElement("div");
    el.className = "message assistant";
    el.innerHTML = `
      <div class="message-avatar">!</div>
      <div class="message-body">
        <div class="message-bubble" style="color:#c62828;background:rgba(229,57,53,.08);">${esc(msg)}</div>
      </div>`;
    messagesInner.appendChild(el);
    scrollToBottom();
  }

  function scrollToBottom() {
    messagesArea.scrollTo({ top: messagesArea.scrollHeight, behavior: "smooth" });
  }

  function setStreaming(val) {
    isStreaming = val;
    sendBtn.disabled = val;
    chatTextarea.disabled = val;
  }

  function renderMarkdown(text) {
    let html = esc(text);
    html = html.replace(/```(\w*)\n?([\s\S]*?)```/g, (_, lang, code) =>
      `<pre><code class="lang-${lang || "text"}">${code.trim()}</code></pre>`);
    html = html.replace(/`([^`\n]+)`/g, "<code>$1</code>");
    html = html.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
    html = html.replace(/__(.+?)__/g, "<strong>$1</strong>");
    html = html.replace(/\*(.+?)\*/g, "<em>$1</em>");
    html = html.replace(/_(.+?)_/g, "<em>$1</em>");
    html = html.replace(/^### (.+)$/gm, "<h3>$1</h3>");
    html = html.replace(/^## (.+)$/gm, "<h2>$1</h2>");
    html = html.replace(/^# (.+)$/gm, "<h1>$1</h1>");
    html = html.replace(/^&gt; (.+)$/gm, "<blockquote>$1</blockquote>");
    html = html.replace(/^[*\-] (.+)$/gm, "<li>$1</li>");
    html = html.replace(/(<li>.*<\/li>\n?)+/g, m => `<ul>${m}</ul>`);
    html = html.replace(/^\d+\. (.+)$/gm, "<li>$1</li>");
    html = html.replace(/\n{2,}/g, "</p><p>");
    html = "<p>" + html + "</p>";
    html = html.replace(/([^>])\n([^<])/g, "$1<br>$2");
    html = html.replace(/<p>\s*<\/p>/g, "");
    html = html.replace(/<p>(<(?:pre|ul|ol|h[1-6]|blockquote))/g, "$1");
    html = html.replace(/(<\/(?:pre|ul|ol|h[1-6]|blockquote)>)<\/p>/g, "$1");
    return html;
  }

  function esc(str) {
    return String(str).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;").replace(/'/g,"&#39;");
  }

  function setupTextarea() {
    chatTextarea.addEventListener("keydown", e => {
      if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendMessage(); }
    });
    chatTextarea.addEventListener("input", resizeTextarea);
    sendBtn.addEventListener("click", sendMessage);
  }

  function resizeTextarea() {
    chatTextarea.style.height = "auto";
    chatTextarea.style.height = Math.min(chatTextarea.scrollHeight, 200) + "px";
  }

  function setupSidebar() {
    if (sidebarToggle) sidebarToggle.addEventListener("click", () => sidebar.classList.toggle("open"));
    if (sidebarOverlay) sidebarOverlay.addEventListener("click", closeSidebar);
    if (newChatBtn) newChatBtn.addEventListener("click", newChat);
  }

  function closeSidebar() { sidebar.classList.remove("open"); }

  function confirmDelete(id, title) {
    const overlay = document.createElement("div");
    overlay.className = "modal-overlay";
    overlay.innerHTML = `
      <div class="modal">
        <h3>Eliminar conversación</h3>
        <p>¿Seguro que quieres eliminar "<strong>${esc(title)}</strong>"?</p>
        <div class="modal-actions">
          <button class="btn-sm" id="mc">Cancelar</button>
          <button class="btn-sm danger" id="md">Eliminar</button>
        </div>
      </div>`;
    document.body.appendChild(overlay);
    overlay.querySelector("#mc").addEventListener("click", () => overlay.remove());
    overlay.querySelector("#md").addEventListener("click", async () => {
      overlay.remove();
      await fetch(`/api/conversations/${id}`, { method: "DELETE" });
      if (currentConvId === id) { currentConvId = null; showEmptyState(); }
      await loadConversations();
    });
  }

  document.addEventListener("DOMContentLoaded", init);
})();
