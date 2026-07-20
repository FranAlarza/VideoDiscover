# Fase 0 — Definición del MVP

## Propósito

Cerrar las decisiones de producto y los límites técnicos antes de instalar dependencias o comenzar la implementación.

## Tareas

### 0.1 Definir el usuario y el escenario

- [x] Confirmar que habrá un único usuario local.
- [x] Confirmar el sistema operativo prioritario para el primer paquete.
- [x] Definir la carpeta de descarga predeterminada.
- [x] Decidir si el MVP se inicia desde terminal o ya debe tener lanzador gráfico.

#### Decisiones aprobadas para 0.1

- Usuario: una única persona en su ordenador, sin cuentas ni perfiles.
- Plataforma inicial: macOS sobre Apple Silicon (`arm64`).
- Compatibilidad futura: evitar decisiones que impidan soportar Windows o Linux.
- Carpeta predeterminada: `~/Downloads/Video Downloader`.
- Configuración: la carpeta podrá cambiarse y la preferencia se guardará localmente.
- Desarrollo: frontend y backend se iniciarán desde VS Code o terminal.
- Distribución: el empaquetado con lanzador gráfico se abordará después de validar el núcleo.
- Red: los servicios locales escucharán únicamente en `127.0.0.1`.
- Conflictos de nombre: se conservará el archivo existente y se añadirá un sufijo numérico al nuevo.

### 0.2 Cerrar el alcance funcional

- [x] Confirmar YouTube y TikTok como plataformas iniciales.
- [x] Confirmar MP4 y MP3 como formatos de salida.
- [x] Definir las opciones de calidad que verá el usuario.
- [x] Confirmar una sola descarga activa.
- [x] Decidir qué datos aparecen antes de descargar.
- [x] Decidir qué acciones ofrece el historial.

La especificación aprobada y sus criterios verificables se encuentran en
[`functional-scope.md`](functional-scope.md).

### 0.3 Definir comportamiento y errores

- [x] Diseñar el flujo: pegar URL, analizar, configurar y descargar.
- [x] Enumerar estados de descarga y transiciones válidas.
- [x] Definir mensajes para URL inválida, contenido no disponible y fallo de FFmpeg.
- [x] Definir qué ocurre con archivos parciales al cancelar o fallar.
- [x] Definir la política cuando el archivo ya existe.

El contrato de comportamiento, los errores y sus criterios verificables se
encuentran en [`behavior-and-errors.md`](behavior-and-errors.md).

### 0.4 Acordar límites de seguridad y uso

- [x] Redactar el aviso de uso legítimo y responsabilidad del usuario.
- [x] Confirmar que no se admiten DRM, contenido privado ni controles de acceso.
- [x] Definir validación de URL y bloqueo de redes privadas.
- [x] Confirmar que backend y frontend solo escuchan en `127.0.0.1`.
- [x] Definir las rutas locales en las que la aplicación puede escribir.

Los límites, controles y criterios verificables se encuentran en
[`security-and-use.md`](security-and-use.md).

### 0.5 Validar decisiones técnicas

- [x] Confirmar Python, FastAPI, `yt-dlp`, FFmpeg y SQLite.
- [x] Confirmar React, TypeScript y Vite para la interfaz.
- [x] Decidir entre sondeo HTTP o eventos en tiempo real para el progreso.
- [x] Decidir si Tauri pertenece al MVP o a la fase posterior.
- [x] Establecer versiones mínimas de las herramientas.

La arquitectura, versiones y política de dependencias se encuentran en
[`technical-decisions.md`](technical-decisions.md).

### 0.6 Preparar criterios de aceptación

- [x] Seleccionar la política y las entradas requeridas para URLs de prueba autorizadas.
- [x] Definir una prueba manual completa para YouTube.
- [x] Definir una prueba manual completa para TikTok.
- [x] Definir una prueba de cancelación y una de fallo controlado.
- [x] Aprobar la definición de terminado del MVP.

La matriz, evidencias y puerta de aceptación se encuentran en
[`acceptance-criteria.md`](acceptance-criteria.md).

## Entregables

- Alcance aprobado y funciones excluidas documentadas.
- Flujo principal y estados acordados.
- Requisitos de seguridad aceptados.
- Stack y plataforma inicial confirmados.
- Criterios de aceptación reproducibles.

## Decisiones preliminares

| Tema | Propuesta inicial | Estado |
|---|---|---|
| Uso | Personal, para un único usuario local | Aprobado |
| Plataforma inicial | macOS Apple Silicon (`arm64`) | Aprobado |
| Destino inicial | `~/Downloads/Video Downloader` | Aprobado |
| Inicio durante desarrollo | VS Code o terminal | Aprobado |
| Plataformas | YouTube y TikTok | Aprobado |
| Salidas | Vídeo MP4 y audio MP3 | Aprobado |
| Concurrencia | Una activa y el resto en cola | Aprobado |
| Backend | Python 3.13 + FastAPI | Aprobado |
| Motor | yt-dlp + FFmpeg | Aprobado |
| Datos | SQLite + SQLAlchemy + Alembic | Aprobado |
| Progreso | Server-Sent Events (SSE) | Aprobado |
| Frontend | React + TypeScript + Vite | Aprobado |
| Escritorio | Tauri 2 después de validar el núcleo | Aprobado |

## Puerta de salida

La fase 0 queda cerrada. La fase 1 puede comenzar con la preparación del entorno y
el núcleo de análisis, respetando las especificaciones enlazadas en este documento.
