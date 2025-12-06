import hid

all_ds4 = [d for d in hid.enumerate(0x054C, 0x09CC)]
print(f'Total interfaces DS4: {len(all_ds4)}')

gamepads = [d for d in all_ds4 if d.get('usage_page') == 1 and d.get('usage') == 5]
print(f'Gamepad interfaces (usage_page=1, usage=5): {len(gamepads)}')

for i, d in enumerate(gamepads):
    print(f'\nGamepad {i+1}:')
    print(f'  Path: {d["path"].hex()}')
    print(f'  Serial: {d.get("serial_number", "N/A")}')
    print(f'  Interface: {d.get("interface_number", -1)}')

print(f'\nTodas las interfaces:')
for i, d in enumerate(all_ds4):
    print(f'\nInterface {i+1}:')
    print(f'  Path: {d["path"].hex()}')
    print(f'  Usage Page: {d.get("usage_page", -1)}')
    print(f'  Usage: {d.get("usage", -1)}')
    print(f'  Interface: {d.get("interface_number", -1)}')
    print(f'  Serial: {d.get("serial_number", "N/A")}')
