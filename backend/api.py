"""Unprivileged HTTPS API. Only the Unix-socket agent can change WireGuard."""
import hashlib
import hmac
import json
import os
import pathlib
import secrets
import socket
import sqlite3
import time
from fastapi import Depends, FastAPI, Header, HTTPException, Request, Response
from pydantic import BaseModel, Field, StrictInt

STATE=pathlib.Path(os.environ.get('GESTIONVPS_API_STATE','/var/lib/gestionvps-api'))
app=FastAPI(title='GestionVPS',version='0.1.0',docs_url=None,redoc_url=None,openapi_url=None)

def database():
    c=sqlite3.connect(STATE/'auth.sqlite',timeout=15); c.row_factory=sqlite3.Row
    return c

def password_hash(password,salt):
    return hashlib.scrypt(password.encode(),salt=bytes.fromhex(salt),n=16384,r=8,p=1).hex()

class Login(BaseModel):
    username: str=Field(min_length=1,max_length=64)
    password: str=Field(min_length=1,max_length=256)

class Client(BaseModel):
    name: str=Field(min_length=1,max_length=64)
    download_mbps: StrictInt=Field(default=2,ge=1,le=1000)
    upload_mbps: StrictInt=Field(default=1,ge=1,le=1000)

def authenticate(authorization: str=Header(default='')):
    if not authorization.startswith('Bearer '): raise HTTPException(401,'Inicia sesión')
    digest=hashlib.sha256(authorization[7:].encode()).hexdigest()
    with database() as c:
        row=c.execute('SELECT * FROM sessions WHERE token=? AND expires>?',(digest,time.time())).fetchone()
    if not row: raise HTTPException(401,'Sesión expirada')
    return digest

def rpc(op,data=None):
    try:
        with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as s:
            s.settimeout(90); s.connect('/run/gestionvps/agent.sock')
            s.sendall((json.dumps({'op':op,'data':data or {}})+'\n').encode())
            response=json.loads(s.makefile('rb').readline(2*1024*1024))
        if not response['ok']: raise HTTPException(400,response['error'])
        return response['data']
    except (OSError,ValueError,KeyError): raise HTTPException(503,'Agente no disponible')

@app.middleware('http')
async def headers(request:Request,call_next):
    try: size=int(request.headers.get('content-length','0'))
    except ValueError: return Response(status_code=400)
    if size>8192: return Response(status_code=413)
    response=await call_next(request)
    response.headers['Cache-Control']='no-store'
    response.headers['X-Content-Type-Options']='nosniff'
    response.headers['Strict-Transport-Security']='max-age=31536000'
    return response

@app.get('/health')
def health(): return {'status':'ok','version':'0.1.0'}

@app.post('/login')
def login(body:Login,request:Request):
    # Persist rate limits across restarts. Use actual TCP peer, never X-Forwarded-For.
    peer=request.client.host if request.client else 'unknown'; now=int(time.time())
    with database() as c:
        c.execute('BEGIN IMMEDIATE')
        c.execute('DELETE FROM attempts WHERE ts<?',(now-900,))
        count=c.execute('SELECT count(*) FROM attempts WHERE peer=?',(peer,)).fetchone()[0]
        total=c.execute('SELECT count(*) FROM attempts').fetchone()[0]
        if count>=8 or total>=100: raise HTTPException(429,'Demasiados intentos; espera 15 minutos')
        c.execute('INSERT INTO attempts(peer,ts) VALUES(?,?)',(peer,now))
        row=c.execute('SELECT * FROM admins WHERE username=?',(body.username,)).fetchone()
    salt=row['salt'] if row else '00'*16
    candidate=password_hash(body.password,salt)
    if not row or not hmac.compare_digest(candidate,row['password_hash']): raise HTTPException(401,'Credenciales incorrectas')
    token=secrets.token_urlsafe(32); digest=hashlib.sha256(token.encode()).hexdigest()
    with database() as c:
        c.execute('DELETE FROM sessions WHERE expires<?',(now,))
        c.execute('INSERT INTO sessions VALUES(?,?)',(digest,now+3600))
        c.execute('DELETE FROM attempts WHERE peer=?',(peer,))
    return {'token':token,'expires_in':3600}

@app.post('/logout')
def logout(token=Depends(authenticate)):
    with database() as c: c.execute('DELETE FROM sessions WHERE token=?',(token,))
    return {'ok':True}

@app.get('/dashboard',dependencies=[Depends(authenticate)])
def dashboard(): return rpc('dashboard')

@app.get('/audit',dependencies=[Depends(authenticate)])
def audit(): return rpc('audit')

@app.get('/diagnostics',dependencies=[Depends(authenticate)])
def diagnostics(): return rpc('diagnostics')

@app.post('/clients',dependencies=[Depends(authenticate)])
def create(body:Client): return rpc('create',body.model_dump())

@app.put('/clients/{identifier}',dependencies=[Depends(authenticate)])
def update(identifier:str,body:Client): return rpc('update',{'id':identifier,**body.model_dump()})

@app.delete('/clients/{identifier}',dependencies=[Depends(authenticate)])
def delete(identifier:str): return rpc('delete',{'id':identifier})

@app.post('/clients/{identifier}/{operation}',dependencies=[Depends(authenticate)])
def operate(identifier:str,operation:str):
    if operation not in ('suspend','activate','rotate'): raise HTTPException(404,'Operación desconocida')
    return rpc(operation,{'id':identifier})

@app.get('/clients/{identifier}/profile',dependencies=[Depends(authenticate)])
def profile(identifier:str): return rpc('profile',{'id':identifier})

@app.get('/clients/{identifier}/traffic',dependencies=[Depends(authenticate)])
def traffic(identifier:str): return rpc('traffic',{'id':identifier})
