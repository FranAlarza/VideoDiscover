# Alcance funcional del MVP

## Plataformas

- YouTube y TikTok son las únicas plataformas garantizadas y probadas.
- Una URL de otra plataforma debe rechazarse con un mensaje comprensible, aunque `yt-dlp` pueda reconocerla.
- Las listas de reproducción no forman parte del MVP. Si una URL corresponde a una, la aplicación debe informar de ello y no iniciar una descarga por lotes.

## Salidas

### Vídeo MP4

- La aplicación seleccionará la mejor combinación de vídeo y audio compatible con la calidad elegida.
- FFmpeg combinará las pistas cuando lleguen separadas.
- Se preferirá MP4 sin recodificar cuando sea posible.
- Si la fuente no permite producir MP4 de forma compatible, la aplicación debe explicar el problema; WebM no será una opción visible del MVP.

### Audio MP3

- FFmpeg extraerá y convertirá el audio a MP3.
- No se conservará el vídeo temporal después de completar la extracción.
- La calidad predeterminada será 192 kbps.
- La interfaz no afirmará que una conversión a mayor bitrate mejora la fuente original.

## Calidad seleccionable

### Vídeo

- Mejor disponible.
- 2160p.
- 1440p.
- 1080p.
- 720p.
- 480p.
- 360p.

Después del análisis solo se mostrarán las resoluciones disponibles. Al escoger una resolución, se seleccionará la mejor variante que no supere ese límite.

### Audio

- 128 kbps.
- 192 kbps, predeterminada.
- 320 kbps.

## Cola

- Solo puede existir una descarga activa.
- Las nuevas descargas quedan en una cola FIFO.
- Al finalizar, fallar o cancelar la descarga activa, comienza automáticamente la siguiente.
- El usuario puede cancelar la descarga activa o retirar una tarea pendiente.
- Reordenar la cola queda fuera del MVP.

## Análisis previo

Al analizar una URL válida, la interfaz mostrará cuando los datos estén disponibles:

- Miniatura.
- Título.
- Autor o canal.
- Plataforma.
- Duración.
- Fecha de publicación.
- Resoluciones disponibles.
- Tamaño estimado.

La ausencia de fecha o tamaño estimado no debe impedir la descarga. Las visualizaciones, comentarios y seguidores no se consultarán ni mostrarán.

## Historial

Cada entrada guardará:

- URL original, título y plataforma.
- Formato y calidad solicitados.
- Estado y marcas de tiempo.
- Ruta final, si la descarga terminó.
- Mensaje de error comprensible, si falló.

La interfaz permitirá:

- Abrir un archivo completado.
- Mostrarlo en Finder.
- Reintentar una descarga fallida.
- Cancelar una descarga activa o pendiente.
- Eliminar una entrada del historial.

Eliminar una entrada del historial no eliminará el archivo descargado. El borrado de archivos desde la aplicación queda fuera del MVP.

## Criterios de aceptación de la tarea 0.2

- Una URL admitida puede analizarse antes de descargar.
- La interfaz ofrece únicamente las salidas y calidades definidas aquí.
- Nunca se ejecutan dos descargas simultáneamente.
- Las tareas pendientes mantienen el orden de llegada.
- Los metadatos opcionales ausentes no bloquean el flujo.
- El historial ofrece las acciones definidas sin borrar archivos del usuario.
- Una lista de reproducción o plataforma no admitida se rechaza de forma explícita.
