# Comportamiento y errores del MVP

## Flujo principal

1. El usuario pega una URL y pulsa **Analizar**.
2. La aplicación deshabilita temporalmente esa acción para evitar solicitudes duplicadas.
3. Se validan URL y plataforma antes de invocar `yt-dlp`.
4. Se consultan y presentan los metadatos y opciones disponibles.
5. El usuario elige vídeo o audio, calidad y pulsa **Descargar**.
6. La tarea comienza si no existe otra activa; en caso contrario entra en la cola FIFO.
7. La interfaz muestra estado y progreso y permite cancelar.
8. La descarga no se considera completada hasta finalizar el procesamiento de FFmpeg y existir el archivo final.
9. Al completar se ofrecen **Abrir archivo** y **Mostrar en Finder**.
10. El resultado se conserva en el historial.

## Estados

| Estado | Significado |
|---|---|
| `queued` | Espera su turno en la cola |
| `downloading` | `yt-dlp` está obteniendo el contenido |
| `processing` | FFmpeg está combinando o convirtiendo pistas |
| `completed` | El archivo final se creó correctamente |
| `failed` | La operación terminó por un error |
| `cancelled` | El usuario canceló la operación |
| `interrupted` | La aplicación se cerró durante la operación |

### Transiciones permitidas

- `queued` → `downloading` o `cancelled`.
- `downloading` → `processing`, `completed`, `failed`, `cancelled` o `interrupted`.
- `processing` → `completed`, `failed`, `cancelled` o `interrupted`.
- `completed`, `failed`, `cancelled` e `interrupted` son estados terminales de esa ejecución.
- Reintentar crea una ejecución nueva; no modifica un estado terminal anterior.

Cuando una salida no necesita procesamiento adicional, `downloading` puede pasar directamente a `completed`.

## Recuperación al arrancar

- Las tareas `queued` se recuperan manteniendo su orden.
- Las tareas persistidas como `downloading` o `processing` pasan a `interrupted`.
- Una tarea `interrupted` puede reintentarse manualmente.
- El MVP no reanuda automáticamente archivos parciales.

## Progreso

Durante `downloading`, la interfaz mostrará cuando estén disponibles:

- Porcentaje.
- Bytes descargados y tamaño total.
- Velocidad.
- Tiempo restante estimado.

Durante `processing` se mostrará un indicador indeterminado y el texto **Procesando archivo** si no existe un porcentaje fiable. Los valores desconocidos se ocultan; nunca se inventan ni se representan como cero.

## Cancelación y temporales

- Cancelar no requiere confirmación adicional.
- Se detienen el trabajo de `yt-dlp` y cualquier proceso FFmpeg perteneciente a la tarea.
- Se eliminan únicamente los `.part`, `.ytdl` y archivos intermedios registrados para esa ejecución.
- Nunca se elimina un archivo preexistente ni un archivo ajeno a la tarea.
- Un fallo de limpieza se registra y comunica, pero no bloquea el avance de la cola.
- Tras cancelar o fallar, comienza la siguiente tarea pendiente.
- La cancelación durante `processing` puede permanecer brevemente en curso mientras FFmpeg termina y se limpian los temporales.

## Colisiones de nombres

Los archivos existentes nunca se sobrescriben. Después de sanear el nombre y conservar la extensión, se añade el primer sufijo numérico libre:

```text
Mi vídeo.mp4
Mi vídeo (1).mp4
Mi vídeo (2).mp4
```

La disponibilidad se comprueba inmediatamente antes de reservar la salida. Temporales y archivo final usan un identificador interno de tarea para impedir colisiones entre ejecuciones.

## Reintentos

- No hay reintentos automáticos de una descarga completa.
- Se permiten los reintentos internos limitados de fragmentos que gestione `yt-dlp`.
- `failed` e `interrupted` ofrecen una acción manual **Reintentar**.
- Antes de reintentar se analiza otra vez la URL, porque los formatos pueden haber cambiado.
- El nuevo intento queda asociado a la entrada original para conservar la trazabilidad.

## Errores visibles

| Código interno | Situación | Mensaje para el usuario | Acción sugerida |
|---|---|---|---|
| `empty_url` | URL vacía | Introduce una URL. | Volver al campo |
| `invalid_url` | URL mal formada | La dirección introducida no es válida. | Corregir URL |
| `url_too_long` | URL por encima del límite | La dirección introducida es demasiado larga. | Usar una URL normal |
| `unsupported_scheme` | Protocolo distinto de HTTP/HTTPS | Solo se admiten direcciones HTTP o HTTPS. | Corregir URL |
| `embedded_credentials` | Credenciales incluidas en la URL | La dirección no puede incluir credenciales. | Usar una URL pública |
| `unsupported_platform` | Plataforma fuera del MVP | Esta plataforma no está soportada en el MVP. | Usar otra URL |
| `playlist_not_supported` | La URL representa una lista | Las listas de reproducción todavía no están soportadas. | Usar la URL de un vídeo |
| `invalid_media_url` | No identifica un vídeo individual | La dirección no corresponde a un vídeo individual válido. | Usar el enlace del vídeo |
| `blocked_network_target` | Destino DNS/IP no público | La dirección apunta a un destino de red no permitido. | Usar una URL pública oficial |
| `dns_resolution_failed` | DNS no verificable | No se ha podido verificar el destino de la dirección. | Reintentar |
| `redirect_not_allowed` | Redirección fuera de política | El enlace redirige a un destino no permitido. | Usar la URL canónica |
| `too_many_redirects` | Supera el límite de redirecciones | El enlace contiene demasiadas redirecciones. | Usar la URL canónica |
| `redirect_loop` | Bucle de redirecciones | El enlace contiene un bucle de redirecciones. | Usar la URL canónica |
| `short_link_unresolved` | Enlace corto no resoluble | No se ha podido resolver el enlace corto. | Reintentar o usar la URL canónica |
| `private_media` | Contenido privado o con login | Este contenido es privado o requiere iniciar sesión. | Sin reintento directo |
| `media_unavailable` | Eliminado o no disponible | El contenido ya no está disponible. | Sin reintento directo |
| `region_restricted` | Bloqueo geográfico | Este contenido no está disponible desde tu ubicación. | Sin reintento directo |
| `age_restricted` | Requiere verificación | Este contenido requiere una verificación no disponible en el MVP. | Sin reintento directo |
| `drm_protected` | DRM detectado | El contenido está protegido y no puede descargarse. | Sin reintento directo |
| `ffmpeg_missing` | FFmpeg no está disponible | FFmpeg no está instalado o no se encuentra. | Mostrar ayuda de instalación |
| `ffmpeg_incompatible` | FFmpeg está fuera de la línea admitida | La versión instalada de FFmpeg no es compatible. | Actualizar FFmpeg |
| `ffprobe_missing` | ffprobe no está disponible | ffprobe no está instalado o no se encuentra. | Mostrar ayuda de instalación |
| `ffprobe_incompatible` | ffprobe está fuera de la línea admitida | La versión instalada de ffprobe no es compatible. | Actualizar FFmpeg |
| `node_missing` | Node.js no está disponible | Node.js no está instalado o no se encuentra. | Mostrar ayuda de instalación |
| `node_incompatible` | Node.js está fuera de la línea admitida | La versión instalada de Node.js no es compatible. | Instalar Node.js 24 LTS |
| `yt_dlp_missing` | yt-dlp no está disponible | El motor de descarga no está instalado. | Reparar instalación |
| `yt_dlp_incompatible` | yt-dlp no es compatible | El motor de descarga debe actualizarse. | Actualizar dependencias |
| `format_unavailable` | Cambió la oferta de formatos | La calidad seleccionada ya no está disponible. | Analizar otra vez |
| `disk_full` | Espacio insuficiente | No hay suficiente espacio en el disco. | Liberar espacio |
| `output_not_writable` | Sin permisos de escritura | No se puede escribir en la carpeta seleccionada. | Cambiar carpeta |
| `network_error` | Conexión interrumpida | La conexión se interrumpió durante la descarga. | Reintentar |
| `inspection_timeout` | El extractor supera el límite | El análisis ha superado el tiempo permitido. | Reintentar |
| `inspection_unavailable` | No se puede iniciar el extractor | El servicio de análisis no está disponible. | Revisar dependencias |
| `temporarily_blocked` | Rechazo temporal de plataforma | La plataforma ha rechazado temporalmente la solicitud. | Reintentar más tarde |
| `cleanup_failed` | Quedaron temporales propios | No se pudieron eliminar todos los archivos temporales. | Mostrar ubicación |
| `unknown_error` | Error no clasificado | No se pudo completar la descarga. | Reintentar o consultar registro |

El registro técnico puede conservar el detalle original, pero nunca debe mostrar credenciales, cookies, tokens o información sensible en la interfaz.

## Criterios de aceptación de la tarea 0.3

- Cada ejecución siempre tiene uno de los estados definidos.
- Solo se aceptan las transiciones documentadas.
- `completed` implica que el archivo final existe y FFmpeg terminó correctamente.
- Un dato de progreso desconocido no se inventa.
- Cancelar solo elimina temporales registrados para esa ejecución.
- Un fallo o cancelación no bloquea la siguiente tarea de la cola.
- Al reiniciar, las operaciones activas anteriores quedan `interrupted`.
- Ningún archivo existente se sobrescribe.
- Cada error conocido se traduce a un código estable y un mensaje comprensible.
- Reintentar vuelve a analizar los formatos y crea una ejecución nueva.
