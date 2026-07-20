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

## 3.2 Siguiente entrega — Análisis de URL

La siguiente tarea implementará el formulario de URL, errores accesibles, estado
de análisis y tarjeta de metadatos con opciones de vídeo y audio disponibles.
