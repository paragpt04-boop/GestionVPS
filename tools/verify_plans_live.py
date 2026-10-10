"""Root-only integration: temporary peer, real encrypted traffic and unattended cutoff.
Never prints credentials or profiles. Expiry is accelerated only for the temporary subscription.
"""
import hashlib,json,pathlib,socket,sqlite3,ssl,subprocess,tempfile,threading,time,urllib.request

ctx=ssl.create_default_context(cafile='/root/gestionvps-ca/ca.crt');token=None
def req(path,method='GET',data=None):
    headers={'Content-Type':'application/json'}
    if token:headers['Authorization']='Bearer '+token
    request=urllib.request.Request('https://107.178.51.31:8443'+path,data=None if data is None else json.dumps(data).encode(),headers=headers,method=method)
    with urllib.request.urlopen(request,context=ctx,timeout=90) as response:return json.load(response)
def run(*args):return subprocess.run(args,check=True,capture_output=True,text=True,timeout=30).stdout
def ns(*args):return run('ip','netns','exec','gvpsplans',*args)
def peer_present():return ip+'/32' in run('wg','show','wg0','allowed-ips')
def wait_absent():
    deadline=time.monotonic()+15
    while time.monotonic()<deadline:
        if not peer_present():return
        time.sleep(.5)
    raise AssertionError('Automatic suspension did not revoke peer')
def reconnect():
    # Revocation discards server session keys; emulate toggling the official client.
    public=next(line.split('=',1)[1].strip() for line in profile.splitlines() if line.startswith('PublicKey'))
    ns('wg','set','wgtest','peer',public,'remove')
    with tempfile.NamedTemporaryFile(mode='w',dir='/root',suffix='.conf') as temp:
        temp.write('\n'.join(line for line in profile.splitlines() if not line.startswith(('Address','DNS')))+'\n');temp.flush()
        ns('wg','setconf','wgtest',temp.name)
    ns('ping','-c','2','-W','3','10.5.0.1')
credentials=pathlib.Path('/root/gestionvps-admin.txt').read_text().splitlines()
token=req('/login','POST',{'username':'admin','password':credentials[1].split(': ',1)[1]})['token'];del credentials
before=req('/dashboard')['clients'];original={c['id'] for c in before}
jesus_hash=hashlib.sha256(pathlib.Path('/etc/wireguard/clientes/jesus.conf').read_bytes()).hexdigest()
identifier=None;plan=None;ip=None
try:
    plan=req('/plans','POST',{'name':'Prueba integración temporal','duration':1,'unit':'days','quota_bytes':2_000_000})['id']
    identifier=req('/clients','POST',{'name':'Prueba planes temporal','download_mbps':3,'upload_mbps':2,'plan_id':plan})['id']
    profile=req(f'/clients/{identifier}/profile')['config']
    client=next(c for c in req('/dashboard')['clients'] if c['id']==identifier);ip=client['ip'];initial=client['subscription']
    def change(operation,**data):return req(f'/clients/{identifier}/subscription','PUT',{'operation':operation,**data})
    run('ip','netns','add','gvpsplans')
    run('ip','link','add','gvpsplan0','type','veth','peer','name','gvpsplan1')
    run('ip','link','set','gvpsplan1','netns','gvpsplans')
    run('ip','addr','add','198.18.78.1/30','dev','gvpsplan0');run('ip','link','set','gvpsplan0','up')
    ns('ip','addr','add','198.18.78.2/30','dev','gvpsplan1');ns('ip','link','set','gvpsplan1','up');ns('ip','link','set','lo','up')
    ns('ip','route','add','107.178.51.31/32','via','198.18.78.1');ns('ip','link','add','wgtest','type','wireguard')
    with tempfile.NamedTemporaryFile(mode='w',dir='/root',suffix='.conf') as temp:
        temp.write('\n'.join(line for line in profile.splitlines() if not line.startswith(('Address','DNS')))+'\n');temp.flush()
        ns('wg','setconf','wgtest',temp.name)
    ns('ip','addr','add',ip+'/32','dev','wgtest');ns('ip','link','set','wgtest','mtu','1380','up');ns('ip','route','add','default','dev','wgtest')
    reconnect()
    for direction in ('upload','download'):
        listener=socket.socket();listener.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1);listener.bind(('10.5.0.1',0));port=listener.getsockname()[1];listener.listen();listener.settimeout(10)
        def serve():
            try:
                conn,_=listener.accept();conn.settimeout(12)
                with conn:
                    if direction=='download':conn.sendall(b'x'*1_200_000)
                    else:
                        while conn.recv(65536):pass
            except (TimeoutError,OSError):pass # expected if quota removes this temporary peer mid-transfer
            finally:listener.close()
        worker=threading.Thread(target=serve);worker.start()
        code=f'''import socket
try:
 s=socket.create_connection(('10.5.0.1',{port}),5);s.settimeout(10)
 if {direction!r}=='upload':s.sendall(b'x'*1200000)
 else:
  while s.recv(65536):pass
 s.close()
except (TimeoutError,OSError):pass
'''
        ns('python3','-c',code);worker.join(timeout=15)
    wait_absent() # no dashboard call: prove server sampler enforces without the app
    client=next(c for c in req('/dashboard')['clients'] if c['id']==identifier)
    assert client['subscription']['blocked_reason']=='exhausted'
    assert client['subscription']['used_bytes']>=2_000_000
    print('PASS real upload + download quota, background peer revocation')
    change('topup',bytes=5_000_000);assert peer_present()
    client=next(c for c in req('/dashboard')['clients'] if c['id']==identifier)
    assert client['subscription']['expires']==initial['expires']
    reconnect()
    print('PASS top-up restores real tunnel and preserves billing deadline')
    change('cancel');assert not peer_present()
    change('assign',plan_id=plan)
    # Accelerate only this test client's deadline; do not wait a real day.
    with sqlite3.connect('/var/lib/gestionvps-agent/state.sqlite',timeout=30) as c:
        c.execute('UPDATE subscriptions SET expires=? WHERE client_id=?',(int(time.time())-1,identifier))
    wait_absent()
    assert next(c for c in req('/dashboard')['clients'] if c['id']==identifier)['subscription']['blocked_reason']=='expired'
    change('renew');assert peer_present()
    reconnect()
    print('PASS accelerated deadline cutoff and renewal restore real tunnel')
    run('systemctl','restart','gestionvps-agent')
    time.sleep(1)
    client=next(c for c in req('/dashboard')['clients'] if c['id']==identifier)
    assert client['subscription'] and not client['suspended']
    assert len(req(f'/clients/{identifier}/subscription-history'))>=5
    print('PASS subscription, calendar and history survive agent restart')
finally:
    subprocess.run(['ip','netns','del','gvpsplans'],capture_output=True)
    subprocess.run(['ip','link','del','gvpsplan0'],capture_output=True)
    if identifier:req('/clients/'+identifier,'DELETE')
    if plan:req('/plans/'+plan,'DELETE')
    after=req('/dashboard')['clients']
    assert {c['id'] for c in after}==original
    assert all(c['subscription'] is None for c in after if c['id'] in original and next(x for x in before if x['id']==c['id'])['subscription'] is None)
    assert jesus_hash==hashlib.sha256(pathlib.Path('/etc/wireguard/clientes/jesus.conf').read_bytes()).hexdigest()
    assert ':443' in run('ss','-lnt') and 'MASQUERADE' in run('iptables','-t','nat','-S')
    req('/logout','POST')
    print('PASS temporary resources removed; existing clients, jesus, NAT and SSH preserved')
