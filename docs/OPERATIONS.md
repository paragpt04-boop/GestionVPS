# Operación segura

## Inspección inicial, 2026-10-09

Ubuntu 24.04, interfaz ens18, wg0 10.5.0.1/24, UDP 51820, forwarding habilitado. NAT MASQUERADE existente por ens18. SSH escucha en 443 y 22. Cliente jesus 10.5.0.2. QoS verificada con contadores en clases 1:2 (2 Mbps) y 2:2 (1 Mbps), filtros por destino/origen y redirección ingress a ifb-wg0. wg-qos activo; wg-quick@wg0 habilitado pero inactivo con interfaz levantada. No se corrigió mediante reinicio a ciegas.

Respaldo original protegido: `/root/gestionvps-backups/20261009T185943Z/` con configuración, runtime, NAT y colas. Contiene secretos; no descargar a repositorios ni adjuntarlo a incidencias.

## Instalar

1. Revisar diferencias entre servidor real y código; asegurar acceso SSH alternativo.
2. Crear respaldo protegido de `/etc/wireguard`, script QoS, unidades systemd, sysctl y reglas NAT. Guardar también el estado runtime con `wg showconf`, siempre en archivo root 600.
3. Copiar checkout revisado a `/opt/gestionvps`. Crear CA privada protegida y certificado de servidor con SAN IP correcta; distribuir únicamente su certificado público. Guardar server.crt/key en `/etc/gestionvps`.
4. Con python3-venv disponible, ejecutar `bash /opt/gestionvps/deploy/install.sh`. No modifica SSH, NAT, sysctl ni la unidad wg-quick. Los nuevos servicios se habilitan al arranque.
5. Consultar credenciales solo desde una terminal privada: `sudo cat /root/gestionvps-admin.txt`. No enviarlas por chat ni ponerlas en la app como valores predeterminados.
6. Revisar acceso HTTPS y operaciones con cliente temporal. Repartir el certificado de CA público mediante la APK.

## Reversión

Detener `gestionvps-api` y `gestionvps-agent` antes de restaurar. Conservar `/var/lib/gestionvps-agent` y `/var/lib/gestionvps-api` con permisos root/servicio, nunca públicos. Restaurar únicamente archivos necesarios desde el respaldo, primero inspeccionando su índice. Para el estado inicial: restaurar wg0.conf, qos-clientes.txt, script QoS y unidad wg-qos. Restaurar runtime con `wg syncconf wg0 /root/gestionvps-backups/20261009T185943Z/wg-runtime.txt`, y ejecutar el script QoS restaurado. Esto revoca clientes creados después del respaldo: revisar antes de hacerlo. No restaurar toda la tabla iptables sin comparar las reglas actuales. No reiniciar SSH.

Cada operación del agente guarda su propio respaldo bajo `/var/lib/gestionvps-agent/backups/` y un journal de recuperación. Estos respaldos contienen secretos, requieren almacenamiento protegido y política de retención. Si una reversión falla, detener escrituras y recuperar manualmente. No borrar un pending.json sin revisar.

## Prueba de reinicio completada

Registrar servicios, peer jesus y claves mediante hashes (no valores), reglas NAT, clases y filtros. Coordinar ventana con el administrador. Reiniciar únicamente Miami. Al volver, comprobar SSH 443, wg0, wg-qos, agente, API, rutas y forwarding, handshake de un cliente real, IP de salida y velocidades en ambas direcciones. Que una unidad esté habilitada no demuestra que haya sobrevivido un reinicio.

Se completó esta comprobación con autorización el 9 de octubre de 2026; ver VALIDATION.md. La ampliación de planes se probó con reinicio del agente, sin reiniciar otra vez el VPS. Para sus reglas, migración y respaldo específico ver PLANS.md.

## Certificados y credenciales

La CA privada nunca sale del VPS. Renovar el certificado del servidor antes de su vencimiento con la misma CA; distribuir una actualización de la APK antes de cambiar la CA. Respaldar las claves de firma release por separado. La contraseña SSH compartida previamente debe cambiarse desde una terminal privada; no se usa en esta aplicación.
