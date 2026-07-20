# Fase 2 — Núcleo de descarga

## Objetivo

Construir tareas de descarga seguras, persistentes y ejecutables mediante una
cola FIFO con una única transferencia activa.

## 2.1 Modelo de tarea y API provisional

- [x] Definir salidas `video` y `audio` con opciones mutuamente excluyentes.
- [x] Limitar vídeo a 360p, 480p, 720p, 1080p, 1440p y 2160p.
- [x] Limitar audio a 128, 192 y 320 kbps.
- [x] Crear tareas con UUID y fechas UTC.
- [x] Separar la tarea estable de sus intentos de ejecución.
- [x] Implementar estados y transiciones permitidas.
- [x] Hacer inmutables los estados terminales de un intento.
- [x] Exigir resultado al completar y error al fallar.
- [x] Validar progreso y permitir valores desconocidos como `null`.
- [x] Crear un repositorio en memoria seguro para concurrencia.
- [x] Devolver copias para impedir mutaciones fuera del repositorio.
- [x] Validar e inspeccionar antes de crear la tarea.
- [x] Rechazar una calidad o pista de audio no disponible.
- [x] Crear, listar, consultar y cancelar tareas en cola mediante HTTP.
- [x] Omitir URL original, URL canónica y rutas internas de la respuesta.
- [x] Añadir pruebas de dominio, repositorio, servicio y API.

### Crear una tarea

```http
POST /api/downloads
Content-Type: application/json

{
  "url": "https://www.youtube.com/watch?v=VIDEO_ID",
  "output_type": "video",
  "video_quality": 1080,
  "audio_bitrate": null
}
```

La respuesta HTTP 201 incluye identidad, selección, estado, posición y el intento
actual, pero no contiene URLs ni información del sistema de archivos.

Para audio:

```json
{
  "url": "https://www.youtube.com/watch?v=VIDEO_ID",
  "output_type": "audio",
  "video_quality": null,
  "audio_bitrate": 192
}
```

### Consultas

```http
GET  /api/downloads
GET  /api/downloads/{id}
POST /api/downloads/{id}/cancel
```

El worker simulado procesa automáticamente las tareas. Permite comprobar cola,
progreso, procesamiento y cancelación sin acceder a la red ni crear archivos.

### Máquina de estados

```text
queued       -> downloading | cancelled
downloading  -> processing | completed | failed | cancelled | interrupted
processing   -> completed | failed | cancelled | interrupted
```

`completed`, `failed`, `cancelled` e `interrupted` son terminales. Un reintento
de `failed` o `interrupted` añade un intento nuevo en estado `queued`.

### Persistencia provisional

`InMemoryDownloadRepository` protege operaciones con un lock asíncrono y devuelve
copias profundas. Sus datos desaparecen al reiniciar; SQLite se incorporará en
una entrega posterior usando el protocolo `DownloadRepository` ya definido.

### Evidencia de la entrega

- Pruebas totales del backend: 89 aprobadas.
- Pruebas de dominio, repositorio, servicio y API: 22 aprobadas.
- Ruff lint y formato: aprobados.
- Una URL autorizada de YouTube creó mediante HTTP una tarea 1080p con estado
  `queued`, posición 1, UUID y primer intento.
- La respuesta no expuso URL original, URL canónica ni rutas internas.
- La cancelación respondió HTTP 200 y llevó el intento a `cancelled` con fecha de
  finalización y sin posición de cola.
- No se crearon vídeos, audios, `.part` ni `.ytdl`.

## 2.2 Cola FIFO y worker simulado

- [x] Crear un coordinador de cola con una única tarea activa.
- [x] Reclamar atómicamente y desencolar en orden de creación.
- [x] Avanzar tras completar, fallar o cancelar.
- [x] Impedir ejecuciones duplicadas y descargas simultáneas.
- [x] Recuperar tareas pendientes al iniciar el servicio.
- [x] Marcar como `interrupted` las tareas que quedaron activas.
- [x] Publicar progreso mediante callbacks internos.
- [x] Cancelar tareas activas mediante una señal cooperativa.
- [x] Apagar ordenadamente el worker.
- [x] Usar un ejecutor simulado sin red ni escrituras.

### Evidencia de la entrega 2.2

- Orden FIFO verificado con tres tareas.
- La cola continúa después de un fallo y después de una cancelación activa.
- Progreso, procesamiento, resultado y error se guardan en el repositorio.
- Una tarea activa previa se convierte en `interrupted` al arrancar.
- Suite completa: 92 pruebas aprobadas; Ruff lint y formato aprobados.

## 2.3 Ejecutor real

Estado de implementación: completado; flujo real principal verificado.

- [x] Integrar `yt-dlp` detrás del contrato `DownloadExecutor`.
- [x] Mantener el modo simulado como opción predeterminada segura.
- [x] Habilitar el modo real únicamente con `VD_DOWNLOAD_EXECUTOR=real`.
- [x] Crear un staging impredecible y exclusivo por UUID.
- [x] Limitar vídeo a la altura solicitada y producir MP4 con H.264 + AAC para
  compatibilidad con QuickTime.
- [x] Extraer audio a MP3 con el bitrate solicitado.
- [x] Ejecutar `yt-dlp` en un proceso `spawn`, sin shell.
- [x] Comunicar progreso y comienzo del postprocesado mediante IPC.
- [x] Terminar únicamente el proceso de la tarea cancelada.
- [x] Sanear nombres y bloquear semántica de rutas en títulos/extensiones.
- [x] Resolver colisiones con sufijos sin sobrescribir archivos.
- [x] Verificar que el resultado procede del staging autorizado.
- [x] Publicar el resultado en la carpeta final y limpiar el staging.
- [x] Traducir errores comunes a códigos y mensajes estables.

### Configuración

```text
VD_DOWNLOAD_EXECUTOR=simulated|real
VD_DOWNLOAD_OUTPUT_ROOT=/ruta/autorizada
VD_DOWNLOAD_TEMPORARY_ROOT=/ruta/temporal
VD_NODE_BINARY=/ruta/a/node
```

Los valores predeterminados de desarrollo son `simulated`, `downloads/` y
`downloads/.temporary/`. La API nunca devuelve la URL canónica ni rutas físicas.

### Evidencia automatizada

- Selección acotada de vídeo y conversión MP3 verificadas sin red.
- Traversal, caracteres de control y extensiones maliciosas rechazados o saneados.
- Colisiones verificadas conservando intacto el archivo existente.
- Progreso y procesamiento propagados mediante callbacks.
- Cancelación cooperativa y limpieza del staging verificadas.
- Publicación y resultado final verificados con un runner falso.
- Suite completa: 106 pruebas aprobadas; Ruff lint y formato aprobados.

### Evidencia manual — 20 de julio de 2026, macOS Apple Silicon

- YouTube MP4 autorizado a 720p: `completed`, progreso 100 %, calidad efectiva
  720p y archivo final publicado sin exponer su ruta en la API. La primera
  selección AV1 + Opus mostró pantalla negra en QuickTime; se corrigió el selector
  para exigir H.264 + AAC. La segunda descarga se reprodujo correctamente con
  imagen y sonido en QuickTime, sin advertencias.
- Audio autorizado a 192 kbps: `completed`, progreso 100 % y archivo MP3 final.
- Cancelación real durante `downloading`: transición a `cancelled` en menos de un
  segundo, sin resultado final ni fallo.
- Tras completar y cancelar, `downloads/.temporary/` quedó vacío y no aparecieron
  archivos `.part` ni `.ytdl`.
- MP4 y MP3 se reprodujeron correctamente. `ffprobe` identificó la causa de la
  primera incompatibilidad y la salida compatible quedó verificada en QuickTime.

## Puerta de salida de la fase 2

La fase termina cuando vídeo y audio pueden descargarse de forma controlada a un
directorio temporal, procesarse con FFmpeg, moverse a una ruta final segura y
cancelarse sin dejar procesos ni archivos parciales.

## 2.4 Persistencia SQLite y recuperación

Estado de implementación: completado y reinicio real verificado.

- [x] Fijar SQLAlchemy 2 y Alembic en el proyecto y el lockfile.
- [x] Crear tablas normalizadas `downloads` y `download_attempts`.
- [x] Añadir índices para creación, estado y número de intento.
- [x] Activar claves foráneas y WAL en conexiones de aplicación.
- [x] Crear una migración inicial reproducible sobre una base vacía.
- [x] Aplicar migraciones automáticamente al arrancar.
- [x] Implementar el contrato completo con `SqliteDownloadRepository`.
- [x] Reclamar FIFO mediante `BEGIN IMMEDIATE` para impedir duplicados.
- [x] Mantener el progreso frecuente en memoria sin escribir cada fragmento.
- [x] Persistir estados, errores, resultados y progreso terminal.
- [x] Convertir tareas activas anteriores a `interrupted` al arrancar.
- [x] Recuperar y continuar tareas `queued` conservando el orden.
- [x] Mantener el repositorio en memoria para pruebas aisladas.

### Configuración y migraciones

```text
VD_DATABASE_PATH=/ruta/video-downloader.sqlite3
```

El valor de desarrollo es `data/video-downloader.sqlite3`. Desde `backend/` se
puede ejecutar `uv run alembic upgrade head`; el arranque normal realiza la misma
actualización programáticamente.

### Evidencia automatizada

- Migración inicial verificada sobre una base vacía.
- Tarea completada reconstruida con selección, progreso y resultado.
- Reclamación FIFO única verificada con llamadas concurrentes.
- Progreso visible en vivo y ausente tras crear otro repositorio sin transición.
- Reinicio simulado: activa a `interrupted`, pendiente conservada y reclamada.
- Suite completa: 112 pruebas aprobadas; Ruff lint y formato aprobados.

### Evidencia manual — 20 de julio de 2026

- Se creó una tarea con ejecutor simulado y base SQLite separada.
- Tras detener y volver a iniciar Uvicorn con la misma base, `GET /api/downloads/{id}`
  devolvió el mismo UUID, selección, fechas, progreso, resultado e intento.
- El estado terminal permaneció en `completed` y no se creó otro intento.
