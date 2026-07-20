# Frontend

Interfaz local del Video Downloader construida con React 19.2, TypeScript 6 y
Vite 8. Requiere Node.js 24; otras líneas no forman parte del entorno aprobado.

## Desarrollo

Con el backend en `127.0.0.1:8000`:

```bash
npm install
npm run dev
```

La aplicación queda disponible en `http://127.0.0.1:5173`. El servidor de Vite
falla si ese puerto está ocupado y no escucha en interfaces de red externas.

## Verificación

```bash
npm run build
npm test
npm run lint
npm run format
```

El proxy de desarrollo permite consumir `/health` y `/api/*` sin introducir la
dirección del backend en componentes React.
