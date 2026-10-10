# Planes y suscripciones

En **Planes → Crear plan**, elige cualquier nombre: Plan Prueba, Diario, Semanal, Mensual o el que necesites. Define días o meses naturales y/o GB. Los accesos rápidos proponen 1 día, 7 días, 1 mes y 3 meses; puedes escribir otra duración. Un campo vacío significa sin ese límite. Ambos vacíos crean un plan ilimitado explícito. La velocidad sigue siendo independiente por cliente.

Puedes asignar un plan al crear el cliente o desde **Clientes → Acciones → Plan, recargas y renovaciones**. Los clientes existentes conservan acceso sin cuota ni vencimiento hasta que les asignes uno. La instalación no contrata planes para jesus ni para otros clientes existentes.

## Calendario fijo

- **Añadir GB** suma saldo al contrato actual, conserva su consumo y no cambia la fecha de vencimiento. Si ya venció, la recarga no evita la suspensión por fecha.
- **Cambiar plan** sustituye el saldo por la cuota completa del plan elegido y empieza a contar ese saldo desde el consumo actual. Conserva el calendario y la periodicidad originales. Si el contrato ya venció, también hay que renovar. No suma el saldo anterior.
- **Renovar** después del vencimiento repone la cuota originalmente contratada, sin recargas anteriores, y avanza hasta la próxima fecha del calendario original. No cobra ni renueva automáticamente. Un plan solo de GB permite renovación en cualquier momento; esta reemplaza el saldo.
- **Cancelar suscripción** corta el acceso y permite contratar de nuevo. La contratación nueva establece otra fecha y periodicidad. Conserva el perfil y el historial.

Ejemplo: si vence el 15, comprar GB el 10 conserva el día 15. Si pagas el 20 después de vencer, renovar conserva el próximo día 15; no concede un mes desde el día 20. Para iniciar un nuevo mes desde el 20, cancela y contrata de nuevo. En planes mensuales iniciados el 31, febrero usa su último día y marzo vuelve al 31. Se conserva la hora UTC; la app presenta la fecha en la zona horaria del teléfono. Un día equivale a 24 horas.

Editar el catálogo afecta nuevas contrataciones, nunca reescribe contratos existentes. Archivar impide contratar ese plan de nuevo; mantiene contratos e historial. Para modificar las condiciones de un cliente usa sus acciones de suscripción. La app gestiona acceso y fechas; no procesa pagos ni emite facturas monetarias.

## Suspensión automática

Se descuenta la suma de bytes recibidos y enviados que reporta WireGuard para ese cliente: subida + descarga; 1 GB = 1 000 000 000 bytes. Si hay cuota y duración, se corta al alcanzar cualquiera de las dos. El servidor comprueba cada 5 segundos incluso con la APK cerrada. No es un corte por paquete: puede superar la cuota durante ese intervalo, más el tiempo de aplicación. No reconstruye tráfico que WireGuard perdió antes de una muestra o por modificaciones externas.

La suspensión retira el peer de WireGuard y de la configuración persistente sin reiniciar wg0, SSH ni las colas. Una recarga suficiente restaura un plan agotado mientras siga vigente. Renovar restaura un plan vencido. La suspensión manual se conserva: después de ajustar su plan debes reactivar manualmente al cliente si también lo habías suspendido tú. Reactivar no permite saltarse un vencimiento o cuota agotada.

Después de revocar y restaurar acceso, puede ser necesario apagar y encender el túnel en el cliente WireGuard para negociar una sesión nueva. Los perfiles se conservan; renovar claves sí requiere entregar un perfil nuevo.

Las suscripciones, saldo, ancla del calendario, consumo y eventos se guardan en SQLite en el VPS. El agente reevalúa vencimientos al iniciar. Durante un arranque, wg0 puede levantarse antes de que el agente vuelva a comprobar los planes; esta versión no promete bloqueo estricto durante ese intervalo ni si el agente está detenido. Deben mantenerse activos los servicios y atender las alertas.

## Validación

`backend/tests/test_plans.py` comprueba calendario mensual, ciclos perdidos, sumatoria de tráfico, recargas, suspensión manual, catálogo no retroactivo, cancelación, renovación, persistencia, rotación de claves suspendidas y reversión ante fallo.

`tools/verify_plans_live.py` prueba en Miami un peer temporal con tráfico WireGuard real: consumo, corte sin dashboard, recarga y reconexión, vencimiento acelerado únicamente en su contrato de prueba, renovación y persistencia al reiniciar el agente. Limpia sus recursos y comprueba los clientes previos, jesus, NAT y SSH. Requiere una terminal root privada; nunca publica perfiles o contraseñas.

Respaldo anterior a la migración: `/root/gestionvps-backups/before-plans-20261010T032722Z/`. Incluye código previo, configuración y copia consistente SQLite, junto con instrucciones de reversión. Contiene secretos y no debe publicarse. Una reversión tras nuevas contrataciones requiere revisar qué accesos y saldos se perderían.
