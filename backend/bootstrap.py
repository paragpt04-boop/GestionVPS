"""Run locally on VPS as root. Never print generated credentials."""
import os
import pathlib
import secrets
import sqlite3
import hashlib
import pwd

def bootstrap():
    os.umask(0o077)
    root=pathlib.Path('/var/lib/gestionvps-api'); root.mkdir(mode=0o700,exist_ok=True)
    account=pwd.getpwnam('gestionvps')
    os.chown(root,account.pw_uid,account.pw_gid)
    with sqlite3.connect(root/'auth.sqlite') as c:
        c.executescript('''CREATE TABLE IF NOT EXISTS admins(username TEXT PRIMARY KEY,salt TEXT,password_hash TEXT);
        CREATE TABLE IF NOT EXISTS sessions(token TEXT PRIMARY KEY,expires INTEGER);
        CREATE TABLE IF NOT EXISTS attempts(peer TEXT,ts INTEGER);''')
        if not c.execute('SELECT count(*) FROM admins').fetchone()[0]:
            password=secrets.token_urlsafe(24); salt=secrets.token_hex(16)
            hashed=hashlib.scrypt(password.encode(),salt=bytes.fromhex(salt),n=16384,r=8,p=1).hex()
            c.execute('INSERT INTO admins VALUES(?,?,?)',('admin',salt,hashed))
            pathlib.Path('/root/gestionvps-admin.txt').write_text('Usuario: admin\nContraseña: '+password+'\nAPI: https://107.178.51.31:8443\n')
    os.chown(root/'auth.sqlite',account.pw_uid,account.pw_gid)

if __name__=='__main__': bootstrap()
