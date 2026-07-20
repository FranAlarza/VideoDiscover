# Resultados de aceptación del MVP

## Estado actual

| Criterio | Estado | Evidencia pendiente |
|---|---|---|
| AC-01 YouTube MP4 | NOT RUN | Repetir el flujo final desde la interfaz y registrar reproducción y Finder. |
| AC-02 TikTok MP4 | NOT RUN | Repetir el flujo final desde la interfaz y registrar reproducción y Finder. |
| AC-03 Audio MP3 | NOT RUN | Descargar a 192 kbps y comprobar reproducción. |
| AC-04 Cola FIFO | NOT RUN | Crear tres tareas reales y registrar el orden observado. |
| AC-05 Cancelación | NOT RUN | Cancelar una descarga real y verificar limpieza. |
| AC-06 Fallos controlados | NOT RUN | Completar la matriz manual complementaria. |
| AC-07 Colisión de nombres | NOT RUN | Descargar dos veces el mismo contenido. |
| AC-08 Reinicio y recuperación | NOT RUN | Reiniciar con una tarea activa y otra pendiente. |
| AC-09 Seguridad mínima | NOT RUN | Ejecutar suite automática y prueba SSRF de integración. |
| AC-10 Aviso de uso | NOT RUN | Verificar rechazo, aceptación y persistencia en navegador. |

`NOT RUN` significa que todavía no se ha ejecutado la comprobación final sobre la
versión candidata. Las pruebas realizadas durante el desarrollo no se convierten
retroactivamente en una aceptación formal sin registrar su contexto.

## Comprobación automática

Desde la raíz del proyecto:

```bash
./scripts/check.sh
```

Registrar para cada ejecución:

```text
Fecha:
Commit:
macOS:
Apple Silicon:
Python:
yt-dlp:
FFmpeg:
Node.js:
Backend tests:
Frontend tests:
Resultado: PASS | FAIL | BLOCKED
Notas:
```

## Plantilla de prueba manual

Copiar una sección por cada criterio ejecutado. No guardar URLs completas,
cookies, tokens ni parámetros sensibles.

```text
Criterio:
Fecha:
Commit:
Entrada autorizada (identificador no sensible):
Resultado esperado:
Resultado observado:
Estado: PASS | FAIL | BLOCKED | NOT RUN
Evidencia local:
Notas:
```
