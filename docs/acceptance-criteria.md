# Criterios de aceptación del MVP

## Propósito

Este documento define cómo demostrar que el MVP funciona. Aprobar el plan no significa que las pruebas ya se hayan ejecutado; cada resultado deberá registrarse cuando exista una implementación verificable.

## Entradas de prueba autorizadas

Las pruebas reales requieren URLs aportadas por el propietario del entorno y sobre las que tenga derechos o permiso. No se versionan URLs de contenido personal ni tokens de acceso.

Se usarán estas variables locales, excluidas de Git:

```text
TEST_YOUTUBE_VIDEO_URL=
TEST_TIKTOK_VIDEO_URL=
TEST_CANCELLATION_VIDEO_URL=
```

Requisitos de las entradas:

- `TEST_YOUTUBE_VIDEO_URL`: un vídeo público individual, corto, con audio y al menos una calidad de hasta 720p.
- `TEST_TIKTOK_VIDEO_URL`: un vídeo público individual, corto y con audio.
- `TEST_CANCELLATION_VIDEO_URL`: un vídeo autorizado suficientemente grande para cancelar antes de que termine.
- Ninguna entrada puede requerir cuenta, cookies, pago, verificación de edad ni elusión de restricciones.
- Antes de ejecutar, la persona responsable registra el origen y confirma la autorización sin guardar información personal innecesaria.

Las pruebas automáticas no dependen de estas URLs: usan fixtures de metadatos, dobles de `yt-dlp` y archivos multimedia pequeños generados o autorizados. Las pruebas de integración reales se ejecutan manualmente porque las plataformas cambian y requieren red.

## Evidencias

Cada ejecución manual registra:

- Fecha, versión de la aplicación y plataforma probada.
- Versión de Python, `yt-dlp`, FFmpeg y Node.js.
- Identificador no sensible de la entrada; la URL completa puede omitirse.
- Resultado esperado y observado.
- Estado `PASS`, `FAIL`, `BLOCKED` o `NOT RUN`.
- Ruta o referencia a registros redactados y capturas cuando aporten valor.

Los secretos, cookies, tokens y cadenas de consulta sensibles nunca forman parte de la evidencia.

## AC-01 — Flujo completo de YouTube en MP4

Precondiciones:

- `TEST_YOUTUBE_VIDEO_URL` está definida y autorizada.
- FFmpeg y `ffprobe` están disponibles.
- La carpeta de salida está vacía o controlada para la prueba.

Pasos:

1. Pegar la URL y pulsar **Analizar**.
2. Comprobar plataforma, título, miniatura, autor, duración y resoluciones disponibles.
3. Elegir **Vídeo MP4** y 720p, o la mejor resolución disponible que no la supere.
4. Iniciar la descarga y observar sus estados.
5. Esperar a que termine y abrir el archivo.
6. Mostrarlo en Finder y consultar el historial.

Resultado esperado:

- El análisis no descarga el archivo completo.
- Solo se muestran calidades disponibles.
- La tarea transita por estados permitidos y termina en `completed`.
- El MP4 tiene imagen y audio sincronizados, se reproduce y no supera la resolución solicitada.
- La ruta final existe y coincide con la registrada en el historial.
- No quedan temporales pertenecientes a la tarea.

## AC-02 — Flujo completo de TikTok en MP4

Precondiciones:

- `TEST_TIKTOK_VIDEO_URL` está definida y autorizada.

Pasos:

1. Analizar la URL pública individual.
2. Revisar los metadatos disponibles sin exigir campos opcionales ausentes.
3. Elegir **Vídeo MP4** y la mejor calidad disponible.
4. Descargar, abrir el resultado y mostrarlo en Finder.
5. Revisar la entrada del historial.

Resultado esperado:

- La plataforma se identifica como TikTok.
- La ausencia de fecha o tamaño estimado no bloquea la operación.
- El archivo final se reproduce con imagen y audio.
- La tarea termina en `completed` y el historial contiene sus datos esenciales.
- No quedan archivos temporales de la tarea.

## AC-03 — Extracción de audio MP3

Pasos:

1. Analizar una de las URLs autorizadas.
2. Elegir **Audio MP3** y 192 kbps.
3. Descargar y abrir el resultado.

Resultado esperado:

- FFmpeg produce un archivo `.mp3` reproducible.
- El archivo final contiene audio y no conserva una copia temporal del vídeo.
- El historial registra formato y calidad solicitados.

## AC-04 — Cola FIFO

Pasos:

1. Iniciar una descarga que permanezca activa el tiempo suficiente.
2. Añadir dos descargas adicionales.
3. Observar el orden hasta que finalicen o cancelar de forma controlada.

Resultado esperado:

- Existe como máximo una tarea en `downloading` o `processing`.
- Las otras permanecen `queued`.
- La siguiente tarea comienza respetando el orden de llegada.
- Un fallo o cancelación no detiene la cola.

## AC-05 — Cancelación y limpieza

Precondición: `TEST_CANCELLATION_VIDEO_URL` está definida y autorizada.

Pasos:

1. Iniciar la descarga y esperar al estado `downloading`.
2. Cancelarla antes de completar.
3. Inspeccionar estado, carpeta final y directorio temporal.
4. Repetir, cuando sea viable, cancelando durante `processing`.

Resultado esperado:

- La ejecución termina en `cancelled`.
- Se detienen únicamente los procesos asociados a esa tarea.
- No aparece un archivo final incompleto.
- Se eliminan sus temporales registrados sin tocar archivos preexistentes.
- La siguiente tarea de la cola puede comenzar.

## AC-06 — Fallos controlados

Ejecutar al menos estos casos:

| Caso | Resultado esperado |
|---|---|
| Campo vacío | `empty_url` sin acceder a la red |
| URL mal formada | `invalid_url` sin invocar `yt-dlp` |
| Esquema no permitido | `unsupported_scheme` |
| Plataforma fuera del MVP | `unsupported_platform` |
| Lista de reproducción | `playlist_not_supported` |
| FFmpeg no disponible | `ffmpeg_missing` con ayuda accionable |
| Carpeta sin escritura | `output_not_writable` |
| Formato desaparecido tras analizar | `format_unavailable` y opción de analizar de nuevo |
| Error inesperado simulado | `unknown_error` sin cerrar el backend |

Después de cada caso, `/health` debe seguir respondiendo y una tarea posterior válida debe poder procesarse.

## AC-07 — Colisión de nombres

Pasos:

1. Crear o descargar `Mi vídeo.mp4` en la carpeta controlada.
2. Repetir una descarga que produzca el mismo nombre.

Resultado esperado:

- El primer archivo no cambia.
- El nuevo resultado usa `Mi vídeo (1).mp4`, o el siguiente sufijo libre.
- Historial y ruta física coinciden.

## AC-08 — Reinicio y recuperación

Pasos:

1. Mantener una tarea activa y otra en cola.
2. Cerrar la aplicación de forma controlada o simular la interrupción.
3. Volver a iniciar.

Resultado esperado:

- La tarea antes activa aparece como `interrupted`.
- La tarea pendiente se recupera conservando su posición.
- La interrumpida solo vuelve a ejecutarse si el usuario pulsa **Reintentar**.
- Reintentar analiza de nuevo los formatos y crea una ejecución nueva.

## AC-09 — Seguridad mínima

Se verifican mediante pruebas automáticas y una prueba de integración:

- Bloqueo de esquemas, credenciales embebidas y dominios no admitidos.
- Bloqueo de loopback, redes privadas, link-local, reservadas y equivalentes IPv6.
- Revalidación de redirecciones observables.
- Protección frente a path traversal y escapes mediante enlaces simbólicos.
- Ausencia de `shell=True` y argumentos de proceso estructurados.
- Escucha exclusiva en `127.0.0.1` y CORS con orígenes exactos.
- Redacción de credenciales, cookies, tokens y parámetros sensibles en registros.
- La prueba SSRF de integración debe pasar antes de afirmar protección completa.

## AC-10 — Aviso de uso

Resultado esperado:

- Antes de la primera descarga aparece el texto aprobado.
- Rechazarlo impide descargar, pero permite cerrar o revisar la aplicación.
- Aceptarlo guarda localmente la versión del aviso.
- Una nueva versión sustancial solicita aceptación otra vez.
- El aviso permanece disponible en **Acerca de**.

## Pruebas automáticas obligatorias

- Validación y normalización de URLs.
- Clasificación DNS/IP en IPv4 e IPv6.
- Sanitización y reserva de nombres.
- Contención de rutas y enlaces simbólicos.
- Máquina de estados y transiciones inválidas.
- Orden FIFO y avance tras fallo o cancelación.
- Traducción de errores técnicos a códigos estables.
- Redacción de registros.
- Persistencia y recuperación tras reinicio.
- Endpoints principales con dobles de `yt-dlp` y FFmpeg.
- Componentes y flujos esenciales del frontend.

## Definición de terminado del MVP

El MVP se considera terminado únicamente cuando:

- Todos los criterios AC-01 a AC-10 están en `PASS`.
- Las pruebas automáticas están en verde en una instalación limpia.
- No existen fallos conocidos de severidad crítica o alta.
- El backend y frontend solo son accesibles localmente.
- No se sobrescriben archivos ni quedan temporales tras operaciones correctas.
- La documentación describe el comportamiento real y las dependencias instalables.
- Una segunda instalación limpia puede reproducir el flujo siguiendo el README.
- Los resultados reales de YouTube y TikTok se verifican con contenido autorizado.

Un criterio sin ejecutar es `NOT RUN`, no aprobado. Una falta de URL autorizada o dependencia externa se registra como `BLOCKED`, no como fallo del producto.
