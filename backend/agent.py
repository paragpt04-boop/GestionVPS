"""Root-only state and WireGuard adapter. No user supplied shell commands."""
import configparser
import datetime
import fcntl
import grp
import json
import os
import pathlib
import re
import shutil
import socketserver
import sqlite3
import subprocess
import tempfile
import threading
import time
import uuid

from domain import delta, validate_client
from qos import apply as apply_qos, parse as parse_qos

ROOT = pathlib.Path('/var/lib/gestionvps-agent')
WG = pathlib.Path('/etc/wireguard/wg0.conf')
QOS = pathlib.Path('/etc/wireguard/qos-clientes.txt')
CLIENTS = pathlib.Path('/etc/wireguard/clientes')
LOCK = threading.RLock()

def command(*args, input=None):
    return subprocess.run(args, input=input, text=True, check=True, capture_output=True, timeout=20).stdout.strip()

def atomic(path, text):
    fd, temp = tempfile.mkstemp(dir=path.parent)
    try:
        with os.fdopen(fd, 'w') as file:
            file.write(text); file.flush(); os.fsync(file.fileno())
        os.chmod(temp, 0o600); os.replace(temp, path)
    finally:
        if os.path.exists(temp): os.unlink(temp)

def db():
    connection = sqlite3.connect(ROOT/'state.sqlite', timeout=30)
    connection.row_factory = sqlite3.Row
    connection.execute('PRAGMA foreign_keys=ON')
    return connection

def blocks(text):
    return re.split(r'(?m)^\[Peer\]\s*$', text)

def fields(text):
    return dict(re.findall(r'(?m)^\s*(\w+)\s*=\s*(.*?)\s*$', text))

def sync_runtime():
    stripped = command('wg-quick','strip','wg0')
    path = ROOT/'sync.conf'
    atomic(path, stripped+'\n')
    try: command('wg','syncconf','wg0',str(path))
    finally: path.unlink(missing_ok=True)

def audit(c, action, client=None):
    c.execute('INSERT INTO audit(ts,action,client_id) VALUES(?,?,?)',(int(time.time()),action,client))

def initialize():
    os.umask(0o077); ROOT.mkdir(mode=0o700, exist_ok=True)
    with db() as c:
        c.executescript('''
        CREATE TABLE IF NOT EXISTS clients(
          id TEXT PRIMARY KEY, name TEXT NOT NULL COLLATE NOCASE,
          ip TEXT NOT NULL, public_key TEXT NOT NULL UNIQUE,
          profile TEXT NOT NULL, down INTEGER NOT NULL, up INTEGER NOT NULL,
          suspended INTEGER NOT NULL DEFAULT 0, deleted INTEGER NOT NULL DEFAULT 0,
          rx INTEGER NOT NULL DEFAULT 0, tx INTEGER NOT NULL DEFAULT 0,
          total_rx INTEGER NOT NULL DEFAULT 0, total_tx INTEGER NOT NULL DEFAULT 0,
          boot TEXT NOT NULL DEFAULT '', handshake INTEGER NOT NULL DEFAULT 0,
          peer_options TEXT NOT NULL DEFAULT '');
        CREATE TABLE IF NOT EXISTS traffic(day TEXT,client_id TEXT,rx INTEGER NOT NULL,tx INTEGER NOT NULL,PRIMARY KEY(day,client_id));
        CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY,ts INTEGER NOT NULL,action TEXT NOT NULL,client_id TEXT);
        ''')
        # Upgrade the initial pilot schema without losing traffic or tombstones.
        columns=[r[1] for r in c.execute('PRAGMA table_info(clients)')]
        if 'peer_options' not in columns:
            c.execute("ALTER TABLE clients ADD COLUMN peer_options TEXT NOT NULL DEFAULT ''")
        sql=c.execute("SELECT sql FROM sqlite_master WHERE name='clients'").fetchone()[0]
        if 'name TEXT NOT NULL UNIQUE' in sql:
            replacement=sql.replace('CREATE TABLE clients','CREATE TABLE clients_v2',1).replace('name TEXT NOT NULL UNIQUE','name TEXT NOT NULL').replace('ip TEXT NOT NULL UNIQUE','ip TEXT NOT NULL')
            c.execute(replacement)
            c.execute('INSERT INTO clients_v2 SELECT * FROM clients')
            c.execute('DROP TABLE clients');c.execute('ALTER TABLE clients_v2 RENAME TO clients')
        c.execute('CREATE UNIQUE INDEX IF NOT EXISTS live_names ON clients(name COLLATE NOCASE) WHERE deleted=0')
        c.execute('CREATE UNIQUE INDEX IF NOT EXISTS live_ips ON clients(ip) WHERE deleted=0')
        for b in blocks(WG.read_text())[1:]:
            c.execute("UPDATE clients SET peer_options=? WHERE public_key=? AND peer_options=''",(b.strip(),fields(b).get('PublicKey')))
        c.execute('PRAGMA user_version=2')
    recover()
    with db() as c:
        if c.execute('SELECT count(*) FROM clients').fetchone()[0]: return
        rates={ip:(down,up) for ip,down,up in parse_qos(QOS.read_text())}
        profiles = {}
        for profile in CLIENTS.glob('*.conf'):
            f=fields(profile.read_text())
            address=f.get('Address','').split('/')[0]
            profiles[address]=profile
        for block in blocks(WG.read_text())[1:]:
            f=fields(block); ip=f['AllowedIPs'].split('/')[0].strip()
            if not re.fullmatch(r'10\.5\.0\.(?:[0-9]{1,3})',ip) or ',' in f['AllowedIPs']:
                raise RuntimeError('Existing peer requires manual migration')
            profile=profiles.get(ip)
            name=profile.stem if profile else 'cliente-'+ip.split('.')[-1]
            down,up=rates.get(ip,(2,1))
            c.execute('INSERT INTO clients(id,name,ip,public_key,profile,down,up,peer_options) VALUES(?,?,?,?,?,?,?,?)',
                      (str(uuid.uuid4()),name,ip,f['PublicKey'],str(profile) if profile else '',down,up,block.strip()))
        audit(c,'import_existing')

def recover():
    journal=ROOT/'pending.json'
    if not journal.exists(): return
    info=json.loads(journal.read_text())
    with db() as c:
        committed=c.execute('SELECT 1 FROM audit WHERE action=?',('commit:'+info['id'],)).fetchone()
    if not committed:
        backup=pathlib.Path(info['backup'])
        atomic(WG,(backup/'wg0.conf').read_text()); atomic(QOS,(backup/'qos.txt').read_text())
        for path, saved in info['profiles'].items():
            target=pathlib.Path(path)
            if saved: atomic(target,(backup/saved).read_text())
            else: target.unlink(missing_ok=True)
        sync_runtime(); apply_qos(parse_qos(QOS.read_text()))
    journal.unlink()

def public(row):
    return {'id':row['id'],'name':row['name'],'ip':row['ip'],
            'download_mbps':row['down'],'upload_mbps':row['up'],
            'suspended':bool(row['suspended']), 'last_handshake':row['handshake'],
            'active_estimated':not row['suspended'] and row['handshake'] > time.time()-180,
            'received_bytes':row['total_rx'],'sent_bytes':row['total_tx'],
            'profile_available':bool(row['profile'])}

def collect():
    boot=pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    # dump includes private server key on its first line: never log or return it.
    lines=command('wg','show','wg0','dump').splitlines()[1:]
    with db() as c:
        day=datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%d')
        for line in lines:
            parts=line.split('\t')
            key,handshake,rx,tx=parts[0],int(parts[4]),int(parts[5]),int(parts[6])
            row=c.execute('SELECT * FROM clients WHERE public_key=? AND deleted=0',(key,)).fetchone()
            if not row: continue
            dr,dt=delta(row['rx'],rx,row['boot']==boot),delta(row['tx'],tx,row['boot']==boot)
            c.execute('UPDATE clients SET rx=?,tx=?,total_rx=total_rx+?,total_tx=total_tx+?,boot=?,handshake=? WHERE id=?',
                      (rx,tx,dr,dt,boot,handshake,row['id']))
            c.execute('INSERT INTO traffic VALUES(?,?,?,?) ON CONFLICT(day,client_id) DO UPDATE SET rx=rx+excluded.rx,tx=tx+excluded.tx',(day,row['id'],dr,dt))

def mutate(op, data):
    # Serialize runtime and database changes; recovery journal covers process crashes.
    collect()
    c=db(); c.execute('BEGIN IMMEDIATE')
    journal=ROOT/'pending.json'
    info=None
    try:
        existing=c.execute('SELECT * FROM clients WHERE id=? AND deleted=0',(data.get('id',''),)).fetchone()
        if op != 'create' and not existing: raise ValueError('Cliente no encontrado')
        identifier=str(uuid.uuid4()) if op=='create' else existing['id']
        profile=None; new_profile=None
        if op in ('create','update'):
            name,down,up=validate_client(data)
            if c.execute('SELECT 1 FROM clients WHERE name=? COLLATE NOCASE AND id<>? AND deleted=0',(name,identifier)).fetchone():
                raise ValueError('Ese nombre ya existe')
        if op=='create':
            used={row[0] for row in c.execute('SELECT ip FROM clients WHERE deleted=0')}
            for b in blocks(WG.read_text())[1:]:
                used.update(ip.strip().split('/')[0] for ip in fields(b).get('AllowedIPs','').split(','))
            ip=next((f'10.5.0.{n}' for n in range(2,255) if f'10.5.0.{n}' not in used),None)
            if not ip: raise ValueError('No hay direcciones disponibles')
            private=command('wg','genkey'); key=command('wg','pubkey',input=private+'\n')
            profile=CLIENTS/(identifier+'.conf')
            new_profile=f'[Interface]\nPrivateKey = {private}\nAddress = {ip}/32\nDNS = 1.1.1.1\n\n[Peer]\nPublicKey = {command("wg","show","wg0","public-key")}\nEndpoint = 107.178.51.31:51820\nAllowedIPs = 0.0.0.0/0\nPersistentKeepalive = 25\n'
            c.execute('INSERT INTO clients(id,name,ip,public_key,profile,down,up) VALUES(?,?,?,?,?,?,?)',(identifier,name,ip,key,str(profile),down,up))
        elif op=='update':
            c.execute('UPDATE clients SET name=?,down=?,up=? WHERE id=?',(name,down,up,identifier))
        elif op in ('suspend','activate'):
            c.execute('UPDATE clients SET suspended=?,rx=0,tx=0,handshake=0 WHERE id=?',(int(op=='suspend'),identifier))
        elif op=='delete':
            c.execute('UPDATE clients SET deleted=1,suspended=1 WHERE id=?',(identifier,))
            profile=pathlib.Path(existing['profile']) if existing['profile'] else None
        elif op=='rotate':
            if not existing['profile']: raise ValueError('No hay perfil disponible para renovar')
            profile=pathlib.Path(existing['profile'])
            private=command('wg','genkey'); key=command('wg','pubkey',input=private+'\n')
            new_profile=re.sub(r'(?m)^PrivateKey\s*=.*$', 'PrivateKey = '+private,profile.read_text())
            c.execute('UPDATE clients SET public_key=?,rx=0,tx=0,handshake=0 WHERE id=?',(key,identifier))
        else: raise ValueError('Operación no permitida')
        # Retain unknown external peer blocks, all Interface directives and existing keys.
        original=blocks(WG.read_text()); known={r[0] for r in c.execute('SELECT public_key FROM clients')}
        if existing: known.add(existing['public_key'])
        external=[b for b in original[1:] if fields(b).get('PublicKey') not in known]
        selected=c.execute('SELECT * FROM clients WHERE deleted=0').fetchall()
        cfg=original[0].rstrip()+'\n'
        for b in external: cfg+='\n[Peer]\n'+b.strip()+'\n'
        # Preserve existing per-peer options (including PSK), when present.
        old_blocks={fields(b).get('PublicKey'):b for b in original[1:]}
        for row in selected:
            if row['suspended']: continue
            block=old_blocks.get(row['public_key']) or row['peer_options']
            if op=='rotate' and row['id']==identifier:
                block=old_blocks.get(existing['public_key']) or existing['peer_options']
                if block: block=re.sub(r'(?m)^PublicKey\s*=.*$', 'PublicKey = '+row['public_key'],block)
            block=block.strip() if block else f'PublicKey = {row["public_key"]}\nAllowedIPs = {row["ip"]}/32'
            c.execute('UPDATE clients SET peer_options=? WHERE id=?',(block,row['id']))
            cfg+='\n[Peer]\n'+block+'\n'
        qos=''.join(f'{r["ip"]} {r["down"]} {r["up"]}\n' for r in selected)
        parse_qos(qos)
        txid=str(uuid.uuid4()); backup=ROOT/'backups'/txid; backup.mkdir(parents=True,mode=0o700)
        shutil.copy2(WG,backup/'wg0.conf'); shutil.copy2(QOS,backup/'qos.txt')
        saved={}
        if profile:
            saved[str(profile)]='profile.conf' if profile.exists() else None
            if profile.exists(): shutil.copy2(profile,backup/'profile.conf')
        info={'id':txid,'backup':str(backup),'profiles':saved}
        atomic(journal,json.dumps(info))
        if profile and new_profile: atomic(profile,new_profile)
        atomic(WG,cfg); atomic(QOS,qos)
        apply_qos(parse_qos(qos)); sync_runtime()
        if profile and op=='delete': profile.unlink(missing_ok=True)
        audit(c,op,identifier); audit(c,'commit:'+txid,identifier)
        c.commit(); journal.unlink()
        return {'id':identifier,'ok':True}
    except Exception:
        c.rollback()
        if info: recover()
        raise
    finally: c.close()

def dispatch(request):
    op=request.get('op'); data=request.get('data',{})
    with LOCK:
        if op in ('create','update','suspend','activate','delete','rotate'): return mutate(op,data)
        if op=='dashboard':
            collect()
            with db() as c:
                rows=c.execute('SELECT * FROM clients WHERE deleted=0 ORDER BY name COLLATE NOCASE').fetchall()
                history=[dict(r) for r in c.execute('SELECT day,sum(rx) received_bytes,sum(tx) sent_bytes FROM traffic GROUP BY day ORDER BY day DESC LIMIT 30')]
            services={}
            for name in ['wg-quick@wg0','wg-qos']:
                services[name]=subprocess.run(['systemctl','is-active',name],capture_output=True,text=True).stdout.strip()
            return {'server':'Miami','timestamp':int(time.time()),'clients':[public(r) for r in rows],
                    'services':services,'history':history,'load':os.getloadavg()[0],
                    'uptime_seconds':float(pathlib.Path('/proc/uptime').read_text().split()[0]),
                    'alerts':[{'severity':'warning','message':f'{k}: {v}'} for k,v in services.items() if v!='active'],
                    'traffic_note':'Bytes vistos por el servidor. Recibidos = subida del cliente. Enviados = descarga. Los reinicios entre muestras pueden perder tráfico no observado.'}
        if op=='profile':
            with db() as c:
                row=c.execute('SELECT * FROM clients WHERE id=? AND deleted=0',(data.get('id'),)).fetchone()
                if not row or not row['profile']: raise ValueError('Perfil no disponible')
                if row['suspended']: raise ValueError('Reactiva el cliente antes de exportar')
                audit(c,'export_profile',row['id'])
                return {'name':row['name'],'config':pathlib.Path(row['profile']).read_text()}
        if op=='audit':
            with db() as c: return [dict(r) for r in c.execute("SELECT * FROM audit WHERE action NOT LIKE 'commit:%' ORDER BY id DESC LIMIT 200")]
        if op=='traffic':
            with db() as c:
                if not c.execute('SELECT 1 FROM clients WHERE id=?',(data.get('id'),)).fetchone():
                    raise ValueError('Cliente no encontrado')
                return [dict(r) for r in c.execute('SELECT day,rx received_bytes,tx sent_bytes FROM traffic WHERE client_id=? ORDER BY day DESC LIMIT 365',(data['id'],))]
        if op=='diagnostics':
            return {name:command(*args) for name,args in {
                'download':['tc','-s','class','show','dev','wg0'],
                'upload':['tc','-s','class','show','dev','ifb-wg0'],
                'forwarding':['sysctl','net.ipv4.ip_forward']}.items()}
        raise ValueError('Operación no permitida')

class Handler(socketserver.StreamRequestHandler):
    def handle(self):
        self.request.settimeout(30)
        try:
            line=self.rfile.readline(8193)
            if len(line)>8192: raise ValueError('Solicitud demasiado grande')
            result={'ok':True,'data':dispatch(json.loads(line))}
        except ValueError as error: result={'ok':False,'error':str(error)}
        except Exception: result={'ok':False,'error':'Operación fallida; se ha intentado revertir. Revisar diagnóstico.'}
        self.wfile.write((json.dumps(result)+'\n').encode())

def sampler():
    while True:
        time.sleep(15)
        try:
            with LOCK: collect()
        except Exception:
            # No exception dumps: subprocess output can contain keys.
            print('Traffic sampling unavailable',flush=True)

if __name__=='__main__':
    initialize()
    lock=open(ROOT/'agent.lock','w'); fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    sock=pathlib.Path('/run/gestionvps/agent.sock'); sock.unlink(missing_ok=True)
    server=socketserver.UnixStreamServer(str(sock),Handler)
    os.chown(sock,0,grp.getgrnam('gestionvps').gr_gid); os.chmod(sock,0o660)
    threading.Thread(target=sampler,daemon=True).start()
    server.serve_forever()
