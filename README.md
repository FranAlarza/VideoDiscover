# Video Downloader

Aplicación local para analizar y descargar contenido audiovisual autorizado a partir de una URL.

La fase 0 de definición está cerrada. Consulta [`docs/phase-0.md`](docs/phase-0.md)
y [`docs/acceptance-criteria.md`](docs/acceptance-criteria.md) antes de comenzar la
implementación.

La fase 1 está completada: el backend valida y analiza URLs autorizadas de
YouTube y TikTok sin descargar contenido. Consulta
[`docs/phase-1.md`](docs/phase-1.md) para ver contratos y evidencias.

La fase 2 está en curso. Ya existe el modelo de tarea, una cola FIFO con un único
worker, progreso y cancelación mediante un ejecutor simulado; consulta
[`docs/phase-2.md`](docs/phase-2.md).

## Estructura

- `backend/`: API, motor de descarga y persistencia.
- `frontend/`: interfaz local.
- `docs/`: requisitos y decisiones del proyecto.
- `scripts/`: automatización de desarrollo y empaquetado.
- `downloads/`: salida local de desarrollo; su contenido no se versiona.

## Backend

```bash
cd backend
uv sync
uv run pytest
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

También puede iniciarse desde la raíz con `./scripts/dev-backend.sh`.
