# Backend

API local del MVP construida con Python 3.13 y FastAPI.

## Preparación

```bash
uv sync
```

## Desarrollo

Desde `backend/`:

```bash
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

El endpoint de salud queda disponible en `http://127.0.0.1:8000/health`.

El diagnóstico local de dependencias está disponible en
`http://127.0.0.1:8000/api/system/diagnostics`. La comprobación se realiza al
arrancar y nunca expone las rutas de los ejecutables.

La validación segura de una URL se realiza con:

```http
POST /api/media/validate
Content-Type: application/json

{"url":"https://www.youtube.com/watch?v=VIDEO_ID"}
```

El endpoint admite vídeos individuales de YouTube y TikTok, valida DNS/IP y
resuelve de forma limitada los enlaces cortos de TikTok. No descarga contenido.

## Verificación

```bash
uv run pytest
uv run ruff check .
uv run ruff format --check .
```

La configuración admite `VD_ENV`, `VD_PORT`, `VD_LOG_LEVEL`,
`VD_FRONTEND_ORIGIN` y `VD_NODE_BINARY`. El host no es configurable: permanece
limitado a `127.0.0.1`.
