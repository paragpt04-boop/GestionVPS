"""Prepaid subscriptions; calendar anchors never move on top-up or renewal."""
import calendar
import datetime as dt
import json
import time
import uuid


def schema(c):
    c.executescript('''
    CREATE TABLE IF NOT EXISTS plans(id TEXT PRIMARY KEY,name TEXT NOT NULL,
      duration INTEGER,unit TEXT NOT NULL,quota_bytes INTEGER,archived INTEGER NOT NULL DEFAULT 0);
    CREATE TABLE IF NOT EXISTS subscriptions(client_id TEXT PRIMARY KEY,plan_id TEXT NOT NULL,
      name TEXT NOT NULL,duration INTEGER,unit TEXT NOT NULL,anchor INTEGER NOT NULL,
      expires INTEGER,quota_bytes INTEGER,baseline INTEGER NOT NULL,cancelled INTEGER NOT NULL DEFAULT 0,
      base_quota_bytes INTEGER);
    CREATE TABLE IF NOT EXISTS subscription_events(id INTEGER PRIMARY KEY,client_id TEXT NOT NULL,
      ts INTEGER NOT NULL,operation TEXT NOT NULL,details TEXT NOT NULL);
    ''')
    if 'plan_blocked' not in [r[1] for r in c.execute('PRAGMA table_info(clients)')]:
        c.execute('ALTER TABLE clients ADD COLUMN plan_blocked INTEGER NOT NULL DEFAULT 0')


def definition(data):
    name=data.get('name','').strip()
    if not name or len(name)>64 or any(ord(ch)<32 for ch in name):
        raise ValueError('Nombre de plan inválido')
    duration=data.get('duration')
    unit=data.get('unit','days')
    if unit not in ('days','months'): raise ValueError('Unidad de duración inválida')
    if duration is not None and (type(duration)!=int or not 1<=duration<=3650):
        raise ValueError('Duración: de 1 a 3650 días o meses')
    quota=data.get('quota_bytes')
    if quota is not None and (type(quota)!=int or not 1_000_000<=quota<=1_000_000_000_000_000):
        raise ValueError('Cuota: de 0.001 a 1000000 GB')
    return name,duration,unit,quota


def boundary(anchor, duration, unit, now):
    """First fixed calendar boundary strictly after now, including missed cycles."""
    if duration is None: return None
    if unit=='days':
        interval=duration*86400
        return anchor+(max(0,(now-anchor)//interval)+1)*interval
    start=dt.datetime.fromtimestamp(anchor,dt.timezone.utc)
    current=dt.datetime.fromtimestamp(now,dt.timezone.utc)
    cycles=max(1,((current.year-start.year)*12+current.month-start.month)//duration)
    while True:
        months=start.year*12+start.month-1+cycles*duration
        year,month=divmod(months,12); month+=1
        if year>9999: raise ValueError('Fecha fuera de rango')
        result=int(start.replace(year=year,month=month,day=min(start.day,calendar.monthrange(year,month)[1])).timestamp())
        if result>now: return result
        cycles+=1


def status(c, row, now=None):
    sub=c.execute('SELECT * FROM subscriptions WHERE client_id=?',(row['id'],)).fetchone()
    if not sub: return None
    used=max(0,row['total_rx']+row['total_tx']-sub['baseline'])
    now=int(time.time()) if now is None else now
    reason=('cancelled' if sub['cancelled'] else 'expired' if sub['expires'] is not None and now>=sub['expires']
            else 'exhausted' if sub['quota_bytes'] is not None and used>=sub['quota_bytes'] else None)
    return {**dict(sub),'used_bytes':used,
            'remaining_bytes':None if sub['quota_bytes'] is None else max(0,sub['quota_bytes']-used),
            'blocked_reason':reason}


def catalog(c, op, data):
    identifier=data.get('id') or str(uuid.uuid4())
    if op!='plan_create' and not c.execute('SELECT 1 FROM plans WHERE id=?',(identifier,)).fetchone():
        raise ValueError('Plan no encontrado')
    if op=='plan_archive': c.execute('UPDATE plans SET archived=1 WHERE id=?',(identifier,))
    else:
        name,duration,unit,quota=definition(data)
        if op=='plan_create': c.execute('INSERT INTO plans VALUES(?,?,?,?,?,0)',(identifier,name,duration,unit,quota))
        else: c.execute('UPDATE plans SET name=?,duration=?,unit=?,quota_bytes=? WHERE id=?',(name,duration,unit,quota,identifier))
    return {'id':identifier,'ok':True}


def change(c, row, data):
    op=data.get('operation'); now=int(time.time()); identifier=row['id']
    sub=c.execute('SELECT * FROM subscriptions WHERE client_id=?',(identifier,)).fetchone()
    total=row['total_rx']+row['total_tx']
    details={}
    if op in ('assign','change'):
        plan=c.execute('SELECT * FROM plans WHERE id=? AND archived=0',(data.get('plan_id'),)).fetchone()
        if not plan: raise ValueError('Selecciona un plan disponible')
        if op=='assign' and sub and not sub['cancelled']:
            raise ValueError('Ya tiene suscripción: cambia o renueva conservando su calendario')
        if op=='change' and (not sub or sub['cancelled']): raise ValueError('Asigna una suscripción nueva')
        # Catalog changes never rewrite current contracts. Changing a contract
        # replaces its GB balance but retains its original billing cadence.
        anchor=sub['anchor'] if op=='change' else now
        duration=sub['duration'] if op=='change' else plan['duration']
        unit=sub['unit'] if op=='change' else plan['unit']
        expires=sub['expires'] if op=='change' else boundary(anchor,duration,unit,now)
        c.execute('INSERT OR REPLACE INTO subscriptions VALUES(?,?,?,?,?,?,?,?,?,0,?)',
                  (identifier,plan['id'],plan['name'],duration,unit,anchor,expires,plan['quota_bytes'],total,plan['quota_bytes']))
        details={'plan':plan['name'],'quota_bytes':plan['quota_bytes'],'expires':expires}
    elif op=='cancel':
        if not sub or sub['cancelled']: raise ValueError('No tiene suscripción activa')
        c.execute('UPDATE subscriptions SET cancelled=1 WHERE client_id=?',(identifier,))
    elif op=='topup':
        if not sub or sub['cancelled']: raise ValueError('Primero asigna una suscripción')
        amount=data.get('bytes')
        definition({'name':'recarga','quota_bytes':amount})
        if amount is None or sub['quota_bytes'] is None: raise ValueError('La suscripción debe tener cuota de GB')
        if sub['quota_bytes']+amount>1_000_000_000_000_000: raise ValueError('Saldo máximo excedido')
        c.execute('UPDATE subscriptions SET quota_bytes=quota_bytes+? WHERE client_id=?',(amount,identifier))
        details={'added_bytes':amount,'expires':sub['expires']}
    elif op=='renew':
        if not sub or sub['cancelled']: raise ValueError('Primero asigna una suscripción')
        if sub['expires'] is not None and now<sub['expires']:
            raise ValueError('Aún no vence: usa añadir GB; la fecha de facturación se conserva')
        # Renew the agreed quota snapshot, not an edited catalog definition.
        quota=data.get('quota_bytes',sub['base_quota_bytes'])
        definition({'name':sub['name'],'quota_bytes':quota})
        expires=boundary(sub['anchor'],sub['duration'],sub['unit'],now)
        c.execute('UPDATE subscriptions SET expires=?,baseline=?,quota_bytes=? WHERE client_id=?',(expires,total,quota,identifier))
        details={'quota_bytes':quota,'expires':expires}
    else: raise ValueError('Operación de suscripción inválida')
    c.execute('INSERT INTO subscription_events(client_id,ts,operation,details) VALUES(?,?,?,?)',
              (identifier,now,op,json.dumps(details,ensure_ascii=False)))
    return status(c,row,now)
