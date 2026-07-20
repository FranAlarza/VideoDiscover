# Seguridad y límites de uso del MVP

## Principio general

La aplicación es una herramienta local para contenido propio, autorizado, de dominio público o cuya licencia permita descargarlo. No determina por sí misma si el usuario posee los derechos necesarios y no debe presentarse como una forma de eludir las condiciones de una plataforma.

## Aviso visible

La interfaz mostrará antes de la primera descarga y mantendrá accesible en **Acerca de** el siguiente aviso:

> Descarga únicamente contenido propio o que tengas derecho a guardar. Esta aplicación no permite eludir DRM, pagos, autenticación ni otros controles de acceso. Tú eres responsable de respetar los derechos de autor, las licencias aplicables y las condiciones de cada plataforma.

La aceptación se guardará localmente con la versión del texto. Un cambio sustancial del aviso requerirá una nueva aceptación. No se enviará este dato fuera del dispositivo.

## Contenido fuera de alcance

El MVP no debe intentar superar ni proporcionar instrucciones para superar:

- DRM o cifrado destinado a controlar el acceso.
- Paywalls, suscripciones o compras.
- Vídeos privados o restringidos a una cuenta.
- Inicio de sesión, cookies de sesión o verificación de edad.
- Bloqueos geográficos, CAPTCHA o medidas anti-bot.
- URLs firmadas obtenidas mediante credenciales ajenas al flujo público.

Cuando se detecte uno de estos casos, la operación termina con el error estable correspondiente definido en `behavior-and-errors.md`.

## Superficie de red

- Backend y frontend escuchan exclusivamente en `127.0.0.1`.
- No se utiliza `0.0.0.0`, una IP de LAN ni una interfaz pública.
- El backend no confía en cabeceras de proxy para decidir el origen del cliente.
- CORS permite únicamente los orígenes locales exactos usados por el frontend durante desarrollo.
- No se habilita documentación interactiva de la API en una distribución final salvo necesidad justificada.
- El MVP no acepta webhooks ni solicitudes entrantes desde Internet.

## Validación de la URL de entrada

La validación se realiza antes de consultar metadatos y antes de iniciar una descarga:

1. El valor debe ser una URL absoluta y tener esquema `http` o `https`.
2. Se rechazan usuario y contraseña embebidos en la URL.
3. El nombre de host se normaliza mediante IDNA y se compara sin distinguir mayúsculas.
4. El puerto, si está presente, debe ser válido; no se infiere confianza por usar 80 o 443.
5. La plataforma debe corresponder a los dominios oficiales admitidos de YouTube o TikTok, incluyendo únicamente sus subdominios necesarios y variantes documentadas.
6. Se resuelven todos los registros DNS disponibles y se rechaza el destino si cualquiera apunta a una dirección no pública.
7. Se aplica la misma validación cuando una redirección cambia de host.
8. Se limita el número de redirecciones y se detectan bucles.

Nunca se comprueba un dominio mediante coincidencias de texto como `endswith("youtube.com")` sin exigir antes el límite de etiqueta DNS; `youtube.com.example.org` no pertenece a YouTube.

## Destinos de red bloqueados

Se rechazan explícitamente:

- `localhost` y nombres equivalentes.
- Loopback IPv4 e IPv6.
- Redes privadas.
- Link-local y direcciones autoconfiguradas.
- Multicast, broadcast y direcciones sin especificar.
- Rangos reservados, de documentación o de uso especial.
- Hosts resueltos por `/etc/hosts` hacia cualquiera de esos rangos.
- Representaciones alternativas de IP diseñadas para evitar la validación.

La decisión se toma con las utilidades de clasificación de IP de la biblioteca estándar, no con una lista parcial escrita a mano. Tanto IPv4 como IPv6 son obligatorios.

## DNS y redirecciones

Validar una URL una sola vez no evita DNS rebinding ni una redirección posterior a la red local. La implementación debe:

- Validar todos los resultados DNS antes de iniciar el acceso.
- Volver a validar cada cambio de host conocido por la aplicación.
- Mantener una lista permitida de plataformas de entrada, separada de los hosts multimedia que use internamente el extractor.
- No exponer al usuario una función genérica para descargar una URL directa arbitraria.

Si la integración elegida no permite observar de forma fiable las redirecciones internas de `yt-dlp`, esa limitación debe registrarse como riesgo conocido antes de implementar. No se afirmará que existe protección completa contra SSRF sin una prueba de integración.

## Procesos externos

- Se prefiere la API Python de `yt-dlp`.
- Si es necesario crear procesos, se pasan argumentos como una lista y nunca mediante una cadena interpretada por un shell.
- No se usa `shell=True`.
- Las rutas y opciones procedentes del usuario no pueden convertirse en opciones adicionales del proceso.
- Cada proceso queda asociado a una tarea para poder cancelarlo sin afectar trabajos ajenos.
- Los registros eliminan cookies, tokens, cabeceras y parámetros sensibles antes de persistirlos.

## Directorios autorizados en macOS

La aplicación solo escribe en:

- Descargas: `~/Downloads/Video Downloader`, o una carpeta elegida explícitamente por el usuario.
- Datos: `~/Library/Application Support/Video Downloader`.
- Caché: `~/Library/Caches/Video Downloader`.
- Temporales: un subdirectorio único creado mediante la API segura del sistema.

Durante desarrollo se permite `downloads/` dentro del repositorio como destino de pruebas.

## Validación de rutas

- Las rutas configuradas se expanden y resuelven de forma canónica antes de usarse.
- El nombre derivado del vídeo se trata como un nombre, nunca como una ruta.
- Se eliminan separadores, componentes `.` y `..`, bytes nulos y caracteres incompatibles.
- Tras resolver el destino final, se comprueba que siga contenido en la raíz autorizada.
- Se contemplan enlaces simbólicos: la ruta resuelta no puede escapar de la raíz.
- Se usan permisos mínimos y no se hacen ejecutables los archivos descargados.
- Un archivo existente nunca se sobrescribe.
- Los temporales se crean con nombres impredecibles y quedan asociados a su tarea.

Abrir un archivo o mostrarlo en Finder solo se permite para rutas finales registradas y validadas como pertenecientes a una descarga completada.

## Datos locales

- SQLite no almacena credenciales ni cookies.
- Solo se conserva la información necesaria para configuración, cola e historial.
- Las URLs pueden contener parámetros sensibles; antes de mostrarlas o registrarlas se eliminarán credenciales y se evaluará ocultar la cadena de consulta.
- El usuario podrá eliminar entradas del historial sin borrar el archivo descargado.
- No existe telemetría ni envío de diagnósticos en el MVP.

## Riesgos aceptados del MVP

- Las plataformas y sus hosts auxiliares pueden cambiar y exigir una actualización de la lista permitida o de `yt-dlp`.
- La disponibilidad pública de un contenido no demuestra que el usuario tenga derecho a descargarlo.
- Un proceso multimedia trabaja con datos externos potencialmente malformados; las dependencias deben mantenerse actualizadas.
- La aplicación local no protege frente a una cuenta del sistema ya comprometida.

## Criterios de aceptación de la tarea 0.4

- El aviso aparece antes de la primera descarga y su versión aceptada se guarda localmente.
- Solo se aceptan URLs HTTP/HTTPS de las plataformas aprobadas.
- Se rechazan credenciales embebidas y destinos no públicos en IPv4 e IPv6.
- Las redirecciones observables se validan de nuevo.
- Los servicios solo escuchan en `127.0.0.1` y CORS usa orígenes exactos.
- Ninguna entrada del usuario se ejecuta mediante un shell.
- Una ruta o enlace simbólico no puede escapar de los directorios autorizados.
- Cancelar o limpiar una tarea no afecta archivos ajenos.
- Los registros no contienen credenciales, cookies ni tokens.
- Existen pruebas unitarias para URL, DNS/IP, rutas, nombres y redacción de registros, además de una prueba de integración SSRF antes de declarar completa la protección.
