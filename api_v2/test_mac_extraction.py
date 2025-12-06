import hid
import re

# Buscar Joy-Cons
devices = hid.enumerate(0x057E, 0)

for dev in devices:
    if dev['product_id'] in [0x2006, 0x2007]:
        path = dev['path']
        print(f"Joy-Con encontrado:")
        print(f"  Path: {path}")
        
        # Extraer MAC
        path_str = path.decode('utf-8') if isinstance(path, bytes) else path
        mac_match = re.search(r'[0-9A-Fa-f]{12}', path_str)
        
        if mac_match:
            mac = mac_match.group(0).upper()
            print(f"  MAC: {mac}")
        else:
            print(f"  MAC: No encontrada")
        print()
