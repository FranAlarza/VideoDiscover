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

## 2.3 Siguiente entrega — Ejecutor real

Se integrará `yt-dlp` detrás del contrato `DownloadExecutor`, con temporales por
tarea, selección de formato, progreso real, cancelación del proceso y publicación
segura del archivo final. Hasta entonces, los resultados del worker son simulados
y no representan archivos existentes.

## Puerta de salida de la fase 2

La fase termina cuando vídeo y audio pueden descargarse de forma controlada a un
directorio temporal, procesarse con FFmpeg, moverse a una ruta final segura y
cancelarse sin dejar procesos ni archivos parciales.
