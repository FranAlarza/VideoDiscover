# Resultados de aceptación del MVP

## Estado actual

| Criterio | Estado | Evidencia pendiente |
|---|---|---|
| AC-01 YouTube MP4 | PASS | Verificado en la versión candidata local del 2026-07-20. |
| AC-02 TikTok MP4 | PASS | Verificado en la versión candidata local del 2026-07-20. |
| AC-03 Audio MP3 | PASS | MP3 a 192 kbps reproducible y sin temporales. |
| AC-04 Cola FIFO | PASS | Orden, exclusión de ejecución y avance verificados manualmente. |
| AC-05 Cancelación | PASS | Estado, limpieza y avance de cola verificados manualmente. |
| AC-06 Fallos controlados | PASS | Matriz funcional revisada por el responsable del entorno. |
| AC-07 Colisión de nombres | PASS | Archivos repetidos conservados con sufijos distintos. |
| AC-08 Reinicio y recuperación | PASS | Interrupción, cola y reintento verificados manualmente. |
| AC-09 Seguridad mínima | PASS | Suite automática y comprobaciones de integración revisadas. |
| AC-10 Aviso de uso | PASS | Rechazo, aceptación, persistencia y acceso verificados. |

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

## Ejecuciones registradas

### AC-01 — YouTube MP4

```text
Fecha: 2026-07-20
Versión: 302bf69 + corrección local de limpieza al arrancar
Plataforma: macOS en Apple Silicon
Entrada: vídeo público individual de YouTube autorizado por el responsable
Selección: MP4, 720p
Resultado observado: descarga completed; imagen y audio reproducibles y
sincronizados; Abrir archivo correcto; Mostrar en Finder selecciona el archivo;
workspace de la tarea eliminado.
Incidencia encontrada: existía un workspace huérfano de una ejecución anterior
interrumpida. Se añadió limpieza segura al arranque y se verificó la carpeta
temporal vacía después del reinicio.
Estado: PASS
```

### AC-02 — TikTok MP4

```text
Fecha: 2026-07-20
Versión: 302bf69 + corrección local de limpieza al arrancar
Plataforma: macOS en Apple Silicon
Entrada: vídeo público individual de TikTok autorizado por el responsable
Selección: MP4, mejor calidad disponible
Resultado observado: descarga completed; imagen y audio reproducibles y
sincronizados; Abrir archivo correcto; Mostrar en Finder selecciona el archivo;
sin temporales de la tarea.
Estado: PASS
```

### AC-03 — Audio MP3

```text
Fecha: 2026-07-20
Versión: 302bf69 + corrección local de limpieza al arrancar
Plataforma: macOS en Apple Silicon
Entrada: contenido público autorizado por el responsable
Selección: MP3, 192 kbps
Resultado observado: descarga completed; MP3 reproducible; historial muestra
MP3 y 192 kbps; sin copia temporal del vídeo ni workspace residual.
Estado: PASS
```

### AC-04 a AC-10 — Revisión final

```text
Fecha: 2026-07-20
Versión: 302bf69 + corrección local de limpieza al arrancar
Plataforma: macOS en Apple Silicon
Responsable de la prueba: propietario del entorno local
AC-04: una única ejecución activa, cola FIFO y avance correcto — PASS
AC-05: cancelación, ausencia de resultado parcial y limpieza — PASS
AC-06: casos de error controlado y continuidad del backend — PASS
AC-07: colisiones resueltas sin sobrescritura — PASS
AC-08: reinicio, interrupted, cola conservada y reintento — PASS
AC-09: controles mínimos y comprobaciones de integración — PASS
AC-10: aviso previo, rechazo, aceptación y persistencia — PASS
Declaración: el responsable del entorno confirma que ha revisado todos los
criterios y que los resultados observados son correctos.
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
