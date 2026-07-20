# Video Downloader

Aplicación local para analizar y descargar contenido audiovisual autorizado a partir de una URL.

La fase 0 de definición está cerrada. Consulta [`docs/phase-0.md`](docs/phase-0.md)
y [`docs/acceptance-criteria.md`](docs/acceptance-criteria.md) antes de comenzar la
implementación.

La fase 1 está completada: el backend valida y analiza URLs autorizadas de
YouTube y TikTok sin descargar contenido. Consulta
[`docs/phase-1.md`](docs/phase-1.md) para ver contratos y evidencias.

La fase 2 del backend está completada. La fase 3 de interfaz ya incluye análisis,
descargas reales, progreso, cancelación, historial, reintentos y acciones sobre
archivos completados; consulta
[`docs/phase-2.md`](docs/phase-2.md) y [`docs/phase-3.md`](docs/phase-3.md).

## Estructura

- `backend/`: API, motor de descarga y persistencia.
- `frontend/`: interfaz local.
- `docs/`: requisitos y decisiones del proyecto.
- `scripts/`: automatización de desarrollo y empaquetado.
- `downloads/`: salida local de desarrollo; su contenido no se versiona.

## Backend

Para levantar backend y frontend juntos en desarrollo:

```bash
./scripts/dev.sh
```

La interfaz queda disponible en `http://127.0.0.1:5173`. El script también
arranca la API en `http://127.0.0.1:8000` y detiene ambos procesos con `Ctrl+C`.
Si alguno de los puertos ya está ocupado por una ejecución anterior:

```bash
./scripts/dev.sh --restart
```

Para arrancar solo el backend:

```bash
cd backend
uv sync
uv run pytest
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

También puede iniciarse desde la raíz con `./scripts/dev-backend.sh`.

`./scripts/dev.sh` usa el ejecutor real. Para arrancar manualmente el backend con
ese mismo comportamiento:

```bash
VD_DOWNLOAD_EXECUTOR=real uv run uvicorn app.main:app \
  --host 127.0.0.1 --port 8000
```

Los archivos terminados se guardan en `downloads/` y cada ejecución usa un
subdirectorio aislado en `downloads/.temporary/`. Se pueden cambiar mediante
`VD_DOWNLOAD_OUTPUT_ROOT` y `VD_DOWNLOAD_TEMPORARY_ROOT`.

Las tareas y sus intentos se conservan en SQLite, por defecto en
`data/video-downloader.sqlite3`. Al arrancar, Alembic aplica automáticamente las
migraciones pendientes. La ruta puede cambiarse con `VD_DATABASE_PATH` y las
migraciones también pueden ejecutarse manualmente desde `backend/`:

```bash
uv run alembic upgrade head
```

El endpoint `GET /api/events` publica una instantánea inicial y cambios de tareas
mediante Server-Sent Events. Admite `Last-Event-ID`, keepalive y solicita una
resincronización si un cliente lento pierde eventos.

## Frontend

Requiere Node.js 24:

```bash
cd frontend
npm install
npm run dev
```

Vite escucha únicamente en `http://127.0.0.1:5173` y envía `/api` y `/health` al
backend local en el puerto 8000. Las comprobaciones disponibles son:

```bash
npm run build
npm test
npm run lint
npm run format
```
