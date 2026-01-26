import base64
import re

def safe_base64_decode(base64_string):
    # 1. Supprime les caractères non-base64 (espaces, sauts de ligne, \r)
    # qui auraient pu être ajoutés par Git ou le protocole HTTP
    clean_string = re.sub(r'[^a-zA-Z0-9+/=]', '', base64_string)
    
    # 2. Corrige le "Padding" (les '=' à la fin) si nécessaire
    missing_padding = len(clean_string) % 4
    if missing_padding:
        clean_string += '=' * (4 - missing_padding)
        
    return base64.b64decode(clean_string)