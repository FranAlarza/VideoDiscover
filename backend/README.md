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

## Verificación

```bash
uv run pytest
uv run ruff check .
uv run ruff format --check .
```

La configuración admite `VD_ENV`, `VD_PORT`, `VD_LOG_LEVEL` y
`VD_FRONTEND_ORIGIN`. El host no es configurable: permanece limitado a
`127.0.0.1`.
