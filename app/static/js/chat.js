/**
 * chat.js — Lógica del chat: SSE streaming, historial, markdown básico.
 */
(function () {
  "use strict";

  // ── Estado ──────────────────────────────────────────────────────────────────
  let currentConvId   = null;
  let isStreaming     = false;
  let currentEventSrc = null;

  // ── Elementos DOM ────────────────────────────────────────────────────────────
  const messagesArea   = document.getElementById("messages-area");
  const messagesInner  = document.getElementById("messages-inner");
  const chatTextarea   = document.getElementById("chat-textarea");
  const sendBtn        = document.getElementById("send-btn");
  const modelSelect    = document.getElementById("model-select");
  const statusDot      = document.getElementById("status-dot");
  const statusText     = document.getElementById("status-text");
  const convList       = document.getElementById("conv-list");
  const newChatBtn     = document.getElementById("btn-new-chat");
  const sidebarToggle  = document.getElementById("btn-sidebar-toggle");
  const sidebar        = document.getElementById("sidebar");
  const sidebarOverlay = document.getElementById("sidebar-overlay");
  const currentConvTitle = document.getElementById("current-conv-title");

  // ── Init ─────────────────────────────────────────────────────────────────────
  async function init() {
    await loadModels();
    await checkOllamaStatus();
    await loadConversations();
    setupTextarea();
    setupSidebar();
  }

  // ── Modelos ──────────────────────────────────────────────────────────────────
  async function loadModels() {
    try {
      const res  = await fetch("/api/models");
      const data = await res.json();
      modelSelect.innerHTML = "";
      if (!data.models || data.models.length === 0) {
        const opt = document.createElement("option");
        opt.value = "";
        opt.textContent = "Sin modelos disponibles";
        modelSelect.appendChild(opt);
        return;
      }
      data.models.forEach((m) => {
        const opt = document.createElement("option");
        opt.value = m;
        opt.textContent = m;
        modelSelect.appendChild(opt);
      });
    } catch {
      modelSelect.innerHTML = '<option value="">Error cargando modelos</option>';
    }
  }

  // ── Estado de Ollama ─────────────────────────────────────────────────────────
  async function checkOllamaStatus() {
    try {
      const res  = await fetch("/api/ollama/status");
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

  // ── Conversaciones ────────────────────────────────────────────────────────────
  async function loadConversations() {
    try {
      const res   = await fetch("/api/conversations");
      const convs = await res.json();
      renderConvList(convs);
    } catch { /* silencioso */ }
  }

  function renderConvList(convs) {
    convList.innerHTML = "";
    if (convs.length === 0) {
      convList.innerHTML = '<p style="font-size:.78rem;color:var(--text-sidebar-muted);padding:8px 10px">Sin conversaciones aún</p>';
      return;
    }
    convs.forEach((c) => convList.appendChild(buildConvItem(c)));
  }

  function buildConvItem(c) {
    const el = document.createElement("div");
    el.className = "conv-item" + (c.id === currentConvId ? " active" : "");
    el.dataset.id = c.id;
    el.innerHTML = `
      <span class="conv-title" title="${esc(c.title)}">${esc(c.title)}</span>
      <span class="conv-actions">
        <button class="conv-btn" data-action="export" title="Exportar XML">⬇</button>
        <button class="conv-btn" data-action="delete" title="Eliminar">✕</button>
      </span>`;

    el.addEventListener("click", (e) => {
      if (e.target.closest("[data-action]")) return;
      loadConversation(c.id, c.title);
    });

    el.querySelector("[data-action='delete']").addEventListener("click", (e) => {
      e.stopPropagation();
      confirmDelete(c.id, c.title);
    });

    el.querySelector("[data-action='export']").addEventListener("click", (e) => {
      e.stopPropagation();
      window.location.href = `/api/conversations/${c.id}/export`;
    });

    return el;
  }

  function setActiveConv(id) {
    document.querySelectorAll(".conv-item").forEach((el) => {
      el.classList.toggle("active", Number(el.dataset.id) === id);
    });
  }

  async function loadConversation(id, title) {
    if (isStreaming) return;
    closeSidebar();
    currentConvId = id;
    setActiveConv(id);
    if (currentConvTitle) currentConvTitle.textContent = title || "Conversación";

    // Skeleton
    messagesInner.innerHTML = `
      <div class="message assistant">
        <div class="message-avatar">AI</div>
        <div class="message-body" style="flex:1">
          <div class="message-bubble">
            <div class="skeleton-line" style="width:80%"></div>
            <div class="skeleton-line" style="width:60%;margin-top:6px"></div>
            <div class="skeleton-line" style="width:70%;margin-top:6px"></div>
          </div>
        </div>
      </div>`;

    try {
      const res  = await fetch(`/api/conversations/${id}`);
      const data = await res.json();
      renderMessages(data.messages || []);
      if (data.conversation) {
        if (currentConvTitle) currentConvTitle.textContent = data.conversation.title;
        // Selecciona el modelo si está disponible
        if (data.conversation.model) {
          const opt = modelSelect.querySelector(`option[value="${CSS.escape(data.conversation.model)}"]`);
          if (opt) modelSelect.value = data.conversation.model;
        }
      }
    } catch {
      messagesInner.innerHTML = '<p style="color:var(--text-secondary);text-align:center;padding:32px">Error cargando conversación.</p>';
    }
  }

  function renderMessages(msgs) {
    if (msgs.length === 0) {
      showEmptyState();
      return;
    }
    messagesInner.innerHTML = "";
    msgs.forEach((m) => appendMessage(m.role, m.content));
    scrollToBottom();
  }

  function showEmptyState() {
    messagesInner.innerHTML = `
      <div class="empty-state">
        <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
          <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
        </svg>
        <h2>¿En qué puedo ayudarte?</h2>
        <p>Selecciona un modelo y empieza a escribir.</p>
      </div>`;
  }

  // ── Nueva conversación ────────────────────────────────────────────────────────
  function newChat() {
    if (isStreaming) return;
    currentConvId = null;
    document.querySelectorAll(".conv-item").forEach((el) => el.classList.remove("active"));
    if (currentConvTitle) currentConvTitle.textContent = "Nueva conversación";
    showEmptyState();
    closeSidebar();
    chatTextarea.focus();
  }

  // ── Envío de mensajes ─────────────────────────────────────────────────────────
  async function sendMessage() {
    const content = chatTextarea.value.trim();
    const model   = modelSelect.value;
    if (!content || !model || isStreaming) return;

    // Oculta empty state si existe
    const emptyState = messagesInner.querySelector(".empty-state");
    if (emptyState) emptyState.remove();

    chatTextarea.value = "";
    resizeTextarea();
    setStreaming(true);

    appendMessage("user", content);
    const thinkingEl = appendThinking();
    scrollToBottom();

    const body = { message: content, model };
    if (currentConvId) body.conversation_id = currentConvId;

    let assistantBubble = null;
    let fullText = "";

    try {
      const evtSrc = new EventSource("/api/chat?" + new URLSearchParams({
        // Usamos fetch+ReadableStream porque EventSource no soporta POST
        // Truco: hacemos un fetch y simulamos SSE manualmente
      }));
      evtSrc.close(); // cerramos el EventSource vacío
    } catch { /* ok */ }

    // Usamos fetch + ReadableStream para POST con SSE
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

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop(); // la última línea puede estar incompleta

      for (const line of lines) {
        if (!line.startsWith("data: ")) continue;
        const raw = line.slice(6).trim();
        if (raw === "[DONE]") {
          setStreaming(false);
          await loadConversations(); // refresca la lista
          break;
        }
        try {
          const obj = JSON.parse(raw);
          if (obj.conv_id && !currentConvId) {
            currentConvId = obj.conv_id;
            setActiveConv(currentConvId);
          }
          if (obj.token) {
            thinkingEl.remove(); // elimina "pensando" en el primer token
            if (!assistantBubble) {
              assistantBubble = appendMessageStreaming();
            }
            fullText += obj.token;
            assistantBubble.innerHTML = renderMarkdown(fullText);
            scrollToBottom();
          }
          if (obj.error) {
            thinkingEl.remove();
            appendError(obj.error);
            setStreaming(false);
          }
        } catch { /* JSON incompleto, continúa */ }
      }
    }
    setStreaming(false);
  }

  // ── DOM helpers ───────────────────────────────────────────────────────────────

  function appendMessage(role, content) {
    const el = document.createElement("div");
    el.className = `message ${role}`;
    const avatarLabel = role === "user" ? "Tú" : "AI";
    el.innerHTML = `
      <div class="message-avatar">${avatarLabel}</div>
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
          <span class="thinking-dot"></span>
          <span class="thinking-dot"></span>
          <span class="thinking-dot"></span>
        </div>
      </div>`;
    messagesInner.appendChild(el);
    scrollToBottom();
    return el;
  }

  function appendMessageStreaming() {
    // Elimina el "pensando" si aún existe
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

  // ── Markdown básico ───────────────────────────────────────────────────────────
  function renderMarkdown(text) {
    let html = esc(text);

    // Code blocks (```)
    html = html.replace(/```(\w*)\n?([\s\S]*?)```/g, (_, lang, code) =>
      `<pre><code class="lang-${lang || 'text'}">${code.trim()}</code></pre>`
    );

    // Inline code
    html = html.replace(/`([^`\n]+)`/g, "<code>$1</code>");

    // Negrita
    html = html.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
    html = html.replace(/__(.+?)__/g, "<strong>$1</strong>");

    // Cursiva
    html = html.replace(/\*(.+?)\*/g, "<em>$1</em>");
    html = html.replace(/_(.+?)_/g, "<em>$1</em>");

    // Headers
    html = html.replace(/^### (.+)$/gm, "<h3>$1</h3>");
    html = html.replace(/^## (.+)$/gm, "<h2>$1</h2>");
    html = html.replace(/^# (.+)$/gm, "<h1>$1</h1>");

    // Blockquote
    html = html.replace(/^&gt; (.+)$/gm, "<blockquote>$1</blockquote>");

    // Listas desordenadas
    html = html.replace(/^[*\-] (.+)$/gm, "<li>$1</li>");
    html = html.replace(/(<li>.*<\/li>\n?)+/g, (m) => `<ul>${m}</ul>`);

    // Listas ordenadas
    html = html.replace(/^\d+\. (.+)$/gm, "<li>$1</li>");

    // Párrafos (doble salto de línea)
    html = html.replace(/\n{2,}/g, "</p><p>");
    html = "<p>" + html + "</p>";

    // Saltos simples dentro de párrafo
    html = html.replace(/([^>])\n([^<])/g, "$1<br>$2");

    // Limpia párrafos vacíos
    html = html.replace(/<p>\s*<\/p>/g, "");
    html = html.replace(/<p>(<(?:pre|ul|ol|h[1-6]|blockquote))/g, "$1");
    html = html.replace(/(<\/(?:pre|ul|ol|h[1-6]|blockquote)>)<\/p>/g, "$1");

    return html;
  }

  // Escape HTML para contenido de usuario (anti-XSS)
  function esc(str) {
    return String(str)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  // ── Textarea autoexpandible ────────────────────────────────────────────────────
  function setupTextarea() {
    chatTextarea.addEventListener("keydown", (e) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
      }
    });
    chatTextarea.addEventListener("input", resizeTextarea);
    sendBtn.addEventListener("click", sendMessage);
  }

  function resizeTextarea() {
    chatTextarea.style.height = "auto";
    chatTextarea.style.height = Math.min(chatTextarea.scrollHeight, 200) + "px";
  }

  // ── Sidebar móvil ─────────────────────────────────────────────────────────────
  function setupSidebar() {
    if (sidebarToggle) sidebarToggle.addEventListener("click", toggleSidebar);
    if (sidebarOverlay) sidebarOverlay.addEventListener("click", closeSidebar);
    if (newChatBtn) newChatBtn.addEventListener("click", newChat);
  }

  function toggleSidebar() {
    sidebar.classList.toggle("open");
  }

  function closeSidebar() {
    sidebar.classList.remove("open");
  }

  // ── Confirmación de borrado ───────────────────────────────────────────────────
  function confirmDelete(id, title) {
    const overlay = document.createElement("div");
    overlay.className = "modal-overlay";
    overlay.innerHTML = `
      <div class="modal">
        <h3>Eliminar conversación</h3>
        <p>¿Seguro que quieres eliminar "<strong>${esc(title)}</strong>"? Esta acción no se puede deshacer.</p>
        <div class="modal-actions">
          <button class="btn-sm" id="modal-cancel">Cancelar</button>
          <button class="btn-sm danger" id="modal-confirm">Eliminar</button>
        </div>
      </div>`;
    document.body.appendChild(overlay);

    overlay.querySelector("#modal-cancel").addEventListener("click", () => overlay.remove());
    overlay.querySelector("#modal-confirm").addEventListener("click", async () => {
      overlay.remove();
      await deleteConversation(id);
    });
  }

  async function deleteConversation(id) {
    try {
      await fetch(`/api/conversations/${id}`, { method: "DELETE" });
      if (currentConvId === id) {
        currentConvId = null;
        showEmptyState();
        if (currentConvTitle) currentConvTitle.textContent = "Nueva conversación";
      }
      await loadConversations();
    } catch { /* silencioso */ }
  }

  // ── Arranque ──────────────────────────────────────────────────────────────────
  document.addEventListener("DOMContentLoaded", init);
})();
