@echo off
echo ========================================
echo  🎮 Gamepad Monitor Overlay - Setup
echo ========================================
echo.

REM Verificar Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Python no encontrado. Instala Python 3.10+ primero.
    pause
    exit /b 1
)

echo ✅ Python encontrado
echo.

REM Instalar dependencias
echo 📦 Instalando dependencias...
pip install PyQt6 aiohttp --quiet

if errorlevel 1 (
    echo ❌ Error instalando dependencias
    pause
    exit /b 1
)

echo ✅ Dependencias instaladas
echo.

REM Crear acceso directo en Startup (opcional)
echo ¿Deseas que el overlay se inicie con Windows? (S/N)
set /p autostart="> "

if /i "%autostart%"=="S" (
    echo Creando acceso directo...
    
    set STARTUP=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup
    set SCRIPT_PATH=%~dp0gamepad_overlay.py
    
    echo Set oWS = WScript.CreateObject("WScript.Shell") > CreateShortcut.vbs
    echo sLinkFile = "%STARTUP%\Gamepad Overlay.lnk" >> CreateShortcut.vbs
    echo Set oLink = oWS.CreateShortcut(sLinkFile) >> CreateShortcut.vbs
    echo oLink.TargetPath = "pythonw" >> CreateShortcut.vbs
    echo oLink.Arguments = """%SCRIPT_PATH%""" >> CreateShortcut.vbs
    echo oLink.WorkingDirectory = "%~dp0" >> CreateShortcut.vbs
    echo oLink.Description = "Gamepad Monitor Overlay" >> CreateShortcut.vbs
    echo oLink.Save >> CreateShortcut.vbs
    cscript //nologo CreateShortcut.vbs
    del CreateShortcut.vbs
    
    echo ✅ Se iniciará con Windows
)

echo.
echo ========================================
echo  ✅ Instalación completada
echo ========================================
echo.
echo Para iniciar el overlay:
echo   python gamepad_overlay.py
echo.
echo O usa el archivo: run_overlay.bat
echo.
pause
