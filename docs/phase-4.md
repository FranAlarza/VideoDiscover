# Fase 4 — Configuración local y cierre del MVP

## 4.1 Persistencia de configuración

Estado: implementado como base interna y conectado al ejecutor.

- [x] Crear la tabla SQLite `settings` mediante una migración incremental.
- [x] Mantener actualizables las bases creadas con la migración inicial.
- [x] Implementar un repositorio tipado para `download_output_root`.
- [x] Resolver y persistir rutas absolutas sin exponerlas en contratos públicos.
- [x] Verificar que la preferencia se conserva usando una nueva instancia.
- [x] Crear y comprobar una carpeta escribible sin dejar archivos de prueba.
- [x] Rechazar rutas relativas, la raíz, archivos y el árbol temporal interno.
- [x] Bloquear cambios mientras existan descargas activas o en cola.
- [x] Persistir la ruta validada cuando todas las tareas sean terminales.
- [x] Aplicar la carpeta validada a descargas futuras.
- [x] Guardar internamente la carpeta original de cada archivo terminado.
- [x] Reconstruir la ubicación de resultados históricos al migrar.
- [x] Mantener «Abrir» y «Mostrar en Finder» ligados a la ubicación original.
- [x] Exponer la configuración mediante una API local validada.
- [x] Añadir selección nativa de carpeta en macOS y conectarla a la interfaz.

## 4.2 Cierre verificable del MVP

- [x] Añadir un comando único para las comprobaciones automáticas.
- [x] Crear un registro explícito para los resultados de aceptación.
- [x] Limpiar al arrancar workspaces huérfanos reconocibles tras una interrupción.
- [x] Ejecutar y registrar AC-01 a AC-10 sobre la versión candidata.
- [ ] Reproducir la instalación y el flujo en una segunda instalación limpia.
- [x] Confirmar que no quedan fallos conocidos críticos o altos.
