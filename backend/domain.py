import re
import unicodedata

def validate_client(data):
    name = unicodedata.normalize('NFC', str(data.get('name', ''))).strip()
    if not 1 <= len(name) <= 64 or any(unicodedata.category(c).startswith('C') for c in name):
        raise ValueError('Nombre: entre 1 y 64 caracteres, sin caracteres de control')
    down, up = data.get('download_mbps', 2), data.get('upload_mbps', 1)
    if type(down) is not int or type(up) is not int or not 1 <= down <= 1000 or not 1 <= up <= 1000:
        raise ValueError('Velocidades: números enteros entre 1 y 1000 Mbps')
    return name, down, up

def delta(previous, current, same_boot=True):
    return current - previous if same_boot and current >= previous else current

def safe_filename(name):
    value = re.sub(r'[^a-zA-Z0-9_-]', '_', name).strip('_')[:48]
    return (value or 'cliente') + '.conf'
