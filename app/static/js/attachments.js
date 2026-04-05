/**
 * attachments.js — Lógica de adjuntos de entrada y exportación de salida.
 * Diseñado para ser incluido después de chat.js.
 *
 * FIXES sesión 4.1:
 *  - El contexto del adjunto se inyecta correctamente en cada mensaje.
 *  - El panel de exportar solo aparece al pulsar el botón "Exportar" de la topbar.
 *  - El upload no pre-crea conversación innecesaria si ya existe una abierta.
 */
(function () {
  "use strict";

  // ── Estado ────────────────────────────────────────────────────────────────────

  let currentAttachment = null;
  // { id, conversation_id, original_name, chunk_unit, chunk_count, is_long,
  //   loaded_from, loaded_to, loaded_text }

  // ── DOM refs ──────────────────────────────────────────────────────────────────

  const fileInput       = document.getElementById("attach-file-input");
  const attachBtn       = document.getElementById("attach-btn");
  const attachPanelWrap = document.getElementById("attach-panel-wrap");
  const messagesArea    = document.getElementById("messages-area");
  const exportPanel     = document.getElementById("export-panel");
  const exportToggleBtn = document.getElementById("btn-export-toggle");

  if (!fileInput || !attachBtn) return;

  // Panel de exportar: siempre oculto al inicio
  if (exportPanel) exportPanel.style.display = "none";

  // ── Botón Exportar en topbar ──────────────────────────────────────────────────

  if (exportToggleBtn) {
    exportToggleBtn.addEventListener("click", () => {
      if (!exportPanel) return;
      const visible = exportPanel.style.display !== "none";
      exportPanel.style.display = visible ? "none" : "block";
      exportToggleBtn.classList.toggle("active", !visible);
      if (!visible) exportPanel.scrollIntoView({ behavior: "smooth", block: "nearest" });
    });
  }

  // ── Botón 📎 ──────────────────────────────────────────────────────────────────

  attachBtn.addEventListener("click", () => fileInput.click());

  fileInput.addEventListener("change", async () => {
    const file = fileInput.files[0];
    if (!file) return;
    fileInput.value = "";
    await uploadFile(file);
  });

  // ── Drag & Drop ───────────────────────────────────────────────────────────────

  messagesArea.addEventListener("dragover", e => {
    e.preventDefault();
    messagesArea.style.outline = "2px dashed var(--accent)";
    messagesArea.style.outlineOffset = "-4px";
  });
  messagesArea.addEventListener("dragleave", () => { messagesArea.style.outline = ""; });
  messagesArea.addEventListener("drop", async e => {
    e.preventDefault();
    messagesArea.style.outline = "";
    const file = e.dataTransfer.files[0];
    if (file) await uploadFile(file);
  });

  // ── Upload ────────────────────────────────────────────────────────────────────

  async function uploadFile(file) {
    clearAttachment();
    showAttachPanel({ original_name: file.name, size_bytes: file.size, loading: true });

    const fd = new FormData();
    fd.append("file", file);

    // Pasar conv_id solo si ya existe una conversación abierta
    const convId = window.getCurrentConvId ? window.getCurrentConvId() : null;
    if (convId) fd.append("conversation_id", String(convId));

    try {
      const res = await fetch("/api/upload", { method: "POST", body: fd });

      if (res.status === 413) {
        const limitMB = 50;
        const fileMB  = (file.size / 1048576).toFixed(1);
        showAttachPanel({
          error: `El archivo pesa ${fileMB} MB y supera el límite de ${limitMB} MB.`,
          original_name: file.name,
          size_bytes: file.size
        });
        return;
      }

      const data = await res.json();
      if (!res.ok) {
        showAttachPanel({ error: data.error || "Error subiendo archivo", original_name: file.name, size_bytes: file.size });
        return;
      }

      // Si el backend creó una conversación nueva, registrarla en chat.js
      if (data.conversation_id && window.setCurrentConvId) {
        window.setCurrentConvId(data.conversation_id);
      }

      currentAttachment = {
        id:              data.attachment_id,
        conversation_id: data.conversation_id,
        original_name:   data.original_name,
        chunk_unit:      data.chunk_unit,
        chunk_count:     data.chunk_count,
        is_long:         data.is_long,
        loaded_from:     null,
        loaded_to:       null,
        loaded_text:     null,
      };

      attachBtn.classList.add("has-file");

      if (!data.is_long) {
        // Archivo corto: cargar todo el contenido automáticamente
        await loadRange(1, data.chunk_count);
      } else {
        showAttachPanel({
          original_name: data.original_name,
          size_bytes:    file.size,
          chunk_count:   data.chunk_count,
          chunk_unit:    data.chunk_unit,
          is_long:       true,
          loaded_from:   null,
          loaded_to:     null,
        });
      }
    } catch {
      showAttachPanel({ error: "Error de red al subir el archivo", original_name: file.name, size_bytes: file.size });
    }
  }

  // ── Cargar rango ──────────────────────────────────────────────────────────────

  async function loadRange(from, to) {
    if (!currentAttachment) return;

    try {
      const res  = await fetch(`/api/attachments/${currentAttachment.id}/range?from=${from}&to=${to}`);
      const data = await res.json();
      if (!res.ok) { console.error("Error cargando rango:", data.error); return; }

      // Guardar texto en el estado — getAttachmentContext() lo leerá desde aquí
      currentAttachment.loaded_from = data.from;
      currentAttachment.loaded_to   = data.to;
      currentAttachment.loaded_text = data.text;

      const wordCount = data.text.split(/\s+/).filter(Boolean).length;

      showAttachPanel({
        original_name: currentAttachment.original_name,
        chunk_count:   currentAttachment.chunk_count,
        chunk_unit:    currentAttachment.chunk_unit,
        is_long:       currentAttachment.is_long,
        loaded_from:   data.from,
        loaded_to:     data.to,
        total:         data.total,
        word_count:    wordCount,
      });
    } catch (err) {
      console.error("Error cargando rango:", err);
    }
  }

  // ── Panel UI ──────────────────────────────────────────────────────────────────

  function showAttachPanel(opts) {
    attachPanelWrap.innerHTML = "";
    attachPanelWrap.style.display = "block";

    const panel     = document.createElement("div");
    panel.className = "attach-panel";

    const sizeStr   = opts.size_bytes ? formatBytes(opts.size_bytes) : "";
    const unitLabel = unitName(opts.chunk_unit);

    // Header
    const header = document.createElement("div");
    header.className = "attach-panel-header";
    header.innerHTML = `
      <span class="attach-icon">📄</span>
      <span style="flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;" title="${esc(opts.original_name || "")}">${esc(opts.original_name || "")}</span>
      ${sizeStr ? `<span class="attach-panel-meta">${sizeStr}</span>` : ""}
      <button class="attach-close-btn" id="attach-close-btn" title="Quitar adjunto">✕</button>
    `;
    panel.appendChild(header);

    if (opts.loading) {
      const st = document.createElement("div");
      st.className = "attach-status warning";
      st.innerHTML = `<span>⏳</span> Procesando archivo…`;
      panel.appendChild(st);

    } else if (opts.error) {
      const st = document.createElement("div");
      st.className = "attach-status warning";
      st.innerHTML = `<span>⚠</span> ${esc(opts.error)}`;
      panel.appendChild(st);

    } else if (!opts.is_long && opts.loaded_from !== null) {
      // Archivo corto cargado — listo para enviar
      const st = document.createElement("div");
      st.className = "attach-status ok";
      st.innerHTML = `<span>✓</span> Contenido cargado (${(opts.word_count || 0).toLocaleString()} palabras) · Se incluirá en tu próximo mensaje`;
      panel.appendChild(st);

    } else if (opts.is_long) {
      // Selector de rango para archivo largo
      const warn = document.createElement("div");
      warn.className = "attach-status warning";
      warn.innerHTML = `<span>⚠</span> Archivo extenso · ${opts.chunk_count} ${unitLabel}s en total. Selecciona el rango a analizar:`;
      panel.appendChild(warn);

      const rangeWrap = document.createElement("div");
      rangeWrap.className = "attach-range";
      const defaultTo = Math.min(10, opts.chunk_count);
      rangeWrap.innerHTML = `
        <div class="attach-range-row">
          <span class="attach-range-label">${capitalize(unitLabel)}s desde</span>
          <input class="attach-range-input" id="range-from" type="number" min="1" max="${opts.chunk_count}" value="${opts.loaded_from || 1}">
          <span class="attach-range-label">hasta</span>
          <input class="attach-range-input" id="range-to" type="number" min="1" max="${opts.chunk_count}" value="${opts.loaded_to || defaultTo}">
          <button class="attach-range-btn" id="range-load-btn">Cargar rango</button>
        </div>
      `;

      if (opts.loaded_from !== null) {
        const loaded = document.createElement("div");
        loaded.className = "attach-loaded-info";
        loaded.innerHTML = `✓ ${capitalize(unitLabel)}s ${opts.loaded_from}–${opts.loaded_to} cargados (${(opts.word_count || 0).toLocaleString()} palabras) · Se incluirán en tu próximo mensaje`;
        rangeWrap.appendChild(loaded);

        if (opts.loaded_to < opts.total) {
          const nextFrom = opts.loaded_to + 1;
          const nextTo   = Math.min(opts.loaded_to + 10, opts.total);
          const continueBtn = document.createElement("button");
          continueBtn.className = "attach-range-btn secondary";
          continueBtn.textContent = `→ Continuar con ${unitLabel}s ${nextFrom}–${nextTo}`;
          continueBtn.addEventListener("click", () => {
            document.getElementById("range-from").value = nextFrom;
            document.getElementById("range-to").value   = nextTo;
          });
          rangeWrap.appendChild(continueBtn);
        }
      }

      panel.appendChild(rangeWrap);

      setTimeout(() => {
        const btn = document.getElementById("range-load-btn");
        if (btn) {
          btn.addEventListener("click", async () => {
            const from = parseInt(document.getElementById("range-from").value, 10);
            const to   = parseInt(document.getElementById("range-to").value, 10);
            if (isNaN(from) || isNaN(to) || from < 1 || to < from) return;
            await loadRange(from, Math.min(to, currentAttachment.chunk_count));
          });
        }
      }, 0);
    }

    attachPanelWrap.appendChild(panel);

    setTimeout(() => {
      const closeBtn = document.getElementById("attach-close-btn");
      if (closeBtn) closeBtn.addEventListener("click", clearAttachment);
    }, 0);
  }

  function clearAttachment() {
    if (currentAttachment) {
      fetch(`/api/attachments/${currentAttachment.id}`, { method: "DELETE" }).catch(() => {});
    }
    currentAttachment = null;
    attachPanelWrap.innerHTML = "";
    attachPanelWrap.style.display = "none";
    attachBtn.classList.remove("has-file");
  }

  // ── API pública para chat.js ──────────────────────────────────────────────────

  /**
   * Devuelve el texto del adjunto para concatenar al mensaje del usuario,
   * o null si no hay adjunto con texto cargado.
   */
  window.getAttachmentContext = function () {
    if (!currentAttachment || !currentAttachment.loaded_text) return null;
    const unit = unitName(currentAttachment.chunk_unit);
    const rangeDesc = currentAttachment.is_long
      ? ` (${unit}s ${currentAttachment.loaded_from}–${currentAttachment.loaded_to} de ${currentAttachment.chunk_count})`
      : "";
    return `\n\n---\n[Archivo adjunto: ${currentAttachment.original_name}${rangeDesc}]\n\n${currentAttachment.loaded_text}\n---\n`;
  };

  /**
   * Llamado por chat.js tras un envío exitoso.
   * Archivos cortos: limpia el panel (texto ya enviado).
   * Archivos largos: mantiene el panel para cargar el siguiente rango.
   */
  window.clearAttachmentAfterSend = function () {
    if (!currentAttachment) return;
    if (currentAttachment.is_long) return; // mantener para siguiente rango
    attachPanelWrap.innerHTML = "";
    attachPanelWrap.style.display = "none";
    attachBtn.classList.remove("has-file");
    currentAttachment = null;
  };

  // ── Panel de exportar ─────────────────────────────────────────────────────────

  function initExportPanel() {
    const formatSel   = document.getElementById("export-format");
    const templateSel = document.getElementById("export-template");
    const filenameInp = document.getElementById("export-filename");
    const dlBtn       = document.getElementById("export-download-btn");
    const saveBtn     = document.getElementById("export-save-btn");
    const resultEl    = document.getElementById("export-result");

    if (!formatSel) return;

    const TEMPLATE_OPTIONS = {
      txt:  ["libre"],
      md:   ["libre"],
      csv:  ["libre"],
      docx: ["libre", "informe", "carta", "legal", "email", "resumen"],
      pdf:  ["libre", "informe", "carta", "legal", "email", "resumen"],
    };
    const TEMPLATE_LABELS = {
      libre: "Texto libre", informe: "Informe", carta: "Carta",
      legal: "Escrito legal", email: "Email", resumen: "Resumen ejecutivo",
    };

    formatSel.addEventListener("change", () => {
      const opts = TEMPLATE_OPTIONS[formatSel.value] || ["libre"];
      templateSel.innerHTML = opts.map(t => `<option value="${t}">${TEMPLATE_LABELS[t] || t}</option>`).join("");
    });

    async function doExport(saveToProject) {
      const text = collectConversationText();
      if (!text) { showResult("No hay respuestas del asistente para exportar.", false); return; }

      const fmt      = formatSel.value;
      const template = templateSel.value;
      const filename = (filenameInp.value.trim() || "documento").replace(/[^\w\-\.]/g, "_");
      const body     = { text, format: fmt, template, filename };

      if (saveToProject) {
        const pid = window.getCurrentProjectId ? window.getCurrentProjectId() : null;
        if (!pid) { showResult("No hay proyecto activo.", false); return; }
        body.project_id = pid;
        const cid = window.getCurrentConvId ? window.getCurrentConvId() : null;
        if (cid) body.conversation_id = cid;
      }

      [dlBtn, saveBtn].forEach(b => b && (b.disabled = true));
      showResult("Generando…", null);

      try {
        const res = await fetch("/api/export", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        });
        if (!res.ok) {
          const err = await res.json();
          showResult(err.error || "Error generando archivo.", false);
          return;
        }
        if (saveToProject) {
          showResult(`✓ Guardado en el proyecto. <a href="/projects/" style="color:var(--accent)">Ver en Proyectos</a>`, true);
        } else {
          const blob = await res.blob();
          const url  = URL.createObjectURL(blob);
          const a    = Object.assign(document.createElement("a"), { href: url, download: filename + "." + fmt });
          document.body.appendChild(a);
          a.click();
          setTimeout(() => { URL.revokeObjectURL(url); a.remove(); }, 1000);
          showResult("✓ Descarga iniciada.", true);
        }
      } catch { showResult("Error de red.", false); }
      finally { [dlBtn, saveBtn].forEach(b => b && (b.disabled = false)); }
    }

    function showResult(msg, ok) {
      if (!resultEl) return;
      resultEl.innerHTML = msg;
      resultEl.className = "export-result" + (ok === true ? " ok" : ok === false ? " err" : "");
      resultEl.style.display = "block";
    }

    if (dlBtn)   dlBtn.addEventListener("click", () => doExport(false));
    if (saveBtn) saveBtn.addEventListener("click", () => doExport(true));
  }

  function collectConversationText() {
    const msgInner = document.getElementById("messages-inner");
    if (!msgInner) return "";
    return [...msgInner.querySelectorAll(".message.assistant .message-bubble")]
      .map(b => b.innerText || b.textContent || "")
      .filter(Boolean)
      .join("\n\n");
  }

  // ── Helpers ───────────────────────────────────────────────────────────────────

  function formatBytes(b) {
    if (b < 1024) return b + " B";
    if (b < 1048576) return (b / 1024).toFixed(1) + " KB";
    return (b / 1048576).toFixed(1) + " MB";
  }
  function unitName(u) { return { page: "página", block: "bloque", row: "fila" }[u] || (u || "bloque"); }
  function capitalize(s) { return s ? s[0].toUpperCase() + s.slice(1) : s; }
  function esc(str) {
    return String(str).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;").replace(/'/g,"&#39;");
  }

  // ── Init ──────────────────────────────────────────────────────────────────────

  document.addEventListener("DOMContentLoaded", initExportPanel);
  if (document.readyState !== "loading") initExportPanel();

})();
