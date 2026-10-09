#!/bin/bash
# Run from a reviewed checkout on the Miami VPS, after protected backup.
set -euo pipefail
[[ $(id -u) = 0 ]] || { echo 'Run as root'; exit 1; }
[[ -f /etc/wireguard/wg0.conf ]] || exit 1
[[ -f /etc/gestionvps/server.crt && -f /etc/gestionvps/server.key ]] || { echo 'Provision TLS first'; exit 1; }
id gestionvps >/dev/null 2>&1 || useradd --system --home /nonexistent --shell /usr/sbin/nologin gestionvps
install -d -m 700 /var/lib/gestionvps-agent
install -d -m 700 -o gestionvps -g gestionvps /var/lib/gestionvps-api
python3 -m venv /opt/gestionvps/venv
/opt/gestionvps/venv/bin/pip install -r /opt/gestionvps/backend/requirements.txt
python3 /opt/gestionvps/backend/bootstrap.py
chown root:gestionvps /etc/gestionvps /etc/gestionvps/server.key /etc/gestionvps/server.crt
chmod 750 /etc/gestionvps
chmod 640 /etc/gestionvps/server.key
chmod 644 /etc/gestionvps/server.crt
install -m 700 /opt/gestionvps/deploy/wg-qos.sh /usr/local/sbin/wg-qos.sh
install -m 644 /opt/gestionvps/deploy/gestionvps-agent.service /etc/systemd/system/
install -m 644 /opt/gestionvps/deploy/gestionvps-api.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now gestionvps-agent gestionvps-api
# Do not restart wg0 or SSH. QoS updates occur through the agent or existing boot service.
