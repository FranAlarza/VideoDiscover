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

Estado: implementado; pendiente de prueba manual real tras conectar el entorno.

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
- [ ] Verificar una descarga real iniciada íntegramente desde la interfaz.

## 3.4 Siguiente entrega — Controles de descarga

La siguiente tarea añadirá acciones sobre descargas desde la interfaz,
empezando por cancelar una tarea activa o en cola y reflejar el resultado en la
misma tarjeta.
