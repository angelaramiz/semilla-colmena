"""Lanza reparar_ruti.ps1 en ruti y muestra el reporte. Uso: python lanzar_reparar.py"""
import os
import paramiko, sys, io, time
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

# Auth sin secretos en repo (protocol/seguridad.md): llave SSH primero
# (como comunicacion/comandante_mcp.py), env var como respaldo.
RUTI_HOST = os.getenv("RUTI_SSH_HOST", "100.114.102.85")
RUTI_USER = os.getenv("RUTI_SSH_USER", "agente")
RUTI_KEY = os.path.expanduser(os.getenv("RUTI_SSH_KEY", "~/.ssh/id_colmena"))
RUTI_PS1 = os.path.join(os.path.dirname(os.path.abspath(__file__)), "reparar_ruti.ps1")


def _conectar():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    if os.path.exists(RUTI_KEY):
        c.connect(RUTI_HOST, username=RUTI_USER, key_filename=RUTI_KEY, timeout=25)
        return c
    pwd = os.getenv("RUTI_SSH_PASSWORD")
    if pwd:
        c.connect(RUTI_HOST, username=RUTI_USER, password=pwd, timeout=25)
        return c
    sys.exit("ERROR: sin auth a ruti. Instala la llave SSH (~/.ssh/id_colmena, ver ~/.ssh/config)"
             " o define RUTI_SSH_PASSWORD. Cero passwords en el repo (protocol/seguridad.md).")


print('conectando a ruti...', flush=True)
c = _conectar()
sftp = c.open_sftp()
with open(RUTI_PS1, 'r', encoding='utf-8') as f:
    contenido = f.read()
with sftp.open('C:/Users/agente/reparar_ruti.ps1', 'w') as f:
    f.write(contenido)
sftp.close()
print('script subido, ejecutando (puede tardar varios minutos)...', flush=True)
stdin, stdout, stderr = c.exec_command('powershell -NoProfile -ExecutionPolicy Bypass -File C:\\Users\\agente\\reparar_ruti.ps1', timeout=900)
while not stdout.channel.exit_status_ready():
    time.sleep(5)
    if stdout.channel.recv_ready():
        print(stdout.channel.recv(4096).decode('utf-8', errors='replace'), end='', flush=True)
print(stdout.read().decode('utf-8', errors='replace'))
sftp = c.open_sftp()
script = "Get-Content C:\\Users\\agente\\reparar_ruti.log -ErrorAction SilentlyContinue | Select-Object -Last 30\n"
with sftp.open('C:/Users/agente/verrep.ps1', 'w') as f:
    f.write(script)
sftp.close()
stdin, stdout, stderr = c.exec_command('powershell -NoProfile -ExecutionPolicy Bypass -File C:\\Users\\agente\\verrep.ps1', timeout=60)
print('=== REPORTE ===')
print(stdout.read().decode('utf-8', errors='replace').strip())
c.close()