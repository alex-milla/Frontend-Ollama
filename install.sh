#!/usr/bin/env bash
# ╔══════════════════════════════════════════════════════════════════╗
# ║  Frontend-Ollama — Instalador                                    ║
# ║  Uso: bash <(curl -fsSL https://raw.githubusercontent.com/      ║
# ║         alex-milla/Frontend-Ollama/main/install.sh)              ║
# ╚══════════════════════════════════════════════════════════════════╝
set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; NC='\033[0m'

log()  { echo -e "${GREEN}[✓]${NC} $*"; }
info() { echo -e "${CYAN}[·]${NC} $*"; }
warn() { echo -e "${YELLOW}[!]${NC} $*"; }
die()  { echo -e "${RED}[✗]${NC} $*" >&2; exit 1; }

[[ "$(id -u)" -eq 0 ]] || die "Ejecuta este script como root (sudo bash install.sh)"

if ! grep -qiE "ubuntu" /etc/os-release 2>/dev/null; then
    warn "Sistema no detectado como Ubuntu. Continúa bajo tu responsabilidad."
fi

echo -e "\n${BOLD}═══════════════════════════════════════${NC}"
echo -e "${BOLD}  Frontend-Ollama — Instalación${NC}"
echo -e "${BOLD}═══════════════════════════════════════${NC}\n"

INSTALL_DIR="/opt/frontend-ollama"
SERVICE_USER="frontollama"
REPO_URL="https://github.com/alex-milla/Frontend-Ollama"
LOG_DIR="/var/log/frontend-ollama"

read -rp "$(echo -e "${CYAN}[?]${NC} URL de la API de Ollama [http://192.168.1.100:11434]: ")" OLLAMA_HOST
OLLAMA_HOST="${OLLAMA_HOST:-http://192.168.1.100:11434}"

read -rp "$(echo -e "${CYAN}[?]${NC} Puerto HTTPS [443]: ")" HTTPS_PORT
HTTPS_PORT="${HTTPS_PORT:-443}"

SERVER_IP=$(hostname -I | awk '{print $1}')
read -rp "$(echo -e "${CYAN}[?]${NC} IP o dominio para el certificado SSL [$SERVER_IP]: ")" CERT_CN
CERT_CN="${CERT_CN:-$SERVER_IP}"

echo ""
info "Instalando en: $INSTALL_DIR"
info "Ollama host:   $OLLAMA_HOST"
info "Puerto HTTPS:  $HTTPS_PORT"
info "Cert CN:       $CERT_CN"
echo ""

# ── 1. Dependencias ────────────────────────────────────────────────────────────
info "Instalando dependencias del sistema…"
apt-get update -qq
apt-get install -y -qq python3 python3-pip python3-venv nginx openssl git curl 2>/dev/null
log "Dependencias instaladas"

# ── 2. Usuario ─────────────────────────────────────────────────────────────────
if ! id "$SERVICE_USER" &>/dev/null; then
    info "Creando usuario de sistema '$SERVICE_USER'…"
    useradd --system --no-create-home --shell /usr/sbin/nologin \
        --comment "Frontend-Ollama service user" "$SERVICE_USER"
    log "Usuario '$SERVICE_USER' creado"
else
    log "Usuario '$SERVICE_USER' ya existe"
fi

# ── 3. Repositorio ─────────────────────────────────────────────────────────────
if [[ -d "$INSTALL_DIR/.git" ]]; then
    info "Actualizando repositorio existente…"
    git -C "$INSTALL_DIR" pull --quiet
else
    info "Clonando repositorio…"
    git clone --quiet "$REPO_URL" "$INSTALL_DIR"
fi
log "Repositorio listo en $INSTALL_DIR"

# ── 4. Virtualenv ──────────────────────────────────────────────────────────────
info "Creando virtualenv y instalando dependencias Python…"
python3 -m venv "$INSTALL_DIR/venv"
"$INSTALL_DIR/venv/bin/pip" install --quiet --upgrade pip
"$INSTALL_DIR/venv/bin/pip" install --quiet -r "$INSTALL_DIR/requirements.txt"
log "Virtualenv listo"

# ── 5. Directorios ─────────────────────────────────────────────────────────────
info "Creando directorios de datos y logs…"
mkdir -p "$INSTALL_DIR/data/uploads"
mkdir -p "$LOG_DIR"
log "Directorios creados"

# ── 6. config.env ─────────────────────────────────────────────────────────────
if [[ ! -f "$INSTALL_DIR/config.env" ]]; then
    info "Generando config.env…"
    SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")
    cat > "$INSTALL_DIR/config.env" <<EOF
# Generado automáticamente por install.sh — $(date -u +%Y-%m-%dT%H:%M:%SZ)
OLLAMA_HOST=${OLLAMA_HOST}
SECRET_KEY=${SECRET_KEY}
DB_PATH=${INSTALL_DIR}/data/ollama-chat.db
UPLOAD_FOLDER=${INSTALL_DIR}/data/uploads
MAX_CONTENT_LENGTH=10485760
EOF
    log "config.env generado"
else
    warn "config.env ya existe, no se sobreescribe"
fi

# ── 7. Certificado SSL ─────────────────────────────────────────────────────────
if [[ ! -f "/etc/ssl/frontend-ollama/cert.pem" ]]; then
    info "Generando certificado autofirmado para '$CERT_CN'…"
    bash "$INSTALL_DIR/nginx/generate-cert.sh" "$CERT_CN"
    log "Certificado generado"
else
    log "Certificado ya existe, no se regenera"
fi

# ── 8. NGINX ───────────────────────────────────────────────────────────────────
info "Configurando NGINX…"
NGINX_CONF="$INSTALL_DIR/nginx/frontend-ollama.conf"
if [[ "$HTTPS_PORT" != "443" ]]; then
    sed -i "s/listen 443 ssl/listen $HTTPS_PORT ssl/" "$NGINX_CONF"
    sed -i "s/listen \[::\]:443 ssl/listen [::]:$HTTPS_PORT ssl/" "$NGINX_CONF"
fi
cp "$NGINX_CONF" /etc/nginx/sites-available/frontend-ollama
ln -sf /etc/nginx/sites-available/frontend-ollama /etc/nginx/sites-enabled/frontend-ollama
rm -f /etc/nginx/sites-enabled/default
nginx -t || die "La configuración de NGINX tiene errores"
log "NGINX configurado"

# ── 9. Permisos ────────────────────────────────────────────────────────────────
info "Aplicando permisos…"

# app/ — legible por todos (gunicorn necesita importar los módulos como frontollama)
chown -R root:root "$INSTALL_DIR/app"
find "$INSTALL_DIR/app" -type d -exec chmod 755 {} \;
find "$INSTALL_DIR/app" -type f -exec chmod 644 {} \;

# data/ — frontollama propietario; 711 para que nginx pueda traversar hasta el socket
chown -R "$SERVICE_USER":"$SERVICE_USER" "$INSTALL_DIR/data"
chmod 711 "$INSTALL_DIR/data"

# config.env
chown root:"$SERVICE_USER" "$INSTALL_DIR/config.env"
chmod 640 "$INSTALL_DIR/config.env"

# venv — 755 para que systemd pueda ejecutar gunicorn sin importar el grupo activo
chown -R root:root "$INSTALL_DIR/venv"
chmod -R 755 "$INSTALL_DIR/venv"

# update.sh
chown root:root "$INSTALL_DIR/update.sh" 2>/dev/null || true
chmod 700 "$INSTALL_DIR/update.sh" 2>/dev/null || true

# Logs
chown root:"$SERVICE_USER" "$LOG_DIR"
chmod 775 "$LOG_DIR"

log "Permisos aplicados"

# ── 10. Systemd ────────────────────────────────────────────────────────────────
info "Instalando servicio systemd…"
cp "$INSTALL_DIR/systemd/frontend-ollama.service" /etc/systemd/system/
systemctl daemon-reload
systemctl enable --quiet frontend-ollama
log "Servicio systemd instalado y habilitado"

# ── 11. Base de datos ──────────────────────────────────────────────────────────
info "Inicializando base de datos…"
sudo -u "$SERVICE_USER" bash -c "
    cd '$INSTALL_DIR' && \
    '$INSTALL_DIR/venv/bin/python3' -c \
        'from app.database import init_db; from app.config import Config; init_db(Config.DB_PATH)'
"
chown "$SERVICE_USER":"$SERVICE_USER" "$INSTALL_DIR/data/ollama-chat.db" 2>/dev/null || true
chmod 600 "$INSTALL_DIR/data/ollama-chat.db" 2>/dev/null || true
log "Base de datos inicializada"

# ── 12. Arrancar servicios ─────────────────────────────────────────────────────
info "Arrancando servicios…"
systemctl restart frontend-ollama
systemctl restart nginx
log "Servicios arrancados"

# ── 13. Health check ───────────────────────────────────────────────────────────
info "Comprobando que el servicio responde…"
sleep 3
for i in {1..10}; do
    if curl -kfs "https://127.0.0.1:${HTTPS_PORT}/login" -o /dev/null; then
        log "Health check OK ✓"
        break
    fi
    if [[ $i -eq 10 ]]; then
        warn "Health check falló. Revisa: journalctl -u frontend-ollama -n 50"
    fi
    sleep 2
done

echo ""
echo -e "${BOLD}═══════════════════════════════════════${NC}"
echo -e "${BOLD}  ✓ Instalación completada${NC}"
echo -e "${BOLD}═══════════════════════════════════════${NC}"
echo ""
echo -e "  ${CYAN}URL:${NC}            https://${SERVER_IP}:${HTTPS_PORT}"
echo -e "  ${CYAN}Usuario:${NC}        admin"
echo -e "  ${CYAN}Contraseña:${NC}     admin  ${YELLOW}(cambio obligatorio en el primer login)${NC}"
echo ""
echo -e "  ${CYAN}Logs del servicio:${NC}  journalctl -u frontend-ollama -f"
echo -e "  ${CYAN}Logs de acceso:${NC}     tail -f ${LOG_DIR}/access.log"
echo ""
