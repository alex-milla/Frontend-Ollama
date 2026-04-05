#!/usr/bin/env bash
# ╔══════════════════════════════════════════════════════════════════╗
# ║  Frontend-Ollama — Script de actualización (Fase 5)             ║
# ║  Uso: sudo bash /opt/frontend-ollama/update.sh                  ║
# ╚══════════════════════════════════════════════════════════════════╝
set -euo pipefail

# ── Constantes ────────────────────────────────────────────────────────────────
INSTALL_DIR="/opt/frontend-ollama"
SERVICE_USER="frontollama"
SERVICE_NAME="frontend-ollama"
LOG_FILE="/var/log/frontend-ollama/update.log"
LOCK_FILE="/tmp/frontend-ollama-update.lock"
BACKUP_DIR="/tmp/frontend-ollama-backup-$(date +%Y%m%d-%H%M%S)"
GITHUB_API="https://api.github.com/repos/alex-milla/Frontend-Ollama/releases/latest"
TIMEOUT=300  # 5 minutos máximo

# ── Colores ───────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; NC='\033[0m'

# ── Logging ───────────────────────────────────────────────────────────────────
mkdir -p "$(dirname "$LOG_FILE")"
exec > >(tee -a "$LOG_FILE") 2>&1

ts()   { date -u +"%Y-%m-%dT%H:%M:%SZ"; }
log()  { echo -e "$(ts) ${GREEN}[✓]${NC} $*"; }
info() { echo -e "$(ts) ${CYAN}[·]${NC} $*"; }
warn() { echo -e "$(ts) ${YELLOW}[!]${NC} $*"; }
die()  { echo -e "$(ts) ${RED}[✗]${NC} $*" >&2; cleanup_on_error; exit 1; }

# ── Lock ──────────────────────────────────────────────────────────────────────
[[ "$(id -u)" -eq 0 ]] || die "Ejecuta como root (sudo)"

if [[ -f "$LOCK_FILE" ]]; then
    LOCK_PID=$(cat "$LOCK_FILE" 2>/dev/null || echo "?")
    die "Actualización ya en curso (PID $LOCK_PID). Si no es así, elimina $LOCK_FILE"
fi
echo $$ > "$LOCK_FILE"

cleanup_on_error() {
    rm -f "$LOCK_FILE"
    if [[ -d "$BACKUP_DIR" ]]; then
        warn "Iniciando rollback desde $BACKUP_DIR…"
        do_rollback
    fi
}

trap 'cleanup_on_error' ERR
# Timeout global
( sleep $TIMEOUT; echo "$(ts) [!] Timeout de actualización alcanzado" >> "$LOG_FILE"; kill $$ 2>/dev/null ) &
TIMEOUT_PID=$!

# ── Funciones de actualización ─────────────────────────────────────────────────

read_version() {
    cat "$INSTALL_DIR/VERSION" 2>/dev/null | tr -d '[:space:]' || echo "0.0.0"
}

fetch_latest_release() {
    curl -fsSL --max-time 30 \
        -H "User-Agent: Frontend-Ollama-Updater" \
        "$GITHUB_API"
}

do_rollback() {
    warn "Rollback: restaurando desde backup…"
    if [[ -d "$BACKUP_DIR/app" ]]; then
        cp -a "$BACKUP_DIR/app/." "$INSTALL_DIR/app/"
        log "Código restaurado"
    fi
    systemctl start "$SERVICE_NAME" 2>/dev/null || warn "No se pudo reiniciar el servicio tras rollback"
    warn "Rollback completado. Revisa los logs: $LOG_FILE"
}

detect_change_type() {
    # Devuelve: static | python | nginx | systemd | mixed
    local tarball_dir="$1"
    local has_python=0 has_static=0 has_nginx=0 has_systemd=0

    [[ -n "$(find "$tarball_dir/app" -name "*.py" -newer "$INSTALL_DIR/VERSION" 2>/dev/null)" ]] && has_python=1
    [[ -n "$(find "$tarball_dir/app/static" -type f -newer "$INSTALL_DIR/VERSION" 2>/dev/null)" ]] && has_static=1
    [[ -f "$tarball_dir/nginx/frontend-ollama.conf" ]] && \
        ! diff -q "$tarball_dir/nginx/frontend-ollama.conf" "/etc/nginx/sites-available/frontend-ollama" &>/dev/null && has_nginx=1
    [[ -f "$tarball_dir/systemd/frontend-ollama.service" ]] && \
        ! diff -q "$tarball_dir/systemd/frontend-ollama.service" "/etc/systemd/system/frontend-ollama.service" &>/dev/null && has_systemd=1

    if [[ $has_python -eq 1 || $has_systemd -eq 1 ]]; then echo "python"
    elif [[ $has_nginx -eq 1 ]]; then echo "nginx"
    elif [[ $has_static -eq 1 ]]; then echo "static"
    else echo "none"
    fi
}

health_check() {
    info "Health check…"
    for i in {1..15}; do
        if curl -kfs "https://127.0.0.1/login" -o /dev/null 2>/dev/null; then
            log "Health check OK ✓"
            return 0
        fi
        sleep 2
    done
    die "Health check falló tras 30 segundos"
}

# ── Main ───────────────────────────────────────────────────────────────────────

echo ""
echo "═══════════════════════════════════════════"
echo "  Frontend-Ollama — Actualización"
echo "  $(ts)"
echo "═══════════════════════════════════════════"
echo ""

CURRENT=$(read_version)
info "Versión actual: $CURRENT"

# 1. Consultar GitHub
info "Consultando última release en GitHub…"
RELEASE_JSON=$(fetch_latest_release)
LATEST_TAG=$(echo "$RELEASE_JSON" | python3 -c "import sys,json; print(json.load(sys.stdin).get('tag_name','').lstrip('v'))" 2>/dev/null || echo "")
TARBALL_URL=$(echo "$RELEASE_JSON" | python3 -c "import sys,json; print(json.load(sys.stdin).get('tarball_url',''))" 2>/dev/null || echo "")

if [[ -z "$LATEST_TAG" ]]; then
    die "No se pudo obtener la última versión de GitHub"
fi

info "Última versión disponible: $LATEST_TAG"

# 2. Comparar versiones
if [[ "$CURRENT" == "$LATEST_TAG" ]]; then
    log "Ya estás en la versión más reciente ($CURRENT). Nada que actualizar."
    rm -f "$LOCK_FILE"
    kill $TIMEOUT_PID 2>/dev/null || true
    exit 0
fi

info "Actualizando $CURRENT → $LATEST_TAG"

# 3. Descargar tarball
TMP_DIR=$(mktemp -d)
TARBALL="$TMP_DIR/release.tar.gz"
info "Descargando release…"
curl -fsSL --max-time 120 -o "$TARBALL" "$TARBALL_URL"
log "Descarga completada"

# Extraer
tar -xzf "$TARBALL" -C "$TMP_DIR"
EXTRACT_DIR=$(find "$TMP_DIR" -maxdepth 1 -mindepth 1 -type d | head -1)
[[ -d "$EXTRACT_DIR" ]] || die "No se pudo extraer el tarball"

# 4. Detectar tipo de cambio
CHANGE_TYPE=$(detect_change_type "$EXTRACT_DIR")
info "Tipo de cambio detectado: $CHANGE_TYPE"

# 5. Backup
info "Creando backup en $BACKUP_DIR…"
mkdir -p "$BACKUP_DIR"
cp -a "$INSTALL_DIR/app/." "$BACKUP_DIR/app" 2>/dev/null || true
cp "$INSTALL_DIR/VERSION" "$BACKUP_DIR/VERSION" 2>/dev/null || true
log "Backup creado"

# 6. Parar servicio (si necesario)
if [[ "$CHANGE_TYPE" == "python" || "$CHANGE_TYPE" == "nginx" ]]; then
    info "Parando servicio $SERVICE_NAME…"
    systemctl stop "$SERVICE_NAME" || warn "El servicio ya estaba parado"
fi

# 7. Copiar nuevos archivos (NO sobreescribe data/ ni config.env)
info "Instalando nuevos archivos…"
rsync -a --exclude="data/" --exclude="config.env" --exclude=".git" \
    "$EXTRACT_DIR/" "$INSTALL_DIR/"

# 8. Actualizar dependencias Python
info "Actualizando dependencias Python…"
"$INSTALL_DIR/venv/bin/pip" install --quiet --upgrade pip
"$INSTALL_DIR/venv/bin/pip" install --quiet -r "$INSTALL_DIR/requirements.txt"
log "Dependencias actualizadas"

# 9. Migraciones de BD (por ahora ejecuta init_db que es idempotente)
info "Ejecutando migraciones de base de datos…"
sudo -u "$SERVICE_USER" "$INSTALL_DIR/venv/bin/python3" \
    -c "from app.database import init_db; from app.config import Config; init_db(Config.DB_PATH)"
log "Migraciones completadas"

# 10. Restaurar permisos
info "Restaurando permisos…"
chown -R root:"$SERVICE_USER" "$INSTALL_DIR/app"
find "$INSTALL_DIR/app" -type d -exec chmod 750 {} \;
find "$INSTALL_DIR/app" -type f -exec chmod 640 {} \;
chown -R "$SERVICE_USER":"$SERVICE_USER" "$INSTALL_DIR/data"
chmod 700 "$INSTALL_DIR/data"
chmod 600 "$INSTALL_DIR/data/ollama-chat.db" 2>/dev/null || true
chown root:"$SERVICE_USER" "$INSTALL_DIR/config.env"
chmod 640 "$INSTALL_DIR/config.env"
chown root:root "$INSTALL_DIR/update.sh"
chmod 700 "$INSTALL_DIR/update.sh"
log "Permisos restaurados"

# 11. Reiniciar servicios según tipo de cambio
case "$CHANGE_TYPE" in
    none)
        log "Sin cambios detectados, nada que reiniciar."
        ;;
    static)
        info "Solo estáticos cambiados → nginx reload (sin downtime)…"
        nginx -t && systemctl reload nginx
        log "NGINX recargado"
        ;;
    nginx)
        info "Configuración NGINX cambiada → actualizando y recargando…"
        cp "$EXTRACT_DIR/nginx/frontend-ollama.conf" /etc/nginx/sites-available/frontend-ollama
        nginx -t && systemctl reload nginx
        systemctl start "$SERVICE_NAME"
        log "NGINX recargado y servicio reiniciado"
        ;;
    python|*)
        info "Cambios en Python/systemd → reiniciando servicio…"
        if [[ -f "$EXTRACT_DIR/systemd/frontend-ollama.service" ]]; then
            cp "$EXTRACT_DIR/systemd/frontend-ollama.service" /etc/systemd/system/
            systemctl daemon-reload
        fi
        systemctl start "$SERVICE_NAME"
        log "Servicio reiniciado"
        ;;
esac

# 12. Health check
health_check

# 13. Limpieza
rm -rf "$TMP_DIR"
rm -f "$LOCK_FILE"
kill $TIMEOUT_PID 2>/dev/null || true

echo ""
log "════════════════════════════════════════"
log "  Actualización completada: $CURRENT → $LATEST_TAG"
log "  Backup guardado en: $BACKUP_DIR"
log "  (Elimínalo manualmente si ya no lo necesitas)"
log "════════════════════════════════════════"
echo ""
