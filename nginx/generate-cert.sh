#!/usr/bin/env bash
# Genera un certificado autofirmado válido 10 años para uso LAN/interno.
set -euo pipefail

CERT_DIR="/etc/ssl/frontend-ollama"
SUBJECT_CN="${1:-frontend-ollama}"

echo "[cert] Creando directorio $CERT_DIR"
mkdir -p "$CERT_DIR"
chmod 700 "$CERT_DIR"

echo "[cert] Generando clave privada RSA 4096…"
openssl genrsa -out "$CERT_DIR/key.pem" 4096 2>/dev/null

echo "[cert] Generando certificado autofirmado (CN=$SUBJECT_CN, 10 años)…"
openssl req -new -x509 \
  -key "$CERT_DIR/key.pem" \
  -out "$CERT_DIR/cert.pem" \
  -days 3650 \
  -subj "/CN=$SUBJECT_CN/O=Frontend-Ollama/C=ES" \
  -addext "subjectAltName=IP:127.0.0.1,DNS:localhost,DNS:$SUBJECT_CN" \
  2>/dev/null

chmod 600 "$CERT_DIR/key.pem"
chmod 644 "$CERT_DIR/cert.pem"

echo "[cert] ✓ Certificado generado en $CERT_DIR"
echo "       Fingerprint SHA-256:"
openssl x509 -noout -fingerprint -sha256 -in "$CERT_DIR/cert.pem" | sed 's/^/       /'
