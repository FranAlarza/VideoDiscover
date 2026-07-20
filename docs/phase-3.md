# Fase 3 — Interfaz local

## Objetivo

Construir una interfaz React accesible y responsive sobre los contratos HTTP y
SSE ya verificados por el backend.

## 3.1 Inicialización de React, TypeScript y Vite

Estado: completado.

- [x] Crear el proyecto directamente en `frontend/`.
- [x] Fijar React 19.2 y generar `package-lock.json`.
- [x] Usar Node.js 24 y alinear sus tipos con esa línea.
- [x] Configurar TypeScript estricto sin `any` implícitos.
- [x] Configurar alias `@/` sin usar la opción obsoleta `baseUrl`.
- [x] Configurar Vite en `127.0.0.1:5173` con puerto estricto.
- [x] Añadir proxy de `/api` y `/health` hacia el backend local.
- [x] Configurar Vitest, jsdom y React Testing Library.
- [x] Configurar ESLint tipado y Prettier.
- [x] Crear una pantalla responsive con propósito y estado del backend.
- [x] Validar el contrato exacto de `GET /health`.
- [x] Cancelar la comprobación de salud al desmontar el componente.
- [x] Añadir foco visible y respeto por `prefers-reduced-motion`.

### Versiones resueltas principales

```text
Node.js 24.18.0
React 19.2.0
TypeScript 6.0.2
Vite 8.1.5
Vitest 4.1.10
ESLint 10.7.0
```

TypeScript 7 no se adoptó porque la línea actual de `typescript-eslint` requiere
una versión anterior a 6.1. La instalación no fuerza dependencias incompatibles.

### Evidencia

- Build de producción aprobado.
- Cuatro pruebas de interfaz aprobadas.
- ESLint tipado y Prettier aprobados.
- Auditoría npm: cero vulnerabilidades conocidas.
- Vite verificado en `127.0.0.1:5173`.
- `/health` atravesó el proxy y devolvió el contrato exacto de FastAPI.

## 3.2 Análisis de URL

Estado: completado.

- [x] Implementar el formulario de URL y su estado de análisis.
- [x] Consumir el contrato estable de `POST /api/media/inspect`.
- [x] Mostrar errores comprensibles y accesibles.
- [x] Presentar miniatura, plataforma, título, autor y duración disponibles.
- [x] Mostrar únicamente las calidades de vídeo informadas por el backend.
- [x] Permitir escoger vídeo o audio.

## 3.3 Creación de descargas desde la interfaz

Estado: implementado y verificado manualmente con descargas reales.

- [x] Consumir el contrato estable de `POST /api/downloads`.
- [x] Construir selecciones válidas para MP4 y MP3.
- [x] Ofrecer 128, 192 y 320 kbps, con 192 kbps como valor inicial.
- [x] Impedir solicitudes duplicadas mientras se crea la tarea.
- [x] Mostrar el estado inicial, formato y posición en cola.
- [x] Actualizar la tarjeta con eventos SSE del backend.
- [x] Mostrar progreso, fallo y archivo final cuando estén disponibles.
- [x] Traducir errores del backend a mensajes visibles.
- [x] Mostrar y persistir localmente la versión aceptada del aviso de uso.
- [x] Mantener el aviso disponible en **Acerca de**.
- [x] Cubrir el flujo con pruebas de interfaz y del cliente HTTP.
- [x] Arrancar `./scripts/dev.sh` con ejecutor real por defecto.
- [x] Verificar una descarga real iniciada íntegramente desde la interfaz.

## 3.4 Controles de descarga

Estado: implementado y verificado manualmente con una descarga real.

- [x] Cancelar tareas en cola, en descarga o en procesamiento desde la interfaz.
- [x] Deshabilitar la acción mientras la cancelación está en curso.
- [x] Reflejar inmediatamente la respuesta y sincronizar el estado final mediante SSE.
- [x] Ocultar la acción en estados terminales.
- [x] Mostrar los errores estables del backend sin perder la tarjeta actual.
- [x] Cubrir el cliente HTTP y la interacción principal con pruebas automatizadas.
- [x] Verificar una cancelación real y la limpieza de temporales.

## 3.5 Historial local

Estado: implementado y verificado manualmente.

- [x] Cargar las descargas persistidas al abrir la aplicación.
- [x] Mostrar estados de carga, vacío y error.
- [x] Ordenar desde la descarga más reciente y evitar duplicados por identificador.
- [x] Añadir nuevas tareas y actualizar las existentes mediante SSE.
- [x] Mantener progreso, resultado, fallo y cancelación independientes por tarjeta.
- [x] Adaptar la lista a títulos, nombres de archivo y pantallas estrechas.
- [x] Cubrir carga inicial, sincronización y acciones por tarea con pruebas.
- [x] Verificar persistencia, actualización y cancelación con varias descargas reales.

## 3.6 Reintentos manuales

Estado: implementado y verificado manualmente.

- [x] Consumir el contrato estable de `POST /api/downloads/{id}/retry`.
- [x] Mostrar **Reintentar** únicamente para descargas fallidas o interrumpidas.
- [x] Bloquear solicitudes duplicadas mientras se vuelve a analizar el contenido.
- [x] Reflejar el nuevo intento en la misma entrada y continuar mediante SSE.
- [x] Mantener errores y estados de reintento independientes por tarjeta.
- [x] Conservar la cancelación cuando la tarea vuelve a estar activa o en cola.
- [x] Cubrir el cliente HTTP y la interacción con pruebas automatizadas.
- [x] Verificar manualmente un reintento real hasta completarse.

## 3.7 Acciones sobre archivos completados

Estado: implementado y verificado manualmente en macOS.

- [x] Resolver el archivo final exclusivamente dentro de la carpeta autorizada.
- [x] Rechazar rutas manipuladas, archivos ausentes y enlaces que escapen del destino.
- [x] Exponer acciones para abrir el archivo y mostrarlo en Finder.
- [x] Ejecutar `/usr/bin/open` con argumentos separados y sin construir comandos de shell.
- [x] Mostrar acciones únicamente en descargas completadas con resultado.
- [x] Mantener carga y errores independientes por tarjeta.
- [x] Cubrir servicio, API, cliente HTTP e interfaz con pruebas automatizadas.
- [x] Verificar manualmente **Abrir archivo** y **Mostrar en Finder**.

## 3.8 Eliminación de entradas del historial

Estado: implementado y verificado manualmente.

- [x] Eliminar únicamente tareas en estado terminal.
- [x] Borrar la tarea y sus intentos persistidos sin tocar el archivo final.
- [x] Publicar la eliminación mediante SSE para todas las vistas abiertas.
- [x] Solicitar confirmación explícita desde la interfaz.
- [x] Mantener carga y errores independientes por tarjeta.
- [x] Cubrir repositorios, servicio, API, eventos y frontend con pruebas.
- [x] Verificar manualmente que la tarjeta desaparece y el archivo permanece.

## 3.9 Metadatos y progreso detallado

Estado: implementado y verificado manualmente.

- [x] Mostrar fecha de publicación y tamaño estimado cuando estén disponibles.
- [x] Ofrecer explícitamente **Mejor disponible** y enviar la mayor calidad analizada.
- [x] Mostrar bytes transferidos, tamaño total, velocidad y tiempo restante.
- [x] Representar el procesamiento sin porcentaje como progreso indeterminado.
- [x] Ocultar cualquier dato desconocido en lugar de inventar un valor.
- [x] Cubrir metadatos opcionales, selección y progreso con pruebas.
- [x] Verificar los datos disponibles durante una descarga real.
