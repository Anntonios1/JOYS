# 🚀 INICIO RÁPIDO - Gamepad Monitor

## ⚡ Compilar en 1 Comando

```powershell
.\build.ps1
```

**Eso es todo!** El script hará todo automáticamente.

## 📦 Resultado

Después de 2-3 minutos tendrás:
```
dist/GamepadMonitor.exe  (~100 MB)
```

## ▶️ Ejecutar

```powershell
cd dist
.\GamepadMonitor.exe
```

O simplemente doble-click en el .exe

## 🎯 Lo Que Verás

Una ventana con:
- ✅ Consola de debug
- ✅ Estado del servidor
- ✅ Botón "Abrir en Navegador"
- ✅ Estadísticas en tiempo real

## 🌐 Acceder al Frontend

**Opción 1:** Click en "🌐 Abrir en Navegador"

**Opción 2:** Ir a http://localhost:8000

**Desde celular:** Usar la URL de "Red Local" (ej: http://192.168.1.5:8000)

## ⚠️ Si Hay Problemas

### Error al compilar
```powershell
pip install -r requirements_build.txt
.\build.ps1
```

### El .exe no inicia
```powershell
# Compilar con consola visible
# Editar gamepad_monitor.spec
# Cambiar: console=True
```

### Firewall bloquea
Windows pedirá permiso → **Permitir acceso**

## 📚 Documentación Completa

- `BUILD_INSTRUCTIONS.md` - Guía detallada de compilación
- `RESUMEN_SISTEMA.md` - Información del sistema completo
- `CACHE_SYSTEM.md` - Sistema de caché
- `ALERTS.md` - Sistema de alertas

## 🎮 Listo!

Eso es todo. El sistema está completo y listo para empaquetar.

---
**¿Dudas?** Revisa BUILD_INSTRUCTIONS.md
