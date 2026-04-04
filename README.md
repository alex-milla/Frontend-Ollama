# Frontend-Ollama

Chat web ligero conectado a una API de Ollama remota.  
Stack: Python (Flask) + SQLite + NGINX + HTML/CSS/JS vanilla.

## Instalación rápida

```bash
# Desde un contenedor LXC Ubuntu 24/25 recién creado:
bash <(curl -fsSL https://raw.githubusercontent.com/alex-milla/Frontend-Ollama/main/install.sh)
```

El instalador preguntará:
1. URL de la API de Ollama (default: `http://192.168.1.100:11434`)
2. Puerto HTTPS (default: `443`)
3. IP/dominio para el certificado autofirmado

Al terminar muestra la URL de acceso y las credenciales iniciales.

## Credenciales iniciales

| Usuario | Contraseña | Nota |
|---------|-----------|------|
| `admin` | `admin` | **Cambio obligatorio en el primer login** |

## Estructura

```
Frontend-Ollama/
├── install.sh          # Instalador principal
├── update.sh           # Actualizador automático
├── config.env.example  # Plantilla de configuración
├── app/                # Aplicación Flask
│   ├── __init__.py     # Factory
│   ├── config.py       # Configuración
│   ├── database.py     # SQLite + schema
│   ├── models.py       # Acceso a datos
│   ├── auth.py         # Blueprint: login/logout/change-password
│   ├── chat.py         # Blueprint: chat SSE + historial + export
│   ├── admin.py        # Blueprint: gestión de usuarios
│   ├── ollama_client.py# Cliente HTTP para Ollama
│   ├── static/
│   │   ├── css/style.css
│   │   └── js/{theme,auth,chat,admin}.js
│   └── templates/
│       ├── base.html
│       ├── login.html
│       ├── chat.html
│       ├── admin.html
│       └── change_password.html
├── nginx/
│   ├── frontend-ollama.conf
│   └── generate-cert.sh
├── systemd/
│   └── frontend-ollama.service
└── data/               # gitignored — BD y uploads
```

## Permisos

| Recurso | Propietario | Modo |
|---------|------------|------|
| `app/` | `root:frontollama` | `750/640` |
| `data/` | `frontollama:frontollama` | `700` |
| `data/ollama-chat.db` | `frontollama:frontollama` | `600` |
| `config.env` | `root:frontollama` | `640` |
| `update.sh` | `root:root` | `700` |
| Certificados SSL | `root:root` | `600` |
| Socket Gunicorn | `frontollama:www-data` | `660` |

## Actualización

```bash
sudo /opt/frontend-ollama/update.sh
```

O desde el panel de administración → *Actualizaciones*.

## Comandos útiles

```bash
# Estado del servicio
systemctl status frontend-ollama

# Logs en tiempo real
journalctl -u frontend-ollama -f

# Reiniciar
systemctl restart frontend-ollama

# Logs de acceso
tail -f /var/log/frontend-ollama/access.log
```

## Licencia

MIT
