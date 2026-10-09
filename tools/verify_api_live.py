import urllib.request, urllib.error, ssl, json, pathlib, subprocess, hashlib, time
ctx=ssl.create_default_context(cafile='/root/gestionvps-ca/ca.crt')
base='https://107.178.51.31:8443'
token=None
def req(path,method='GET',data=None):
    headers={'Content-Type':'application/json'}
    if token:headers['Authorization']='Bearer '+token
    r=urllib.request.Request(base+path,data=json.dumps(data).encode() if data is not None else None,method=method,headers=headers)
    try:
        with urllib.request.urlopen(r,context=ctx,timeout=100) as response:return json.load(response)
    except urllib.error.HTTPError as e:
        message=e.read().decode()
        raise RuntimeError(f'HTTP {e.code}: '+message) from None
def cmd(*args):return subprocess.check_output(args,text=True)
before=hashlib.sha256(pathlib.Path('/etc/wireguard/clientes/jesus.conf').read_bytes()).hexdigest()
server_key=cmd('wg','show','wg0','public-key')
assert req('/health')['status']=='ok'
try:req('/dashboard');raise AssertionError('Unauthenticated access allowed')
except RuntimeError as e:assert str(e).startswith('HTTP 401:')
credentials=pathlib.Path('/root/gestionvps-admin.txt').read_text().splitlines()
password=credentials[1].split(': ',1)[1]
token=req('/login','POST',{'username':'admin','password':password})['token'];del password
data=req('/dashboard');jesus=next(c for c in data['clients'] if c['name']=='jesus')
assert jesus['ip']=='10.5.0.2'
print('PASS TLS, authentication, existing jesus imported')
identifier=None
try:
    result=req('/clients','POST',{'name':'Prueba Miami ñ','download_mbps':3,'upload_mbps':2});identifier=result['id']
    client=next(c for c in req('/dashboard')['clients'] if c['id']==identifier)
    assert client['ip']!='10.5.0.2'
    profile=req(f'/clients/{identifier}/profile')['config'];assert '[Interface]' in profile and 'PrivateKey = ' in profile
    assert '3Mbit' in cmd('tc','class','show','dev','wg0')
    assert '2Mbit' in cmd('tc','class','show','dev','ifb-wg0')
    print('PASS create, custom name, private profile, independent QoS')
    try:req('/clients','POST',{'name':'Prueba Miami ñ'});raise AssertionError('Duplicate accepted')
    except RuntimeError as e:assert str(e).startswith('HTTP 400:')
    req(f'/clients/{identifier}','PUT',{'name':'Prueba editada','download_mbps':4,'upload_mbps':3})
    assert '4Mbit' in cmd('tc','class','show','dev','wg0')
    req(f'/clients/{identifier}/suspend','POST')
    assert client['ip'] not in cmd('wg','show','wg0','allowed-ips')
    req(f'/clients/{identifier}/activate','POST')
    assert client['ip'] in cmd('wg','show','wg0','allowed-ips')
    req(f'/clients/{identifier}/rotate','POST')
    renewed=req(f'/clients/{identifier}/profile')['config'];assert renewed!=profile
    print('PASS edit, suspend, activate, rotate')
    req('/diagnostics');assert len(req('/audit'))>=6
    print('PASS diagnostics and audit')
finally:
    if identifier:
        req(f'/clients/{identifier}','DELETE')
        assert all(c['id']!=identifier for c in req('/dashboard')['clients'])
        assert client['ip'] not in cmd('wg','show','wg0','allowed-ips')
        print('PASS delete and revoke temporary peer')
assert before==hashlib.sha256(pathlib.Path('/etc/wireguard/clientes/jesus.conf').read_bytes()).hexdigest()
assert server_key==cmd('wg','show','wg0','public-key')
assert '10.5.0.2/32' in cmd('wg','show','wg0','allowed-ips')
assert 'MASQUERADE' in cmd('iptables','-t','nat','-S')
assert ':443' in cmd('ss','-lnt')
req('/logout','POST')
try:req('/dashboard');raise AssertionError('Session survived logout')
except RuntimeError as e:assert str(e).startswith('HTTP 401:')
print('PASS jesus profile and server key unchanged, NAT and SSH preserved, logout revoked')
