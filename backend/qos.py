"""Idempotent HTB updates; accepts existing one-column Miami QoS file."""
import ipaddress
import pathlib
import subprocess
import sys

def parse(text):
    rows = []
    seen = set()
    for line in text.splitlines():
        line = line.split('#', 1)[0].strip()
        if not line:
            continue
        parts = line.split()
        if len(parts) not in (1, 3):
            raise ValueError('QoS: expected IP or IP download upload')
        ip = ipaddress.ip_address(parts[0])
        if ip not in ipaddress.ip_network('10.5.0.0/24') or not 2 <= int(str(ip).split('.')[-1]) <= 254 or str(ip) in seen:
            raise ValueError('QoS: invalid or duplicate IP')
        down, up = (2, 1) if len(parts) == 1 else tuple(int(v) for v in parts[1:])
        if not (1 <= down <= 1000 and 1 <= up <= 1000):
            raise ValueError('QoS: rates must be 1..1000 Mbps')
        seen.add(str(ip)); rows.append((str(ip), down, up))
    return rows

def run(*args):
    return subprocess.run(args, check=True, capture_output=True, text=True, timeout=15).stdout

def apply(rows):
    run('ip', 'link', 'show', 'wg0')
    run('modprobe', 'ifb')
    if subprocess.run(['ip','link','show','ifb-wg0'],capture_output=True).returncode:
        run('ip','link','add','ifb-wg0','type','ifb')
    run('ip','link','set','ifb-wg0','up')
    for dev, handle in [('wg0','1'),('ifb-wg0','2')]:
        current = run('tc','qdisc','show','dev',dev)
        if f'qdisc htb {handle}:' not in current:
            # Refuse to overwrite an unrelated root queue.
            if ' root ' in current and 'qdisc noqueue ' not in current:
                raise RuntimeError('Unexpected root qdisc; manual review required')
            run('tc','qdisc','replace','dev',dev,'root','handle',handle+':','htb','default','999')
        run('tc','class','replace','dev',dev,'parent',handle+':','classid',handle+':999','htb','rate','128kbit','ceil','128kbit')
    for ip, down, up in rows:
        n = str(int(ip.split('.')[-1]))
        for dev, handle, direction, rate in [('wg0','1','dst',down),('ifb-wg0','2','src',up)]:
            run('tc','class','replace','dev',dev,'parent',handle+':','classid',handle+':'+n,'htb','rate',f'{rate}mbit','ceil',f'{rate}mbit')
            run('tc','filter','replace','dev',dev,'parent',handle+':','protocol','ip','prio',n,'handle','800::800','u32','match','ip',direction,ip+'/32','flowid',handle+':'+n)
    if 'ingress ffff:' not in run('tc','qdisc','show','dev','wg0'):
        run('tc','qdisc','add','dev','wg0','handle','ffff:','ingress')
    run('tc','filter','replace','dev','wg0','parent','ffff:','protocol','ip','prio','10','handle','800::800','u32','match','u32','0','0','action','mirred','egress','redirect','dev','ifb-wg0')

if __name__ == '__main__':
    apply(parse(pathlib.Path('/etc/wireguard/qos-clientes.txt').read_text()))
