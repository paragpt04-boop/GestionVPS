"""Temporary network namespace tests real WireGuard encryption and HTB, no jesus changes."""
import urllib.request,ssl,json,pathlib,subprocess,tempfile,threading,socket,time,hashlib
ctx=ssl.create_default_context(cafile='/root/gestionvps-ca/ca.crt');token=None
def req(path,method='GET',data=None):
    headers={'Content-Type':'application/json'}
    if token:headers['Authorization']='Bearer '+token
    request=urllib.request.Request('https://107.178.51.31:8443'+path,data=json.dumps(data).encode() if data is not None else None,headers=headers,method=method)
    with urllib.request.urlopen(request,context=ctx,timeout=90) as response:return json.load(response)
def run(*args):return subprocess.run(args,check=True,capture_output=True,text=True,timeout=30).stdout
credentials=pathlib.Path('/root/gestionvps-admin.txt').read_text().splitlines()
token=req('/login','POST',{'username':'admin','password':credentials[1].split(': ',1)[1]})['token'];del credentials
before=hashlib.sha256(pathlib.Path('/etc/wireguard/clientes/jesus.conf').read_bytes()).hexdigest()
identifier=None;namespace='gvpstest';link='gvpstest0';clientip=None
try:
    identifier=req('/clients','POST',{'name':'Prueba de túnel temporal','download_mbps':3,'upload_mbps':2})['id']
    profile=req(f'/clients/{identifier}/profile')['config']
    clientip=next(c['ip'] for c in req('/dashboard')['clients'] if c['id']==identifier)
    run('ip','netns','add',namespace)
    run('ip','link','add',link,'type','veth','peer','name','gvpstest1')
    run('ip','link','set','gvpstest1','netns',namespace)
    run('ip','addr','add','198.18.77.1/30','dev',link);run('ip','link','set',link,'up')
    def ns(*args):return run('ip','netns','exec',namespace,*args)
    ns('ip','addr','add','198.18.77.2/30','dev','gvpstest1');ns('ip','link','set','gvpstest1','up');ns('ip','link','set','lo','up')
    ns('ip','route','add','107.178.51.31/32','via','198.18.77.1')
    ns('ip','link','add','wgtest','type','wireguard')
    with tempfile.NamedTemporaryFile(mode='w',dir='/root',suffix='.conf') as temp:
        temp.write('\n'.join(line for line in profile.splitlines() if not line.startswith(('Address','DNS')))+'\n');temp.flush()
        ns('wg','setconf','wgtest',temp.name)
    ns('ip','addr','add',clientip+'/32','dev','wgtest');ns('ip','link','set','wgtest','mtu','1380','up');ns('ip','route','add','default','dev','wgtest')
    print('PASS encrypted tunnel ping:',ns('ping','-c','2','-W','3','10.5.0.1').splitlines()[-1])
    observed={}
    for direction in ['download','upload']:
        listener=socket.socket();listener.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1);listener.bind(('10.5.0.1',0));port=listener.getsockname()[1];listener.listen();listener.settimeout(15)
        def serve():
            conn,_=listener.accept();conn.settimeout(20)
            with conn:
                if direction=='download':
                    start=time.monotonic()
                    while time.monotonic()-start<8:conn.sendall(b'0'*8192)
                else:
                    size=0;start=time.monotonic()
                    while True:
                        data=conn.recv(65536)
                        if not data:break
                        size+=len(data)
                    observed[direction]=size*8/(time.monotonic()-start)/1e6
            listener.close()
        worker=threading.Thread(target=serve);worker.start()
        code=f'''import socket,time
s=socket.create_connection(('10.5.0.1',{port}),10);s.settimeout(20)
start=time.monotonic();size=0
if {direction!r}=='download':
 while True:
  data=s.recv(65536)
  if not data:break
  size+=len(data)
 print(size*8/(time.monotonic()-start)/1e6)
else:
 while time.monotonic()-start<8:s.sendall(b'0'*8192)
s.close()
'''
        result=ns('python3','-c',code);worker.join(timeout=25)
        if direction=='download':observed[direction]=float(result)
    print('MEASURED_Mbps',json.dumps(observed))
    assert 2.0<observed['download']<3.4,observed
    assert 1.2<observed['upload']<2.3,observed
    assert next(c for c in req('/dashboard')['clients'] if c['id']==identifier)['active_estimated']
    print('PASS real handshake and independent shaping')
finally:
    subprocess.run(['ip','netns','del',namespace],capture_output=True)
    subprocess.run(['ip','link','del',link],capture_output=True)
    if identifier:req('/clients/'+identifier,'DELETE')
    req('/logout','POST')
assert before==hashlib.sha256(pathlib.Path('/etc/wireguard/clientes/jesus.conf').read_bytes()).hexdigest()
print('PASS test peer and namespace cleaned up; jesus unchanged')
