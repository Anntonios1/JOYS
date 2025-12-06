"""Script para listar dispositivos conectados"""
import hid

print('Dispositivos Sony (0x054C) conectados:')
print('=' * 50)
sony_found = False
for d in hid.enumerate():
    if d['vendor_id'] == 0x054C:
        sony_found = True
        pid = d['product_id']
        if pid == 0x05C4:
            name = 'DualShock 4 v1'
        elif pid == 0x09CC:
            name = 'DualShock 4 v2'
        elif pid == 0x0CE6:
            name = 'DualSense'
        elif pid == 0x0DF2:
            name = 'DualSense Edge'
        else:
            name = f'Unknown ({hex(pid)})'
        print(f'  {name}: PID={hex(pid)}, Page={d.get("usage_page")}, Usage={d.get("usage")}')

if not sony_found:
    print('  (ninguno)')

print()
print('Dispositivos Nintendo (0x057E) conectados:')
print('=' * 50)
nintendo_found = False
for d in hid.enumerate():
    if d['vendor_id'] == 0x057E:
        nintendo_found = True
        pid = d['product_id']
        if pid == 0x2006:
            name = 'Joy-Con (L)'
        elif pid == 0x2007:
            name = 'Joy-Con (R)'
        else:
            name = f'Unknown ({hex(pid)})'
        print(f'  {name}: PID={hex(pid)}')

if not nintendo_found:
    print('  (ninguno)')
