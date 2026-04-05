# Frontend-Ollama

Chat web ligero conectado a una API de Ollama remota.  
Stack: Python (Flask) + SQLite + NGINX + HTML/CSS/JS vanilla.

## Instalación rápida

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/alex-milla/Frontend-Ollama/main/install.sh)
```

## Credenciales iniciales

| Usuario | Contraseña | Nota |
|---------|-----------|------|
| `admin` | `admin` | **Cambio obligatorio en el primer login** |

## Comandos útiles

```bash
systemctl status frontend-ollama
journalctl -u frontend-ollama -f
systemctl restart frontend-ollama
sudo /opt/frontend-ollama/update.sh
```

## Licencia

MIT
