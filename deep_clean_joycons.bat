@echo off
echo ========================================
echo LIMPIEZA PROFUNDA DE JOY-CONS
echo ========================================
echo.
echo Este script eliminara TODOS los emparejamientos
echo de Joy-Con y limpiara el cache de Bluetooth.
echo.
pause

echo.
echo [1/3] Deteniendo servicios...
net stop bthserv
timeout /t 2 /nobreak >nul

echo [2/3] Limpiando cache de Bluetooth...
del /F /Q "%SystemRoot%\System32\config\systemprofile\AppData\Local\Microsoft\Bluetooth\*" 2>nul
del /F /Q "%LocalAppData%\Microsoft\Bluetooth\*" 2>nul

echo [3/3] Reiniciando servicios...
net start bthserv
timeout /t 3 /nobreak >nul

echo.
echo ========================================
echo COMPLETO!
echo ========================================
echo.
echo SIGUIENTE PASO:
echo 1. Presiona el boton de sincronizacion en cada Joy-Con
echo 2. Ve a Configuracion - Bluetooth y dispositivos
echo 3. Agregar dispositivo - Bluetooth
echo 4. Selecciona cada Joy-Con
echo.
pause
