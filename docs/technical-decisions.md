# Decisiones técnicas del MVP

## Plataforma de referencia

- Sistema: macOS 13 o posterior.
- Arquitectura: Apple Silicon (`arm64`).
- Desarrollo: VS Code y terminal.
- La lógica del núcleo evitará APIs exclusivas de macOS cuando no sean necesarias.

## Backend

- Python 3.13 como línea de desarrollo.
- FastAPI 0.139.x.
- Uvicorn como servidor ASGI local.
- Pydantic 2 para contratos y validación.
- `yt-dlp` mediante su API Python.
- FFmpeg y `ffprobe` 8.x como binarios externos.
- SQLite con SQLAlchemy 2.
- Alembic para migraciones de esquema.
- `pytest` para pruebas.
- Ruff para formato y análisis estático.
- `uv` para entorno, instalación y bloqueo de dependencias.

Python 3.13 se elige como línea madura para el núcleo y el futuro empaquetado. No se utiliza el Python incluido por el sistema operativo.

## Frontend

- Node.js 24 LTS.
- React 19.2.
- TypeScript 5.8 o posterior dentro de la misma línea compatible fijada por el archivo de bloqueo.
- Vite como servidor de desarrollo y herramienta de compilación.
- npm y `package-lock.json` para instalaciones reproducibles.
- Vitest y React Testing Library.
- ESLint y Prettier.
- TypeScript se configura en modo estricto.

No se incorporará un framework de renderizado de servidor: la aplicación es local y Vite produce una SPA estática.

## Descarga y multimedia

- `yt-dlp` analiza y descarga mediante su API Python y `progress_hooks`.
- La versión estable se fija exactamente en `uv.lock`.
- Las actualizaciones de `yt-dlp` se hacen de forma explícita y pasan las pruebas de integración de YouTube y TikTok.
- FFmpeg combina pistas y convierte a MP3; no se instala un paquete Python llamado `ffmpeg` como sustituto del binario.
- Al arrancar, el backend comprueba la presencia y versión de `ffmpeg` y `ffprobe`.
- Node.js 24 actúa también como runtime JavaScript cuando `yt-dlp` lo necesite para la extracción.

## Persistencia

SQLite guardará configuración, aceptación del aviso, cola, historial e intentos de descarga. El esquema preliminar se separa en:

- `downloads`: identidad y datos funcionales de la descarga.
- `download_attempts`: cada ejecución o reintento y su estado terminal.
- `settings`: preferencias locales.
- `legal_acceptances`: versión y fecha de aceptación del aviso.

La tabla `settings` se crea en la revisión `20260720_02`. La primera preferencia
tipada es `download_output_root`; el repositorio conserva rutas absolutas resueltas,
pero su validación operativa y su aplicación al ejecutor pertenecen a la siguiente
entrega.

El progreso de alta frecuencia permanece en memoria. Solo se persisten transiciones de estado y puntos necesarios para recuperación; no se escribe en SQLite por cada actualización de porcentaje.

Las modificaciones del esquema se realizan mediante migraciones Alembic. No se altera la base de datos manualmente durante una actualización normal.

## Comunicación entre frontend y backend

- HTTP JSON para comandos, análisis, consultas e historial.
- Server-Sent Events (SSE) para progreso y cambios de estado enviados por el backend.
- Una única conexión SSE por instancia de frontend.
- Si SSE se reconecta, el frontend consulta una instantánea del estado para evitar eventos perdidos.
- WebSockets y sondeo periódico quedan fuera del flujo principal del MVP.

Endpoints conceptuales iniciales:

```text
GET  /health
POST /api/media/inspect
POST /api/downloads
GET  /api/downloads
GET  /api/downloads/{id}
DELETE /api/downloads/{id}
POST /api/downloads/{id}/cancel
POST /api/downloads/{id}/retry
POST /api/downloads/{id}/open
POST /api/downloads/{id}/reveal
GET  /api/events
GET  /api/settings
PUT  /api/settings/download-directory
POST /api/settings/download-directory/choose
```

La ubicación absoluta del resultado se conserva únicamente en SQLite para que
las acciones locales sigan funcionando aunque cambie la carpeta configurada.
Esa ruta no forma parte de las respuestas HTTP ni de los eventos SSE.

La forma definitiva de estos contratos se establecerá antes de implementarlos.

## Aplicación de escritorio

- El núcleo del MVP se valida ejecutando frontend y backend desde terminal.
- Tauri 2 se incorpora después de completar y probar el flujo funcional.
- Rust y las herramientas adicionales de Tauri no son dependencias de la primera iteración.
- El empaquetado deberá gestionar el backend y los binarios auxiliares sin exponerlos a la red.

## Política de versiones

| Componente | Línea aprobada |
|---|---|
| macOS | 13 o posterior |
| Python | 3.13.x |
| FastAPI | 0.139.x |
| Pydantic | 2.x |
| SQLAlchemy | 2.x |
| FFmpeg y ffprobe | 8.x |
| Node.js | 24 LTS |
| React y React DOM | 19.2.x |
| TypeScript | 5.8 o posterior compatible |
| Tauri | 2.x, fase posterior |

- Las dependencias directas se declaran con límites compatibles y las resoluciones exactas quedan en archivos de bloqueo.
- `backend/uv.lock` y `frontend/package-lock.json` se versionan.
- No se actualizan dependencias incidentalmente dentro de una tarea no relacionada.
- Una actualización ejecuta pruebas unitarias, integración afectada y comprobaciones de seguridad.
- FastAPI controla su versión compatible de Starlette; no se fija Starlette directamente salvo necesidad documentada.

## Fuentes de referencia consultadas

- Python: <https://www.python.org/downloads/>
- FastAPI: <https://fastapi.tiangolo.com/deployment/versions/>
- yt-dlp: <https://github.com/yt-dlp/yt-dlp>
- FFmpeg: <https://ffmpeg.org/download.html>
- Node.js: <https://nodejs.org/en/about/previous-releases>
- React: <https://react.dev/versions>
- Tauri: <https://v2.tauri.app/start/prerequisites/>

## Criterios de aceptación de la tarea 0.5

- Cada componente principal tiene una responsabilidad definida.
- Las líneas mínimas o compatibles están documentadas.
- Backend y frontend dispondrán de un archivo de bloqueo versionado.
- El progreso usa SSE y dispone de resincronización al reconectar.
- El progreso frecuente no provoca escrituras continuas en SQLite.
- `yt-dlp` se integra sin shell y FFmpeg se verifica al arrancar.
- Tauri no bloquea la implementación ni las pruebas del núcleo.
- Toda actualización de dependencias es explícita y verificable.
