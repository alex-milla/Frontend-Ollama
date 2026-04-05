# Frontend-Ollama — Sesión 4: Adjuntos y Exportación

## Archivos nuevos

| Archivo | Descripción |
|---|---|
| `app/file_processor.py` | Extracción de texto y chunking (PDF/DOCX/TXT/CSV/XLSX) |
| `app/file_exporter.py` | Generación de DOCX/PDF/TXT/CSV con plantillas |
| `app/static/css/attachments.css` | Estilos para paneles de adjunto y exportación |
| `app/static/js/attachments.js` | Lógica JS de adjuntos y exportación |

## Archivos modificados

| Archivo | Cambios |
|---|---|
| `requirements.txt` | `pypdf`, `python-docx`, `openpyxl`, `reportlab` |
| `app/config.py` | Nueva variable `OUTPUT_FOLDER` |
| `app/database.py` | Tablas `conversation_attachments` y `project_outputs` + índices |
| `app/models.py` | CRUD para adjuntos y outputs |
| `app/chat.py` | Endpoints `/api/upload`, `/api/attachments/*`, `/api/export`, `/api/outputs/*` |
| `app/projects.py` | Endpoint `/projects/api/projects/{id}/outputs` |
| `app/templates/base.html` | Incluye `attachments.css` |
| `app/templates/chat.html` | Botón 📎, panel adjunto, panel exportar |
| `app/templates/projects.html` | Sección "Archivos generados" |
| `app/static/js/chat.js` | Expone API pública, inyecta contexto del adjunto en mensajes |
| `app/static/js/projects.js` | Carga y gestión de archivos generados |
| `config.env.example` | Variable `OUTPUT_FOLDER` |

## Instalación en servidor existente

```bash
# 1. Ir al directorio de instalación
cd /opt/frontend-ollama

# 2. Copiar todos los archivos del ZIP (sin sobreescribir data/ ni config.env)
# El update.sh existente ya lo hace correctamente

# 3. Instalar dependencias nuevas
venv/bin/pip install pypdf python-docx openpyxl reportlab

# 4. Crear directorio de outputs
mkdir -p data/outputs
chown frontollama:frontollama data/outputs
chmod 700 data/outputs

# 5. Añadir OUTPUT_FOLDER a config.env si no existe
echo "OUTPUT_FOLDER=/opt/frontend-ollama/data/outputs" >> config.env

# 6. Reiniciar servicio (las migraciones de BD se ejecutan al arrancar)
systemctl restart frontend-ollama
```

## Nuevos endpoints API

```
POST   /api/upload                          — Subir archivo adjunto
GET    /api/attachments/{id}/range          — Obtener rango de chunks
DELETE /api/attachments/{id}               — Eliminar adjunto
POST   /api/export                          — Exportar texto como archivo
GET    /api/outputs/{id}/download           — Descargar archivo guardado
DELETE /api/outputs/{id}                   — Eliminar archivo guardado
GET    /projects/api/projects/{id}/outputs  — Listar outputs de un proyecto
```

## Formatos soportados

### Entrada
- PDF (extracción de texto por páginas)
- DOCX (párrafos)
- TXT / MD / .py / .js / .json (lectura directa)
- CSV (filas)
- XLSX (filas por hoja)

### Salida
- TXT / Markdown
- DOCX (con plantillas: Informe, Carta, Escrito legal, Email, Resumen ejecutivo, Texto libre)
- PDF (con las mismas plantillas)
- CSV
