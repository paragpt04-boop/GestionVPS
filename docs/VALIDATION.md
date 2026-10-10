# Validación · 9 de octubre de 2026

## Servidor real de Miami

- Acceso SSH con clave, verificación de huella y respaldo protegido antes de cambios.
- Pruebas del backend: nombres, límites, archivos QoS originales/extendidos, contadores que se reinician, rollback inyectando un fallo y persistencia de cambios. La ampliación de planes pasa 23 ejecuciones unitarias (incluye regresiones heredadas).
- API HTTPS con verificación de CA y SAN de IP desde dentro y fuera del VPS. Acceso sin token rechazado. Login y revocación de sesión probados.
- Cliente temporal: alta, nombre elegido, exportación de perfil, cambio de velocidades, suspensión, reactivación, renovación de claves y eliminación probadas en el servidor real.
- Perfil original de jesus y clave pública del servidor comparados antes/después; sin cambios. NAT y SSH por 443 preservados.
- Túnel WireGuard real desde namespace temporal, con handshake y ping. Medición TCP: 2.916 Mbps de descarga y 1.927 Mbps de subida con límites 3/2 Mbps.
- Primera prueba de reinicio detectó que ifb-wg0 nace con fq_codel. Se corrigió la inicialización de esa cola; no se aceptó como validación exitosa.
- Segundo reinicio: nuevo boot ID, hashes de configuración y perfil jesus iguales, wg-quick@wg0, wg-qos, gestionvps-agent y gestionvps-api activos y habilitados. NAT, forwarding, wg0 10.5.0.1 y límites 2/1 de jesus comprobados.
- Túnel y QoS repetidos después del reinicio: 2.936 Mbps de descarga y 1.926 Mbps de subida para límites 3/2 Mbps.
- Clientes y namespaces temporales eliminados tras las pruebas. Estas mediciones prueban el shaping del VPS; no sustituyen una prueba de Fast.com desde la red física del usuario.

## Android

Compilación y pruebas de dispositivo en curso. Consultar las ejecuciones de GitHub Actions y los artefactos publicados; no considerar un APK validado hasta que la ejecución correspondiente termine correctamente. Las pruebas no equivalen a compatibilidad con todos los modelos Android.

## Planes, 10 de octubre de 2026 UTC

- Respaldo protegido previo a migración v3, sin asignar planes a los cuatro clientes existentes.
- Tráfico cifrado real de subida y descarga para un cliente temporal con 0.002 GB. El muestreador retiró el peer al consumir el saldo, sin abrir el dashboard para provocar el corte.
- Recarga, conservación de fecha, reconexión real y ping correctos. Se reinició el túnel de prueba para renegociar sus claves de sesión después de la revocación.
- Vencimiento acelerado solo para el contrato temporal: retirada automática del peer, renovación y ping posteriores correctos.
- Reinicio únicamente del agente: contrato, saldo, calendario e historial persistentes.
- Limpieza del cliente, plan y namespace temporales; IDs de los cuatro clientes previos iguales, perfil jesus sin cambios, NAT y SSH 443 preservados.
- Esta comprobación no simula un nuevo reinicio completo del VPS ni un corte por paquete. La ventana de muestreo es de 5 segundos.
