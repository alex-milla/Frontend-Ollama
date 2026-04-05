#!/usr/bin/env bash
# Frontend-Ollama — Sesión 5: aplicar patch a chat.js en servidor
set -euo pipefail

CHAT_JS="/opt/frontend-ollama/app/static/js/chat.js"

if [[ ! -f "$CHAT_JS" ]]; then
  echo "✗ No se encuentra $CHAT_JS"
  exit 1
fi

python3 - << 'EOF'
import sys

path = "/opt/frontend-ollama/app/static/js/chat.js"
with open(path) as f:
    content = f.read()

changes = 0

# 1. sendMessage: capturar attachmentId y pasarlo a doStream
old1 = """    const attachCtx = window.getAttachmentContext ? window.getAttachmentContext() : null;
    if (attachCtx) content = content + attachCtx;

    const displayContent = chatTextarea.value.trim();
    chatTextarea.value = "";
    resizeTextarea();

    document.getElementById("status-wrap")?.remove();
    if (window.clearAttachmentAfterSend) window.clearAttachmentAfterSend();

    messagesInner.querySelector(".empty-state")?.remove();
    appendMessage("user", displayContent);
    scrollToBottom();

    await doStream(content);"""

new1 = """    const attachCtx = window.getAttachmentContext ? window.getAttachmentContext() : null;
    if (attachCtx) content = content + attachCtx;
    const attachmentId = window.getAttachmentId ? window.getAttachmentId() : null;

    const displayContent = chatTextarea.value.trim();
    chatTextarea.value = "";
    resizeTextarea();

    document.getElementById("status-wrap")?.remove();
    if (window.clearAttachmentAfterSend) window.clearAttachmentAfterSend();

    messagesInner.querySelector(".empty-state")?.remove();
    appendMessage("user", displayContent);
    scrollToBottom();

    await doStream(content, attachmentId);"""

if old1 in content:
    content = content.replace(old1, new1)
    changes += 1
    print("✓ Patch 1 aplicado: sendMessage captura attachmentId")
else:
    print("⚠ Patch 1: bloque no encontrado (¿ya aplicado?)")

# 2. doStream: aceptar attachmentId e incluirlo en el body
old2 = """  async function doStream(content) {
    const model = modelSelect.value;
    if (!model) return;

    setStreaming(true);
    abortController = new AbortController();

    const thinkingEl = appendThinking();
    scrollToBottom();

    const body = { message: content, model, skill_ids: activeSkillIds };
    if (currentConvId)  body.conversation_id = currentConvId;
    if (currentProject) body.project_id = currentProject.id;"""

new2 = """  async function doStream(content, attachmentId) {
    const model = modelSelect.value;
    if (!model) return;

    setStreaming(true);
    abortController = new AbortController();

    const thinkingEl = appendThinking();
    scrollToBottom();

    const body = { message: content, model, skill_ids: activeSkillIds };
    if (currentConvId)  body.conversation_id = currentConvId;
    if (currentProject) body.project_id = currentProject.id;
    if (attachmentId)   body.attachment_id = attachmentId;"""

if old2 in content:
    content = content.replace(old2, new2)
    changes += 1
    print("✓ Patch 2 aplicado: doStream acepta attachmentId")
else:
    print("⚠ Patch 2: bloque no encontrado (¿ya aplicado?)")

# 3. continueResponse: pasar null como attachmentId
old3 = '    await doStream("Continúa exactamente donde te quedaste, sin repetir lo ya escrito.");'
new3 = '    await doStream("Continúa exactamente donde te quedaste, sin repetir lo ya escrito.", null);'

if old3 in content:
    content = content.replace(old3, new3)
    changes += 1
    print("✓ Patch 3 aplicado: continueResponse pasa null")
else:
    print("⚠ Patch 3: bloque no encontrado (¿ya aplicado?)")

with open(path, "w") as f:
    f.write(content)

print(f"\n{'✓ ' + str(changes) + ' patches aplicados correctamente' if changes > 0 else '⚠ Sin cambios — revisa manualmente'}")
EOF

systemctl restart frontend-ollama
echo "✓ Servicio reiniciado"
