# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

# Archivos de datos a incluir
added_files = [
    ('frontend', 'frontend'),
    ('api_v2/readers', 'api_v2/readers'),
    ('api_v2/models', 'api_v2/models'),
    ('api_v2/utils', 'api_v2/utils'),
]

# Módulos ocultos que PyInstaller puede no detectar
hidden_imports = [
    'uvicorn.logging',
    'uvicorn.loops',
    'uvicorn.loops.auto',
    'uvicorn.protocols',
    'uvicorn.protocols.http',
    'uvicorn.protocols.http.auto',
    'uvicorn.protocols.websockets',
    'uvicorn.protocols.websockets.auto',
    'uvicorn.lifespan',
    'uvicorn.lifespan.on',
    'fastapi',
    'fastapi.middleware',
    'fastapi.middleware.cors',
    'fastapi.staticfiles',
    'pydantic',
    'pythonnet',
    'clr',
    'System',
    'hid',
    'hidapi',
    'sqlite3',
    'starlette.middleware',
    'starlette.middleware.cors',
    'starlette.staticfiles',
]

a = Analysis(
    ['gui_app.py'],
    pathex=[],
    binaries=[],
    datas=added_files,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

# Agregar todos los módulos de api_v2
api_v2_modules = [
    'api_v2/main.py',
    'api_v2/device_manager.py',
    'api_v2/db_manager.py',
    'api_v2/bluetooth_manager.py',
    'api_v2/alert_manager.py',
    'api_v2/cache_manager.py',
]

for module in api_v2_modules:
    a.datas += [(module, module, 'DATA')]

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='GamepadMonitor',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,  # Mostrar consola para debug
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,  # Puedes agregar un .ico aquí
)
