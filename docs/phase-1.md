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

## 1.2 Diagnóstico de dependencias multimedia

- [x] Integrar `yt-dlp` y su runtime JavaScript recomendado.
- [x] Instalar Node.js 24 LTS de forma versionada para no reemplazar el Node global.
- [x] Actualizar FFmpeg y `ffprobe` a la línea 8.x.
- [x] Detectar `yt-dlp`, Node.js, FFmpeg y `ffprobe` al arrancar.
- [x] Exponer el diagnóstico interno sin alterar ni filtrar información en `/health`.
- [x] Evitar exponer rutas de ejecutables en la respuesta pública.
- [x] Traducir dependencias ausentes o incompatibles a códigos estables.
- [x] Añadir pruebas mediante dobles y una comprobación local controlada.

### Contrato

```http
GET /api/system/diagnostics
```

```json
{
  "ready": true,
  "dependencies": [
    {
      "name": "yt-dlp",
      "status": "available",
      "version": "2026.07.04",
      "error_code": null
    }
  ]
}
```

Cada dependencia usa `available`, `missing` o `incompatible`. Los códigos siguen
el patrón `<dependencia>_missing` y `<dependencia>_incompatible`. El diagnóstico
se captura una vez durante el arranque de FastAPI; `/health` conserva su contrato
de vida y no ejecuta estas comprobaciones.

Los comandos de versión usan argumentos estructurados, `shell=False`, un timeout
de cinco segundos y una salida saneada que omite la ruta local del binario.

### Evidencia de la entrega

- `yt-dlp`: 2026.07.04, con `yt-dlp-ejs` y `curl-cffi`.
- Node.js: 24.18.0 desde la fórmula versionada `node@24`.
- FFmpeg y `ffprobe`: 8.1.2.
- Diagnóstico local: `ready: true` para las cuatro dependencias.
- Pruebas: 11 aprobadas.
- Ruff lint y formato: aprobados.
- `/health` mantiene el contrato aprobado.

Durante la comprobación HTTP se detectó que Node utiliza `--version`, frente a
`-version` de FFmpeg. El diagnóstico se corrigió y dispone de una prueba de
regresión específica.

## 1.3 Validación segura de URL

- [x] Normalizar y validar URLs HTTP/HTTPS.
- [x] Limitar longitud, caracteres, parámetros y puertos.
- [x] Reconocer únicamente URLs individuales de YouTube y TikTok.
- [x] Admitir YouTube Watch, enlaces cortos, Shorts, Live y Embed.
- [x] Admitir URLs canónicas y enlaces cortos de TikTok.
- [x] Canonicalizar plataforma, identificador y URL final.
- [x] Rechazar credenciales embebidas, playlists, perfiles y dominios engañosos.
- [x] Clasificar todos los destinos DNS/IP en IPv4 e IPv6.
- [x] Rechazar el host completo si cualquiera de sus direcciones no es pública.
- [x] Limitar redirecciones, detectar bucles y revalidar cada destino.
- [x] Implementar códigos y mensajes de error estables.
- [x] Añadir pruebas unitarias sin acceder a plataformas reales.
- [x] Verificar el contrato mediante HTTP local.

### Contrato

```http
POST /api/media/validate
Content-Type: application/json

{"url":"https://youtu.be/dQw4w9WgXcQ"}
```

```json
{
  "valid": true,
  "platform": "youtube",
  "media_id": "dQw4w9WgXcQ",
  "canonical_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
}
```

Los errores de formato o política devuelven HTTP 400 con `{error: {code,
message}}`. Una imposibilidad temporal de verificar DNS o un enlace corto
devuelve HTTP 503. Los cuerpos JSON mal formados continúan bajo la validación 422
de FastAPI.

### Capas

1. `MediaUrlParser`: sintaxis, dominio, forma de URL e identificador.
2. `NetworkSafetyChecker`: resolución DNS y clasificación de todas las IP.
3. `MediaUrlValidationService`: coordinación y redirecciones limitadas.
4. Endpoint FastAPI: contrato público y traducción estable de errores.

Los enlaces con un vídeo de YouTube y parámetro `list` conservan únicamente el
vídeo individual; una URL cuyo recurso principal sea una playlist se rechaza.

### Evidencia de la entrega

- Pruebas totales del backend: 40 aprobadas.
- Casos del validador: 29 aprobados.
- Ruff lint y formato: aprobados.
- Una URL Watch de YouTube devolvió HTTP 200 y su forma canónica.
- `youtube.com.example.org` devolvió HTTP 400 con `unsupported_platform`.
- `/health` mantuvo su respuesta exacta.

### Limitación conocida

La aplicación valida DNS antes de abrir una conexión y vuelve a validar cada
redirección observable. La biblioteca HTTP resuelve después el host para abrir la
conexión, por lo que esta implementación no afirma eliminar completamente una
ventana de DNS rebinding. La allowlist estricta de plataformas reduce la
superficie; una prueba SSRF de integración seguirá siendo obligatoria antes de la
aceptación final.

## 1.4 Siguiente entrega — Análisis de metadatos

- [ ] Invocar `yt-dlp` con `download=False`.
- [ ] Usar únicamente una URL validada y canónica.
- [ ] Traducir los metadatos al contrato propio del MVP.
- [ ] Detectar playlists o contenido no disponible devuelto por el extractor.
- [ ] Enumerar resoluciones disponibles sin descargar contenido.
- [ ] Añadir timeout, cancelación y traducción de errores.
- [ ] Probar con dobles y una URL autorizada controlada.

## Puerta de salida de la fase 1

La fase termina cuando una URL autorizada de YouTube o TikTok puede validarse y analizarse sin descargar el archivo, y el resultado cumple los contratos funcionales y de seguridad de la fase 0.
