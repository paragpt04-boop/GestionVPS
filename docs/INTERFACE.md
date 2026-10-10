# Interfaz 0.3.0

La lista de clientes muestra el estado junto al menú de tres puntos:

- **Activo ahora**, verde: handshake reciente (menos de tres minutos según el servidor) o aumento de tráfico observado por la app en los últimos 45 segundos.
- **No activo ahora**, rojo: no existe esa evidencia reciente, o el acceso está suspendido.
- **Sin actualizar**, gris: han pasado más de 30 segundos sin recibir un dashboard nuevo. No se presenta un estado antiguo como actual.

Tocar el indicador abre su explicación y el último handshake. Es una estimación de actividad: WireGuard no expone una sesión permanente ni permite saber con certeza si el dispositivo sigue conectado. Al cerrar y volver a abrir la app, la evidencia local de tráfico se reconstruye; no se deduce actividad de los GB acumulados de una primera muestra. Los clientes suspendidos nunca aparecen activos.

El panel consulta cada cinco segundos. Las muestras de tráfico y su persistencia en el VPS mantienen las reglas existentes. Esta actualización solo modifica Android; no cambia WireGuard, clientes, planes, contraseñas, TLS, SSH ni servicios del VPS.

Los GB usan coma decimal y omiten ceros innecesarios: `2 GB`, `2,5 GB`, `0,002 GB`. La cuota se presenta como **Disponible: 2 GB de 2 GB**, con una barra de saldo. No se usa separador de miles con punto.

Se sustituyó la apariencia oscura de grandes bloques por una interfaz clara, fondo cálido, tarjetas blancas, bordes discretos y acentos azules. Los formularios de cliente, plan y suscripción tienen una ventana amplia, encabezado propio, contenido desplazable y acción de guardar fija. Las operaciones de suscripción se eligen con botones de selección compactos; los mensajes explican la consecuencia de cada operación.

La APK release 0.3.0 conserva la firma de 0.2.0 y aumenta versionCode a 3. Se puede actualizar sobre la APK release anterior. Una instalación debug usa otra firma y debe desinstalarse previamente, sin borrar datos del VPS ni perfiles de WireGuard.
