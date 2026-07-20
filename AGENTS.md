# Video Downloader — Guía de trabajo

## Objetivo

Construir una aplicación local de escritorio para analizar y descargar contenido audiovisual mediante una URL, únicamente cuando el usuario tenga derecho a hacerlo.

El MVP debe permitir analizar una URL pública compatible, elegir vídeo MP4 o audio MP3, seleccionar calidad, iniciar o cancelar la descarga, mostrar progreso y conservar un historial local.

## Alcance inicial

- Plataformas prioritarias: YouTube y TikTok.
- Ejecución exclusivamente local, enlazada a `127.0.0.1`.
- Una descarga activa simultánea.
- Las descargas adicionales permanecen en una cola FIFO.
- Vídeo MP4 y audio MP3 como únicas salidas expuestas en el MVP.
- Calidades de vídeo: mejor disponible, 2160p, 1440p, 1080p, 720p, 480p y 360p, mostrando solo las disponibles.
- Calidades de audio: 128, 192 y 320 kbps; 192 kbps es la predeterminada.
- Contenido público, sin DRM y sin autenticación.
- Motor de extracción: `yt-dlp`.
- Procesamiento multimedia: FFmpeg.
- Backend: Python 3.12+ y FastAPI.
- Persistencia: SQLite.
- Frontend: React, TypeScript y Vite.
- Empaquetado de escritorio posterior al MVP funcional.

## Fuera del MVP

- Eludir DRM, pagos, controles de acceso o restricciones técnicas.
- Descargar contenido privado o que requiera cookies.
- Listas de reproducción y descargas por lotes.
- Varias descargas simultáneas.
- Servicio público o acceso desde la red local.
- Aplicaciones móviles, nube y sincronización entre dispositivos.
- Actualizaciones automáticas.

## Reglas de implementación

- No implementar extractores propios mientras `yt-dlp` cubra el caso de uso.
- No construir comandos de shell concatenando entradas del usuario.
- Aceptar únicamente URLs `http` y `https` y bloquear destinos locales o privados.
- Impedir escrituras fuera del directorio de descarga autorizado.
- No guardar credenciales, cookies ni tokens en el MVP.
- Aplicar íntegramente los controles definidos en `docs/security-and-use.md`.
- Respetar las versiones, límites entre componentes y política de dependencias de `docs/technical-decisions.md`.
- Verificar cada entrega contra `docs/acceptance-criteria.md` y conservar la evidencia indicada.
- Mantener separados análisis, descarga, persistencia y API.
- Añadir pruebas para validación de URLs, rutas de salida y transiciones de estado.
- Los errores técnicos deben convertirse en mensajes comprensibles para el usuario.
- No añadir funciones fuera del alcance sin documentar primero la decisión.

## Flujo de trabajo

1. Consultar `docs/phase-0.md` antes de cambiar el alcance.
2. Consultar `docs/functional-scope.md` antes de implementar comportamiento funcional.
3. Consultar `docs/behavior-and-errors.md` para estados, transiciones, cancelación y errores.
4. Consultar `docs/security-and-use.md` antes de implementar red, procesos o archivos.
5. Consultar `docs/technical-decisions.md` antes de añadir o actualizar dependencias.
6. Consultar `docs/acceptance-criteria.md` para determinar qué evidencia requiere cada entrega.
7. Implementar en incrementos pequeños y verificables.
8. Añadir o actualizar pruebas junto con cada comportamiento nuevo.
9. Ejecutar las pruebas afectadas antes de dar una tarea por terminada.
10. Mantener `README.md` y la documentación alineados con el comportamiento real.

## Criterio de finalización del MVP

El MVP termina cuando una persona puede pegar una URL compatible, inspeccionar sus metadatos, escoger MP4 o MP3 y una calidad, descargar con progreso y cancelación, encontrar el archivo en una carpeta configurable y consultar el historial, todo desde la interfaz local.
