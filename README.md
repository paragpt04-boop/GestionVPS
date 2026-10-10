# GestionVPS · Miami

Panel Android nativo (Kotlin, Compose, Android 8.0+) y API HTTPS para administrar WireGuard. El repositorio nunca contiene claves privadas ni contraseñas. La APK no utiliza SSH.

## Arquitectura

- `android/`: interfaz en español, dashboard con consulta cada 15 s, clientes, planes, recargas, renovaciones, velocidades, suspensión, claves, exportación `.conf`, QR local, auditoría y diagnósticos. Sesiones en memoria y pantalla protegida contra capturas.
- `backend/api.py`: FastAPI sin privilegios, HTTPS en 8443, credenciales administrativas independientes, contraseñas scrypt, tokens opacos con caducidad de una hora, cierre de sesión y limitación persistente de intentos.
- `backend/agent.py`: agente local privilegiado accesible solo por socket Unix al usuario de la API. Validación estricta, comandos sin shell, SQLite, muestreo y aplicación de planes cada 5 s, respaldo y journal de reversión antes de modificar WireGuard.
- `backend/plans.py`: catálogo y contratos persistentes, GB de subida + descarga, días o meses naturales, suspensión automática y calendario fijo de facturación. Ver [reglas y ejemplos](docs/PLANS.md).
- `backend/qos.py`: HTB por IP en wg0 e ifb-wg0. Acepta el formato original de una IP por línea (2/1 Mbps) y el extendido `IP descarga subida`. Actualiza clases sin destruir toda la cola.
- SQLite se eligió para un solo VPS y un escritor serializado, con menos consumo y administración que PostgreSQL. No ejecutar múltiples agentes ni trabajadores que escriban directamente en sus archivos.

## Compilación

JDK 17, Android SDK 35 y Gradle 8.11.1. Desde `android/`: `gradle :app:assembleDebug :app:lintDebug`. GitHub Actions instala las mismas versiones y publica un APK de prueba instalable. La firma debug de CI no es una identidad permanente de producción: para actualizaciones estables se debe configurar un keystore privado de release, fuera del repositorio y en secretos de CI. No se promete identidad binaria entre builds ni compatibilidad con todos los fabricantes sin pruebas en dispositivos.

## Instalación del servidor

Consultar `docs/OPERATIONS.md`. La instalación requiere revisar y respaldar el servidor existente. No ejecutar en otro VPS. API: `https://107.178.51.31:8443`. El certificado público de la CA de esta instalación se incorpora en `android/app/src/main/res/raw/miami_ca.crt`; la CA privada permanece protegida en el VPS. Nunca desactivar la validación TLS o el hostname.

## Pruebas

`cd backend && python -m unittest discover -s tests -v`.
Las pruebas reales de integración deben usar un cliente temporal y comprobar que el peer, perfil y límites de jesus no cambian. No ejecutar reinicios automáticos en producción. Estado y resultados concretos en `docs/VALIDATION.md`.

## Límites conocidos

- Los handshakes recientes estiman actividad; WireGuard no mantiene un concepto de sesión conectada.
- Bytes recibidos por el servidor = subida del cliente; enviados = descarga. Un GB son 1 000 000 000 bytes. Los planes limitan por GB, duración o ambos; clientes sin plan siguen sin cuota. La aplicación del corte se comprueba cada 5 s, no por paquete.
- Historial diario UTC desde la instalación. La primera muestra incluye los contadores actuales de WireGuard; no reconstruye fechas anteriores. Puede perderse tráfico entre una muestra y un reinicio o eliminación externa del peer.
- Un único administrador en esta versión. Alertas dentro del panel, sin notificaciones push en segundo plano.
- Perfiles IPv4 como el cliente original. No se anuncia soporte de túnel IPv6 ni bloqueo de fugas IPv6 del dispositivo.
- No editar WireGuard/QoS simultáneamente fuera del panel. Una configuración externa inesperada requiere revisión y nueva importación controlada.
- La revocación invalida la clave en el servidor; las copias del perfil que ya se hayan entregado no se pueden borrar remotamente.
