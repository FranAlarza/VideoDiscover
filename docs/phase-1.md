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

## 1.4 Análisis de metadatos

- [x] Invocar `yt-dlp` con `download=False`, `skip_download` y modo simulado.
- [x] Usar únicamente una URL validada y canónica.
- [x] Ejecutar el extractor en un proceso aislado terminable.
- [x] Configurar un timeout real de 25 segundos.
- [x] Pasar explícitamente Node.js 24 al runtime JavaScript.
- [x] Deshabilitar componentes JavaScript remotos.
- [x] Traducir metadatos a un contrato propio y limitado.
- [x] Omitir URLs de formatos, cabeceras, cookies y campos internos.
- [x] Detectar playlists, directos y respuestas mal formadas.
- [x] Enumerar resoluciones únicas y disponibilidad de audio.
- [x] Calcular tamaño estimado solo con datos disponibles.
- [x] Traducir errores de extractor a códigos y mensajes estables.
- [x] Impedir que errores crudos de `yt-dlp` lleguen a stderr o al frontend.
- [x] Añadir pruebas mediante dobles sin acceder a plataformas reales.
- [x] Comprobar el proceso aislado mediante una petición HTTP real.

### Contrato

```http
POST /api/media/inspect
Content-Type: application/json

{"url":"https://www.youtube.com/watch?v=VIDEO_ID"}
```

```json
{
  "platform": "youtube",
  "media_id": "VIDEO_ID",
  "title": "Título",
  "author": "Autor",
  "duration_seconds": 120,
  "thumbnail_url": "https://...",
  "published_at": "2026-07-20",
  "estimated_size": 1000000,
  "video_qualities": [1080, 720, 480],
  "audio_available": true,
  "is_live": false
}
```

Los campos `author`, duración, miniatura, fecha y tamaño son opcionales. Las
resoluciones se limitan a 2160p, 1440p, 1080p, 720p, 480p y 360p y se devuelven
sin duplicados.

### Aislamiento

FastAPI valida primero la URL. Después crea un proceso mediante el método
`spawn`; dentro de ese proceso se usa la API Python de `yt-dlp`. Si el límite se
supera, el proceso se termina y, si fuera necesario, se mata tras un periodo de
gracia. De este modo un extractor bloqueado no continúa trabajando en segundo
plano.

El proceso devuelve metadatos saneados mediante una conexión unidireccional. La
aplicación transforma inmediatamente esos datos y descarta campos no incluidos
en el contrato público.

### Evidencia de la entrega

- Pruebas totales del backend: 60 aprobadas.
- Casos específicos de inspección: 20 aprobados.
- Ruff lint y formato: aprobados.
- La configuración prueba `download=False`, `skip_download`, `simulate` y
  `noplaylist`.
- La URL entregada al runner es siempre la canónica producida por el validador.
- Una petición real inició correctamente el proceso aislado y no creó archivos.
- El vídeo histórico de prueba consultado respondió actualmente como no
  disponible; la API lo tradujo a HTTP 404 con `media_unavailable`.
- Una URL activa proporcionada por el usuario superó validación e inspección con
  HTTP 200: se obtuvieron título, autor, duración, fecha, miniatura, tamaño
  estimado, audio y calidades 1080p, 720p, 480p y 360p.
- Después de la inspección real no existían vídeos, audios, `.part` ni `.ytdl` en
  los directorios del proyecto.
- Los logs reales solo mostraron las solicitudes saneadas y sus códigos HTTP.

Las pruebas reales positivas de YouTube y TikTok quedan en `PASS` con URLs
activas proporcionadas por el usuario.

## 1.5 Siguiente entrega — Inspección real autorizada y endurecimiento

- [x] Proporcionar una URL activa y autorizada de YouTube.
- [x] Proporcionar una URL activa y autorizada de TikTok.
- [x] Verificar metadatos y resoluciones reales de TikTok.
- [x] Confirmar mediante el sistema de archivos que YouTube no crea contenido.
- [x] Confirmar mediante el sistema de archivos que TikTok no crea contenido.
- [ ] Ejecutar una prueba de timeout real controlada.
- [ ] Revisar redacción de logs y límites de metadatos con respuestas reales.

### Evidencia real de TikTok

- La query de seguimiento se eliminó correctamente de la URL canónica.
- La validación y la inspección respondieron HTTP 200.
- Se obtuvieron título, autor, duración, fecha, miniatura, tamaño y audio.
- El primer análisis reveló que el vídeo vertical usaba dimensiones no estándar.
- El mapeo se corrigió para utilizar el lado corto y seleccionar la mejor calidad
  estándar que no lo supere; el resultado real pasó a ofrecer 480p.
- Se añadió una prueba de regresión para vídeo vertical.
- No se crearon vídeos, audios, `.part` ni `.ytdl`.
- Los logs solo mostraron la solicitud saneada y su código HTTP.

## Puerta de salida de la fase 1

La fase termina cuando una URL autorizada de YouTube o TikTok puede validarse y analizarse sin descargar el archivo, y el resultado cumple los contratos funcionales y de seguridad de la fase 0.
