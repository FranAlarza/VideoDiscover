# Fase 1 — Backend y núcleo de análisis

## Objetivo

Construir un backend local verificable y el primer flujo de análisis de una URL sin descargar contenido.

## 1.1 Backend mínimo y endpoint de salud

- [x] Auditar arquitectura y herramientas locales.
- [x] Instalar Python 3.13 y `uv` para Apple Silicon.
- [x] Inicializar el proyecto Python y generar `uv.lock`.
- [x] Crear una factoría de aplicación FastAPI sin estado global mutable compartido.
- [x] Centralizar configuración local y validar el puerto.
- [x] Limitar el arranque documentado a `127.0.0.1`.
- [x] Configurar CORS con el origen exacto del frontend de desarrollo.
- [x] Desactivar OpenAPI y Swagger en producción.
- [x] Implementar `GET /health`.
- [x] Añadir pruebas de contrato, aislamiento y configuración.
- [x] Configurar Ruff y pytest.
- [x] Añadir un script de desarrollo y documentar los comandos.
- [x] Verificar el endpoint mediante una petición HTTP real.

### Contrato

```http
GET /health
```

```json
{
  "status": "ok",
  "service": "video-downloader-api"
}
```

El endpoint es una comprobación de vida: no consulta Internet, SQLite, `yt-dlp`, FFmpeg ni información del sistema.

### Evidencia de la entrega

- Plataforma: macOS Apple Silicon (`arm64`).
- Python: 3.13.14.
- `uv`: 0.11.29.
- FastAPI bloqueado: 0.139.2.
- Pruebas: 5 aprobadas.
- Ruff lint: aprobado.
- Ruff format: aprobado.
- HTTP real: `GET /health` respondió 200 con el contrato exacto.

Existe un aviso de deprecación originado dentro de `fastapi.testclient`/Starlette por su transición de `httpx` a `httpx2`. No afecta al resultado de las pruebas y se mantiene visible para revisarlo al actualizar dependencias.

### Diferencias detectadas para tareas posteriores

- Node.js instalado: 23.11.0; debe sustituirse por Node.js 24 LTS antes de inicializar el frontend.
- FFmpeg instalado: 7.1.1; la línea aprobada es FFmpeg 8.x y se revisará antes de integrar procesamiento multimedia.

## 1.2 Siguiente entrega — Diagnóstico de dependencias multimedia

- [ ] Integrar `yt-dlp` y su runtime JavaScript recomendado.
- [ ] Detectar `yt-dlp`, Node.js, FFmpeg y `ffprobe` al arrancar.
- [ ] Exponer el diagnóstico interno sin filtrar rutas o versiones en `/health`.
- [ ] Traducir dependencias ausentes a códigos de error estables.
- [ ] Añadir pruebas mediante dobles y una comprobación local controlada.

## Puerta de salida de la fase 1

La fase termina cuando una URL autorizada de YouTube o TikTok puede validarse y analizarse sin descargar el archivo, y el resultado cumple los contratos funcionales y de seguridad de la fase 0.
